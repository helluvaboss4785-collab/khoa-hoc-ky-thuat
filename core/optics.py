"""Mô hình quang học của lăng kính rỗng hai ngăn (Cột mốc 1).

Hình học: tia laser vuông góc mặt vào nên không bị lệch ở mặt vào; trong chất lỏng
tia đến mặt ra với góc tới bằng góc đỉnh A; ra không khí theo định luật Snell:

    sin(θ_ra) = n · sin(A)          (không dùng xấp xỉ lăng kính mỏng)
    δ = θ_ra − A                    (góc lệch)
    dịch chuyển trên màn ≈ D·tan(δ)

Thành kính/acrylic hai mặt song song nên không đổi góc ra (chỉ dời tia song song).
Phản xạ toàn phần khi n·sin(A) ≥ 1.

Lưu ý: MỌI hằng số lấy từ config.yaml là xấp xỉ, cần xác nhận bằng tài liệu
và đường chuẩn thực nghiệm. Kết quả ở đây là DỰ BÁO LÍ THUYẾT, không phải số đo.
"""
from __future__ import annotations

import logging
import math
import warnings
from dataclasses import dataclass
from pathlib import Path

import yaml

_LOGGER = logging.getLogger(__name__)
CONFIG_MAC_DINH = Path(__file__).resolve().parents[1] / "config.yaml"


class PhanXaToanPhanError(ValueError):
    """Báo lỗi khi n·sin(A) ≥ 1: tia bị phản xạ toàn phần, không ló ra."""


class GanPhanXaToanPhanWarning(UserWarning):
    """Cảnh báo khi n·sin(A) gần 1: độ nhạy tăng vọt nhưng rất dễ mất tia."""


class NgoaiDaiQuanFryWarning(UserWarning):
    """Cảnh báo khi T, S hoặc bước sóng λ nằm ngoài dải hiệu lực công thức Quan–Fry."""


@dataclass(frozen=True)
class CauHinhQuangHoc:
    """Các tham số quang học (đọc từ config.yaml)."""

    A_do: float            # góc đỉnh (độ)
    D_m: float             # quãng đường tới màn (m)
    n_nuoc_ngot: float     # chiết suất nước ngọt tại nhiệt độ tham chiếu
    dn_dS: float           # dn/dS (1/‰)
    dn_dT: float           # dn/dT (1/°C)
    T_tham_chieu_C: float  # nhiệt độ ứng với n_nuoc_ngot (°C)
    bien_TIR: float        # biên an toàn phản xạ toàn phần
    pixel_mm: float        # kích thước pixel quy đổi trên màn (mm/px)
    mo_hinh_chiet_suat: str = "tuyen_tinh"  # "tuyen_tinh" hoặc "quan_fry"
    buoc_song_nm: float = 650.0             # bước sóng (nm) cho công thức Quan–Fry

    @property
    def T_chuan_chiet_suat_C(self) -> float:
        """Bí danh rõ nghĩa hơn cho nhiệt độ chuẩn chiết suất của nước ngọt."""
        return self.T_tham_chieu_C

    @classmethod
    def tu_yaml(cls, duong_dan: str | Path = CONFIG_MAC_DINH) -> "CauHinhQuangHoc":
        """Đọc cấu hình từ file YAML."""
        with open(duong_dan, encoding="utf-8") as f:
            c = yaml.safe_load(f)
        q, a = c["quang_hoc"], c["anh"]
        if "nhiet_do_chuan_chiet_suat_C" in q:
            t_chuan = float(q["nhiet_do_chuan_chiet_suat_C"])
        elif "nhiet_do_tham_chieu_C" in q:
            msg = (
                "Khóa 'quang_hoc.nhiet_do_tham_chieu_C' đã lỗi thời và dễ nhầm với nhiệt độ ngăn tham chiếu; "
                "hãy đổi sang 'quang_hoc.nhiet_do_chuan_chiet_suat_C'."
            )
            warnings.warn(msg, DeprecationWarning, stacklevel=2)
            _LOGGER.warning(msg)
            t_chuan = float(q["nhiet_do_tham_chieu_C"])
        else:
            raise KeyError("Thiếu khóa 'quang_hoc.nhiet_do_chuan_chiet_suat_C' trong config.")
        return cls(
            A_do=float(q["goc_dinh_A_do"]),
            D_m=float(q["khoang_cach_man_D_m"]),
            n_nuoc_ngot=float(q["chiet_suat_nuoc_ngot"]),
            dn_dS=float(q["dn_dS_moi_phan_nghin"]),
            dn_dT=float(q["dn_dT_moi_do_C"]),
            T_tham_chieu_C=t_chuan,
            bien_TIR=float(q["bien_an_toan_TIR"]),
            pixel_mm=float(a["kich_thuoc_pixel_mm"]),
            mo_hinh_chiet_suat=str(q.get("mo_hinh_chiet_suat", "tuyen_tinh")).strip().lower(),
            buoc_song_nm=float(q.get("buoc_song_nm", 650.0)),
        )


HE_SO_QUAN_FRY_TRONG_MA: dict[str, float] = {
    "a0": 1.31405,
    "a1": 1.779e-4,
    "a2": -1.05e-6,
    "a3": 1.6e-8,
    "a4": -2.02e-6,
    "a5": 15.868,
    "a6": 0.01155,
    "a7": -0.00423,
    "a8": -4382.0,
    "a9": 1.1455e6,
}


def chiet_suat_quan_fry(S_ppt: float, T_C: float, buoc_song_nm: float = 650.0) -> float:
    """Chiết suất tuyệt đối của nước biển n(S, T, λ) theo công thức thực nghiệm Quan–Fry.

    Các hệ số lấy từ nhóm; PHẢI đối chiếu với bài gốc Quan & Fry (Applied Optics, 1995) trước khi đưa vào báo cáo.
    Không nhân thêm chiết suất không khí. Phát cảnh báo khi ngoài dải 0–30 °C, 0–35 ‰, 400–700 nm.
    """
    a0 = HE_SO_QUAN_FRY_TRONG_MA["a0"]
    a1 = HE_SO_QUAN_FRY_TRONG_MA["a1"]
    a2 = HE_SO_QUAN_FRY_TRONG_MA["a2"]
    a3 = HE_SO_QUAN_FRY_TRONG_MA["a3"]
    a4 = HE_SO_QUAN_FRY_TRONG_MA["a4"]
    a5 = HE_SO_QUAN_FRY_TRONG_MA["a5"]
    a6 = HE_SO_QUAN_FRY_TRONG_MA["a6"]
    a7 = HE_SO_QUAN_FRY_TRONG_MA["a7"]
    a8 = HE_SO_QUAN_FRY_TRONG_MA["a8"]
    a9 = HE_SO_QUAN_FRY_TRONG_MA["a9"]

    ngoai: list[str] = []
    if not (0.0 <= T_C <= 30.0):
        ngoai.append(f"T={T_C:g} °C ngoài 0–30 °C")
    if not (0.0 <= S_ppt <= 35.0):
        ngoai.append(f"S={S_ppt:g} ‰ ngoài 0–35 ‰")
    if not (400.0 <= buoc_song_nm <= 700.0):
        ngoai.append(f"λ={buoc_song_nm:g} nm ngoài 400–700 nm")
    if ngoai:
        warnings.warn(
            "Ngoài dải hiệu lực Quan–Fry (" + ", ".join(ngoai) + ").",
            NgoaiDaiQuanFryWarning,
            stacklevel=2,
        )

    lam = float(buoc_song_nm)
    return float(
        a0
        + (a1 + a2 * T_C + a3 * (T_C**2)) * S_ppt
        + a4 * (T_C**2)
        + (a5 + a6 * S_ppt + a7 * T_C) / lam
        + a8 / (lam**2)
        + a9 / (lam**3)
    )


def _dn_dS(S_ppt: float, T_C: float, cfg: CauHinhQuangHoc) -> float:
    if cfg.mo_hinh_chiet_suat == "quan_fry":
        return float(1.779e-4 - 1.05e-6 * T_C + 1.6e-8 * (T_C**2) + 0.01155 / cfg.buoc_song_nm)
    return cfg.dn_dS


def _dn_dT(S_ppt: float, T_C: float, cfg: CauHinhQuangHoc) -> float:
    if cfg.mo_hinh_chiet_suat == "quan_fry":
        return float((-1.05e-6 + 2.0 * 1.6e-8 * T_C) * S_ppt + 2.0 * (-2.02e-6) * T_C - 0.00423 / cfg.buoc_song_nm)
    return cfg.dn_dT


def chiet_suat(S_ppt: float, T_C: float, cfg: CauHinhQuangHoc) -> float:
    """Chiết suất nước mặn theo mô hình tuyến tính hoặc Quan–Fry (nếu chọn trong config).

    - Mặc định ("tuyen_tinh"): n(S, T) = n0 + (dn/dS)·S + (dn/dT)·(T − T_ref).
    - Nếu mo_hinh_chiet_suat == "quan_fry": gọi `chiet_suat_quan_fry`.
    Giả định: chỉ xét thành phần muối biển chuẩn / NaCl (nước ao thật còn ion khác).
    """
    if cfg.mo_hinh_chiet_suat == "quan_fry":
        return chiet_suat_quan_fry(S_ppt, T_C, cfg.buoc_song_nm)
    return cfg.n_nuoc_ngot + cfg.dn_dS * S_ppt + cfg.dn_dT * (T_C - cfg.T_tham_chieu_C)


def goc_ra(n: float, A_do: float, bien_TIR: float = 0.02) -> float:
    """Góc ló θ_ra (độ) từ sin(θ_ra) = n·sin(A).

    Raises:
        PhanXaToanPhanError: nếu n·sin(A) ≥ 1.
    Warns:
        GanPhanXaToanPhanWarning: nếu n·sin(A) > 1 − bien_TIR.
    """
    x = n * math.sin(math.radians(A_do))
    if x >= 1.0:
        raise PhanXaToanPhanError(
            f"Phản xạ toàn phần: n·sin(A) = {x:.4f} ≥ 1 (n={n:.4f}, A={A_do:.2f}°). "
            "Giảm góc đỉnh A."
        )
    if x > 1.0 - bien_TIR:
        warnings.warn(
            f"Gần phản xạ toàn phần: n·sin(A) = {x:.4f}. Tia ló rất xiên, dễ mất tín hiệu.",
            GanPhanXaToanPhanWarning,
            stacklevel=2,
        )
    return math.degrees(math.asin(x))


def goc_lech(n: float, A_do: float, bien_TIR: float = 0.02) -> float:
    """Góc lệch δ = θ_ra − A (độ)."""
    return goc_ra(n, A_do, bien_TIR) - A_do


def do_nhay_goc_theo_n(n: float, A_do: float) -> float:
    """dδ/dn = sin(A)/cos(θ_ra) (rad trên đơn vị chiết suất).

    Suy ra từ vi phân sin(θ_ra) = n·sin(A) theo n, vì A cố định: δ' = θ_ra'.
    Tăng nhanh khi θ_ra → 90° (gần phản xạ toàn phần).
    """
    theta = math.radians(goc_ra(n, A_do))
    return math.sin(math.radians(A_do)) / math.cos(theta)


def dich_chuyen_man_mm(n: float, A_do: float, D_m: float) -> float:
    """Độ dịch tia trên màn (mm) so với tia không lệch: D·tan(δ).

    Giả định: tia tới vuông góc mặt vào, D đo từ mặt ra tới màn, màn vuông góc
    tia không lệch, bỏ qua bề dày lăng kính.
    """
    delta = math.radians(goc_lech(n, A_do))
    return D_m * 1000.0 * math.tan(delta)


def delta_y_vi_sai_mm(
    S_ppt: float, T_mau_C: float, T_thamchieu_C: float, cfg: CauHinhQuangHoc,
    A_do: float | None = None,
) -> float:
    """Δy lí thuyết (mm) = dịch chuyển vạch mẫu − dịch chuyển vạch tham chiếu.

    Ngăn tham chiếu là nước cất (S = 0) ở nhiệt độ T_thamchieu_C.
    Đo vi sai nên phần chung (rung máy, trôi laser) bị triệt tiêu.
    """
    A = cfg.A_do if A_do is None else A_do
    n_mau = chiet_suat(S_ppt, T_mau_C, cfg)
    n_tc = chiet_suat(0.0, T_thamchieu_C, cfg)
    return dich_chuyen_man_mm(n_mau, A, cfg.D_m) - dich_chuyen_man_mm(n_tc, A, cfg.D_m)


def delta_y_vi_sai_px(
    S_ppt: float, T_mau_C: float, T_thamchieu_C: float, cfg: CauHinhQuangHoc,
    A_do: float | None = None,
) -> float:
    """Δy lí thuyết quy ra pixel = mm / (mm mỗi pixel)."""
    return delta_y_vi_sai_mm(S_ppt, T_mau_C, T_thamchieu_C, cfg, A_do) / cfg.pixel_mm


def pixel_moi_phan_nghin(
    S_ppt: float, T_C: float, cfg: CauHinhQuangHoc,
    A_do: float | None = None, D_m: float | None = None,
) -> float:
    """Độ nhạy: số pixel dịch mỗi 1‰ tại độ mặn S, nhiệt độ T.

    d(Δy)/dS = D·sec²(δ)·(dδ/dn)·(dn/dS) / (mm mỗi pixel)
    """
    A = cfg.A_do if A_do is None else A_do
    D = cfg.D_m if D_m is None else D_m
    n = chiet_suat(S_ppt, T_C, cfg)
    delta = math.radians(goc_lech(n, A))
    dd_dn = do_nhay_goc_theo_n(n, A)
    mm_moi_ppt = D * 1000.0 * dd_dn * _dn_dS(S_ppt, T_C, cfg) / math.cos(delta) ** 2
    return mm_moi_ppt / cfg.pixel_mm


def ngan_sach_sai_so(
    S_ppt: float,
    T_C: float,
    cfg: CauHinhQuangHoc,
    sai_so_tim_tam_px: float,
    lech_nhiet_do_C: float,
    sai_so_goc_A_do: float,
    troi_laser_px: float,
    he_so_triet_chung: float,
) -> dict[str, float]:
    """Quy các nguồn nhiễu về đơn vị ‰ (độ lệch chuẩn tương đương).

    - tim_tam: σ_px / (px mỗi ‰).
    - nhiet_do: chênh nhiệt độ hai ngăn ΔT đổi chiết suất |dn/dT|·ΔT,
      tương đương |dn/dT|·ΔT / (dn/dS) ‰.
    - goc_A: hai ngăn dùng chung góc A nên A sai chỉ làm sai độ nhạy (tỉ lệ với S);
      tính số học bằng đạo hàm sai phân của Δy theo A.
    - troi_laser: trôi chung × hệ số triệt chung còn lọt vào Δy (cần đo thực nghiệm).
    Tổng hợp theo căn bậc hai tổng bình phương (các nguồn độc lập).
    Đây là PHÂN TÍCH ĐỘ NHẠY với giả định đầu vào, không phải bất định đo thực.
    """
    px_ppt = pixel_moi_phan_nghin(S_ppt, T_C, cfg)
    tim_tam = sai_so_tim_tam_px / px_ppt
    nhiet = abs(_dn_dT(S_ppt, T_C, cfg)) * lech_nhiet_do_C / abs(_dn_dS(S_ppt, T_C, cfg))

    h = 1e-3  # độ, bước sai phân
    y_p = delta_y_vi_sai_px(S_ppt, T_C, T_C, cfg, cfg.A_do + h)
    y_m = delta_y_vi_sai_px(S_ppt, T_C, T_C, cfg, cfg.A_do - h)
    dy_dA = (y_p - y_m) / (2 * h)  # px/độ
    goc_a = abs(dy_dA) * sai_so_goc_A_do / px_ppt

    troi = troi_laser_px * he_so_triet_chung / px_ppt

    ket_qua = {"tim_tam": tim_tam, "nhiet_do": nhiet, "goc_A": goc_a, "troi_laser": troi}
    ket_qua["tong_RSS"] = math.sqrt(sum(v * v for v in ket_qua.values()))
    return ket_qua
