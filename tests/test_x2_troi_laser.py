"""Kiểm thử X2 — phân tích độ trôi laser, mức triệt nhiễu chung κ và áp dụng tường minh.

Mọi dữ liệu trong file test này đều là MÔ PHỎNG tổng hợp (fixed seeds) dùng để kiểm
chứng logic thống kê (độ phủ 95%, tỉ lệ phát hiện warm-up, tỉ lệ đạt κ thấp/cao) kèm
khoảng tin cậy Wilson 95%; kể cả các phép thử truyền nhãn THUC_TE chỉ nhằm kiểm logic
đường ống và bảo vệ W0, KHÔNG phải số liệu đo thật của thiết bị.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from starlette.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.web_app import app
from core import optics as op
from core.troi_laser import (
    LoiDuLieuTroiKhongDuError,
    ap_dung_troi_laser_vao_tham_so,
    duong_dan_phan_tich_troi,
    duong_dan_tham_so_do_duoc,
    phan_tich_chuoi_troi_laser,
    phan_tich_troi_laser_tu_thu_muc,
)
from scripts.kiem_tra_chap_nhan_vong3 import khoang_tin_cay_wilson
from scripts.phan_tich_troi_laser import main as cli_troi_main
from scripts.xu_ly_thu_muc_anh import LoiAnhMoPhongGanNhanThucTeError
from sim.synth import ThamSoMoPhong, luu_anh_mo_phong_png, sinh_anh_hai_vach_mo_phong


def _tom_tat_thong_ke(ten: str, values: list[float], pass_count: int, n_total: int) -> dict[str, object]:
    arr = np.asarray(values, dtype=float)
    w_lo, w_hi = khoang_tin_cay_wilson(pass_count, n_total)
    return {
        "ten": ten,
        "n": n_total,
        "mean": float(np.mean(arr)),
        "rms": float(np.sqrt(np.mean(arr * arr))),
        "max": float(np.max(arr)),
        "min": float(np.min(arr)),
        "ty_le": pass_count / max(n_total, 1),
        "wilson_95": (w_lo, w_hi),
    }


def test_x2_i_troi_chung_thuan_tuy_200_chuoi() -> None:
    """(i) 200 chuỗi trôi chung 20 px, nhiễu độc lập σ=0.05 px: κ gần 1 và KTC95% phủ ≥ 90%."""
    rng = np.random.default_rng(202601)
    n_series = 200
    n_khung = 60
    t_phut = np.linspace(0.0, 24.0, n_khung)
    drift_chung = 20.0 * (t_phut / 24.0)
    var_drift = float(np.var(drift_chung, ddof=1))
    sigma_don_true = float(np.sqrt(var_drift + 0.05 ** 2))
    sigma_dy_true = float(np.sqrt(2.0) * 0.05)
    kappa_true = 1.0 - sigma_dy_true / sigma_don_true

    kappas: list[float] = []
    phu_ci = 0
    for i in range(n_series):
        yt = 220.0 + drift_chung + rng.normal(0.0, 0.05, size=n_khung)
        ym = 280.0 + drift_chung + rng.normal(0.0, 0.05, size=n_khung)
        kq = phan_tich_chuoi_troi_laser(
            t_phut,
            yt,
            ym,
            nguon_du_lieu="MO_PHONG",
            n_bootstrap=300,
            seed=10000 + i,
        )
        kappas.append(kq["kappa"])
        lo, hi = kq["ktc_95_kappa"]
        if lo <= kappa_true <= hi:
            phu_ci += 1

    tk = _tom_tat_thong_ke("kappa_troi_chung", kappas, phu_ci, n_series)
    assert tk["mean"] > 0.96
    assert min(kappas) > 0.90
    assert tk["ty_le"] >= 0.90, f"Độ phủ KTC95% κ thấp: {tk}"


def test_x2_ii_troi_doc_lap_kappa_thap_200_chuoi() -> None:
    """(ii) 200 chuỗi trôi độc lập (Δy trôi mạnh): κ thấp (≤ 0.2)."""
    rng = np.random.default_rng(202602)
    n_series = 200
    n_khung = 60
    t_phut = np.linspace(0.0, 24.0, n_khung)
    drift_mau = 20.0 * (t_phut / 24.0)
    drift_tc = -10.0 * (t_phut / 24.0)

    kappas: list[float] = []
    dat_thap = 0
    for i in range(n_series):
        yt = 220.0 + drift_tc + rng.normal(0.0, 0.05, size=n_khung)
        ym = 280.0 + drift_mau + rng.normal(0.0, 0.05, size=n_khung)
        kq = phan_tich_chuoi_troi_laser(
            t_phut,
            yt,
            ym,
            nguon_du_lieu="MO_PHONG",
            n_bootstrap=200,
            seed=20000 + i,
        )
        kappas.append(kq["kappa"])
        if kq["kappa"] <= 0.2:
            dat_thap += 1

    tk = _tom_tat_thong_ke("kappa_troi_doc_lap", kappas, dat_thap, n_series)
    assert tk["mean"] <= 0.2
    assert tk["max"] <= 0.2
    assert tk["ty_le"] >= 0.99


def test_x2_iii_bat_thuong_warmup_200_chuoi() -> None:
    """(iii) 200 chuỗi 5 phút đầu trôi gấp 5× 15+ phút sau bật cảnh báo warm-up; trôi đều không báo nhầm."""
    rng = np.random.default_rng(202603)
    n_series = 200
    n_khung = 60
    t_phut = np.linspace(0.0, 20.0, n_khung)

    # Trôi warm-up: [0,5] tốc độ 1.0 px/phút; (5,20] tốc độ 0.2 px/phút
    drift_wu = np.where(t_phut <= 5.0, 1.0 * t_phut, 5.0 + 0.2 * (t_phut - 5.0))
    # Đối chứng: trôi tuyến tính đều 0.5 px/phút
    drift_deu = 0.5 * t_phut

    phat_hien_wu = 0
    bao_nham = 0
    ratios: list[float] = []
    for i in range(n_series):
        yt_wu = 220.0 + drift_wu + rng.normal(0.0, 0.05, size=n_khung)
        ym_wu = 280.0 + drift_wu + rng.normal(0.0, 0.05, size=n_khung)
        kq_wu = phan_tich_chuoi_troi_laser(
            t_phut,
            yt_wu,
            ym_wu,
            nguon_du_lieu="MO_PHONG",
            n_bootstrap=100,
            seed=30000 + i,
        )
        ratios.append(kq_wu["chi_tiet_warm_up"]["ty_le_toc_do_dau_sau"])
        if kq_wu["canh_bao_warm_up"]:
            phat_hien_wu += 1

        yt_ctrl = 220.0 + drift_deu + rng.normal(0.0, 0.05, size=n_khung)
        ym_ctrl = 280.0 + drift_deu + rng.normal(0.0, 0.05, size=n_khung)
        kq_ctrl = phan_tich_chuoi_troi_laser(
            t_phut,
            yt_ctrl,
            ym_ctrl,
            nguon_du_lieu="MO_PHONG",
            n_bootstrap=100,
            seed=40000 + i,
        )
        if kq_ctrl["canh_bao_warm_up"]:
            bao_nham += 1

    tk_wu = _tom_tat_thong_ke("ty_le_warm_up", ratios, phat_hien_wu, n_series)
    w_ctrl = khoang_tin_cay_wilson(bao_nham, n_series)
    assert tk_wu["ty_le"] >= 0.95, f"Phát hiện warm-up thấp: {tk_wu}"
    assert bao_nham / n_series <= 0.05, f"Báo nhầm warm-up quá cao: {bao_nham}/{n_series}, {w_ctrl}"


def test_x2_iv_toc_do_troi_biet_truoc_200_chuoi() -> None:
    """(iv) 200 chuỗi có tốc độ trôi biết trước k_tc, k_mẫu: khớp sai số nhỏ và KTC95% phủ ≥ 90%."""
    rng = np.random.default_rng(202604)
    n_series = 200
    n_khung = 60
    t_phut = np.linspace(0.0, 24.0, n_khung)
    t_gio = t_phut / 60.0
    k_tc_true = 12.0
    k_mau_true = 14.5

    err_tc: list[float] = []
    err_mau: list[float] = []
    phu_tc = 0
    phu_mau = 0
    for i in range(n_series):
        yt = 220.0 + k_tc_true * t_gio + rng.normal(0.0, 0.05, size=n_khung)
        ym = 280.0 + k_mau_true * t_gio + rng.normal(0.0, 0.05, size=n_khung)
        kq = phan_tich_chuoi_troi_laser(
            t_phut,
            yt,
            ym,
            nguon_du_lieu="MO_PHONG",
            n_bootstrap=100,
            seed=50000 + i,
        )
        err_tc.append(abs(kq["toc_do_troi_tc_px_gio"] - k_tc_true))
        err_mau.append(abs(kq["toc_do_troi_mau_px_gio"] - k_mau_true))
        lo_t, hi_t = kq["ktc_95_toc_do_tc_px_gio"]
        lo_m, hi_m = kq["ktc_95_toc_do_mau_px_gio"]
        if lo_t <= k_tc_true <= hi_t:
            phu_tc += 1
        if lo_m <= k_mau_true <= hi_m:
            phu_mau += 1

    tk_tc = _tom_tat_thong_ke("sai_so_k_tc", err_tc, phu_tc, n_series)
    tk_mau = _tom_tat_thong_ke("sai_so_k_mau", err_mau, phu_mau, n_series)
    assert tk_tc["rms"] < 0.25 and tk_mau["rms"] < 0.25
    assert tk_tc["ty_le"] >= 0.90 and tk_mau["ty_le"] >= 0.90


def test_x2_v_chuoi_5_phut_bi_gan_co_va_tu_choi_ap_dung() -> None:
    """(v) Chuỗi dài 5 phút (< 20 phút) bị gắn cờ CHUA_DU_DU_LIEU và từ chối --ap-dung;

    chỉ kiểm logic, dữ liệu vẫn là mô phỏng.
    """
    rng = np.random.default_rng(202605)
    t_phut = np.linspace(0.0, 5.0, 60)
    drift = 4.0 * (t_phut / 5.0)
    yt = 220.0 + drift + rng.normal(0.0, 0.05, size=60)
    ym = 280.0 + drift + rng.normal(0.0, 0.05, size=60)

    kq = phan_tich_chuoi_troi_laser(t_phut, yt, ym, nguon_du_lieu="THUC_TE")
    assert kq["trang_thai"] == "CHUA_DU_DU_LIEU"
    assert kq["hop_le"] is False
    assert any("CHUA_DU_DU_LIEU" in c for c in kq["canh_bao"])

    with pytest.raises(LoiDuLieuTroiKhongDuError):
        ap_dung_troi_laser_vao_tham_so(kq, nguoi_thuc_hien="Hoc Sinh A")
    assert not duong_dan_tham_so_do_duoc().exists()

    client = TestClient(app)
    r_api = client.post(
        "/api/troi-laser",
        json={
            "thoi_gian_phut": t_phut.tolist(),
            "y_tc_px": yt.tolist(),
            "y_mau_px": ym.tolist(),
            "nguon_du_lieu": "THUC_TE",
            "nguoi_thuc_hien": "Hoc Sinh A",
            "ap_dung": True,
        },
    )
    assert r_api.status_code == 422
    assert r_api.json()["loai_loi"] == "CHUA_DU_DU_LIEU"


def test_x2_thu_muc_anh_cli_api_va_optics_uu_tien_do_duoc(tmp_path: Path) -> None:
    """Kiểm tra thư mục ảnh mô phỏng + chống gắn nhãn giả + CLI --ap-dung + optics.ngan_sach_sai_so.

    chỉ kiểm logic đường ống và bảo vệ W0, dữ liệu vẫn là mô phỏng.
    """
    cfg_qh = op.CauHinhQuangHoc.tu_yaml()
    ns_truoc = op.ngan_sach_sai_so(15.0, 25.0, cfg_qh, 0.05, 0.5, 0.05, 5.0, 0.01)
    assert set(ns_truoc) == {"tim_tam", "nhiet_do", "goc_A", "troi_laser", "tong_RSS"}
    assert ns_truoc.nguon["troi_laser"] == "giả định"
    assert ns_truoc["nguon"]["troi_laser"] == "giả định"

    # Tạo 60 ảnh mô phỏng trôi chung từ 0 đến 12 px trong 24 phút
    thu_muc = tmp_path / "chuoi_troi_sim"
    thu_muc.mkdir()
    ts_rows = []
    for idx in range(60):
        t_p = 24.0 * idx / 59.0
        troi_px = 12.0 * idx / 59.0
        ts_mp = ThamSoMoPhong(
            chieu_rong=400,
            chieu_cao=300,
            S_ppt=0.0,
            T_C=25.0,
            drift_chung_px=troi_px,
            sigma_nhieu_doc=1.0,
            seed=7000 + idx,
        )
        anh_mp = sinh_anh_hai_vach_mo_phong(ts_mp)
        ten = f"frame_{idx:03d}.png"
        luu_anh_mo_phong_png(anh_mp, thu_muc / ten, gan_watermark=False)
        ts_rows.append({"ten_file": ten, "thoi_gian_phut": t_p})
    pd.DataFrame(ts_rows).to_csv(thu_muc / "timestamps.csv", index=False)

    # Ảnh mô phỏng mà gắn nhãn THUC_TE phải bị chặn theo W0
    with pytest.raises(LoiAnhMoPhongGanNhanThucTeError):
        phan_tich_troi_laser_tu_thu_muc(thu_muc, nguon_du_lieu="THUC_TE")

    # Chạy CLI với MO_PHONG và --ap-dung
    rc = cli_troi_main([
        "--thu-muc",
        str(thu_muc),
        "--nguon",
        "MO_PHONG",
        "--nguoi-thuc-hien",
        "Nhom KHKT Test",
        "--ap-dung",
    ])
    assert rc == 0
    assert duong_dan_phan_tich_troi().exists()
    assert duong_dan_tham_so_do_duoc().exists()

    tham_so = json.loads(duong_dan_tham_so_do_duoc().read_text(encoding="utf-8"))
    he_so_lot = tham_so["tham_so"]["he_so_triet_chung"]["gia_tri"]
    assert 0.0 <= he_so_lot <= 1.0
    assert tham_so["tham_so"]["he_so_triet_chung"]["nguoi_thuc_hien"] == "Nhom KHKT Test"

    # ngan_sach_sai_so bây giờ ưu tiên đọc tham số vừa lưu và gắn nhãn "đo được"
    ns_sau = op.ngan_sach_sai_so(15.0, 25.0, cfg_qh, 0.05, 0.5, 0.05, 5.0, 0.01)
    assert ns_sau.nguon["troi_laser"] == "đo được"
    assert ns_sau["nguon"]["tim_tam"] == "giả định"
    assert ns_sau.tham_so_su_dung["he_so_triet_chung"] == pytest.approx(he_so_lot)

    # Kiểm API GET trạng thái + POST /api/troi-laser + chặn WebP 415
    client = TestClient(app)
    r_st = client.get("/api/troi-laser/trang-thai")
    assert r_st.status_code == 200
    assert r_st.json()["bao_cao"]["trang_thai"] == "HOP_LE"

    webp_bytes = b"RIFF\x10\x00\x00\x00WEBP" + b"\x00" * 16
    r_webp = client.post(
        "/api/troi-laser",
        files=[("files", ("troi.webp", webp_bytes, "image/webp"))],
        data={"nguon_du_lieu": "THUC_TE"},
    )
    assert r_webp.status_code == 415
    assert r_webp.json()["loai_loi"] == "ANH_KHONG_HO_TRO_DINH_DANG"

    # Kiểm tra ảnh PNG sạch không nhãn mô phỏng đi qua luồng THUC_TE bình thường
    # (chỉ kiểm logic đường ống, dữ liệu vẫn là mô phỏng).
    import cv2

    clean_files = []
    for j in range(3):
        img_j = sinh_anh_hai_vach_mo_phong(
            ThamSoMoPhong(chieu_rong=400, chieu_cao=300, S_ppt=0.0, T_C=25.0, drift_chung_px=float(j), seed=900 + j)
        ).anh
        ok, buf = cv2.imencode(".png", img_j)
        assert ok
        clean_files.append(("files", (f"clean_{j}.png", buf.tobytes(), "image/png")))
    r_clean = client.post(
        "/api/troi-laser",
        files=clean_files,
        data={"nguon_du_lieu": "THUC_TE", "buoc_thoi_gian_giay": "60"},
    )
    assert r_clean.status_code == 200
    assert r_clean.json()["ket_qua"]["trang_thai"] == "CHUA_DU_DU_LIEU"
