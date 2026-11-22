"""Kiểm thử W3: sàn sai số lượng tử hóa độ phân giải σ_pg cho hiệu chuẩn chéo nhiệt kế."""

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

from core import nhiet_ke


def _chay_mc_phan_giai(
    r_step: float,
    n_trials: int = 400,
    seed: int = 5301,
    offset_true: float = 0.37,
    sigma_read: float = 0.03,
) -> dict[str, float]:
    """Chạy Monte Carlo mô phỏng hiệu chuẩn chéo 9 cặp ở 3 mức nhiệt với bước lượng tử hóa r_step."""
    rng = np.random.default_rng(seed)
    cov_old = 0
    cov_new = 0
    sig_olds: list[float] = []
    sig_news: list[float] = []
    errs: list[float] = []
    so_canh_bao = 0

    for _ in range(n_trials):
        t_levels = np.array([20.0, 28.0, 36.0]) + rng.uniform(-0.5, 0.5, size=3)
        t_true = np.repeat(t_levels, 3)
        t_tc = np.round((t_true + offset_true + rng.normal(0.0, sigma_read, size=9)) / r_step) * r_step
        t_mau = np.round((t_true + rng.normal(0.0, sigma_read, size=9)) / r_step) * r_step

        df = pd.DataFrame({
            nhiet_ke.COT_T_MAU_DOC: t_mau,
            nhiet_ke.COT_T_TC_DOC: t_tc,
            nhiet_ke.COT_NGUON_NK: ["MO_PHONG"] * 9,
        })
        hc = nhiet_ke.hieu_chuan_cheo_tu_df(
            df,
            nguoi_thuc_hien="HS Kiem W3",
            nguon_du_lieu="MO_PHONG",
            do_phan_giai_toi_da_C=0.1,
        )
        diff = t_tc - t_mau
        sig_old = float(np.std(diff, ddof=1) / math.sqrt(9))
        err = abs(hc.offset_C - offset_true)

        errs.append(err)
        sig_olds.append(sig_old)
        sig_news.append(hc.sigma_offset_C)
        if err <= 2.0 * sig_old:
            cov_old += 1
        if err <= 2.0 * hc.sigma_offset_C:
            cov_new += 1
        if hc.canh_bao_do_phan_giai:
            so_canh_bao += 1

    rms = float(math.sqrt(float(np.mean(np.square(errs)))))
    return {
        "cov_old": cov_old / float(n_trials),
        "cov_new": cov_new / float(n_trials),
        "mean_sig_old": float(np.mean(sig_olds)),
        "mean_sig_new": float(np.mean(sig_news)),
        "rms": rms,
        "ti_le_canh_bao": so_canh_bao / float(n_trials),
    }


def test_w3_uoc_luong_do_phan_giai_khong_nham_khoang_cach_muc() -> None:
    """Đảm bảo uoc_luong_do_phan_giai phân biệt bước chia thực với khoảng cách giữa các bể nhiệt."""
    assert nhiet_ke.uoc_luong_do_phan_giai(np.array([20.0, 20.5, 28.0, 36.0])) == 0.5
    assert nhiet_ke.uoc_luong_do_phan_giai(np.array([20.00, 20.01, 28.00])) == 0.01
    assert nhiet_ke.uoc_luong_do_phan_giai(np.array([20.0, 28.0, 36.0])) == 1.0
    assert nhiet_ke.uoc_luong_do_phan_giai(np.array([25.5, 25.5])) == 0.5
    assert nhiet_ke.uoc_luong_do_phan_giai(np.array([25.3, 25.3])) == 0.1
    assert nhiet_ke.uoc_luong_do_phan_giai(np.array([])) == 0.0


def test_w3_monte_carlo_ba_muc_do_phan_giai() -> None:
    """Kiểm σ_pg trên 400 lần lặp ở r = 0.01, 0.1 và 0.5 °C với seed cố định."""
    res_001 = _chay_mc_phan_giai(0.01, n_trials=400, seed=5301)
    assert res_001["mean_sig_new"] <= 1.5 * res_001["mean_sig_old"]
    assert res_001["cov_new"] >= res_001["cov_old"]

    res_010 = _chay_mc_phan_giai(0.1, n_trials=400, seed=5301)
    assert res_010["cov_new"] >= 0.95

    res_050 = _chay_mc_phan_giai(0.5, n_trials=400, seed=5301)
    assert res_050["cov_new"] >= 0.95
    assert res_050["cov_new"] > res_050["cov_old"]
    assert res_050["ti_le_canh_bao"] == 1.0


def test_w3_doc_tuyen_tinh_va_canh_bao_do_phan_giai_tho() -> None:
    """Độ dốc 0.02 °C/°C ở mức r = 0.5 °C: bật hồi quy tuyến tính, dư <= 0.1 °C và σ(T) >= σ_pg."""
    rng = np.random.default_rng(5309)
    rows = []
    for t_base in (10.2, 20.3, 30.1, 39.8):
        for _ in range(4):
            tm_raw = t_base + rng.normal(0.0, 0.03)
            off_true = -0.2 + 0.02 * tm_raw
            ttc_raw = tm_raw + off_true + rng.normal(0.0, 0.03)
            rows.append({
                nhiet_ke.COT_T_MAU_DOC: round(tm_raw / 0.5) * 0.5,
                nhiet_ke.COT_T_TC_DOC: round(ttc_raw / 0.5) * 0.5,
                nhiet_ke.COT_NGUON_NK: "MO_PHONG",
            })
    df = pd.DataFrame(rows)
    hc = nhiet_ke.hieu_chuan_cheo_tu_df(
        df,
        nguoi_thuc_hien="HS Slope W3",
        nguon_du_lieu="MO_PHONG",
        do_phan_giai_toi_da_C=0.1,
    )
    assert hc.phu_thuoc_nhiet_do is True
    assert hc.canh_bao_do_phan_giai is True
    assert hc.phan_giai_suy_ra is True
    assert any(cb.get("ma") == "DO_PHAN_GIAI_NHIET_KE_THO" for cb in hc.canh_bao_chi_tiet)
    assert hc.sigma_phan_giai_C > 0.0
    for t_chk in (10.0, 20.0, 30.0, 40.0):
        off_est, sig_t = hc.offset_va_sigma_tai(t_chk)
        assert abs(off_est - (-0.2 + 0.02 * t_chk)) <= 0.15
        assert sig_t >= hc.sigma_phan_giai_C - 1e-12


def test_w3_cli_khai_bao_do_phan_giai_va_tuong_thich_json_cu(tmp_path: Path) -> None:
    """CLI --do-phan-giai-mau/--do-phan-giai-tc ghi đè suy đoán và tương thích JSON V1 cũ."""
    df = pd.DataFrame({
        nhiet_ke.COT_T_MAU_DOC: [20.0, 20.0, 20.0, 30.0, 30.0, 30.0],
        nhiet_ke.COT_T_TC_DOC: [20.5, 20.5, 20.5, 30.5, 30.5, 30.5],
        nhiet_ke.COT_NGUON_NK: ["MO_PHONG"] * 6,
    })
    csv_path = tmp_path / "nk.csv"
    df.to_csv(csv_path, index=False)

    # Ghi đè 1 phía: phan_giai_suy_ra vẫn True vì r_tc vẫn suy ra từ số liệu
    out_partial = tmp_path / "out_partial.json"
    proc1 = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "hieu_chuan_cheo_nhiet_ke.py"),
            "--csv", str(csv_path),
            "--nguoi-thuc-hien", "HS W3",
            "--nguon", "MO_PHONG",
            "--do-phan-giai-mau", "0.05",
            "--out", str(out_partial),
        ],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc1.returncode == 0, proc1.stdout + proc1.stderr
    hc1 = nhiet_ke.tai_hieu_chuan_cheo_nhiet_ke(out_partial)
    assert hc1 is not None
    assert hc1.do_phan_giai_mau_C == 0.05
    assert hc1.phan_giai_suy_ra is True
    assert hc1.canh_bao_do_phan_giai is True  # vì r_tc suy ra = 0.5 > 0.1

    # Ghi đè cả 2 phía bằng 0.05 -> phan_giai_suy_ra False, hết cảnh báo thô
    out_both = tmp_path / "out_both.json"
    proc2 = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "hieu_chuan_cheo_nhiet_ke.py"),
            "--csv", str(csv_path),
            "--nguoi-thuc-hien", "HS W3",
            "--nguon", "MO_PHONG",
            "--do-phan-giai-mau", "0.05",
            "--do-phan-giai-tc", "0.05",
            "--out", str(out_both),
        ],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc2.returncode == 0, proc2.stdout + proc2.stderr
    hc2 = nhiet_ke.tai_hieu_chuan_cheo_nhiet_ke(out_both)
    assert hc2 is not None
    assert hc2.do_phan_giai_mau_C == 0.05
    assert hc2.do_phan_giai_tc_C == 0.05
    assert hc2.phan_giai_suy_ra is False
    assert hc2.canh_bao_do_phan_giai is False

    # JSON V1 cũ thiếu các trường W3 vẫn đọc được bình thường
    old_json = tmp_path / "old_v1.json"
    old_json.write_text(
        json.dumps({
            "offset_C": 0.4,
            "sigma_offset_C": 0.06,
            "phu_thuoc_nhiet_do": False,
            "so_cap": 6,
            "so_muc_nhiet": 2,
            "ngay": "2026-11-21",
            "nguon_du_lieu": "MO_PHONG",
            "nguoi_thuc_hien": "HS Cu",
        }),
        encoding="utf-8",
    )
    hc_old = nhiet_ke.tai_hieu_chuan_cheo_nhiet_ke(old_json)
    assert hc_old is not None and hc_old.offset_va_sigma_tai(25.0) == (0.4, 0.06)
