"""Kiểm chứng chấp nhận Vòng 4 (V0–V7) trên dữ liệu/ảnh MÔ PHỎNG với seed cố định.

Xuất `outputs/kiem_tra_chap_nhan_vong4.csv` (mọi dòng đều ghi rõ nguồn MO_PHONG).
Mọi con số báo cáo đều đo từ lần chạy thực tế, không chọn lại seed hay nới lỏng tiêu chí.
"""

from __future__ import annotations

import csv
import io
import math
import subprocess
import sys
import tempfile
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
from core import calibration as cal, optics as op  # noqa: E402
from core.kiem_tra_thiet_ke import kiem_tra_thiet_ke_thi_nghiem, kiem_tra_thiet_ke_tu_csv  # noqa: E402
from core.nhiet_ke import (  # noqa: E402
    COT_NGUON_NK,
    COT_T_MAU_DOC,
    COT_T_TC_DOC,
    hieu_chuan_cheo_tu_df,
)
from core.trang_thai_cau_hinh import liet_ke_tham_so_chua_xac_nhan  # noqa: E402
from scripts.kiem_tra_chap_nhan_vong3 import khoang_tin_cay_wilson  # noqa: E402
from scripts.kiem_tra_quan_fry import CANH_BAO_KHONG_CHEP_TU_MA, doi_chieu_csv_quan_fry  # noqa: E402
from sim.synth import (  # noqa: E402
    ThamSoMoPhong,
    doc_nhan_mo_phong,
    luu_anh_mo_phong_jpeg,
    luu_anh_mo_phong_png,
    sinh_anh_hai_vach_mo_phong,
    sinh_du_lieu_hieu_chuan_mo_phong,
)


def _chay_cli_xu_ly_thuc_te(thu_muc: Path, csv_out: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "xu_ly_thu_muc_anh.py"),
            "--thu-muc",
            str(thu_muc),
            "--nguon",
            "THUC_TE",
            "--tu-ten-file",
            "--out",
            str(csv_out),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _danh_gia_v0(add_row: Any) -> None:
    """V0: 6 tình huống chống gắn nhãn sai nguồn dữ liệu trên dữ liệu MÔ PHỎNG."""
    cfg_op = op.CauHinhQuangHoc.tu_yaml()
    ts = ThamSoMoPhong(S_ppt=20.0, T_C=25.0, T_tham_chieu_C=25.0, seed=4001)
    anh_mp = sinh_anh_hai_vach_mo_phong(ts, cfg=cfg_op, gan_watermark=False)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        # 1. PNG nhúng chunk tEXt (xóa .json và đổi tên sạch)
        d_png = tmp / "case_png"
        p_png = luu_anh_mo_phong_png(anh_mp, d_png / "tmp_sim.png", gan_watermark=False)
        p_png.with_suffix(".json").unlink(missing_ok=True)
        p_png_clean = d_png / "20_25_01.png"
        p_png.rename(p_png_clean)
        csv1 = tmp / "out1.csv"
        proc1 = _chay_cli_xu_ly_thuc_te(d_png, csv1)
        dat1 = doc_nhan_mo_phong(p_png_clean) and proc1.returncode == 2 and not csv1.exists()
        add_row("V0", "V0_png_tEXt_chan", f"ret={proc1.returncode}, csv_ton_tai={csv1.exists()}", "nhung=True & bi_chan", dat1)

        # 2. JPEG nhúng đoạn COM (xóa .json và đổi tên sạch)
        d_jpg = tmp / "case_jpg"
        p_jpg = luu_anh_mo_phong_jpeg(anh_mp, d_jpg / "tmp_sim.jpg", gan_watermark=False)
        p_jpg.with_suffix(".json").unlink(missing_ok=True)
        p_jpg_clean = d_jpg / "20_25_01.jpg"
        p_jpg.rename(p_jpg_clean)
        csv2 = tmp / "out2.csv"
        proc2 = _chay_cli_xu_ly_thuc_te(d_jpg, csv2)
        dat2 = doc_nhan_mo_phong(p_jpg_clean) and proc2.returncode == 2 and not csv2.exists()
        add_row("V0", "V0_jpeg_COM_chan", f"ret={proc2.returncode}, csv_ton_tai={csv2.exists()}", "nhung=True & bi_chan", dat2)

        # 3. Sidecar .json simulated=true trên PNG thô không nhúng
        d_json = tmp / "case_json"
        d_json.mkdir(parents=True)
        ok, raw_clean = cv2.imencode(".png", anh_mp.anh)
        assert ok
        (d_json / "20_25_01.png").write_bytes(raw_clean.tobytes())
        (d_json / "20_25_01.json").write_text('{"simulated": true}', encoding="utf-8")
        csv3 = tmp / "out3.csv"
        proc3 = _chay_cli_xu_ly_thuc_te(d_json, csv3)
        add_row("V0", "V0_sidecar_json_chan", f"ret={proc3.returncode}, csv_ton_tai={csv3.exists()}", "bi_chan", proc3.returncode == 2 and not csv3.exists())

        # 4. Tên file chứa MO_PHONG / SIMULATED
        d_name = tmp / "case_name"
        d_name.mkdir(parents=True)
        (d_name / "mau_MO_PHONG_20_25_01.png").write_bytes(raw_clean.tobytes())
        csv4 = tmp / "out4.csv"
        proc4 = _chay_cli_xu_ly_thuc_te(d_name, csv4)
        add_row("V0", "V0_ten_file_MO_PHONG_chan", f"ret={proc4.returncode}, csv_ton_tai={csv4.exists()}", "bi_chan", proc4.returncode == 2 and not csv4.exists())

        # 5. API /api/measure phát hiện nhãn nhúng (chỉ kiểm logic qua TestClient)
        with TestClient(web_app.app) as client:
            resp = client.post(
                "/api/measure",
                files={"file": ("anh_ten_sach.png", p_png_clean.read_bytes(), "image/png")},
                data={"nhiet_do_do": "25.0"},
            )
            j = resp.json() if resp.status_code == 200 else {}
            ds_cb = [c.get("ma") for c in (j.get("chat_luong", {}).get("canh_bao_chi_tiet") or [])]
            dat5 = (
                resp.status_code == 200
                and j.get("la_mo_phong") is True
                and j.get("phat_hien_nhan_mo_phong_anh") is True
                and j.get("khong_danh_gia_duoc") is True
                and "ANH_MO_PHONG_NHUNG" in ds_cb
            )
            add_row("V0", "V0_api_measure_nhan_nhung", f"http={resp.status_code}, la_mo_phong={j.get('la_mo_phong')}, cb={ds_cb}", "ep la_mo_phong & chan", dat5)

        # 6. Ảnh sạch không nhãn nhúng trả doc_nhan_mo_phong == False (chỉ kiểm logic, dữ liệu vẫn mô phỏng)
        sach_bytes = raw_clean.tobytes()
        dat6 = doc_nhan_mo_phong(sach_bytes) is False
        add_row("V0", "V0_anh_sach_khong_nhung", f"doc_nhan_mo_phong={doc_nhan_mo_phong(sach_bytes)}", "False (khong duong tinh gia)", dat6)


def _chay_kich_ban_v1(
    seed: int,
    slope_true: float,
    intercept_true: float,
    n_cal_per_T: int,
    mh: cal.MoHinhHieuChuan,
    cfg_op: op.CauHinhQuangHoc,
    n_test: int = 400,
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    t_levels_cal = (15.0, 25.0, 35.0)
    cal_rows = []
    for t_true in t_levels_cal:
        off_true = intercept_true + slope_true * t_true
        for _ in range(n_cal_per_T):
            t_m_doc = t_true + float(rng.normal(0.0, 0.08))
            t_tc_doc = t_true + off_true + float(rng.normal(0.0, 0.08))
            cal_rows.append({
                COT_T_MAU_DOC: t_m_doc,
                COT_T_TC_DOC: t_tc_doc,
                COT_NGUON_NK: "MO_PHONG",
            })
    df_cal_nk = pd.DataFrame(cal_rows)
    hc_nk = hieu_chuan_cheo_tu_df(df_cal_nk, nguoi_thuc_hien="Kiem thu V4", nguon_du_lieu="MO_PHONG")

    s_errs_all: list[float] = []
    cov_after = 0
    n_ok_after = 0
    chan_before = 0
    chan_after = 0

    for _ in range(n_test):
        S_that = float(rng.uniform(2.0, 33.0))
        T_that = float(rng.uniform(16.0, 34.0))
        off_true = intercept_true + slope_true * T_that
        # Hai ngăn đang cân bằng nhiệt thật (D_that = 0), nhưng nhiệt kế tc bị lệch off_true
        dy_meas = op.delta_y_vi_sai_px(S_that, T_that, T_that, cfg_op) + float(rng.normal(0.0, 0.05))
        t_m_doc = T_that + float(rng.normal(0.0, 0.2))
        t_tc_doc = T_that + off_true + float(rng.normal(0.0, 0.2))

        kq_trc = cal.uoc_luong_do_man(
            mh=mh,
            delta_y_px=dy_meas,
            T_C=t_m_doc,
            sigma_delta_y_px=0.05,
            sigma_T_C=0.2,
            T_tham_chieu_C=t_tc_doc,
            sigma_T_tham_chieu_C=0.2,
            nguong_lech_T_hai_ngan_C=0.5,
            offset_nhiet_ke_C=0.0,
            sigma_offset_nhiet_ke_C=0.0,
        )
        if kq_trc.chenh_T_ngoai_mo_hinh or kq_trc.ngoai_dai_S or kq_trc.ngoai_dai_T or kq_trc.ngoai_dai_D:
            chan_before += 1

        off_est, sig_est = hc_nk.offset_va_sigma_tai(t_m_doc)
        kq_sau = cal.uoc_luong_do_man(
            mh=mh,
            delta_y_px=dy_meas,
            T_C=t_m_doc,
            sigma_delta_y_px=0.05,
            sigma_T_C=0.2,
            T_tham_chieu_C=t_tc_doc,
            sigma_T_tham_chieu_C=0.2,
            nguong_lech_T_hai_ngan_C=0.5,
            offset_nhiet_ke_C=off_est,
            sigma_offset_nhiet_ke_C=sig_est,
        )
        err = float(kq_sau.S_ppt - S_that)
        s_errs_all.append(err)
        if kq_sau.chenh_T_ngoai_mo_hinh or kq_sau.ngoai_dai_S or kq_sau.ngoai_dai_T or kq_sau.ngoai_dai_D:
            chan_after += 1
        else:
            n_ok_after += 1
            if abs(err) <= kq_sau.U_S_ppt:
                cov_after += 1

    arr = np.asarray(s_errs_all, dtype=float)
    cov_rate = (cov_after / n_ok_after) if n_ok_after > 0 else 0.0
    return {
        "hc": hc_nk,
        "n_test": n_test,
        "n_ok_after": n_ok_after,
        "chan_before": chan_before,
        "chan_after": chan_after,
        "cov_count": cov_after,
        "cov_rate": cov_rate,
        "cov_ci": khoang_tin_cay_wilson(cov_after, n_ok_after),
        "chan_before_ci": khoang_tin_cay_wilson(chan_before, n_test),
        "chan_after_ci": khoang_tin_cay_wilson(chan_after, n_test),
        "mean_err": float(np.mean(arr)),
        "rms_err": float(np.sqrt(np.mean(arr ** 2))),
        "max_err": float(np.max(np.abs(arr))),
    }


def _danh_gia_v1(add_row: Any) -> None:
    """V1: hiệu chuẩn chéo nhiệt kế trên 400 mẫu/kịch bản (seed 4101..4104)."""
    cfg_op = op.CauHinhQuangHoc.tu_yaml()
    df_cal = sinh_du_lieu_hieu_chuan_mo_phong(
        cfg=cfg_op,
        muc_T=(15.0, 25.0, 35.0),
        T_tham_chieu_C=None,
        sigma_delta_y_px=0.04,
        sigma_nhiet_ke_C=0.0,
        seed=4100,
    )
    mh = cal.dung_duong_chuan(df_cal, cal.CauHinhHieuChuan(), bac_ep=1).mo_hinh

    # 1. Offset +0.5 °C
    r1 = _chay_kich_ban_v1(4101, 0.0, 0.5, 4, mh, cfg_op)
    dat1 = r1["cov_rate"] >= 0.95 and r1["chan_after"] < r1["chan_before"]
    add_row(
        "V1",
        "V1_offset_co_dinh_0.5C",
        f"N=400, chan_truoc={r1['chan_before']}/400 [CI {r1['chan_before_ci'][0]*100:.1f}-{r1['chan_before_ci'][1]*100:.1f}%] -> chan_sau={r1['chan_after']}/400 [CI {r1['chan_after_ci'][0]*100:.1f}-{r1['chan_after_ci'][1]*100:.1f}%]",
        f"cov={r1['cov_rate']*100:.1f}% [CI {r1['cov_ci'][0]*100:.1f}-{r1['cov_ci'][1]*100:.1f}%], mean={r1['mean_err']:+.4f}, RMS={r1['rms_err']:.4f}, max={r1['max_err']:.4f}‰",
        dat1,
    )

    # 2. Offset +1.0 °C
    r2 = _chay_kich_ban_v1(4102, 0.0, 1.0, 4, mh, cfg_op)
    dat2 = r2["cov_rate"] >= 0.95 and r2["chan_after"] < r2["chan_before"]
    add_row(
        "V1",
        "V1_offset_co_dinh_1.0C",
        f"N=400, chan_truoc={r2['chan_before']}/400 [CI {r2['chan_before_ci'][0]*100:.1f}-{r2['chan_before_ci'][1]*100:.1f}%] -> chan_sau={r2['chan_after']}/400 [CI {r2['chan_after_ci'][0]*100:.1f}-{r2['chan_after_ci'][1]*100:.1f}%]",
        f"cov={r2['cov_rate']*100:.1f}% [CI {r2['cov_ci'][0]*100:.1f}-{r2['cov_ci'][1]*100:.1f}%], mean={r2['mean_err']:+.4f}, RMS={r2['rms_err']:.4f}, max={r2['max_err']:.4f}‰",
        dat2,
    )

    # 3. Offset tuyến tính -0.2 + 0.02*T
    r3 = _chay_kich_ban_v1(4103, 0.02, -0.2, 6, mh, cfg_op)
    hc3 = r3["hc"]
    dat3 = (
        hc3.phu_thuoc_nhiet_do is True
        and hc3.he_so_b is not None
        and abs(hc3.he_so_b - 0.02) < 0.01
        and r3["cov_rate"] >= 0.95
        and r3["chan_after"] <= r3["chan_before"]
    )
    add_row(
        "V1",
        "V1_offset_tuyen_tinh_0.02",
        f"b_do={hc3.he_so_b:.5f}, phu_thuoc_T={hc3.phu_thuoc_nhiet_do}, chan {r3['chan_before']}->{r3['chan_after']}/400",
        f"cov={r3['cov_rate']*100:.1f}% [CI {r3['cov_ci'][0]*100:.1f}-{r3['cov_ci'][1]*100:.1f}%], RMS={r3['rms_err']:.4f}, max={r3['max_err']:.4f}‰",
        dat3,
    )

    # 4. Cơ sở offset = 0.0 °C (không hồi quy xấu đi)
    r4 = _chay_kich_ban_v1(4104, 0.0, 0.0, 4, mh, cfg_op)
    dat4 = r4["cov_rate"] >= 0.95 and abs(r4["chan_after"] - r4["chan_before"]) <= 10 and abs(r4["hc"].offset_C) < 0.1
    add_row(
        "V1",
        "V1_co_so_offset_0",
        f"off_uoc={r4['hc'].offset_C:+.4f}C, chan {r4['chan_before']}->{r4['chan_after']}/400",
        f"cov={r4['cov_rate']*100:.1f}% [CI {r4['cov_ci'][0]*100:.1f}-{r4['cov_ci'][1]*100:.1f}%], RMS={r4['rms_err']:.4f}, max={r4['max_err']:.4f}‰",
        dat4,
    )

    # 5. Từ chối đầu vào thiếu cặp (<6) hoặc thiếu mức nhiệt (<2)
    tu_choi_cap = False
    try:
        hieu_chuan_cheo_tu_df(
            pd.DataFrame({COT_T_MAU_DOC: [15, 20, 25, 30, 35], COT_T_TC_DOC: [15.5, 20.5, 25.5, 30.5, 35.5], COT_NGUON_NK: ["MO_PHONG"] * 5}),
            nguoi_thuc_hien="Kiem thu", nguon_du_lieu="MO_PHONG",
        )
    except ValueError:
        tu_choi_cap = True

    tu_choi_muc = False
    try:
        hieu_chuan_cheo_tu_df(
            pd.DataFrame({COT_T_MAU_DOC: [25.0] * 8, COT_T_TC_DOC: [25.5] * 8, COT_NGUON_NK: ["MO_PHONG"] * 8}),
            nguoi_thuc_hien="Kiem thu", nguon_du_lieu="MO_PHONG",
        )
    except ValueError:
        tu_choi_muc = True

    add_row("V1", "V1_tu_choi_thieu_du_lieu", f"tu_choi_cap_lt6={tu_choi_cap}, tu_choi_muc_lt2={tu_choi_muc}", "ca hai True", tu_choi_cap and tu_choi_muc)


def _danh_gia_v2(add_row: Any) -> None:
    """V2: 5 tình huống đối chiếu Quan–Fry và 3 trạng thái R7."""
    from core.optics import HE_SO_QUAN_FRY_TRONG_MA

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        p_ok = tmp / "qf_ok.csv"
        with open(p_ok, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["he_so", "gia_tri_bai_goc", "trang_bang"])
            for k, v in HE_SO_QUAN_FRY_TRONG_MA.items():
                w.writerow([k, repr(v), "Applied Optics 34(18), Table 1"])

        p_no_tb = tmp / "qf_no_tb.csv"
        with open(p_no_tb, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["he_so", "gia_tri_bai_goc", "trang_bang"])
            for idx, (k, v) in enumerate(HE_SO_QUAN_FRY_TRONG_MA.items()):
                w.writerow([k, repr(v), "" if idx == 0 else "Table 1"])

        ok_no_tb, _, _ = doi_chieu_csv_quan_fry(p_no_tb)
        add_row("V2", "V2_thieu_trang_bang", f"khop={ok_no_tb}", "False", not ok_no_tb)

        out_json = tmp / "xac_nhan_qf.json"
        ok_no_nd, _, _ = doi_chieu_csv_quan_fry(p_ok, luu_xac_nhan=True, file_xac_nhan=out_json, nguoi_doi_chieu="", trich_dan="Quan & Fry 1995")
        ok_no_td, _, _ = doi_chieu_csv_quan_fry(p_ok, luu_xac_nhan=True, file_xac_nhan=out_json, nguoi_doi_chieu="HS A", trich_dan="")
        add_row("V2", "V2_thieu_nguoi_hoac_trich_dan", f"no_nd={ok_no_nd}, no_td={ok_no_td}, ton_tai={out_json.exists()}", "ca hai bi chan & khong luu", (not ok_no_nd) and (not ok_no_td) and (not out_json.exists()))

        ok_trung, _, _ = doi_chieu_csv_quan_fry(p_ok, luu_xac_nhan=True, file_xac_nhan=out_json, nguoi_doi_chieu="HS A", nguoi_xac_nhan_2="hs a", trich_dan="Quan & Fry 1995")
        add_row("V2", "V2_trung_nguoi_1_va_2", f"khop={ok_trung}", "False", not ok_trung)

        # 3 trạng thái R7: 0 -> 1 -> 2 người
        st0 = liet_ke_tham_so_chua_xac_nhan(ROOT / "config.yaml", xac_nhan_quan_fry_path=tmp / "missing.json")
        ok_1, _, _ = doi_chieu_csv_quan_fry(p_ok, luu_xac_nhan=True, file_xac_nhan=out_json, nguoi_doi_chieu="HS A", trich_dan="Quan & Fry (1995) Table 1")
        st1 = liet_ke_tham_so_chua_xac_nhan(ROOT / "config.yaml", xac_nhan_quan_fry_path=out_json)
        ok_2, _, _ = doi_chieu_csv_quan_fry(p_ok, luu_xac_nhan=True, file_xac_nhan=out_json, nguoi_doi_chieu="HS A", nguoi_xac_nhan_2="GV B", trich_dan="Quan & Fry (1995) Table 1")
        st2 = liet_ke_tham_so_chua_xac_nhan(ROOT / "config.yaml", xac_nhan_quan_fry_path=out_json)
        ma1 = {x["ma"] for x in st1["danh_sach"]}
        ma2 = {x["ma"] for x in st2["danh_sach"]}
        dat_3 = (
            st0["xac_nhan_quan_fry"]["trang_thai"] == "chua_xac_nhan"
            and ok_1 and st1["xac_nhan_quan_fry"]["trang_thai"] == "xac_nhan_1_nguoi"
            and "quan_fry.xac_nhan_doc_lap_nguoi_2" in ma1
            and ok_2 and st2["xac_nhan_quan_fry"]["trang_thai"] == "xac_nhan_2_nguoi"
            and "quan_fry.he_so_quan_fry_1995" not in ma2
            and "quan_fry.xac_nhan_doc_lap_nguoi_2" not in ma2
        )
        add_row("V2", "V2_3_trang_thai_R7", f"0={st0['xac_nhan_quan_fry']['trang_thai']}, 1={st1['xac_nhan_quan_fry']['trang_thai']}, 2={st2['xac_nhan_quan_fry']['trang_thai']}", "chua -> 1_nguoi -> 2_nguoi", dat_3)

        proc_qf = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "kiem_tra_quan_fry.py"), "--csv", str(p_ok)],
            capture_output=True, text=True, encoding="utf-8",
        )
        add_row("V2", "V2_canh_bao_khong_chep_ma", f"ret={proc_qf.returncode}", "co CANH BAO khong chep ma", proc_qf.returncode == 0 and CANH_BAO_KHONG_CHEP_TU_MA in proc_qf.stdout)


def _danh_gia_v4(add_row: Any) -> None:
    """V4: kiểm tra thiết kế thí nghiệm không chặn dựng đường chuẩn."""
    df_full = sinh_du_lieu_hieu_chuan_mo_phong(
        muc_S=(0.0, 5.0, 10.0, 15.0, 25.0, 35.0),
        muc_T=(20.0, 25.0, 30.0),
        so_lan_lap=3,
        seed=4401,
    )
    df_full[cal.COT_MA_ME_PHA] = ["ME_1" if i % 2 == 0 else "ME_2" for i in range(len(df_full))]
    df_full[cal.COT_PX_PER_MM] = 20.0

    kq_ok = kiem_tra_thiet_ke_thi_nghiem(df_full, config_path=ROOT / "config.yaml", muon_hoc_D=False, don_vi_y="px")
    add_row("V4", "V4_bo_day_du_dat", f"hop_le={kq_ok['hop_le_tong_quat']}, chua_dat={kq_ok['so_chua_dat']}, cb={kq_ok['so_canh_bao']}", "hop_le=True", kq_ok["hop_le_tong_quat"] is True and kq_ok["so_chua_dat"] == 0)

    # Phát hiện lỗi nhưng KHÔNG chặn cal.dung_duong_chuan
    csv_no_me = df_full.drop(columns=[cal.COT_MA_ME_PHA]).to_csv(index=False)
    st_no_me = {m["ma"]: m["trang_thai"] for m in kiem_tra_thiet_ke_tu_csv(csv_no_me)["muc_kiem"]}["me_pha"]

    df_1me = df_full.copy()
    df_1me[cal.COT_MA_ME_PHA] = "ME_DUY_NHAT"
    st_1me = {m["ma"]: m["trang_thai"] for m in kiem_tra_thiet_ke_thi_nghiem(df_1me)["muc_kiem"]}["me_pha"]

    df_mix = df_full.copy()
    # Chỉ kiểm logic trộn nhãn, dữ liệu vẫn mô phỏng
    df_mix.loc[df_mix.index[:2], cal.COT_NGUON] = cal.NHAN_THUC_TE
    st_mix = {m["ma"]: m["trang_thai"] for m in kiem_tra_thiet_ke_thi_nghiem(df_mix)["muc_kiem"]}["nguon_du_lieu"]

    df_d0 = df_full.copy()
    df_d0[cal.COT_NHIET_DO_TC] = df_d0[cal.COT_NHIET_DO]
    st_d0 = {m["ma"]: m["trang_thai"] for m in kiem_tra_thiet_ke_thi_nghiem(df_d0, muon_hoc_D=True)["muc_kiem"]}["bien_thien_D"]

    bc_fit = cal.dung_duong_chuan(cal.doc_csv_hieu_chuan(io.StringIO(csv_no_me)), cal.CauHinhHieuChuan())
    dat_fail = (st_no_me == "chua_dat") and (st_1me == "chua_dat") and (st_mix == "chua_dat") and (st_d0 == "chua_dat") and (bc_fit.mo_hinh.R2 > 0.99)
    add_row(
        "V4",
        "V4_bat_loi_khong_chan",
        f"no_me={st_no_me}, 1_me={st_1me}, mix={st_mix}, D0={st_d0}, R2_fit={bc_fit.mo_hinh.R2:.5f}",
        "tat ca chua_dat & van fit duoc",
        dat_fail,
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

    _danh_gia_v0(add_row)
    _danh_gia_v1(add_row)
    _danh_gia_v2(add_row)
    _danh_gia_v4(add_row)

    out_csv = ROOT / "outputs" / "kiem_tra_chap_nhan_vong4.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["nhom", "tieu_chi", "chi_tiet", "gia_tri_do", "ket_luan", "nguon_du_lieu"])
        w.writeheader()
        w.writerows(rows)

    print("=== KET QUA NGHIEM THU VONG 4 (MO PHONG) ===")
    for r in rows:
        print(f"[{r['ket_luan']:9s}] {r['tieu_chi']}: {r['gia_tri_do']} | {r['chi_tiet']}")
    so_dat = sum(1 for r in rows if r["ket_luan"] == "DAT")
    print(f"\nTong hop: {so_dat}/{len(rows)} tieu chi DAT. Da xuat: {out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
