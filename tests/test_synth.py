"""Unit tests & Test hồi quy cho Cột mốc 3: Bộ sinh ảnh mô phỏng & Thử nghiệm Monte Carlo (sim/synth.py)."""
from __future__ import annotations

import math
import numpy as np
import pytest

from core.measure import do_delta_y_tu_anh
from core.optics import CauHinhQuangHoc
from sim.synth import (
    ThamSoMoPhong,
    luu_anh_mo_phong_png,
    sinh_anh_hai_vach_mo_phong,
    sinh_anh_mau_mo_phong,
)


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


def test_cac_hieu_ung_nhieu_thuc_te_mac_dinh_tat_va_hoat_dong():
    """T9: Tham số mô phỏng mới mặc định tắt; khi bật sẽ biến đổi ảnh hợp lệ."""
    p_base = ThamSoMoPhong(S_ppt=15.0, T_C=25.0, seed=10)
    assert p_base.speckle_cuong_do == 0.0
    assert p_base.meo_ong_kinh_k1 == 0.0
    assert p_base.gradient_nen_y == 0.0
    assert p_base.do_cong_vach == 0.0
    assert p_base.chenh_sang_hai_nua == 0.0
    assert p_base.gamma_cam_bien == 1.0
    assert p_base.chat_luong_jpeg is None

    img_base = sinh_anh_hai_vach_mo_phong(p_base, cfg=CFG).anh
    hieu_ung = [
        ThamSoMoPhong(S_ppt=15.0, T_C=25.0, seed=10, speckle_cuong_do=0.15),
        ThamSoMoPhong(S_ppt=15.0, T_C=25.0, seed=10, meo_ong_kinh_k1=0.08),
        ThamSoMoPhong(S_ppt=15.0, T_C=25.0, seed=10, gradient_nen_y=40.0),
        ThamSoMoPhong(S_ppt=15.0, T_C=25.0, seed=10, do_cong_vach=1.5),
        ThamSoMoPhong(S_ppt=15.0, T_C=25.0, seed=10, chenh_sang_hai_nua=0.4),
        ThamSoMoPhong(S_ppt=15.0, T_C=25.0, seed=10, gamma_cam_bien=1.6),
        ThamSoMoPhong(S_ppt=15.0, T_C=25.0, seed=10, chat_luong_jpeg=60),
    ]
    for params in hieu_ung:
        mp = sinh_anh_hai_vach_mo_phong(params, cfg=CFG)
        assert mp.anh.shape == img_base.shape
        assert not np.array_equal(mp.anh, img_base)


def test_luu_anh_mo_phong_mac_dinh_watermark_va_json(tmp_path):
    """T9: Lưu ảnh mô phỏng mặc định bật watermark và luôn ghi file .json {"simulated": true}."""
    import json

    p = ThamSoMoPhong(S_ppt=12.0, T_C=25.0, seed=3)
    mp = sinh_anh_hai_vach_mo_phong(p, cfg=CFG, gan_watermark=False)
    assert mp.metadata["da_gan_watermark"] is False

    out_png = tmp_path / "mau_mo_phong.png"
    luu_anh_mo_phong_png(mp, out_png)
    assert out_png.exists()

    json_path = out_png.with_suffix(".json")
    assert json_path.exists()
    meta = json.loads(json_path.read_text(encoding="utf-8"))
    assert meta["simulated"] is True
    assert meta["NGUON"] == "SIMULATED"
    assert meta["da_gan_watermark"] is True

    # Kiểm tra ảnh đã lưu thực sự có pixel watermark ở vùng góc dưới khác ảnh gốc không watermark
    import cv2
    img_saved = cv2.imread(str(out_png), cv2.IMREAD_GRAYSCALE)
    assert not np.array_equal(img_saved[-30:, :220], mp.anh[-30:, :220])


def test_q1_anh_mau_laser_do_bao_hoa_kenh_r_va_snr():
    """Q1: Laser đỏ cháy kênh R (ảnh xám < 250) vẫn phải bật bão hòa kênh R; ảnh sạch SNR R >= xám và sai số <= 0.05 px."""
    # 1. Ảnh cháy kênh R nhưng G=B=0.20 nên ảnh xám < 250 (đỉnh xám ~ 115)
    p_chay = ThamSoMoPhong(S_ppt=18.0, T_C=25.0, cuong_do_dinh_goc=245.0, cuong_do_nen=15.0, seed=5)
    mp_chay = sinh_anh_mau_mo_phong(p_chay, cfg=CFG, ty_le_kenh=(1.0, 0.20, 0.20))
    import cv2
    anh_xam_mix = cv2.cvtColor(mp_chay.anh, cv2.COLOR_BGR2GRAY)
    assert int(anh_xam_mix.max()) < 250
    assert int(mp_chay.anh[:, :, 2].max()) >= 250

    kq_chay = do_delta_y_tu_anh(mp_chay.anh, x_ref=mp_chay.x_ref, kenh_laser="auto", tao_anh_ve=False)
    assert kq_chay.kenh_su_dung == "R"
    assert kq_chay.chat_luong.bao_hoa is True
    assert "R" in kq_chay.chat_luong.kenh_bao_hoa

    # 2. Ảnh màu sạch không cháy: SNR kênh R >= SNR khi trộn ảnh xám, sai số Δy <= 0.05 px
    p_sach = ThamSoMoPhong(S_ppt=20.0, T_C=25.0, cuong_do_dinh_goc=180.0, cuong_do_nen=15.0, seed=11)
    mp_sach = sinh_anh_mau_mo_phong(p_sach, cfg=CFG, ty_le_kenh=(1.0, 0.35, 0.35))
    kq_auto = do_delta_y_tu_anh(mp_sach.anh, x_ref=mp_sach.x_ref, kenh_laser="auto", tao_anh_ve=False)
    kq_xam = do_delta_y_tu_anh(mp_sach.anh, x_ref=mp_sach.x_ref, kenh_laser="xam", tao_anh_ve=False)
    assert kq_auto.kenh_su_dung == "R"
    assert kq_auto.chat_luong.hop_le is True
    assert kq_auto.chat_luong.snr >= kq_xam.chat_luong.snr
    assert abs(kq_auto.delta_y_px - mp_sach.delta_y_ly_thuyet_px) <= 0.05

    # 3. Ảnh xám 2D cho kết quả hồi quy y hệt trước
    mp_2d = sinh_anh_hai_vach_mo_phong(p_sach, cfg=CFG)
    kq_2d = do_delta_y_tu_anh(mp_2d.anh, x_ref=mp_2d.x_ref, tao_anh_ve=False)
    assert kq_2d.kenh_su_dung == "xam_2d"
    assert abs(kq_2d.delta_y_px - mp_2d.delta_y_ly_thuyet_px) <= 0.05


def test_q2_phan_biet_speckle_va_bao_hoa_that():
    """Q2: Đốm speckle (0.1 và 0.2, 10 seed/mức) phải >=90% hợp lệ đồng thời |sai số| <0.15 px; clipping thật phải bị loại."""
    for spk in (0.1, 0.2):
        dat_ca_hai = 0
        errs = []
        for s in range(10):
            p = ThamSoMoPhong(S_ppt=20.0, T_C=25.0, speckle_cuong_do=spk, seed=s)
            mp = sinh_anh_hai_vach_mo_phong(p, cfg=CFG)
            kq = do_delta_y_tu_anh(mp.anh, x_ref=mp.x_ref, tao_anh_ve=False)
            err = abs(kq.delta_y_px - mp.delta_y_ly_thuyet_px)
            errs.append(err)
            if kq.chat_luong.hop_le and err < 0.15:
                dat_ca_hai += 1
        rms = float(np.sqrt(np.mean(np.square(errs))))
        assert dat_ca_hai >= 9, f"Speckle {spk}: chỉ {dat_ca_hai}/10 đạt đồng thời hop_le và |err|<0.15 px"
        assert rms < 0.10, f"Speckle {spk}: RMS {rms:.4f} >= 0.10 px"

    # Kiểm tra ảnh có bẹt đỉnh thực sự: cho_phep_bao_hoa=True, đỉnh 400 -> bao_hoa=True, hop_le=False
    p_clip = ThamSoMoPhong(S_ppt=20.0, T_C=25.0, cho_phep_bao_hoa=True, cuong_do_dinh_goc=400.0, seed=1)
    mp_clip = sinh_anh_hai_vach_mo_phong(p_clip, cfg=CFG)
    kq_clip = do_delta_y_tu_anh(mp_clip.anh, x_ref=mp_clip.x_ref, tao_anh_ve=False)
    assert kq_clip.chat_luong.bao_hoa is True
    assert kq_clip.chat_luong.hop_le is False
    assert kq_clip.chat_luong.so_cot_bao_hoa_lien_tiep_max >= 15
    assert any(c["ma"] == "BAO_HOA_NGHIEM_TRONG" and c["cap"] == "nghiem_trong" for c in kq_clip.chat_luong.canh_bao_chi_tiet)


def test_q3_nen_sang_khong_deu_gradient_40_va_90():
    """Q3: Với gradient_nen_y = 40 và 90 (10 seed/mức), phải đo đúng (<0.2 px) hoặc báo đúng nguyên nhân nen_khong_deu."""
    for grad in (40.0, 90.0):
        for s in range(10):
            p = ThamSoMoPhong(S_ppt=20.0, T_C=25.0, gradient_nen_y=grad, seed=200 + s)
            mp = sinh_anh_hai_vach_mo_phong(p, cfg=CFG)
            kq = do_delta_y_tu_anh(mp.anh, x_ref=mp.x_ref, tao_anh_ve=False)
            sai_so = abs(kq.delta_y_px - mp.delta_y_ly_thuyet_px)
            assert kq.chat_luong.nen_khong_deu is True
            assert any(
                c["ma"] == "NEN_KHONG_DEU" and "nền sáng không đều" in c["noi_dung"].lower()
                for c in kq.chat_luong.canh_bao_chi_tiet
            )
            assert sai_so < 0.2, f"grad={grad}, seed={s}: sai số lớn {sai_so:.3f} px"


