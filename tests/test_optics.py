"""Test Cột mốc 1: mô hình quang học."""
import math
import warnings

import pytest

from core import optics as op

CFG = op.CauHinhQuangHoc.tu_yaml()


def test_truong_hop_da_biet():
    """A = 40°, n = 1,333 => θ_ra ≈ 59,0°, δ ≈ 19,0° (sin40°·1,333 = 0,8569)."""
    assert op.goc_ra(1.333, 40.0) == pytest.approx(58.97, abs=0.05)
    assert op.goc_lech(1.333, 40.0) == pytest.approx(18.97, abs=0.05)


def test_n_bang_1_khong_lech():
    assert op.goc_lech(1.0, 40.0) == pytest.approx(0.0, abs=1e-9)


def test_phan_xa_toan_phan_bao_loi():
    with pytest.raises(op.PhanXaToanPhanError):
        op.goc_ra(1.333, 50.0)  # 1,333·sin50° = 1,021 > 1


def test_gan_phan_xa_toan_phan_canh_bao():
    A = math.degrees(math.asin(0.99 / 1.333))  # n·sinA = 0,99
    with pytest.warns(op.GanPhanXaToanPhanWarning):
        op.goc_ra(1.333, A)


def test_khong_canh_bao_o_cau_hinh_thuong():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        op.goc_ra(1.333, 40.0)


def test_dao_ham_khop_sai_phan():
    n, A, h = 1.34, 40.0, 1e-6
    sai_phan = (math.radians(op.goc_lech(n + h, A)) - math.radians(op.goc_lech(n - h, A))) / (2 * h)
    assert op.do_nhay_goc_theo_n(n, A) == pytest.approx(sai_phan, rel=1e-5)


def test_dich_chuyen_man():
    delta = math.radians(op.goc_lech(1.333, 40.0))
    assert op.dich_chuyen_man_mm(1.333, 40.0, 1.0) == pytest.approx(1000 * math.tan(delta))


def test_vi_sai_bang_0_khi_nuoc_cat_cung_nhiet_do():
    assert op.delta_y_vi_sai_mm(0.0, 20.0, 20.0, CFG) == pytest.approx(0.0, abs=1e-9)


def test_vi_sai_tang_theo_do_man():
    y = [op.delta_y_vi_sai_px(s, 20.0, 20.0, CFG) for s in (0, 10, 20, 35)]
    assert y == sorted(y) and y[-1] > 0


def test_pixel_moi_phan_nghin_khop_sai_phan_huu_han():
    h = 0.01
    y1 = op.delta_y_vi_sai_px(10 + h, 20.0, 20.0, CFG)
    y0 = op.delta_y_vi_sai_px(10 - h, 20.0, 20.0, CFG)
    assert op.pixel_moi_phan_nghin(10.0, 20.0, CFG) == pytest.approx((y1 - y0) / (2 * h), rel=1e-4)


def test_do_nhay_ti_le_thuan_voi_D():
    a = op.pixel_moi_phan_nghin(10, 20, CFG, D_m=1.0)
    b = op.pixel_moi_phan_nghin(10, 20, CFG, D_m=2.0)
    assert b == pytest.approx(2 * a, rel=1e-9)


def test_do_nhay_tang_theo_A():
    assert op.pixel_moi_phan_nghin(10, 20, CFG, A_do=45) > op.pixel_moi_phan_nghin(10, 20, CFG, A_do=30)


def test_nhiet_do_lam_lech_chiet_suat_dung_dau():
    assert op.chiet_suat(0, 30, CFG) < op.chiet_suat(0, 20, CFG)  # dn/dT < 0


def test_ngan_sach_sai_so():
    r = op.ngan_sach_sai_so(17.5, 20.0, CFG, 0.05, 0.5, 0.05, 5.0, 0.01)
    assert set(r) == {"tim_tam", "nhiet_do", "goc_A", "troi_laser", "tong_RSS"}
    assert all(v >= 0 for v in r.values())
    # ΔT = 0,5 °C => |dn/dT|·ΔT/(dn/dS) = 1.1e-4·0,5/1,8e-4 ≈ 0,3056 ‰ (xấp xỉ tại 650 nm, 25 °C)
    assert r["nhiet_do"] == pytest.approx(0.5 * 1.1e-4 / 1.8e-4, rel=1e-9)
    assert r["tong_RSS"] >= max(v for k, v in r.items() if k != "tong_RSS")


def test_quan_fry_kiem_tinh_hop_li_va_canh_bao():
    """T10: Kiểm tính hợp lí sơ bộ (KHÔNG phải kiểm chuẩn với bài báo gốc 1995)."""
    from dataclasses import replace

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        n_ref = op.chiet_suat_quan_fry(S_ppt=0.0, T_C=20.0, buoc_song_nm=589.0)
    assert abs(n_ref - 1.3330) < 3e-4

    h = 0.01
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        dn_dS_num = (
            op.chiet_suat_quan_fry(15.0 + h, 25.0, 650.0)
            - op.chiet_suat_quan_fry(15.0 - h, 25.0, 650.0)
        ) / (2.0 * h)
    assert dn_dS_num == pytest.approx(1.79e-4, rel=0.05)

    # Cảnh báo ngoài dải hiệu lực Quan–Fry
    for kw in ({"T_C": 35.0}, {"S_ppt": 40.0}, {"buoc_song_nm": 750.0}):
        params = {"S_ppt": 15.0, "T_C": 25.0, "buoc_song_nm": 650.0, **kw}
        with pytest.warns(op.NgoaiDaiQuanFryWarning):
            op.chiet_suat_quan_fry(**params)

    # Kiểm tra dispatch theo cấu hình mo_hinh_chiet_suat="quan_fry"
    cfg_qf = replace(CFG, mo_hinh_chiet_suat="quan_fry", buoc_song_nm=650.0)
    hs = 0.01
    y1 = op.delta_y_vi_sai_px(15.0 + hs, 25.0, 25.0, cfg_qf)
    y0 = op.delta_y_vi_sai_px(15.0 - hs, 25.0, 25.0, cfg_qf)
    assert op.pixel_moi_phan_nghin(15.0, 25.0, cfg_qf) == pytest.approx((y1 - y0) / (2.0 * hs), rel=1e-4)


def test_r4_khoa_nhiet_do_chuan_chiet_suat_va_alias_cu(tmp_path, caplog):
    """R4: config.yaml dùng nhiet_do_chuan_chiet_suat_C; YAML cũ dùng nhiet_do_tham_chieu_C vẫn chạy kèm cảnh báo."""
    import logging
    from pathlib import Path
    import yaml

    raw = yaml.safe_load(Path(op.CONFIG_MAC_DINH).read_text(encoding="utf-8"))
    q = raw["quang_hoc"]
    assert "nhiet_do_chuan_chiet_suat_C" in q
    assert "nhiet_do_tham_chieu_C" not in q

    cfg_cur = op.CauHinhQuangHoc.tu_yaml()
    assert cfg_cur.T_chuan_chiet_suat_C == cfg_cur.T_tham_chieu_C

    old_yaml = tmp_path / "old_config.yaml"
    q_old = dict(q)
    q_old["nhiet_do_tham_chieu_C"] = 22.5
    q_old.pop("nhiet_do_chuan_chiet_suat_C", None)
    old_yaml.write_text(
        yaml.safe_dump({"quang_hoc": q_old, "anh": raw["anh"]}, allow_unicode=True),
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING):
        with pytest.warns(DeprecationWarning, match="nhiet_do_chuan_chiet_suat_C"):
            cfg_old = op.CauHinhQuangHoc.tu_yaml(old_yaml)
    assert cfg_old.T_chuan_chiet_suat_C == pytest.approx(22.5)
    assert cfg_old.T_tham_chieu_C == pytest.approx(22.5)
    assert any("nhiet_do_tham_chieu_C" in rec.message for rec in caplog.records)

