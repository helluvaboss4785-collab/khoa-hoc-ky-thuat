"""Hiệu chuẩn, bù nhiệt và ước lượng bất định (Cột mốc 4).

Ý tưởng vật lí:
- Thiết bị đo ra Δy (pixel). Độ mặn S KHÔNG được tính thẳng từ công thức Snell vì
  các hằng số (n0, dn/dS, dn/dT, D, kích thước pixel, góc A thật) đều chỉ là xấp xỉ.
  Thay vào đó ta ĐO Δy với các dung dịch NaCl đã biết độ mặn (pha bằng cân và bình
  định mức) ở vài nhiệt độ, rồi dựng ĐƯỜNG CHUẨN thực nghiệm:

      Δy = f(S, T)   (đa thức bậc thấp theo S và ΔT = T − T_ref)

  Bậc 1:  Δy = c0 + c_S·S + c_T·ΔT
  Bậc 2:  thêm c_SS·S² + c_ST·S·ΔT + c_TT·ΔT²
  (S·ΔT mô tả việc độ nhạy theo độ mặn thay đổi theo nhiệt độ.)

- Khi đo mẫu chưa biết: giải ngược S = g(Δy, T) bằng cách tìm nghiệm f(S, T) = Δy.
- Bất định của S (truyền sai số bậc 1):

      u_S² = [σ_Δy² + s_res² + u_fit² + (∂f/∂T·σ_T)²] / (∂f/∂S)²

  trong đó s_res là độ tản mát của điểm chuẩn quanh đường chuẩn (độ lặp lại),
  u_fit là bất định do hệ số đường chuẩn (từ ma trận hiệp phương sai).
  Bất định mở rộng U = k·u_S (k = 2 ≈ 95%).

Giới hạn quan trọng (phải nói rõ khi phỏng vấn):
- Đường chuẩn dựng bằng NaCl. Nước tự nhiên chứa nhiều ion khác nên kết quả chỉ là
  "độ mặn tương đương NaCl".
- Ngoài dải S, T đã hiệu chuẩn thì kết quả là NGOẠI SUY, không đáng tin.
- Chỉ dùng numpy/scipy/pandas, không dùng thư viện học máy để học sinh tự giải thích được.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import IO, Any

import numpy as np
import pandas as pd
import yaml

CONFIG_MAC_DINH = Path(__file__).resolve().parents[1] / "config.yaml"

# ---------------------------------------------------------------------------
# Tên cột CSV
# ---------------------------------------------------------------------------
COT_DO_MAN = "do_man_chuan_ppt"        # độ mặn chuẩn của dung dịch (‰)
COT_NHIET_DO = "nhiet_do_C"            # nhiệt độ mẫu khi đo (°C)
COT_DELTA_Y = "delta_y_px"             # Δy đo được (pixel)
COT_DO_DUC = "do_duc_tuong_doi"        # chỉ số độ đục tương đối (0–1)
COT_GHI_CHU = "ghi_chu"
COT_ID_THIET_BI = "id_thiet_bi"
COT_ID_DIEN_THOAI = "id_dien_thoai"
COT_NGUON = "nguon_du_lieu"            # (tùy chọn) "THUC_TE" hoặc "MO_PHONG"

COT_BAT_BUOC = [
    COT_DO_MAN, COT_NHIET_DO, COT_DELTA_Y, COT_DO_DUC,
    COT_GHI_CHU, COT_ID_THIET_BI, COT_ID_DIEN_THOAI,
]

# Một số tên cột khác mà học sinh có thể dùng khi tự nhập bảng tính
BI_DANH_COT = {
    "do_man": COT_DO_MAN, "S_ppt": COT_DO_MAN, "do_man_ppt": COT_DO_MAN,
    "nhiet_do": COT_NHIET_DO, "T_C": COT_NHIET_DO,
    "delta_y": COT_DELTA_Y, "dy_px": COT_DELTA_Y,
    "do_duc": COT_DO_DUC,
    "id_dt": COT_ID_DIEN_THOAI, "id_phone": COT_ID_DIEN_THOAI,
}

NHAN_MO_PHONG = "MO_PHONG"
NHAN_THUC_TE = "THUC_TE"
NHAN_CHUA_HIEU_CHUAN = "CHƯA HIỆU CHUẨN – DỮ LIỆU MÔ PHỎNG"
HAN_CHE_NACL = (
    "Đường chuẩn dựng bằng dung dịch NaCl. Nước tự nhiên còn nhiều ion khác "
    "(Mg²⁺, Ca²⁺, K⁺, SO₄²⁻, HCO₃⁻…) và chất hữu cơ hòa tan, nên chiết suất có thể "
    "khác dung dịch NaCl cùng độ mặn. Kết quả chỉ là ĐỘ MẶN TƯƠNG ĐƯƠNG NaCl (ước lượng)."
)


# ---------------------------------------------------------------------------
# Cấu hình
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CauHinhHieuChuan:
    """Tham số dựng đường chuẩn, đọc từ mục `hieu_chuan` của config.yaml."""

    ti_le_test: float = 0.25
    so_fold: int = 5
    nguong_cai_thien_bac2: float = 0.10
    he_so_phu_k: float = 2.0
    sai_so_nhiet_ke_C: float = 0.5
    nguong_lech_T_khong_bu_C: float = 1.0
    seed: int = 0

    @classmethod
    def tu_yaml(cls, duong_dan: str | Path = CONFIG_MAC_DINH) -> "CauHinhHieuChuan":
        """Đọc cấu hình; thiếu mục nào thì dùng giá trị mặc định ở trên."""
        with open(duong_dan, encoding="utf-8") as f:
            c = (yaml.safe_load(f) or {}).get("hieu_chuan", {}) or {}
        mac_dinh = cls()
        return cls(
            ti_le_test=float(c.get("ti_le_tap_test", mac_dinh.ti_le_test)),
            so_fold=int(c.get("so_fold_kiem_dinh_cheo", mac_dinh.so_fold)),
            nguong_cai_thien_bac2=float(c.get("nguong_cai_thien_bac2", mac_dinh.nguong_cai_thien_bac2)),
            he_so_phu_k=float(c.get("he_so_phu_k", mac_dinh.he_so_phu_k)),
            sai_so_nhiet_ke_C=float(c.get("sai_so_nhiet_ke_C", mac_dinh.sai_so_nhiet_ke_C)),
            nguong_lech_T_khong_bu_C=float(c.get("nguong_lech_T_khong_bu_C", mac_dinh.nguong_lech_T_khong_bu_C)),
            seed=int(c.get("seed", mac_dinh.seed)),
        )


# ---------------------------------------------------------------------------
# Đọc CSV
# ---------------------------------------------------------------------------
def doc_csv_hieu_chuan(nguon: str | Path | IO[Any]) -> pd.DataFrame:
    """Đọc file CSV dữ liệu hiệu chuẩn và kiểm tra hợp lệ.

    Cột bắt buộc: do_man_chuan_ppt, nhiet_do_C, delta_y_px, do_duc_tuong_doi,
    ghi_chu, id_thiet_bi, id_dien_thoai. Cột tùy chọn: nguon_du_lieu.

    - Dòng thiếu S, T hoặc Δy bị loại (số dòng bị loại lưu ở df.attrs["so_dong_bi_loai"]).
    - Nếu không có cột nguon_du_lieu thì coi là dữ liệu THUC_TE (do người dùng cung cấp).

    Raises:
        ValueError: thiếu cột bắt buộc hoặc không còn dòng hợp lệ.
    """
    df = pd.read_csv(nguon, encoding="utf-8-sig")
    df.columns = [str(c).strip() for c in df.columns]
    df = df.rename(columns={k: v for k, v in BI_DANH_COT.items() if k in df.columns})

    thieu = [c for c in COT_BAT_BUOC if c not in df.columns]
    if thieu:
        raise ValueError(
            f"File CSV thiếu cột bắt buộc: {', '.join(thieu)}. "
            f"Cần đủ các cột: {', '.join(COT_BAT_BUOC)}."
        )

    for c in (COT_DO_MAN, COT_NHIET_DO, COT_DELTA_Y, COT_DO_DUC):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in (COT_GHI_CHU, COT_ID_THIET_BI, COT_ID_DIEN_THOAI):
        df[c] = df[c].fillna("").astype(str)
    if COT_NGUON not in df.columns:
        df[COT_NGUON] = NHAN_THUC_TE
    df[COT_NGUON] = df[COT_NGUON].fillna(NHAN_THUC_TE).astype(str).str.upper()

    n_truoc = len(df)
    df = df.dropna(subset=[COT_DO_MAN, COT_NHIET_DO, COT_DELTA_Y]).reset_index(drop=True)
    df.attrs["so_dong_bi_loai"] = n_truoc - len(df)

    if len(df) == 0:
        raise ValueError("Không còn dòng hợp lệ nào (thiếu S, T hoặc Δy).")
    if (df[COT_DO_MAN] < 0).any():
        raise ValueError("Có độ mặn chuẩn âm – kiểm tra lại dữ liệu.")
    return df


def la_du_lieu_mo_phong(df: pd.DataFrame) -> bool:
    """True nếu BẤT KÌ dòng nào được đánh dấu là mô phỏng (thận trọng: một dòng mô phỏng
    cũng làm cả đường chuẩn bị coi là chưa hiệu chuẩn thật)."""
    nguon = df.get(COT_NGUON, pd.Series([], dtype=str)).astype(str).str.upper()
    return bool(nguon.isin([NHAN_MO_PHONG, "SIMULATED"]).any())


# ---------------------------------------------------------------------------
# Đa thức và khớp bình phương tối thiểu
# ---------------------------------------------------------------------------
def chon_so_hang(bac: int, co_T: bool, co_TT: bool) -> list[str]:
    """Danh sách số hạng của đa thức.

    "1": hằng số; "S": S; "T": ΔT; "SS": S²; "ST": S·ΔT; "TT": ΔT².
    - Không có nhiệt độ thay đổi trong dữ liệu (co_T=False) -> bỏ mọi số hạng chứa T.
    - Chỉ có 2 mức nhiệt độ -> không xác định được ΔT² (co_TT=False).
    """
    hang = ["1", "S"]
    if co_T:
        hang.append("T")
    if bac >= 2:
        hang.append("SS")
        if co_T:
            hang.append("ST")
            if co_TT:
                hang.append("TT")
    return hang


def ma_tran_dac_trung(S: Any, T: Any, hang: list[str], T_ref: float) -> np.ndarray:
    """Ma trận thiết kế X (mỗi dòng một phép đo, mỗi cột một số hạng)."""
    S_arr, T_arr = np.broadcast_arrays(np.atleast_1d(np.asarray(S, float)),
                                       np.atleast_1d(np.asarray(T, float)))
    dT = T_arr - T_ref
    gia_tri = {"1": np.ones_like(S_arr), "S": S_arr, "T": dT,
               "SS": S_arr**2, "ST": S_arr * dT, "TT": dT**2}
    return np.column_stack([gia_tri[h] for h in hang])


@dataclass
class KetQuaKhop:
    """Kết quả khớp bình phương tối thiểu."""

    he_so: np.ndarray
    hiep_phuong_sai: np.ndarray
    s_res: float          # độ lệch chuẩn phần dư (px), đã chia cho bậc tự do n − p
    bac_tu_do: int
    phan_du: np.ndarray


def khop_binh_phuong_toi_thieu(
    S: np.ndarray, T: np.ndarray, y: np.ndarray, hang: list[str], T_ref: float
) -> KetQuaKhop:
    """Khớp y = X·c bằng bình phương tối thiểu thường.

    Hiệp phương sai hệ số: Cov(c) = s_res²·(XᵀX)⁻¹, với s_res² = Σ(phần dư²)/(n − p).
    Giả định: sai số Δy độc lập, cùng phương sai; S, T chính xác hơn Δy nhiều.

    Raises:
        ValueError: nếu số điểm không lớn hơn số hệ số.
    """
    X = ma_tran_dac_trung(S, T, hang, T_ref)
    n, p = X.shape
    if n <= p:
        raise ValueError(f"Cần nhiều hơn {p} điểm để khớp {p} hệ số (đang có {n}).")
    he_so, *_ = np.linalg.lstsq(X, y, rcond=None)
    phan_du = y - X @ he_so
    bac_tu_do = n - p
    s2 = float(phan_du @ phan_du) / bac_tu_do
    cov = s2 * np.linalg.pinv(X.T @ X)
    return KetQuaKhop(he_so, cov, math.sqrt(s2), bac_tu_do, phan_du)


def rmse_kiem_dinh_cheo(
    S: np.ndarray, T: np.ndarray, y: np.ndarray, hang: list[str], T_ref: float,
    so_fold: int = 5, seed: int = 0,
) -> float:
    """RMSE kiểm định chéo k-phần (k-fold).

    Chia dữ liệu thành k phần; lần lượt bỏ ra 1 phần, khớp trên phần còn lại rồi dự đoán
    phần bị bỏ ra. Mô hình quá khớp (học cả nhiễu) sẽ dự đoán điểm mới kém -> RMSE lớn.
    """
    n = len(y)
    k = max(2, min(so_fold, n))
    rng = np.random.default_rng(seed)
    chi_so = rng.permutation(n)
    sai_so: list[float] = []
    for phan in np.array_split(chi_so, k):
        train = np.setdiff1d(chi_so, phan)
        if len(train) <= len(hang):
            return float("inf")
        kq = khop_binh_phuong_toi_thieu(S[train], T[train], y[train], hang, T_ref)
        du_doan = ma_tran_dac_trung(S[phan], T[phan], hang, T_ref) @ kq.he_so
        sai_so.extend((y[phan] - du_doan).tolist())
    return float(np.sqrt(np.mean(np.square(sai_so))))


# ---------------------------------------------------------------------------
# Mô hình đường chuẩn
# ---------------------------------------------------------------------------
@dataclass
class MoHinhHieuChuan:
    """Đường chuẩn Δy = f(S, T) đã khớp, kèm thông tin để đánh giá độ tin cậy."""

    bac: int
    hang: list[str]
    he_so: list[float]
    hiep_phuong_sai: list[list[float]]
    s_res_px: float
    bac_tu_do: int
    T_ref: float
    co_bu_nhiet: bool
    S_min: float
    S_max: float
    T_min: float
    T_max: float
    so_diem: int
    R2: float
    RMSE_px: float
    la_mo_phong: bool
    id_thiet_bi: list[str] = field(default_factory=list)
    id_dien_thoai: list[str] = field(default_factory=list)
    ngay_tao: str = ""

    # --- tính toán ---------------------------------------------------------
    @property
    def nhan(self) -> str:
        """Nhãn trạng thái hiển thị cho người dùng."""
        return NHAN_CHUA_HIEU_CHUAN if self.la_mo_phong else "ĐÃ HIỆU CHUẨN (dữ liệu đo thật)"

    def du_doan_delta_y(self, S: Any, T: Any) -> np.ndarray:
        """Δy dự đoán (px) tại (S, T)."""
        return ma_tran_dac_trung(S, T, self.hang, self.T_ref) @ np.asarray(self.he_so)

    def _dao_ham(self, S: float, T: float, theo: str) -> float:
        dT = T - self.T_ref
        if theo == "S":
            d = {"1": 0.0, "S": 1.0, "T": 0.0, "SS": 2 * S, "ST": dT, "TT": 0.0}
        else:
            d = {"1": 0.0, "S": 0.0, "T": 1.0, "SS": 0.0, "ST": S, "TT": 2 * dT}
        return float(sum(c * d[h] for c, h in zip(self.he_so, self.hang)))

    def dao_ham_theo_S(self, S: float, T: float) -> float:
        """∂f/∂S (px/‰): độ nhạy thực nghiệm của thiết bị."""
        return self._dao_ham(S, T, "S")

    def dao_ham_theo_T(self, S: float, T: float) -> float:
        """∂f/∂T (px/°C): ảnh hưởng nhiệt độ cần bù."""
        return self._dao_ham(S, T, "T")

    def phuong_sai_du_doan(self, S: float, T: float) -> float:
        """u_fit² = xᵀ·Cov·x : phương sai của Δy dự đoán do bất định hệ số."""
        x = ma_tran_dac_trung(S, T, self.hang, self.T_ref)[0]
        return float(x @ np.asarray(self.hiep_phuong_sai) @ x)

    # --- lưu / đọc ---------------------------------------------------------
    def sang_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["NGUON"] = NHAN_MO_PHONG if self.la_mo_phong else NHAN_THUC_TE
        d["nhan"] = self.nhan
        return d

    @classmethod
    def tu_dict(cls, d: dict[str, Any]) -> "MoHinhHieuChuan":
        ten_truong = cls.__dataclass_fields__.keys()
        return cls(**{k: v for k, v in d.items() if k in ten_truong})

    def luu_json(self, duong_dan: str | Path) -> None:
        """Lưu hệ số đường chuẩn ra file JSON (đọc được bằng mắt)."""
        p = Path(duong_dan)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.sang_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def doc_json(cls, duong_dan: str | Path) -> "MoHinhHieuChuan":
        return cls.tu_dict(json.loads(Path(duong_dan).read_text(encoding="utf-8")))


def _so_muc(gia_tri: np.ndarray, buoc: float) -> int:
    """Đếm số mức khác nhau sau khi làm tròn theo bước `buoc`."""
    return int(len(np.unique(np.round(gia_tri / buoc))))


def tao_mo_hinh(df: pd.DataFrame, bac: int) -> MoHinhHieuChuan:
    """Khớp đường chuẩn bậc `bac` trên toàn bộ DataFrame.

    - Bù nhiệt chỉ bật khi dữ liệu có ≥ 2 mức nhiệt độ (cách nhau ≥ 0,5 °C).
    - Bậc 2 cần ≥ 3 mức độ mặn khác nhau.
    """
    S = df[COT_DO_MAN].to_numpy(float)
    T = df[COT_NHIET_DO].to_numpy(float)
    y = df[COT_DELTA_Y].to_numpy(float)

    so_muc_T = _so_muc(T, 0.5)
    co_T = so_muc_T >= 2
    co_TT = so_muc_T >= 3
    if bac >= 2 and _so_muc(S, 0.01) < 3:
        raise ValueError("Bậc 2 cần ít nhất 3 mức độ mặn chuẩn khác nhau.")

    T_ref = float(np.round(np.mean(T), 1))
    hang = chon_so_hang(bac, co_T, co_TT)
    kq = khop_binh_phuong_toi_thieu(S, T, y, hang, T_ref)

    ss_tot = float(np.sum((y - y.mean()) ** 2))
    ss_res = float(np.sum(kq.phan_du**2))
    return MoHinhHieuChuan(
        bac=bac, hang=hang,
        he_so=[float(c) for c in kq.he_so],
        hiep_phuong_sai=[[float(v) for v in row] for row in kq.hiep_phuong_sai],
        s_res_px=kq.s_res, bac_tu_do=kq.bac_tu_do, T_ref=T_ref, co_bu_nhiet=co_T,
        S_min=float(S.min()), S_max=float(S.max()),
        T_min=float(T.min()), T_max=float(T.max()),
        so_diem=len(y),
        R2=1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan"),
        RMSE_px=float(np.sqrt(np.mean(kq.phan_du**2))),
        la_mo_phong=la_du_lieu_mo_phong(df),
        id_thiet_bi=sorted({str(v) for v in df[COT_ID_THIET_BI]} - {""}),
        id_dien_thoai=sorted({str(v) for v in df[COT_ID_DIEN_THOAI]} - {""}),
        ngay_tao=datetime.now().isoformat(timespec="seconds"),
    )


# ---------------------------------------------------------------------------
# Hàm ngược S = g(Δy, T) và bất định
# ---------------------------------------------------------------------------
@dataclass
class KetQuaDoMan:
    """Kết quả ước lượng độ mặn cho một phép đo."""

    S_ppt: float                       # độ mặn ước lượng (‰, tương đương NaCl)
    u_S_ppt: float                     # bất định chuẩn (1σ)
    U_S_ppt: float                     # bất định mở rộng U = k·u
    k: float
    thanh_phan_bat_dinh: dict[str, float]   # đóng góp từng nguồn (‰)
    ngoai_dai_S: bool
    ngoai_dai_T: bool
    la_mo_phong: bool
    nhan: str
    canh_bao: list[str] = field(default_factory=list)
    han_che: str = HAN_CHE_NACL


def _tim_nghiem_S(mh: MoHinhHieuChuan, delta_y: float, T: float) -> float:
    """Tìm S sao cho f(S, T) = Δy.

    Quét lưới trong khoảng rộng hơn dải hiệu chuẩn 50% mỗi phía để tìm các điểm đổi dấu,
    rồi tinh chỉnh bằng phương pháp chia đôi (brentq). Nếu có nhiều nghiệm (đa thức bậc 2
    không đơn điệu), chọn nghiệm nằm trong dải hiệu chuẩn hoặc gần dải nhất.
    """
    from scipy.optimize import brentq

    nhip = max(mh.S_max - mh.S_min, 1.0)
    lo, hi = mh.S_min - 0.5 * nhip, mh.S_max + 0.5 * nhip
    luoi = np.linspace(lo, hi, 801)
    g = mh.du_doan_delta_y(luoi, T) - delta_y
    nghiem: list[float] = []
    for i in np.nonzero(np.sign(g[:-1]) * np.sign(g[1:]) <= 0)[0]:
        a, b = luoi[i], luoi[i + 1]
        if g[i] == 0:
            nghiem.append(float(a))
        elif g[i] * g[i + 1] < 0:
            nghiem.append(float(brentq(lambda s: float(mh.du_doan_delta_y(s, T)[0]) - delta_y, a, b)))
    if not nghiem:
        raise ValueError(
            f"Δy = {delta_y:.2f} px nằm quá xa ngoài dải đường chuẩn "
            f"(S {mh.S_min:g}–{mh.S_max:g} ‰). Không ước lượng được độ mặn."
        )
    giua = 0.5 * (mh.S_min + mh.S_max)
    trong_dai = [s for s in nghiem if mh.S_min <= s <= mh.S_max]
    ung_vien = trong_dai or nghiem
    return min(ung_vien, key=lambda s: abs(s - giua))


def uoc_luong_do_man(
    mh: MoHinhHieuChuan,
    delta_y_px: float,
    T_C: float,
    sigma_delta_y_px: float = 0.0,
    sigma_T_C: float = 0.0,
    k: float = 2.0,
    nguong_lech_T_khong_bu_C: float = 1.0,
) -> KetQuaDoMan:
    """Ước lượng độ mặn từ Δy và nhiệt độ, kèm bất định và cờ cảnh báo.

    Truyền sai số bậc 1 (xem docstring đầu mô-đun). Các nguồn bất định (đơn vị ‰):
      - "do_anh": bất định Δy của chính phép đo này (từ Cột mốc 2, σ_Δy).
      - "lap_lai_duong_chuan": độ tản mát s_res của điểm chuẩn (gồm nhiễu ảnh, pha dung
        dịch, đặt cuvet...). Có thể trùng một phần với "do_anh" -> ước lượng hơi thận trọng.
      - "he_so_duong_chuan": do hệ số đường chuẩn chỉ ước lượng từ số điểm hữu hạn.
      - "nhiet_do": do nhiệt kế sai σ_T, qua ∂f/∂T.
    """
    if not (math.isfinite(delta_y_px) and math.isfinite(T_C)):
        raise ValueError("Δy hoặc nhiệt độ không hợp lệ (NaN/vô cực).")

    S = _tim_nghiem_S(mh, delta_y_px, T_C)
    f_S = mh.dao_ham_theo_S(S, T_C)
    if abs(f_S) < 1e-9:
        raise ValueError("Độ nhạy ∂Δy/∂S ≈ 0 tại điểm này – không giải ngược được.")
    f_T = mh.dao_ham_theo_T(S, T_C) if mh.co_bu_nhiet else 0.0

    thanh_phan = {
        "do_anh": abs(sigma_delta_y_px / f_S),
        "lap_lai_duong_chuan": abs(mh.s_res_px / f_S),
        "he_so_duong_chuan": math.sqrt(max(mh.phuong_sai_du_doan(S, T_C), 0.0)) / abs(f_S),
        "nhiet_do": abs(f_T * sigma_T_C / f_S),
    }
    u = math.sqrt(sum(v * v for v in thanh_phan.values()))

    canh_bao: list[str] = []
    ngoai_S = not (mh.S_min <= S <= mh.S_max)
    if ngoai_S:
        canh_bao.append(
            f"Độ mặn ước lượng {S:.2f} ‰ nằm NGOÀI dải hiệu chuẩn "
            f"({mh.S_min:g}–{mh.S_max:g} ‰): kết quả là ngoại suy, không đáng tin."
        )
    ngoai_T = not (mh.T_min - 0.5 <= T_C <= mh.T_max + 0.5)
    if ngoai_T:
        canh_bao.append(
            f"Nhiệt độ {T_C:.1f} °C nằm ngoài khoảng đã hiệu chuẩn "
            f"({mh.T_min:.1f}–{mh.T_max:.1f} °C): bù nhiệt là ngoại suy."
        )
    if not mh.co_bu_nhiet and abs(T_C - mh.T_ref) > nguong_lech_T_khong_bu_C:
        canh_bao.append(
            f"Đường chuẩn chỉ đo ở một nhiệt độ (~{mh.T_ref:.1f} °C) nên KHÔNG bù nhiệt; "
            f"mẫu đang ở {T_C:.1f} °C. Hãy hiệu chuẩn thêm ở nhiều nhiệt độ."
        )
    if mh.la_mo_phong:
        canh_bao.append(f"{NHAN_CHUA_HIEU_CHUAN}: con số này KHÔNG phải kết quả đo thật.")
    if f_S <= 0:
        canh_bao.append("Đường chuẩn có độ nhạy âm/không đơn điệu tại điểm này – kiểm tra lại dữ liệu.")

    return KetQuaDoMan(
        S_ppt=float(S), u_S_ppt=u, U_S_ppt=k * u, k=k,
        thanh_phan_bat_dinh=thanh_phan, ngoai_dai_S=ngoai_S, ngoai_dai_T=ngoai_T,
        la_mo_phong=mh.la_mo_phong, nhan=mh.nhan, canh_bao=canh_bao,
    )


def uoc_luong_do_man_bootstrap(
    df: pd.DataFrame,
    bac: int,
    delta_y_px: float,
    T_C: float,
    sigma_delta_y_px: float = 0.0,
    so_lan: int = 500,
    muc_tin_cay: float = 0.95,
    seed: int = 0,
) -> tuple[float, float, float]:
    """Khoảng tin cậy của S bằng bootstrap (cách kiểm tra chéo cho truyền sai số).

    Mỗi lần: rút lại có hoàn lại các điểm chuẩn -> khớp lại đường chuẩn -> cộng nhiễu
    N(0, s_res² + σ_Δy²) vào Δy -> giải ngược S. Lấy phân vị của phân bố S thu được.

    Returns:
        (S_trung_vi, S_duoi, S_tren)
    """
    rng = np.random.default_rng(seed)
    gia_tri: list[float] = []
    n = len(df)
    for _ in range(so_lan):
        mau = df.iloc[rng.integers(0, n, n)]
        try:
            mh = tao_mo_hinh(mau, bac)
            nhieu = rng.normal(0.0, math.sqrt(mh.s_res_px**2 + sigma_delta_y_px**2))
            gia_tri.append(_tim_nghiem_S(mh, delta_y_px + nhieu, T_C))
        except (ValueError, np.linalg.LinAlgError):
            continue  # mẫu rút lại suy biến (vd. thiếu mức S) -> bỏ qua
    if len(gia_tri) < so_lan // 2:
        raise ValueError("Bootstrap thất bại: quá nhiều mẫu rút lại bị suy biến.")
    a = (1.0 - muc_tin_cay) / 2.0
    arr = np.asarray(gia_tri)
    return float(np.median(arr)), float(np.quantile(arr, a)), float(np.quantile(arr, 1 - a))


# ---------------------------------------------------------------------------
# Dựng đường chuẩn hoàn chỉnh: chia train/test, chọn bậc, báo cáo
# ---------------------------------------------------------------------------
@dataclass
class BaoCaoHieuChuan:
    """Toàn bộ kết quả dựng đường chuẩn."""

    mo_hinh: MoHinhHieuChuan             # khớp trên TOÀN BỘ dữ liệu -> dùng để đo
    mo_hinh_train: MoHinhHieuChuan       # khớp chỉ trên tập train -> dùng để đánh giá trên test
    rmse_kiem_dinh_cheo: dict[int, float]
    bac_chon: int
    ly_do_chon: str
    RMSE_test_px: float
    RMSE_test_ppt: float
    sai_so_theo_muc: pd.DataFrame        # sai số từng mức độ mặn (trên toàn bộ dữ liệu)
    bang_test: pd.DataFrame              # từng điểm test: S chuẩn, S ước lượng, sai số
    df_train: pd.DataFrame
    df_test: pd.DataFrame
    canh_bao: list[str] = field(default_factory=list)


def chia_train_test(
    df: pd.DataFrame, ti_le_test: float = 0.25, seed: int = 0
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Chia train/test phân tầng theo mức độ mặn.

    Mỗi mức S đưa khoảng `ti_le_test` số điểm vào test nhưng luôn giữ ≥ 1 điểm ở train,
    để train phủ hết dải S (tránh việc test phải ngoại suy).
    """
    rng = np.random.default_rng(seed)
    chi_so_test: list[int] = []
    for _, nhom in df.groupby(COT_DO_MAN):
        n_test = min(int(round(len(nhom) * ti_le_test)), len(nhom) - 1)
        if n_test > 0:
            chi_so_test.extend(rng.choice(nhom.index.to_numpy(), n_test, replace=False).tolist())
    return df.drop(index=chi_so_test), df.loc[chi_so_test]


def _bang_sai_so(mh: MoHinhHieuChuan, df: pd.DataFrame, k: float) -> pd.DataFrame:
    """Bảng từng điểm: Δy dự đoán, phần dư, S ước lượng ngược, sai số S."""
    dong = []
    for _, r in df.iterrows():
        S0, T0, y0 = float(r[COT_DO_MAN]), float(r[COT_NHIET_DO]), float(r[COT_DELTA_Y])
        try:
            S_est = uoc_luong_do_man(mh, y0, T0, k=k).S_ppt
        except ValueError:
            S_est = float("nan")
        dong.append({
            COT_DO_MAN: S0, COT_NHIET_DO: T0, COT_DELTA_Y: y0,
            "delta_y_du_doan_px": float(mh.du_doan_delta_y(S0, T0)[0]),
            "phan_du_px": y0 - float(mh.du_doan_delta_y(S0, T0)[0]),
            "S_uoc_luong_ppt": S_est,
            "sai_so_S_ppt": S_est - S0,
        })
    return pd.DataFrame(dong)


def dung_duong_chuan(
    df: pd.DataFrame,
    cau_hinh: CauHinhHieuChuan | None = None,
    bac_ep: int | None = None,
) -> BaoCaoHieuChuan:
    """Dựng đường chuẩn từ dữ liệu hiệu chuẩn.

    Quy trình:
      1. Chia train/test phân tầng theo S.
      2. Trên train: tính RMSE kiểm định chéo cho bậc 1 và bậc 2.
      3. Chọn bậc 2 CHỈ KHI nó giảm RMSE kiểm định chéo ≥ ngưỡng (mặc định 10%);
         ngược lại chọn bậc 1 (nguyên tắc "đơn giản nhất đủ dùng", chống quá khớp).
      4. Khớp bậc đã chọn trên train -> đánh giá trên test (số liệu báo cáo trung thực).
      5. Khớp lại trên toàn bộ dữ liệu -> mô hình dùng để đo.
    """
    ch = cau_hinh or CauHinhHieuChuan()
    canh_bao: list[str] = []
    if la_du_lieu_mo_phong(df):
        canh_bao.append(f"{NHAN_CHUA_HIEU_CHUAN}: đường chuẩn này dựng từ dữ liệu mô phỏng.")
    if df.attrs.get("so_dong_bi_loai", 0):
        canh_bao.append(f"Đã loại {df.attrs['so_dong_bi_loai']} dòng thiếu dữ liệu.")
    if _so_muc(df[COT_DO_MAN].to_numpy(float), 0.01) < 3:
        canh_bao.append("Cần ít nhất 3 mức độ mặn chuẩn; nên dùng 5–8 mức phủ hết dải cần đo.")

    if len(df) >= 8:
        df_train, df_test = chia_train_test(df, ch.ti_le_test, ch.seed)
    else:
        df_train, df_test = df, df.iloc[0:0]
        canh_bao.append("Quá ít điểm (< 8) nên không tách được tập test; chỉ báo cáo sai số trong mẫu.")

    S = df_train[COT_DO_MAN].to_numpy(float)
    T = df_train[COT_NHIET_DO].to_numpy(float)
    y = df_train[COT_DELTA_Y].to_numpy(float)
    so_muc_T = _so_muc(T, 0.5)
    T_ref = float(np.round(np.mean(T), 1))

    rmse_cv: dict[int, float] = {}
    for bac in (1, 2):
        if bac == 2 and _so_muc(S, 0.01) < 3:
            continue
        hang = chon_so_hang(bac, so_muc_T >= 2, so_muc_T >= 3)
        rmse_cv[bac] = rmse_kiem_dinh_cheo(S, T, y, hang, T_ref, ch.so_fold, ch.seed)

    if bac_ep is not None:
        bac_chon, ly_do = bac_ep, f"Bậc {bac_ep} do người dùng chỉ định."
    elif 2 in rmse_cv and rmse_cv[2] < (1.0 - ch.nguong_cai_thien_bac2) * rmse_cv[1]:
        bac_chon = 2
        ly_do = (f"Bậc 2 giảm RMSE kiểm định chéo từ {rmse_cv[1]:.3f} xuống {rmse_cv[2]:.3f} px "
                 f"(> {ch.nguong_cai_thien_bac2:.0%}), nên chọn bậc 2.")
    else:
        bac_chon = 1
        r2 = f"{rmse_cv[2]:.3f}" if 2 in rmse_cv else "không tính được"
        ly_do = (f"Bậc 2 (RMSE CV {r2} px) không tốt hơn bậc 1 (RMSE CV {rmse_cv[1]:.3f} px) "
                 f"đủ {ch.nguong_cai_thien_bac2:.0%}, nên chọn bậc 1 đơn giản hơn.")

    mh_train = tao_mo_hinh(df_train, bac_chon)
    mh_full = tao_mo_hinh(df, bac_chon)
    if not mh_full.co_bu_nhiet:
        canh_bao.append("Dữ liệu chỉ có một mức nhiệt độ: đường chuẩn KHÔNG bù nhiệt được.")

    if len(df_test):
        bang_test = _bang_sai_so(mh_train, df_test, ch.he_so_phu_k)
        rmse_test_px = float(np.sqrt(np.mean(bang_test["phan_du_px"] ** 2)))
        rmse_test_ppt = float(np.sqrt(np.nanmean(bang_test["sai_so_S_ppt"] ** 2)))
    else:
        bang_test = pd.DataFrame()
        rmse_test_px = rmse_test_ppt = float("nan")

    bang_all = _bang_sai_so(mh_full, df, ch.he_so_phu_k)
    theo_muc = (
        bang_all.groupby(COT_DO_MAN)
        .agg(so_diem=(COT_DELTA_Y, "size"),
             delta_y_tb_px=(COT_DELTA_Y, "mean"),
             do_lech_chuan_px=(COT_DELTA_Y, "std"),
             phan_du_tb_px=("phan_du_px", "mean"),
             S_uoc_luong_tb_ppt=("S_uoc_luong_ppt", "mean"),
             sai_so_S_tb_ppt=("sai_so_S_ppt", "mean"),
             sai_so_S_max_ppt=("sai_so_S_ppt", lambda v: float(np.nanmax(np.abs(v)))))
        .reset_index()
    )

    return BaoCaoHieuChuan(
        mo_hinh=mh_full, mo_hinh_train=mh_train, rmse_kiem_dinh_cheo=rmse_cv,
        bac_chon=bac_chon, ly_do_chon=ly_do,
        RMSE_test_px=rmse_test_px, RMSE_test_ppt=rmse_test_ppt,
        sai_so_theo_muc=theo_muc, bang_test=bang_test,
        df_train=df_train, df_test=df_test, canh_bao=canh_bao,
    )


# ---------------------------------------------------------------------------
# Đồ thị (dùng matplotlib.figure.Figure để chạy được cả trong Streamlit lẫn pytest)
# ---------------------------------------------------------------------------
def ve_duong_chuan(bc: BaoCaoHieuChuan):  # -> matplotlib.figure.Figure
    """Đồ thị Δy theo S: điểm đo (train/test) và đường chuẩn tại từng mức nhiệt độ."""
    from matplotlib.figure import Figure

    mh = bc.mo_hinh
    fig = Figure(figsize=(7, 4.5), dpi=110)
    ax = fig.add_subplot(111)
    ax.scatter(bc.df_train[COT_DO_MAN], bc.df_train[COT_DELTA_Y], s=18, label="Điểm chuẩn (train)")
    if len(bc.df_test):
        ax.scatter(bc.df_test[COT_DO_MAN], bc.df_test[COT_DELTA_Y], s=30, marker="x",
                   color="red", label="Điểm kiểm tra (test)")
    S_luoi = np.linspace(mh.S_min, mh.S_max, 200)
    tat_ca_T = pd.concat([bc.df_train, bc.df_test])[COT_NHIET_DO].to_numpy(float)
    muc_T = sorted(np.unique(np.round(tat_ca_T * 2) / 2))  # làm tròn 0,5 °C
    for T in (muc_T if mh.co_bu_nhiet else [mh.T_ref])[:6]:
        ax.plot(S_luoi, mh.du_doan_delta_y(S_luoi, T), lw=1.2, label=f"Đường chuẩn T = {T:g} °C")
    ax.set_xlabel("Độ mặn chuẩn S (‰)")
    ax.set_ylabel("Δy (pixel)")
    tieu_de = f"Đường chuẩn bậc {mh.bac}  (R² = {mh.R2:.5f})"
    if mh.la_mo_phong:
        tieu_de += f"\n{NHAN_CHUA_HIEU_CHUAN}"
    ax.set_title(tieu_de, fontsize=10, color="red" if mh.la_mo_phong else "black")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7)
    fig.tight_layout()
    return fig


def ve_phan_du(bc: BaoCaoHieuChuan):  # -> matplotlib.figure.Figure
    """Đồ thị phần dư (Δy đo − Δy dự đoán) theo S. Phần dư tốt: tản mát ngẫu nhiên quanh 0,
    không có dạng cong (nếu cong -> cần bậc cao hơn hoặc có sai số hệ thống)."""
    from matplotlib.figure import Figure

    mh = bc.mo_hinh_train
    fig = Figure(figsize=(7, 3.5), dpi=110)
    ax = fig.add_subplot(111)
    for d, nhan, kieu in ((bc.df_train, "train", "o"), (bc.df_test, "test", "x")):
        if len(d):
            du = d[COT_DELTA_Y].to_numpy(float) - mh.du_doan_delta_y(
                d[COT_DO_MAN].to_numpy(float), d[COT_NHIET_DO].to_numpy(float))
            ax.scatter(d[COT_DO_MAN], du, s=20, marker=kieu, label=nhan)
    ax.axhline(0, color="k", lw=0.8)
    for dau in (-2, 2):
        ax.axhline(dau * mh.s_res_px, color="gray", ls="--", lw=0.8)
    ax.set_xlabel("Độ mặn chuẩn S (‰)")
    ax.set_ylabel("Phần dư (pixel)")
    tieu_de = f"Phần dư (đường nét đứt: ±2·s_res = ±{2 * mh.s_res_px:.3f} px)"
    if mh.la_mo_phong:
        tieu_de += f"\n{NHAN_CHUA_HIEU_CHUAN}"
    ax.set_title(tieu_de, fontsize=10, color="red" if mh.la_mo_phong else "black")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    return fig
