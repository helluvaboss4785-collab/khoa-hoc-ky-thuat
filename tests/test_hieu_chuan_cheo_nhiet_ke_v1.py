"""Kiểm thử V1: hiệu chuẩn chéo hai nhiệt kế, áp dụng vào uoc_luong_do_man, CSV hiệu chuẩn và web API."""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import web_app
from core import calibration as cal
from core import nhiet_ke, optics as op
from sim.synth import ThamSoMoPhong, sinh_anh_hai_vach_mo_phong, sinh_du_lieu_hieu_chuan_mo_phong
from tests.test_web_app import _make_request, _run_coro


def _tao_bang_nhiet_ke_mo_phong(
    offset_that: float,
    slope_that: float = 0.0,
    sigma_nhieu: float = 0.05,
    muc_T: tuple[float, ...] = (15.0, 22.0, 29.0, 36.0),
    lap: int = 3,
    seed: int = 101,
) -> pd.DataFrame:
    """Sinh cặp số đọc mô phỏng khi nhúng 2 nhiệt kế vào cùng cốc nước khuấy đều."""
    rng = np.random.default_rng(seed)
    rows = []
    for t_true in muc_T:
        for _ in range(lap):
            t_m_doc = float(t_true + rng.normal(0.0, sigma_nhieu))
            off_true = offset_that + slope_that * t_true
            t_tc_doc = float(t_true + off_true + rng.normal(0.0, sigma_nhieu))
            rows.append({
                nhiet_ke.COT_T_MAU_DOC: t_m_doc,
                nhiet_ke.COT_T_TC_DOC: t_tc_doc,
                nhiet_ke.COT_T_CHUAN: float(t_true),
                nhiet_ke.COT_NGUON_NK: "MO_PHONG",
                nhiet_ke.COT_GHI_CHU_NK: "du_lieu_mo_phong_kiem_V1",
            })
    return pd.DataFrame(rows)


def _chay_mc_v1(
    mh: cal.MoHinhHieuChuan,
    cfg: op.CauHinhQuangHoc,
    offset_that: float,
    hc_nk: nhiet_ke.HieuChuanCheoNhietKe | None,
    n_mau: int = 400,
    seed: int = 4101,
    d_max: float = 0.3,
    sigma_T: float = 0.1,
) -> tuple[float, float, float]:
    """Chạy Monte Carlo >= 400 phép đo (D thật ~ U[-0.3, 0.3], nhiễu nhiệt kế 0.1 °C)."""
    rng = np.random.default_rng(seed)
    errs: list[float] = []
    cov_ok = 0
    n_ok = 0
    n_blocked = 0
    for _ in range(n_mau):
        s_t = float(rng.uniform(2.0, 33.0))
        t_m_true = float(rng.uniform(20.0, 30.0))
        d_true = float(rng.uniform(-d_max, d_max))
        t_tc_true = t_m_true - d_true
        dy_meas = op.delta_y_vi_sai_px(s_t, t_m_true, t_tc_true, cfg) + float(rng.normal(0.0, 0.05))
        t_m_meas = t_m_true + float(rng.normal(0.0, sigma_T))
        t_tc_meas = t_tc_true + offset_that + float(rng.normal(0.0, sigma_T))

        off_c = sig_off = None
        if hc_nk is not None:
            off_c, sig_off = hc_nk.offset_va_sigma_tai(t_m_meas)

        kq = cal.uoc_luong_do_man(
            mh=mh,
            delta_y_px=dy_meas,
            T_C=t_m_meas,
            sigma_delta_y_px=0.05,
            sigma_T_C=sigma_T,
            T_tham_chieu_C=t_tc_meas,
            sigma_T_tham_chieu_C=sigma_T,
            nguong_lech_T_hai_ngan_C=0.5,
            offset_nhiet_ke_C=off_c,
            sigma_offset_nhiet_ke_C=sig_off,
        )
        errs.append(kq.S_ppt - s_t)
        if kq.chenh_T_ngoai_mo_hinh or kq.ngoai_dai_S or kq.ngoai_dai_T:
            n_blocked += 1
        else:
            n_ok += 1
            if abs(kq.S_ppt - s_t) <= kq.U_S_ppt:
                cov_ok += 1

    cov = (cov_ok / n_ok) if n_ok > 0 else 1.0
    p_blocked = n_blocked / float(n_mau)
    rms = float(np.sqrt(np.mean(np.square(errs))))
    return cov, p_blocked, rms


def test_v1_hieu_chuan_cheo_offset_co_dinh_va_tuyen_tinh():
    """V1: kiểm ước lượng offset (+0.5, +1.0 °C) và hồi quy tuyến tính phụ thuộc nhiệt độ (0.02 °C/°C) trên >= 400 mẫu."""
    assert not nhiet_ke.FILE_HIEU_CHUAN_NHIET_KE_MAC_DINH.exists(), "Không được tạo sẵn data/hieu_chuan_nhiet_ke.json"

    cfg = op.CauHinhQuangHoc.tu_yaml()
    df_cb = sinh_du_lieu_hieu_chuan_mo_phong(cfg=cfg, T_tham_chieu_C=None, sigma_delta_y_px=0.05, sigma_nhiet_ke_C=0.0, seed=7)
    mh_no_d = cal.dung_duong_chuan(df_cb, bac_ep=1).mo_hinh

    # Cơ sở offset = 0
    cov_0, blk_0, rms_0 = _chay_mc_v1(mh_no_d, cfg, offset_that=0.0, hc_nk=None, n_mau=400, seed=4100)
    assert cov_0 >= 0.95

    for idx, off_true in enumerate((0.5, 1.0)):
        df_pairs = _tao_bang_nhiet_ke_mo_phong(offset_that=off_true, slope_that=0.0, sigma_nhieu=0.05, seed=200 + idx)
        hc = nhiet_ke.hieu_chuan_cheo_tu_df(df_pairs, nguoi_thuc_hien="Hoc Sinh A", nguon_du_lieu="MO_PHONG")
        assert abs(hc.offset_C - off_true) <= 0.1

        # Trước khi hiệu chuẩn chéo -> bị chặn hàng loạt
        _, blk_truoc, _ = _chay_mc_v1(mh_no_d, cfg, offset_that=off_true, hc_nk=None, n_mau=400, seed=4110 + idx)
        assert blk_truoc > 0.40

        # Sau khi áp offset -> cov >= 95%, tỉ lệ bị chặn <= blk_0 + 5pp, RMS <= 1.3 * rms_0
        cov_sau, blk_sau, rms_sau = _chay_mc_v1(mh_no_d, cfg, offset_that=off_true, hc_nk=hc, n_mau=400, seed=4120 + idx)
        assert cov_sau >= 0.95
        assert blk_sau <= blk_0 + 0.05
        assert rms_sau <= 1.3 * rms_0

    # Offset phụ thuộc nhiệt độ (b = 0.02 °C/°C) -> bật cờ phu_thuoc_nhiet_do và sai số dư <= 0.1 °C
    df_slope = _tao_bang_nhiet_ke_mo_phong(offset_that=-0.2, slope_that=0.02, sigma_nhieu=0.02, muc_T=(10.0, 20.0, 30.0, 40.0), lap=4, seed=305)
    hc_slope = nhiet_ke.hieu_chuan_cheo_tu_df(df_slope, nguoi_thuc_hien="Hoc Sinh B", nguon_du_lieu="MO_PHONG")
    assert hc_slope.phu_thuoc_nhiet_do is True
    for t_chk in (10.0, 20.0, 30.0, 40.0):
        off_est, _ = hc_slope.offset_va_sigma_tai(t_chk)
        assert abs(off_est - (-0.2 + 0.02 * t_chk)) <= 0.1


def test_v1_tu_choi_thieu_du_lieu_va_hoi_quy_khong_co_file(tmp_path: Path):
    """V1: thiếu cặp (<6), thiếu mức (<2), hoặc thiếu --nguoi-thuc-hien đều bị từ chối và không ghi file; không có file thì giữ nguyên + thêm cờ mới."""
    # 1. Thiếu số cặp
    df_few = _tao_bang_nhiet_ke_mo_phong(0.5, muc_T=(20.0, 30.0), lap=2, seed=1)  # 4 cặp < 6
    p_few = tmp_path / "few.csv"
    df_few.to_csv(p_few, index=False)
    out_none = tmp_path / "out_never.json"
    p_proc1 = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "hieu_chuan_cheo_nhiet_ke.py"), "--csv", str(p_few), "--nguoi-thuc-hien", "HS", "--out", str(out_none)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert p_proc1.returncode != 0 and not out_none.exists()

    # 2. Thiếu mức nhiệt (< 2 mức phân biệt >= 0.5°C)
    df_1level = _tao_bang_nhiet_ke_mo_phong(0.5, muc_T=(25.0,), lap=6, seed=2)
    p_1l = tmp_path / "one_level.csv"
    df_1level.to_csv(p_1l, index=False)
    p_proc2 = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "hieu_chuan_cheo_nhiet_ke.py"), "--csv", str(p_1l), "--nguoi-thuc-hien", "HS", "--out", str(out_none)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert p_proc2.returncode != 0 and not out_none.exists()

    # 3. Thiếu --nguoi-thuc-hien hoặc rỗng
    df_ok = _tao_bang_nhiet_ke_mo_phong(0.5, muc_T=(20.0, 30.0), lap=4, seed=3)
    p_ok = tmp_path / "ok.csv"
    df_ok.to_csv(p_ok, index=False)
    p_proc3 = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "hieu_chuan_cheo_nhiet_ke.py"), "--csv", str(p_ok), "--nguoi-thuc-hien", "   ", "--out", str(out_none)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert p_proc3.returncode != 0 and not out_none.exists()

    # 4. Hồi quy khi không có hiệu chuẩn chéo -> kết quả số giữ nguyên và thêm cờ nhiet_ke_chua_hieu_chuan_cheo
    cfg = op.CauHinhQuangHoc.tu_yaml()
    mh_no_d = cal.dung_duong_chuan(sinh_du_lieu_hieu_chuan_mo_phong(cfg=cfg, seed=0), bac_ep=1).mo_hinh
    dy = op.delta_y_vi_sai_px(18.0, 25.0, 25.0, cfg)
    kq = cal.uoc_luong_do_man(mh_no_d, dy, 25.0, sigma_T_C=0.2, T_tham_chieu_C=25.0, sigma_T_tham_chieu_C=0.2)
    assert any(c["ma"] == "nhiet_ke_chua_hieu_chuan_cheo" and c["cap"] == "can_than" for c in kq.canh_bao_chi_tiet)


def test_v1_csv_hieu_chuan_offset_va_web_api(monkeypatch, tmp_path: Path):
    """V1: doc_csv_hieu_chuan dùng T_tc đã trừ offset_nhiet_ke_C (vẫn giữ số đọc thô); Web API tự nạp file hiệu chuẩn chéo."""
    cfg = op.CauHinhQuangHoc.tu_yaml()
    df_raw = sinh_du_lieu_hieu_chuan_mo_phong(
        cfg=cfg, T_tham_chieu_C=(22.0, 25.0, 28.0), sigma_delta_y_px=0.02, sigma_nhiet_ke_C=0.0, seed=9, offset_nhiet_ke_tc_C=0.8
    )
    df_raw[cal.COT_NHIET_DO_TC_DOC] = df_raw[cal.COT_NHIET_DO_TC]
    df_raw[cal.COT_OFFSET_NHIET_KE] = 0.8
    p_csv = tmp_path / "cal_offset.csv"
    df_raw.to_csv(p_csv, index=False)
    df_loaded = cal.doc_csv_hieu_chuan(p_csv)
    assert np.allclose(df_loaded[cal.COT_NHIET_DO_TC], df_loaded[cal.COT_NHIET_DO_TC_DOC] - 0.8)
    mh_d = cal.dung_duong_chuan(df_loaded, bac_ep=1).mo_hinh
    assert mh_d.co_bu_chenh_T is True

    # Web API tự đọc file hiệu chuẩn chéo từ tmp_path (không tạo trong repo)
    df_pairs = _tao_bang_nhiet_ke_mo_phong(offset_that=0.8, seed=11)
    hc = nhiet_ke.hieu_chuan_cheo_tu_df(df_pairs, nguoi_thuc_hien="GVHD Test", nguon_du_lieu="MO_PHONG")
    p_json = nhiet_ke.luu_hieu_chuan_cheo_nhiet_ke(hc, tmp_path / "hc_nk.json")
    monkeypatch.setattr(web_app, "FILE_HIEU_CHUAN_NHIET_KE", p_json)
    monkeypatch.setattr(web_app, "get_model_for_profile", lambda _hs="mac_dinh": cal.dung_duong_chuan(sinh_du_lieu_hieu_chuan_mo_phong(cfg=cfg, seed=0), bac_ep=1).mo_hinh)

    r_boot = _run_coro(web_app.api_bootstrap(_make_request("GET", "/api/bootstrap")))
    d_boot = json.loads(r_boot.body.decode("utf-8"))
    assert d_boot["hieu_chuan_nhiet_ke"]["da_hieu_chuan"] is True
    assert "GVHD Test" in d_boot["hieu_chuan_nhiet_ke"]["thong_bao"]

    # Gửi T_mẫu=25.0, T_tc_đọc=25.8 -> sau trừ offset ~0.8 thì |D_eff| ~ 0 <= 0.5 nên không bị chặn chenh_T_ngoai_mo_hinh
    r_meas = _run_coro(
        web_app.api_measure(
            _make_request("POST", "/api/measure", {"mode": "sim", "S_ppt": 18.0, "T_C": 25.0, "T_tham_chieu_C": 25.0, "nhiet_do_do": 25.0, "nhiet_do_tham_chieu": 25.8})
        )
    )
    d_meas = json.loads(r_meas.body.decode("utf-8"))
    assert d_meas["mo_hinh_man"]["chenh_T_ngoai_mo_hinh"] is False
    assert d_meas["hieu_chuan_nhiet_ke"]["da_hieu_chuan"] is True

    # R7 panel: thiếu file -> có mục hieu_chuan.hieu_chuan_cheo_nhiet_ke; có file -> rời danh sách
    from core import trang_thai_cau_hinh as tt

    st_truoc = tt.liet_ke_tham_so_chua_xac_nhan(ROOT / "config.yaml", hieu_chuan_nhiet_ke_path=tmp_path / "khong_ton_tai.json")
    ma_truoc = {x["ma"] for x in st_truoc["danh_sach"]}
    assert "hieu_chuan.hieu_chuan_cheo_nhiet_ke" in ma_truoc
    assert "hieu_chuan.nhiet_ke_cheo.so_cap_toi_thieu" in ma_truoc

    st_sau = tt.liet_ke_tham_so_chua_xac_nhan(ROOT / "config.yaml", hieu_chuan_nhiet_ke_path=p_json)
    ma_sau = {x["ma"] for x in st_sau["danh_sach"]}
    assert "hieu_chuan.hieu_chuan_cheo_nhiet_ke" not in ma_sau

