"""Kiểm thử API HTTP thật bằng starlette.testclient.TestClient (V3, httpx==0.28.1)."""

from __future__ import annotations

import base64
import io
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from starlette.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import web_app
from core import calibration as cal
from core import nhiet_ke, optics as op
from sim.synth import (
    ThamSoMoPhong,
    luu_anh_mo_phong_jpeg,
    sinh_anh_hai_vach_mo_phong,
    sinh_du_lieu_hieu_chuan_mo_phong,
)


def _tao_anh_sach_bytes() -> bytes:
    """Tạo ảnh NumPy sạch không chứa nhãn nhúng SIMULATED — chỉ kiểm logic multipart."""
    anh = np.full((300, 400, 3), 18, dtype=np.uint8)
    y_grid = np.arange(300, dtype=float)[:, None]
    sig_tc = 185.0 * np.exp(-0.5 * ((y_grid - 100.0) / 1.5) ** 2)
    sig_m = 185.0 * np.exp(-0.5 * ((y_grid - 180.0) / 1.5) ** 2)
    anh[:, :192, 2] = np.clip(anh[:, :192, 2] + sig_tc, 0, 255).astype(np.uint8)
    anh[:, 208:, 2] = np.clip(anh[:, 208:, 2] + sig_m, 0, 255).astype(np.uint8)
    ok, buf = cv2.imencode(".png", anh)
    assert ok
    return buf.tobytes()


def test_v3_testclient_bootstrap_va_trang_thai_cau_hinh(monkeypatch, tmp_path: Path):
    """TestClient thật: GET /api/bootstrap và GET /api/trang-thai-cau-hinh."""
    monkeypatch.setattr(web_app, "DB_PATH", tmp_path / "boot_test.db")
    monkeypatch.setattr(web_app, "_DB_INIT_PATH", None)
    with TestClient(web_app.app) as client:
        r_boot = client.get("/api/bootstrap")
        assert r_boot.status_code == 200
        d_boot = r_boot.json()
        assert "so_tham_so_chua_xac_nhan" in d_boot
        assert "hieu_chuan_nhiet_ke" in d_boot

        r_st = client.get("/api/trang-thai-cau-hinh")
        assert r_st.status_code == 200
        d_st = r_st.json()
        assert d_st["so_tham_so_chua_xac_nhan"] == len(d_st["danh_sach"]) > 20
        assert d_st["so_tham_so_chua_xac_nhan"] == d_boot["so_tham_so_chua_xac_nhan"]


def test_v3_testclient_measure_r0_r3_v0_v1_va_multipart(monkeypatch, tmp_path: Path):
    """TestClient thật: POST /api/measure qua JSON và multipart/form-data thật."""
    cfg_op = op.CauHinhQuangHoc.tu_yaml()
    df_mp = sinh_du_lieu_hieu_chuan_mo_phong(cfg=cfg_op, seed=0)
    mh_no_d = cal.dung_duong_chuan(df_mp, cal.CauHinhHieuChuan(), bac_ep=1).mo_hinh
    monkeypatch.setattr(web_app, "get_model_for_profile", lambda _hs="mac_dinh": mh_no_d)

    with TestClient(web_app.app) as client:
        # 1. R0 qua TestClient JSON: nhập T_tc trên mô hình chưa học D -> có chenh_nhiet_con_lai & U tăng theo σ_T
        obj = sinh_anh_hai_vach_mo_phong(
            ThamSoMoPhong(S_ppt=20.0, T_C=25.4, T_tham_chieu_C=25.0, sigma_nhieu_doc=0.2, he_so_poisson=0.0, seed=11),
            cfg=cfg_op,
            gan_watermark=False,
        )
        ok, buf = cv2.imencode(".png", obj.anh)
        assert ok
        img_b64 = "data:image/png;base64," + base64.b64encode(buf.tobytes()).decode("ascii")

        u_vals = []
        for sig_t in (0.1, 0.5):
            cfg_c = cal.CauHinhHieuChuan(sai_so_nhiet_ke_C=sig_t)
            monkeypatch.setattr(web_app, "load_calib_config", lambda c=cfg_c: c)
            resp = client.post(
                "/api/measure",
                json={"mode": "upload", "image_base64": img_b64, "nhiet_do_do": 25.4, "nhiet_do_tham_chieu": 25.0},
            )
            assert resp.status_code == 200
            d = resp.json()
            assert d["mo_hinh_man"]["thanh_phan_bat_dinh"]["chenh_nhiet_con_lai"] > 0
            u_vals.append(d["mo_hinh_man"]["U_S_ppt"])
        assert u_vals[1] > u_vals[0]

        # 2. R3 qua TestClient JSON: méo rìa mặc định không phát MEO_ONG_KINH, có k1 mới phát
        obj_ria = sinh_anh_hai_vach_mo_phong(
            ThamSoMoPhong(S_ppt=5.0, T_C=25.0, y_tham_chieu_goc=45.0, sigma_nhieu_doc=0.2, he_so_poisson=0.0, seed=12),
            cfg=cfg_op,
            gan_watermark=False,
        )
        ok_r, buf_r = cv2.imencode(".png", obj_ria.anh)
        assert ok_r
        ria_b64 = "data:image/png;base64," + base64.b64encode(buf_r.tobytes()).decode("ascii")
        base_icfg = web_app.load_image_config()
        monkeypatch.setattr(web_app, "load_image_config", lambda: {**base_icfg, "he_so_meo_k1_khai_bao": None})
        r_r3_def = client.post("/api/measure", json={"mode": "upload", "image_base64": ria_b64, "nhiet_do_do": 25.0})
        assert r_r3_def.status_code == 200
        assert all(c["ma"] != "MEO_ONG_KINH" for c in r_r3_def.json()["chat_luong"]["canh_bao_chi_tiet"])

        monkeypatch.setattr(web_app, "load_image_config", lambda: {**base_icfg, "he_so_meo_k1_khai_bao": -0.1})
        r_r3_k1 = client.post("/api/measure", json={"mode": "upload", "image_base64": ria_b64, "nhiet_do_do": 25.0})
        assert r_r3_k1.status_code == 200
        assert any(c["ma"] == "MEO_ONG_KINH" for c in r_r3_k1.json()["chat_luong"]["canh_bao_chi_tiet"])

        # 3. Upload multipart/form-data thật cho V0 (ảnh JPEG nhúng SIMULATED trên mô hình THUC_TE chỉ kiểm logic)
        df_tt = pd.DataFrame({
            cal.COT_DO_MAN: [0.0, 10.0, 20.0, 30.0, 0.0, 10.0, 20.0, 30.0],
            cal.COT_NHIET_DO: [25.0] * 8,
            cal.COT_DELTA_Y: [0.0, 50.0, 100.0, 150.0, 0.1, 50.1, 99.9, 150.2],
            cal.COT_DO_DUC: [0.0] * 8,
            cal.COT_GHI_CHU: ["kiem_logic"] * 8,
            cal.COT_ID_THIET_BI: ["TB_KL"] * 8,
            cal.COT_ID_DIEN_THOAI: ["DT_KL"] * 8,
            cal.COT_MA_ME_PHA: ["M1", "M1", "M1", "M1", "M2", "M2", "M2", "M2"],
            cal.COT_NGUON: [cal.NHAN_THUC_TE] * 8,
        })
        mh_tt = cal.dung_duong_chuan(df_tt, cal.CauHinhHieuChuan(), bac_ep=1).mo_hinh
        monkeypatch.setattr(web_app, "get_model_for_profile", lambda _hs="mac_dinh": mh_tt)

        mp_jpg = luu_anh_mo_phong_jpeg(obj, tmp_path / "mau_upload.jpg", gan_watermark=False)
        r_mp_up = client.post(
            "/api/measure",
            files={"file": ("mau_upload.jpg", mp_jpg.read_bytes(), "image/jpeg")},
            data={"nhiet_do_do": "25.4", "nhiet_do_tham_chieu": "25.0"},
        )
        assert r_mp_up.status_code == 200
        d_mp = r_mp_up.json()
        assert d_mp["la_anh_mo_phong"] is True
        assert d_mp["la_mo_phong"] is True
        assert d_mp["phat_hien_nhan_mo_phong_anh"] is True
        assert d_mp["khong_danh_gia_duoc"] is True

        # Ảnh sạch không nhãn qua multipart trên mô hình THUC_TE (chỉ kiểm logic)
        sach_bytes = _tao_anh_sach_bytes()
        r_sach_up = client.post(
            "/api/measure",
            files={"file": ("sach.png", sach_bytes, "image/png")},
            data={"nhiet_do_do": "25.0", "khoa_ae_af": "true"},
        )
        assert r_sach_up.status_code == 200
        d_sach = r_sach_up.json()
        assert d_sach["la_mo_phong"] is False
        assert d_sach["phat_hien_nhan_mo_phong_anh"] is False

        # 4. V1 qua TestClient: áp dụng hiệu chuẩn chéo nhiệt kế từ JSON
        hc_nk = nhiet_ke.HieuChuanCheoNhietKe(
            offset_C=0.8, sigma_offset_C=0.02, phu_thuoc_nhiet_do=False,
            so_cap=8, so_muc_nhiet=3, ngay="2026-11-21", nguon_du_lieu="MO_PHONG", nguoi_thuc_hien="HS",
        )
        p_nk = nhiet_ke.luu_hieu_chuan_cheo_nhiet_ke(hc_nk, tmp_path / "hc_nk.json")
        monkeypatch.setattr(web_app, "FILE_HIEU_CHUAN_NHIET_KE", p_nk)
        monkeypatch.setattr(web_app, "get_model_for_profile", lambda _hs="mac_dinh": mh_no_d)
        r_v1 = client.post(
            "/api/measure",
            json={"mode": "sim", "S_ppt": 18.0, "T_C": 25.0, "T_tham_chieu_C": 25.0, "nhiet_do_do": 25.0, "nhiet_do_tham_chieu": 25.8},
        )
        assert r_v1.status_code == 200
        assert r_v1.json()["mo_hinh_man"]["chenh_T_ngoai_mo_hinh"] is False


def test_v3_testclient_measure_multi_calibrate_va_logs(monkeypatch, tmp_path: Path):
    """TestClient thật: /api/measure-multi (R1/V0), /api/calibrate, /api/logs/*."""
    cfg_op = op.CauHinhQuangHoc.tu_yaml()
    tmp_db = tmp_path / "testclient_logs.db"
    monkeypatch.setattr(web_app, "DB_PATH", tmp_db)
    monkeypatch.setattr(web_app, "_DB_INIT_PATH", None)

    with TestClient(web_app.app) as client:
        # 1. /api/measure-multi (R1)
        imgs_b64 = []
        times_s = [0.0, 90.0, 180.0, 270.0, 360.0]
        for idx, _ in enumerate(times_s):
            obj = sinh_anh_hai_vach_mo_phong(
                ThamSoMoPhong(S_ppt=20.0, T_C=25.0, T_tham_chieu_C=25.0, sigma_nhieu_doc=0.3, he_so_poisson=0.0, seed=50 + idx),
                cfg=cfg_op,
                gan_watermark=False,
            )
            ok, buf = cv2.imencode(".png", obj.anh)
            assert ok
            imgs_b64.append("data:image/png;base64," + base64.b64encode(buf.tobytes()).decode("ascii"))

        cfg_on = cal.CauHinhHieuChuan(
            cho_phep_giam_sigma_D_khi_on_dinh=True,
            sigma_D_khi_chua_do_C=2.0,
            sigma_D_khi_da_on_dinh_C=1.0,
            thoi_gian_on_dinh_toi_thieu_phut=5.0,
        )
        monkeypatch.setattr(web_app, "load_calib_config", lambda: cfg_on)
        r_multi = client.post(
            "/api/measure-multi",
            json={"mode": "upload", "images_base64": imgs_b64, "thoi_gian_s": times_s, "nhiet_do_do": 25.0},
        )
        assert r_multi.status_code == 200
        d_m = r_multi.json()
        assert d_m["can_bang_nhiet"]["da_ap_dung_giam_sigma_D"] is True

        # 2. /api/calibrate (mô phỏng + CSV)
        r_cal = client.post("/api/calibrate", json={"mode": "sim", "activate": False})
        assert r_cal.status_code == 200
        d_cal = r_cal.json()
        assert d_cal["bac_chon"] in (1, 2)
        assert d_cal["mo_hinh"]["R2"] > 0.99

        # 3. /api/logs/add + /api/logs + /api/logs/csv trên DB tạm
        r_add = client.post(
            "/api/logs/add",
            json={
                "vi_tri": "Ao TestClient",
                "loai_nuoi": "Tom",
                "delta_y_px": 95.0,
                "do_man_ppt": 19.0,
                "bat_dinh_U_ppt": 0.25,
                "nhiet_do_C": 26.0,
                "do_duc": 0.1,
                "nguon_du_lieu": "MÔ PHỎNG",
                "ghi_chu": "kiem_testclient",
            },
        )
        assert r_add.status_code == 200 and r_add.json()["ok"] is True

        r_list = client.get("/api/logs")
        assert r_list.status_code == 200
        rows = r_list.json()["rows"]
        assert any(r["vi_tri"] == "Ao TestClient" for r in rows)

        r_csv = client.get("/api/logs/csv")
        assert r_csv.status_code == 200
        assert "Ao TestClient" in r_csv.text
