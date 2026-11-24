"""Phân tích cân bằng nhiệt hai ngăn sau khi đổ mẫu thực nghiệm — X3.

Mục đích vật lí:
Khi đổ mẫu nước cần đo (nhiệt độ ban đầu khác nhiệt độ ngăn tham chiếu),
độ lệch nhiệt độ giữa hai ngăn D(t) = T_mẫu(t) − T_tc(t) suy giảm theo thời gian
theo quy luật làm nguội/ấm mũ bậc nhất:

    D(t) = D_∞ + D_0 · exp(−t / τ)

trong đó:
- τ (giây): hằng số thời gian cân bằng nhiệt của buồng hai ngăn;
- D_∞ (°C): độ lệch nhiệt độ dừng (khác 0 nếu có nguồn nhiệt lệch như diode laser
  hoặc đối lưu không đối xứng);
- t_chờ (giây): thời gian cần chờ để |D(t) − D_∞| ≤ nguong_D_C (mặc định 0,3 °C),
  tức t_chờ = τ · ln(|D_0| / nguong_D_C) khi |D_0| > nguong_D_C.

Do D_∞ có thể khác 0, đề xuất σ_D (khi chưa ổn định và khi đã ổn định) dựa trên
phân vị 90% của |D(t)| quan sát thực tế, phản ánh đầy đủ cả phần lệch dừng D_∞.
"""
from __future__ import annotations

import io
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from scipy import optimize, stats

from core.troi_laser import ghi_tham_so_do_duoc

ROOT = Path(__file__).resolve().parents[1]
CONFIG_MAC_DINH = ROOT / "config.yaml"
PHAN_TICH_CBN_MAC_DINH = ROOT / "data" / "phan_tich_can_bang_nhiet.json"


class LoiCanBangNhietKhongHopLeError(ValueError):
    """Không có lần đổ mẫu nào đủ điểm hoặc hội tụ để áp dụng tham số cân bằng nhiệt."""


def duong_dan_phan_tich_can_bang_nhiet(path: str | Path | None = None) -> Path:
    """Đường dẫn file JSON lưu báo cáo phân tích cân bằng nhiệt thực nghiệm."""
    if path is not None:
        return Path(path)
    env = os.environ.get("SALINITY_PHAN_TICH_CBN_PATH", "").strip()
    return Path(env) if env else PHAN_TICH_CBN_MAC_DINH


def tai_cau_hinh_can_bang_nhiet(config_path: str | Path | None = None) -> dict[str, Any]:
    """Đọc ngưỡng cân bằng nhiệt từ config.yaml."""
    cfg_p = Path(config_path) if config_path else CONFIG_MAC_DINH
    raw: dict[str, Any] = {}
    if cfg_p.exists():
        raw = yaml.safe_load(cfg_p.read_text(encoding="utf-8")) or {}
    cbn = raw.get("can_bang_nhiet") or {}
    return {
        "nguong_D_C": float(cbn.get("nguong_D_C", 0.3)),
        "so_diem_toi_thieu_lan_do": int(cbn.get("so_diem_toi_thieu_lan_do", 5)),
    }


def doc_csv_can_bang_nhiet(nguon: str | Path | io.StringIO | pd.DataFrame) -> pd.DataFrame:
    """Đọc bảng chuỗi thời gian nhiệt độ hai ngăn sau khi đổ mẫu và chuẩn hóa cột."""
    if isinstance(nguon, pd.DataFrame):
        df = nguon.copy()
    elif isinstance(nguon, io.StringIO):
        df = pd.read_csv(nguon)
    else:
        p = Path(nguon)
        if not p.exists():
            raise FileNotFoundError(f"Không tìm thấy file CSV cân bằng nhiệt: {p}")
        df = pd.read_csv(p)

    df.columns = [str(c).strip() for c in df.columns]
    out = pd.DataFrame(index=df.index)

    if "ma_lan_do" in df.columns:
        out["ma_lan_do"] = df["ma_lan_do"].astype(object).fillna("LAN_01").astype(str).str.strip()
        out.loc[out["ma_lan_do"] == "", "ma_lan_do"] = "LAN_01"
    else:
        out["ma_lan_do"] = "LAN_01"

    if "thoi_gian_giay" in df.columns:
        out["thoi_gian_giay"] = pd.to_numeric(df["thoi_gian_giay"], errors="coerce")
    elif "t_giay" in df.columns:
        out["thoi_gian_giay"] = pd.to_numeric(df["t_giay"], errors="coerce")
    elif "thoi_gian_phut" in df.columns:
        out["thoi_gian_giay"] = pd.to_numeric(df["thoi_gian_phut"], errors="coerce") * 60.0
    else:
        raise ValueError("CSV phải có cột 'thoi_gian_giay' (hoặc 'thoi_gian_phut').")

    if "D_C" in df.columns:
        out["D_C"] = pd.to_numeric(df["D_C"], errors="coerce")
    elif "delta_T_C" in df.columns:
        out["D_C"] = pd.to_numeric(df["delta_T_C"], errors="coerce")
    else:
        col_mau = next((c for c in ("T_mau_C", "nhiet_do_C", "T_mau") if c in df.columns), None)
        col_tc = next((c for c in ("T_tham_chieu_C", "nhiet_do_tham_chieu_C", "T_tc_C", "T_tc") if c in df.columns), None)
        if col_mau is None or col_tc is None:
            raise ValueError("CSV phải có cột 'D_C' hoặc cặp ('T_mau_C', 'T_tham_chieu_C').")
        t_mau = pd.to_numeric(df[col_mau], errors="coerce")
        t_tc = pd.to_numeric(df[col_tc], errors="coerce")
        out["D_C"] = t_mau - t_tc

    out = out[np.isfinite(out["thoi_gian_giay"]) & np.isfinite(out["D_C"])].copy()
    if out.empty:
        raise ValueError("Không có dòng số liệu hợp lệ trong dữ liệu cân bằng nhiệt.")
    return out.reset_index(drop=True)


def _mo_hinh_mu(t: np.ndarray, d_inf: float, d_0: float, tau: float) -> np.ndarray:
    """D(t) = D_∞ + D_0 · exp(−t / τ)."""
    return d_inf + d_0 * np.exp(-np.clip(t / max(tau, 1e-6), 0.0, 500.0))


def khop_lan_do_can_bang_nhiet(
    thoi_gian_giay: np.ndarray,
    d_c: np.ndarray,
    *,
    ma_lan_do: str = "LAN_01",
    nguong_D_C: float = 0.3,
    so_diem_toi_thieu: int = 5,
) -> dict[str, Any]:
    """Khớp mô hình hàm mũ cho một lần đổ mẫu và tính bất định bằng ma trận hiệp phương sai."""
    t = np.asarray(thoi_gian_giay, dtype=float)
    d = np.asarray(d_c, dtype=float)
    mask = np.isfinite(t) & np.isfinite(d)
    t = t[mask]
    d = d[mask]

    n = int(len(t))
    if n < so_diem_toi_thieu:
        return {
            "ma_lan_do": ma_lan_do,
            "hop_le": False,
            "so_diem": n,
            "ly_do_loai": f"Số điểm {n} < ngưỡng tối thiểu {so_diem_toi_thieu}.",
        }

    order = np.argsort(t, kind="stable")
    t = t[order] - float(t[order[0]])
    d = d[order]
    t_span = float(t[-1] - t[0])
    if t_span <= 1e-6:
        return {
            "ma_lan_do": ma_lan_do,
            "hop_le": False,
            "so_diem": n,
            "ly_do_loai": "Khoảng thời gian đo bằng 0.",
        }

    k_tail = max(2, n // 5)
    d_inf_init = float(np.mean(d[-k_tail:]))
    d0_init = float(d[0] - d_inf_init)
    if abs(d0_init) <= 1e-6:
        d0_init = float(d[0] - d[-1]) if abs(d[0] - d[-1]) > 1e-6 else 0.1

    tau_init = max(10.0, 0.3 * t_span)
    if abs(d0_init) > 0.1:
        target = d_inf_init + 0.5 * d0_init
        idx_half = int(np.argmin(np.abs(d - target)))
        if t[idx_half] > 1.0:
            tau_init = float(t[idx_half] / math.log(2.0))
    tau_ub = max(36000.0, 20.0 * t_span)
    tau_init = float(np.clip(tau_init, 2.0, 0.8 * tau_ub))

    try:
        popt, pcov = optimize.curve_fit(
            _mo_hinh_mu,
            t,
            d,
            p0=[d_inf_init, d0_init, tau_init],
            bounds=([-50.0, -100.0, 1.0], [50.0, 100.0, tau_ub]),
            maxfev=5000,
        )
    except Exception as exc:
        return {
            "ma_lan_do": ma_lan_do,
            "hop_le": False,
            "so_diem": n,
            "ly_do_loai": f"Hồi quy phi tuyến không hội tụ: {exc}",
        }

    if not np.all(np.isfinite(popt)) or not np.all(np.isfinite(pcov)):
        return {
            "ma_lan_do": ma_lan_do,
            "hop_le": False,
            "so_diem": n,
            "ly_do_loai": "Ma trận hiệp phương sai không hữu hạn (không định danh được tham số).",
        }

    d_inf, d_0, tau = [float(v) for v in popt]
    if tau <= 1.05 or tau >= 0.98 * tau_ub:
        return {
            "ma_lan_do": ma_lan_do,
            "hop_le": False,
            "so_diem": n,
            "ly_do_loai": f"Hằng số thời gian τ={tau:.1f}s chạm biên, đường cong không rõ suy giảm mũ.",
        }

    diag = np.diag(pcov)
    if np.any(diag < 0) or not np.all(np.isfinite(diag)):
        return {
            "ma_lan_do": ma_lan_do,
            "hop_le": False,
            "so_diem": n,
            "ly_do_loai": "Phương sai ước lượng âm hoặc vô hạn.",
        }

    se_d_inf, se_d_0, se_tau = [float(math.sqrt(v)) for v in diag]
    if se_tau / max(tau, 1e-9) > 2.0:
        return {
            "ma_lan_do": ma_lan_do,
            "hop_le": False,
            "so_diem": n,
            "ly_do_loai": f"Bất định τ quá lớn (SE/τ = {se_tau/tau:.2f} > 2.0), tín hiệu nhiệt quá phẳng.",
        }

    d_pred = _mo_hinh_mu(t, d_inf, d_0, tau)
    res = d - d_pred
    rms_res = float(math.sqrt(np.mean(res * res)))
    t_crit = float(stats.t.ppf(0.975, df=max(n - 3, 1)))

    if abs(d_0) > nguong_D_C:
        t_cho = float(tau * math.log(abs(d_0) / nguong_D_C))
        grad_d0 = tau / d_0
        grad_tau = math.log(abs(d_0) / nguong_D_C)
        grad = np.array([0.0, grad_d0, grad_tau], dtype=float)
        var_t_cho = float(grad @ pcov @ grad)
        se_t_cho = math.sqrt(max(var_t_cho, 0.0))
    else:
        t_cho = 0.0
        se_t_cho = 0.0

    return {
        "ma_lan_do": ma_lan_do,
        "hop_le": True,
        "so_diem": n,
        "thoi_luong_giay": t_span,
        "D_inf_C": d_inf,
        "se_D_inf_C": se_d_inf,
        "ktc_95_D_inf_C": [d_inf - t_crit * se_d_inf, d_inf + t_crit * se_d_inf],
        "D_0_C": d_0,
        "se_D_0_C": se_d_0,
        "tau_giay": tau,
        "se_tau_giay": se_tau,
        "ktc_95_tau_giay": [max(0.0, tau - t_crit * se_tau), tau + t_crit * se_tau],
        "t_cho_giay": t_cho,
        "se_t_cho_giay": se_t_cho,
        "ktc_95_t_cho_giay": [max(0.0, t_cho - t_crit * se_t_cho), t_cho + t_crit * se_t_cho],
        "rms_phan_du_C": rms_res,
        "t_giay": t.tolist(),
        "D_C": d.tolist(),
        "D_khop_C": d_pred.tolist(),
    }


def phan_tich_can_bang_nhiet_tu_df(
    df_raw: pd.DataFrame,
    *,
    nguong_D_C: float | None = None,
    so_diem_toi_thieu: int | None = None,
    nguon_du_lieu: str = "THUC_TE",
    nguoi_thuc_hien: str = "",
    ngay: str | None = None,
    luu_json: bool = True,
    output_path: str | Path | None = None,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    """Phân tích cân bằng nhiệt qua nhiều lần đổ mẫu, loại lần không hợp lệ và đề xuất σ_D."""
    cfg_cbn = tai_cau_hinh_can_bang_nhiet(config_path)
    nguong = float(nguong_D_C if nguong_D_C is not None else cfg_cbn["nguong_D_C"])
    min_pts = int(so_diem_toi_thieu if so_diem_toi_thieu is not None else cfg_cbn["so_diem_toi_thieu_lan_do"])

    df = doc_csv_can_bang_nhiet(df_raw)
    hop_le_list: list[dict[str, Any]] = []
    loai_list: list[dict[str, Any]] = []

    d_abs_chua_on_dinh: list[float] = []
    d_abs_da_on_dinh: list[float] = []

    for ma, nhom in df.groupby("ma_lan_do", sort=False):
        kq_lan = khop_lan_do_can_bang_nhiet(
            nhom["thoi_gian_giay"].to_numpy(dtype=float),
            nhom["D_C"].to_numpy(dtype=float),
            ma_lan_do=str(ma),
            nguong_D_C=nguong,
            so_diem_toi_thieu=min_pts,
        )
        if not kq_lan["hop_le"]:
            loai_list.append(kq_lan)
            continue
        hop_le_list.append(kq_lan)

        t_arr = np.asarray(kq_lan["t_giay"], dtype=float)
        d_abs = np.abs(np.asarray(kq_lan["D_C"], dtype=float))
        t_cho = float(kq_lan["t_cho_giay"])
        mask_truoc = t_arr < t_cho
        mask_sau = t_arr >= t_cho
        if np.any(mask_truoc):
            d_abs_chua_on_dinh.extend(d_abs[mask_truoc].tolist())
        if np.any(mask_sau):
            d_abs_da_on_dinh.extend(d_abs[mask_sau].tolist())

    n_tong = len(hop_le_list) + len(loai_list)
    n_ok = len(hop_le_list)
    ngay_str = str(ngay or "").strip() or datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")

    if n_ok == 0:
        kq_out: dict[str, Any] = {
            "nguon_du_lieu": str(nguon_du_lieu or "THUC_TE"),
            "nguoi_thuc_hien": str(nguoi_thuc_hien or ""),
            "ngay_phan_tich": ngay_str,
            "trang_thai": "CHUA_DU_DU_LIEU",
            "hop_le": False,
            "nguong_D_C": nguong,
            "so_diem_toi_thieu": min_pts,
            "so_lan_do_tong": n_tong,
            "so_lan_do_hop_le": 0,
            "so_lan_do_bi_loai": len(loai_list),
            "cac_lan_do_hop_le": [],
            "danh_sach_loai": loai_list,
            "canh_bao": ["CHUA_DU_DU_LIEU: không có lần đổ mẫu nào đạt số điểm tối thiểu hoặc hội tụ."],
        }
    else:
        taus = np.array([x["tau_giay"] for x in hop_le_list], dtype=float)
        t_chos = np.array([x["t_cho_giay"] for x in hop_le_list], dtype=float)
        d_infs = np.array([x["D_inf_C"] for x in hop_le_list], dtype=float)

        if not d_abs_chua_on_dinh:
            for x in hop_le_list:
                d_abs_chua_on_dinh.extend(np.abs(x["D_C"]).tolist())
        if not d_abs_da_on_dinh:
            # Nếu mọi chuỗi dừng trước t_cho, lấy cận bảo thủ từ |D_∞| + ngưỡng_D_C
            d_abs_da_on_dinh = [abs(float(x["D_inf_C"])) + nguong for x in hop_le_list]

        sigma_chua = float(np.percentile(d_abs_chua_on_dinh, 90))
        sigma_on_dinh = float(np.percentile(d_abs_da_on_dinh, 90))
        # Bảo đảm phần ổn định phản ánh rõ |D_∞| trung bình nếu khác 0
        sigma_on_dinh = max(sigma_on_dinh, float(np.mean(np.abs(d_infs))))

        canh_bao: list[str] = []
        if abs(float(np.mean(d_infs))) >= 0.15:
            canh_bao.append(
                f"Độ lệch dừng trung bình |D_∞| = {abs(float(np.mean(d_infs))):.3f} °C khác 0 đáng kể; "
                "đề xuất σ_D đã tính gồm phần lệch dừng này."
            )
        if loai_list:
            canh_bao.append(f"Đã loại minh bạch {len(loai_list)}/{n_tong} lần đo không đạt/không hội tụ.")

        kq_out = {
            "nguon_du_lieu": str(nguon_du_lieu or "THUC_TE"),
            "nguoi_thuc_hien": str(nguoi_thuc_hien or ""),
            "ngay_phan_tich": ngay_str,
            "trang_thai": "HOP_LE",
            "hop_le": True,
            "nguong_D_C": nguong,
            "so_diem_toi_thieu": min_pts,
            "so_lan_do_tong": n_tong,
            "so_lan_do_hop_le": n_ok,
            "so_lan_do_bi_loai": len(loai_list),
            "median_tau_giay": float(np.median(taus)),
            "p90_tau_giay": float(np.percentile(taus, 90)),
            "median_t_cho_giay": float(np.median(t_chos)),
            "p90_t_cho_giay": float(np.percentile(t_chos, 90)),
            "D_inf_trung_binh_C": float(np.mean(d_infs)),
            "D_inf_abs_p90_C": float(np.percentile(np.abs(d_infs), 90)),
            "sigma_D_khi_chua_do_C": sigma_chua,
            "sigma_D_khi_da_on_dinh_C": sigma_on_dinh,
            "cac_lan_do_hop_le": hop_le_list,
            "danh_sach_loai": loai_list,
            "canh_bao": canh_bao,
        }

    if luu_json:
        out_p = duong_dan_phan_tich_can_bang_nhiet(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(kq_out, ensure_ascii=False, indent=2), encoding="utf-8")
        kq_out["duong_dan_json"] = str(out_p)
    return kq_out


def phan_tich_can_bang_nhiet_tu_csv(
    csv_path: str | Path,
    *,
    nguong_D_C: float | None = None,
    so_diem_toi_thieu: int | None = None,
    nguon_du_lieu: str = "THUC_TE",
    nguoi_thuc_hien: str = "",
    ngay: str | None = None,
    luu_json: bool = True,
    output_path: str | Path | None = None,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    """Đọc CSV cân bằng nhiệt và chạy phân tích toàn bộ các lần đổ mẫu."""
    df = doc_csv_can_bang_nhiet(csv_path)
    return phan_tich_can_bang_nhiet_tu_df(
        df,
        nguong_D_C=nguong_D_C,
        so_diem_toi_thieu=so_diem_toi_thieu,
        nguon_du_lieu=nguon_du_lieu,
        nguoi_thuc_hien=nguoi_thuc_hien,
        ngay=ngay,
        luu_json=luu_json,
        output_path=output_path,
        config_path=config_path,
    )


def ap_dung_can_bang_nhiet_vao_tham_so(
    ket_qua: dict[str, Any],
    *,
    nguoi_thuc_hien: str,
    ngay: str | None = None,
    tham_so_path: str | Path | None = None,
) -> dict[str, Any]:
    """Áp dụng tường minh sigma_D_khi_chua_do_C và sigma_D_khi_da_on_dinh_C vào data/tham_so_do_duoc.json."""
    if str(ket_qua.get("trang_thai")) != "HOP_LE" or not ket_qua.get("hop_le"):
        raise LoiCanBangNhietKhongHopLeError(
            "Không thể áp dụng tham số cân bằng nhiệt vì chưa có lần đo hợp lệ."
        )
    if str(ket_qua.get("nguon_du_lieu", "")).upper() == "MO_PHONG":
        nguon_label = "MO_PHONG (chỉ tham khảo)"
    else:
        nguon_label = "ĐO ĐƯỢC"

    chi_tiet_chung = {
        "median_tau_giay": float(ket_qua["median_tau_giay"]),
        "p90_tau_giay": float(ket_qua["p90_tau_giay"]),
        "median_t_cho_giay": float(ket_qua["median_t_cho_giay"]),
        "p90_t_cho_giay": float(ket_qua["p90_t_cho_giay"]),
        "D_inf_trung_binh_C": float(ket_qua["D_inf_trung_binh_C"]),
        "so_lan_do_hop_le": int(ket_qua["so_lan_do_hop_le"]),
        "nguong_D_C": float(ket_qua["nguong_D_C"]),
    }
    return ghi_tham_so_do_duoc(
        {
            "sigma_D_khi_chua_do_C": {
                "gia_tri": float(ket_qua["sigma_D_khi_chua_do_C"]),
                "chi_tiet": {**chi_tiet_chung, "mo_ta": "Phân vị 90% |D| trước khi ổn định"},
            },
            "sigma_D_khi_da_on_dinh_C": {
                "gia_tri": float(ket_qua["sigma_D_khi_da_on_dinh_C"]),
                "chi_tiet": {**chi_tiet_chung, "mo_ta": "Phân vị 90% |D| khi t >= t_cho (gồm D_inf)"},
            },
        },
        nguon=nguon_label,
        nguoi_thuc_hien=nguoi_thuc_hien,
        ngay=ngay,
        path=tham_so_path,
    )
