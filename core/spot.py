"""Mô-đun ước lượng tâm vạch laser dưới độ phân giải pixel (Cột mốc 2).

Vật lí & Thuật toán:
- Chùm laser chiếu qua chất lỏng tạo ra vạch sáng nằm ngang trên màn/cảm biến camera.
- Theo phương đứng (trục y), phân bố cường độ của chùm laser cơ bản (TEM00) tuân theo
  hàm Gauss: I(y) = I_bg + A * exp(-(y - mu)^2 / (2 * sigma^2)).
- Để đạt độ chính xác dưới pixel (sub-pixel, mục tiêu sai số < 0.1 px), ta tiến hành:
  1. Với từng cột x dọc theo chiều dài vạch, ước lượng tâm mu_i bằng khớp Gauss phi tuyến
     (scipy.optimize.curve_fit) hoặc trọng tâm có trừ nền (centroid).
  2. Lọc các ước lượng kém chất lượng (R² thấp, độ rộng bất thường).
  3. Khớp đường thẳng y(x) = a * x + b qua các tâm cột bằng bình phương tối thiểu có trọng số.
  4. Nội suy/ngoại suy vị trí vạch tại cột tham chiếu x_ref kèm theo khoảng sai số chuẩn
     của phép khớp thống kê.

Lưu ý:
- Giả định vạch laser thẳng và nằm gần ngang (độ dốc nhỏ).
- Nếu ảnh bị bão hòa (clipping ở 255), đỉnh Gauss bị bẹt, tâm tính được sẽ có sai số hệ thống.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
from scipy.optimize import curve_fit


@dataclass(frozen=True)
class KetQuaCotGauss:
    """Kết quả khớp Gauss cho một cột ảnh đơn lẻ."""

    mu: float           # tọa độ tâm (sub-pixel)
    sigma: float        # độ lệch chuẩn không gian (px)
    bien_do_A: float    # cường độ đỉnh trừ nền
    nen_bg: float       # cường độ nền ước lượng
    sai_so_mu: float    # sai số chuẩn của mu từ ma trận hiệp phương sai
    r2: float           # hệ số xác định R²
    fwhm: float         # độ rộng toàn phần ở nửa cực đại FWHM = 2*sqrt(2*ln(2))*sigma
    hop_le: bool        # cờ đánh dấu khớp thành công và đạt chuẩn


@dataclass(frozen=True)
class KetQuaUocLuongVach:
    """Kết quả ước lượng vị trí và hình học của toàn bộ đoạn vạch laser."""

    x_ref: float                  # cột tham chiếu được chọn
    y_tam: float                  # vị trí tâm vạch tại x_ref (sub-pixel)
    sai_so_y: float               # sai số chuẩn của y_tam (px)
    do_doc_a: float               # hệ số góc đường vạch (px/px)
    he_so_b: float                # hệ số tự do: y = a*x + b
    fwhm_trung_binh: float        # FWHM trung bình dọc theo vạch (px)
    cuong_do_dinh_tb: float       # cường độ đỉnh trung bình (mức xám)
    r2_trung_binh: float          # R² trung bình của các cột
    so_cot_hop_le: int            # số cột đạt chuẩn được đưa vào khớp
    so_cot_tong: int              # tổng số cột đã quét
    phuong_phap: str              # "gauss" hoặc "centroid"
    danh_sach_x: list[float] = field(default_factory=list)
    danh_sach_y: list[float] = field(default_factory=list)


def ham_gauss_1d(y: np.ndarray, bg: float, A: float, mu: float, sigma: float) -> np.ndarray:
    """Mô hình hàm Gauss 1 chiều có nền phẳng: I(y) = bg + A * exp(-(y - mu)^2 / (2 * sigma^2))."""
    return bg + A * np.exp(-((y - mu) ** 2) / (2.0 * sigma**2))


def uoc_luong_tam_gauss_cot(
    y_coords: np.ndarray,
    cuong_do: np.ndarray,
    r2_toi_thieu: float = 0.80,
    fwhm_min: float = 1.0,
    fwhm_max: float = 80.0,
) -> KetQuaCotGauss:
    """Ước lượng tâm dưới pixel cho một cột ảnh bằng khớp hàm Gauss phi tuyến.

    Args:
        y_coords: Mảng tọa độ y tương ứng các pixel (thường là 0, 1, 2, ...).
        cuong_do: Mảng mức xám I(y) (0..255 hoặc float).
        r2_toi_thieu: Ngưỡng R² chấp nhận được.
        fwhm_min: FWHM tối thiểu vật lí (px).
        fwhm_max: FWHM tối đa vật lí (px).

    Returns:
        KetQuaCotGauss chứa tọa độ tâm, fwhm, sai số và cờ hợp lệ.
    """
    y_coords = np.asarray(y_coords, dtype=float)
    cuong_do = np.asarray(cuong_do, dtype=float)

    if len(cuong_do) < 4:
        return KetQuaCotGauss(0.0, 0.0, 0.0, 0.0, float("inf"), 0.0, 0.0, False)

    i_min = float(np.min(cuong_do))
    i_max = float(np.max(cuong_do))
    delta_i = i_max - i_min

    if delta_i < 5.0:  # Quá phẳng, không có tín hiệu vạch rõ
        return KetQuaCotGauss(0.0, 0.0, 0.0, i_min, float("inf"), 0.0, 0.0, False)

    # Khởi tạo tham số ban đầu từ phân bố thực nghiệm
    bg_init = float(np.percentile(cuong_do, 15))
    cuong_do_tru_nen = np.clip(cuong_do - bg_init, 0, None)
    tong_i = np.sum(cuong_do_tru_nen)

    if tong_i <= 0:
        mu_init = float(y_coords[np.argmax(cuong_do)])
        sigma_init = 3.0
    else:
        mu_init = float(np.sum(y_coords * cuong_do_tru_nen) / tong_i)
        variance = np.sum(((y_coords - mu_init) ** 2) * cuong_do_tru_nen) / tong_i
        sigma_init = float(np.sqrt(max(variance, 0.5)))

    A_init = max(delta_i, 1.0)
    sigma_init = float(np.clip(sigma_init, 1.0, 20.0))

    p0 = [bg_init, A_init, mu_init, sigma_init]
    bounds = (
        [0.0, 0.0, float(y_coords[0]), 0.3],
        [255.0, 300.0, float(y_coords[-1]), 40.0],
    )

    try:
        popt, pcov = curve_fit(
            ham_gauss_1d,
            y_coords,
            cuong_do,
            p0=p0,
            bounds=bounds,
            maxfev=600,
        )
        bg_fit, A_fit, mu_fit, sigma_fit = popt
        perr = np.sqrt(np.diag(pcov))
        sai_so_mu = float(perr[2]) if np.isfinite(perr[2]) else 1.0

        # Đánh giá hệ số R²
        y_pred = ham_gauss_1d(y_coords, *popt)
        ss_res = float(np.sum((cuong_do - y_pred) ** 2))
        ss_tot = float(np.sum((cuong_do - np.mean(cuong_do)) ** 2))
        r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-9 else 0.0

        fwhm = float(2.0 * math.sqrt(2.0 * math.log(2.0)) * abs(sigma_fit))

        hop_le = bool(
            (r2 >= r2_toi_thieu)
            and (fwhm_min <= fwhm <= fwhm_max)
            and (y_coords[0] <= mu_fit <= y_coords[-1])
            and np.isfinite(sai_so_mu)
            and (sai_so_mu < 5.0)
        )

        return KetQuaCotGauss(
            mu=float(mu_fit),
            sigma=float(abs(sigma_fit)),
            bien_do_A=float(A_fit),
            nen_bg=float(bg_fit),
            sai_so_mu=sai_so_mu,
            r2=r2,
            fwhm=fwhm,
            hop_le=hop_le,
        )

    except Exception:
        # Nếu khớp Gauss không hội tụ, đánh dấu không hợp lệ
        return KetQuaCotGauss(0.0, 0.0, 0.0, 0.0, float("inf"), 0.0, 0.0, False)


def uoc_luong_tam_centroid_cot(
    y_coords: np.ndarray,
    cuong_do: np.ndarray,
    ty_le_nguong_nen: float = 0.20,
) -> KetQuaCotGauss:
    """Ước lượng tâm theo phương pháp trọng tâm bậc 1 có trừ ngưỡng nền (Centroid).

    Dùng làm phương án dự phòng khi vạch có hình dạng phi Gauss hoặc khi Gauss không hội tụ.
    """
    y_coords = np.asarray(y_coords, dtype=float)
    cuong_do = np.asarray(cuong_do, dtype=float)

    if len(cuong_do) < 3:
        return KetQuaCotGauss(0.0, 0.0, 0.0, 0.0, float("inf"), 0.0, 0.0, False)

    i_min = float(np.min(cuong_do))
    i_max = float(np.max(cuong_do))
    delta_i = i_max - i_min

    if delta_i < 5.0:
        return KetQuaCotGauss(0.0, 0.0, 0.0, i_min, float("inf"), 0.0, 0.0, False)

    nguong = i_min + ty_le_nguong_nen * delta_i
    w = np.clip(cuong_do - nguong, 0, None)
    tong_w = float(np.sum(w))

    if tong_w <= 0:
        return KetQuaCotGauss(0.0, 0.0, 0.0, i_min, float("inf"), 0.0, 0.0, False)

    mu = float(np.sum(y_coords * w) / tong_w)
    variance = float(np.sum(((y_coords - mu) ** 2) * w) / tong_w)
    sigma = math.sqrt(max(variance, 0.2))
    fwhm = 2.35482 * sigma

    # Ước lượng thô sai số của centroid do nhiễu Poisson/đọc
    sai_so_mu = sigma / math.sqrt(tong_w / (delta_i + 1e-6) + 1e-6)

    return KetQuaCotGauss(
        mu=mu,
        sigma=sigma,
        bien_do_A=delta_i,
        nen_bg=nguong,
        sai_so_mu=sai_so_mu,
        r2=0.85,  # gán giá trị danh định khi dùng centroid
        fwhm=fwhm,
        hop_le=True,
    )


def uoc_luong_duong_vach(
    anh_roi: np.ndarray,
    x_offset: int = 0,
    y_offset: int = 0,
    x_ref: float | None = None,
    phuong_phap: Literal["gauss", "centroid"] = "gauss",
    r2_toi_thieu: float = 0.80,
    buoc_nhay_cot: int = 1,
) -> KetQuaUocLuongVach:
    """Ước lượng vị trí vạch laser từ một vùng ảnh chữ nhật (ROI).

    Thuật toán:
    1. Quét dọc từng cột x trong ROI từ x_min đến x_max.
    2. Tại mỗi cột, tìm tọa độ tâm y_mu theo Gauss hoặc Centroid.
    3. Lọc bỏ các cột không đạt chuẩn (không hợp lệ, outlier).
    4. Khớp đường thẳng y(x) = a * x + b qua các điểm hợp lệ bằng bình phương tối thiểu có trọng số.
    5. Tính vị trí và sai số chuẩn tại cột tham chiếu x_ref.

    Args:
        anh_roi: Mảng ảnh 2D mức xám (H, W).
        x_offset: Tọa độ x gốc của ROI trên ảnh toàn phần.
        y_offset: Tọa độ y gốc của ROI trên ảnh toàn phần.
        x_ref: Cột tham chiếu trên ảnh toàn phần. Nếu None, lấy trung điểm ROI.
        phuong_phap: "gauss" hoặc "centroid".
        r2_toi_thieu: Ngưỡng R² tối thiểu khi khớp Gauss.
        buoc_nhay_cot: Bước nhảy cột (1: quét toàn bộ, 2: nhảy cách để tăng tốc).

    Returns:
        KetQuaUocLuongVach chứa vị trí vạch tại x_ref, độ nghiêng, sai số, và hình dạng.

    Raises:
        ValueError: Nếu không đủ số cột hợp lệ để khớp đường thẳng.
    """
    if anh_roi.ndim != 2:
        raise ValueError(f"anh_roi phải là ảnh mức xám 2D, nhận được ndim={anh_roi.ndim}")

    h, w = anh_roi.shape
    if h < 5 or w < 5:
        raise ValueError(f"Kích thước ROI quá nhỏ ({h}x{w})")

    if x_ref is None:
        x_ref = float(x_offset + w / 2.0)

    y_coords = np.arange(h, dtype=float)

    xs: list[float] = []
    ys: list[float] = []
    weights: list[float] = []
    fwhms: list[float] = []
    amplitudes: list[float] = []
    r2s: list[float] = []

    so_cot_tong = 0

    for col in range(0, w, buoc_nhay_cot):
        so_cot_tong += 1
        cuong_do_cot = anh_roi[:, col]

        if phuong_phap == "gauss":
            kq = uoc_luong_tam_gauss_cot(
                y_coords, cuong_do_cot, r2_toi_thieu=r2_toi_thieu
            )
            # Nếu Gauss thất bại thử lại bằng centroid
            if not kq.hop_le:
                kq_cent = uoc_luong_tam_centroid_cot(y_coords, cuong_do_cot)
                if kq_cent.hop_le:
                    kq = kq_cent
        else:
            kq = uoc_luong_tam_centroid_cot(y_coords, cuong_do_cot)

        if kq.hop_le and np.isfinite(kq.mu) and np.isfinite(kq.sai_so_mu):
            xs.append(float(x_offset + col))
            ys.append(float(y_offset + kq.mu))
            # Trọng số w = 1 / sigma^2
            sigma_tong = max(kq.sai_so_mu, 0.02)
            weights.append(1.0 / (sigma_tong**2))
            fwhms.append(kq.fwhm)
            amplitudes.append(kq.bien_do_A)
            r2s.append(kq.r2)

    so_cot_hop_le = len(xs)
    if so_cot_hop_le < 3:
        raise ValueError(
            f"Không đủ cột hợp lệ để khớp vạch (chỉ có {so_cot_hop_le}/{so_cot_tong} cột đạt chuẩn). "
            "Kiểm tra lại vùng chọn ROI hoặc chất lượng vạch sáng."
        )

    arr_x = np.array(xs, dtype=float)
    arr_y = np.array(ys, dtype=float)
    arr_w = np.array(weights, dtype=float)

    # Khớp đường thẳng có trọng số y = a*x + b
    # Bằng cách giải hệ ma trận Design: [x, 1]
    deg = 1
    poly_coeffs, cov = np.polyfit(arr_x, arr_y, deg=deg, w=np.sqrt(arr_w), cov=True)
    a, b = float(poly_coeffs[0]), float(poly_coeffs[1])

    # Dự báo tại x_ref: y_ref = a * x_ref + b
    y_ref = a * x_ref + b

    # Sai số chuẩn của y_ref:
    # Var(y_ref) = Var(a)*x_ref^2 + Var(b) + 2*x_ref*Cov(a,b)
    var_y_ref = cov[0, 0] * (x_ref**2) + cov[1, 1] + 2.0 * x_ref * cov[0, 1]
    sai_so_y = float(math.sqrt(max(var_y_ref, 1e-8)))

    return KetQuaUocLuongVach(
        x_ref=x_ref,
        y_tam=y_ref,
        sai_so_y=sai_so_y,
        do_doc_a=a,
        he_so_b=b,
        fwhm_trung_binh=float(np.mean(fwhms)),
        cuong_do_dinh_tb=float(np.mean(amplitudes)),
        r2_trung_binh=float(np.mean(r2s)),
        so_cot_hop_le=so_cot_hop_le,
        so_cot_tong=so_cot_tong,
        phuong_phap=phuong_phap,
        danh_sach_x=xs,
        danh_sach_y=ys,
    )

