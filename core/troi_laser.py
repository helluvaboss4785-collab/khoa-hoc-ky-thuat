"""Phân tích độ trôi laser theo thời gian và mức triệt nhiễu chung κ — X2.

Mục đích vật lí:
Khi đặt nước cất vào CẢ HAI ngăn (ΔS = 0), mọi dịch chuyển giống hệt nhau
của cả vạch tham chiếu y_tc(t) và vạch mẫu y_mẫu(t) (do trôi nhiệt diode laser,
giãn nở giá đỡ, rung bàn...) được xem là nhiễu/trôi chung. Phép đo vi sai
Δy(t) = y_mẫu(t) − y_tc(t) kỳ vọng khử phần chung đó với hệ số triệt:

    κ = 1 − σ(Δy) / σ_đơn

trong đó σ(Δy) là độ lệch chuẩn của hiệu Δy(t) (không loại xu hướng tuyến tính
của từng kênh trước), còn σ_đơn = 0.5 · (σ(y_tc) + σ(y_mẫu)) là độ lệch chuẩn
trung bình của từng kênh đơn riêng lẻ. Khi hai kênh trôi hệt nhau, σ(Δy) << σ_đơn
nên κ → 1; ngược lại nếu hai kênh trôi độc lập hoặc ngược chiều, κ thấp (≤ 0.2).

Phần trôi chung còn lọt vào Δy dùng bảo thủ cho ngân sách sai số là 1 − κ_lo
(với κ_lo là cận dưới khoảng tin cậy 95% block-bootstrap của κ).
"""
from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd
import yaml
from scipy import stats

from core import thang
from core.measure import (
    AnhKhongHopLeError,
    AnhKhongHoTroDinhDangError,
    do_delta_y_tu_anh,
    giai_ma_anh_tu_bytes,
)
from scripts.xu_ly_thu_muc_anh import (
    LoiAnhMoPhongGanNhanThucTeError,
    _doc_so_anh_da_xu_ly,
)
from sim.synth import doc_nhan_mo_phong, tra_cuu_so_anh_mo_phong

ROOT = Path(__file__).resolve().parents[1]
CONFIG_MAC_DINH = ROOT / "config.yaml"
THAM_SO_DO_DUOC_MAC_DINH = ROOT / "data" / "tham_so_do_duoc.json"
PHAN_TICH_TROI_MAC_DINH = ROOT / "data" / "phan_tich_troi_laser.json"


class LoiDuLieuTroiKhongDuError(ValueError):
    """Dữ liệu chuỗi trôi không đủ khung hoặc không đủ thời lượng tối thiểu để áp dụng."""


def duong_dan_tham_so_do_duoc(path: str | Path | None = None) -> Path:
    """Đường dẫn file JSON lưu các tham số ĐÃ ĐO ĐƯỢC (chỉ ghi khi có lệnh --ap-dung)."""
    if path is not None:
        return Path(path)
    env = os.environ.get("SALINITY_THAM_SO_DO_DUOC_PATH", "").strip()
    return Path(env) if env else THAM_SO_DO_DUOC_MAC_DINH


def duong_dan_phan_tich_troi(path: str | Path | None = None) -> Path:
    """Đường dẫn file JSON lưu báo cáo phân tích độ trôi laser."""
    if path is not None:
        return Path(path)
    env = os.environ.get("SALINITY_PHAN_TICH_TROI_PATH", "").strip()
    return Path(env) if env else PHAN_TICH_TROI_MAC_DINH


def doc_tham_so_do_duoc(path: str | Path | None = None) -> dict[str, Any]:
    """Đọc toàn bộ file tham số đo được nếu đã tồn tại (trả dict rỗng nếu chưa có)."""
    p = duong_dan_tham_so_do_duoc(path)
    if not p.exists():
        return {"tham_so": {}, "lich_su": []}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"tham_so": {}, "lich_su": []}
    if not isinstance(raw, dict):
        return {"tham_so": {}, "lich_su": []}
    tham_so = raw.get("tham_so")
    if not isinstance(tham_so, dict):
        tham_so = {}
    lich_su = raw.get("lich_su")
    if not isinstance(lich_su, list):
        lich_su = []
    return {
        "nguon": raw.get("nguon", "ĐO ĐƯỢC"),
        "ngay_cap_nhat": raw.get("ngay_cap_nhat", ""),
        "tham_so": tham_so,
        "lich_su": lich_su,
    }


def lay_tham_so_do_duoc(khoa: str, path: str | Path | None = None) -> dict[str, Any] | None:
    """Lấy mục tham số đã đo theo khóa (vd 'he_so_triet_chung') nếu tồn tại và hợp lệ."""
    data = doc_tham_so_do_duoc(path)
    muc = data.get("tham_so", {}).get(khoa)
    if not isinstance(muc, dict) or "gia_tri" not in muc:
        return None
    try:
        val = float(muc["gia_tri"])
    except (TypeError, ValueError):
        return None
    if not math.isfinite(val):
        return None
    return {**muc, "gia_tri": val}


def ghi_tham_so_do_duoc(
    cap_nhat: dict[str, dict[str, Any] | float],
    *,
    nguon: str = "ĐO ĐƯỢC",
    nguoi_thuc_hien: str,
    ngay: str | None = None,
    path: str | Path | None = None,
) -> dict[str, Any]:
    """Ghi nhận tường minh các tham số đo được vào JSON riêng (KHÔNG ghi đè config.yaml)."""
    nguoi = str(nguoi_thuc_hien or "").strip()
    if not nguoi:
        raise ValueError("Phải cung cấp --nguoi-thuc-hien khác rỗng khi áp dụng tham số đo được.")
    ngay_str = str(ngay or "").strip() or datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    nguon_str = str(nguon or "ĐO ĐƯỢC").strip() or "ĐO ĐƯỢC"

    p = duong_dan_tham_so_do_duoc(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    hien_tai = doc_tham_so_do_duoc(p)
    tham_so = dict(hien_tai.get("tham_so") or {})
    lich_su = list(hien_tai.get("lich_su") or [])

    da_ghi: dict[str, Any] = {}
    for k, v in cap_nhat.items():
        if isinstance(v, dict):
            gia_tri = float(v["gia_tri"])
            chi_tiet = dict(v.get("chi_tiet") or {})
        else:
            gia_tri = float(v)
            chi_tiet = {}
        if not math.isfinite(gia_tri):
            raise ValueError(f"Giá trị tham số '{k}' không hữu hạn: {gia_tri}")
        muc = {
            "gia_tri": gia_tri,
            "nguon": nguon_str,
            "nguoi_thuc_hien": nguoi,
            "ngay": ngay_str,
            "chi_tiet": chi_tiet,
        }
        tham_so[k] = muc
        da_ghi[k] = gia_tri

    lich_su.append({
        "ngay": ngay_str,
        "nguon": nguon_str,
        "nguoi_thuc_hien": nguoi,
        "cac_tham_so": da_ghi,
    })
    ket_qua = {
        "nguon": nguon_str,
        "ngay_cap_nhat": ngay_str,
        "tham_so": tham_so,
        "lich_su": lich_su,
    }
    p.write_text(json.dumps(ket_qua, ensure_ascii=False, indent=2), encoding="utf-8")
    return ket_qua


def tai_cau_hinh_troi_laser(config_path: str | Path | None = None) -> dict[str, Any]:
    """Đọc các ngưỡng tối thiểu cho phân tích độ trôi từ config.yaml."""
    cfg_p = Path(config_path) if config_path else CONFIG_MAC_DINH
    raw: dict[str, Any] = {}
    if cfg_p.exists():
        raw = yaml.safe_load(cfg_p.read_text(encoding="utf-8")) or {}
    ps = raw.get("phan_tich_sai_so") or {}
    return {
        "so_khung_toi_thieu_troi": int(ps.get("so_khung_toi_thieu_troi", 60)),
        "thoi_luong_toi_thieu_phut": float(ps.get("thoi_luong_toi_thieu_phut", 20.0)),
    }


def _hoi_quy_tuyen_tinh_ols(x: np.ndarray, y: np.ndarray) -> dict[str, Any]:
    """Khớp hồi quy tuyến tính OLS y = a + b*x và tính KTC 95% cho độ dốc b."""
    n = int(len(x))
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if n < 3 or float(np.ptp(x)) <= 1e-12:
        std_val = float(np.std(y, ddof=1)) if n > 1 else 0.0
        return {
            "slope": 0.0,
            "intercept": float(np.mean(y)) if n > 0 else 0.0,
            "se_slope": float("inf"),
            "ci_lo": 0.0,
            "ci_hi": 0.0,
            "std_res": std_val,
            "residuals": y - (float(np.mean(y)) if n > 0 else 0.0),
        }

    x_bar = float(np.mean(x))
    y_bar = float(np.mean(y))
    dx = x - x_bar
    dy = y - y_bar
    sxx = float(np.dot(dx, dx))
    slope = float(np.dot(dx, dy) / sxx)
    intercept = y_bar - slope * x_bar
    res = y - (intercept + slope * x)
    s2 = float(np.dot(res, res)) / float(max(n - 2, 1))
    std_res = math.sqrt(max(s2, 0.0))
    se_slope = math.sqrt(max(s2 / sxx, 0.0))
    t_crit = float(stats.t.ppf(0.975, df=max(n - 2, 1)))
    return {
        "slope": slope,
        "intercept": intercept,
        "se_slope": se_slope,
        "ci_lo": slope - t_crit * se_slope,
        "ci_hi": slope + t_crit * se_slope,
        "std_res": std_res,
        "residuals": res,
    }


def _tu_tuong_quan_bac_1(res: np.ndarray) -> float:
    """Ước lượng tự tương quan bậc 1 (không âm) trên phần dư sau khử xu hướng."""
    if len(res) < 6:
        return 0.0
    r0 = res[:-1] - np.mean(res[:-1])
    r1 = res[1:] - np.mean(res[1:])
    denom = float(math.sqrt(max(float(np.dot(r0, r0) * np.dot(r1, r1)), 1e-24)))
    if denom <= 1e-18:
        return 0.0
    return float(max(0.0, min(0.95, np.dot(r0, r1) / denom)))


def _block_bootstrap_kappa_ci(
    y_tc: np.ndarray,
    y_mau: np.ndarray,
    delta_y: np.ndarray,
    res_detrend: np.ndarray,
    *,
    n_bootstrap: int = 400,
    seed: int = 202604,
) -> tuple[tuple[float, float], int]:
    """Khoảng tin cậy 95% của κ bằng circular block bootstrap theo cặp thời gian.

    Dùng circular block bootstrap để mọi điểm thời gian (kể cả hai đầu mút có biên độ
    trôi lớn nhất) đều có xác suất được lấy mẫu ngang nhau 1/n, tránh làm hẹp giả σ_đơn.
    Độ dài block chọn từ tự tương quan bậc 1 trên phần dư đã loại xu hướng tuyến tính.
    """
    n = len(delta_y)
    if n < 6:
        return (-1.0, 1.0), 1

    rho1 = max(_tu_tuong_quan_bac_1(res_detrend[0]), _tu_tuong_quan_bac_1(res_detrend[1]))
    block_len = int(round(1.0 + 3.0 * rho1 / (1.0 - min(0.92, rho1))))
    block_len = max(2, min(block_len, max(2, n // 8)))

    rng = np.random.default_rng(seed)
    n_blocks = int(math.ceil(n / block_len))
    starts = rng.integers(0, n, size=(int(n_bootstrap), n_blocks))
    offsets = np.arange(block_len, dtype=int)[None, None, :]
    idx = ((starts[:, :, None] + offsets).reshape(int(n_bootstrap), -1)[:, :n]) % n

    yt = y_tc[idx]
    ym = y_mau[idx]
    dy = delta_y[idx]
    std_dy = np.std(dy, axis=1, ddof=1)
    sigma_don = 0.5 * (np.std(yt, axis=1, ddof=1) + np.std(ym, axis=1, ddof=1))
    hop_le = sigma_don > 1e-12
    kappa_boot = np.where(hop_le, 1.0 - std_dy / np.where(hop_le, sigma_don, 1.0), 0.0)
    lo, hi = np.percentile(kappa_boot, [2.5, 97.5])
    return (float(lo), float(hi)), block_len


def _chan_doan_warm_up(
    t_phut: np.ndarray,
    y_tc: np.ndarray,
    y_mau: np.ndarray,
    delta_y: np.ndarray,
) -> dict[str, Any]:
    """Phát hiện trôi mạnh bất thường ở giai đoạn đầu (chưa ổn định nhiệt warm-up laser)."""
    thoi_luong = float(t_phut[-1] - t_phut[0]) if len(t_phut) >= 2 else 0.0
    if len(t_phut) < 12 or thoi_luong < 2.0:
        return {
            "canh_bao_warm_up": False,
            "thoi_gian_cat_phut": 0.0,
            "ty_le_toc_do_dau_sau": 1.0,
            "kenh_kich_hoat": None,
            "thong_diep": "",
        }

    t_tu_dau = t_phut - t_phut[0]
    t_cut = min(5.0, 0.25 * thoi_luong)
    mask_dau = t_tu_dau <= t_cut + 1e-9
    mask_sau = t_tu_dau > t_cut + 1e-9
    if int(np.sum(mask_dau)) < 4 or int(np.sum(mask_sau)) < 6:
        idx_cut = max(4, min(len(t_tu_dau) - 6, len(t_tu_dau) // 4))
        mask_dau = np.zeros(len(t_tu_dau), dtype=bool)
        mask_dau[:idx_cut] = True
        mask_sau = ~mask_dau
        t_cut = float(t_tu_dau[idx_cut - 1])

    ty_le_max = 1.0
    kenh_max: str | None = None
    chi_tiet: dict[str, Any] = {}
    for ten, mang in (("y_tc", y_tc), ("y_mau", y_mau), ("delta_y", delta_y)):
        ols_dau = _hoi_quy_tuyen_tinh_ols(t_tu_dau[mask_dau], mang[mask_dau])
        ols_sau = _hoi_quy_tuyen_tinh_ols(t_tu_dau[mask_sau], mang[mask_sau])
        toc_dau = abs(ols_dau["slope"])
        toc_sau = abs(ols_sau["slope"])
        se_dau = ols_dau["se_slope"]
        se_sau = ols_sau["se_slope"]
        y_nghia_dau = math.isfinite(se_dau) and (toc_dau > max(0.03, 3.0 * se_dau))
        mau_so = max(toc_sau, max(0.02, 1.5 * se_sau) if math.isfinite(se_sau) else 0.02)
        ty_le = toc_dau / mau_so if y_nghia_dau else 1.0
        chi_tiet[ten] = {
            "toc_do_dau_px_phut": float(toc_dau),
            "toc_do_sau_px_phut": float(toc_sau),
            "ty_le": float(ty_le),
            "y_nghia_thong_ke": bool(y_nghia_dau),
        }
        if y_nghia_dau and ty_le > ty_le_max:
            ty_le_max = float(ty_le)
            kenh_max = ten

    co_warm_up = bool(kenh_max is not None and ty_le_max >= 2.5)
    thong_diep = ""
    if co_warm_up:
        thong_diep = (
            f"Cảnh báo warm-up: tốc độ trôi trong {t_cut:.1f} phút đầu trên kênh {kenh_max} "
            f"cao gấp {ty_le_max:.1f}× giai đoạn sau. Hãy bật nguồn laser ổn định trước khi bắt đầu đo."
        )
    return {
        "canh_bao_warm_up": co_warm_up,
        "thoi_gian_cat_phut": float(t_cut),
        "ty_le_toc_do_dau_sau": float(ty_le_max),
        "kenh_kich_hoat": kenh_max,
        "chi_tiet_tung_kenh": chi_tiet,
        "thong_diep": thong_diep,
    }


def phan_tich_chuoi_troi_laser(
    thoi_gian_phut: Sequence[float] | np.ndarray,
    y_tc_px: Sequence[float] | np.ndarray,
    y_mau_px: Sequence[float] | np.ndarray,
    *,
    roi_hop_le: Sequence[bool] | None = None,
    so_khung_toi_thieu: int | None = None,
    thoi_luong_toi_thieu_phut: float | None = None,
    nguon_du_lieu: str = "THUC_TE",
    nguoi_thuc_hien: str = "",
    ngay: str | None = None,
    n_bootstrap: int = 400,
    seed: int = 202604,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    """Phân tích chuỗi thời gian hai vạch khi hai ngăn chứa cùng nước cất (ΔS = 0)."""
    cfg_troi = tai_cau_hinh_troi_laser(config_path)
    min_khung = int(so_khung_toi_thieu if so_khung_toi_thieu is not None else cfg_troi["so_khung_toi_thieu_troi"])
    min_phut = float(
        thoi_luong_toi_thieu_phut if thoi_luong_toi_thieu_phut is not None else cfg_troi["thoi_luong_toi_thieu_phut"]
    )

    t_arr = np.asarray(thoi_gian_phut, dtype=float)
    yt_arr = np.asarray(y_tc_px, dtype=float)
    ym_arr = np.asarray(y_mau_px, dtype=float)
    if not (t_arr.shape == yt_arr.shape == ym_arr.shape) or t_arr.ndim != 1:
        raise ValueError("Các chuỗi thời gian, y_tc_px và y_mau_px phải là mảng 1 chiều cùng độ dài.")

    mask = np.isfinite(t_arr) & np.isfinite(yt_arr) & np.isfinite(ym_arr)
    if roi_hop_le is not None:
        mask &= np.asarray(roi_hop_le, dtype=bool)
    t_arr = t_arr[mask]
    yt_arr = yt_arr[mask]
    ym_arr = ym_arr[mask]

    if len(t_arr) < 3:
        raise LoiDuLieuTroiKhongDuError(
            f"Chỉ có {len(t_arr)} khung hình hợp lệ (< 3), không thể ước lượng hồi quy độ trôi."
        )

    order = np.argsort(t_arr, kind="stable")
    t_arr = t_arr[order] - float(t_arr[order[0]])
    yt_arr = yt_arr[order]
    ym_arr = ym_arr[order]
    dy_arr = ym_arr - yt_arr

    n = int(len(t_arr))
    thoi_luong_phut = float(t_arr[-1] - t_arr[0])
    t_gio = t_arr / 60.0

    du_khung = n >= min_khung
    du_thoi_luong = thoi_luong_phut >= min_phut - 1e-9
    hop_le = bool(du_khung and du_thoi_luong)
    trang_thai = "HOP_LE" if hop_le else "CHUA_DU_DU_LIEU"

    ols_tc = _hoi_quy_tuyen_tinh_ols(t_gio, yt_arr)
    ols_mau = _hoi_quy_tuyen_tinh_ols(t_gio, ym_arr)
    ols_dy = _hoi_quy_tuyen_tinh_ols(t_gio, dy_arr)

    std_tho_tc = float(np.std(yt_arr, ddof=1))
    std_tho_mau = float(np.std(ym_arr, ddof=1))
    std_tho_dy = float(np.std(dy_arr, ddof=1))
    sigma_don = 0.5 * (std_tho_tc + std_tho_mau)

    if sigma_don > 1e-12:
        kappa = float(1.0 - std_tho_dy / sigma_don)
    else:
        kappa = 0.0
    kappa_chan_khong = float(max(0.0, min(1.0, kappa)))

    if std_tho_tc > 1e-12 and std_tho_mau > 1e-12:
        corr_r = float(np.corrcoef(yt_arr, ym_arr)[0, 1])
    else:
        corr_r = 0.0

    ktc_kappa, block_len = _block_bootstrap_kappa_ci(
        yt_arr,
        ym_arr,
        dy_arr,
        (ols_dy["residuals"], ols_tc["residuals"]),
        n_bootstrap=n_bootstrap,
        seed=seed,
    )
    kappa_lo, kappa_hi = ktc_kappa
    he_so_lot_bao_thu = float(max(0.0, min(1.0, 1.0 - kappa_lo)))

    warm_up = _chan_doan_warm_up(t_arr, yt_arr, ym_arr, dy_arr)

    canh_bao: list[str] = []
    if not du_khung:
        canh_bao.append(f"CHUA_DU_DU_LIEU: mới có {n} khung hình (cần ≥ {min_khung}).")
    if not du_thoi_luong:
        canh_bao.append(
            f"CHUA_DU_DU_LIEU: thời lượng mới đạt {thoi_luong_phut:.1f} phút (cần ≥ {min_phut:.1f} phút)."
        )
    if warm_up["canh_bao_warm_up"]:
        canh_bao.append(warm_up["thong_diep"])
    if kappa < 0.5:
        canh_bao.append(
            f"Mức triệt nhiễu chung κ = {kappa:.3f} (cận dưới 95%: {kappa_lo:.3f}) khá thấp; "
            "kiểm tra xem hai ngăn có rung/lệch độc lập hoặc chênh lệch nhiệt không."
        )

    ngay_str = str(ngay or "").strip() or datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    return {
        "nguon_du_lieu": str(nguon_du_lieu or "THUC_TE"),
        "nguoi_thuc_hien": str(nguoi_thuc_hien or ""),
        "ngay_phan_tich": ngay_str,
        "trang_thai": trang_thai,
        "hop_le": hop_le,
        "du_so_khung": du_khung,
        "du_thoi_luong": du_thoi_luong,
        "so_khung": n,
        "thoi_luong_phut": thoi_luong_phut,
        "so_khung_toi_thieu": min_khung,
        "thoi_luong_toi_thieu_phut": min_phut,
        "toc_do_troi_tc_px_gio": float(ols_tc["slope"]),
        "ktc_95_toc_do_tc_px_gio": [float(ols_tc["ci_lo"]), float(ols_tc["ci_hi"])],
        "toc_do_troi_mau_px_gio": float(ols_mau["slope"]),
        "ktc_95_toc_do_mau_px_gio": [float(ols_mau["ci_lo"]), float(ols_mau["ci_hi"])],
        "toc_do_troi_delta_y_px_gio": float(ols_dy["slope"]),
        "ktc_95_toc_do_delta_y_px_gio": [float(ols_dy["ci_lo"]), float(ols_dy["ci_hi"])],
        "std_tho_tc_px": std_tho_tc,
        "std_tho_mau_px": std_tho_mau,
        "std_tho_delta_y_px": std_tho_dy,
        "sigma_don_px": float(sigma_don),
        "std_sau_detrend_tc_px": float(ols_tc["std_res"]),
        "std_sau_detrend_mau_px": float(ols_mau["std_res"]),
        "std_sau_detrend_delta_y_px": float(ols_dy["std_res"]),
        "he_so_tuong_quan_r": float(corr_r),
        "kappa": float(kappa),
        "kappa_chan_khong": kappa_chan_khong,
        "ktc_95_kappa": [float(kappa_lo), float(kappa_hi)],
        "he_so_lot_bao_thu": he_so_lot_bao_thu,
        "chi_tiet_bootstrap": {
            "n_bootstrap": int(n_bootstrap),
            "do_dai_block": int(block_len),
            "seed": int(seed),
        },
        "canh_bao_warm_up": bool(warm_up["canh_bao_warm_up"]),
        "chi_tiet_warm_up": warm_up,
        "canh_bao": canh_bao,
        "chuoi_thoi_gian": {
            "thoi_gian_phut": [round(float(v), 4) for v in t_arr],
            "y_tc_px": [round(float(v), 4) for v in yt_arr],
            "y_mau_px": [round(float(v), 4) for v in ym_arr],
            "delta_y_px": [round(float(v), 4) for v in dy_arr],
        },
    }


def _trich_xuat_phut_tu_ten_file(ten_file: str) -> datetime | None:
    """Thử đọc dấu thời gian YYYYMMDD_HHMMSS trong tên file nếu thiếu EXIF."""
    m = re.search(r"(\d{4})(\d{2})(\d{2})[_-](\d{2})(\d{2})(\d{2})", ten_file)
    if not m:
        return None
    try:
        return datetime(
            int(m.group(1)),
            int(m.group(2)),
            int(m.group(3)),
            int(m.group(4)),
            int(m.group(5)),
            int(m.group(6)),
        )
    except ValueError:
        return None


def phan_tich_troi_laser_tu_danh_sach_anh(
    danh_sach_anh: Sequence[tuple[str, bytes]],
    *,
    buoc_thoi_gian_giay: float | None = None,
    thoi_gian_phut_thu_cong: Sequence[float] | None = None,
    nguon_du_lieu: str = "THUC_TE",
    nguoi_thuc_hien: str = "",
    ngay: str | None = None,
    luu_json: bool = True,
    output_path: str | Path | None = None,
    config_path: str | Path | None = None,
    so_anh_mo_phong_path: str | Path | None = None,
) -> dict[str, Any]:
    """Đo y_tc, y_mẫu, Δy trên từng khung ảnh chuỗi trôi rồi chạy phân tích thống kê."""
    if not danh_sach_anh:
        raise ValueError("Danh sách ảnh chuỗi trôi rỗng.")

    with open(CONFIG_MAC_DINH if not config_path else config_path, "r", encoding="utf-8") as f:
        cfg_all = yaml.safe_load(f) or {}
    xu_ly = cfg_all.get("xu_ly_anh") or {}

    thoi_diem_dt: list[datetime | None] = []
    y_tc_list: list[float] = []
    y_mau_list: list[float] = []
    ten_files: list[str] = []
    co_anh_mo_phong = False
    x_ref_co_dinh: int | None = None

    for idx, (ten, raw) in enumerate(danh_sach_anh):
        anh = giai_ma_anh_tu_bytes(raw)
        if nguon_du_lieu == "THUC_TE":
            co_mp = bool(doc_nhan_mo_phong(raw))
            ly_do_mp = "Ảnh mang chữ kí/metadata MÔ PHỎNG nhưng được gắn nhãn THUC_TE." if co_mp else ""
            if not co_mp:
                tra = tra_cuu_so_anh_mo_phong(raw, so_path=so_anh_mo_phong_path)
                if tra is not None:
                    co_mp = True
                    ly_do_mp = f"Ảnh khớp SHA-256 trong sổ ảnh mô phỏng ({tra.get('duong_dan', '')})."
            if co_mp:
                raise LoiAnhMoPhongGanNhanThucTeError(f"{ten}: {ly_do_mp}")
        else:
            if bool(doc_nhan_mo_phong(raw)) or tra_cuu_so_anh_mo_phong(raw, so_path=so_anh_mo_phong_path) is not None:
                co_anh_mo_phong = True

        kq = do_delta_y_tu_anh(
            anh,
            x_ref=x_ref_co_dinh,
            phuong_phap=str(xu_ly.get("phuong_phap_tim_tam", "gauss")),
            buoc_nhay_cot=int(xu_ly.get("buoc_nhay_cot", 2)),
            nguong_bao_hoa=int(xu_ly.get("nguong_bao_hoa", 252)),
            ti_le_bao_hoa_toi_da=float(xu_ly.get("ti_le_bao_hoa_toi_da", 0.05)),
            snr_toi_thieu=float(xu_ly.get("snr_toi_thieu", 10.0)),
            tao_anh_ve=False,
        )
        if x_ref_co_dinh is None:
            x_ref_co_dinh = int(kq.x_ref)

        dt_val: datetime | None = None
        exif = thang.doc_exif_may_anh(raw)
        if exif.get("thoi_diem_chup"):
            try:
                dt_val = datetime.strptime(str(exif["thoi_diem_chup"]).strip(), "%Y:%m:%d %H:%M:%S")
            except ValueError:
                dt_val = None
        if dt_val is None:
            dt_val = _trich_xuat_phut_tu_ten_file(ten)

        thoi_diem_dt.append(dt_val)
        y_tc_list.append(float(kq.vach_tham_chieu.y_tam))
        y_mau_list.append(float(kq.vach_mau.y_tam))
        ten_files.append(ten)

    n = len(danh_sach_anh)
    if thoi_gian_phut_thu_cong is not None and len(thoi_gian_phut_thu_cong) == n:
        t_phut = [float(v) for v in thoi_gian_phut_thu_cong]
    elif all(d is not None for d in thoi_diem_dt):
        t0 = thoi_diem_dt[0]
        assert t0 is not None
        t_phut = [(d - t0).total_seconds() / 60.0 for d in thoi_diem_dt if d is not None]
    elif buoc_thoi_gian_giay is not None and float(buoc_thoi_gian_giay) > 0:
        dt_phut = float(buoc_thoi_gian_giay) / 60.0
        t_phut = [i * dt_phut for i in range(n)]
    else:
        t_phut = [0.0 for _ in range(n)]

    nguon_thuc = "MO_PHONG" if (nguon_du_lieu == "MO_PHONG" or co_anh_mo_phong) else str(nguon_du_lieu)
    kq_phan_tich = phan_tich_chuoi_troi_laser(
        t_phut,
        y_tc_list,
        y_mau_list,
        nguon_du_lieu=nguon_thuc,
        nguoi_thuc_hien=nguoi_thuc_hien,
        ngay=ngay,
        config_path=config_path,
    )
    kq_phan_tich["danh_sach_file"] = ten_files
    if luu_json:
        out_p = duong_dan_phan_tich_troi(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(kq_phan_tich, ensure_ascii=False, indent=2), encoding="utf-8")
        kq_phan_tich["duong_dan_json"] = str(out_p)
    return kq_phan_tich


def phan_tich_troi_laser_tu_thu_muc(
    thu_muc: str | Path,
    *,
    buoc_thoi_gian_giay: float | None = None,
    nguon_du_lieu: str = "THUC_TE",
    nguoi_thuc_hien: str = "",
    ngay: str | None = None,
    luu_json: bool = True,
    output_path: str | Path | None = None,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    """Quét thư mục ảnh chuỗi trôi (hoặc timestamps.csv kèm ảnh) và xuất báo cáo JSON."""
    folder = Path(thu_muc)
    if not folder.is_dir():
        raise FileNotFoundError(f"Không tìm thấy thư mục ảnh chuỗi trôi: {folder}")

    duoi_bo_qua = {".csv", ".json", ".txt", ".md", ".yaml", ".yml", ".db"}
    files = sorted(
        [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() not in duoi_bo_qua],
        key=lambda p: p.name,
    )
    if not files:
        raise ValueError(f"Thư mục '{folder}' không có file ảnh nào.")

    ts_map: dict[str, float] = {}
    ts_csv = folder / "timestamps.csv"
    if ts_csv.exists():
        df_ts = pd.read_csv(ts_csv)
        if "ten_file" in df_ts.columns and "thoi_gian_phut" in df_ts.columns:
            for _, row in df_ts.iterrows():
                ts_map[str(row["ten_file"]).strip()] = float(row["thoi_gian_phut"])

    danh_sach: list[tuple[str, bytes]] = []
    t_manual: list[float] = []
    co_day_du_manual = len(ts_map) >= len(files)
    for p in files:
        raw = p.read_bytes()
        danh_sach.append((p.name, raw))
        if p.name in ts_map:
            t_manual.append(ts_map[p.name])
        else:
            co_day_du_manual = False

    return phan_tich_troi_laser_tu_danh_sach_anh(
        danh_sach,
        buoc_thoi_gian_giay=buoc_thoi_gian_giay,
        thoi_gian_phut_thu_cong=t_manual if co_day_du_manual else None,
        nguon_du_lieu=nguon_du_lieu,
        nguoi_thuc_hien=nguoi_thuc_hien,
        ngay=ngay,
        luu_json=luu_json,
        output_path=output_path,
        config_path=config_path,
    )


def ap_dung_troi_laser_vao_tham_so(
    ket_qua: dict[str, Any],
    *,
    nguoi_thuc_hien: str,
    ngay: str | None = None,
    tham_so_path: str | Path | None = None,
) -> dict[str, Any]:
    """Áp dụng tường minh giá trị bảo thủ 1 − κ_lo vào data/tham_so_do_duoc.json."""
    if str(ket_qua.get("trang_thai")) != "HOP_LE" or not ket_qua.get("hop_le"):
        raise LoiDuLieuTroiKhongDuError(
            "Không thể áp dụng hệ số triệt chung vì chuỗi dữ liệu trôi ở trạng thái CHUA_DU_DU_LIEU."
        )
    if str(ket_qua.get("nguon_du_lieu", "")).upper() == "MO_PHONG":
        nguon_label = "MO_PHONG (chỉ tham khảo)"
    else:
        nguon_label = "ĐO ĐƯỢC"

    he_so_lot = float(ket_qua["he_so_lot_bao_thu"])
    return ghi_tham_so_do_duoc(
        {
            "he_so_triet_chung": {
                "gia_tri": he_so_lot,
                "chi_tiet": {
                    "cong_thuc": "1 - kappa_lo (cận dưới 95% block bootstrap)",
                    "kappa": float(ket_qua["kappa"]),
                    "ktc_95_kappa": list(ket_qua["ktc_95_kappa"]),
                    "so_khung": int(ket_qua["so_khung"]),
                    "thoi_luong_phut": float(ket_qua["thoi_luong_phut"]),
                    "toc_do_troi_tc_px_gio": float(ket_qua["toc_do_troi_tc_px_gio"]),
                    "toc_do_troi_mau_px_gio": float(ket_qua["toc_do_troi_mau_px_gio"]),
                },
            }
        },
        nguon=nguon_label,
        nguoi_thuc_hien=nguoi_thuc_hien,
        ngay=ngay,
        path=tham_so_path,
    )
