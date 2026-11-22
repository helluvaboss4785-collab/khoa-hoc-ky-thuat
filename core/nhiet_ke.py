"""Hiệu chuẩn chéo hai nhiệt kế (ngăn mẫu và ngăn tham chiếu) — V1.

Vật lí & Ý nghĩa thực nghiệm:
- Hai nhiệt kế bình thường có thể lệch hệ thống với nhau ±0,3 đến ±1,0 °C (offset cố định hoặc
  lệch tỉ lệ theo nhiệt độ T). Nếu không đo và trừ độ lệch hệ thống này, phép đo vi sai sẽ tính
  nhầm chênh nhiệt hai ngăn D = T_mẫu − T_tc dẫn tới chặn kết luận oan.
- Người dùng nhúng cả hai đầu đo vào CÙNG một cốc nước khuấy đều ở nhiều mức nhiệt độ khác nhau,
  đọc đồng thời cặp (T_mẫu_đọc, T_tc_đọc) rồi dùng công cụ này tính:
      offset(T) = T_tc_đọc − T_mẫu_đọc
  Khi áp hiệu chỉnh: T_tc_hiệu_chỉnh = T_tc_đọc − offset(T), kèm σ_offset truyền vào σ_Dđo.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
CONFIG_MAC_DINH = ROOT / "config.yaml"
FILE_HIEU_CHUAN_NHIET_KE_MAC_DINH = ROOT / "data" / "hieu_chuan_nhiet_ke.json"

COT_T_MAU_DOC = "nhiet_do_mau_doc_C"
COT_T_TC_DOC = "nhiet_do_tc_doc_C"
COT_T_CHUAN = "nhiet_do_chuan_C"
COT_GHI_CHU_NK = "ghi_chu"
COT_NGUON_NK = "nguon_du_lieu"


@dataclass(frozen=True)
class HieuChuanCheoNhietKe:
    """Tham số hiệu chuẩn chéo giữa nhiệt kế ngăn tham chiếu và nhiệt kế ngăn mẫu."""

    offset_C: float
    sigma_offset_C: float
    phu_thuoc_nhiet_do: bool
    he_so_a: float | None = None
    he_so_b: float | None = None
    hiep_phuong_sai_ab: list[list[float]] | None = None
    b_ci95: list[float] | None = None
    p_value_b: float | None = None
    do_lech_chuan_du_C: float = 0.0
    so_cap: int = 0
    so_muc_nhiet: int = 0
    ngay: str = ""
    nguon_du_lieu: str = "CHUA_XAC_DINH"
    nguoi_thuc_hien: str = ""
    sha256_csv: str = ""
    do_phan_giai_mau_C: float = 0.0
    do_phan_giai_tc_C: float = 0.0
    phan_giai_suy_ra: bool = True
    sigma_phan_giai_C: float = 0.0
    canh_bao_do_phan_giai: bool = False
    canh_bao_chi_tiet: list[dict[str, str]] = field(default_factory=list)

    def offset_va_sigma_tai(self, T_C: float) -> tuple[float, float]:
        """Trả `(offset_C, sigma_offset_C)` tại nhiệt độ mẫu `T_C` (°C), luôn giữ sàn `σ_pg`."""
        san_pg = max(float(self.sigma_phan_giai_C or 0.0), 0.0)
        if (
            self.phu_thuoc_nhiet_do
            and self.he_so_a is not None
            and self.he_so_b is not None
            and math.isfinite(T_C)
        ):
            off = float(self.he_so_a + self.he_so_b * float(T_C))
            if self.hiep_phuong_sai_ab is not None:
                cov = np.asarray(self.hiep_phuong_sai_ab, dtype=float)
                x = np.array([1.0, float(T_C)], dtype=float)
                var = float(x @ cov @ x)
                sig = math.sqrt(max(var, 0.0))
            else:
                sig = float(self.sigma_offset_C)
            return off, max(sig, san_pg)
        return float(self.offset_C), max(float(self.sigma_offset_C), san_pg)

    def sang_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def tu_dict(cls, d: dict[str, Any]) -> "HieuChuanCheoNhietKe":
        fields = cls.__dataclass_fields__.keys()
        kw: dict[str, Any] = {k: v for k, v in d.items() if k in fields}
        if kw.get("canh_bao_chi_tiet") is None:
            kw["canh_bao_chi_tiet"] = []
        return cls(**kw)

    def mo_ta_ngan(self) -> str:
        if self.phu_thuoc_nhiet_do and self.he_so_a is not None and self.he_so_b is not None:
            return (
                f"Đã hiệu chuẩn chéo nhiệt kế: offset(T) = {self.he_so_a:+.3f} {self.he_so_b:+.4f}·T °C "
                f"(σ_TB ±{self.sigma_offset_C:.3f} °C, ngày {self.ngay}, người làm: {self.nguoi_thuc_hien})"
            )
        return (
            f"Đã hiệu chuẩn chéo nhiệt kế ({self.offset_C:+.3f} ± {self.sigma_offset_C:.3f} °C, "
            f"ngày {self.ngay}, người làm: {self.nguoi_thuc_hien})"
        )


def uoc_luong_do_phan_giai(values: np.ndarray) -> float:
    """Suy ra độ phân giải hiển thị (°C) từ chuỗi số đọc nhiệt kế (W3).

    Vật lí & tránh bẫy số liệu:
    - Khi nhiệt kế có nhiễu lặp trong cùng mức nhiệt, hiệu giữa các giá trị khác nhau liên tiếp
      nhỏ hơn 1.0 °C phản ánh bước lượng tử hóa thực tế (vd 0.5, 0.1, 0.01 °C).
    - Nếu các số đọc tại từng bể nhiệt đều làm tròn khớp vào một giá trị duy nhất (vd [20, 28, 36]),
      khoảng cách giữa các bể là 8.0 °C chứ không phải độ phân giải 8 °C; do đó ta chỉ lấy
      min(diff) đối với diff < 1.0 °C, còn lại dò theo lưới giảm dần (1.0 -> 0.001) để không bị
      khớp giả bởi bước mịn nhất mà giữ ước lượng thận trọng theo chữ số thập phân quan sát được.
    """
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return 0.0
    uniq = np.unique(np.round(arr, 6))
    if uniq.size >= 2:
        diffs = np.diff(uniq)
        sub = diffs[(diffs > 1e-9) & (diffs < 1.0 - 1e-9)]
        if sub.size > 0:
            return float(round(float(np.min(sub)), 6))
    for cand in (1.0, 0.5, 0.2, 0.1, 0.05, 0.01, 0.001):
        rem = np.abs(uniq / cand - np.round(uniq / cand))
        if np.all(rem < 1e-5):
            return float(cand)
    return 0.001


def _dem_muc_nhiet(T_vals: np.ndarray, nguong_C: float = 0.5) -> int:
    """Đếm số mức nhiệt độ phân biệt (cách nhau >= nguong_C)."""
    sx = np.sort(np.asarray(T_vals, dtype=float))
    if sx.size == 0:
        return 0
    muc = 1
    goc = float(sx[0])
    for v in sx[1:]:
        if float(v) - goc >= nguong_C:
            muc += 1
            goc = float(v)
    return muc


def doc_nguong_nhiet_ke_cheo_yaml(config_path: str | Path = CONFIG_MAC_DINH) -> tuple[int, int]:
    """Đọc `(so_cap_toi_thieu, so_muc_nhiet_toi_thieu)` từ mục `hieu_chuan.nhiet_ke_cheo`."""
    p = Path(config_path)
    if not p.exists():
        return 6, 2
    with open(p, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    nk = ((raw.get("hieu_chuan") or {}).get("nhiet_ke_cheo")) or {}
    return int(nk.get("so_cap_toi_thieu", 6)), int(nk.get("so_muc_nhiet_toi_thieu", 2))


def doc_do_phan_giai_toi_da_yaml(config_path: str | Path = CONFIG_MAC_DINH) -> float:
    """Đọc ngưỡng độ phân giải tối đa `do_phan_giai_toi_da_C` (°C) từ `config.yaml` (mặc định 0.1)."""
    p = Path(config_path)
    if not p.exists():
        return 0.1
    with open(p, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    nk = ((raw.get("hieu_chuan") or {}).get("nhiet_ke_cheo")) or {}
    try:
        val = float(nk.get("do_phan_giai_toi_da_C", 0.1))
        return val if math.isfinite(val) and val > 0 else 0.1
    except Exception:
        return 0.1


def hieu_chuan_cheo_tu_df(
    df_raw: pd.DataFrame,
    nguoi_thuc_hien: str,
    nguon_du_lieu: str | None = None,
    so_cap_toi_thieu: int = 6,
    so_muc_nhiet_toi_thieu: int = 2,
    sha256_csv: str = "",
    ngay: str | None = None,
    do_phan_giai_mau_C: float | None = None,
    do_phan_giai_tc_C: float | None = None,
    do_phan_giai_toi_da_C: float = 0.1,
) -> HieuChuanCheoNhietKe:
    """Tính độ lệch offset hệ thống và kiểm tra phụ thuộc nhiệt độ từ bảng cặp số đọc cùng bể nước."""
    nguoi = str(nguoi_thuc_hien or "").strip()
    if not nguoi:
        raise ValueError("Bắt buộc khai báo tên người thực hiện (--nguoi-thuc-hien).")

    for ten_pg, val_pg in (("do_phan_giai_mau_C", do_phan_giai_mau_C), ("do_phan_giai_tc_C", do_phan_giai_tc_C)):
        if val_pg is not None:
            v = float(val_pg)
            if not math.isfinite(v) or v < 0.0:
                raise ValueError(f"{ten_pg} phải là số hữu hạn >= 0.")

    df = df_raw.copy()
    df.columns = [str(c).strip() for c in df.columns]
    for col in (COT_T_MAU_DOC, COT_T_TC_DOC):
        if col not in df.columns:
            raise ValueError(f"File CSV thiếu cột bắt buộc '{col}'.")
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=[COT_T_MAU_DOC, COT_T_TC_DOC]).reset_index(drop=True)
    so_cap = len(df)
    if so_cap < so_cap_toi_thieu:
        raise ValueError(
            f"Chưa đủ số cặp đo tối thiểu: chỉ có {so_cap} cặp hợp lệ (yêu cầu >= {so_cap_toi_thieu})."
        )

    t_mau = df[COT_T_MAU_DOC].to_numpy(dtype=float)
    t_tc = df[COT_T_TC_DOC].to_numpy(dtype=float)
    so_muc = _dem_muc_nhiet(t_mau, nguong_C=0.5)
    if so_muc < so_muc_nhiet_toi_thieu:
        raise ValueError(
            f"Chưa đủ số mức nhiệt độ phân biệt (>= 0.5 °C): chỉ có {so_muc} mức (yêu cầu >= {so_muc_nhiet_toi_thieu})."
        )

    # Xác định & kiểm chéo nhãn nguồn dữ liệu
    nguon_arg = str(nguon_du_lieu).strip().upper() if nguon_du_lieu is not None else None
    if nguon_arg is not None and nguon_arg not in ("THUC_TE", "MO_PHONG"):
        raise ValueError(f"Nhãn nguồn '{nguon_arg}' không hợp lệ (chỉ nhận THUC_TE hoặc MO_PHONG).")

    if COT_NGUON_NK in df.columns:
        vals_n = df[COT_NGUON_NK].fillna("").astype(str).str.strip().str.upper()
        non_empty = [v for v in vals_n if v]
        if any(v in ("MO_PHONG", "SIMULATED") for v in non_empty):
            nguon_csv = "MO_PHONG"
        elif non_empty and all(v == "THUC_TE" for v in non_empty):
            nguon_csv = "THUC_TE"
        else:
            nguon_csv = None
    else:
        nguon_csv = None

    if nguon_arg == "THUC_TE" and nguon_csv == "MO_PHONG":
        raise ValueError("TỪ CHỐI: CSV chứa nhãn MO_PHONG/SIMULATED nhưng tham số khai báo là THUC_TE.")
    nguon_cuoi = nguon_arg or nguon_csv
    if nguon_cuoi not in ("THUC_TE", "MO_PHONG"):
        raise ValueError("Bắt buộc khai báo --nguon (THUC_TE hoặc MO_PHONG) hoặc điền đủ cột nguon_du_lieu.")

    # Độ phân giải nhiệt kế & sàn sai số lượng tử hóa σ_pg (W3)
    # Giả định lượng tử hóa độc lập giữa `so_muc` mức nhiệt khác nhau:
    # Var(U[-r/2, r/2]) = r²/12 cho mỗi nhiệt kế -> σ_pg = √(r_mẫu² + r_tc²) / √(12 · so_muc).
    r_mau = float(do_phan_giai_mau_C) if do_phan_giai_mau_C is not None else uoc_luong_do_phan_giai(t_mau)
    r_tc = float(do_phan_giai_tc_C) if do_phan_giai_tc_C is not None else uoc_luong_do_phan_giai(t_tc)
    phan_giai_suy_ra = (do_phan_giai_mau_C is None) or (do_phan_giai_tc_C is None)
    sigma_pg = math.sqrt(r_mau**2 + r_tc**2) / math.sqrt(12.0 * max(so_muc, 1))

    canh_bao_pg = (r_mau > do_phan_giai_toi_da_C + 1e-12) or (r_tc > do_phan_giai_toi_da_C + 1e-12)
    canh_bao_chi_tiet: list[dict[str, str]] = []
    if canh_bao_pg:
        canh_bao_chi_tiet.append({
            "ma": "DO_PHAN_GIAI_NHIET_KE_THO",
            "cap": "can_than",
            "thong_diep": (
                f"Nhiệt kế có độ phân giải thô (r_mẫu={r_mau:g} °C, r_tc={r_tc:g} °C > ngưỡng "
                f"{do_phan_giai_toi_da_C:g} °C); σ_offset đã được nâng theo sàn lượng tử hóa σ_pg={sigma_pg:.4f} °C."
            ),
        })

    diff = t_tc - t_mau
    offset_tb = float(np.mean(diff))
    sd_diff = float(np.std(diff, ddof=1)) if so_cap >= 2 else 0.0
    sigma_sem = float(sd_diff / math.sqrt(so_cap)) if so_cap >= 2 else 0.0
    sigma_off = math.hypot(sigma_sem, sigma_pg)

    # Hồi quy tuyến tính offset(T) = a + b * T_mau và kiểm định độ dốc b
    phu_thuoc = False
    he_so_a: float | None = None
    he_so_b: float | None = None
    cov_ab_list: list[list[float]] | None = None
    b_ci95: list[float] | None = None
    p_val_b: float | None = None
    do_lech_du = sd_diff

    if so_cap >= 3 and float(np.var(t_mau)) > 1e-12:
        X = np.column_stack([np.ones_like(t_mau), t_mau])
        beta, *_ = np.linalg.lstsq(X, diff, rcond=None)
        res = diff - X @ beta
        dof = so_cap - 2
        s2 = float(np.sum(res**2) / dof)
        cov_ab = s2 * np.linalg.pinv(X.T @ X)
        a_hat, b_hat = float(beta[0]), float(beta[1])
        se_b = math.sqrt(max(float(cov_ab[1, 1]), 0.0))
        t_crit = float(stats.t.ppf(0.975, df=dof))
        if se_b > 1e-15:
            t_stat = abs(b_hat) / se_b
            p_val = float(2.0 * stats.t.sf(t_stat, df=dof))
            ci_lo, ci_hi = b_hat - t_crit * se_b, b_hat + t_crit * se_b
        else:
            p_val = 0.0 if abs(b_hat) > 1e-4 else 1.0
            ci_lo, ci_hi = b_hat, b_hat

        # Cộng phương sai lượng tử hóa σ_pg² vào phương sai hệ số chặn cov_ab[0, 0]
        # để Var(a + b·T) = Var_OLS(T) + σ_pg² tại mọi mức T_C.
        cov_ab_co_san = cov_ab.copy()
        cov_ab_co_san[0, 0] = float(cov_ab_co_san[0, 0]) + sigma_pg**2

        he_so_a = a_hat
        he_so_b = b_hat
        cov_ab_list = [
            [float(cov_ab_co_san[0, 0]), float(cov_ab_co_san[0, 1])],
            [float(cov_ab_co_san[1, 0]), float(cov_ab_co_san[1, 1])],
        ]
        b_ci95 = [float(ci_lo), float(ci_hi)]
        p_val_b = float(p_val)
        # Ý nghĩa thống kê (p < 0.05 và 0 ngoài CI 95%) + độ dốc vật lí đáng kể
        if p_val < 0.05 and (ci_lo > 0.0 or ci_hi < 0.0) and abs(b_hat) > 1e-4:
            phu_thuoc = True
            do_lech_du = float(math.sqrt(s2))

    return HieuChuanCheoNhietKe(
        offset_C=offset_tb,
        sigma_offset_C=sigma_off,
        phu_thuoc_nhiet_do=phu_thuoc,
        he_so_a=he_so_a,
        he_so_b=he_so_b,
        hiep_phuong_sai_ab=cov_ab_list,
        b_ci95=b_ci95,
        p_value_b=p_val_b,
        do_lech_chuan_du_C=float(do_lech_du),
        so_cap=so_cap,
        so_muc_nhiet=so_muc,
        ngay=ngay or datetime.now().strftime("%Y-%m-%d"),
        nguon_du_lieu=nguon_cuoi,
        nguoi_thuc_hien=nguoi,
        sha256_csv=sha256_csv,
        do_phan_giai_mau_C=r_mau,
        do_phan_giai_tc_C=r_tc,
        phan_giai_suy_ra=phan_giai_suy_ra,
        sigma_phan_giai_C=float(sigma_pg),
        canh_bao_do_phan_giai=canh_bao_pg,
        canh_bao_chi_tiet=canh_bao_chi_tiet,
    )


def luu_hieu_chuan_cheo_nhiet_ke(
    kq: HieuChuanCheoNhietKe,
    duong_dan: str | Path = FILE_HIEU_CHUAN_NHIET_KE_MAC_DINH,
) -> Path:
    """Lưu kết quả hiệu chuẩn chéo nhiệt kế ra JSON."""
    p = Path(duong_dan)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(kq.sang_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def tai_hieu_chuan_cheo_nhiet_ke(
    duong_dan: str | Path | None = FILE_HIEU_CHUAN_NHIET_KE_MAC_DINH,
) -> HieuChuanCheoNhietKe | None:
    """Đọc file hiệu chuẩn chéo nhiệt kế nếu tồn tại và hợp lệ; ngược lại trả None."""
    if duong_dan is None:
        return None
    p = Path(duong_dan)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        if data.get("offset_C") is None or not str(data.get("nguoi_thuc_hien") or "").strip():
            return None
        kq = HieuChuanCheoNhietKe.tu_dict(data)
        if not math.isfinite(kq.offset_C) or not math.isfinite(kq.sigma_offset_C):
            return None
        return kq
    except Exception:
        return None


def tinh_sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
