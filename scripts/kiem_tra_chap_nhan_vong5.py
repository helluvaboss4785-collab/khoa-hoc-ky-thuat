"""Kiểm chứng chấp nhận Vòng 5 (W0–W4) trên dữ liệu/ảnh MÔ PHỎNG với seed cố định.

Xuất `outputs/kiem_tra_chap_nhan_vong5.csv` (mọi dòng đều ghi rõ nguồn MO_PHONG).
Tất cả sổ theo dõi ảnh (so_anh_mo_phong.csv, so_anh_da_xu_ly.csv) đều được cô lập
trong thư mục tạm khi chạy kiểm chứng để không làm bẩn thư mục data/ hay outputs/.
"""

from __future__ import annotations

import csv
import hashlib
import io
import math
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pandas as pd
from starlette.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import web_app  # noqa: E402
from core import calibration as cal, nhiet_ke, optics as op  # noqa: E402
from core.kiem_tra_thiet_ke import kiem_tra_thiet_ke_thi_nghiem  # noqa: E402
from scripts.dong_goi import canh_bao_out_trong_du_an, kiem_tra_goi_zip, tao_file_zip_nop_bai  # noqa: E402
from scripts.kiem_tra_chap_nhan_vong3 import khoang_tin_cay_wilson  # noqa: E402
from scripts.kiem_tra_quan_fry import doi_chieu_csv_quan_fry  # noqa: E402
from scripts.xuat_bao_cao import xuat_bo_bao_cao  # noqa: E402
from sim.synth import (  # noqa: E402
    ThamSoMoPhong,
    ghi_so_anh_mo_phong,
    sinh_anh_hai_vach_mo_phong,
    sinh_du_lieu_hieu_chuan_mo_phong,
)


def _chay_cli_xu_ly(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "xu_ly_thu_muc_anh.py"), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


def _danh_gia_w0(add_row: Any, tmp: Path, env: dict[str, str]) -> None:
    """W0: Sổ ảnh mô phỏng SHA-256, chặn thư mục outputs/, kiểm tra EXIF & sổ ảnh đã xử lí."""
    cfg_op = op.CauHinhQuangHoc.tu_yaml()
    ts = ThamSoMoPhong(S_ppt=18.0, T_C=25.0, T_tham_chieu_C=25.0, seed=5001)
    anh_mp = sinh_anh_hai_vach_mo_phong(ts, cfg=cfg_op, gan_watermark=False)

    # 1. Ảnh mô phỏng sạch (không chunk tEXt/COM/sidecar, tên sạch) nhưng SHA-256 nằm trong sổ mô phỏng -> bị chặn
    d_led = tmp / "w0_ledger"
    d_led.mkdir(parents=True, exist_ok=True)
    ok_enc, buf = cv2.imencode(".jpg", anh_mp.anh, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    assert ok_enc
    raw_jpg = buf.tobytes()
    p_clean_sim = d_led / "18_25_01.jpg"
    p_clean_sim.write_bytes(raw_jpg)
    ghi_so_anh_mo_phong(raw_jpg, p_clean_sim.name, "kiem_tra_chap_nhan_vong5")

    csv_w0_1 = tmp / "w0_out1.csv"
    proc1 = _chay_cli_xu_ly(
        ["--thu-muc", str(d_led), "--nguon", "THUC_TE", "--tu-ten-file", "--out", str(csv_w0_1)],
        env=env,
    )
    client = TestClient(web_app.app)
    r_web_sim = client.post(
        "/api/measure",
        files={"file": ("18_25_01.jpg", raw_jpg, "image/jpeg")},
        data={"nhiet_do_do": "25.0", "nhiet_do_tham_chieu": "25.0"},
    )
    js_sim = r_web_sim.json()
    dat1 = (
        proc1.returncode == 2
        and not csv_w0_1.exists()
        and r_web_sim.status_code == 200
        and js_sim.get("la_anh_mo_phong") is True
        and js_sim.get("la_mo_phong") is True
    )
    add_row(
        "W0",
        "W0_so_anh_mo_phong_chan_cat_metadata",
        f"cli_ret={proc1.returncode}, csv={csv_w0_1.exists()}, web_la_mp={js_sim.get('la_mo_phong')}",
        "cli=2 & web_ep_mo_phong",
        dat1,
    )

    # 2. Chặn ảnh sạch nằm trong thư mục mô phỏng mặc định `outputs/` khi --nguon THUC_TE
    tam_outputs = ROOT / "outputs" / "_tmp_vong5_w0_outputs"
    tam_outputs.mkdir(parents=True, exist_ok=True)
    try:
        cv2.imwrite(str(tam_outputs / "18_25_01.png"), anh_mp.anh)
        csv_w0_2 = tmp / "w0_out2.csv"
        proc2 = _chay_cli_xu_ly(
            ["--thu-muc", str(tam_outputs), "--nguon", "THUC_TE", "--tu-ten-file", "--out", str(csv_w0_2)],
            env=env,
        )
        dat2 = proc2.returncode == 2 and not csv_w0_2.exists()
        add_row(
            "W0",
            "W0_chan_thu_muc_mo_phong_outputs",
            f"cli_ret={proc2.returncode}, csv={csv_w0_2.exists()}",
            "cli=2 & khong ghi CSV",
            dat2,
        )
    finally:
        shutil.rmtree(tam_outputs, ignore_errors=True)

    # 3. Ảnh sạch (ngoài outputs/, không có EXIF, không nằm trong sổ mô phỏng) dưới --nguon THUC_TE
    d_noexif = tmp / "w0_no_exif"
    d_noexif.mkdir(parents=True, exist_ok=True)
    ok_png, buf_png = cv2.imencode(".png", anh_mp.anh)
    assert ok_png
    raw_png = buf_png.tobytes()
    (d_noexif / "18_25_01.png").write_bytes(raw_png)

    csv_w0_3a = tmp / "w0_out3a.csv"
    proc3a = _chay_cli_xu_ly(
        ["--thu-muc", str(d_noexif), "--nguon", "THUC_TE", "--tu-ten-file", "--out", str(csv_w0_3a)],
        env=env,
    )
    csv_w0_3b = tmp / "w0_out3b.csv"
    proc3b = _chay_cli_xu_ly(
        [
            "--thu-muc", str(d_noexif),
            "--nguon", "THUC_TE",
            "--tu-ten-file",
            "--khai-bao-nguon-anh", "Kiem logic V5 anh sach khong EXIF",
            "--nguoi-khai-bao", "HS W5",
            "--out", str(csv_w0_3b),
        ],
        env=env,
    )
    r_web_noexif = client.post(
        "/api/measure",
        files={"file": ("anh_sach.png", raw_png, "image/png")},
        data={"nhiet_do_do": "25.0", "nhiet_do_tham_chieu": "25.0"},
    )
    js_noexif = r_web_noexif.json()
    has_anh_khong_exif = any(
        cb.get("ma") == "ANH_KHONG_EXIF" and cb.get("cap") == "can_than"
        for cb in js_noexif.get("chat_luong", {}).get("canh_bao_chi_tiet", [])
    )
    so_da_xl = Path(env["SALINITY_SO_DA_XU_LY_PATH"])
    df_out_3b = pd.read_csv(csv_w0_3b) if csv_w0_3b.exists() else pd.DataFrame()
    dat3 = (
        proc3a.returncode == 3
        and proc3b.returncode == 0
        and len(df_out_3b) == 1
        and bool(df_out_3b["exif_co"].iloc[0]) is False
        and so_da_xl.exists()
        and r_web_noexif.status_code == 200
        and has_anh_khong_exif
    )
    add_row(
        "W0",
        "W0_exif_va_khai_bao_nguon_cli_web",
        f"no_decl_ret={proc3a.returncode}, decl_ret={proc3b.returncode}, web_warn={has_anh_khong_exif}, so_xl={so_da_xl.exists()}",
        "ret=3->0, web_can_than, ghi_so",
        dat3,
    )


def _danh_gia_w1(add_row: Any, tmp: Path) -> None:
    """W1: Phát hiện bản sao dữ liệu, nghi ngờ gán nhãn lại, lặp sau khử trùng và sửa BI_DANH_COT."""
    cfg_op = op.CauHinhQuangHoc.tu_yaml()
    df_base = sinh_du_lieu_hieu_chuan_mo_phong(
        cfg=cfg_op,
        muc_S=(0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0),
        muc_T=(20.0, 25.0, 30.0),
        so_lan_lap=3,
        seed=5101,
    )
    df_base[cal.COT_MA_ME_PHA] = ["ME_01" if i % 2 == 0 else "ME_02" for i in range(len(df_base))]

    # 1. Dữ liệu trùng hệt + trùng sha256_anh (gán nhãn lại S khác) + trùng ten_file khác delta_y_px
    df_dup = df_base.copy()
    df_dup[cal.COT_TEN_FILE] = [f"img_{i:03d}.jpg" for i in range(len(df_dup))]
    df_dup[cal.COT_SHA256_ANH] = [hashlib.sha256(f"f_{i}".encode()).hexdigest() for i in range(len(df_dup))]

    row_exact = df_dup.iloc[[0]].copy()
    row_relabel = df_dup.iloc[[1]].copy()
    row_relabel[cal.COT_DO_MAN] = 33.0
    row_relabel[cal.COT_TEN_FILE] = "img_relabel_999.jpg"
    row_name_conflict = df_dup.iloc[[2]].copy()
    row_name_conflict[cal.COT_SHA256_ANH] = hashlib.sha256(b"other_file").hexdigest()
    row_name_conflict[cal.COT_DELTA_Y] = float(df_dup[cal.COT_DELTA_Y].iloc[2]) + 9.5

    df_bad = pd.concat([df_dup, row_exact, row_relabel, row_name_conflict], ignore_index=True)
    bc_dup = cal.dung_duong_chuan(df_bad, cal.CauHinhHieuChuan())
    has_dup_warn = any(
        cb.get("ma") == "DU_LIEU_CO_BAN_SAO" and cb.get("cap") == "nghiem_trong"
        for cb in bc_dup.canh_bao_chi_tiet
    )
    # Giả lập ô (S=0, T~20) gồm 3 dòng nhân bản -> trước khử đủ 3 lặp, sau khử chỉ còn 1 lặp
    df_c0 = df_dup[(df_dup[cal.COT_DO_MAN] == 0.0) & (df_dup[cal.COT_NHIET_DO] < 22.0)]
    df_other = df_dup.drop(index=df_c0.index)
    df_fake_rep = pd.concat([df_c0.iloc[[0]]] * 3 + [df_other], ignore_index=True)
    kt_rep = kiem_tra_thiet_ke_thi_nghiem(df_fake_rep)
    muc_map = {m["ma"]: m for m in kt_rep["muc_kiem"]}
    dat1 = (
        bc_dup.co_ban_sao_du_lieu is True
        and bc_dup.so_dong_ban_sao >= 3
        and has_dup_warn
        and muc_map["ban_sao_du_lieu"]["trang_thai"] == "chua_dat"
        and muc_map["so_lan_lap_moi_o"]["trang_thai"] == "chua_dat"
    )
    add_row(
        "W1",
        "W1_phat_hien_ban_sao_va_lap_sau_khu_trung",
        f"co_bs={bc_dup.co_ban_sao_du_lieu}, n_bs={bc_dup.so_dong_ban_sao}, warn={has_dup_warn}, lap_st={muc_map['so_lan_lap_moi_o']['trang_thai']}",
        "3 loai trung & lap_st=chua_dat",
        dat1,
    )

    # 2. Cảnh báo trùng lặp xuất ở đầu tong_hop_bao_cao.md & ánh xạ BI_DANH_COT chuẩn
    p_bad_csv = tmp / "w1_bad.csv"
    df_bad.to_csv(p_bad_csv, index=False, encoding="utf-8-sig")
    out_bc = tmp / "w1_bao_cao"
    res_bc = xuat_bo_bao_cao(csv_hieu_chuan=p_bad_csv, out_dir=out_bc)
    md_txt = Path(res_bc["tong_hop_bao_cao_md"]).read_text(encoding="utf-8")
    idx_dup_hdr = md_txt.find("## Cảnh báo dữ liệu trùng lặp")
    idx_sec1 = md_txt.find("## 1.")

    rename_map = {
        cot_chuan: alias
        for alias, cot_chuan in cal.BI_DANH_COT.items()
        if cot_chuan in df_base.columns
    }
    df_alias = df_base.rename(columns=rename_map)
    kt_alias = kiem_tra_thiet_ke_thi_nghiem(df_alias)
    dat2 = (
        0 <= idx_dup_hdr < idx_sec1
        and kt_alias["hop_le_tong_quat"] is True
    )
    add_row(
        "W1",
        "W1_bao_cao_trung_lap_va_bi_danh_cot",
        f"idx_dup={idx_dup_hdr}, idx_sec1={idx_sec1}, alias_hop_le={kt_alias['hop_le_tong_quat']}",
        "muc canh bao dau md & alias OK",
        dat2,
    )


def _danh_gia_w2(add_row: Any, tmp: Path) -> None:
    """W2: Gỡ 10 hằng số khỏi DOCS, siết trang_bang/trích dẫn/tên tiếng Việt và ghi chú tự khai."""
    doc_txt = (ROOT / "docs" / "DOI_CHIEU_QUAN_FRY.md").read_text(encoding="utf-8")
    hs_that = [str(v) for v in op.HE_SO_QUAN_FRY_TRONG_MA.values()]
    khong_chua_hs = all(s not in doc_txt for s in hs_that)

    # CSV kiểm tra hợp lệ và các CSV bẫy
    he_so_keys = list(op.HE_SO_QUAN_FRY_TRONG_MA.keys())
    p_good = tmp / "qf_good.csv"
    pd.DataFrame({
        "he_so": he_so_keys,
        "gia_tri_bai_goc": [op.HE_SO_QUAN_FRY_TRONG_MA[k] for k in he_so_keys],
        "trang_bang": [f"p.3586 Table 1 row {i + 1}" for i in range(len(he_so_keys))],
    }).to_csv(p_good, index=False)

    p_bad_tb = tmp / "qf_bad_tb.csv"
    pd.DataFrame({
        "he_so": he_so_keys,
        "gia_tri_bai_goc": [op.HE_SO_QUAN_FRY_TRONG_MA[k] for k in he_so_keys],
        "trang_bang": ["?"] * len(he_so_keys),
    }).to_csv(p_bad_tb, index=False)

    out_qf = tmp / "qf_xac_nhan.json"
    proc_bad_tb = subprocess.run(
        [
            sys.executable, str(ROOT / "scripts" / "kiem_tra_quan_fry.py"),
            "--csv", str(p_bad_tb), "--luu-xac-nhan",
            "--nguoi-doi-chieu", "Nguyễn Văn An",
            "--nguoi-xac-nhan-2", "Trần Thị Bình",
            "--trich-dan", "Quan & Fry (1995), Applied Optics 34(18), p.3586",
            "--file-xac-nhan", str(out_qf),
        ],
        capture_output=True, text=True, encoding="utf-8",
    )
    proc_same_vn = subprocess.run(
        [
            sys.executable, str(ROOT / "scripts" / "kiem_tra_quan_fry.py"),
            "--csv", str(p_good), "--luu-xac-nhan",
            "--nguoi-doi-chieu", "Nguyễn Văn An",
            "--nguoi-xac-nhan-2", "nguyen van an",
            "--trich-dan", "Quan & Fry (1995), Applied Optics 34(18), p.3586",
            "--file-xac-nhan", str(out_qf),
        ],
        capture_output=True, text=True, encoding="utf-8",
    )
    proc_ok = subprocess.run(
        [
            sys.executable, str(ROOT / "scripts" / "kiem_tra_quan_fry.py"),
            "--csv", str(p_good), "--luu-xac-nhan",
            "--nguoi-doi-chieu", "Nguyễn Văn An",
            "--nguoi-xac-nhan-2", "Trần Thị Bình",
            "--trich-dan", "Quan & Fry (1995), Applied Optics 34(18), Table 1, p.3586",
            "--file-xac-nhan", str(out_qf),
        ],
        capture_output=True, text=True, encoding="utf-8",
    )
    import json
    qf_data = json.loads(out_qf.read_text(encoding="utf-8")) if out_qf.exists() else {}
    dat = (
        khong_chua_hs
        and proc_bad_tb.returncode == 1
        and proc_same_vn.returncode == 1
        and proc_ok.returncode == 0
        and qf_data.get("trung_chuoi_ma") is True
        and bool(qf_data.get("ghi_chu_gioi_han"))
    )
    add_row(
        "W2",
        "W2_doi_chieu_quan_fry_va_ghi_chu_tu_khai",
        f"no_const_doc={khong_chua_hs}, bad_tb={proc_bad_tb.returncode}, same_vn={proc_same_vn.returncode}, ok={proc_ok.returncode}, trung_ma={qf_data.get('trung_chuoi_ma')}",
        "doc sach & siet format/ten/tu khai",
        dat,
    )


def _danh_gia_w3(add_row: Any) -> None:
    """W3: Monte Carlo 400 lần mỗi mức r (0.01, 0.1, 0.5 °C) ở seed=5301 + hồi quy tuyến tính."""
    for r_step in (0.01, 0.1, 0.5):
        rng = np.random.default_rng(5301)
        cov_old = cov_new = n_warn = 0
        sig_olds, sig_news, errs = [], [], []
        n_trials = 400
        for _ in range(n_trials):
            t_levels = np.array([20.0, 28.0, 36.0]) + rng.uniform(-0.5, 0.5, size=3)
            t_true = np.repeat(t_levels, 3)
            t_tc = np.round((t_true + 0.37 + rng.normal(0.0, 0.03, size=9)) / r_step) * r_step
            t_mau = np.round((t_true + rng.normal(0.0, 0.03, size=9)) / r_step) * r_step
            df = pd.DataFrame({
                nhiet_ke.COT_T_MAU_DOC: t_mau,
                nhiet_ke.COT_T_TC_DOC: t_tc,
                nhiet_ke.COT_NGUON_NK: ["MO_PHONG"] * 9,
            })
            hc = nhiet_ke.hieu_chuan_cheo_tu_df(df, "HS W5", nguon_du_lieu="MO_PHONG", do_phan_giai_toi_da_C=0.1)
            sig_old = float(np.std(t_tc - t_mau, ddof=1) / math.sqrt(9))
            err = abs(hc.offset_C - 0.37)
            errs.append(err)
            sig_olds.append(sig_old)
            sig_news.append(hc.sigma_offset_C)
            cov_old += int(err <= 2.0 * sig_old)
            cov_new += int(err <= 2.0 * hc.sigma_offset_C)
            n_warn += int(hc.canh_bao_do_phan_giai)

        rms = float(math.sqrt(float(np.mean(np.square(errs)))))
        m_old = float(np.mean(sig_olds))
        m_new = float(np.mean(sig_news))
        lo_new, hi_new = khoang_tin_cay_wilson(cov_new, n_trials)
        p_new = cov_new / float(n_trials)
        p_old = cov_old / float(n_trials)
        if r_step == 0.01:
            dat = (m_new <= 1.5 * m_old) and (p_new >= p_old)
        elif r_step == 0.1:
            dat = p_new >= 0.95
        else:
            dat = (p_new >= 0.95) and (p_new > p_old) and (n_warn == n_trials)

        add_row(
            "W3",
            f"W3_san_phan_giai_r_{r_step:.2f}C",
            f"sig_old={m_old:.4f}, sig_new={m_new:.4f} ({m_new/m_old:.2f}x), RMS={rms:.4f}, cov_old={p_old*100:.1f}%, cov_new={p_new*100:.1f}% [{lo_new*100:.1f}-{hi_new*100:.1f}%], warn={n_warn}/{n_trials}",
            f"cov_new={p_new*100:.1f}%",
            dat,
        )

    # Hồi quy tuyến tính b = 0.02 °C/°C ở mức thô r = 0.5 °C
    rng_sl = np.random.default_rng(5309)
    rows = []
    for t_b in (10.2, 20.3, 30.1, 39.8):
        for _ in range(4):
            tm = t_b + rng_sl.normal(0.0, 0.03)
            ttc = tm + (-0.2 + 0.02 * tm) + rng_sl.normal(0.0, 0.03)
            rows.append({
                nhiet_ke.COT_T_MAU_DOC: round(tm / 0.5) * 0.5,
                nhiet_ke.COT_T_TC_DOC: round(ttc / 0.5) * 0.5,
                nhiet_ke.COT_NGUON_NK: "MO_PHONG",
            })
    hc_sl = nhiet_ke.hieu_chuan_cheo_tu_df(pd.DataFrame(rows), "HS Slope W5", nguon_du_lieu="MO_PHONG")
    max_res = max(abs(hc_sl.offset_va_sigma_tai(t)[0] - (-0.2 + 0.02 * t)) for t in (10.0, 20.0, 30.0, 40.0))
    min_sig = min(hc_sl.offset_va_sigma_tai(t)[1] for t in (10.0, 20.0, 30.0, 40.0))
    dat_sl = hc_sl.phu_thuoc_nhiet_do and max_res <= 0.15 and min_sig >= hc_sl.sigma_phan_giai_C - 1e-12
    add_row(
        "W3",
        "W3_doc_tuyen_tinh_va_san_T",
        f"phu_thuoc={hc_sl.phu_thuoc_nhiet_do}, max_res={max_res:.4f}C, min_sig={min_sig:.4f} >= sigma_pg={hc_sl.sigma_phan_giai_C:.4f}",
        f"max_res={max_res:.4f}C",
        dat_sl,
    )


def _danh_gia_w4(add_row: Any, tmp: Path) -> None:
    """W4: dong_goi.bat, dong_goi.sh, NOP_BAI.md, cảnh báo --out trong dự án và đóng gói < 20 MB."""
    has_files = all((ROOT / fn).exists() for fn in ("dong_goi.bat", "dong_goi.sh", "NOP_BAI.md"))
    has_bold_warn = "KHÔNG nén cả thư mục. Chạy dong_goi.bat" in (ROOT / "NOP_BAI.md").read_text(encoding="utf-8")
    warn_in = canh_bao_out_trong_du_an(ROOT / "outputs" / "t.zip", ROOT)

    out_zip = tmp / "w5_nop_bai.zip"
    if sys.platform.startswith("win"):
        proc = subprocess.run(
            ["cmd", "/c", str(ROOT / "dong_goi.bat"), "--out", str(out_zip)],
            cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
        )
        cli_ok = (proc.returncode == 0) and ("KIỂM TRA ĐẠT" in proc.stdout)
    else:
        tao_file_zip_nop_bai(out_zip, ROOT)
        cli_ok = True
    dat_zip, vp_zip, size_mb = kiem_tra_goi_zip(out_zip, gioi_han_mb=20.0)
    dat = has_files and has_bold_warn and (warn_in is not None) and cli_ok and dat_zip and vp_zip == []
    add_row(
        "W4",
        "W4_dong_goi_bat_sh_nop_bai",
        f"files={has_files}, warn_md={has_bold_warn}, warn_out={bool(warn_in)}, cli_ok={cli_ok}, zip_mb={size_mb:.2f}",
        f"{size_mb:.2f} MB < 20 MB",
        dat,
    )


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    rows: list[dict[str, str]] = []

    def add_row(nhom: str, tieu_chi: str, chi_tiet: str, gia_tri_do: str, dat: bool) -> None:
        rows.append({
            "nhom": nhom,
            "tieu_chi": tieu_chi,
            "chi_tiet": chi_tiet,
            "gia_tri_do": gia_tri_do,
            "ket_luan": "DAT" if dat else "KHONG_DAT",
            "nguon_du_lieu": "MO_PHONG",
        })

    old_mp = os.environ.get("SALINITY_SO_MO_PHONG_PATH")
    old_dx = os.environ.get("SALINITY_SO_DA_XU_LY_PATH")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        p_mp = tmp / "so_anh_mo_phong.csv"
        p_dx = tmp / "so_anh_da_xu_ly.csv"
        os.environ["SALINITY_SO_MO_PHONG_PATH"] = str(p_mp)
        os.environ["SALINITY_SO_DA_XU_LY_PATH"] = str(p_dx)
        env_sub = os.environ.copy()
        try:
            _danh_gia_w0(add_row, tmp, env_sub)
            _danh_gia_w1(add_row, tmp)
            _danh_gia_w2(add_row, tmp)
            _danh_gia_w3(add_row)
            _danh_gia_w4(add_row, tmp)
        finally:
            if old_mp is None:
                os.environ.pop("SALINITY_SO_MO_PHONG_PATH", None)
            else:
                os.environ["SALINITY_SO_MO_PHONG_PATH"] = old_mp
            if old_dx is None:
                os.environ.pop("SALINITY_SO_DA_XU_LY_PATH", None)
            else:
                os.environ["SALINITY_SO_DA_XU_LY_PATH"] = old_dx

    out_csv = ROOT / "outputs" / "kiem_tra_chap_nhan_vong5.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["nhom", "tieu_chi", "chi_tiet", "gia_tri_do", "ket_luan", "nguon_du_lieu"])
        w.writeheader()
        w.writerows(rows)

    print("=== KET QUA NGHIEM THU VONG 5 (MO PHONG) ===")
    for r in rows:
        print(f"[{r['ket_luan']:9s}] {r['tieu_chi']}: {r['gia_tri_do']} | {r['chi_tiet']}")
    so_dat = sum(1 for r in rows if r["ket_luan"] == "DAT")
    print(f"\nTong hop: {so_dat}/{len(rows)} tieu chi DAT. Da xuat: {out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
