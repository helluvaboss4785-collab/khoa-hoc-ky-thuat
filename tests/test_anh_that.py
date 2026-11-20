"""Kiểm thử pipeline nhập thư mục ảnh thật (Q4) và hồi quy ảnh thật khi có dữ liệu."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import pytest

from core import calibration as cal
from core.measure import do_delta_y_tu_anh
from core.optics import CauHinhQuangHoc
from scripts.xu_ly_thu_muc_anh import phan_tich_ten_file, xu_ly_thu_muc_anh
from sim.synth import ThamSoMoPhong, sinh_anh_mau_mo_phong

ROOT = Path(__file__).resolve().parents[1]
THU_MUC_ANH_THAT = Path(__file__).resolve().parent / "anh_that"
NHAN_CHUAN_THAT = THU_MUC_ANH_THAT / "nhan_chuan.csv"


def test_hoi_quy_anh_that():
    """Chỉ chạy khi nhóm đã đặt ảnh chụp thật và nhan_chuan.csv vào tests/anh_that/."""
    if not NHAN_CHUAN_THAT.exists():
        pytest.skip("chưa có ảnh thật")

    df_nhan = pd.read_csv(NHAN_CHUAN_THAT, encoding="utf-8-sig")
    assert len(df_nhan) > 0, "nhan_chuan.csv không được rỗng"
    for _, row in df_nhan.iterrows():
        img_path = THU_MUC_ANH_THAT / str(row["ten_file"]).strip()
        assert img_path.exists(), f"Thiếu file ảnh thật: {img_path}"
        img = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
        kq = do_delta_y_tu_anh(img, tao_anh_ve=False)
        assert kq.chat_luong.hop_le is True
        err = abs(kq.delta_y_px - float(row["delta_y_chuan_px"]))
        assert err <= float(row["dung_sai_px"]), f"{img_path.name}: sai số {err:.3f} px > {row['dung_sai_px']}"


def test_q4_xu_ly_thu_muc_anh_mo_phong_va_dung_duong_chuan(tmp_path):
    """Q4: Chạy pipeline trên thư mục ảnh MÔ PHỎNG (--nguon MO_PHONG) -> nạp được CSV và dựng đường chuẩn."""
    cfg_op = CauHinhQuangHoc.tu_yaml()
    img_dir = tmp_path / "bo_anh_sim"
    img_dir.mkdir()

    meta_rows = []
    idx = 0
    for me_idx, t_c in enumerate((22.0, 28.0), start=1):
        for s_ppt in (0.0, 10.0, 20.0, 30.0):
            idx += 1
            ten_file = f"sim_{idx:02d}.png"
            mp = sinh_anh_mau_mo_phong(
                ThamSoMoPhong(S_ppt=s_ppt, T_C=t_c, T_tham_chieu_C=t_c, seed=500 + idx),
                cfg=cfg_op,
                gan_watermark=False,
            )
            cv2.imwrite(str(img_dir / ten_file), mp.anh)
            meta_rows.append({
                "ten_file": ten_file,
                "do_man_chuan_ppt": s_ppt,
                "nhiet_do_C": t_c,
                "nhiet_do_tham_chieu_C": t_c,
                "ma_me_pha": f"ME_{me_idx}",
                "ngay_do": "2026-11-20",
                "id_thiet_bi": "SIM_RIG",
                "id_dien_thoai": "SIM_CAM",
                "khoa_ae_af": 1,
                "px_per_mm": 20.0,
            })

    # Thêm 1 ảnh bị bão hòa cháy phẳng để kiểm tra lọc chất lượng và báo cáo
    ten_chay = "sim_chay.png"
    mp_chay = sinh_anh_mau_mo_phong(
        ThamSoMoPhong(S_ppt=20.0, T_C=25.0, cuong_do_dinh_goc=400.0, cho_phep_bao_hoa=True, seed=99),
        cfg=cfg_op,
        gan_watermark=False,
    )
    cv2.imwrite(str(img_dir / ten_chay), mp_chay.anh)
    meta_rows.append({
        "ten_file": ten_chay,
        "do_man_chuan_ppt": 20.0,
        "nhiet_do_C": 25.0,
        "nhiet_do_tham_chieu_C": 25.0,
        "ma_me_pha": "ME_1",
        "ngay_do": "2026-11-20",
        "id_thiet_bi": "SIM_RIG",
        "id_dien_thoai": "SIM_CAM",
        "khoa_ae_af": 1,
        "px_per_mm": 20.0,
    })

    meta_csv = tmp_path / "metadata.csv"
    pd.DataFrame(meta_rows).to_csv(meta_csv, index=False, encoding="utf-8-sig")

    out_csv = tmp_path / "out_cal.csv"
    out_rep = tmp_path / "out_report.csv"
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "xu_ly_thu_muc_anh.py"),
            "--thu-muc", str(img_dir),
            "--nguon", "MO_PHONG",
            "--metadata", str(meta_csv),
            "--out-csv", str(out_csv),
            "--out-report", str(out_rep),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc.returncode == 0, f"Script lỗi: {proc.stderr}"
    assert out_csv.exists() and out_rep.exists()

    df_rep = pd.read_csv(out_rep, encoding="utf-8-sig")
    assert len(df_rep) == 9
    row_chay = df_rep[df_rep["ten_file"] == ten_chay].iloc[0]
    assert bool(row_chay["hop_le"]) is False
    assert row_chay["trang_thai"] == "LOAI_CHAT_LUONG"

    df_cal = cal.doc_csv_hieu_chuan(out_csv)
    assert len(df_cal) == 8
    assert cal.xac_dinh_nguon_du_lieu(df_cal) == cal.NHAN_MO_PHONG
    bc = cal.dung_duong_chuan(df_cal, cal.CauHinhHieuChuan.tu_yaml())
    assert bc.mo_hinh.la_mo_phong is True
    assert bc.mo_hinh.R2 > 0.999


def test_q4_thieu_nguon_thoat_loi_va_tu_ten_file_roi_fallback(tmp_path):
    """Q4: Thiếu --nguon phải thoát lỗi; --tu-ten-file sai cú pháp báo lỗi rõ; roi.csv cứu khung fallback."""
    # 1. Thiếu --nguon -> argparse báo lỗi rõ và thoát khác 0
    proc_missing = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "xu_ly_thu_muc_anh.py"), "--thu-muc", str(tmp_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc_missing.returncode != 0
    assert "--nguon" in proc_missing.stderr

    # 2. Kiểm tra phân tích tên file đúng và từ chối tên file sai cú pháp
    assert phan_tich_ten_file("20_28_01.jpg") == (20.0, 28.0, 1)
    assert phan_tich_ten_file("15.5_24.5_03.png") == (15.5, 24.5, 3)
    with pytest.raises(ValueError, match="không khớp mẫu"):
        phan_tich_ten_file("anh_ao_tom_01.jpg")

    # 3. Chế độ --tu-ten-file + roi.csv fallback khi nền rối làm auto-ROI thất bại
    img_dir = tmp_path / "tu_ten"
    img_dir.mkdir()
    cfg_op = CauHinhQuangHoc.tu_yaml()
    mp = sinh_anh_mau_mo_phong(ThamSoMoPhong(S_ppt=20.0, T_C=28.0, seed=12), cfg=cfg_op, gan_watermark=False)
    cv2.imwrite(str(img_dir / "20_28_01.png"), mp.anh)

    # Ảnh thứ hai thêm khối sáng nhiễu ở góc để kiểm fallback ROI
    anh_roi = mp.anh.copy()
    anh_roi[240:285, 20:380] = 240
    cv2.imwrite(str(img_dir / "20_28_02.png"), anh_roi)
    roi_csv = tmp_path / "roi.csv"
    pd.DataFrame([
        {
            "ten_file": "20_28_02.png",
            "roi_tc": "40,130,10,190",
            "roi_mau": "140,230,210,390",
        }
    ]).to_csv(roi_csv, index=False, encoding="utf-8-sig")

    df_cal, df_rep, _, _ = xu_ly_thu_muc_anh(
        thu_muc=img_dir,
        nguon="MO_PHONG",
        roi_csv=roi_csv,
        tu_ten_file=True,
    )
    assert len(df_cal) == 2
    assert len(df_rep) == 2
    assert (df_cal[cal.COT_NGUON] == "MO_PHONG").all()
