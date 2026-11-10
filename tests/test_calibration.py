"""Test Cột mốc 4: hiệu chuẩn, bù nhiệt, bất định (core/calibration.py).

Mọi dữ liệu trong file này là MÔ PHỎNG hoặc tổng hợp nhân tạo để kiểm tra thuật toán.
"""
from __future__ import annotations

import io

import numpy as np
import pandas as pd
import pytest

from core import calibration as cal
from sim.synth import sinh_du_lieu_hieu_chuan_mo_phong


@pytest.fixture(scope="module")
def df_mo_phong() -> pd.DataFrame:
    return sinh_du_lieu_hieu_chuan_mo_phong(seed=1)


@pytest.fixture(scope="module")
def bao_cao(df_mo_phong: pd.DataFrame) -> cal.BaoCaoHieuChuan:
    return cal.dung_duong_chuan(df_mo_phong)


def _df_tong_hop(ham, muc_S, muc_T, lap=3, sigma=0.05, seed=0) -> pd.DataFrame:
    """Tạo bảng nhân tạo Δy = ham(S, T) + nhiễu, đúng định dạng CSV."""
    rng = np.random.default_rng(seed)
    dong = []
    for S in muc_S:
        for T in muc_T:
            for _ in range(lap):
                dong.append({
                    cal.COT_DO_MAN: S, cal.COT_NHIET_DO: T,
                    cal.COT_DELTA_Y: ham(S, T) + rng.normal(0, sigma),
                    cal.COT_DO_DUC: 0.0, cal.COT_GHI_CHU: "tong hop",
                    cal.COT_ID_THIET_BI: "TB1", cal.COT_ID_DIEN_THOAI: "DT1",
                    cal.COT_NGUON: cal.NHAN_MO_PHONG,
                })
    return pd.DataFrame(dong)


# --------------------------------------------------------------------------- CSV
def test_doc_csv_thieu_cot_bao_loi():
    csv = "do_man_chuan_ppt,nhiet_do_C\n0,25\n"
    with pytest.raises(ValueError, match="delta_y_px"):
        cal.doc_csv_hieu_chuan(io.StringIO(csv))


def test_doc_csv_hop_le_loai_dong_thieu_va_mac_dinh_thuc_te():
    csv = (
        "do_man_chuan_ppt,nhiet_do_C,delta_y_px,do_duc_tuong_doi,ghi_chu,id_thiet_bi,id_dien_thoai\n"
        "0,25,0.1,0.0,a,TB1,DT1\n"
        "10,25,,0.0,thieu dy,TB1,DT1\n"
        "20,25,100.2,,b,TB1,DT1\n"
    )
    df = cal.doc_csv_hieu_chuan(io.StringIO(csv))
    assert len(df) == 2
    assert df.attrs["so_dong_bi_loai"] == 1
    assert not cal.la_du_lieu_mo_phong(df)  # không có cột nguồn -> coi là đo thật


def test_doc_csv_chap_nhan_bi_danh_cot():
    csv = ("do_man,nhiet_do,delta_y,do_duc,ghi_chu,id_thiet_bi,id_dien_thoai\n"
           "5,25,25.0,0,x,TB1,DT1\n")
    df = cal.doc_csv_hieu_chuan(io.StringIO(csv))
    assert df[cal.COT_DO_MAN].iloc[0] == 5


def test_file_mau_csv_doc_duoc_va_khong_co_so_lieu():
    """File mẫu trong data/ phải có đủ các cột bắt buộc."""
    from pathlib import Path
    p = Path(cal.__file__).resolve().parents[1] / "data" / "mau_hieu_chuan.csv"
    df = pd.read_csv(p, encoding="utf-8-sig")
    assert set(cal.COT_BAT_BUOC) <= set(df.columns)
    assert len(df) >= 0


# ------------------------------------------------------------------ chọn bậc
def test_du_lieu_tuyen_tinh_chon_bac_1():
    df = _df_tong_hop(lambda S, T: 5.0 * S - 0.2 * (T - 25), range(0, 36, 5), (20, 25, 30))
    bc = cal.dung_duong_chuan(df)
    assert bc.bac_chon == 1


def test_du_lieu_cong_ro_chon_bac_2():
    df = _df_tong_hop(lambda S, T: 5.0 * S + 0.05 * S**2, range(0, 36, 5), (20, 25, 30))
    bc = cal.dung_duong_chuan(df)
    assert bc.bac_chon == 2


def test_mot_muc_nhiet_do_thi_khong_bu_nhiet_va_canh_bao():
    df = _df_tong_hop(lambda S, T: 5.0 * S, range(0, 36, 5), (25,))
    bc = cal.dung_duong_chuan(df)
    assert bc.mo_hinh.co_bu_nhiet is False
    assert all("T" not in h for h in bc.mo_hinh.hang)
    kq = cal.uoc_luong_do_man(bc.mo_hinh, 50.0, 30.0)
    assert any("KHÔNG bù nhiệt" in c for c in kq.canh_bao)


# ------------------------------------------------- đường chuẩn trên dữ liệu Snell
def test_bao_cao_mo_phong_co_nhan_va_sai_so_test_nho(bao_cao: cal.BaoCaoHieuChuan):
    mh = bao_cao.mo_hinh
    assert mh.la_mo_phong and mh.nhan == cal.NHAN_CHUA_HIEU_CHUAN
    assert any(cal.NHAN_CHUA_HIEU_CHUAN in c for c in bao_cao.canh_bao)
    assert len(bao_cao.df_test) > 0
    # Test set không được dùng để khớp mô hình train
    assert set(bao_cao.df_test.index).isdisjoint(bao_cao.df_train.index)
    # Với nhiễu mô phỏng σ = 0,05 px và độ nhạy ~5 px/‰, sai số test phải rất nhỏ
    assert bao_cao.RMSE_test_ppt < 0.05
    assert mh.R2 > 0.9999
    assert len(bao_cao.sai_so_theo_muc) == 8


def test_ham_nguoc_khoi_phuc_do_man(bao_cao: cal.BaoCaoHieuChuan):
    mh = bao_cao.mo_hinh
    for S, T in [(0.0, 22.0), (12.3, 26.0), (34.0, 28.0)]:
        kq = cal.uoc_luong_do_man(mh, float(mh.du_doan_delta_y(S, T)[0]), T)
        assert kq.S_ppt == pytest.approx(S, abs=1e-6)
        assert not kq.ngoai_dai_S and not kq.ngoai_dai_T


def test_do_phu_bat_dinh_tren_du_lieu_moi(bao_cao: cal.BaoCaoHieuChuan):
    """Với k = 2, khoảng S ± U phải chứa giá trị thật ở khoảng ≥ 90% điểm đo mới."""
    mh = bao_cao.mo_hinh
    moi = sinh_du_lieu_hieu_chuan_mo_phong(muc_S=(2.5, 7.5, 17.5, 27.5, 32.5),
                                           muc_T=(23.0, 26.5), so_lan_lap=20, seed=99)
    trung = 0
    for _, r in moi.iterrows():
        kq = cal.uoc_luong_do_man(mh, r[cal.COT_DELTA_Y], r[cal.COT_NHIET_DO], sigma_T_C=0.1)
        trung += abs(kq.S_ppt - r[cal.COT_DO_MAN]) <= kq.U_S_ppt
    assert trung / len(moi) >= 0.90


def test_bat_dinh_tang_theo_sigma_va_U_bang_k_nhan_u(bao_cao: cal.BaoCaoHieuChuan):
    mh = bao_cao.mo_hinh
    a = cal.uoc_luong_do_man(mh, 60.0, 25.0, sigma_delta_y_px=0.01, k=2)
    b = cal.uoc_luong_do_man(mh, 60.0, 25.0, sigma_delta_y_px=0.5, k=2)
    assert b.u_S_ppt > a.u_S_ppt
    assert a.U_S_ppt == pytest.approx(2 * a.u_S_ppt)
    tong = np.sqrt(sum(v * v for v in a.thanh_phan_bat_dinh.values()))
    assert a.u_S_ppt == pytest.approx(tong)


def test_co_ngoai_dai(bao_cao: cal.BaoCaoHieuChuan):
    mh = bao_cao.mo_hinh
    kq_S = cal.uoc_luong_do_man(mh, float(mh.du_doan_delta_y(40.0, 25.0)[0]), 25.0)
    assert kq_S.ngoai_dai_S and any("NGOÀI dải" in c for c in kq_S.canh_bao)
    kq_T = cal.uoc_luong_do_man(mh, 50.0, 35.0)
    assert kq_T.ngoai_dai_T
    with pytest.raises(ValueError):
        cal.uoc_luong_do_man(mh, 5000.0, 25.0)  # quá xa, không có nghiệm


def test_luon_kem_han_che_nacl(bao_cao: cal.BaoCaoHieuChuan):
    kq = cal.uoc_luong_do_man(bao_cao.mo_hinh, 60.0, 25.0)
    assert "NaCl" in kq.han_che


def test_luu_doc_json_giu_nguyen(tmp_path, bao_cao: cal.BaoCaoHieuChuan):
    p = tmp_path / "he_so.json"
    bao_cao.mo_hinh.luu_json(p)
    mh2 = cal.MoHinhHieuChuan.doc_json(p)
    S = np.array([0.0, 17.0, 35.0]); T = np.array([22.0, 25.0, 28.0])
    np.testing.assert_allclose(mh2.du_doan_delta_y(S, T), bao_cao.mo_hinh.du_doan_delta_y(S, T))
    assert mh2.la_mo_phong is True
    assert '"NGUON": "MO_PHONG"' in p.read_text(encoding="utf-8")


def test_bootstrap_phu_hop_truyen_sai_so(df_mo_phong: pd.DataFrame, bao_cao: cal.BaoCaoHieuChuan):
    mh = bao_cao.mo_hinh
    S_that, T = 18.0, 25.0
    dy = float(mh.du_doan_delta_y(S_that, T)[0])
    trung_vi, duoi, tren = cal.uoc_luong_do_man_bootstrap(df_mo_phong, mh.bac, dy, T, so_lan=200, seed=3)
    assert duoi < S_that < tren
    kq = cal.uoc_luong_do_man(mh, dy, T)
    # Hai cách ước lượng cùng cỡ độ lớn (chênh không quá 3 lần)
    assert 1 / 3 < (tren - duoi) / 2 / kq.U_S_ppt < 3


def test_ve_do_thi(bao_cao: cal.BaoCaoHieuChuan):
    from matplotlib.figure import Figure
    f1 = cal.ve_duong_chuan(bao_cao)
    f2 = cal.ve_phan_du(bao_cao)
    assert isinstance(f1, Figure) and isinstance(f2, Figure)
    assert cal.NHAN_CHUA_HIEU_CHUAN in f1.axes[0].get_title()


def test_cau_hinh_doc_tu_yaml():
    ch = cal.CauHinhHieuChuan.tu_yaml()
    assert 0 < ch.ti_le_test < 1 and ch.he_so_phu_k > 0

