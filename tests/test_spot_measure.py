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
    chon_kenh_laser,
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


def test_co_bao_hoa_bat_bien_theo_chieu_cao_roi():
    """T6: Cờ bão hòa tính theo cột phải cho cùng kết luận với ROI cao ±15, ±40, ±120 px."""
    anh, _ = tao_anh_hai_vach_ly_thuyet(
        h=320, w=140, y_tc=150.0, y_mau=200.0, amp_tc=260.0, amp_mau=260.0, bg=10.0, noise_std=0.5
    )
    # Làm bão hòa lõi vạch mẫu tại y=200 để kiểm tra không phụ thuộc diện tích ROI
    anh[198:203, 10:130] = 255

    roi_tc = (135, 165, 10, 130)
    ket_luan = []
    for half_h in (15, 40, 120):
        y1 = max(0, 200 - half_h)
        y2 = min(320, 200 + half_h)
        kq = do_delta_y_tu_anh(anh, roi_tham_chieu=roi_tc, roi_mau=(y1, y2, 10, 130), tao_anh_ve=False)
        assert kq.chat_luong.bao_hoa is True
        assert kq.chat_luong.hop_le is False
        ket_luan.append(kq.chat_luong.ti_le_bao_hoa)

    assert ket_luan[0] == pytest.approx(ket_luan[1], abs=1e-6)
    assert ket_luan[1] == pytest.approx(ket_luan[2], abs=1e-6)


def test_snr_tinh_ca_hai_vung_lay_gia_tri_thap_hon():
    """T6: Vạch tham chiếu rõ nhưng vạch mẫu quá mờ vẫn phải báo quá mờ và hop_le=False."""
    anh, _ = tao_anh_hai_vach_ly_thuyet(
        h=200, w=140, y_tc=50.0, y_mau=130.0, amp_tc=190.0, amp_mau=10.0, bg=15.0, noise_std=2.0
    )
    kq = do_delta_y_tu_anh(
        anh,
        roi_tham_chieu=(30, 70, 10, 130),
        roi_mau=(110, 150, 10, 130),
        phuong_phap="centroid",
        snr_toi_thieu=10.0,
        tao_anh_ve=False,
    )
    assert kq.chat_luong.snr < 10.0
    assert kq.chat_luong.qua_mo is True
    assert kq.chat_luong.hop_le is False


def test_loai_ngoai_lai_3_sigma_chan_trong_so_va_dem_centroid():
    """T8: Loại cột ngoại lai 3σ lặp, giới hạn tỉ số trọng số và đếm cột dùng centroid."""
    h, w = 80, 60
    anh_roi = np.full((h, w), 12.0, dtype=float)
    y_coords = np.arange(h, dtype=float)
    slope = 0.02
    mu_center = 40.0
    for x in range(w):
        mu_x = mu_center + slope * (x - w / 2.0)
        # Cố ý tạo 2 cột ngoại lai bị dịch hẳn 12 px so với đường chuẩn
        if x in (10, 45):
            mu_x += 12.0
        # Cột 25..27 làm thành hai đỉnh đối xứng quanh mu_x (R² Gauss đơn < 0.80 -> rơi về centroid dự phòng)
        if x in (25, 26, 27):
            anh_roi[:, x] += 180.0 * np.exp(-((y_coords - (mu_x - 3.5)) ** 2) / 2.0)
            anh_roi[:, x] += 180.0 * np.exp(-((y_coords - (mu_x + 3.5)) ** 2) / 2.0)
        else:
            anh_roi[:, x] += 180.0 * np.exp(-((y_coords - mu_x) ** 2) / (2.0 * 2.0**2))

    anh_u8 = np.clip(anh_roi, 0, 255).astype(np.uint8)
    kq = uoc_luong_duong_vach(
        anh_u8,
        x_offset=0,
        y_offset=0,
        x_ref=w / 2.0,
        phuong_phap="gauss",
        ty_le_trong_so_toi_da=50.0,
    )
    assert abs(kq.y_tam - mu_center) < 0.1
    assert kq.so_cot_bi_loai_ngoai_lai >= 2
    assert kq.so_cot_dung_centroid >= 1


def test_da_khung_hinh_ghi_khung_loi_troi_va_dao_dong_sang():
    """T8: Không nuốt lỗi khung, tổng hợp chất lượng xấu nhất, bắt trôi theo thời gian và dao động sáng."""
    # 1. Chuỗi có 1 khung mờ, 1 khung cháy sáng, 3 khung tốt -> báo 3/5 và chat_luong xấu nhất
    k_tot_1, _ = tao_anh_hai_vach_ly_thuyet(h=220, w=150, y_tc=55.0, y_mau=135.0, seed=1)
    k_tot_2, _ = tao_anh_hai_vach_ly_thuyet(h=220, w=150, y_tc=55.0, y_mau=135.1, seed=2)
    k_tot_3, _ = tao_anh_hai_vach_ly_thuyet(h=220, w=150, y_tc=55.0, y_mau=134.9, seed=3)
    k_den = np.zeros((100, 100), dtype=np.uint8)
    k_chay = k_tot_1.copy()
    k_chay[53:57, 10:140] = 255
    res = do_delta_y_da_khung_hinh([k_tot_1, k_den, k_chay, k_tot_2, k_tot_3])
    assert res.so_khung_hop_le == 3
    assert res.tong_so_khung == 5
    assert len(res.khung_loi) == 2
    assert res.chat_luong_chung.hop_le is False
    assert res.chat_luong_chung.bao_hoa is True

    # 2. Chuỗi có trôi đơn điệu theo thời gian (1.2 px mỗi khung) -> bật cảnh báo trôi
    frames_troi = [
        tao_anh_hai_vach_ly_thuyet(h=220, w=150, y_tc=55.0, y_mau=130.0 + 1.2 * i, seed=20 + i)[0]
        for i in range(5)
    ]
    res_troi = do_delta_y_da_khung_hinh(frames_troi)
    assert res_troi.canh_bao_troi_theo_thoi_gian is True
    assert res_troi.do_doc_troi_px_moi_khung == pytest.approx(1.2, abs=0.1)

    # 3. Chuỗi có dao động mức sáng đỉnh lớn giữa các khung -> bật cảnh báo phơi sáng
    f_sang1, _ = tao_anh_hai_vach_ly_thuyet(h=220, w=150, y_tc=55.0, y_mau=135.0, amp_tc=210.0, amp_mau=210.0, seed=30)
    f_sang2, _ = tao_anh_hai_vach_ly_thuyet(h=220, w=150, y_tc=55.0, y_mau=135.0, amp_tc=90.0, amp_mau=90.0, seed=31)
    res_sang = do_delta_y_da_khung_hinh([f_sang1, f_sang2, f_sang1])
    assert res_sang.canh_bao_dao_dong_phoi_sang is True


def test_q1_chon_kenh_laser_va_bao_hoa_theo_kenh():
    """Q1: Tự chọn kênh R với laser đỏ 650 nm và bắt bão hòa riêng kênh R dù ảnh xám < 250."""
    gray_clean, dy_true = tao_anh_hai_vach_ly_thuyet(
        h=220, w=150, y_tc=55.0, y_mau=135.0, amp_tc=190.0, amp_mau=190.0, bg=10.0, noise_std=0.5, seed=40
    )
    # Dựng ảnh BGR (OpenCV): R mạnh (laser 650 nm), G/B yếu 25% -> độ xám không bão hòa nhưng R rất nét
    bgr = np.zeros((220, 150, 3), dtype=np.uint8)
    bgr[:, :, 2] = gray_clean
    bgr[:, :, 1] = (gray_clean.astype(float) * 0.25).astype(np.uint8)
    bgr[:, :, 0] = (gray_clean.astype(float) * 0.20).astype(np.uint8)

    anh_r, kenh_auto = chon_kenh_laser(bgr, kenh_laser="auto")
    assert kenh_auto == "R"
    assert np.array_equal(anh_r, gray_clean)

    kq_ok = do_delta_y_tu_anh(bgr, kenh_laser="auto", tao_anh_ve=False)
    assert kq_ok.kenh_su_dung == "R"
    assert kq_ok.chat_luong.hop_le is True
    assert abs(kq_ok.delta_y_px - dy_true) < 0.1

    # Làm bão hòa lõi kênh R về 255 nhưng giữ G=60, B=50 -> độ xám L ≈ 0.299*255+0.587*60+0.114*50 ≈ 117 << 250
    bgr_bh = bgr.copy()
    bgr_bh[53:58, 20:130, 2] = 255
    kq_bh = do_delta_y_tu_anh(bgr_bh, kenh_laser="auto", tao_anh_ve=False)
    assert kq_bh.chat_luong.bao_hoa is True
    assert "R" in kq_bh.chat_luong.kenh_bao_hoa
    assert kq_bh.chat_luong.hop_le is False

    # Thử chọn tường minh kênh G
    kq_g = do_delta_y_tu_anh(bgr, kenh_laser="G", tao_anh_ve=False)
    assert kq_g.kenh_su_dung == "G"


def test_q2_canh_bao_dom_cuc_bo_va_cot_lien_tiep():
    """Q2: Đốm bão hòa rải rác (<15 cột liên tiếp, <=30%) chỉ cảnh báo cẩn thận; >=15 cột liên tiếp -> nghiêm trọng."""
    anh, _ = tao_anh_hai_vach_ly_thuyet(h=220, w=150, y_tc=55.0, y_mau=135.0, amp_tc=190.0, amp_mau=190.0, seed=55)
    # 1. Rải 6 cột rời rạc bão hòa trong ROI mẫu (~5% cột < 30%, độ dài liên tiếp = 2 < 15)
    anh_dom = anh.copy()
    for col in (20, 21, 50, 51, 90, 91):
        anh_dom[134:137, col] = 255
    kq_dom = do_delta_y_tu_anh(anh_dom, roi_tham_chieu=(35, 75, 10, 140), roi_mau=(115, 155, 10, 140), tao_anh_ve=False)
    assert kq_dom.chat_luong.bao_hoa is False
    assert kq_dom.chat_luong.co_dom_bao_hoa_cuc_bo is True
    assert kq_dom.chat_luong.hop_le is True
    assert kq_dom.chat_luong.so_cot_bao_hoa_lien_tiep_max == 2
    assert any(c["ma"] == "DOM_BAO_HOA_CUC_BO" and c["cap"] == "can_than" for c in kq_dom.chat_luong.canh_bao_chi_tiet)

    # 2. Một đoạn bẹt đỉnh 18 cột liên tiếp (>= 15, dù tỉ lệ < 30%) -> phải gắn bao_hoa=True, hop_le=False
    anh_bet = anh.copy()
    anh_bet[134:137, 40:58] = 255
    kq_bet = do_delta_y_tu_anh(anh_bet, roi_tham_chieu=(35, 75, 10, 140), roi_mau=(115, 155, 10, 140), tao_anh_ve=False)
    assert kq_bet.chat_luong.bao_hoa is True
    assert kq_bet.chat_luong.hop_le is False
    assert kq_bet.chat_luong.so_cot_bao_hoa_lien_tiep_max >= 15


def test_q3_anh_12mp_nhanh_duoi_3s_va_loi_nen_khong_deu():
    """Q3: Ảnh 4000×3000 (12MP) đo <= 3s và báo đúng nguyên nhân khi nền không đều làm mất vạch."""
    import time
    from core.measure import KhongTimThayVachError

    h_big, w_big = 3000, 4000
    anh_big = np.full((h_big, w_big), 14, dtype=np.uint8)
    y_idx = np.arange(h_big, dtype=np.float32)[:, None]
    vach_trai = 180.0 * np.exp(-((y_idx - 900.0) ** 2) / (2.0 * 4.5**2))
    vach_phai = 180.0 * np.exp(-((y_idx - 1650.25) ** 2) / (2.0 * 4.5**2))
    anh_big[:, 150:1850] = np.clip(14.0 + vach_trai, 0, 255).astype(np.uint8)
    anh_big[:, 2150:3850] = np.clip(14.0 + vach_phai, 0, 255).astype(np.uint8)

    t0 = time.perf_counter()
    kq = do_delta_y_tu_anh(anh_big, tao_anh_ve=False)
    dt = time.perf_counter() - t0
    assert dt <= 3.0, f"Đo ảnh 4000x3000 mất {dt:.2f}s > 3.0s"
    assert abs(kq.delta_y_px - 750.25) < 0.2

    # Khi nền dốc quá mạnh che mất vạch -> phải nêu đúng nguyên nhân nền không đều
    yy = np.linspace(10.0, 220.0, 300, dtype=np.float32)[:, None]
    anh_nen_doc = np.clip(np.broadcast_to(yy, (300, 400)), 0, 255).astype(np.uint8)
    with pytest.raises(KhongTimThayVachError) as exc_info:
        tu_dong_tim_roi_hai_vach(anh_nen_doc, nguong_nen_khong_deu=30.0)
    assert "nền sáng không đều" in str(exc_info.value).lower()




