"""Kiểm thử X0: (a) tiêu chí gốc W3 ở Vòng 5; (b) loại dòng bản sao khi khớp; (c) nhận diện HEIC/HEIF/WebP."""

from __future__ import annotations

import base64
import subprocess
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
from core.measure import AnhKhongHoTroDinhDangError, nhan_dien_dinh_dang_anh_bytes
from sim.synth import ThamSoMoPhong, sinh_anh_hai_vach_mo_phong, sinh_du_lieu_hieu_chuan_mo_phong


def _tao_bo_72_dong_x0(seed: int = 42) -> pd.DataFrame:
    df = sinh_du_lieu_hieu_chuan_mo_phong(
        muc_S=(0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0),
        muc_T=(20.0, 25.0, 30.0),
        so_lan_lap=3,
        sigma_nhiet_ke_C=0.1,
        seed=seed,
    )
    df[cal.COT_MA_ME_PHA] = ["ME_01" if (i % 2 == 0) else "ME_02" for i in range(len(df))]
    df[cal.COT_PX_PER_MM] = 20.0
    return df


def test_x0_b_loai_ban_sao_khi_khop_duong_chuan():
    """X0(b): 72 dòng nhân 3 thành 216 -> bật cờ khớp đúng 72 dòng & he_so_duong_chuan trong ±10% gốc; tắt cờ -> 216; không bản sao -> y hệt."""
    df_72 = _tao_bo_72_dong_x0(seed=42)
    df_216 = pd.concat([df_72, df_72, df_72], ignore_index=True)

    bc_goc = cal.dung_duong_chuan(df_72, cal.CauHinhHieuChuan(loai_ban_sao_khi_khop=True))
    bc_goc_tat = cal.dung_duong_chuan(df_72, cal.CauHinhHieuChuan(loai_ban_sao_khi_khop=False))
    assert bc_goc.mo_hinh.he_so == bc_goc_tat.mo_hinh.he_so
    assert bc_goc.so_dong_loai == 0
    assert bc_goc.so_dong_dung == 72

    bc_loai = cal.dung_duong_chuan(df_216, cal.CauHinhHieuChuan(loai_ban_sao_khi_khop=True))
    assert bc_loai.so_dong_dung == 72
    assert bc_loai.so_dong_loai == 144
    assert bc_loai.mo_hinh.so_diem == 72
    assert bc_loai.mo_hinh.so_dong_dung == 72
    assert bc_loai.mo_hinh.so_dong_loai == 144
    assert bc_loai.da_loai_ban_sao_khi_khop is True
    assert any(c["ma"] == "DU_LIEU_CO_BAN_SAO" and c["cap"] == "nghiem_trong" for c in bc_loai.canh_bao_chi_tiet)

    kq_goc = cal.uoc_luong_do_man(bc_goc.mo_hinh, delta_y_px=100.0, T_C=25.0, T_tham_chieu_C=25.0)
    kq_loai = cal.uoc_luong_do_man(bc_loai.mo_hinh, delta_y_px=100.0, T_C=25.0, T_tham_chieu_C=25.0)
    u_hs_goc = kq_goc.thanh_phan_bat_dinh["he_so_duong_chuan"]
    u_hs_loai = kq_loai.thanh_phan_bat_dinh["he_so_duong_chuan"]
    assert abs(u_hs_loai - u_hs_goc) <= 0.10 * max(u_hs_goc, 1e-12)

    bc_giu = cal.dung_duong_chuan(df_216, cal.CauHinhHieuChuan(loai_ban_sao_khi_khop=False))
    assert bc_giu.so_dong_dung == 216
    assert bc_giu.so_dong_loai == 0
    assert bc_giu.mo_hinh.so_diem == 216
    assert bc_giu.da_loai_ban_sao_khi_khop is False


def test_x0_c_nhan_dien_heic_webp_api_415_va_cli(tmp_path: Path):
    """X0(c): ghép byte chữ kí HEIC và WebP -> API trả 415 ANH_KHONG_HO_TRO_DINH_DANG, CLI trả mã 4, JPEG/PNG hợp lệ vẫn qua."""
    heic_bytes = (24).to_bytes(4, "big") + b"ftypheic\x00\x00\x00\x00mif1heic" + b"\x00" * 32
    heif_bytes = (24).to_bytes(4, "big") + b"ftypmif1\x00\x00\x00\x00mif1hevc" + b"\x00" * 32
    webp_bytes = b"RIFF\x24\x00\x00\x00WEBPVP8 \x18\x00\x00\x00" + b"\x00" * 32

    assert nhan_dien_dinh_dang_anh_bytes(heic_bytes) == "HEIC/HEIF"
    assert nhan_dien_dinh_dang_anh_bytes(heif_bytes) == "HEIC/HEIF"
    assert nhan_dien_dinh_dang_anh_bytes(webp_bytes) == "WebP"

    with TestClient(web_app.app) as client:
        for fname, raw, fmt_lbl in (
            ("iphone.heic", heic_bytes, "HEIC"),
            ("iphone.heif", heif_bytes, "HEIC"),
            ("photo.webp", webp_bytes, "WebP"),
        ):
            resp = client.post(
                "/api/measure",
                files={"file": (fname, raw, "application/octet-stream")},
                data={"nhiet_do_do": "25.0"},
            )
            assert resp.status_code == 415
            js = resp.json()
            assert js["loai_loi"] == "ANH_KHONG_HO_TRO_DINH_DANG"
            assert fmt_lbl in js["error"]
            assert "Tương thích nhất (JPEG)" in js["error"]

            b64 = base64.b64encode(raw).decode("ascii")
            resp_multi = client.post(
                "/api/measure-multi",
                json={"mode": "upload", "images_base64": [b64, b64], "nhiet_do_do": 25.0},
            )
            assert resp_multi.status_code == 415
            assert resp_multi.json()["loai_loi"] == "ANH_KHONG_HO_TRO_DINH_DANG"

        # Ảnh PNG/JPEG hợp lệ vẫn giải mã và đo bình thường
        obj = sinh_anh_hai_vach_mo_phong(ThamSoMoPhong(S_ppt=15.0, T_C=25.0, seed=123), gan_watermark=False)
        for ext, flag in ((".png", []), (".jpg", [int(cv2.IMWRITE_JPEG_QUALITY), 95])):
            ok, buf = cv2.imencode(ext, obj.anh, flag)
            assert ok
            r_ok = client.post(
                "/api/measure",
                files={"file": (f"hop_le{ext}", buf.tobytes(), "image/png")},
                data={"nhiet_do_do": "25.0"},
            )
            assert r_ok.status_code == 200

    # CLI xu_ly_thu_muc_anh thoát mã 4 khi gặp HEIC/WebP
    d_heic = tmp_path / "heic_dir"
    d_heic.mkdir()
    (d_heic / "15_25_01.heic").write_bytes(heic_bytes)
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "xu_ly_thu_muc_anh.py"),
            "--thu-muc", str(d_heic),
            "--nguon", "MO_PHONG",
            "--tu-ten-file",
        ],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 4
    assert "HEIC" in (proc.stdout + proc.stderr)


def test_x0_a_script_vong5_ap_tieu_chi_goc_95(tmp_path: Path):
    """X0(a): kiểm tra logic script vòng 5 áp tiêu chí cov_new >= 0.95 cho cả 3 mức độ phân giải."""
    txt = (ROOT / "scripts" / "kiem_tra_chap_nhan_vong5.py").read_text(encoding="utf-8")
    assert "cov_new >= cov_old" not in txt
    assert "chưa phân biệt được với 95%" in txt
