"""Chế độ thu dữ liệu hiệu chuẩn có hướng dẫn — X1.

Giúp nhóm thực nghiệm tạo phiên thu dữ liệu theo mẻ pha, thiết bị và điện thoại,
đo Δy trực tiếp từ ảnh chụp gốc, áp dụng đầy đủ các lớp bảo vệ nguồn dữ liệu W0
(nhãn mô phỏng nhúng, sổ SHA-256 mô phỏng, kiểm tra EXIF, sổ ảnh đã xử lí,
chống ghi trùng ảnh), áp hiệu chuẩn chéo nhiệt kế (V1), đánh dấu loại bỏ minh bạch
(không xóa dòng), theo dõi tiến độ theo thiết kế thí nghiệm V4 và xuất CSV chuẩn.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from core import calibration as cal
from core import nhiet_ke, thang
from core.kiem_tra_thiet_ke import kiem_tra_thiet_ke_thi_nghiem, tai_cau_hinh_thiet_ke
from core.measure import (
    AnhKhongHopLeError,
    AnhKhongHoTroDinhDangError,
    do_delta_y_tu_anh,
    giai_ma_anh_tu_bytes,
    nhan_dien_dinh_dang_anh_bytes,
)
from scripts.xu_ly_thu_muc_anh import (
    LoiAnhMoPhongGanNhanThucTeError,
    LoiThieuExifAnhThucTeError,
    LoiXungDotNhanAnhError,
    _doc_so_anh_da_xu_ly,
    _ghi_so_anh_da_xu_ly,
    kiem_tra_thu_muc_mo_phong,
)
from sim.synth import doc_nhan_mo_phong, tra_cuu_so_anh_mo_phong

ROOT = Path(__file__).resolve().parents[1]
CONFIG_MAC_DINH = ROOT / "config.yaml"
DU_LIEU_HIEU_CHUAN_THUC_MAC_DINH = ROOT / "data" / "du_lieu_hieu_chuan_thuc.csv"
THU_MUC_ANH_THUC_MAC_DINH = ROOT / "data" / "anh_thuc"
PHIEN_THU_DU_LIEU_MAC_DINH = ROOT / "data" / "phien_thu_du_lieu.json"

COT_CSV_THU_DU_LIEU = [
    cal.COT_DO_MAN,
    cal.COT_NHIET_DO,
    cal.COT_NHIET_DO_TC,
    cal.COT_DELTA_Y,
    cal.COT_PX_PER_MM,
    cal.COT_DO_DUC,
    cal.COT_MA_ME_PHA,
    cal.COT_NGAY_DO,
    cal.COT_GHI_CHU,
    cal.COT_ID_THIET_BI,
    cal.COT_ID_DIEN_THOAI,
    cal.COT_NGUON,
    cal.COT_KHOA_AE_AF,
    cal.COT_SHA256_ANH,
    "kenh_su_dung",
    "exif_co",
    "nguoi_do",
    "phien_id",
    cal.COT_TEN_FILE,
    "tinh_tu_khoi_luong",
    "khoi_luong_muoi_g",
    "khoi_luong_nuoc_g",
    "da_loai",
    "ly_do_loai",
    "khai_bao_nguon_anh",
    "nguoi_khai_bao",
    cal.COT_NHIET_DO_TC_DOC,
    cal.COT_OFFSET_NHIET_KE,
]


class LoiTrungAnhThuDuLieuError(ValueError):
    """Ảnh có sha256 đã được ghi trong bộ dữ liệu thu thập."""


def duong_dan_du_lieu_thuc_csv(csv_path: str | Path | None = None) -> Path:
    if csv_path is not None:
        return Path(csv_path)
    env = os.environ.get("SALINITY_DU_LIEU_THUC_CSV_PATH", "").strip()
    return Path(env) if env else DU_LIEU_HIEU_CHUAN_THUC_MAC_DINH


def duong_dan_thu_muc_anh_thuc(anh_dir: str | Path | None = None) -> Path:
    if anh_dir is not None:
        return Path(anh_dir)
    env = os.environ.get("SALINITY_ANH_THUC_DIR", "").strip()
    return Path(env) if env else THU_MUC_ANH_THUC_MAC_DINH


def duong_dan_phien_thu(phien_path: str | Path | None = None) -> Path:
    if phien_path is not None:
        return Path(phien_path)
    env = os.environ.get("SALINITY_PHIEN_THU_JSON_PATH", "").strip()
    return Path(env) if env else PHIEN_THU_DU_LIEU_MAC_DINH


def _clean_id(raw: str, prefix: str = "PHIEN") -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "_", str(raw or "").strip()).strip("._")
    return s[:64] if s else f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def _clean_filename(raw: str | None, fallback: str = "anh_do.png") -> str:
    txt = str(raw or "").replace("\x00", "").strip()
    if not txt:
        return fallback
    base = txt.replace("\\", "/").rsplit("/", 1)[-1].replace("..", "_")
    clean = re.sub(r"[^a-zA-Z0-9._-]+", "_", base).strip("._")
    return clean[:120] if clean else fallback


def _la_true(val: Any) -> bool:
    if isinstance(val, (bool, np.bool_)):
        return bool(val)
    if val is None or (isinstance(val, float) and not math.isfinite(val)):
        return False
    return str(val).strip().lower() in {"1", "true", "yes", "co", "y"}


def tinh_do_man_tu_khoi_luong(khoi_luong_muoi_g: float, khoi_luong_nuoc_g: float) -> float:
    """Tính độ mặn chuẩn (‰ = g muối / kg dung dịch) từ khối lượng muối và nước cân được.

    Công thức:
        S (‰) = m_muối / (m_muối + m_nước) × 1000
    """
    m_muoi = float(khoi_luong_muoi_g)
    m_nuoc = float(khoi_luong_nuoc_g)
    if not (math.isfinite(m_muoi) and math.isfinite(m_nuoc)):
        raise ValueError("Khối lượng muối và nước phải là số hữu hạn.")
    if m_muoi < 0.0:
        raise ValueError("Khối lượng muối không được âm.")
    if m_nuoc <= 0.0:
        raise ValueError("Khối lượng nước phải lớn hơn 0.")
    return float((m_muoi / (m_muoi + m_nuoc)) * 1000.0)


def lay_danh_sach_phien(phien_path: str | Path | None = None) -> list[dict[str, Any]]:
    p = duong_dan_phien_thu(phien_path)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return list(data) if isinstance(data, list) else []
    except Exception:
        return []


def tao_phien_thu_du_lieu(
    ma_me_pha: str,
    id_thiet_bi: str,
    id_dien_thoai: str,
    nguoi_do: str,
    px_per_mm: float | None = None,
    diem_thang_1: tuple[float, float] | list[float] | None = None,
    diem_thang_2: tuple[float, float] | list[float] | None = None,
    khoang_cach_thang_mm: float | None = None,
    nguon_du_lieu: str = "THUC_TE",
    phien_id: str | None = None,
    phien_path: str | Path | None = None,
) -> dict[str, Any]:
    """Tạo hoặc cập nhật một phiên thu dữ liệu hiệu chuẩn."""
    ma_me = str(ma_me_pha or "").strip()
    id_tb = str(id_thiet_bi or "").strip()
    id_dt = str(id_dien_thoai or "").strip()
    nguoi = str(nguoi_do or "").strip()
    nguon = str(nguon_du_lieu or "THUC_TE").strip().upper()
    if not ma_me:
        raise ValueError("Phiên thu dữ liệu bắt buộc phải có mã mẻ pha (ma_me_pha).")
    if not id_tb:
        raise ValueError("Phiên thu dữ liệu bắt buộc phải có id_thiet_bi.")
    if not id_dt:
        raise ValueError("Phiên thu dữ liệu bắt buộc phải có id_dien_thoai.")
    if not nguoi:
        raise ValueError("Phiên thu dữ liệu bắt buộc phải có tên người đo (nguoi_do).")
    if nguon not in (cal.NHAN_THUC_TE, cal.NHAN_MO_PHONG):
        raise ValueError("nguon_du_lieu của phiên chỉ nhận 'THUC_TE' hoặc 'MO_PHONG'.")

    px_mm_val: float | None = None
    u_px_mm_val = 0.0
    if (
        diem_thang_1 is not None
        and diem_thang_2 is not None
        and len(diem_thang_1) == 2
        and len(diem_thang_2) == 2
        and khoang_cach_thang_mm is not None
    ):
        kq_th = thang.tinh_thang_tu_hai_diem(
            (float(diem_thang_1[0]), float(diem_thang_1[1])),
            (float(diem_thang_2[0]), float(diem_thang_2[1])),
            float(khoang_cach_thang_mm),
        )
        px_mm_val = kq_th.px_per_mm
        u_px_mm_val = kq_th.u_px_per_mm
    elif px_per_mm is not None and str(px_per_mm).strip() != "":
        px_mm_val = float(px_per_mm)
        if not math.isfinite(px_mm_val) or px_mm_val <= 0.0:
            raise ValueError("Thang quy đổi px_per_mm phải lớn hơn 0.")

    sessions = lay_danh_sach_phien(phien_path)
    existing_ids = {str(s.get("phien_id", "")) for s in sessions}
    if phien_id and str(phien_id).strip():
        pid = _clean_id(phien_id)
    else:
        base_pid = _clean_id(f"{ma_me}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        pid = base_pid
        stt = 1
        while pid in existing_ids:
            stt += 1
            pid = f"{base_pid}_{stt}"

    rec: dict[str, Any] = {
        "phien_id": pid,
        "ma_me_pha": ma_me,
        "id_thiet_bi": id_tb,
        "id_dien_thoai": id_dt,
        "nguoi_do": nguoi,
        "px_per_mm": px_mm_val,
        "u_px_per_mm": u_px_mm_val,
        "nguon_du_lieu": nguon,
        "ngay_tao": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    sessions = [s for s in sessions if s.get("phien_id") != pid]
    sessions.append(rec)

    p_out = duong_dan_phien_thu(phien_path)
    p_out.parent.mkdir(parents=True, exist_ok=True)
    p_out.write_text(json.dumps(sessions, ensure_ascii=False, indent=2), encoding="utf-8")
    return rec


def _doc_bang_thu_du_lieu_raw(csv_path: str | Path | None = None) -> pd.DataFrame:
    p = duong_dan_du_lieu_thuc_csv(csv_path)
    if not p.exists():
        return pd.DataFrame(columns=COT_CSV_THU_DU_LIEU)
    df = pd.read_csv(p, encoding="utf-8-sig", keep_default_na=True)
    for col in COT_CSV_THU_DU_LIEU:
        if col not in df.columns:
            df[col] = ""
    for str_col in (
        cal.COT_SHA256_ANH, "ly_do_loai", "da_loai", "khai_bao_nguon_anh",
        "nguoi_khai_bao", "phien_id", cal.COT_MA_ME_PHA, cal.COT_TEN_FILE,
        cal.COT_GHI_CHU, cal.COT_NGUON, "kenh_su_dung", "exif_co", "nguoi_do",
        "tinh_tu_khoi_luong", cal.COT_ID_THIET_BI, cal.COT_ID_DIEN_THOAI,
    ):
        if str_col == "da_loai":
            df[str_col] = df[str_col].map(lambda v: "true" if _la_true(v) else "false").astype(object)
        else:
            df[str_col] = df[str_col].astype(object).fillna("").astype(str).astype(object)
    return df


def _ghi_bang_thu_du_lieu_raw(df: pd.DataFrame, csv_path: str | Path | None = None) -> Path:
    p = duong_dan_du_lieu_thuc_csv(csv_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    for col in COT_CSV_THU_DU_LIEU:
        if col not in df.columns:
            df[col] = ""
    ordered = df[COT_CSV_THU_DU_LIEU]
    ordered.to_csv(p, index=False, encoding="utf-8-sig")
    return p


def _doc_img_cfg(config_path: Path = CONFIG_MAC_DINH) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return dict(raw.get("xu_ly_anh", {}) or {})


def ghi_lan_do_thu_du_lieu(
    raw_bytes: bytes,
    ten_file: str,
    phien: dict[str, Any] | str,
    nhiet_do_C: float | None,
    nhiet_do_tham_chieu_C: float | None,
    do_man_chuan_ppt: float | None = None,
    khoi_luong_muoi_g: float | None = None,
    khoi_luong_nuoc_g: float | None = None,
    khoa_ae_af: bool = False,
    khai_bao_nguon_anh: str = "",
    nguoi_khai_bao: str = "",
    ghi_chu: str = "",
    px_per_mm_override: float | None = None,
    roi_tc: tuple[int, int, int, int] | None = None,
    roi_mau: tuple[int, int, int, int] | None = None,
    duong_dan_nguon: Path | str | None = None,
    csv_path: str | Path | None = None,
    anh_dir: str | Path | None = None,
    phien_path: str | Path | None = None,
    config_path: Path = CONFIG_MAC_DINH,
    hieu_chuan_nhiet_ke_path: str | Path | None = None,
    so_mo_phong_path: str | Path | None = None,
    so_da_xu_ly_path: str | Path | None = None,
) -> dict[str, Any]:
    """Đo Δy từ ảnh gốc, áp toàn bộ bảo vệ W0, ghi 1 dòng vào CSV thực & lưu nguyên byte ảnh."""
    if isinstance(phien, str):
        sessions = lay_danh_sach_phien(phien_path)
        found = next((s for s in sessions if s.get("phien_id") == phien), None)
        if found is None:
            raise ValueError(f"Không tìm thấy phiên thu dữ liệu '{phien}'.")
        phien_info = found
    else:
        phien_info = dict(phien)

    phien_id = _clean_id(str(phien_info.get("phien_id") or "PHIEN"))
    nguon_du_lieu = str(phien_info.get("nguon_du_lieu") or cal.NHAN_THUC_TE).strip().upper()
    if nguon_du_lieu not in (cal.NHAN_THUC_TE, cal.NHAN_MO_PHONG):
        raise ValueError("nguon_du_lieu phải là 'THUC_TE' hoặc 'MO_PHONG'.")

    # 1. Bắt buộc nhập CẢ HAI nhiệt độ (không cho bỏ trống ngăn tham chiếu ở chế độ thu dữ liệu)
    if nhiet_do_C is None or not math.isfinite(float(nhiet_do_C)):
        raise ValueError("Chế độ thu dữ liệu bắt buộc nhập nhiệt độ mẫu nước (nhiet_do_C).")
    if nhiet_do_tham_chieu_C is None or not math.isfinite(float(nhiet_do_tham_chieu_C)):
        raise ValueError("Chế độ thu dữ liệu bắt buộc nhập cả nhiệt độ ngăn tham chiếu (nhiet_do_tham_chieu_C).")
    t_mau = float(nhiet_do_C)
    t_tc_doc = float(nhiet_do_tham_chieu_C)

    # 2. Tính độ mặn chuẩn (trực tiếp hoặc từ khối lượng muối/nước)
    tinh_tu_kl = False
    m_muoi_out: Any = ""
    m_nuoc_out: Any = ""
    if khoi_luong_muoi_g is not None and khoi_luong_nuoc_g is not None:
        s_chuan = tinh_do_man_tu_khoi_luong(float(khoi_luong_muoi_g), float(khoi_luong_nuoc_g))
        tinh_tu_kl = True
        m_muoi_out = round(float(khoi_luong_muoi_g), 4)
        m_nuoc_out = round(float(khoi_luong_nuoc_g), 4)
    elif do_man_chuan_ppt is not None and math.isfinite(float(do_man_chuan_ppt)):
        s_chuan = float(do_man_chuan_ppt)
        if s_chuan < 0.0:
            raise ValueError("Độ mặn chuẩn không được âm.")
    else:
        raise ValueError("Phải nhập do_man_chuan_ppt hoặc cặp khối lượng muối (g) và nước (g).")

    # 3. Kiểm tra định dạng byte (X0c: chặn HEIC/HEIF/WebP trước khi giải mã)
    if not raw_bytes:
        raise AnhKhongHopLeError("Chưa cung cấp dữ liệu ảnh.")
    fmt_raw = nhan_dien_dinh_dang_anh_bytes(raw_bytes)
    if fmt_raw in ("HEIC/HEIF", "HEIC", "HEIF", "WebP"):
        raise AnhKhongHoTroDinhDangError(fmt_raw)
    img_bgr = giai_ma_anh_tu_bytes(raw_bytes)

    # 4. SHA-256 & Toàn bộ lớp bảo vệ W0
    sha256_anh = hashlib.sha256(raw_bytes).hexdigest().lower()
    df_existing = _doc_bang_thu_du_lieu_raw(csv_path)
    if len(df_existing) and cal.COT_SHA256_ANH in df_existing.columns:
        existing_shas = {
            str(v).strip().lower()
            for v in df_existing[cal.COT_SHA256_ANH].fillna("")
            if str(v).strip()
        }
        if sha256_anh in existing_shas:
            raise LoiTrungAnhThuDuLieuError(
                f"Ảnh có sha256={sha256_anh[:12]}... đã tồn tại trong bộ dữ liệu thu thập; không cho phép ghi hai lần."
            )

    so_da_xl = _doc_so_anh_da_xu_ly(so_da_xu_ly_path)
    for rec in so_da_xl.get(sha256_anh, []):
        prev_n = str(rec.get("nguon") or "").strip().upper()
        if prev_n and prev_n != nguon_du_lieu:
            raise LoiXungDotNhanAnhError(
                f"Ảnh sha256={sha256_anh[:12]}... từng xử lí với nhãn {prev_n}, không thể ghi nhãn {nguon_du_lieu}."
            )

    safe_name = _clean_filename(ten_file, fallback=f"anh_{sha256_anh[:8]}.png")
    exif_info = thang.doc_exif_may_anh(raw_bytes)
    exif_co = bool(exif_info.get("co_exif_may_anh"))
    kb_nguon = str(khai_bao_nguon_anh or "").strip()
    kb_nguoi = str(nguoi_khai_bao or "").strip()

    if nguon_du_lieu == cal.NHAN_THUC_TE:
        ly_do_mp: list[str] = []
        if doc_nhan_mo_phong(raw_bytes):
            ly_do_mp.append("nhãn SIMULATED nhúng trong metadata ảnh")
        hit_so = tra_cuu_so_anh_mo_phong(raw_bytes, so_path=so_mo_phong_path)
        if hit_so is not None:
            ly_do_mp.append(f"sha256 khớp sổ ảnh mô phỏng ({hit_so.get('duong_dan', '')})")
        if "MO_PHONG" in safe_name.upper() or "SIMULATED" in safe_name.upper():
            ly_do_mp.append("tên file chứa dấu hiệu MO_PHONG/SIMULATED")
        if duong_dan_nguon is not None:
            p_src = Path(duong_dan_nguon)
            if p_src.exists() and kiem_tra_thu_muc_mo_phong(p_src if p_src.is_dir() else p_src.parent, config_path=config_path):
                ly_do_mp.append("nằm trong thư mục ảnh mô phỏng bị chặn")
        if ly_do_mp:
            raise LoiAnhMoPhongGanNhanThucTeError(
                "TỪ CHỐI gắn nhãn THUC_TE: phát hiện ảnh có dấu hiệu mô phỏng (" + "; ".join(ly_do_mp) + ")."
            )
        if not exif_co and (not kb_nguon or not kb_nguoi):
            raise LoiThieuExifAnhThucTeError(
                "Ảnh thiếu EXIF máy ảnh (Make/Model): ở chế độ THUC_TE bắt buộc phải khai báo nguồn ảnh và người chịu trách nhiệm."
            )

    # 5. Áp hiệu chuẩn chéo nhiệt kế (nếu file tồn tại)
    hc_nk_path = Path(hieu_chuan_nhiet_ke_path) if hieu_chuan_nhiet_ke_path is not None else nhiet_ke.FILE_HIEU_CHUAN_NHIET_KE_MAC_DINH
    hc_nk = nhiet_ke.tai_hieu_chuan_cheo_nhiet_ke(hc_nk_path)
    offset_nk: float | str = ""
    t_tc_hieu_chinh = t_tc_doc
    if hc_nk is not None:
        off_c, _ = hc_nk.offset_va_sigma_tai(t_mau)
        offset_nk = round(float(off_c), 5)
        t_tc_hieu_chinh = t_tc_doc - float(off_c)

    # 6. Đo Δy trên ảnh gốc
    img_cfg = _doc_img_cfg(config_path)
    buoc_cot = max(2, int(img_bgr.shape[1] // 250)) if img_bgr.shape[1] > 600 else 2
    kq_do = do_delta_y_tu_anh(
        img_bgr,
        roi_tham_chieu=roi_tc,
        roi_mau=roi_mau,
        buoc_nhay_cot=buoc_cot,
        nguong_bao_hoa=int(img_cfg.get("nguong_bao_hoa", 250)),
        ti_le_bao_hoa_toi_da=float(img_cfg.get("ti_le_bao_hoa_toi_da", 0.02)),
        snr_toi_thieu=float(img_cfg.get("snr_toi_thieu", 10.0)),
        tao_anh_ve=False,
        kenh_laser=str(img_cfg.get("kenh_laser", "auto")),
        ti_le_cot_bao_hoa_nghiem_trong=float(img_cfg.get("ti_le_cot_bao_hoa_nghiem_trong", 0.30)),
        so_cot_lien_tiep_bao_hoa=int(img_cfg.get("so_cot_lien_tiep_bao_hoa", 15)),
        nguong_nen_khong_deu=float(img_cfg.get("nguong_nen_khong_deu", 30.0)),
    )
    if not kq_do.chat_luong.hop_le or not math.isfinite(kq_do.delta_y_px):
        ly_do_cl = "; ".join(kq_do.chat_luong.canh_bao) or "Chất lượng ảnh không đạt ngưỡng đo"
        raise ValueError(f"Ảnh không đạt chất lượng để ghi vào bộ hiệu chuẩn: {ly_do_cl}")

    # 7. Lưu nguyên byte ảnh gốc vào data/anh_thuc/<phien_id>/ (KHÔNG nén/ghi đè)
    dir_phien = duong_dan_thu_muc_anh_thuc(anh_dir) / phien_id
    dir_phien.mkdir(parents=True, exist_ok=True)
    dest_path = dir_phien / safe_name
    if dest_path.exists():
        stem = dest_path.stem
        suf = dest_path.suffix
        stt = 1
        while (dir_phien / f"{stem}_{stt}{suf}").exists():
            stt += 1
        dest_path = dir_phien / f"{stem}_{stt}{suf}"
    dest_path.write_bytes(raw_bytes)

    # 8. Ghi dòng mới vào CSV & cập nhật sổ ảnh đã xử lí
    px_use = px_per_mm_override if (px_per_mm_override is not None and float(px_per_mm_override) > 0) else phien_info.get("px_per_mm")
    ghi_chu_parts: list[str] = []
    if str(ghi_chu or "").strip():
        ghi_chu_parts.append(str(ghi_chu).strip())
    if tinh_tu_kl:
        ghi_chu_parts.append(f"tính từ khối lượng (muối={m_muoi_out}g, nước={m_nuoc_out}g)")
    if hc_nk is not None:
        ghi_chu_parts.append(f"đã trừ offset nhiệt kế={offset_nk:+.3f}°C")
    ngay_hom_nay = datetime.now().strftime("%Y-%m-%d")

    row = {
        cal.COT_DO_MAN: round(s_chuan, 5),
        cal.COT_NHIET_DO: round(t_mau, 4),
        cal.COT_NHIET_DO_TC: round(t_tc_hieu_chinh, 4),
        cal.COT_DELTA_Y: round(float(kq_do.delta_y_px), 5),
        cal.COT_PX_PER_MM: round(float(px_use), 5) if (px_use not in (None, "")) else "",
        cal.COT_DO_DUC: round(float(kq_do.chi_so_do_duc_tuong_doi), 5),
        cal.COT_MA_ME_PHA: str(phien_info.get("ma_me_pha") or ""),
        cal.COT_NGAY_DO: ngay_hom_nay,
        cal.COT_GHI_CHU: "; ".join(ghi_chu_parts),
        cal.COT_ID_THIET_BI: str(phien_info.get("id_thiet_bi") or ""),
        cal.COT_ID_DIEN_THOAI: str(phien_info.get("id_dien_thoai") or ""),
        cal.COT_NGUON: nguon_du_lieu,
        cal.COT_KHOA_AE_AF: 1 if khoa_ae_af else 0,
        cal.COT_SHA256_ANH: sha256_anh,
        "kenh_su_dung": kq_do.kenh_su_dung,
        "exif_co": "true" if exif_co else "false",
        "nguoi_do": str(phien_info.get("nguoi_do") or ""),
        "phien_id": phien_id,
        cal.COT_TEN_FILE: dest_path.name,
        "tinh_tu_khoi_luong": "true" if tinh_tu_kl else "false",
        "khoi_luong_muoi_g": m_muoi_out,
        "khoi_luong_nuoc_g": m_nuoc_out,
        "da_loai": "false",
        "ly_do_loai": "",
        "khai_bao_nguon_anh": "" if exif_co else kb_nguon,
        "nguoi_khai_bao": "" if exif_co else kb_nguoi,
        cal.COT_NHIET_DO_TC_DOC: round(t_tc_doc, 4),
        cal.COT_OFFSET_NHIET_KE: offset_nk,
    }

    df_new = pd.concat([df_existing, pd.DataFrame([row])], ignore_index=True)
    _ghi_bang_thu_du_lieu_raw(df_new, csv_path)
    _ghi_so_anh_da_xu_ly([(sha256_anh, nguon_du_lieu, dest_path.name)], so_path=so_da_xu_ly_path)

    return {
        "row": row,
        "anh_da_luu": str(dest_path),
        "exif": exif_info,
        "hieu_chuan_nhiet_ke_ap_dung": hc_nk is not None,
        "delta_y_px": float(kq_do.delta_y_px),
        "sai_so_delta_y_px": float(kq_do.sai_so_delta_y_px),
    }


def danh_dau_loai_bo_lan_do(
    ly_do_loai: str,
    sha256_anh: str | None = None,
    row_index: int | None = None,
    csv_path: str | Path | None = None,
) -> dict[str, Any]:
    """Đánh dấu loại bỏ một lần đo (KHÔNG xóa dòng khỏi CSV) kèm lí do bắt buộc."""
    ly_do = str(ly_do_loai or "").strip()
    if not ly_do:
        raise ValueError("Bắt buộc phải ghi rõ lí do khi đánh dấu loại bỏ một lần đo.")

    df = _doc_bang_thu_du_lieu_raw(csv_path)
    if len(df) == 0:
        raise ValueError("Chưa có dữ liệu thu thập nào để loại bỏ.")

    idx_target: int | None = None
    if sha256_anh is not None and str(sha256_anh).strip():
        target = str(sha256_anh).strip().lower()
        for i, val in enumerate(df[cal.COT_SHA256_ANH].fillna("")):
            if str(val).strip().lower() == target:
                idx_target = i
                break
    elif row_index is not None:
        i_req = int(row_index)
        if 0 <= i_req < len(df):
            idx_target = i_req

    if idx_target is None:
        raise ValueError("Không tìm thấy lần đo cần đánh dấu loại bỏ.")

    df.at[idx_target, "da_loai"] = "true"
    df.at[idx_target, "ly_do_loai"] = ly_do
    _ghi_bang_thu_du_lieu_raw(df, csv_path)
    return df.iloc[idx_target].to_dict()


def tinh_tien_do_thu_du_lieu(
    csv_path: str | Path | None = None,
    config_path: str | Path = CONFIG_MAC_DINH,
    muon_hoc_D: bool = False,
    don_vi_y: str = "px",
) -> dict[str, Any]:
    """Tính tiến độ thu dữ liệu theo thiết kế thí nghiệm V4, các ô còn thiếu và gợi ý ô tiếp theo."""
    cfg_tk = tai_cau_hinh_thiet_ke(config_path)
    df_all = _doc_bang_thu_du_lieu_raw(csv_path)
    n_tong = int(len(df_all))
    mask_loai = df_all["da_loai"].map(_la_true).to_numpy(dtype=bool) if n_tong else np.zeros(0, dtype=bool)
    n_loai = int(np.count_nonzero(mask_loai))
    df_active = df_all.loc[~mask_loai].reset_index(drop=True) if n_tong else df_all.copy()

    # Loại bản sao khỏi đếm lặp thực tế
    bs = cal.phat_hien_ban_sao_du_lieu(df_active)
    mask_bs = np.asarray(bs["mask_ban_sao"], dtype=bool) if len(df_active) else np.zeros(0, dtype=bool)
    df_nodup = df_active.loc[~mask_bs].reset_index(drop=True) if len(df_active) else df_active.copy()

    kt_v4 = kiem_tra_thiet_ke_thi_nghiem(
        df_active,
        config_path=config_path,
        muon_hoc_D=muon_hoc_D,
        don_vi_y=don_vi_y,
    )

    s_min, s_max = float(cfg_tk["dai_man_muc_tieu_ppt"][0]), float(cfg_tk["dai_man_muc_tieu_ppt"][1])
    req_s = max(2, int(cfg_tk["so_muc_man_toi_thieu"]))
    req_t = max(1, int(cfg_tk["so_muc_nhiet_toi_thieu"]))
    req_lap = max(1, int(cfg_tk["so_lan_lap_toi_thieu_moi_o"]))

    # Khung mức mục tiêu chuẩn (có thể bao gồm cả các mức người dùng đã đo ngoài lưới mặc định)
    muc_s_co_ban = np.round(np.linspace(s_min, s_max, req_s), 1).tolist()
    if cfg_tk["phai_co_muc_0"] and 0.0 not in muc_s_co_ban:
        muc_s_co_ban = sorted({0.0, *muc_s_co_ban})
    if len(df_nodup):
        s_thuc = pd.to_numeric(df_nodup[cal.COT_DO_MAN], errors="coerce").dropna().round(1).tolist()
        muc_s_luoi = sorted({*muc_s_co_ban, *s_thuc})
    else:
        muc_s_luoi = muc_s_co_ban

    # Các mức nhiệt độ: mặc định dùng [20, 25, 30] hoặc theo số mức yêu cầu, ghép với các mức thực tế cách nhau >= 2°C
    span_t = max(float(cfg_tk["bien_do_nhiet_toi_thieu_C"]), 4.0)
    t_tam = 25.0
    muc_t_mac_dinh = np.round(np.linspace(t_tam - span_t / 2.0, t_tam + span_t / 2.0, req_t), 1).tolist()
    if len(df_nodup):
        t_vals = pd.to_numeric(df_nodup[cal.COT_NHIET_DO], errors="coerce").dropna().to_numpy(float)
        muc_t_gom: list[float] = []
        for tv in sorted(t_vals):
            if not muc_t_gom or abs(tv - muc_t_gom[-1]) >= 2.0:
                muc_t_gom.append(round(float(tv), 1))
        muc_t_luoi = list(muc_t_gom)
        for tm in muc_t_mac_dinh:
            if len(muc_t_luoi) >= req_t:
                break
            if all(abs(tm - x) >= 2.0 for x in muc_t_luoi):
                muc_t_luoi.append(tm)
        muc_t_luoi = sorted(muc_t_luoi)
    else:
        muc_t_luoi = muc_t_mac_dinh

    # Đếm số lần lặp thực (đã trừ bản sao và đã trừ dòng bị loại) vào từng ô (S, T)
    dem_o: dict[tuple[float, float], int] = {(s, t): 0 for s in muc_s_luoi for t in muc_t_luoi}
    if len(df_nodup):
        for _, r in df_nodup.iterrows():
            sv = float(r[cal.COT_DO_MAN])
            tv = float(r[cal.COT_NHIET_DO])
            if not (math.isfinite(sv) and math.isfinite(tv)):
                continue
            s_gan = min(muc_s_luoi, key=lambda x: abs(x - sv))
            t_gan = min(muc_t_luoi, key=lambda x: abs(x - tv))
            dem_o[(s_gan, t_gan)] = dem_o.get((s_gan, t_gan), 0) + 1

    luoi_o: list[dict[str, Any]] = []
    o_con_thieu: list[dict[str, Any]] = []
    for s in muc_s_luoi:
        for t in muc_t_luoi:
            cnt = dem_o.get((s, t), 0)
            thieu = max(0, req_lap - cnt)
            item = {
                "S_ppt": s,
                "T_C": t,
                "so_lan_lap": cnt,
                "muc_tieu_lap": req_lap,
                "con_thieu": thieu,
                "dat": cnt >= req_lap,
            }
            luoi_o.append(item)
            if thieu > 0:
                o_con_thieu.append(item)

    # Gợi ý ô tiếp theo (không bắt buộc theo)
    goi_y: dict[str, Any] | None = None
    if o_con_thieu:
        uu_tien = sorted(
            o_con_thieu,
            key=lambda it: (0 if abs(it["S_ppt"]) <= 0.1 else 1, it["so_lan_lap"], it["T_C"], it["S_ppt"]),
        )[0]
        goi_y = {
            **uu_tien,
            "thong_diep": (
                f"Gợi ý tiếp theo (không bắt buộc): S = {uu_tien['S_ppt']:g} ‰, "
                f"T ≈ {uu_tien['T_C']:g} °C (hiện có {uu_tien['so_lan_lap']}/{req_lap} lần lặp)."
            ),
        }

    ly_do_loai_list = [
        str(x).strip()
        for x in df_all.loc[mask_loai, "ly_do_loai"].fillna("")
        if str(x).strip()
    ] if n_loai > 0 else []

    return {
        "tong_dong": n_tong,
        "so_dong_hop_le": int(len(df_active)),
        "so_dong_doc_lap": int(len(df_nodup)),
        "so_dong_da_loai": n_loai,
        "tom_tat_ly_do_loai": ly_do_loai_list,
        "muc_S_luoi": muc_s_luoi,
        "muc_T_luoi": muc_t_luoi,
        "luoi_o": luoi_o,
        "o_con_thieu": o_con_thieu,
        "goi_y_tiep_theo": goi_y,
        "kiem_tra_thiet_ke": kt_v4,
    }
