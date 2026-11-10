"""Unit tests cho Cột mốc 2: Ước lượng tâm dưới pixel và đo vi sai Δy (spot.py, measure.py)."""
from __future__ import annotations

import math
import numpy as np
import pytest

from core.spot import (
    ham_gauss_1d,
    uoc_luong_tam_gauss_cot,
    uoc_luong_tam_centroid_cot,
    uoc_luong_duong_vach,
)
from core.measure import (
    do_delta_y_tu_anh,
    do_delta_y_da_khung_hinh,
    tinh_chi_so_do_duc_tuong_doi,
    tu_dong_tim_roi_hai_vach,
)


def tao_cot_gauss_ly_thuyet(
    h: int, mu: float, sigma: float = 2.5, A: float = 180.0, bg: float = 15.0, noise_std: float = 0.0
) -> tuple[np.ndarray, np.ndarray]:
    """Tạo profile 1D Gauss với tọa độ và cường độ xác định."""
    y = np.arange(h, dtype=float)
    cuong_do = ham_gauss_1d(y, bg, A, mu, sigma)
    if noise_std > 0:
        np.random.seed(42)
        cuong_do += np.random.normal(0, noise_std, size=h)
    return y, np.clip(cuong_do, 0, 255)


def tao_anh_hai_vach_ly_thuyet(
    h: int = 200,
    w: int = 150,
    y_tc: float = 50.0,
    y_mau: float = 120.35,
    do_doc: float = 0.015,
    sigma_tc: float = 2.2,
    sigma_mau: float = 2.2,
    amp_tc: float = 190.0,
    amp_mau: float = 190.0,
    bg: float = 12.0,
    noise_std: float = 1.0,
    seed: int = 42,
) -> tuple[np.ndarray, float]:
    """Tạo ảnh xám nhân tạo có 2 vạch sáng để kiểm chứng thuật toán.

    Tín hiệu vi sai chuẩn tại trung điểm w/2:
    y_mau(w/2) - y_tc(w/2) = y_mau - y_tc.
    """
    np.random.seed(seed)
    anh = np.full((h, w), bg, dtype=float)
    y_indices = np.arange(h)[:, None]  # shape (h, 1)

    for col in range(w):
        dx = col - (w / 2.0)
        mu_tc_col = y_tc + do_doc * dx
        mu_mau_col = y_mau + do_doc * dx

        vach_tc = amp_tc * np.exp(-((y_indices - mu_tc_col) ** 2) / (2.0 * sigma_tc**2))
        vach_mau = amp_mau * np.exp(-((y_indices - mu_mau_col) ** 2) / (2.0 * sigma_mau**2))
        anh[:, col] += (vach_tc + vach_mau).squeeze()

    if noise_std > 0:
        anh += np.random.normal(0, noise_std, size=(h, w))

    anh_uint8 = np.clip(anh, 0, 255).astype(np.uint8)
    delta_y_chuan = y_mau - y_tc
    return anh_uint8, delta_y_chuan


# ============================================================================
# CÁC TEST CASE CHO spot.py
# ============================================================================


def test_uoc_luong_tam_gauss_chinh_xac_duoi_pixel():
    """Kiểm tra ước lượng tâm khớp Gauss đạt sai số < 0.05 px trên tín hiệu chuẩn."""
    mu_chuan = 24.68
    sigma_chuan = 2.4
    y, cuong_do = tao_cot_gauss_ly_thuyet(50, mu=mu_chuan, sigma=sigma_chuan, noise_std=0.5)

    kq = uoc_luong_tam_gauss_cot(y, cuong_do)
    assert kq.hop_le is True
    # Sai số tìm tâm phải nhỏ hơn 0.05 pixel
    assert abs(kq.mu - mu_chuan) < 0.05
    # FWHM lí thuyết = 2 * sqrt(2*ln(2)) * sigma
    fwhm_ly_thuyet = 2.35482 * sigma_chuan
    assert abs(kq.fwhm - fwhm_ly_thuyet) < 0.2
    assert kq.r2 > 0.95


def test_uoc_luong_tam_centroid_du_phong():
    """Kiểm tra phương pháp centroid trừ nền khi dùng làm dự phòng."""
    mu_chuan = 20.0
    y, cuong_do = tao_cot_gauss_ly_thuyet(40, mu=mu_chuan, sigma=2.0)
    kq = uoc_luong_tam_centroid_cot(y, cuong_do)
    assert kq.hop_le is True
    assert abs(kq.mu - mu_chuan) < 0.15


def test_uoc_luong_duong_vach_roi():
    """Kiểm tra khớp đường thẳng qua các tâm cột trong một ROI."""
    h, w = 60, 80
    mu_center = 30.0
    slope = 0.02
    x_offset, y_offset = 100, 200

    anh_roi = np.full((h, w), 10.0, dtype=float)
    y_coords = np.arange(h)[:, None]
    for x in range(w):
        mu_x = mu_center + slope * (x - w / 2.0)
        anh_roi[:, x] += 180.0 * np.exp(-((y_coords - mu_x) ** 2) / (2.0 * 2.0**2)).squeeze()

    anh_roi = np.clip(anh_roi, 0, 255).astype(np.uint8)

    x_ref = float(x_offset + w / 2.0)
    kq = uoc_luong_duong_vach(
        anh_roi,
        x_offset=x_offset,
        y_offset=y_offset,
        x_ref=x_ref,
        phuong_phap="gauss",
    )

    y_tam_ly_thuyet = y_offset + mu_center
    assert abs(kq.y_tam - y_tam_ly_thuyet) < 0.05
    assert abs(kq.do_doc_a - slope) < 0.005
    assert kq.sai_so_y < 0.1
    assert kq.so_cot_hop_le >= w - 2


# ============================================================================
# CÁC TEST CASE CHO measure.py
# ============================================================================


def test_do_delta_y_chinh_xac_tren_anh():
    """Kiểm tra đo Δy trên ảnh hai vạch với sai số dưới 0.1 pixel."""
    anh, delta_y_chuan = tao_anh_hai_vach_ly_thuyet(
        h=220, w=160, y_tc=55.0, y_mau=145.45, do_doc=0.01, noise_std=1.0
    )

    roi_tc = (30, 80, 10, 150)
    roi_mau = (120, 175, 10, 150)

    kq = do_delta_y_tu_anh(anh, roi_tham_chieu=roi_tc, roi_mau=roi_mau)

    # Tiêu chí nghiệm thu: sai số Δy < 0.1 px
    sai_so_thuc_te = abs(kq.delta_y_px - delta_y_chuan)
    assert sai_so_thuc_te < 0.1, f"Sai số {sai_so_thuc_te:.4f} px vượt quá 0.1 px"
    assert kq.chat_luong.hop_le is True
    assert kq.chat_luong.bao_hoa is False
    assert kq.chat_luong.qua_mo is False
    assert kq.chi_so_do_duc_tuong_doi < 0.1  # Nước trong, cùng độ rộng


def test_tu_dong_tim_roi_hai_vach():
    """Kiểm tra khả năng tự phát hiện vùng ROI của 2 vạch sáng."""
    anh, _ = tao_anh_hai_vach_ly_thuyet(h=200, w=150, y_tc=45.0, y_mau=135.0)
    roi_1, roi_2 = tu_dong_tim_roi_hai_vach(anh)

    # Vạch 1 phải bao quanh y=45, Vạch 2 phải bao quanh y=135
    assert roi_1[0] <= 45 <= roi_1[1]
    assert roi_2[0] <= 135 <= roi_2[1]


def test_canh_bao_chat_luong_bao_hoa_va_mo():
    """Kiểm tra hệ thống phát hiện và cảnh báo ảnh bão hòa hoặc quá mờ."""
    # 1. Ảnh bão hòa (cháy sáng)
    anh_bao_hoa = np.zeros((100, 100), dtype=np.uint8)
    anh_bao_hoa[20:30, :] = 255  # dải pixel bão hòa lớn
    anh_bao_hoa[60:70, :] = 255

    roi_1 = (10, 40, 5, 95)
    roi_2 = (50, 80, 5, 95)
    kq_bh = do_delta_y_tu_anh(anh_bao_hoa, roi_tham_chieu=roi_1, roi_mau=roi_2)
    assert kq_bh.chat_luong.bao_hoa is True
    assert kq_bh.chat_luong.hop_le is False
    assert any("bão hòa" in cb for cb in kq_bh.chat_luong.canh_bao)

    # 2. Ảnh quá mờ (tương phản yếu)
    anh_mo = np.full((100, 100), 10, dtype=np.uint8)
    anh_mo[25, :] = 12  # tín hiệu chỉ chênh 2 mức xám so với nền
    anh_mo[65, :] = 12
    kq_mo = do_delta_y_tu_anh(anh_mo, roi_tham_chieu=roi_1, roi_mau=roi_2, phuong_phap="centroid")
    assert kq_mo.chat_luong.qua_mo is True
    assert kq_mo.chat_luong.hop_le is False


def test_chi_so_do_duc_phan_biet_ro():
    """Kiểm tra chỉ số độ đục phản ánh đúng tán xạ làm vạch phình rộng và suy giảm biên độ."""
    # Trường hợp nước trong: FWHM và biên độ tương đương
    duc_trong = tinh_chi_so_do_duc_tuong_doi(fwhm_tc=5.0, fwhm_mau=5.1, amp_tc=200.0, amp_mau=195.0)
    assert duc_trong < 0.05

    # Trường hợp nước rất đục: FWHM phình to gấp đôi, biên độ sụt giảm 60%
    duc_cao = tinh_chi_so_do_duc_tuong_doi(fwhm_tc=5.0, fwhm_mau=11.0, amp_tc=200.0, amp_mau=80.0)
    assert duc_cao > 0.5


def test_do_vi_sai_triet_tieu_rung_dong_laser_va_may_anh():
    """Kiểm chứng nguyên lí đo vi sai: Rung động chung không làm đổi Δy."""
    delta_y_thiet_ke = 68.50
    khung_hinh = []

    # Giả lập 5 khung hình bị rung lắc chung theo phương y: dịch +10, -5, +3, -8, +6 pixel
    do_rung_chung = [10.0, -5.0, 3.0, -8.0, 6.0]
    for shift in do_rung_chung:
        img, _ = tao_anh_hai_vach_ly_thuyet(
            h=240,
            w=160,
            y_tc=60.0 + shift,
            y_mau=60.0 + shift + delta_y_thiet_ke,
            seed=int(100 + shift),
        )
        khung_hinh.append(img)

    # Đo từng khung hình với ROI linh hoạt hoặc tự động tìm
    ket_qua_da_khung = do_delta_y_da_khung_hinh(khung_hinh)

    # Trung vị của Δy vẫn phải khớp chính xác < 0.1 px dù cả 2 vạch bị dịch chuyển tới 10 px
    sai_so = abs(ket_qua_da_khung.delta_y_trung_vi_px - delta_y_thiet_ke)
    assert sai_so < 0.1, f"Đo vi sai không triệt tiêu được rung động: sai số {sai_so:.4f} px"
    assert ket_qua_da_khung.so_khung_hop_le == 5

