"""Unit tests & Test hồi quy cho Cột mốc 3: Bộ sinh ảnh mô phỏng & Thử nghiệm Monte Carlo (sim/synth.py)."""
from __future__ import annotations

import math
import numpy as np
import pytest

from core.measure import do_delta_y_tu_anh
from core.optics import CauHinhQuangHoc
from sim.synth import ThamSoMoPhong, sinh_anh_hai_vach_mo_phong


CFG = CauHinhQuangHoc.tu_yaml()


def test_anh_mo_phong_co_nhan_simulated():
    """Kiểm tra ảnh mô phỏng bắt buộc phải mang nhãn SIMULATED trong metadata và watermark."""
    p = ThamSoMoPhong(S_ppt=10.0, T_C=20.0, seed=1)
    anh_mp = sinh_anh_hai_vach_mo_phong(p, cfg=CFG, gan_watermark=True)

    assert anh_mp.metadata.get("NGUON") == "SIMULATED"
    assert "KHÔNG phải số đo thực tế" in anh_mp.metadata.get("CANH_BAO", "")
    assert anh_mp.anh.dtype == np.uint8
    assert anh_mp.anh.shape == (p.chieu_cao, p.chieu_rong)


@pytest.mark.parametrize("S_test", [0.0, 5.0, 15.0, 25.0, 35.0])
def test_delta_y_mo_phong_khop_ly_thuyet_snell(S_test: float):
    """Kiểm tra hồi quy: Δy đo được trên ảnh mô phỏng phải khớp giá trị lí thuyết Snell (< 0.1 px)."""
    p = ThamSoMoPhong(
        S_ppt=S_test,
        T_C=25.0,
        T_tham_chieu_C=25.0,
        drift_chung_px=0.0,
        do_duc=0.0,
        cuong_do_nen=15.0,
        he_so_poisson=0.3,
        sigma_nhieu_doc=1.5,
        seed=100 + int(S_test * 10),
    )
    anh_mp = sinh_anh_hai_vach_mo_phong(p, cfg=CFG)

    # Đo bằng thuật toán đo vi sai Cột mốc 2
    kq = do_delta_y_tu_anh(anh_mp.anh, x_ref=anh_mp.x_ref)

    assert kq.chat_luong.hop_le is True
    sai_so_px = abs(kq.delta_y_px - anh_mp.delta_y_ly_thuyet_px)

    # Tiêu chí nghiệm thu bắt buộc: sai số < 0.1 pixel
    assert sai_so_px < 0.1, (
        f"Tại S={S_test}‰: Δy đo={kq.delta_y_px:.4f} px, "
        f"Δy lý thuyết={anh_mp.delta_y_ly_thuyet_px:.4f} px (sai lệch {sai_so_px:.4f} px > 0.1 px)"
    )


def test_dich_chuyen_chung_khong_lam_doi_delta_y():
    """Kiểm tra tính bất biến của phép đo vi sai: Rung động / trôi laser chung không làm đổi Δy."""
    S_chuan = 20.0
    drifts = [-15.0, -8.0, 0.0, 7.5, 14.0]
    ket_qua_do = []

    for d in drifts:
        p = ThamSoMoPhong(
            S_ppt=S_chuan,
            T_C=25.0,
            drift_chung_px=d,
            cuong_do_nen=15.0,
            he_so_poisson=0.3,
            sigma_nhieu_doc=1.5,
            seed=int(abs(d) * 10 + 7),
        )
        anh_mp = sinh_anh_hai_vach_mo_phong(p, cfg=CFG)
        kq = do_delta_y_tu_anh(anh_mp.anh, x_ref=anh_mp.x_ref)
        ket_qua_do.append(kq.delta_y_px)

    do_lech_max = max(ket_qua_do) - min(ket_qua_do)
    assert do_lech_max < 0.08, (
        f"Đo vi sai không triệt tiêu rung trôi: độ phân tán {do_lech_max:.4f} px > 0.08 px"
    )


def test_anh_huong_do_duc_len_fwhm_va_chi_so():
    """Kiểm tra khi nước đục, vạch mẫu mở rộng FWHM và chỉ số độ đục tăng tương ứng."""
    p_trong = ThamSoMoPhong(S_ppt=15.0, do_duc=0.0, seed=42)
    anh_trong = sinh_anh_hai_vach_mo_phong(p_trong, cfg=CFG)
    kq_trong = do_delta_y_tu_anh(anh_trong.anh, x_ref=anh_trong.x_ref)

    p_duc = ThamSoMoPhong(S_ppt=15.0, do_duc=0.6, seed=42)
    anh_duc = sinh_anh_hai_vach_mo_phong(p_duc, cfg=CFG)
    kq_duc = do_delta_y_tu_anh(anh_duc.anh, x_ref=anh_duc.x_ref)

    assert kq_duc.vach_mau.fwhm_trung_binh > kq_trong.vach_mau.fwhm_trung_binh * 1.5
    assert kq_duc.chi_so_do_duc_tuong_doi > 0.4
    assert kq_trong.chi_so_do_duc_tuong_doi < 0.1


def test_do_lap_lai_monte_carlo_100_anh():
    """Thử nghiệm Monte Carlo trên 100 ảnh nhiễu độc lập để đánh giá độ lặp lại và sai số chuẩn.

    Tiêu chí nghiệm thu:
    - RMSE < 0.05 px
    - Sai số cực đại < 0.1 px
    - 100% các phép đo đều hợp lệ
    """
    N = 100
    S_muc_tieu = 18.0
    T_muc_tieu = 26.0

    p_base = ThamSoMoPhong(
        S_ppt=S_muc_tieu,
        T_C=T_muc_tieu,
        he_so_poisson=0.4,
        sigma_nhieu_doc=1.5,
        cuong_do_nen=15.0,
    )
    mau_chuan = sinh_anh_hai_vach_mo_phong(p_base, cfg=CFG)
    delta_y_true = mau_chuan.delta_y_ly_thuyet_px

    # Cố định ROI hai vạch để tối ưu tốc độ đo hàng loạt trong Monte Carlo
    roi_tc = (50, 130, 20, 180)
    roi_mau = (140, 230, 220, 380)

    sai_so_list = []
    dy_list = []

    for i in range(N):
        p = ThamSoMoPhong(
            S_ppt=S_muc_tieu,
            T_C=T_muc_tieu,
            he_so_poisson=0.4,
            sigma_nhieu_doc=1.5,
            cuong_do_nen=15.0,
            seed=2000 + i,
        )
        anh_mp = sinh_anh_hai_vach_mo_phong(p, cfg=CFG)
        kq = do_delta_y_tu_anh(
            anh_mp.anh,
            roi_tham_chieu=roi_tc,
            roi_mau=roi_mau,
            x_ref=anh_mp.x_ref,
            tao_anh_ve=False,
        )

        assert kq.chat_luong.hop_le is True
        error = kq.delta_y_px - delta_y_true
        sai_so_list.append(error)
        dy_list.append(kq.delta_y_px)

    errors = np.array(sai_so_list)
    mean_err = float(np.mean(errors))
    std_err = float(np.std(errors))
    rmse = float(np.sqrt(np.mean(errors**2)))
    max_err = float(np.max(np.abs(errors)))

    print("\n" + "=" * 65)
    print("BẢNG THỐNG KÊ ĐỘ LẶP LẠI PHÉP ĐO MONTE CARLO (N = 100 ẢNH)")
    print("=" * 65)
    print(f"Δy chân lí mặt đất (Snell) : {delta_y_true:.4f} pixel")
    print(f"Δy trung bình đo được       : {np.mean(dy_list):.4f} pixel")
    print(f"Sai số trung bình (Bias)    : {mean_err:+.4f} pixel")
    print(f"Độ lệch chuẩn (Std Dev, σ)  : {std_err:.4f} pixel")
    print(f"Căn quân phương sai số RMSE : {rmse:.4f} pixel")
    print(f"Sai số tuyệt đối cực đại    : {max_err:.4f} pixel")
    print("=" * 65)

    assert rmse < 0.05, f"RMSE {rmse:.4f} px vượt quá 0.05 px"
    assert max_err < 0.10, f"Sai số cực đại {max_err:.4f} px vượt quá 0.10 px"
