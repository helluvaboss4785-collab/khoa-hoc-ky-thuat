"""Kiểm thử V0: nhúng nhãn SIMULATED trong PNG/JPEG và chặn gắn nhãn THUC_TE trên mọi đường đi."""

from __future__ import annotations

import base64
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import web_app
from core import calibration as cal
from core import optics as op
from scripts.xu_ly_thu_muc_anh import xu_ly_thu_muc_anh
from scripts.xuat_bao_cao import BANNER_MO_PHONG, xuat_bo_bao_cao
from sim.synth import (
    ThamSoMoPhong,
    doc_nhan_mo_phong,
    luu_anh_mo_phong_jpeg,
    luu_anh_mo_phong_png,
    sinh_anh_hai_vach_mo_phong,
    sinh_du_lieu_hieu_chuan_mo_phong,
)
from tests.test_web_app import _make_request, _run_coro


def _tao_anh_sach_khong_nhan(chieu_cao: int = 300, chieu_rong: int = 400) -> np.ndarray:
    """Tạo ảnh nền tổng hợp bằng NumPy (không qua hàm lưu mô phỏng) — chỉ kiểm logic."""
    anh = np.full((chieu_cao, chieu_rong, 3), 18, dtype=np.uint8)
    y_grid = np.arange(chieu_cao, dtype=float)[:, None]
    # Nửa trái (tham chiếu) tại y=100, nửa phải (mẫu) tại y=180
    mid = chieu_rong // 2
    sig_tc = 185.0 * np.exp(-0.5 * ((y_grid - 100.0) / 1.5) ** 2)
    sig_m = 185.0 * np.exp(-0.5 * ((y_grid - 180.0) / 1.5) ** 2)
    anh[:, : mid - 8, 2] = np.clip(anh[:, : mid - 8, 2] + sig_tc, 0, 255).astype(np.uint8)
    anh[:, mid + 8 :, 2] = np.clip(anh[:, mid + 8 :, 2] + sig_m, 0, 255).astype(np.uint8)
    return anh


def test_v0_chan_png_mo_phong_da_xoa_json_va_jpeg_doi_ten(tmp_path: Path):
    """V0.1 & V0.2: PNG mô phỏng đã xóa .json hoặc JPEG mô phỏng đổi tên bình thường + --nguon THUC_TE -> thoát mã 2, không ghi CSV."""
    cfg = op.CauHinhQuangHoc.tu_yaml()
    mp = sinh_anh_hai_vach_mo_phong(ThamSoMoPhong(S_ppt=15.0, T_C=25.0, seed=11), cfg=cfg)

    # 1. PNG mô phỏng xóa file .json cạnh bên
    dir_png = tmp_path / "case_png"
    dir_png.mkdir()
    png_path = luu_anh_mo_phong_png(mp, dir_png / "15_25_01.png")
    json_sidecar = png_path.with_suffix(".json")
    assert json_sidecar.exists()
    json_sidecar.unlink()  # xóa sidecar
    assert doc_nhan_mo_phong(png_path) is True

    out_png_csv = dir_png / "out_khong_duoc_tao.csv"
    proc_png = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "xu_ly_thu_muc_anh.py"),
            "--thu-muc",
            str(dir_png),
            "--nguon",
            "THUC_TE",
            "--tu-ten-file",
            "--out-csv",
            str(out_png_csv),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc_png.returncode == 2
    assert "15_25_01.png" in (proc_png.stdout + proc_png.stderr)
    assert not out_png_csv.exists()

    # 2. JPEG mô phỏng đã nén, xóa .json, đổi tên bình thường
    dir_jpg = tmp_path / "case_jpg"
    dir_jpg.mkdir()
    jpg_path = luu_anh_mo_phong_jpeg(mp, dir_jpg / "anh_binh_thuong.jpg", quality=85)
    jpg_path.with_suffix(".json").unlink()
    assert doc_nhan_mo_phong(jpg_path) is True

    meta_csv = dir_jpg / "metadata.csv"
    meta_csv.write_text(
        "ten_file,do_man_chuan_ppt,nhiet_do_C\nanh_binh_thuong.jpg,15.0,25.0\n",
        encoding="utf-8",
    )
    out_jpg_csv = dir_jpg / "out_jpg_khong_duoc_tao.csv"
    proc_jpg = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "xu_ly_thu_muc_anh.py"),
            "--thu-muc",
            str(dir_jpg),
            "--nguon",
            "THUC_TE",
            "--metadata",
            str(meta_csv),
            "--out-csv",
            str(out_jpg_csv),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc_jpg.returncode == 2
    assert "anh_binh_thuong.jpg" in (proc_jpg.stdout + proc_jpg.stderr)
    assert not out_jpg_csv.exists()


def test_v0_mo_phong_hop_le_va_anh_sach_chi_kiem_logic(tmp_path: Path):
    """V0.3 & V0.4: ảnh mô phỏng với --nguon MO_PHONG chạy + ghi sha256_anh; ảnh sạch không nhãn với --nguon THUC_TE (chỉ kiểm logic)."""
    cfg = op.CauHinhQuangHoc.tu_yaml()
    mp = sinh_anh_hai_vach_mo_phong(ThamSoMoPhong(S_ppt=20.0, T_C=25.0, seed=12), cfg=cfg)
    dir_mp = tmp_path / "mo_phong_ok"
    luu_anh_mo_phong_png(mp, dir_mp / "20_25_01.png")

    df_cal_mp, _, csv_mp, _ = xu_ly_thu_muc_anh(thu_muc=dir_mp, nguon="MO_PHONG", tu_ten_file=True)
    assert len(df_cal_mp) == 1
    assert df_cal_mp.iloc[0][cal.COT_NGUON] == "MO_PHONG"
    assert "sha256_anh" in df_cal_mp.columns and len(str(df_cal_mp.iloc[0]["sha256_anh"])) == 64
    assert csv_mp.exists()

    # Ảnh NumPy sạch lưu thẳng bằng cv2.imwrite (không qua hàm mô phỏng) — chỉ kiểm logic nhánh THUC_TE
    dir_tt = tmp_path / "anh_sach_chi_kiem_logic"
    dir_tt.mkdir()
    anh_sach = _tao_anh_sach_khong_nhan()
    p_sach = dir_tt / "16_25_01.png"
    assert cv2.imwrite(str(p_sach), anh_sach)
    assert doc_nhan_mo_phong(p_sach) is False

    df_cal_tt, _, csv_tt, _ = xu_ly_thu_muc_anh(thu_muc=dir_tt, nguon="THUC_TE", tu_ten_file=True)
    assert len(df_cal_tt) == 1
    assert df_cal_tt.iloc[0][cal.COT_NGUON] == "THUC_TE"
    assert "sha256_anh" in df_cal_tt.columns and len(str(df_cal_tt.iloc[0]["sha256_anh"])) == 64
    assert csv_tt.exists()


def test_v0_api_measure_va_multi_cuong_che_nhan_mo_phong(monkeypatch, tmp_path: Path):
    """V0.5: API đo đơn khung và đa khung phát hiện nhãn SIMULATED nhúng (kể cả trên mô hình THUC_TE chỉ kiểm logic)."""
    # Dựng mô hình THUC_TE giả lập từ NumPy sạch để chỉ kiểm logic cổng ảnh
    df_real = pd.DataFrame({
        cal.COT_DO_MAN: [0.0, 10.0, 20.0, 30.0, 0.0, 10.0, 20.0, 30.0],
        cal.COT_NHIET_DO: [25.0, 25.0, 25.0, 25.0, 25.0, 25.0, 25.0, 25.0],
        cal.COT_DELTA_Y: [0.0, 50.0, 100.0, 150.0, 0.1, 50.1, 99.9, 150.2],
        cal.COT_DO_DUC: [0.0] * 8,
        cal.COT_GHI_CHU: ["kiem_logic"] * 8,
        cal.COT_ID_THIET_BI: ["TB_KIEM_LOGIC"] * 8,
        cal.COT_ID_DIEN_THOAI: ["DT_KIEM_LOGIC"] * 8,
        cal.COT_MA_ME_PHA: ["M1", "M1", "M1", "M1", "M2", "M2", "M2", "M2"],
        cal.COT_NGUON: [cal.NHAN_THUC_TE] * 8,
    })
    mh_tt = cal.dung_duong_chuan(df_real, cal.CauHinhHieuChuan()).mo_hinh
    assert mh_tt.da_xac_nhan_thuc_te is True
    monkeypatch.setattr(web_app, "get_model_for_profile", lambda _hs="mac_dinh": mh_tt)

    cfg = op.CauHinhQuangHoc.tu_yaml()
    mp = sinh_anh_hai_vach_mo_phong(ThamSoMoPhong(S_ppt=16.0, T_C=25.0, seed=31), cfg=cfg)
    p_jpg = luu_anh_mo_phong_jpeg(mp, tmp_path / "mau_bt.jpg", gan_watermark=False)
    jpg_b64 = "data:image/jpeg;base64," + base64.b64encode(p_jpg.read_bytes()).decode("ascii")

    # 1. Ảnh JPEG có nhãn nhúng dù model là THUC_TE vẫn bị cưỡng chế la_mo_phong=True & không phân loại loài
    r_sim = _run_coro(
        web_app.api_measure(
            _make_request("POST", "/api/measure", {"mode": "upload", "image_base64": jpg_b64, "nhiet_do_do": 25.0})
        )
    )
    assert r_sim.status_code == 200
    d_sim = json.loads(r_sim.body.decode("utf-8"))
    assert d_sim["la_anh_mo_phong"] is True
    assert d_sim["la_mo_phong"] is True
    assert d_sim["phat_hien_nhan_mo_phong_anh"] is True
    assert d_sim["khong_danh_gia_duoc"] is True
    assert d_sim["trang_thai_danh_gia"] == "KHONG_DANH_GIA_DUOC"
    assert d_sim["mo_hinh_man"]["la_mo_phong"] is True
    assert d_sim["mo_hinh_man"]["da_xac_nhan_thuc_te"] is False
    assert any(c["ma"] == "ANH_MO_PHONG_NHUNG" for c in d_sim["chat_luong"]["canh_bao_chi_tiet"])

    # 2. Nhật kí bắt buộc ghi MÔ PHỎNG khi gửi cờ mô phỏng
    tmp_db = tmp_path / "tmp_nhat_ki.db"
    monkeypatch.setattr(web_app, "DB_PATH", tmp_db)
    monkeypatch.setattr(web_app, "_DB_INIT_PATH", None)
    r_log = _run_coro(
        web_app.api_logs_add(
            _make_request(
                "POST",
                "/api/logs/add",
                {
                    "vi_tri": "Ao 1",
                    "loai_nuoi": "Tom",
                    "delta_y_px": 80.0,
                    "do_man_ppt": 16.0,
                    "bat_dinh_U_ppt": 0.2,
                    "nhiet_do_C": 25.0,
                    "do_duc": 0.0,
                    "nguon_du_lieu": "ĐO THẬT",
                    "ghi_chu": "thu",
                    "la_anh_mo_phong": True,
                    "phat_hien_nhan_mo_phong_anh": True,
                },
            )
        )
    )
    assert r_log.status_code == 200
    df_log = web_app.doc_lich_su_df()
    assert df_log.iloc[0]["nguon_du_lieu"] == "MÔ PHỎNG"
    assert "MO_PHONG_NHUNG" in str(df_log.iloc[0]["ghi_chu"])

    # 3. Đa khung: trộn 1 khung thường + 1 khung mô phỏng -> cả chuỗi bị gắn cờ mô phỏng
    anh_sach = _tao_anh_sach_khong_nhan()
    ok_s, buf_s = cv2.imencode(".png", anh_sach)
    assert ok_s
    sach_b64 = "data:image/png;base64," + base64.b64encode(buf_s.tobytes()).decode("ascii")
    r_multi = _run_coro(
        web_app.api_measure_multi(
            _make_request(
                "POST",
                "/api/measure-multi",
                {"mode": "upload", "images_base64": [sach_b64, jpg_b64], "nhiet_do_do": 25.0},
            )
        )
    )
    assert r_multi.status_code == 200
    d_multi = json.loads(r_multi.body.decode("utf-8"))
    assert d_multi["la_anh_mo_phong"] is True
    assert d_multi["la_mo_phong"] is True
    assert d_multi["khong_danh_gia_duoc"] is True

    # 4. Ảnh sạch không nhãn trên mô hình THUC_TE -> không gán cờ mô phỏng (chỉ kiểm logic)
    r_sach = _run_coro(
        web_app.api_measure(
            _make_request("POST", "/api/measure", {"mode": "upload", "image_base64": sach_b64, "nhiet_do_do": 25.0})
        )
    )
    assert r_sach.status_code == 200
    d_sach = json.loads(r_sach.body.decode("utf-8"))
    assert d_sach["la_anh_mo_phong"] is False
    assert d_sach["la_mo_phong"] is False
    assert d_sach["phat_hien_nhan_mo_phong_anh"] is False


def test_v0_xuat_bao_cao_va_requirements_khong_doi(tmp_path: Path):
    """V0: sửa tay nguon_du_lieu=THUC_TE nhưng giữ id_thiet_bi/ghi_chu mô phỏng vẫn bị đóng dấu; requirements không thêm gói mới cho V0."""
    df_spoof = sinh_du_lieu_hieu_chuan_mo_phong()
    df_spoof["nguon_du_lieu"] = "THUC_TE"  # giả mạo đổi cột nguồn nhưng còn vết MO_PHONG
    p_csv = tmp_path / "spoof.csv"
    df_spoof.to_csv(p_csv, index=False, encoding="utf-8")

    kq = xuat_bo_bao_cao(csv_hieu_chuan=p_csv, out_dir=tmp_path / "bc_spoof")
    assert kq["chua_xac_nhan_hc"] is True
    assert BANNER_MO_PHONG in kq["tong_hop_bao_cao_md"].read_text(encoding="utf-8")
