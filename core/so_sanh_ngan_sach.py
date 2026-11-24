"""Đối chiếu ngân sách sai số thực nghiệm với lí thuyết — X5.

Mục đích vật lí & thống kê:
- Tính phần dư độ mặn e_i = Ŝ_i − S_i (‰) từ đường chuẩn thực nghiệm.
- Phân rã phương sai phần dư thành các thành phần thực nghiệm (ANOVA method-of-moments
  không âm) theo đơn vị ‰:
  1. Sai số lặp lại trong cùng ô (cùng S, T, mẻ pha, điện thoại): σ_lặp_lại
  2. Biến thiên giữa các mẻ pha (ma_me_pha): σ_mẻ_pha
  3. Biến thiên giữa các điện thoại (id_dien_thoai): σ_điện_thoại
  4. Biến thiên nhiệt độ còn dư sau hiệu chuẩn: σ_nhiệt_độ_dư
  5. Trôi laser đo từ X2 (data/phan_tich_troi_laser.json, quy đổi sang ‰) nếu có.
- Nếu nhóm chỉ có 1 mức (ví dụ chỉ 1 mẻ pha hoặc 1 điện thoại), ghi chú rõ
  "không tách được" thay vì gán bằng 0 giả tạo.
- Đối chiếu σ_tổng_thực_nghiệm với tổng RSS lí thuyết từ core/optics.ngan_sach_sai_so;
  khi tỉ lệ vượt ngưỡng `ngan_sach_so_sanh.he_so_canh_bao` (1.5), bật cờ cảnh báo
  `SAI_SO_THUC_VUOT_LY_THUYET`.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from core import calibration as cal
from core import optics as op
from core.chuyen_duong_chuan import _loc_du_lieu_hieu_chuan_sach
from core.troi_laser import duong_dan_phan_tich_troi

ROOT = Path(__file__).resolve().parents[1]
CONFIG_MAC_DINH = ROOT / "config.yaml"


def tai_cau_hinh_ngan_sach_so_sanh(config_path: str | Path | None = None) -> dict[str, Any]:
    """Đọc hệ số cảnh báo sai số thực vượt lí thuyết từ config.yaml."""
    cfg_p = Path(config_path) if config_path else CONFIG_MAC_DINH
    raw: dict[str, Any] = {}
    if cfg_p.exists():
        raw = yaml.safe_load(cfg_p.read_text(encoding="utf-8")) or {}
    nss = raw.get("ngan_sach_so_sanh") or {}
    return {
        "he_so_canh_bao": float(nss.get("he_so_canh_bao", 1.5)),
    }


def _anova_thanh_phan_nhom(gia_tri: np.ndarray, nhan_nhom: list[str]) -> tuple[float | None, str]:
    """Ước lượng độ lệch chuẩn giữa các nhóm theo ANOVA một nhân tố (random effects, không âm)."""
    nhom_sach = [str(g or "").strip() for g in nhan_nhom]
    hop_le_idx = [i for i, g in enumerate(nhom_sach) if g]
    if not hop_le_idx:
        return None, "không tách được (thiếu nhãn nhóm)"

    y = gia_tri[hop_le_idx]
    nhom = [nhom_sach[i] for i in hop_le_idx]
    muc = sorted(set(nhom))
    k = len(muc)
    if k < 2:
        return None, f"không tách được (chỉ có 1 mức: {muc[0]})"

    n = len(y)
    if n <= k:
        return None, "không tách được (không đủ bậc tự do trong nhóm)"

    y_bar = float(np.mean(y))
    ssb = 0.0
    ssw = 0.0
    n_k_sq_sum = 0.0
    for m in muc:
        yk = y[[i for i, g in enumerate(nhom) if g == m]]
        nk = len(yk)
        n_k_sq_sum += float(nk * nk)
        mk = float(np.mean(yk))
        ssb += nk * (mk - y_bar) ** 2
        if nk > 1:
            ssw += float(np.sum((yk - mk) ** 2))

    msb = ssb / float(k - 1)
    msw = ssw / float(n - k)
    n0 = (float(n) - n_k_sq_sum / float(n)) / float(k - 1)
    if n0 <= 1e-12:
        return None, "không tách được (cỡ nhóm suy biến)"
    var_between = max(0.0, (msb - msw) / n0)
    return float(math.sqrt(var_between)), f"ước lượng ANOVA từ {k} nhóm"


def phan_ra_phuong_sai_phan_du(
    nguon: pd.DataFrame | str | Path,
    *,
    bac_ep: int | None = None,
    don_vi_y: str = "px",
    config_path: str | Path | None = None,
    phan_tich_troi_path: str | Path | None = None,
) -> dict[str, Any]:
    """Khớp đường chuẩn và phân rã phương sai phần dư thực nghiệm (‰)."""
    cfg_p = Path(config_path) if config_path else CONFIG_MAC_DINH
    cfg_hc = cal.CauHinhHieuChuan.tu_yaml(cfg_p)
    cfg_qh = op.CauHinhQuangHoc.tu_yaml(cfg_p)

    df_sach, thong_ke_loc = _loc_du_lieu_hieu_chuan_sach(nguon, cfg_hc)
    bc = cal.dung_duong_chuan(df_sach, cau_hinh=cfg_hc, bac_ep=bac_ep, don_vi_y=don_vi_y)
    mh = bc.mo_hinh

    t_tc_col = cal.COT_NHIET_DO_TC if cal.COT_NHIET_DO_TC in df_sach.columns else None
    px_col = cal.COT_PX_PER_MM if cal.COT_PX_PER_MM in df_sach.columns else None
    phan_du = np.empty(len(df_sach), dtype=float)
    for i, row in df_sach.iterrows():
        t_tc = float(row[t_tc_col]) if (t_tc_col and pd.notna(row[t_tc_col])) else None
        px_mm = float(row[px_col]) if (px_col and pd.notna(row[px_col])) else None
        kq = cal.uoc_luong_do_man(
            mh,
            delta_y_px=float(row[cal.COT_DELTA_Y]),
            T_C=float(row[cal.COT_NHIET_DO]),
            T_tham_chieu_C=t_tc,
            px_per_mm=px_mm if don_vi_y == "mm" else None,
        )
        phan_du[i] = float(kq.S_ppt - float(row[cal.COT_DO_MAN]))

    sigma_tong_thuc = float(np.std(phan_du, ddof=1)) if len(phan_du) > 1 else 0.0
    rms_phan_du = float(np.sqrt(np.mean(phan_du * phan_du)))

    # 1. Lặp lại trong ô (S, T làm tròn 0.1°C, ma_me_pha, id_dien_thoai)
    me_vals = (
        df_sach[cal.COT_MA_ME_PHA].astype(object).fillna("").astype(str).tolist()
        if cal.COT_MA_ME_PHA in df_sach.columns
        else [""] * len(df_sach)
    )
    dt_vals = (
        df_sach[cal.COT_ID_DIEN_THOAI].astype(object).fillna("").astype(str).tolist()
        if cal.COT_ID_DIEN_THOAI in df_sach.columns
        else [""] * len(df_sach)
    )
    cells: dict[tuple[Any, ...], list[float]] = {}
    for i, row in df_sach.iterrows():
        key = (
            round(float(row[cal.COT_DO_MAN]), 4),
            round(float(row[cal.COT_NHIET_DO]), 1),
            me_vals[i].strip(),
            dt_vals[i].strip(),
        )
        cells.setdefault(key, []).append(float(phan_du[i]))

    ss_within = 0.0
    df_within = 0
    for vals in cells.values():
        if len(vals) >= 2:
            arr = np.asarray(vals, dtype=float)
            ss_within += float(np.sum((arr - np.mean(arr)) ** 2))
            df_within += len(vals) - 1

    if df_within >= 1:
        sigma_lap_lai: float | None = float(math.sqrt(ss_within / float(df_within)))
        ghi_chu_lap = f"pooled từ {df_within} bậc tự do lặp lại trong ô"
    else:
        sigma_lap_lai = None
        ghi_chu_lap = "không tách được (không có ô nào lặp ≥ 2 lần)"

    # 2. Giữa mẻ pha & 3. Giữa điện thoại
    sigma_me_pha, ghi_chu_me = _anova_thanh_phan_nhom(phan_du, me_vals)
    sigma_dien_thoai, ghi_chu_dt = _anova_thanh_phan_nhom(phan_du, dt_vals)

    # 4. Phần dư nhiệt độ (kiểm sự phụ thuộc còn sót của e theo T và D)
    t_arr = df_sach[cal.COT_NHIET_DO].to_numpy(dtype=float)
    if float(np.std(t_arr)) > 0.2 and len(phan_du) >= 6:
        cols_t = [np.ones(len(t_arr)), t_arr - float(np.mean(t_arr))]
        if t_tc_col:
            t_tc_raw = pd.to_numeric(df_sach[t_tc_col], errors="coerce").to_numpy(dtype=float)
            t_tc_arr = np.where(np.isfinite(t_tc_raw), t_tc_raw, t_arr)
            d_arr = t_arr - t_tc_arr
            if float(np.std(d_arr)) > 0.05:
                cols_t.append(d_arr - float(np.mean(d_arr)))
        X_t = np.column_stack(cols_t)
        beta_t, _, _, _ = np.linalg.lstsq(X_t, phan_du, rcond=None)
        e_t_hat = X_t[:, 1:] @ beta_t[1:]
        sigma_t_du: float | None = float(np.std(e_t_hat, ddof=1)) if len(e_t_hat) > 1 else 0.0
        ghi_chu_t = "ước lượng từ hồi quy phần dư theo nhiệt độ còn sót"
    else:
        sigma_t_du = None
        ghi_chu_t = "không tách được (biến thiên nhiệt độ quá hẹp)"

    # 5. Trôi laser từ X2 nếu đã đo
    p_troi = duong_dan_phan_tich_troi(phan_tich_troi_path)
    sigma_troi_x2: float | None = None
    ghi_chu_troi = "chưa có báo cáo trôi laser X2"
    if p_troi.exists():
        try:
            troi_js = json.loads(p_troi.read_text(encoding="utf-8"))
            std_dy = float(troi_js.get("std_tho_delta_y_px", 0.0))
            s_tb = float(np.mean(df_sach[cal.COT_DO_MAN].to_numpy(dtype=float)))
            t_tb = float(np.mean(t_arr))
            px_ppt = op.pixel_moi_phan_nghin(s_tb, t_tb, cfg_qh)
            sigma_troi_x2 = float(std_dy / max(px_ppt, 1e-12))
            ghi_chu_troi = f"từ X2 std(Δy)={std_dy:.3f} px quy đổi sang ‰"
        except Exception:
            sigma_troi_x2 = None

    return {
        "thong_ke_loc": thong_ke_loc,
        "bac_duong_chuan": int(mh.bac),
        "sigma_tong_thuc_nghiem_ppt": sigma_tong_thuc,
        "rms_phan_du_ppt": rms_phan_du,
        "sigma_lap_lai_ppt": sigma_lap_lai,
        "ghi_chu_lap_lai": ghi_chu_lap,
        "sigma_me_pha_ppt": sigma_me_pha,
        "ghi_chu_me_pha": ghi_chu_me,
        "sigma_dien_thoai_ppt": sigma_dien_thoai,
        "ghi_chu_dien_thoai": ghi_chu_dt,
        "sigma_nhiet_do_du_ppt": sigma_t_du,
        "ghi_chu_nhiet_do_du": ghi_chu_t,
        "sigma_troi_laser_x2_ppt": sigma_troi_x2,
        "ghi_chu_troi_laser": ghi_chu_troi,
    }


def bang_doi_chieu_df(kq: dict[str, Any]) -> pd.DataFrame:
    """Chuyển kết quả đối chiếu X5 thành DataFrame phẳng để xuất CSV/Markdown."""
    return pd.DataFrame(kq.get("bang_doi_chieu") or [])


def so_sanh_ngan_sach_sai_so(
    nguon: pd.DataFrame | str | Path,
    *,
    S_tham_chieu_ppt: float = 15.0,
    T_tham_chieu_C: float = 25.0,
    bac_ep: int | None = None,
    don_vi_y: str = "px",
    config_path: str | Path | None = None,
    tham_so_do_duoc_path: str | Path | None = None,
    phan_tich_troi_path: str | Path | None = None,
    luu_json_path: str | Path | None = None,
) -> dict[str, Any]:
    """Đối chiếu ngân sách sai số thực nghiệm với ngân sách sai số lí thuyết (`core/optics.py`)."""
    cfg_p = Path(config_path) if config_path else CONFIG_MAC_DINH
    raw_cfg: dict[str, Any] = {}
    if cfg_p.exists():
        raw_cfg = yaml.safe_load(cfg_p.read_text(encoding="utf-8")) or {}
    ps = raw_cfg.get("phan_tich_sai_so") or {}
    cfg_qh = op.CauHinhQuangHoc.tu_yaml(cfg_p)
    he_so_cb = float(tai_cau_hinh_ngan_sach_so_sanh(cfg_p)["he_so_canh_bao"])

    ns_ly_thuyet = op.ngan_sach_sai_so(
        S_tham_chieu_ppt,
        T_tham_chieu_C,
        cfg_qh,
        float(ps.get("sai_so_tim_tam_px", 0.05)),
        float(ps.get("lech_nhiet_do_hai_ngan_C", 0.5)),
        float(ps.get("sai_so_goc_A_do", 0.05)),
        float(ps.get("troi_laser_chung_px", 5.0)),
        float(ps.get("he_so_triet_chung", 0.01)),
        uu_tien_do_duoc=True,
        tham_so_do_duoc_path=tham_so_do_duoc_path,
    )

    thuc_nghiem = phan_ra_phuong_sai_phan_du(
        nguon,
        bac_ep=bac_ep,
        don_vi_y=don_vi_y,
        config_path=cfg_p,
        phan_tich_troi_path=phan_tich_troi_path,
    )

    sigma_thuc = float(thuc_nghiem["sigma_tong_thuc_nghiem_ppt"])
    sigma_lt = float(ns_ly_thuyet["tong_RSS"])
    ty_le = sigma_thuc / max(sigma_lt, 1e-12)
    vuot = bool(ty_le > he_so_cb)

    canh_bao_chi_tiet: list[dict[str, str]] = []
    if vuot:
        canh_bao_chi_tiet.append({
            "ma": "SAI_SO_THUC_VUOT_LY_THUYET",
            "cap": "canh_bao",
            "thong_diep": (
                f"Sai số thực nghiệm tổng hợp ({sigma_thuc:.3f} ‰) vượt {ty_le:.2f}× ngân sách lí thuyết "
                f"({sigma_lt:.3f} ‰, ngưỡng cảnh báo {he_so_cb:.2f}×). Cần rà soát nguồn nhiễu chưa mô hình hóa."
            ),
        })

    bang = [
        {
            "hang_muc": "1. Lặp lại trong ô (tìm tâm + nhiễu đo ngắn hạn)",
            "thuc_nghiem_ppt": round(thuc_nghiem["sigma_lap_lai_ppt"], 4) if thuc_nghiem["sigma_lap_lai_ppt"] is not None else None,
            "ly_thuyet_ppt": round(float(ns_ly_thuyet["tim_tam"]), 4),
            "nguon_ly_thuyet": ns_ly_thuyet.nguon["tim_tam"],
            "ghi_chu": thuc_nghiem["ghi_chu_lap_lai"],
        },
        {
            "hang_muc": "2. Giữa các mẻ pha chuẩn",
            "thuc_nghiem_ppt": round(thuc_nghiem["sigma_me_pha_ppt"], 4) if thuc_nghiem["sigma_me_pha_ppt"] is not None else None,
            "ly_thuyet_ppt": None,
            "nguon_ly_thuyet": "chưa mô hình hóa riêng",
            "ghi_chu": thuc_nghiem["ghi_chu_me_pha"],
        },
        {
            "hang_muc": "3. Giữa các điện thoại",
            "thuc_nghiem_ppt": round(thuc_nghiem["sigma_dien_thoai_ppt"], 4) if thuc_nghiem["sigma_dien_thoai_ppt"] is not None else None,
            "ly_thuyet_ppt": None,
            "nguon_ly_thuyet": "chưa mô hình hóa riêng",
            "ghi_chu": thuc_nghiem["ghi_chu_dien_thoai"],
        },
        {
            "hang_muc": "4. Nhiệt độ hai ngăn / phần dư nhiệt độ",
            "thuc_nghiem_ppt": round(thuc_nghiem["sigma_nhiet_do_du_ppt"], 4) if thuc_nghiem["sigma_nhiet_do_du_ppt"] is not None else None,
            "ly_thuyet_ppt": round(float(ns_ly_thuyet["nhiet_do"]), 4),
            "nguon_ly_thuyet": ns_ly_thuyet.nguon["nhiet_do"],
            "ghi_chu": thuc_nghiem["ghi_chu_nhiet_do_du"],
        },
        {
            "hang_muc": "5. Trôi laser & rung còn sót sau vi sai",
            "thuc_nghiem_ppt": round(thuc_nghiem["sigma_troi_laser_x2_ppt"], 4) if thuc_nghiem["sigma_troi_laser_x2_ppt"] is not None else None,
            "ly_thuyet_ppt": round(float(ns_ly_thuyet["troi_laser"]), 4),
            "nguon_ly_thuyet": ns_ly_thuyet.nguon["troi_laser"],
            "ghi_chu": thuc_nghiem["ghi_chu_troi_laser"],
        },
        {
            "hang_muc": "6. Sai số gia công góc A (lí thuyết)",
            "thuc_nghiem_ppt": None,
            "ly_thuyet_ppt": round(float(ns_ly_thuyet["goc_A"]), 4),
            "nguon_ly_thuyet": ns_ly_thuyet.nguon["goc_A"],
            "ghi_chu": "gộp vào phần dư tổng hợp",
        },
        {
            "hang_muc": "∑ TỔNG HỢP (1σ)",
            "thuc_nghiem_ppt": round(sigma_thuc, 4),
            "ly_thuyet_ppt": round(sigma_lt, 4),
            "nguon_ly_thuyet": "hỗn hợp" if "đo được" in ns_ly_thuyet.nguon.values() else "giả định",
            "ghi_chu": f"Tỉ lệ thực/lí thuyết = {ty_le:.2f}× (ngưỡng {he_so_cb:.2f}×)",
        },
    ]

    out = {
        "he_so_canh_bao": he_so_cb,
        "sigma_tong_thuc_nghiem_ppt": sigma_thuc,
        "sigma_tong_ly_thuyet_ppt": sigma_lt,
        "ty_le_thuc_tren_ly_thuyet": ty_le,
        "sai_so_thuc_vuot_ly_thuyet": vuot,
        "thuc_nghiem": thuc_nghiem,
        "ly_thuyet": ns_ly_thuyet.to_dict_day_du(),
        "bang_doi_chieu": bang,
        "canh_bao_chi_tiet": canh_bao_chi_tiet,
    }
    if luu_json_path is not None:
        p_out = Path(luu_json_path)
        p_out.parent.mkdir(parents=True, exist_ok=True)
        p_out.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
