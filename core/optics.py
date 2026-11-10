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

import math
import warnings
from dataclasses import dataclass
from pathlib import Path

import yaml

CONFIG_MAC_DINH = Path(__file__).resolve().parents[1] / "config.yaml"


class PhanXaToanPhanError(ValueError):
    """Báo lỗi khi n·sin(A) ≥ 1: tia bị phản xạ toàn phần, không ló ra."""


class GanPhanXaToanPhanWarning(UserWarning):
    """Cảnh báo khi n·sin(A) gần 1: độ nhạy tăng vọt nhưng rất dễ mất tia."""


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

    @classmethod
    def tu_yaml(cls, duong_dan: str | Path = CONFIG_MAC_DINH) -> "CauHinhQuangHoc":
        """Đọc cấu hình từ file YAML."""
        with open(duong_dan, encoding="utf-8") as f:
            c = yaml.safe_load(f)
        q, a = c["quang_hoc"], c["anh"]
        return cls(
            A_do=float(q["goc_dinh_A_do"]),
            D_m=float(q["khoang_cach_man_D_m"]),
            n_nuoc_ngot=float(q["chiet_suat_nuoc_ngot"]),
            dn_dS=float(q["dn_dS_moi_phan_nghin"]),
            dn_dT=float(q["dn_dT_moi_do_C"]),
            T_tham_chieu_C=float(q["nhiet_do_tham_chieu_C"]),
            bien_TIR=float(q["bien_an_toan_TIR"]),
            pixel_mm=float(a["kich_thuoc_pixel_mm"]),
        )


def chiet_suat(S_ppt: float, T_C: float, cfg: CauHinhQuangHoc) -> float:
    """Chiết suất nước mặn theo mô hình tuyến tính.

    n(S, T) = n0 + (dn/dS)·S + (dn/dT)·(T − T_ref)
    Giả định: tuyến tính trong dải hẹp; chỉ xét NaCl (nước thật còn ion khác).
    """
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
    mm_moi_ppt = D * 1000.0 * dd_dn * cfg.dn_dS / math.cos(delta) ** 2
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
    nhiet = abs(cfg.dn_dT) * lech_nhiet_do_C / abs(cfg.dn_dS)

    h = 1e-3  # độ, bước sai phân
    y_p = delta_y_vi_sai_px(S_ppt, T_C, T_C, cfg, cfg.A_do + h)
    y_m = delta_y_vi_sai_px(S_ppt, T_C, T_C, cfg, cfg.A_do - h)
    dy_dA = (y_p - y_m) / (2 * h)  # px/độ
    goc_a = abs(dy_dA) * sai_so_goc_A_do / px_ppt

    troi = troi_laser_px * he_so_triet_chung / px_ppt

    ket_qua = {"tim_tam": tim_tam, "nhiet_do": nhiet, "goc_A": goc_a, "troi_laser": troi}
    ket_qua["tong_RSS"] = math.sqrt(sum(v * v for v in ket_qua.values()))
    return ket_qua
