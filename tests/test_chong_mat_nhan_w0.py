"""Kiểm thử W0: sổ ảnh mô phỏng sha256, kiểm EXIF THUC_TE, chặn thư mục và sổ ảnh đã xử lí."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import shutil
import struct
import subprocess
import sys
import uuid
import zipfile
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from PIL import Image
from starlette.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import web_app
from core import calibration as cal
from core import optics as op
from core import thang
from scripts.dong_goi import kiem_tra_goi_zip, tao_file_zip_nop_bai
from scripts.so_sanh_kenh import _tai_mau_jpeg_sim
from sim.synth import (
    ThamSoMoPhong,
    doc_nhan_mo_phong,
    ghi_so_anh_mo_phong,
    luu_anh_mo_phong_png,
    sinh_anh_hai_vach_mo_phong,
    tra_cuu_so_anh_mo_phong,
)


def _tao_anh_sach(chieu_cao: int = 300, chieu_rong: int = 400) -> np.ndarray:
    """Ảnh nền tổng hợp hai vạch bằng NumPy — chỉ kiểm logic, KHÔNG phải ảnh chụp thật."""
    anh = np.full((chieu_cao, chieu_rong, 3), 18, dtype=np.uint8)
    y_grid = np.arange(chieu_cao, dtype=float)[:, None]
    mid = chieu_rong // 2
    sig_tc = 185.0 * np.exp(-0.5 * ((y_grid - 100.0) / 1.5) ** 2)
    sig_m = 185.0 * np.exp(-0.5 * ((y_grid - 180.0) / 1.5) ** 2)
    anh[:, : mid - 8, 2] = np.clip(anh[:, : mid - 8, 2] + sig_tc, 0, 255).astype(np.uint8)
    anh[:, mid + 8 :, 2] = np.clip(anh[:, mid + 8 :, 2] + sig_m, 0, 255).astype(np.uint8)
    return anh


def _go_chunk_text_png(png_bytes: bytes) -> bytes:
    """Gỡ toàn bộ chunk tEXt/iTXt/zTXt khỏi PNG để mô phỏng ảnh bị xóa metadata nhúng (sha256 khác gốc)."""
    sig = b"\x89PNG\r\n\x1a\n"
    assert png_bytes.startswith(sig)
    out = bytearray(sig)
    pos = len(sig)
    while pos + 12 <= len(png_bytes):
        length = struct.unpack(">I", png_bytes[pos : pos + 4])[0]
        ctype = png_bytes[pos + 4 : pos + 8]
        chunk_end = pos + 12 + length
        if chunk_end > len(png_bytes):
            break
        if ctype not in (b"tEXt", b"iTXt", b"zTXt"):
            out.extend(png_bytes[pos:chunk_end])
        pos = chunk_end
        if ctype == b"IEND":
            break
    return bytes(out)


def _chay_cli(args: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "xu_ly_thu_muc_anh.py"), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_w0_png_luu_lai_mat_nhan_va_ban_sao_nguyen_byte_vs_go_chunk(tmp_path: Path):
    """W0: PNG mở/lưu lại bằng cv2 -> mã 3 (thiếu EXIF); bản sao nguyên byte (đã vào sổ) -> mã 2; PNG gỡ chunk (sha256 khác) -> mã 3."""
    cfg = op.CauHinhQuangHoc.tu_yaml()
    mp = sinh_anh_hai_vach_mo_phong(ThamSoMoPhong(S_ppt=15.0, T_C=25.0, seed=101), cfg=cfg, gan_watermark=False)

    d_src = tmp_path / "src_sim"
    p_sim = luu_anh_mo_phong_png(mp, d_src / "15_25_01.png", gan_watermark=False)
    assert doc_nhan_mo_phong(p_sim) is True
    assert tra_cuu_so_anh_mo_phong(p_sim) is not None

    # 1. Mở & lưu lại bằng cv2.imread + cv2.imwrite (mất nhãn nhúng, xóa .json, đổi tên) + không khai báo -> thoát mã 3
    img_re = cv2.imread(str(p_sim), cv2.IMREAD_COLOR)
    d_resave = tmp_path / "resaved"
    d_resave.mkdir()
    p_resaved = d_resave / "15_25_01.png"
    assert cv2.imwrite(str(p_resaved), img_re)
    assert doc_nhan_mo_phong(p_resaved) is False
    out1 = d_resave / "out_khong_duoc_tao.csv"
    proc1 = _chay_cli(["--thu-muc", str(d_resave), "--nguon", "THUC_TE", "--tu-ten-file", "--out-csv", str(out1)])
    assert proc1.returncode == 3, proc1.stdout + proc1.stderr
    assert "15_25_01.png" in (proc1.stdout + proc1.stderr)
    assert not out1.exists()

    # 2a. Ảnh gỡ chunk metadata (sha256 thay đổi, không khớp sổ, mất nhãn nhúng): bị chặn mã 3 khi thiếu EXIF/khai báo
    d_stripped = tmp_path / "stripped"
    d_stripped.mkdir()
    stripped_bytes = _go_chunk_text_png(p_sim.read_bytes())
    assert hashlib.sha256(stripped_bytes).hexdigest() != hashlib.sha256(p_sim.read_bytes()).hexdigest()
    (d_stripped / "15_25_01.png").write_bytes(stripped_bytes)
    assert doc_nhan_mo_phong(d_stripped / "15_25_01.png") is False
    assert tra_cuu_so_anh_mo_phong(stripped_bytes) is None
    proc_strip = _chay_cli(["--thu-muc", str(d_stripped), "--nguon", "THUC_TE", "--tu-ten-file"])
    assert proc_strip.returncode == 3

    # 2b. Bản sao nguyên byte KHÔNG đổi từ tệp có sha256 trong sổ (thậm chí không có nhãn nhúng, tên sạch, không json):
    # bị chặn mã 2 nhờ sổ sha256 outputs/so_anh_mo_phong.csv
    d_exact = tmp_path / "exact_copy_in_ledger"
    d_exact.mkdir()
    p_ledger_only = d_exact / "15_25_01.png"
    p_ledger_only.write_bytes(stripped_bytes)
    ghi_so_anh_mo_phong(stripped_bytes, p_sim, mo_ta_tham_so="test ban sao nguyen byte trong so")
    proc_exact = _chay_cli(
        [
            "--thu-muc", str(d_exact),
            "--nguon", "THUC_TE",
            "--tu-ten-file",
            "--khai-bao-nguon-anh", "Co tinh bo qua EXIF van phai bi so chan",
            "--nguoi-khai-bao", "Kiem thu W0",
        ]
    )
    assert proc_exact.returncode == 2
    assert "sha256" in (proc_exact.stdout + proc_exact.stderr)


def test_w0_so_sanh_kenh_ghi_so_va_anh_exif_gia_lap_chi_kiem_logic(tmp_path: Path):
    """W0: so_sanh_kenh ghi sổ ảnh mô phỏng; ảnh có EXIF tối thiểu chạy THUC_TE bình thường (chỉ kiểm logic, dữ liệu vẫn mô phỏng)."""
    cfg = op.CauHinhQuangHoc.tu_yaml()
    mau = _tai_mau_jpeg_sim(1, cfg)
    assert len(mau) >= 1
    so_path = Path(os.environ["SALINITY_SO_MO_PHONG_PATH"])
    assert so_path.exists()
    df_so = pd.read_csv(so_path, encoding="utf-8-sig")
    assert len(df_so) >= len(mau)
    assert list(df_so.columns) == ["sha256", "thoi_gian", "duong_dan", "mo_ta_tham_so"]

    # Ảnh sạch chèn EXIF tối thiểu bằng PIL (chỉ kiểm logic EXIF, dữ liệu vẫn là mô phỏng)
    d_exif = tmp_path / "anh_co_exif_chi_kiem_logic"
    d_exif.mkdir()
    anh_rgb = cv2.cvtColor(_tao_anh_sach(), cv2.COLOR_BGR2RGB)
    pil_im = Image.fromarray(anh_rgb)
    ex = Image.Exif()
    ex[271] = "TestPhoneBrand"
    ex[272] = "PixelMock-W0"
    ex[36867] = "2026:11:22 08:00:00"
    ex[34855] = 100
    p_exif = d_exif / "16_25_01.jpg"
    pil_im.save(p_exif, format="JPEG", quality=95, exif=ex.tobytes())

    info_ex = thang.doc_exif_may_anh(p_exif.read_bytes())
    assert info_ex["co_exif_may_anh"] is True
    assert info_ex["hang_may_anh"] == "TestPhoneBrand"
    assert info_ex["mau_may_anh"] == "PixelMock-W0"

    out_csv = tmp_path / "cal_exif.csv"
    out_rep = tmp_path / "rep_exif.csv"
    proc = _chay_cli([
        "--thu-muc", str(d_exif),
        "--nguon", "THUC_TE",
        "--tu-ten-file",
        "--out-csv", str(out_csv),
        "--out-report", str(out_rep),
    ])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    df_cal = pd.read_csv(out_csv, encoding="utf-8-sig")
    assert len(df_cal) == 1
    assert str(df_cal.iloc[0]["exif_co"]).lower() == "true"


def test_w0_khai_bao_thieu_exif_chan_thu_muc_va_xung_dot_so_da_xu_ly(tmp_path: Path):
    """W0: thiếu EXIF + khai báo -> đủ 3 cột + cảnh báo; thư mục dưới outputs/ -> mã 2; trùng sha256 khác nhãn -> mã 2."""
    # 1. Ảnh thiếu EXIF + đủ --khai-bao-nguon-anh & --nguoi-khai-bao
    d_decl = tmp_path / "anh_thieu_exif_khai_bao"
    d_decl.mkdir()
    p_noex = d_decl / "16_25_01.png"
    assert cv2.imwrite(str(p_noex), _tao_anh_sach())
    out_csv = tmp_path / "cal_decl.csv"
    out_rep = tmp_path / "rep_decl.csv"
    proc_ok = _chay_cli([
        "--thu-muc", str(d_decl),
        "--nguon", "THUC_TE",
        "--tu-ten-file",
        "--khai-bao-nguon-anh", "Anh chup dien thoai xuat PNG mat EXIF",
        "--nguoi-khai-bao", "Nguyen Van A",
        "--out-csv", str(out_csv),
        "--out-report", str(out_rep),
    ])
    assert proc_ok.returncode == 0, proc_ok.stdout + proc_ok.stderr
    df_cal = pd.read_csv(out_csv, encoding="utf-8-sig")
    assert str(df_cal.iloc[0]["exif_co"]).lower() == "false"
    assert df_cal.iloc[0]["khai_bao_nguon_anh"] == "Anh chup dien thoai xuat PNG mat EXIF"
    assert df_cal.iloc[0]["nguoi_khai_bao"] == "Nguyen Van A"
    df_rep = pd.read_csv(out_rep, encoding="utf-8-sig")
    assert df_rep.iloc[0]["canh_bao_nguon_exif"] == "Ảnh không có EXIF, nguồn do người dùng tự khai"

    # 2. Xử lí lại ĐÚNG ảnh vừa có sha256 gắn THUC_TE với nhãn --nguon MO_PHONG -> bị chặn mã 2 (xung đột sổ)
    out_conflict = tmp_path / "cal_conflict.csv"
    proc_conf = _chay_cli([
        "--thu-muc", str(d_decl),
        "--nguon", "MO_PHONG",
        "--tu-ten-file",
        "--out-csv", str(out_conflict),
    ])
    assert proc_conf.returncode == 2
    assert "THUC_TE" in (proc_conf.stdout + proc_conf.stderr)
    assert not out_conflict.exists()

    # 3. Chiều ngược lại: MO_PHONG trước, sau đó mang cùng sha256 gắn THUC_TE -> chặn mã 2
    d_mp_then_tt = tmp_path / "mp_then_tt"
    d_mp_then_tt.mkdir()
    anh_2 = _tao_anh_sach()
    anh_2[0, 0, 0] = (int(anh_2[0, 0, 0]) + 1) % 255  # sha256 mới chưa xử lí
    assert cv2.imwrite(str(d_mp_then_tt / "16_25_02.png"), anh_2)
    proc_mp = _chay_cli(["--thu-muc", str(d_mp_then_tt), "--nguon", "MO_PHONG", "--tu-ten-file"])
    assert proc_mp.returncode == 0
    proc_tt = _chay_cli([
        "--thu-muc", str(d_mp_then_tt),
        "--nguon", "THUC_TE",
        "--tu-ten-file",
        "--khai-bao-nguon-anh", "Thu doi nhan",
        "--nguoi-khai-bao", "Kiem thu W0",
    ])
    assert proc_tt.returncode == 2
    assert "MO_PHONG" in (proc_tt.stdout + proc_tt.stderr)

    # 4. Thư mục nằm dưới outputs/ + THUC_TE -> mã thoát 2
    out_sub = ROOT / "outputs" / f"_tmp_w0_folder_check_{uuid.uuid4().hex[:8]}"
    out_sub.mkdir(parents=True, exist_ok=True)
    try:
        assert cv2.imwrite(str(out_sub / "16_25_01.png"), _tao_anh_sach())
        proc_dir = _chay_cli([
            "--thu-muc", str(out_sub),
            "--nguon", "THUC_TE",
            "--tu-ten-file",
            "--khai-bao-nguon-anh", "Test chan thu muc",
            "--nguoi-khai-bao", "Kiem thu W0",
        ])
        assert proc_dir.returncode == 2
    finally:
        shutil.rmtree(out_sub, ignore_errors=True)


def test_w0_webapp_exif_va_tra_cuu_so_anh_mo_phong_va_dong_goi(monkeypatch, tmp_path: Path):
    """W0: /api/measure phát hiện ảnh thiếu EXIF (can_than) + tra sha256 sổ mô phỏng; dong_goi giữ so_anh_da_xu_ly và bỏ so_anh_mo_phong."""
    df_real = pd.DataFrame({
        cal.COT_DO_MAN: [0.0, 10.0, 20.0, 30.0, 0.0, 10.0, 20.0, 30.0],
        cal.COT_NHIET_DO: [25.0] * 8,
        cal.COT_DELTA_Y: [0.0, 50.0, 100.0, 150.0, 0.1, 50.1, 99.9, 150.2],
        cal.COT_DO_DUC: [0.0] * 8,
        cal.COT_GHI_CHU: ["kiem_logic"] * 8,
        cal.COT_ID_THIET_BI: ["TB_KIEM_LOGIC"] * 8,
        cal.COT_ID_DIEN_THOAI: ["DT_KIEM_LOGIC"] * 8,
        cal.COT_MA_ME_PHA: ["M1"] * 4 + ["M2"] * 4,
        cal.COT_NGUON: [cal.NHAN_THUC_TE] * 8,
    })
    mh_tt = cal.dung_duong_chuan(df_real, cal.CauHinhHieuChuan()).mo_hinh
    monkeypatch.setattr(web_app, "get_model_for_profile", lambda _hs="mac_dinh": mh_tt)

    anh_sach = _tao_anh_sach()
    ok, buf = cv2.imencode(".png", anh_sach)
    assert ok
    raw_sach = buf.tobytes()

    client = TestClient(web_app.app)
    # 1. Ảnh thiếu EXIF và KHÔNG nằm trong sổ -> không chặn, có ANH_KHONG_EXIF (can_than)
    r1 = client.post("/api/measure", files={"file": ("sach.png", raw_sach, "image/png")}, data={"nhiet_do_do": "25.0"})
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["la_anh_mo_phong"] is False
    assert d1["exif"]["co_exif_may_anh"] is False
    cb1 = {c["ma"]: c for c in d1["chat_luong"]["canh_bao_chi_tiet"]}
    assert "ANH_KHONG_EXIF" in cb1 and cb1["ANH_KHONG_EXIF"]["cap"] == "can_than"

    # 2. Ghi sha256 vào sổ ảnh mô phỏng -> /api/measure & /api/measure-multi ép la_mo_phong=True, khong_danh_gia_duoc=True
    ghi_so_anh_mo_phong(raw_sach, tmp_path / "sim_no_tag.png", mo_ta_tham_so="test web tra so")
    r2 = client.post("/api/measure", files={"file": ("ten_sach.png", raw_sach, "image/png")}, data={"nhiet_do_do": "25.0"})
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["la_anh_mo_phong"] is True
    assert d2["la_mo_phong"] is True
    assert d2["khong_danh_gia_duoc"] is True
    assert any(c["ma"] == "ANH_MO_PHONG_NHUNG" for c in d2["chat_luong"]["canh_bao_chi_tiet"])

    # 3. Đóng gói giữ data/so_anh_da_xu_ly.csv, loại outputs/so_anh_mo_phong.csv
    fake_proj = tmp_path / "proj_pkg_w0"
    (fake_proj / "data").mkdir(parents=True)
    (fake_proj / "outputs").mkdir(parents=True)
    (fake_proj / "data" / "so_anh_da_xu_ly.csv").write_text("sha256,nguon,thoi_gian,ten_file\nabc,THUC_TE,now,a.jpg\n", encoding="utf-8")
    (fake_proj / "outputs" / "so_anh_mo_phong.csv").write_text("sha256,thoi_gian,duong_dan,mo_ta_tham_so\ndef,now,b.png,sim\n", encoding="utf-8")
    zp = tmp_path / "pkg_w0.zip"
    tao_file_zip_nop_bai(zp, fake_proj)
    dat, _, _ = kiem_tra_goi_zip(zp)
    assert dat is True
    with zipfile.ZipFile(zp, "r") as zf:
        names = set(zf.namelist())
    assert "data/so_anh_da_xu_ly.csv" in names
    assert "outputs/so_anh_mo_phong.csv" not in names
