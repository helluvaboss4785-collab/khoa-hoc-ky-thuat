"""Ứng dụng Web 2.5D: Hệ thống đo độ mặn khúc xạ laser hai ngăn vi sai.

Cung cấp máy chủ ASGI (Starlette + Uvicorn) phục vụ giao diện HTML5/CSS3/JS 2.5D
và kết nối trực tiếp tới các mô-đun khoa học `core/` và `sim/`.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import math
import re
import sqlite3
import sys
import threading
import unicodedata
import urllib.parse
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pandas as pd
import uvicorn
import yaml
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Message, Receive, Scope, Send

THU_MUC_GOC = Path(__file__).resolve().parents[1]
if str(THU_MUC_GOC) not in sys.path:
    sys.path.insert(0, str(THU_MUC_GOC))

from core import calibration as cal
from core import optics as op
from core import thang
from core import thresholds as th
from core.measure import (
    AnhKhongHopLeError,
    KetQuaDoDeltaY,
    KhongTimThayVachError,
    chuyen_anh_xam,
    do_delta_y_da_khung_hinh,
    do_delta_y_tu_anh,
)
from sim.synth import (
    ThamSoMoPhong,
    sinh_anh_hai_vach_mo_phong,
    sinh_du_lieu_hieu_chuan_mo_phong,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
DB_PATH = THU_MUC_GOC / "data" / "nhat_ki_do.db"
CONFIG_PATH = THU_MUC_GOC / "config.yaml"
OUTPUTS_DIR = THU_MUC_GOC / "outputs"
HE_SO_JSON_PATH = OUTPUTS_DIR / "he_so_hieu_chuan.json"
HE_SO_MP_PATH = OUTPUTS_DIR / "he_so_hieu_chuan_MO_PHONG.json"

CSV_TEMPLATE_7_COT = (
    "do_man_chuan_ppt,nhiet_do_C,nhiet_do_tham_chieu_C,delta_y_px,px_per_mm,do_duc_tuong_doi,"
    "ma_me_pha,ngay_do,ghi_chu,id_thiet_bi,id_dien_thoai,nguon_du_lieu,khoa_ae_af\n"
)


# ---------------------------------------------------------------------------
# Quản lí cấu hình, mô hình và tuần tự hóa JSON an toàn
# ---------------------------------------------------------------------------
def _to_jsonable(obj: Any) -> Any:
    """Chuyển đổi các kiểu NumPy/Pandas/NaN sang cấu trúc JSON chuẩn hợp lệ."""
    if obj is None or isinstance(obj, (str, bool, int)):
        return obj
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        val = float(obj)
        return val if math.isfinite(val) else None
    if isinstance(obj, np.ndarray):
        return [_to_jsonable(x) for x in obj.tolist()]
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    return str(obj)


def _json_ok(data: Any, status_code: int = 200) -> JSONResponse:
    return JSONResponse(_to_jsonable(data), status_code=status_code)


def _json_err(message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status_code)


def _json_err_typed(
    status_code: int,
    loai_loi: str,
    message: str,
    exc: Exception | None = None,
) -> JSONResponse:
    payload: dict[str, Any] = {"error": message, "loai_loi": loai_loi}
    if exc is not None:
        payload["chi_tiet_ky_thuat"] = str(exc)
    return JSONResponse(payload, status_code=status_code)


_CONFIG_CACHE: dict[str, Any] = {
    "sig": None,
    "optics": None,
    "species": None,
    "calib": None,
    "image": None,
    "species_serialized": None,
}


def _config_file_sig() -> tuple[int, int] | None:
    try:
        st = CONFIG_PATH.stat()
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def invalidate_config_cache() -> None:
    _CONFIG_CACHE["sig"] = None
    _CONFIG_CACHE["optics"] = None
    _CONFIG_CACHE["species"] = None
    _CONFIG_CACHE["calib"] = None
    _CONFIG_CACHE["image"] = None
    _CONFIG_CACHE["species_serialized"] = None


def _ensure_config_cache() -> None:
    sig = _config_file_sig()
    if sig is not None and _CONFIG_CACHE["sig"] == sig and _CONFIG_CACHE["optics"] is not None:
        return
    cfg_opt = op.CauHinhQuangHoc.tu_yaml(CONFIG_PATH)
    ds_loai = th.doc_danh_sach_loai(CONFIG_PATH)
    cfg_cal = cal.CauHinhHieuChuan.tu_yaml(CONFIG_PATH)
    raw_yaml = {}
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, encoding="utf-8") as f:
            raw_yaml = yaml.safe_load(f) or {}
    img_raw = raw_yaml.get("xu_ly_anh", {}) or {}
    _CONFIG_CACHE["sig"] = sig
    _CONFIG_CACHE["optics"] = cfg_opt
    _CONFIG_CACHE["species"] = ds_loai
    _CONFIG_CACHE["calib"] = cfg_cal
    _CONFIG_CACHE["image"] = {
        "nguong_bao_hoa": int(img_raw.get("nguong_bao_hoa", 250)),
        "ti_le_bao_hoa_toi_da": float(img_raw.get("ti_le_bao_hoa_toi_da", 0.02)),
        "snr_toi_thieu": float(img_raw.get("snr_toi_thieu", 10.0)),
    }
    _CONFIG_CACHE["species_serialized"] = None


def load_image_config() -> dict[str, Any]:
    _ensure_config_cache()
    return dict(_CONFIG_CACHE["image"] or {})


def load_config() -> op.CauHinhQuangHoc:
    _ensure_config_cache()
    return _CONFIG_CACHE["optics"]


def load_species_map() -> dict[str, th.ThongTinLoai]:
    _ensure_config_cache()
    return _CONFIG_CACHE["species"]


def load_calib_config() -> cal.CauHinhHieuChuan:
    _ensure_config_cache()
    return _CONFIG_CACHE["calib"]


def load_serialized_species() -> list[dict[str, Any]]:
    _ensure_config_cache()
    cached = _CONFIG_CACHE["species_serialized"]
    if cached is None:
        cached = [_serialize_species(v) for v in _CONFIG_CACHE["species"].values()]
        _CONFIG_CACHE["species_serialized"] = cached
    return cached


def load_initial_model() -> cal.MoHinhHieuChuan:
    if HE_SO_JSON_PATH.exists():
        return cal.MoHinhHieuChuan.doc_json(HE_SO_JSON_PATH)
    if HE_SO_MP_PATH.exists():
        return cal.MoHinhHieuChuan.doc_json(HE_SO_MP_PATH)
    df_mp = sinh_du_lieu_hieu_chuan_mo_phong(cfg=load_config(), seed=0)
    bc = cal.dung_duong_chuan(df_mp, load_calib_config())
    OUTPUTS_DIR.mkdir(exist_ok=True)
    bc.mo_hinh.luu_json(HE_SO_MP_PATH)
    return bc.mo_hinh


APP_STATE: dict[str, Any] = {
    "mo_hinh": load_initial_model(),
    "mo_hinh_theo_ho_so": {},
}


def _clean_ho_so(raw: str | None) -> str:
    """Chuẩn hóa tên hồ sơ hộ nuôi / xưởng (mặc định 'mac_dinh')."""
    if raw is None:
        return "mac_dinh"
    s = re.sub(r"[\r\n\t]+", " ", str(raw)).strip()
    if not s or s.lower() == "default":
        return "mac_dinh"
    return s[:60]


def _slug_ho_so(ho_so: str) -> str:
    """Tạo định danh ASCII an toàn để đặt tên file JSON theo hồ sơ."""
    s = unicodedata.normalize("NFKD", ho_so.replace("đ", "d").replace("Đ", "D"))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", s).strip("_").lower()
    return (slug[:40] if slug else "mac_dinh")


def _model_suffix(la_mo_phong: bool, da_xac_nhan_thuc_te: bool) -> str:
    if la_mo_phong:
        return "_MO_PHONG"
    if not da_xac_nhan_thuc_te:
        return "_CHUA_XAC_NHAN"
    return ""


def _model_path_for_profile(
    ho_so: str, la_mo_phong: bool, da_xac_nhan_thuc_te: bool = True
) -> Path:
    clean = _clean_ho_so(ho_so)
    suffix = _model_suffix(la_mo_phong, da_xac_nhan_thuc_te)
    if clean == "mac_dinh":
        return OUTPUTS_DIR / f"he_so_hieu_chuan{suffix}.json"
    return OUTPUTS_DIR / f"he_so_hieu_chuan_{_slug_ho_so(clean)}{suffix}.json"


def get_model_for_profile(ho_so: str | None = None) -> cal.MoHinhHieuChuan:
    clean = _clean_ho_so(ho_so)
    if clean == "mac_dinh":
        return APP_STATE["mo_hinh"]
    cache: dict[str, cal.MoHinhHieuChuan] = APP_STATE.setdefault("mo_hinh_theo_ho_so", {})
    if clean in cache:
        return cache[clean]
    for is_sim, verified in ((False, True), (False, False), (True, False)):
        p = _model_path_for_profile(clean, is_sim, verified)
        if p.exists():
            mh = cal.MoHinhHieuChuan.doc_json(p)
            cache[clean] = mh
            return mh
    return APP_STATE["mo_hinh"]


def set_model_for_profile(ho_so: str | None, mh: cal.MoHinhHieuChuan) -> Path:
    clean = _clean_ho_so(ho_so)
    OUTPUTS_DIR.mkdir(exist_ok=True)
    luu_path = _model_path_for_profile(clean, mh.la_mo_phong, mh.da_xac_nhan_thuc_te)
    mh.luu_json(luu_path)
    if clean == "mac_dinh":
        APP_STATE["mo_hinh"] = mh
    else:
        APP_STATE.setdefault("mo_hinh_theo_ho_so", {})[clean] = mh
    return luu_path


def _req_ho_so(request: Request, body: dict[str, Any] | None = None) -> str:
    if body and body.get("ho_so"):
        return _clean_ho_so(str(body.get("ho_so")))
    q = request.query_params.get("ho_so")
    if q:
        return _clean_ho_so(q)
    hdr = request.headers.get("X-Ho-So")
    if hdr:
        return _clean_ho_so(urllib.parse.unquote(hdr))
    return "mac_dinh"


def _format_equation(mh: cal.MoHinhHieuChuan) -> str:
    terms = [f"({c:+.5g})·{h}" for h, c in zip(mh.hang, mh.he_so)]
    ghi_chu = [f"ΔT = T − {mh.T_ref:g} °C"]
    if getattr(mh, "co_bu_chenh_T", False):
        ghi_chu.append("D = T_mẫu − T_tc")
    dv = getattr(mh, "don_vi_y", "px")
    return f"Δy ({dv}) = {' + '.join(terms)}   [{'; '.join(ghi_chu)}]"


def _serialize_model(mh: cal.MoHinhHieuChuan) -> dict[str, Any]:
    d = mh.sang_dict()
    d["phuong_trinh"] = _format_equation(mh)
    return d


# ---------------------------------------------------------------------------
# Cơ sở dữ liệu SQLite Nhật kí đo
# ---------------------------------------------------------------------------
_DB_INIT_PATH: Path | None = None


def khoi_tao_db(force: bool = False) -> None:
    global _DB_INIT_PATH
    if not force and _DB_INIT_PATH == DB_PATH and DB_PATH.exists():
        return
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS nhat_ki (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thoi_gian TEXT,
                vi_tri TEXT,
                loai_nuoi TEXT,
                delta_y_px REAL,
                do_man_ppt REAL,
                bat_dinh_U_ppt REAL,
                nhiet_do_C REAL,
                do_duc REAL,
                chat_luong_hop_le INTEGER,
                nguon_du_lieu TEXT,
                ghi_chu TEXT,
                ho_so TEXT DEFAULT 'mac_dinh'
            )
        """)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(nhat_ki)").fetchall()}
        if "ho_so" not in cols:
            conn.execute("ALTER TABLE nhat_ki ADD COLUMN ho_so TEXT DEFAULT 'mac_dinh'")
        for col_name, col_def in (
            ("px_per_mm", "REAL"),
            ("delta_y_mm", "REAL"),
            ("khoa_ae_af", "INTEGER DEFAULT 0"),
            ("exif_exposure", "TEXT DEFAULT ''"),
            ("exif_iso", "INTEGER"),
        ):
            if col_name not in cols:
                conn.execute(f"ALTER TABLE nhat_ki ADD COLUMN {col_name} {col_def}")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_nhat_ki_ho_so ON nhat_ki(ho_so)")
    _DB_INIT_PATH = DB_PATH


def _tom_tat_nhat_ki_nhanh(ho_so: str) -> tuple[int, list[str]]:
    """Đếm số bản ghi và lấy danh sách vị trí theo hồ sơ trực tiếp bằng SQL (không tải Pandas)."""
    khoi_tao_db()
    hs = _clean_ho_so(ho_so)
    with sqlite3.connect(DB_PATH) as conn:
        row_cnt = conn.execute(
            "SELECT COUNT(*) FROM nhat_ki WHERE COALESCE(NULLIF(TRIM(ho_so), ''), 'mac_dinh') = ?",
            (hs,),
        ).fetchone()
        loc_rows = conn.execute(
            "SELECT DISTINCT vi_tri FROM nhat_ki "
            "WHERE COALESCE(NULLIF(TRIM(ho_so), ''), 'mac_dinh') = ? "
            "AND vi_tri IS NOT NULL AND TRIM(vi_tri) != '' ORDER BY vi_tri",
            (hs,),
        ).fetchall()
    return int(row_cnt[0] if row_cnt else 0), [str(r[0]) for r in loc_rows]


def luu_nhat_ki(
    vi_tri: str,
    loai_nuoi: str,
    delta_y_px: float,
    do_man_ppt: float,
    bat_dinh_U_ppt: float,
    nhiet_do_C: float,
    do_duc: float,
    chat_luong_hop_le: bool,
    nguon_du_lieu: str,
    ghi_chu: str,
    thoi_gian_tuy_chinh: str | None = None,
    ho_so: str = "mac_dinh",
    px_per_mm: float | None = None,
    delta_y_mm: float | None = None,
    khoa_ae_af: bool = False,
    exif_exposure: str = "",
    exif_iso: int | None = None,
) -> int:
    khoi_tao_db()
    tg = thoi_gian_tuy_chinh or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    hs = _clean_ho_so(ho_so)
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            """
            INSERT INTO nhat_ki (
                thoi_gian, vi_tri, loai_nuoi, delta_y_px, do_man_ppt,
                bat_dinh_U_ppt, nhiet_do_C, do_duc, chat_luong_hop_le,
                nguon_du_lieu, ghi_chu, ho_so,
                px_per_mm, delta_y_mm, khoa_ae_af, exif_exposure, exif_iso
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tg,
                vi_tri,
                loai_nuoi,
                delta_y_px,
                do_man_ppt,
                bat_dinh_U_ppt,
                nhiet_do_C,
                do_duc,
                1 if chat_luong_hop_le else 0,
                nguon_du_lieu,
                ghi_chu,
                hs,
                px_per_mm,
                delta_y_mm,
                1 if khoa_ae_af else 0,
                exif_exposure or "",
                exif_iso,
            ),
        )
        return int(cur.lastrowid or 0)


def doc_lich_su_df(
    loai: str | None = None,
    nguon: str | None = None,
    vi_tri: str | None = None,
    ho_so: str | None = "mac_dinh",
) -> pd.DataFrame:
    khoi_tao_db()
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query("SELECT * FROM nhat_ki ORDER BY id DESC", conn)
    if "ho_so" not in df.columns:
        df["ho_so"] = "mac_dinh"
    else:
        df["ho_so"] = df["ho_so"].fillna("mac_dinh").replace("", "mac_dinh")
    if ho_so and ho_so != "ALL":
        hs = _clean_ho_so(ho_so)
        df = df[df["ho_so"] == hs]
    if loai and loai != "ALL":
        df = df[df["loai_nuoi"] == loai]
    if nguon and nguon != "ALL":
        df = df[df["nguon_du_lieu"] == nguon]
    if vi_tri and vi_tri != "ALL":
        df = df[df["vi_tri"] == vi_tri]
    return df


def lay_danh_sach_ho_so() -> list[str]:
    """Trả về danh sách các hồ sơ đã lưu trong CSDL (luôn bắt đầu bằng 'mac_dinh')."""
    khoi_tao_db()
    profiles: set[str] = set(APP_STATE.get("mo_hinh_theo_ho_so", {}).keys())
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT DISTINCT COALESCE(NULLIF(TRIM(ho_so), ''), 'mac_dinh') FROM nhat_ki"
        ).fetchall()
    for (p,) in rows:
        if p and p != "mac_dinh":
            profiles.add(str(p))
    return ["mac_dinh", *sorted(profiles)]


def xoa_nhat_ki_theo_id(row_id: int, ho_so: str | None = None) -> int:
    """Xóa một bản ghi theo id (có thể giới hạn theo hồ sơ). Trả về số dòng đã xóa (0 hoặc 1)."""
    khoi_tao_db()
    with sqlite3.connect(DB_PATH) as conn:
        if ho_so and ho_so != "ALL":
            hs = _clean_ho_so(ho_so)
            cur = conn.execute(
                "DELETE FROM nhat_ki WHERE id = ? AND COALESCE(NULLIF(TRIM(ho_so), ''), 'mac_dinh') = ?",
                (row_id, hs),
            )
        else:
            cur = conn.execute("DELETE FROM nhat_ki WHERE id = ?", (row_id,))
        return int(cur.rowcount or 0)


def nap_nhat_ki_mau_mo_phong(mh: cal.MoHinhHieuChuan, ho_so: str = "mac_dinh") -> int:
    khoi_tao_db()
    rng = np.random.default_rng(2026)
    now = datetime.now()
    hs = _clean_ho_so(ho_so)
    cac_muc_s = [12.5, 13.2, 14.8, 16.0, 17.5, 19.2, 21.0, 23.5, 20.4, 18.0]
    rows_to_insert = []
    for idx, s_val in enumerate(cac_muc_s):
        tg = (now - timedelta(hours=(len(cac_muc_s) - idx) * 6)).strftime("%Y-%m-%d %H:%M:%S")
        t_val = float(np.round(25.0 + rng.normal(0, 1.2), 1))
        dy_val = float(mh.du_doan_delta_y(s_val, t_val)[0]) + float(rng.normal(0, 0.06))
        u_val = float(np.round(0.18 + rng.uniform(0, 0.08), 2))
        duc_val = float(np.round(rng.uniform(0.05, 0.35), 2))
        rows_to_insert.append((
            tg,
            "Ao nuôi tôm số 1 (Mẫu thử)",
            "Tôm thẻ chân trắng (Litopenaeus vannamei)",
            round(dy_val, 2),
            round(s_val, 2),
            u_val,
            t_val,
            duc_val,
            1,
            "MÔ PHỎNG",
            f"Quan trắc định kì lần {idx + 1} (Dữ liệu mô phỏng)",
            hs,
        ))
    with sqlite3.connect(DB_PATH) as conn:
        conn.executemany(
            """
            INSERT INTO nhat_ki (
                thoi_gian, vi_tri, loai_nuoi, delta_y_px, do_man_ppt,
                bat_dinh_U_ppt, nhiet_do_C, do_duc, chat_luong_hop_le,
                nguon_du_lieu, ghi_chu, ho_so
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows_to_insert,
        )
    return len(rows_to_insert)


# ---------------------------------------------------------------------------
# Hàm phụ trợ cho ngưỡng loài & đo ảnh
# ---------------------------------------------------------------------------
def _serialize_species(loai: th.ThongTinLoai) -> dict[str, Any]:
    s_max_scale = max(
        40.0,
        (loai.nguy_hiem_tren or 0.0) * 1.25,
        (loai.an_toan_max or 0.0) * 1.5,
    )
    if s_max_scale <= 5.0:
        s_max_scale = 4.0

    ng_duoi_str = f"< {loai.nguy_hiem_duoi:g} ‰" if loai.nguy_hiem_duoi is not None else "Không"
    ng_tren_str = f"> {loai.nguy_hiem_tren:g} ‰" if loai.nguy_hiem_tren is not None else "Không"
    an_toan_str = (
        f"{loai.an_toan_min:g} – {loai.an_toan_max:g} ‰"
        if loai.an_toan_min is not None and loai.an_toan_max is not None
        else "Chưa có"
    )
    cb_thap_str = f"{loai.canh_bao_thap[0]:g} – {loai.canh_bao_thap[1]:g} ‰" if loai.canh_bao_thap else "Không"
    cb_cao_str = f"{loai.canh_bao_cao[0]:g} – {loai.canh_bao_cao[1]:g} ‰" if loai.canh_bao_cao else "Không"

    return {
        "ma_loai": loai.ma_loai,
        "ten_hien_thi": loai.ten_hien_thi,
        "co_du_lieu_nguon": loai.co_du_lieu_nguon,
        "an_toan_min": loai.an_toan_min,
        "an_toan_max": loai.an_toan_max,
        "canh_bao_thap": list(loai.canh_bao_thap) if loai.canh_bao_thap else None,
        "canh_bao_cao": list(loai.canh_bao_cao) if loai.canh_bao_cao else None,
        "nguy_hiem_duoi": loai.nguy_hiem_duoi,
        "nguy_hiem_tren": loai.nguy_hiem_tren,
        "nguon_tham_khao": loai.nguon_tham_khao,
        "s_max_scale": s_max_scale,
        "an_toan_str": an_toan_str,
        "cb_thap_str": cb_thap_str,
        "cb_cao_str": cb_cao_str,
        "nguy_hiem_str": f"Dưới: {ng_duoi_str} | Trên: {ng_tren_str}",
    }


def _evaluate_species_detail(S_ppt: float, loai: th.ThongTinLoai, U: float = 0.0) -> dict[str, Any]:
    dg = th.danh_gia_do_man_loai(S_ppt, loai, U=U)
    info = _serialize_species(loai)

    pho = None
    if loai.co_du_lieu_nguon and loai.an_toan_min is not None and loai.an_toan_max is not None:
        s_max_scale = max(
            40.0,
            (loai.nguy_hiem_tren or 0.0) * 1.25,
            (loai.an_toan_max or 0.0) * 1.5,
            S_ppt * 1.15,
        )
        if s_max_scale <= 5.0 and S_ppt <= 4.5:
            s_max_scale = 4.0

        def pct(val: float) -> float:
            return max(0.0, min(100.0, (val / s_max_scale) * 100.0))

        p_nguy_duoi = pct(loai.nguy_hiem_duoi or 0.0)
        p_at_min = pct(loai.an_toan_min)
        p_at_max = pct(loai.an_toan_max)
        p_nguy_tren = pct(loai.nguy_hiem_tren if loai.nguy_hiem_tren is not None else s_max_scale)
        p_cur = max(2.0, min(98.0, pct(S_ppt)))
        pho = {
            "s_max_scale": s_max_scale,
            "p_cur": p_cur,
            "w1": p_nguy_duoi,
            "w2": max(0.0, p_at_min - p_nguy_duoi),
            "w3": max(0.0, p_at_max - p_at_min),
            "w4": max(0.0, p_nguy_tren - p_at_max),
            "w5": max(0.0, 100.0 - p_nguy_tren),
        }

    return {
        "ma_loai": dg.ma_loai,
        "ten_loai": dg.ten_loai,
        "trang_thai": dg.trang_thai,
        "mau_sac": dg.mau_sac,
        "tieu_de": dg.tieu_de,
        "loi_khuyen": dg.loi_khuyen,
        "nguon_tham_khao": dg.nguon_tham_khao,
        "pho": pho,
        "info": info,
    }


def _decode_base64_image_bytes(b64_str: str) -> tuple[np.ndarray, bytes]:
    try:
        if "," in b64_str:
            b64_str = b64_str.split(",", 1)[1]
        raw = base64.b64decode(b64_str, validate=False)
        arr = np.frombuffer(raw, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR) if arr.size > 0 else None
    except Exception as exc:
        raise AnhKhongHopLeError("Không giải mã được dữ liệu ảnh base64 tải lên.") from exc
    if img is None or img.size == 0:
        raise AnhKhongHopLeError("Không giải mã được định dạng ảnh tải lên.")
    return img, raw


def _decode_base64_image(b64_str: str) -> np.ndarray:
    img, _ = _decode_base64_image_bytes(b64_str)
    return img


def _encode_preview_b64(img_bgr: np.ndarray, max_width: int = 960) -> str:
    """Mã hóa ảnh đánh dấu để hiển thị gọn nhẹ trên web/di động (WebP ~25x nhỏ hơn PNG).

    Chỉ thu gọn chiều ngang cho bản xem trước khi ảnh gốc quá lớn (> max_width);
    không ảnh hưởng tới ảnh gốc dùng để đo tâm vạch Δy.
    """
    h, w = img_bgr.shape[:2]
    preview = img_bgr
    if w > max_width:
        scale = max_width / float(w)
        preview = cv2.resize(
            img_bgr,
            (max_width, max(1, int(round(h * scale)))),
            interpolation=cv2.INTER_AREA,
        )
    ok, buf = cv2.imencode(".webp", preview, [cv2.IMWRITE_WEBP_QUALITY, 86])
    if ok:
        return "data:image/webp;base64," + base64.b64encode(buf.tobytes()).decode("ascii")
    ok, buf = cv2.imencode(".png", preview, [cv2.IMWRITE_PNG_COMPRESSION, 6])
    if not ok:
        raise ValueError("Không mã hóa được ảnh kết quả.")
    return "data:image/png;base64," + base64.b64encode(buf.tobytes()).decode("ascii")


def _extract_profile_data(anh_bgr: np.ndarray, kq: KetQuaDoDeltaY) -> dict[str, Any]:
    anh_xam = chuyen_anh_xam(anh_bgr)
    h, w = anh_xam.shape
    col_tc = int(np.clip(round(kq.vach_tham_chieu.x_ref), 0, w - 1))
    col_m = int(np.clip(round(kq.vach_mau.x_ref), 0, w - 1))
    if kq.vach_tham_chieu.danh_sach_x:
        col_tc = int(np.clip(round(float(np.median(kq.vach_tham_chieu.danh_sach_x))), 0, w - 1))
    if kq.vach_mau.danh_sach_x:
        col_m = int(np.clip(round(float(np.median(kq.vach_mau.danh_sach_x))), 0, w - 1))

    # Nếu ảnh chụp điện thoại rất cao (>800px), lấy mẫu đều cho đồ thị mặt cắt để JSON nhỏ gọn
    stride_y = max(1, h // 600) if h > 800 else 1
    y_coords = list(range(0, h, stride_y))
    prof_tc = anh_xam[::stride_y, col_tc].tolist()
    prof_mau = anh_xam[::stride_y, col_m].tolist()

    return {
        "height": h,
        "width": w,
        "col_tc": col_tc,
        "col_mau": col_m,
        "y_coords": y_coords,
        "prof_tc": prof_tc,
        "prof_mau": prof_mau,
        "y_tam_tc": round(float(kq.vach_tham_chieu.y_tam), 4),
        "y_tam_mau": round(float(kq.vach_mau.y_tam), 4),
        "x_ref": round(float(kq.x_ref), 2),
        "x_tc": [round(float(v), 1) for v in kq.vach_tham_chieu.danh_sach_x],
        "y_tc": [round(float(v), 2) for v in kq.vach_tham_chieu.danh_sach_y],
        "x_mau": [round(float(v), 1) for v in kq.vach_mau.danh_sach_x],
        "y_mau": [round(float(v), 2) for v in kq.vach_mau.danh_sach_y],
        "do_doc_tc": float(kq.vach_tham_chieu.do_doc_a),
        "he_so_b_tc": float(kq.vach_tham_chieu.he_so_b),
        "do_doc_mau": float(kq.vach_mau.do_doc_a),
        "he_so_b_mau": float(kq.vach_mau.he_so_b),
    }


def _serialize_line_fit(vach: Any) -> dict[str, Any]:
    return {
        "x_ref": vach.x_ref,
        "y_tam": vach.y_tam,
        "sai_so_y": vach.sai_so_y,
        "do_doc_a": vach.do_doc_a,
        "he_so_b": vach.he_so_b,
        "fwhm_trung_binh": vach.fwhm_trung_binh,
        "cuong_do_dinh_tb": vach.cuong_do_dinh_tb,
        "r2_trung_binh": vach.r2_trung_binh,
        "so_cot_hop_le": vach.so_cot_hop_le,
        "so_cot_tong": vach.so_cot_tong,
        "phuong_phap": vach.phuong_phap,
        "so_cot_bi_loai_ngoai_lai": getattr(vach, "so_cot_bi_loai_ngoai_lai", 0),
        "so_cot_dung_centroid": getattr(vach, "so_cot_dung_centroid", 0),
    }


# ---------------------------------------------------------------------------
# Routes HTTP & API Endpoints
# ---------------------------------------------------------------------------
async def index(request: Request) -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


async def favicon(request: Request) -> FileResponse:
    return FileResponse(STATIC_DIR / "favicon.png", media_type="image/png")


async def manifest_json(request: Request) -> FileResponse:
    return FileResponse(STATIC_DIR / "manifest.json", media_type="application/manifest+json")


async def service_worker_js(request: Request) -> FileResponse:
    return FileResponse(
        STATIC_DIR / "sw.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache"},
    )


async def api_bootstrap(request: Request) -> JSONResponse:
    ho_so = _req_ho_so(request)
    cfg = load_config()
    mh: cal.MoHinhHieuChuan = get_model_for_profile(ho_so)
    so_ban_ghi, all_locations = _tom_tat_nhat_ki_nhanh(ho_so)
    try:
        sens_default = op.pixel_moi_phan_nghin(15.0, cfg.T_tham_chieu_C, cfg)
    except Exception:
        sens_default = 0.0

    return _json_ok({
        "ho_so_hien_tai": ho_so,
        "all_profiles": lay_danh_sach_ho_so(),
        "all_locations": all_locations,
        "mo_hinh": _serialize_model(mh),
        "quang_hoc": {
            "A_do": cfg.A_do,
            "D_m": cfg.D_m,
            "n_nuoc_ngot": cfg.n_nuoc_ngot,
            "dn_dS": cfg.dn_dS,
            "dn_dT": cfg.dn_dT,
            "T_tham_chieu_C": cfg.T_tham_chieu_C,
            "bien_TIR": cfg.bien_TIR,
            "pixel_mm": cfg.pixel_mm,
            "lambda_nm": 650,
            "do_nhay_mac_dinh": sens_default,
        },
        "danh_sach_loai": load_serialized_species(),
        "so_ban_ghi_nhat_ki": so_ban_ghi,
        "han_che_nacl": cal.HAN_CHE_NACL,
        "nhan_chua_hieu_chuan": cal.NHAN_CHUA_HIEU_CHUAN,
    })


async def api_measure(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return _json_err("Dữ liệu JSON gửi lên không hợp lệ.")

    mode = str(body.get("mode", "sim"))
    ho_so = _req_ho_so(request, body)
    cfg = load_config()
    mh: cal.MoHinhHieuChuan = get_model_for_profile(ho_so)
    chan_li_mp: dict[str, Any] | None = None
    la_anh_mo_phong = mode == "sim"

    try:
        khong_do_nhiet_do = bool(body.get("khong_do_nhiet_do", False))
        raw_t = body.get("nhiet_do_do")
        if not khong_do_nhiet_do:
            if raw_t is None or (isinstance(raw_t, str) and not raw_t.strip()):
                return _json_err(
                    "Vui lòng nhập nhiệt độ mẫu nước (°C) hoặc chọn 'Không đo nhiệt độ'.",
                    400,
                )
            try:
                nhiet_do_do = float(raw_t)
            except (TypeError, ValueError):
                return _json_err("Nhiệt độ mẫu nước không hợp lệ.", 400)
            if not math.isfinite(nhiet_do_do):
                return _json_err("Nhiệt độ mẫu nước không hợp lệ.", 400)
        else:
            nhiet_do_do = float(mh.T_ref)

        raw_t_ref = body.get("nhiet_do_tham_chieu")
        if raw_t_ref is None or (isinstance(raw_t_ref, str) and not raw_t_ref.strip()):
            nhiet_do_tham_chieu = None
        else:
            try:
                nhiet_do_tham_chieu = float(raw_t_ref)
            except (TypeError, ValueError):
                return _json_err("Nhiệt độ ngăn tham chiếu không hợp lệ.", 400)
            if not math.isfinite(nhiet_do_tham_chieu):
                return _json_err("Nhiệt độ ngăn tham chiếu không hợp lệ.", 400)

        exif_info: dict[str, Any] = {}
        if mode == "sim":
            s_mp = float(body.get("S_ppt", 16.5))
            t_mp = float(body.get("T_C", nhiet_do_do))
            t_tc_mp = float(body.get("T_tham_chieu_C", nhiet_do_tham_chieu if nhiet_do_tham_chieu is not None else t_mp))
            do_duc = float(body.get("do_duc", 0.15))
            drift_px = float(body.get("drift_px", 4.0))
            bo_tri = "doc" if body.get("bo_tri") == "doc" else "ngang"
            cho_phep_bao_hoa = bool(body.get("cho_phep_bao_hoa", False))
            seed = int(body.get("seed", 42))

            p_synth = ThamSoMoPhong(
                S_ppt=s_mp,
                T_C=t_mp,
                T_tham_chieu_C=t_tc_mp,
                drift_chung_px=drift_px,
                do_duc=do_duc,
                bo_tri=bo_tri,
                cho_phep_bao_hoa=cho_phep_bao_hoa,
                seed=seed,
            )
            anh_mp_obj = sinh_anh_hai_vach_mo_phong(p_synth, cfg, gan_watermark=False)
            anh_input = cv2.cvtColor(anh_mp_obj.anh, cv2.COLOR_GRAY2BGR)
            chan_li_mp = {
                "S_chan_li": s_mp,
                "T_chan_li": t_mp,
                "T_tc_chan_li": t_tc_mp,
                "delta_y_snell": anh_mp_obj.delta_y_ly_thuyet_px,
                "drift_px": drift_px,
            }
        elif mode == "upload":
            image_b64 = body.get("image_base64")
            if not image_b64 or not isinstance(image_b64, str):
                return _json_err("Chưa cung cấp ảnh (image_base64) để đo.")
            anh_input, raw_img_bytes = _decode_base64_image_bytes(image_b64)
            exif_info = thang.doc_exif_phoi_sang(raw_img_bytes)
        else:
            return _json_err(f"Chế độ đo '{mode}' không được hỗ trợ.")

        khoa_ae_af = bool(body.get("khoa_ae_af", False))
        thang_anh_dict: dict[str, Any] | None = None
        px_per_mm_val: float | None = None
        u_px_per_mm_val = 0.0

        d1 = body.get("diem_thang_1")
        d2 = body.get("diem_thang_2")
        kc_mm = body.get("khoang_cach_thang_mm")
        if (
            isinstance(d1, (list, tuple)) and len(d1) == 2
            and isinstance(d2, (list, tuple)) and len(d2) == 2
            and kc_mm is not None and kc_mm != ""
        ):
            kq_thang = thang.tinh_thang_tu_hai_diem(
                (float(d1[0]), float(d1[1])),
                (float(d2[0]), float(d2[1])),
                float(kc_mm),
            )
            px_per_mm_val = kq_thang.px_per_mm
            u_px_per_mm_val = kq_thang.u_px_per_mm
            thang_anh_dict = {
                "khoang_cach_px": kq_thang.khoang_cach_px,
                "khoang_cach_mm": kq_thang.khoang_cach_mm,
                "px_per_mm": kq_thang.px_per_mm,
                "u_px_per_mm": kq_thang.u_px_per_mm,
                "mm_per_px": kq_thang.mm_per_px,
            }
        elif body.get("px_per_mm") not in (None, ""):
            px_per_mm_val = float(body["px_per_mm"])
            if not math.isfinite(px_per_mm_val) or px_per_mm_val <= 0:
                return _json_err("Giá trị thang px_per_mm phải lớn hơn 0.", 400)
            thang_anh_dict = {
                "px_per_mm": px_per_mm_val,
                "u_px_per_mm": 0.0,
                "mm_per_px": 1.0 / px_per_mm_val,
            }

        phuong_phap = "centroid" if body.get("phuong_phap") == "centroid" else "gauss"
        dung_roi_thu_cong = bool(body.get("dung_roi_thu_cong", False))

        roi_tc_tuple = None
        roi_mau_tuple = None
        if dung_roi_thu_cong:
            rtc = body.get("roi_tc")
            rmau = body.get("roi_mau")
            if isinstance(rtc, (list, tuple)) and len(rtc) == 4:
                roi_tc_tuple = tuple(int(v) for v in rtc)
            if isinstance(rmau, (list, tuple)) and len(rmau) == 4:
                roi_mau_tuple = tuple(int(v) for v in rmau)

        img_cfg = load_image_config()
        buoc_cot = max(2, int(anh_input.shape[1] // 250)) if anh_input.shape[1] > 600 else 2
        kq_do = do_delta_y_tu_anh(
            anh_input,
            roi_tham_chieu=roi_tc_tuple,
            roi_mau=roi_mau_tuple,
            phuong_phap=phuong_phap,
            buoc_nhay_cot=buoc_cot,
            nguong_bao_hoa=int(img_cfg.get("nguong_bao_hoa", 250)),
            ti_le_bao_hoa_toi_da=float(img_cfg.get("ti_le_bao_hoa_toi_da", 0.02)),
            snr_toi_thieu=float(img_cfg.get("snr_toi_thieu", 10.0)),
            tao_anh_ve=True,
        )

        (
            kq_man_dict,
            error_man,
            loai_loi_man,
            khong_danh_gia_duoc,
            ly_do_khong_danh_gia,
            danh_gia_loai,
        ) = _solve_and_gate_measurement(
            mh=mh,
            delta_y_px=kq_do.delta_y_px,
            sigma_delta_y_px=kq_do.sai_so_delta_y_px,
            nhiet_do_do=nhiet_do_do,
            nhiet_do_tham_chieu=nhiet_do_tham_chieu,
            khong_do_nhiet_do=khong_do_nhiet_do,
            px_per_mm_val=px_per_mm_val,
            u_px_per_mm_val=u_px_per_mm_val,
            chat_luong_hop_le=kq_do.chat_luong.hop_le,
            la_anh_mo_phong=la_anh_mo_phong,
            ma_loai_req=str(body.get("ma_loai") or "").strip(),
        )
        cq = kq_do.chat_luong

        canh_bao_anh = list(cq.canh_bao)
        if mode != "sim" and not khoa_ae_af:
            canh_bao_anh.append(
                "Chưa khóa phơi sáng và lấy nét (AE/AF lock): độ sáng/độ nét vạch có thể thay đổi giữa các lần chụp."
            )
        delta_y_mm_val = None
        sai_so_delta_y_mm_val = None
        if px_per_mm_val is not None and math.isfinite(kq_do.delta_y_px):
            delta_y_mm_val, sai_so_delta_y_mm_val = thang.quy_doi_delta_y_sang_mm(
                kq_do.delta_y_px,
                px_per_mm_val,
                kq_do.sai_so_delta_y_px if math.isfinite(kq_do.sai_so_delta_y_px) else 0.0,
                u_px_per_mm_val,
            )

        anh_b64 = _encode_preview_b64(kq_do.anh_danh_dau if kq_do.anh_danh_dau is not None else anh_input)
        h_img, w_img = anh_input.shape[:2]

        return _json_ok({
            "la_anh_mo_phong": la_anh_mo_phong,
            "khong_do_nhiet_do": khong_do_nhiet_do,
            "nhiet_do_do": None if khong_do_nhiet_do else nhiet_do_do,
            "nhiet_do_tham_chieu": nhiet_do_tham_chieu,
            "khoa_ae_af": khoa_ae_af,
            "exif": exif_info,
            "thang_anh": thang_anh_dict,
            "delta_y_mm": delta_y_mm_val,
            "sai_so_delta_y_mm": sai_so_delta_y_mm_val,
            "anh_width": w_img,
            "anh_height": h_img,
            "delta_y_px": kq_do.delta_y_px,
            "sai_so_delta_y_px": kq_do.sai_so_delta_y_px,
            "x_ref": kq_do.x_ref,
            "chi_so_do_duc_tuong_doi": kq_do.chi_so_do_duc_tuong_doi,
            "chat_luong": {
                "hop_le": cq.hop_le,
                "bao_hoa": cq.bao_hoa,
                "ti_le_bao_hoa": cq.ti_le_bao_hoa,
                "qua_mo": cq.qua_mo,
                "snr": cq.snr,
                "nhoe": cq.nhoe,
                "fwhm_mau": cq.fwhm_mau,
                "fwhm_tc": cq.fwhm_tc,
                "canh_bao": canh_bao_anh,
            },
            "vach_tham_chieu": _serialize_line_fit(kq_do.vach_tham_chieu),
            "vach_mau": _serialize_line_fit(kq_do.vach_mau),
            "mo_hinh_man": kq_man_dict,
            "error_man": error_man,
            "loai_loi_man": loai_loi_man,
            "khong_danh_gia_duoc": khong_danh_gia_duoc,
            "trang_thai_danh_gia": (
                "KHONG_DANH_GIA_DUOC"
                if khong_danh_gia_duoc
                else (danh_gia_loai["trang_thai"] if danh_gia_loai else None)
            ),
            "ly_do_khong_danh_gia": ly_do_khong_danh_gia,
            "chan_li_mp": chan_li_mp,
            "anh_danh_dau_b64": anh_b64,
            "profile": _extract_profile_data(anh_input, kq_do),
            "danh_gia_loai": danh_gia_loai,
        })
    except AnhKhongHopLeError as exc:
        return _json_err_typed(
            400,
            "ANH_KHONG_HOP_LE",
            "Ảnh tải lên bị hỏng, rỗng hoặc không đúng định dạng ảnh hợp lệ.",
            exc,
        )
    except KhongTimThayVachError as exc:
        return _json_err_typed(
            422,
            "KHONG_TIM_THAY_VACH",
            "Không tìm thấy đủ 2 vạch laser rõ ràng trong ảnh. "
            "Hãy chụp lại trong chỗ tối, giữ máy thẳng và để cả 2 vạch sáng nằm gọn trong khung hình.",
            exc,
        )
    except cal.LoiMoHinhHieuChuanError as exc:
        return _json_err_typed(
            422,
            "LOI_MO_HINH_GIAI_NGUOC",
            f"Lỗi mô hình hiệu chuẩn hoặc giải ngược độ mặn: {exc}",
            exc,
        )
    except (ValueError, TypeError) as exc:
        return _json_err_typed(
            400,
            "DAU_VAO_KHONG_HOP_LE",
            f"Tham số đo không hợp lệ: {exc}",
            exc,
        )


def _parse_measure_common(
    body: dict[str, Any], mh: cal.MoHinhHieuChuan
) -> tuple[bool, float, float | None, bool, float | None, float, dict[str, Any] | None, str, bool, tuple | None, tuple | None]:
    """Đọc và kiểm tra đầu vào chung cho /api/measure và /api/measure-multi."""
    khong_do_nhiet_do = bool(body.get("khong_do_nhiet_do", False))
    raw_t = body.get("nhiet_do_do")
    if not khong_do_nhiet_do:
        if raw_t is None or (isinstance(raw_t, str) and not raw_t.strip()):
            raise ValueError("Vui lòng nhập nhiệt độ mẫu nước (°C) hoặc chọn 'Không đo nhiệt độ'.")
        try:
            nhiet_do_do = float(raw_t)
        except (TypeError, ValueError) as exc:
            raise ValueError("Nhiệt độ mẫu nước không hợp lệ.") from exc
        if not math.isfinite(nhiet_do_do):
            raise ValueError("Nhiệt độ mẫu nước không hợp lệ.")
    else:
        nhiet_do_do = float(mh.T_ref)

    raw_t_ref = body.get("nhiet_do_tham_chieu")
    if raw_t_ref is None or (isinstance(raw_t_ref, str) and not raw_t_ref.strip()):
        nhiet_do_tham_chieu = None
    else:
        try:
            nhiet_do_tham_chieu = float(raw_t_ref)
        except (TypeError, ValueError) as exc:
            raise ValueError("Nhiệt độ ngăn tham chiếu không hợp lệ.") from exc
        if not math.isfinite(nhiet_do_tham_chieu):
            raise ValueError("Nhiệt độ ngăn tham chiếu không hợp lệ.")

    khoa_ae_af = bool(body.get("khoa_ae_af", False))
    thang_anh_dict: dict[str, Any] | None = None
    px_per_mm_val: float | None = None
    u_px_per_mm_val = 0.0

    d1 = body.get("diem_thang_1")
    d2 = body.get("diem_thang_2")
    kc_mm = body.get("khoang_cach_thang_mm")
    if (
        isinstance(d1, (list, tuple)) and len(d1) == 2
        and isinstance(d2, (list, tuple)) and len(d2) == 2
        and kc_mm is not None and kc_mm != ""
    ):
        kq_thang = thang.tinh_thang_tu_hai_diem(
            (float(d1[0]), float(d1[1])),
            (float(d2[0]), float(d2[1])),
            float(kc_mm),
        )
        px_per_mm_val = kq_thang.px_per_mm
        u_px_per_mm_val = kq_thang.u_px_per_mm
        thang_anh_dict = {
            "khoang_cach_px": kq_thang.khoang_cach_px,
            "khoang_cach_mm": kq_thang.khoang_cach_mm,
            "px_per_mm": kq_thang.px_per_mm,
            "u_px_per_mm": kq_thang.u_px_per_mm,
            "mm_per_px": kq_thang.mm_per_px,
        }
    elif body.get("px_per_mm") not in (None, ""):
        px_per_mm_val = float(body["px_per_mm"])
        if not math.isfinite(px_per_mm_val) or px_per_mm_val <= 0:
            raise ValueError("Giá trị thang px_per_mm phải lớn hơn 0.")
        thang_anh_dict = {
            "px_per_mm": px_per_mm_val,
            "u_px_per_mm": 0.0,
            "mm_per_px": 1.0 / px_per_mm_val,
        }

    phuong_phap = "centroid" if body.get("phuong_phap") == "centroid" else "gauss"
    dung_roi_thu_cong = bool(body.get("dung_roi_thu_cong", False))
    roi_tc_tuple = None
    roi_mau_tuple = None
    if dung_roi_thu_cong:
        rtc = body.get("roi_tc")
        rmau = body.get("roi_mau")
        if isinstance(rtc, (list, tuple)) and len(rtc) == 4:
            roi_tc_tuple = tuple(int(v) for v in rtc)
        if isinstance(rmau, (list, tuple)) and len(rmau) == 4:
            roi_mau_tuple = tuple(int(v) for v in rmau)

    return (
        khong_do_nhiet_do,
        nhiet_do_do,
        nhiet_do_tham_chieu,
        khoa_ae_af,
        px_per_mm_val,
        u_px_per_mm_val,
        thang_anh_dict,
        phuong_phap,
        dung_roi_thu_cong,
        roi_tc_tuple,
        roi_mau_tuple,
    )


def _solve_and_gate_measurement(
    mh: cal.MoHinhHieuChuan,
    delta_y_px: float,
    sigma_delta_y_px: float,
    nhiet_do_do: float,
    nhiet_do_tham_chieu: float | None,
    khong_do_nhiet_do: bool,
    px_per_mm_val: float | None,
    u_px_per_mm_val: float,
    chat_luong_hop_le: bool,
    la_anh_mo_phong: bool,
    ma_loai_req: str,
) -> tuple[dict[str, Any] | None, str | None, str | None, bool, list[str], dict[str, Any] | None]:
    """Giải ngược độ mặn từ Δy và áp dụng cổng chất lượng + phân loại loài theo [S-U, S+U]."""
    cfg_cal = load_calib_config()
    kq_man_dict = None
    error_man = None
    loai_loi_man = None
    if math.isfinite(delta_y_px):
        try:
            kq_man = cal.uoc_luong_do_man(
                mh=mh,
                delta_y_px=delta_y_px,
                T_C=nhiet_do_do,
                sigma_delta_y_px=sigma_delta_y_px,
                sigma_T_C=cfg_cal.sai_so_nhiet_ke_C,
                k=cfg_cal.he_so_phu_k,
                nguong_lech_T_khong_bu_C=cfg_cal.nguong_lech_T_khong_bu_C,
                T_tham_chieu_C=nhiet_do_tham_chieu,
                sigma_T_tham_chieu_C=cfg_cal.sai_so_nhiet_ke_C if nhiet_do_tham_chieu is not None else 0.0,
                nguong_lech_T_hai_ngan_C=cfg_cal.nguong_lech_T_hai_ngan_C,
                px_per_mm=px_per_mm_val,
                u_px_per_mm=u_px_per_mm_val,
                sigma_dung_dich_chuan_ppt=cfg_cal.sai_so_dung_dich_chuan_ppt,
                sigma_D_khi_chua_do_C=cfg_cal.sigma_D_khi_chua_do_C,
            )
            canh_bao_man = list(kq_man.canh_bao)
            canh_bao_chi_tiet = list(kq_man.canh_bao_chi_tiet)
            if khong_do_nhiet_do:
                msg_no_t = "CHƯA ĐO NHIỆT ĐỘ: không thực hiện bù nhiệt thực tế và KHÔNG đưa ra kết luận phân loại loài."
                canh_bao_man.insert(0, msg_no_t)
                canh_bao_chi_tiet.insert(0, {"ma": "CHUA_DO_NHIET_DO", "cap": "nghiem_trong", "noi_dung": msg_no_t})
            kq_man_dict = {
                "S_ppt": kq_man.S_ppt,
                "u_S_ppt": kq_man.u_S_ppt,
                "U_S_ppt": kq_man.U_S_ppt,
                "k": kq_man.k,
                "thanh_phan_bat_dinh": kq_man.thanh_phan_bat_dinh,
                "mo_ta_thanh_phan_bat_dinh": kq_man.mo_ta_thanh_phan_bat_dinh,
                "ngoai_dai_S": kq_man.ngoai_dai_S,
                "ngoai_dai_T": kq_man.ngoai_dai_T,
                "ngoai_dai_D": kq_man.ngoai_dai_D,
                "chenh_T_ngoai_mo_hinh": kq_man.chenh_T_ngoai_mo_hinh,
                "khong_danh_gia_duoc": kq_man.khong_danh_gia_duoc,
                "la_mo_phong": kq_man.la_mo_phong,
                "nguon_du_lieu": kq_man.nguon_du_lieu,
                "da_xac_nhan_thuc_te": kq_man.da_xac_nhan_thuc_te,
                "nhan": kq_man.nhan,
                "canh_bao": canh_bao_man,
                "canh_bao_chi_tiet": canh_bao_chi_tiet,
                "han_che": kq_man.han_che,
            }
        except cal.LoiMoHinhHieuChuanError as ex_man:
            error_man = str(ex_man)
            loai_loi_man = "LOI_MO_HINH_GIAI_NGUOC"
        except (ValueError, TypeError) as ex_man:
            error_man = str(ex_man)
            loai_loi_man = "DAU_VAO_KHONG_HOP_LE"

    ly_do_khong_danh_gia: list[str] = []
    if khong_do_nhiet_do:
        ly_do_khong_danh_gia.append("Chưa đo nhiệt độ mẫu")
    if not chat_luong_hop_le:
        ly_do_khong_danh_gia.append("Ảnh không đạt chuẩn chất lượng (bão hòa / quá mờ / nhòe / thiếu cột)")
    if kq_man_dict is None:
        ly_do_khong_danh_gia.append(error_man or "Không giải ngược được độ mặn")
    else:
        if kq_man_dict["ngoai_dai_S"]:
            ly_do_khong_danh_gia.append("Độ mặn ước lượng nằm ngoài dải hiệu chuẩn")
        if kq_man_dict["ngoai_dai_T"]:
            ly_do_khong_danh_gia.append("Nhiệt độ nằm ngoài dải hiệu chuẩn")
        if kq_man_dict.get("ngoai_dai_D"):
            ly_do_khong_danh_gia.append("Chênh nhiệt hai ngăn D nằm ngoài dải hiệu chuẩn")
        if kq_man_dict.get("chenh_T_ngoai_mo_hinh"):
            ly_do_khong_danh_gia.append("Chênh nhiệt hai ngăn vượt ngưỡng trên đường chuẩn chưa học số hạng D")
        if mh.la_mo_phong or la_anh_mo_phong:
            ly_do_khong_danh_gia.append("Đang dùng ảnh hoặc đường chuẩn MÔ PHỎNG (chưa phải đo thật)")
        elif not mh.da_xac_nhan_thuc_te:
            ly_do_khong_danh_gia.append("Đường chuẩn CHƯA XÁC NHẬN NGUỒN DỮ LIỆU thực tế")

    khong_danh_gia_duoc = bool(ly_do_khong_danh_gia)
    ds_loai = load_species_map()
    ma_loai = ma_loai_req or next(iter(ds_loai.keys()), "")
    danh_gia_loai = None
    if ma_loai in ds_loai:
        if khong_do_nhiet_do:
            danh_gia_loai = None
        elif khong_danh_gia_duoc:
            kq_kdg = th.tao_ket_qua_khong_danh_gia_duoc(
                ds_loai[ma_loai],
                kq_man_dict["S_ppt"] if kq_man_dict else None,
                kq_man_dict["U_S_ppt"] if kq_man_dict else 0.0,
                ly_do_khong_danh_gia,
            )
            danh_gia_loai = {
                "ma_loai": kq_kdg.ma_loai,
                "ten_loai": kq_kdg.ten_loai,
                "trang_thai": kq_kdg.trang_thai,
                "mau_sac": kq_kdg.mau_sac,
                "tieu_de": kq_kdg.tieu_de,
                "loi_khuyen": kq_kdg.loi_khuyen,
                "nguon_tham_khao": kq_kdg.nguon_tham_khao,
                "pho": None,
                "info": _serialize_species(ds_loai[ma_loai]),
            }
        else:
            danh_gia_loai = _evaluate_species_detail(
                kq_man_dict["S_ppt"],
                ds_loai[ma_loai],
                U=kq_man_dict["U_S_ppt"],
            )

    return kq_man_dict, error_man, loai_loi_man, khong_danh_gia_duoc, ly_do_khong_danh_gia, danh_gia_loai


async def api_measure_multi(request: Request) -> JSONResponse:
    """Đo độ lệch Δy từ chuỗi nhiều khung hình (nhiều ảnh chụp hoặc video tách khung)."""
    try:
        body = await request.json()
    except Exception:
        return _json_err("Dữ liệu JSON gửi lên không hợp lệ.")

    mode = str(body.get("mode", "upload"))
    ho_so = _req_ho_so(request, body)
    cfg = load_config()
    mh: cal.MoHinhHieuChuan = get_model_for_profile(ho_so)
    la_anh_mo_phong = mode == "sim"
    chan_li_mp: dict[str, Any] | None = None

    try:
        (
            khong_do_nhiet_do,
            nhiet_do_do,
            nhiet_do_tham_chieu,
            khoa_ae_af,
            px_per_mm_val,
            u_px_per_mm_val,
            thang_anh_dict,
            phuong_phap,
            _dung_roi,
            roi_tc_tuple,
            roi_mau_tuple,
        ) = _parse_measure_common(body, mh)

        frames_ok: list[np.ndarray] = []
        raw_idx_map: list[int] = []
        pre_errors: list[tuple[int, str]] = []
        exif_info: dict[str, Any] = {}

        if mode == "sim":
            so_khung = max(2, min(20, int(body.get("so_khung", 5))))
            s_mp = float(body.get("S_ppt", 16.5))
            t_mp = float(body.get("T_C", nhiet_do_do))
            t_tc_mp = float(body.get("T_tham_chieu_C", nhiet_do_tham_chieu if nhiet_do_tham_chieu is not None else t_mp))
            do_duc = float(body.get("do_duc", 0.15))
            drift_px = float(body.get("drift_px", 4.0))
            bo_tri = "doc" if body.get("bo_tri") == "doc" else "ngang"
            cho_phep_bao_hoa = bool(body.get("cho_phep_bao_hoa", False))
            seed = int(body.get("seed", 42))
            for i in range(so_khung):
                p_synth = ThamSoMoPhong(
                    S_ppt=s_mp,
                    T_C=t_mp,
                    T_tham_chieu_C=t_tc_mp,
                    drift_chung_px=drift_px + ((i - so_khung / 2.0) * 0.5),
                    do_duc=do_duc,
                    bo_tri=bo_tri,
                    cho_phep_bao_hoa=cho_phep_bao_hoa,
                    seed=seed + i,
                )
                anh_obj = sinh_anh_hai_vach_mo_phong(p_synth, cfg, gan_watermark=False)
                frames_ok.append(cv2.cvtColor(anh_obj.anh, cv2.COLOR_GRAY2BGR))
                raw_idx_map.append(i)
                if i == 0:
                    chan_li_mp = {
                        "S_chan_li": s_mp,
                        "T_chan_li": t_mp,
                        "T_tc_chan_li": t_tc_mp,
                        "delta_y_snell": anh_obj.delta_y_ly_thuyet_px,
                        "drift_px": drift_px,
                    }
            tong_so_gui = so_khung
        else:
            raw_imgs = body.get("images_base64")
            if not isinstance(raw_imgs, list) or len(raw_imgs) < 2:
                return _json_err_typed(
                    400,
                    "DAU_VAO_KHONG_HOP_LE",
                    "Đo đa khung hình cần gửi danh sách images_base64 gồm ít nhất 2 ảnh.",
                )
            tong_so_gui = len(raw_imgs)
            for idx, b64_item in enumerate(raw_imgs):
                if not isinstance(b64_item, str) or not b64_item.strip():
                    pre_errors.append((idx, "Dữ liệu ảnh trống"))
                    continue
                try:
                    img_bgr, raw_bytes = _decode_base64_image_bytes(b64_item)
                    if not exif_info and raw_bytes:
                        exif_info = thang.doc_exif_phoi_sang(raw_bytes)
                    frames_ok.append(img_bgr)
                    raw_idx_map.append(idx)
                except AnhKhongHopLeError as exc_dec:
                    pre_errors.append((idx, str(exc_dec)))

            if not frames_ok:
                raise AnhKhongHopLeError("Không giải mã được khung ảnh hợp lệ nào trong chuỗi.")

        img_cfg = load_image_config()
        kq_da = do_delta_y_da_khung_hinh(
            frames_ok,
            roi_tham_chieu=roi_tc_tuple,
            roi_mau=roi_mau_tuple,
            phuong_phap=phuong_phap,
            nguong_bao_hoa=int(img_cfg.get("nguong_bao_hoa", 250)),
            ti_le_bao_hoa_toi_da=float(img_cfg.get("ti_le_bao_hoa_toi_da", 0.02)),
            snr_toi_thieu=float(img_cfg.get("snr_toi_thieu", 10.0)),
        )

        # Hợp nhất danh sách khung lỗi (cả khung lỗi lúc giải mã + khung lỗi lúc đo vạch)
        khung_loi_day_du: list[dict[str, Any]] = [
            {"khung": i, "ly_do": msg} for i, msg in pre_errors
        ]
        for sub_idx, msg in kq_da.khung_loi:
            khung_loi_day_du.append({"khung": raw_idx_map[sub_idx], "ly_do": msg})
        khung_loi_day_du.sort(key=lambda r: r["khung"])

        # Lấy 1 khung hợp lệ để dựng ảnh đánh dấu & profile
        anh_rep = frames_ok[0]
        kq_rep = do_delta_y_tu_anh(
            anh_rep,
            roi_tham_chieu=roi_tc_tuple,
            roi_mau=roi_mau_tuple,
            phuong_phap=phuong_phap,
            nguong_bao_hoa=int(img_cfg.get("nguong_bao_hoa", 250)),
            ti_le_bao_hoa_toi_da=float(img_cfg.get("ti_le_bao_hoa_toi_da", 0.02)),
            snr_toi_thieu=float(img_cfg.get("snr_toi_thieu", 10.0)),
            tao_anh_ve=True,
        )
        sigma_dy_use = max(kq_da.sai_so_thong_ke_px, kq_rep.sai_so_delta_y_px if kq_da.sai_so_thong_ke_px <= 0 else 0.0)
        cq_chung = kq_da.chat_luong_chung
        tong_hop_le_cuoi = cq_chung.hop_le and (not pre_errors)

        (
            kq_man_dict,
            error_man,
            loai_loi_man,
            khong_danh_gia_duoc,
            ly_do_khong_danh_gia,
            danh_gia_loai,
        ) = _solve_and_gate_measurement(
            mh=mh,
            delta_y_px=kq_da.delta_y_trung_vi_px,
            sigma_delta_y_px=sigma_dy_use,
            nhiet_do_do=nhiet_do_do,
            nhiet_do_tham_chieu=nhiet_do_tham_chieu,
            khong_do_nhiet_do=khong_do_nhiet_do,
            px_per_mm_val=px_per_mm_val,
            u_px_per_mm_val=u_px_per_mm_val,
            chat_luong_hop_le=tong_hop_le_cuoi,
            la_anh_mo_phong=la_anh_mo_phong,
            ma_loai_req=str(body.get("ma_loai") or "").strip(),
        )

        canh_bao_anh = list(cq_chung.canh_bao)
        if pre_errors:
            canh_bao_anh.append(f"Có {len(pre_errors)}/{tong_so_gui} khung ảnh không giải mã được.")
        if mode != "sim" and not khoa_ae_af:
            canh_bao_anh.append(
                "Chưa khóa phơi sáng và lấy nét (AE/AF lock): độ sáng/độ nét vạch có thể thay đổi giữa các lần chụp."
            )

        delta_y_mm_val = None
        sai_so_delta_y_mm_val = None
        if px_per_mm_val is not None:
            delta_y_mm_val, sai_so_delta_y_mm_val = thang.quy_doi_delta_y_sang_mm(
                kq_da.delta_y_trung_vi_px, px_per_mm_val, sigma_dy_use, u_px_per_mm_val
            )

        anh_b64 = _encode_preview_b64(kq_rep.anh_danh_dau if kq_rep.anh_danh_dau is not None else anh_rep)
        h_img, w_img = anh_rep.shape[:2]

        return _json_ok({
            "da_khung_hinh": True,
            "la_anh_mo_phong": la_anh_mo_phong,
            "khong_do_nhiet_do": khong_do_nhiet_do,
            "nhiet_do_do": None if khong_do_nhiet_do else nhiet_do_do,
            "nhiet_do_tham_chieu": nhiet_do_tham_chieu,
            "khoa_ae_af": khoa_ae_af,
            "exif": exif_info,
            "thang_anh": thang_anh_dict,
            "delta_y_mm": delta_y_mm_val,
            "sai_so_delta_y_mm": sai_so_delta_y_mm_val,
            "anh_width": w_img,
            "anh_height": h_img,
            "delta_y_px": kq_da.delta_y_trung_vi_px,
            "sai_so_delta_y_px": sigma_dy_use,
            "x_ref": kq_rep.x_ref,
            "chi_so_do_duc_tuong_doi": kq_da.chi_so_do_duc_tb,
            "so_khung_hop_le": kq_da.so_khung_hop_le,
            "tong_so_khung": tong_so_gui,
            "danh_sach_delta_y": kq_da.danh_sach_delta_y,
            "khung_loi": khung_loi_day_du,
            "do_doc_troi_px_moi_khung": kq_da.do_doc_troi_px_moi_khung,
            "sai_so_do_doc_troi": kq_da.sai_so_do_doc_troi,
            "canh_bao_troi_theo_thoi_gian": kq_da.canh_bao_troi_theo_thoi_gian,
            "canh_bao_dao_dong_phoi_sang": kq_da.canh_bao_dao_dong_phoi_sang,
            "canh_bao_da_khung": kq_da.canh_bao_da_khung,
            "chat_luong": {
                "hop_le": tong_hop_le_cuoi,
                "bao_hoa": cq_chung.bao_hoa,
                "ti_le_bao_hoa": cq_chung.ti_le_bao_hoa,
                "qua_mo": cq_chung.qua_mo,
                "snr": cq_chung.snr,
                "nhoe": cq_chung.nhoe,
                "fwhm_mau": cq_chung.fwhm_mau,
                "fwhm_tc": cq_chung.fwhm_tc,
                "canh_bao": canh_bao_anh,
            },
            "vach_tham_chieu": _serialize_line_fit(kq_rep.vach_tham_chieu),
            "vach_mau": _serialize_line_fit(kq_rep.vach_mau),
            "mo_hinh_man": kq_man_dict,
            "error_man": error_man,
            "loai_loi_man": loai_loi_man,
            "khong_danh_gia_duoc": khong_danh_gia_duoc,
            "trang_thai_danh_gia": (
                "KHONG_DANH_GIA_DUOC"
                if khong_danh_gia_duoc
                else (danh_gia_loai["trang_thai"] if danh_gia_loai else None)
            ),
            "ly_do_khong_danh_gia": ly_do_khong_danh_gia,
            "chan_li_mp": chan_li_mp,
            "anh_danh_dau_b64": anh_b64,
            "profile": _extract_profile_data(anh_rep, kq_rep),
            "danh_gia_loai": danh_gia_loai,
        })
    except AnhKhongHopLeError as exc:
        return _json_err_typed(400, "ANH_KHONG_HOP_LE", f"Chuỗi ảnh tải lên không hợp lệ: {exc}", exc)
    except KhongTimThayVachError as exc:
        return _json_err_typed(422, "KHONG_TIM_THAY_VACH", str(exc), exc)
    except cal.LoiMoHinhHieuChuanError as exc:
        return _json_err_typed(422, "LOI_MO_HINH_GIAI_NGUOC", f"Lỗi giải ngược độ mặn: {exc}", exc)
    except (ValueError, TypeError) as exc:
        return _json_err_typed(400, "DAU_VAO_KHONG_HOP_LE", f"Tham số đo đa khung không hợp lệ: {exc}", exc)


async def api_species_eval(request: Request) -> JSONResponse:
    try:
        body = await request.json()
        s_ppt = float(body.get("S_ppt", 15.0))
        u_ppt = max(float(body.get("U_ppt", 0.0) or 0.0), 0.0)
        ds_loai = load_species_map()
        if not ds_loai:
            return _json_err("Không tìm thấy danh mục loài trong config.yaml.", 404)
        ma_loai = str(body.get("ma_loai") or "").strip() or next(iter(ds_loai.keys()))
        if ma_loai not in ds_loai:
            return _json_err(f"Không tìm thấy loài '{ma_loai}'.", 404)

        chi_tiet = _evaluate_species_detail(s_ppt, ds_loai[ma_loai], U=u_ppt)
        bang_nguong = load_serialized_species()
        ser_by_code = {item["ma_loai"]: item for item in bang_nguong}
        ma_tran = []
        for k, loai_obj in ds_loai.items():
            dg_k = th.danh_gia_do_man_loai(s_ppt, loai_obj, U=u_ppt)
            ser = ser_by_code[k]
            ma_tran.append({
                "ma_loai": k,
                "ten_loai": loai_obj.ten_hien_thi,
                "trang_thai": dg_k.trang_thai,
                "tieu_de": dg_k.tieu_de,
                "an_toan_str": ser["an_toan_str"],
                "nguon_tham_khao": loai_obj.nguon_tham_khao or "Chưa có nguồn tài liệu",
            })

        return _json_ok({
            "S_ppt": s_ppt,
            "U_ppt": u_ppt,
            "chi_tiet": chi_tiet,
            "ma_tran": ma_tran,
            "bang_nguong": bang_nguong,
        })
    except Exception as exc:
        return _json_err(f"Lỗi đánh giá loài: {exc}")


def _tinh_toc_do_bien_doi_df(df_all: pd.DataFrame) -> dict[int, tuple[float | None, float | None]]:
    """Tính tốc độ biến đổi độ mặn (‰/giờ) và bất định giữa 2 lần đo liên tiếp cùng (vị trí, nguồn)."""
    ket_qua: dict[int, tuple[float | None, float | None]] = {}
    if df_all.empty or "id" not in df_all.columns:
        return ket_qua
    work = df_all.copy()
    work["_dt"] = pd.to_datetime(work["thoi_gian"], errors="coerce")
    work["_loc"] = work["vi_tri"].fillna("").astype(str).str.strip()
    work["_src"] = work["nguon_du_lieu"].fillna("").astype(str).str.strip()

    for _, grp in work.groupby(["_loc", "_src"], sort=False):
        grp_s = grp.sort_values(by=["_dt", "id"], ascending=[True, True], na_position="first")
        prev_row = None
        for _, row in grp_s.iterrows():
            rid = int(row["id"])
            if prev_row is None or pd.isna(row["_dt"]) or pd.isna(prev_row["_dt"]):
                ket_qua[rid] = (None, None)
                prev_row = row
                continue
            dt_h = (row["_dt"] - prev_row["_dt"]).total_seconds() / 3600.0
            if dt_h <= 1e-6:
                ket_qua[rid] = (None, None)
            else:
                s_curr = float(row["do_man_ppt"])
                s_prev = float(prev_row["do_man_ppt"])
                u_curr = float(row["bat_dinh_U_ppt"]) if pd.notna(row["bat_dinh_U_ppt"]) else 0.0
                u_prev = float(prev_row["bat_dinh_U_ppt"]) if pd.notna(prev_row["bat_dinh_U_ppt"]) else 0.0
                rate = (s_curr - s_prev) / dt_h
                u_rate = math.hypot(u_curr, u_prev) / dt_h
                ket_qua[rid] = (rate, u_rate)
            prev_row = row
    return ket_qua


async def api_logs_list(request: Request) -> JSONResponse:
    ho_so = _req_ho_so(request)
    loai = request.query_params.get("loai")
    nguon = request.query_params.get("nguon")
    vi_tri = request.query_params.get("vi_tri")
    df_all = doc_lich_su_df(ho_so=ho_so)
    rates_map = _tinh_toc_do_bien_doi_df(df_all)
    df = df_all
    if loai and loai != "ALL":
        df = df[df["loai_nuoi"] == loai]
    if nguon and nguon != "ALL":
        df = df[df["nguon_du_lieu"] == nguon]
    if vi_tri and vi_tri != "ALL":
        df = df[df["vi_tri"] == vi_tri]

    rows = df.to_dict(orient="records")
    for r in rows:
        rid = r.get("id")
        rate_val, u_rate_val = rates_map.get(int(rid), (None, None)) if rid is not None else (None, None)
        r["toc_do_ppt_gio"] = rate_val
        r["u_toc_do_ppt_gio"] = u_rate_val

    summary = {
        "tong_so": len(df),
        "tong_tat_ca": len(df_all),
        "s_tb": float(df["do_man_ppt"].mean()) if len(df) else 0.0,
        "s_max": float(df["do_man_ppt"].max()) if len(df) else 0.0,
        "duc_tb": float(df["do_duc"].mean()) if len(df) else 0.0,
    }
    return _json_ok({
        "ho_so_hien_tai": ho_so,
        "all_profiles": lay_danh_sach_ho_so(),
        "rows": rows,
        "summary": summary,
        "all_species": sorted(df_all["loai_nuoi"].dropna().unique().tolist()) if len(df_all) else [],
        "all_sources": sorted(df_all["nguon_du_lieu"].dropna().unique().tolist()) if len(df_all) else [],
        "all_locations": sorted(df_all["vi_tri"].dropna().unique().tolist()) if len(df_all) else [],
    })


async def api_logs_delete(request: Request) -> JSONResponse:
    try:
        body = await request.json()
        row_id = int(body.get("id"))
    except Exception:
        return _json_err("Thiếu hoặc sai mã bản ghi (id) cần xóa.")
    ho_so = _req_ho_so(request, body if isinstance(body, dict) else None)
    deleted = xoa_nhat_ki_theo_id(row_id, ho_so=ho_so)
    if deleted == 0:
        return _json_err(f"Không tìm thấy bản ghi #{row_id} trong hồ sơ hiện tại.", 404)
    return _json_ok({"ok": True, "deleted_id": row_id})


async def api_logs_add(request: Request) -> JSONResponse:
    try:
        body = await request.json()
        ho_so = _req_ho_so(request, body)
        row_id = luu_nhat_ki(
            vi_tri=str(body.get("vi_tri", "Ao nuôi tôm số 1")),
            loai_nuoi=str(body.get("loai_nuoi", "Chưa chọn")),
            delta_y_px=float(body["delta_y_px"]),
            do_man_ppt=float(body["do_man_ppt"]),
            bat_dinh_U_ppt=float(body["bat_dinh_U_ppt"]),
            nhiet_do_C=float(body["nhiet_do_C"]),
            do_duc=float(body["do_duc"]),
            chat_luong_hop_le=bool(body.get("chat_luong_hop_le", True)),
            nguon_du_lieu=str(body.get("nguon_du_lieu", "MÔ PHỎNG")),
            ghi_chu=str(body.get("ghi_chu", "")),
            thoi_gian_tuy_chinh=str(body["thoi_gian"]) if body.get("thoi_gian") else None,
            ho_so=ho_so,
            px_per_mm=float(body["px_per_mm"]) if body.get("px_per_mm") not in (None, "") else None,
            delta_y_mm=float(body["delta_y_mm"]) if body.get("delta_y_mm") not in (None, "") else None,
            khoa_ae_af=bool(body.get("khoa_ae_af", False)),
            exif_exposure=str(body.get("exif_exposure") or ""),
            exif_iso=int(body["exif_iso"]) if body.get("exif_iso") not in (None, "") else None,
        )
        return _json_ok({"ok": True, "id": row_id, "ho_so": ho_so})
    except Exception as exc:
        return _json_err(f"Lỗi khi lưu nhật kí: {exc}")


async def api_logs_sample(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        body = {}
    ho_so = _req_ho_so(request, body if isinstance(body, dict) else None)
    count = nap_nhat_ki_mau_mo_phong(get_model_for_profile(ho_so), ho_so=ho_so)
    return _json_ok({"ok": True, "added": count, "ho_so": ho_so})


async def api_logs_clear(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        body = {}
    ho_so = _req_ho_so(request, body if isinstance(body, dict) else None)
    khoi_tao_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "DELETE FROM nhat_ki WHERE COALESCE(NULLIF(TRIM(ho_so), ''), 'mac_dinh') = ?",
            (ho_so,),
        )
    return _json_ok({"ok": True, "ho_so": ho_so})


async def api_logs_csv(request: Request) -> Response:
    ho_so = _req_ho_so(request)
    loai = request.query_params.get("loai")
    nguon = request.query_params.get("nguon")
    vi_tri = request.query_params.get("vi_tri")
    df = doc_lich_su_df(loai=loai, nguon=nguon, vi_tri=vi_tri, ho_so=ho_so)
    csv_bytes = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="nhat_ki_do_do_man.csv"'},
    )


async def api_calibrate(request: Request) -> JSONResponse:
    try:
        body = await request.json()
        mode = str(body.get("mode", "sim"))
        bac_ep_raw = body.get("bac_ep")
        bac_ep = int(bac_ep_raw) if bac_ep_raw in (1, 2, "1", "2") else None
        don_vi_y = "mm" if str(body.get("don_vi_y", "px")) == "mm" else "px"
        activate = bool(body.get("activate", False))
        ho_so = _req_ho_so(request, body)
        cfg = load_config()

        if mode == "sim":
            df_cal = sinh_du_lieu_hieu_chuan_mo_phong(cfg=cfg, seed=1)
            ten_nguon = "Bộ dữ liệu mô phỏng Snell (8 mức S × 3 mức T × 3 lần lặp = 72 điểm)"
        elif mode == "csv":
            csv_text = body.get("csv_text")
            if not csv_text or not isinstance(csv_text, str):
                return _json_err("Chưa cung cấp nội dung CSV hiệu chuẩn.")
            df_cal = cal.doc_csv_hieu_chuan(io.StringIO(csv_text))
            ten_nguon = str(body.get("file_name", f"File CSV tải lên ({len(df_cal)} điểm)"))
        else:
            return _json_err(f"Chế độ hiệu chuẩn '{mode}' không hợp lệ.")

        bc = cal.dung_duong_chuan(df_cal, load_calib_config(), bac_ep=bac_ep, don_vi_y=don_vi_y)
        mh_new = bc.mo_hinh
        saved_file = None
        if activate:
            luu_path = set_model_for_profile(ho_so, mh_new)
            saved_file = luu_path.name

        # Chuẩn bị dữ liệu vẽ đồ thị đường chuẩn đa nhiệt độ & phần dư
        s_grid = np.linspace(mh_new.S_min, mh_new.S_max, 100)
        s_grid_list = np.round(s_grid, 4).tolist()
        tat_ca_T = pd.concat([bc.df_train, bc.df_test])[cal.COT_NHIET_DO].to_numpy(float)
        muc_T = sorted(np.unique(np.round(tat_ca_T * 2) / 2))
        t_levels = [float(t) for t in (muc_T if mh_new.co_bu_nhiet else [mh_new.T_ref])[:6]]
        curves = [
            {
                "T_C": t_val,
                "S": s_grid_list,
                "delta_y": np.round(mh_new.du_doan_delta_y(s_grid, t_val), 4).tolist(),
            }
            for t_val in t_levels
        ]

        mh_tr = bc.mo_hinh_train
        t_tc_tr = cal._lay_nhiet_do_tc(bc.df_train)
        y_tr_vals = cal._lay_y_theo_don_vi(bc.df_train, don_vi_y)
        train_pts = [
            {
                "S": float(r[cal.COT_DO_MAN]),
                "T": float(r[cal.COT_NHIET_DO]),
                "delta_y": float(y_tr_vals[idx]),
                "res": float(y_tr_vals[idx]) - float(
                    mh_tr.du_doan_delta_y(float(r[cal.COT_DO_MAN]), float(r[cal.COT_NHIET_DO]), T_tc=float(t_tc_tr[idx]))[0]
                ),
            }
            for idx, (_, r) in enumerate(bc.df_train.iterrows())
        ]
        t_tc_te = cal._lay_nhiet_do_tc(bc.df_test)
        y_te_vals = cal._lay_y_theo_don_vi(bc.df_test, don_vi_y) if len(bc.df_test) else np.array([], dtype=float)
        test_pts = [
            {
                "S": float(r[cal.COT_DO_MAN]),
                "T": float(r[cal.COT_NHIET_DO]),
                "delta_y": float(y_te_vals[idx]),
                "res": float(y_te_vals[idx]) - float(
                    mh_tr.du_doan_delta_y(float(r[cal.COT_DO_MAN]), float(r[cal.COT_NHIET_DO]), T_tc=float(t_tc_te[idx]))[0]
                ),
            }
            for idx, (_, r) in enumerate(bc.df_test.iterrows())
        ]

        return _json_ok({
            "ten_nguon": ten_nguon,
            "activated": activate,
            "saved_file": saved_file,
            "mo_hinh": _serialize_model(mh_new),
            "bac_chon": bc.bac_chon,
            "ly_do_chon": bc.ly_do_chon,
            "rmse_kiem_dinh_cheo": bc.rmse_kiem_dinh_cheo,
            "RMSE_test_px": bc.RMSE_test_px,
            "RMSE_test_ppt": bc.RMSE_test_ppt,
            "s_res_train_px": mh_tr.s_res_px,
            "canh_bao": bc.canh_bao,
            "sai_so_theo_muc": bc.sai_so_theo_muc.round(4).to_dict(orient="records"),
            "plot_data": {
                "curves": curves,
                "train": train_pts,
                "test": test_pts,
            },
        })
    except Exception as exc:
        return _json_err(f"Không thể dựng đường chuẩn: {exc}")


async def api_calibrate_template_csv(request: Request) -> Response:
    csv_bytes = CSV_TEMPLATE_7_COT.encode("utf-8-sig")
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="mau_nhap_hieu_chuan_7_cot.csv"'},
    )


async def api_optics_sim(request: Request) -> JSONResponse:
    try:
        body = await request.json()
        cfg_cur = load_config()
        a_sim = float(body.get("A_deg", cfg_cur.A_do))
        d_sim = float(body.get("D_mm", cfg_cur.D_m * 1000.0)) / 1000.0
        if "D_m" in body:
            d_sim = float(body["D_m"])
        px_sim = float(body.get("pixel_mm", cfg_cur.pixel_mm))
        s_eval = float(body.get("S_ppt", 20.0))
        t_eval = float(body.get("T_C", 25.0))

        err_tam = float(body.get("sai_so_tim_tam_px", 0.05))
        err_t = float(body.get("lech_nhiet_do_C", 0.5))
        err_a = float(body.get("sai_so_goc_A_do", 0.05))
        err_troi = float(body.get("troi_laser_px", 5.0))
        he_so_triet = float(body.get("he_so_triet_chung", 0.01))

        cfg_sim = op.CauHinhQuangHoc(
            A_do=a_sim,
            D_m=d_sim,
            n_nuoc_ngot=cfg_cur.n_nuoc_ngot,
            dn_dS=cfg_cur.dn_dS,
            dn_dT=cfg_cur.dn_dT,
            T_tham_chieu_C=cfg_cur.T_tham_chieu_C,
            bien_TIR=cfg_cur.bien_TIR,
            pixel_mm=px_sim,
        )

        n_calc = op.chiet_suat(s_eval, t_eval, cfg_sim)
        n_tc_calc = op.chiet_suat(0.0, t_eval, cfg_sim)
        tir = False
        theta_ra = None
        delta_goc = None
        dy_px_sim = 0.0
        sens_px = None
        ngan_sach = None
        n_sin_a = n_calc * math.sin(math.radians(a_sim))

        try:
            theta_ra = op.goc_ra(n_calc, a_sim)
            delta_goc = op.goc_lech(n_calc, a_sim)
            dy_px_sim = op.delta_y_vi_sai_px(s_eval, t_eval, t_eval, cfg_sim, A_do=a_sim)
            sens_px = op.pixel_moi_phan_nghin(s_eval, t_eval, cfg_sim, A_do=a_sim, D_m=d_sim)
            ngan_sach = op.ngan_sach_sai_so(
                s_eval, t_eval, cfg_sim, err_tam, err_t, err_a, err_troi, he_so_triet
            )
        except op.PhanXaToanPhanError:
            tir = True

        cac_goc_a = np.linspace(25.0, 47.0, 90)
        do_nhay_a = []
        for a_val in cac_goc_a:
            try:
                do_nhay_a.append(round(op.pixel_moi_phan_nghin(s_eval, t_eval, cfg_sim, A_do=float(a_val), D_m=d_sim), 4))
            except op.PhanXaToanPhanError:
                do_nhay_a.append(None)

        cac_muc_s = np.linspace(0.0, 35.0, 71)
        dy_20: list[float] = []
        dy_30: list[float] = []
        response_tir = False
        try:
            dy_20 = [round(op.delta_y_vi_sai_px(float(sv), 20.0, 20.0, cfg_sim), 3) for sv in cac_muc_s]
            dy_30 = [round(op.delta_y_vi_sai_px(float(sv), 30.0, 30.0, cfg_sim), 3) for sv in cac_muc_s]
        except op.PhanXaToanPhanError:
            response_tir = True

        return _json_ok({
            "A_do": a_sim,
            "D_m": d_sim,
            "pixel_mm": px_sim,
            "S_ppt": s_eval,
            "T_C": t_eval,
            "n_mau": n_calc,
            "n_tc": n_tc_calc,
            "n_sin_A": n_sin_a,
            "tir": tir,
            "theta_ra": theta_ra,
            "delta_goc": delta_goc,
            "delta_y_px": dy_px_sim,
            "sens_px": sens_px,
            "ngan_sach": ngan_sach,
            "curves": {
                "angles": np.round(cac_goc_a, 3).tolist(),
                "sensitivities": do_nhay_a,
                "s_grid": np.round(cac_muc_s, 3).tolist(),
                "dy_20": dy_20,
                "dy_30": dy_30,
                "response_tir": response_tir,
            },
        })
    except Exception as exc:
        return _json_err(f"Lỗi mô phỏng quang học: {exc}")


async def api_bland_altman(request: Request) -> JSONResponse:
    try:
        body = await request.json()
        mode = str(body.get("mode", "sample"))

        if mode == "sample":
            rng_ba = np.random.default_rng(42)
            s_true = np.array([0, 5, 10, 15, 20, 25, 30, 35] * 3, dtype=float)
            m1 = np.round(s_true + rng_ba.normal(0.0, 0.16, len(s_true)), 2)
            m2 = np.round(s_true + rng_ba.normal(0.08, 0.35, len(s_true)), 2)
        elif mode == "csv":
            csv_text = str(body.get("csv_text", ""))
            df = pd.read_csv(io.StringIO(csv_text), encoding="utf-8-sig")
            if "S_thiet_bi" not in df.columns or "S_khuc_xa_ke" not in df.columns:
                return _json_err("File CSV cần có đủ 2 cột: S_thiet_bi và S_khuc_xa_ke.")
            m1 = pd.to_numeric(df["S_thiet_bi"], errors="coerce").dropna().to_numpy(float)
            m2 = pd.to_numeric(df["S_khuc_xa_ke"], errors="coerce").dropna().to_numpy(float)
            n_pair = min(len(m1), len(m2))
            m1, m2 = m1[:n_pair], m2[:n_pair]
        else:
            pairs = body.get("pairs", [])
            m1_list, m2_list = [], []
            for p in pairs:
                try:
                    v1 = float(p.get("S_thiet_bi"))
                    v2 = float(p.get("S_khuc_xa_ke"))
                    if math.isfinite(v1) and math.isfinite(v2):
                        m1_list.append(v1)
                        m2_list.append(v2)
                except (TypeError, ValueError):
                    continue
            m1 = np.asarray(m1_list, dtype=float)
            m2 = np.asarray(m2_list, dtype=float)

        n_pair = len(m1)
        if n_pair < 3:
            return _json_err("Cần tối thiểu 3 cặp số liệu hợp lệ để phân tích Bland–Altman.")

        tb = (m1 + m2) / 2.0
        hieu = m1 - m2
        mean_diff = float(np.mean(hieu))
        std_diff = float(np.std(hieu, ddof=1))
        loa_upper = mean_diff + 1.96 * std_diff
        loa_lower = mean_diff - 1.96 * std_diff
        r_corr = float(np.corrcoef(m1, m2)[0, 1]) if np.std(m1) > 0 and np.std(m2) > 0 else 1.0

        return _json_ok({
            "n_pair": n_pair,
            "mean_diff": mean_diff,
            "std_diff": std_diff,
            "loa_upper": loa_upper,
            "loa_lower": loa_lower,
            "r_corr": r_corr,
            "r2": r_corr ** 2,
            "pairs": [
                {
                    "S_thiet_bi": float(a),
                    "S_khuc_xa_ke": float(b),
                    "mean": float(t),
                    "diff": float(d),
                }
                for a, b, t, d in zip(m1, m2, tb, hieu)
            ],
        })
    except Exception as exc:
        return _json_err(f"Lỗi phân tích Bland–Altman: {exc}")


def _replace_yaml_scalar_line(text: str, key: str, value: float) -> str:
    pattern = re.compile(rf"^(\s*{re.escape(key)}:\s*)([^\s#]+)(.*)$", re.MULTILINE)
    if not pattern.search(text):
        raise ValueError(f"Không tìm thấy khóa '{key}' trong config.yaml.")
    formatted = f"{value:g}"
    return pattern.sub(rf"\g<1>{formatted}\g<3>", text, count=1)


def _format_species_yaml_block(nguong_loai: dict[str, dict[str, Any]]) -> str:
    lines: list[str] = ["nguong_loai:"]
    for key, info in nguong_loai.items():
        lines.append(f"  {key}:")
        ten = str(info.get("ten", key))
        lines.append(f"    ten: {json.dumps(ten, ensure_ascii=False)}")
        for range_key in ("an_toan", "canh_bao_thap", "canh_bao_cao"):
            val = info.get(range_key)
            if isinstance(val, (list, tuple)) and len(val) == 2:
                lines.append(f"    {range_key}: [{float(val[0]):g}, {float(val[1]):g}]")
            else:
                lines.append(f"    {range_key}: null")
        for num_key in ("nguy_hiem_duoi", "nguy_hiem_tren"):
            val = info.get(num_key)
            lines.append(f"    {num_key}: {float(val):g}" if val is not None else f"    {num_key}: null")
        nguon = str(info.get("nguon_tham_khao") or "").strip()
        lines.append(f"    nguon_tham_khao: {json.dumps(nguon, ensure_ascii=False)}")
        giai_doan = info.get("giai_doan")
        if isinstance(giai_doan, list):
            if not giai_doan:
                lines.append("    giai_doan: []")
            else:
                lines.append("    giai_doan:")
                for gd in giai_doan:
                    if not isinstance(gd, dict):
                        continue
                    lines.append(f"      - ten: {json.dumps(str(gd.get('ten', 'Giai đoạn')), ensure_ascii=False)}")
                    for rk in ("an_toan", "canh_bao_thap", "canh_bao_cao"):
                        rv = gd.get(rk)
                        if isinstance(rv, (list, tuple)) and len(rv) == 2:
                            lines.append(f"        {rk}: [{float(rv[0]):g}, {float(rv[1]):g}]")
                        else:
                            lines.append(f"        {rk}: null")
                    for nk in ("nguy_hiem_duoi", "nguy_hiem_tren"):
                        nv = gd.get(nk)
                        lines.append(f"        {nk}: {float(nv):g}" if nv is not None else f"        {nk}: null")
                    gd_ng = str(gd.get("nguon_tham_khao") or "").strip()
                    lines.append(f"        nguon_tham_khao: {json.dumps(gd_ng, ensure_ascii=False)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _parse_opt_float(val: Any) -> float | None:
    if val is None or val == "":
        return None
    f = float(val)
    if not math.isfinite(f):
        raise ValueError("Giá trị số không hợp lệ.")
    return f


async def api_config_optics(request: Request) -> JSONResponse:
    try:
        body = await request.json()
        cur = load_config()
        a_do = float(body.get("goc_dinh_A_do", cur.A_do))
        d_m = float(body.get("khoang_cach_man_D_m", cur.D_m))
        px_mm = float(body.get("kich_thuoc_pixel_mm", cur.pixel_mm))
        t_ref = float(body.get("nhiet_do_tham_chieu_C", cur.T_tham_chieu_C))

        if not (20.0 <= a_do <= 55.0):
            return _json_err("Góc đỉnh lăng kính A phải nằm trong khoảng 20.0° – 55.0°.")
        if not (0.1 <= d_m <= 5.0):
            return _json_err("Khoảng cách màn D phải nằm trong khoảng 0.1 – 5.0 m.")
        if not (0.005 <= px_mm <= 1.0):
            return _json_err("Kích thước pixel phải nằm trong khoảng 0.005 – 1.0 mm/px.")
        if not (5.0 <= t_ref <= 40.0):
            return _json_err("Nhiệt độ tham chiếu phải nằm trong khoảng 5.0 – 40.0 °C.")

        text = CONFIG_PATH.read_text(encoding="utf-8")
        new_text = _replace_yaml_scalar_line(text, "goc_dinh_A_do", a_do)
        new_text = _replace_yaml_scalar_line(new_text, "khoang_cach_man_D_m", d_m)
        new_text = _replace_yaml_scalar_line(new_text, "kich_thuoc_pixel_mm", px_mm)
        new_text = _replace_yaml_scalar_line(new_text, "nhiet_do_tham_chieu_C", t_ref)

        CONFIG_PATH.write_text(new_text, encoding="utf-8")
        invalidate_config_cache()
        try:
            cfg = load_config()
            sens_default = op.pixel_moi_phan_nghin(15.0, cfg.T_tham_chieu_C, cfg)
        except Exception:
            CONFIG_PATH.write_text(text, encoding="utf-8")
            invalidate_config_cache()
            raise

        return _json_ok({
            "ok": True,
            "quang_hoc": {
                "A_do": cfg.A_do,
                "D_m": cfg.D_m,
                "n_nuoc_ngot": cfg.n_nuoc_ngot,
                "dn_dS": cfg.dn_dS,
                "dn_dT": cfg.dn_dT,
                "T_tham_chieu_C": cfg.T_tham_chieu_C,
                "bien_TIR": cfg.bien_TIR,
                "pixel_mm": cfg.pixel_mm,
                "lambda_nm": 650,
                "do_nhay_mac_dinh": sens_default,
            },
        })
    except Exception as exc:
        return _json_err(f"Lỗi khi lưu cấu hình quang học: {exc}")


async def api_config_species(request: Request) -> JSONResponse:
    try:
        body = await request.json()
        ten = str(body.get("ten_hien_thi", "")).strip()
        if not ten:
            return _json_err("Vui lòng nhập tên loài / cây trồng.")

        raw_code = str(body.get("ma_loai", "")).strip()
        ma_loai = _slug_ho_so(raw_code or ten)
        if not ma_loai:
            return _json_err("Không tạo được mã loài hợp lệ.")

        at_min = _parse_opt_float(body.get("an_toan_min"))
        at_max = _parse_opt_float(body.get("an_toan_max"))
        cbt_min = _parse_opt_float(body.get("canh_bao_thap_min"))
        cbt_max = _parse_opt_float(body.get("canh_bao_thap_max"))
        cbc_min = _parse_opt_float(body.get("canh_bao_cao_min"))
        cbc_max = _parse_opt_float(body.get("canh_bao_cao_max"))
        nh_duoi = _parse_opt_float(body.get("nguy_hiem_duoi"))
        nh_tren = _parse_opt_float(body.get("nguy_hiem_tren"))
        nguon = str(body.get("nguon_tham_khao") or "").strip()

        if (at_min is None) != (at_max is None):
            return _json_err("Khoảng An toàn phải nhập đủ cả cận dưới và cận trên (hoặc để trống cả hai).")
        if at_min is not None and at_max is not None and at_min > at_max:
            return _json_err("Cận dưới dải An toàn không được lớn hơn cận trên.")
        co_nguong = any(
            v is not None
            for v in (at_min, at_max, cbt_min, cbt_max, cbc_min, cbc_max, nh_duoi, nh_tren)
        )
        if co_nguong and not nguon:
            return _json_err(
                "Bắt buộc nhập đầy đủ Nguồn tài liệu tham khảo (tác giả, năm, số trang/DOI hoặc số hiệu văn bản) khi khai báo ngưỡng."
            )

        text = CONFIG_PATH.read_text(encoding="utf-8")
        marker = re.search(r"(?m)^nguong_loai:\s*$", text)
        prefix = text[: marker.start()] if marker else (text.rstrip() + "\n\n")
        parsed = yaml.safe_load(text) or {}
        nguong_loai = dict(parsed.get("nguong_loai") or {})
        cu = nguong_loai.get(ma_loai) if isinstance(nguong_loai.get(ma_loai), dict) else {}

        entry: dict[str, Any] = {
            "ten": ten,
            "an_toan": [at_min, at_max] if (at_min is not None and at_max is not None) else None,
            "canh_bao_thap": [cbt_min, cbt_max] if (cbt_min is not None and cbt_max is not None) else None,
            "canh_bao_cao": [cbc_min, cbc_max] if (cbc_min is not None and cbc_max is not None) else None,
            "nguy_hiem_duoi": nh_duoi,
            "nguy_hiem_tren": nh_tren,
            "nguon_tham_khao": nguon,
        }
        if isinstance(cu.get("giai_doan"), list):
            entry["giai_doan"] = cu["giai_doan"]
        nguong_loai[ma_loai] = entry

        new_text = prefix + _format_species_yaml_block(nguong_loai)
        CONFIG_PATH.write_text(new_text, encoding="utf-8")
        invalidate_config_cache()
        try:
            load_config()
            ds_loai_ser = load_serialized_species()
        except Exception:
            CONFIG_PATH.write_text(text, encoding="utf-8")
            invalidate_config_cache()
            raise

        return _json_ok({
            "ok": True,
            "ma_loai": ma_loai,
            "danh_sach_loai": ds_loai_ser,
        })
    except Exception as exc:
        return _json_err(f"Lỗi khi lưu ngưỡng loài: {exc}")


class CacheHeaderMiddleware:
    """ASGI middleware nhẹ thêm Cache-Control chuẩn cho tài nguyên tĩnh và API."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path.startswith("/static/") or path in ("/favicon.ico", "/manifest.json"):
            cache_val = b"public, max-age=300, stale-while-revalidate=86400"
        elif path in ("/", "/sw.js"):
            cache_val = b"no-cache"
        elif path.startswith("/api/"):
            cache_val = b"no-store"
        else:
            cache_val = None

        if cache_val is None:
            await self.app(scope, receive, send)
            return

        async def send_with_cache(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers") or [])
                has_cc = any(k.lower() == b"cache-control" for k, _ in headers)
                if not has_cc:
                    headers.append((b"cache-control", cache_val))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_cache)


routes = [
    Route("/", endpoint=index, methods=["GET"]),
    Route("/favicon.ico", endpoint=favicon, methods=["GET"]),
    Route("/manifest.json", endpoint=manifest_json, methods=["GET"]),
    Route("/sw.js", endpoint=service_worker_js, methods=["GET"]),
    Route("/api/bootstrap", endpoint=api_bootstrap, methods=["GET"]),
    Route("/api/measure", endpoint=api_measure, methods=["POST"]),
    Route("/api/measure-multi", endpoint=api_measure_multi, methods=["POST"]),
    Route("/api/species-eval", endpoint=api_species_eval, methods=["POST"]),
    Route("/api/logs", endpoint=api_logs_list, methods=["GET"]),
    Route("/api/logs/add", endpoint=api_logs_add, methods=["POST"]),
    Route("/api/logs/sample", endpoint=api_logs_sample, methods=["POST"]),
    Route("/api/logs/clear", endpoint=api_logs_clear, methods=["POST"]),
    Route("/api/logs/delete", endpoint=api_logs_delete, methods=["POST"]),
    Route("/api/logs/csv", endpoint=api_logs_csv, methods=["GET"]),
    Route("/api/calibrate", endpoint=api_calibrate, methods=["POST"]),
    Route("/api/calibrate/template-csv", endpoint=api_calibrate_template_csv, methods=["GET"]),
    Route("/api/optics-sim", endpoint=api_optics_sim, methods=["POST"]),
    Route("/api/bland-altman", endpoint=api_bland_altman, methods=["POST"]),
    Route("/api/config/optics", endpoint=api_config_optics, methods=["POST"]),
    Route("/api/config/species", endpoint=api_config_species, methods=["POST"]),
    Mount("/static", app=StaticFiles(directory=str(STATIC_DIR)), name="static"),
]

middleware = [
    Middleware(CacheHeaderMiddleware),
    Middleware(GZipMiddleware, minimum_size=512, compresslevel=6),
]

app = Starlette(routes=routes, middleware=middleware)


def main() -> None:
    parser = argparse.ArgumentParser(description="Khởi chạy giao diện Web 2.5D Hệ thống đo độ mặn vi sai")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true", help="Không tự mở trình duyệt")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"
    print(f"Đang khởi động Web App 2.5D tại {url} (Ctrl+C để dừng)...")
    if not args.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
