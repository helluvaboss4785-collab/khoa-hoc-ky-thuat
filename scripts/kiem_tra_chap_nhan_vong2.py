"""Kiểm tra nghiệm thu tổng hợp Vòng 2 (Q0–Q3) trên dữ liệu MÔ PHỎNG (Q10).

LƯU Ý TRUNG THỰC DỮ LIỆU:
Mọi chỉ tiêu dưới đây đánh giá thuật toán và mô hình bất định trên ảnh/dữ liệu MÔ PHỎNG (`MO_PHONG`),
KHÔNG phải độ chính xác đo trên thiết bị thật ngoài hiện trường.

Cách chạy:
    python scripts/kiem_tra_chap_nhan_vong2.py
"""
from __future__ import annotations

import math
import sys
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import calibration as cal  # noqa: E402
from core import optics as op  # noqa: E402
from core.measure import do_delta_y_tu_anh  # noqa: E402
from scripts.danh_gia_do_ben_vung import khoang_tin_cay_wilson  # noqa: E402
from sim.synth import (  # noqa: E402
    ThamSoMoPhong,
    sinh_anh_hai_vach_mo_phong,
    sinh_anh_mau_mo_phong,
    sinh_du_lieu_hieu_chuan_mo_phong,
)


def _chuan_bi_mo_hinh_q0(cfg_cal: cal.CauHinhHieuChuan, co_D: bool) -> tuple[cal.MoHinhHieuChuan, op.CauHinhQuangHoc]:
    cfg_op = op.CauHinhQuangHoc.tu_yaml()
    t_tc = (22.0, 25.0, 28.0) if co_D else None
    df = sinh_du_lieu_hieu_chuan_mo_phong(
        cfg=cfg_op,
        muc_S=(0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0),
        muc_T=(22.0, 25.0, 28.0),
        T_tham_chieu_C=t_tc,
        so_lan_lap=3,
        sigma_delta_y_px=0.05,
        sigma_nhiet_ke_C=0.0,
        seed=7,
    )
    bc = cal.dung_duong_chuan(df, cfg_cal)
    return bc.mo_hinh, cfg_op


def _do_phu_200_mau(
    mh: cal.MoHinhHieuChuan,
    cfg_op: op.CauHinhQuangHoc,
    D_that: float,
    nhap_T_tc: bool,
    sigma_T_C: float = 0.0,
    sigma_T_tc: float = 0.0,
    seed: int = 2026,
) -> tuple[float, float, float]:
    rng = np.random.default_rng(seed)
    n_mau = 200
    s_vals = rng.uniform(1.0, 34.0, n_mau)
    t_vals = rng.uniform(24.0, 28.0, n_mau)
    errs = []
    u_vals = []
    phu = 0
    for s_t, t_m in zip(s_vals, t_vals):
        t_tc_that = t_m - D_that
        dy = op.delta_y_vi_sai_px(float(s_t), float(t_m), float(t_tc_that), cfg_op) + float(rng.normal(0.0, 0.05))
        t_tc_in = float(t_tc_that) if nhap_T_tc else None
        est = cal.uoc_luong_do_man(
            mh,
            dy,
            float(t_m),
            sigma_delta_y_px=0.05,
            sigma_T_C=sigma_T_C,
            T_tham_chieu_C=t_tc_in,
            sigma_T_tham_chieu_C=sigma_T_tc,
        )
        e = float(est.S_ppt - s_t)
        errs.append(e)
        u_vals.append(float(est.U_S_ppt))
        if abs(e) <= est.U_S_ppt:
            phu += 1
    rms = float(np.sqrt(np.mean(np.square(errs))))
    return phu / n_mau, rms, float(np.mean(u_vals))


def chay_tat_ca() -> pd.DataFrame:
    cfg_cal = cal.CauHinhHieuChuan.tu_yaml()
    mh_no_D, cfg_op = _chuan_bi_mo_hinh_q0(cfg_cal, co_D=False)
    mh_co_D, _ = _chuan_bi_mo_hinh_q0(cfg_cal, co_D=True)

    rows: list[dict[str, Any]] = []

    def add_row(nhom: str, ma: str, mo_ta: str, gia_tri_do: str, nguong: str, dat: bool) -> None:
        rows.append({
            "nguon_du_lieu": "MO_PHONG",
            "nhom": nhom,
            "ma_kiem_tra": ma,
            "mo_ta": mo_ta,
            "ket_qua_do": gia_tri_do,
            "nguong_chap_nhan": nguong,
            "dat": bool(dat),
        })

    # ---- Q0 ----
    cov_d0_none, rms_d0_none, u_d0_none = _do_phu_200_mau(mh_no_D, cfg_op, 0.0, False, seed=11)
    add_row("Q0", "Q0_khong_T_tc_D0", "Chưa nhập T_tc, D thật = 0°C (200 phép đo)", f"cov={cov_d0_none*100:.1f}%, U_tb={u_d0_none:.3f}‰", "cov >= 95%", cov_d0_none >= 0.95)

    cov_d3_none, rms_d3_none, u_d3_none = _do_phu_200_mau(mh_no_D, cfg_op, 3.0, False, seed=12)
    add_row("Q0", "Q0_khong_T_tc_D3", "Chưa nhập T_tc, D thật = 3°C (200 phép đo)", f"cov={cov_d3_none*100:.1f}%, RMS={rms_d3_none:.3f}‰, U_tb={u_d3_none:.3f}‰", "cov >= 95%", cov_d3_none >= 0.95)

    cov_ref0, _, u_ref0 = _do_phu_200_mau(mh_no_D, cfg_op, 0.0, True, sigma_T_C=0.1, sigma_T_tc=0.0, seed=13)
    cov_in, _, u_in = _do_phu_200_mau(mh_no_D, cfg_op, 0.0, True, sigma_T_C=0.1, sigma_T_tc=0.2, seed=14)
    ratio_u = u_in / max(u_ref0, 1e-9)
    add_row("Q0", "Q0_nhap_T_tc_D0", "Có nhập T_tc (σ_T=0.1, σ_Ttc<=0.2°C), D=0°C (200 phép đo)", f"cov={cov_in*100:.1f}%, U/U_ref={ratio_u:.2f}x", "cov >= 95% & <= 3x", cov_in >= 0.95 and ratio_u <= 3.0)

    dy_d3 = op.delta_y_vi_sai_px(18.0, 26.0, 23.0, cfg_op)
    est_gate = cal.uoc_luong_do_man(mh_no_D, dy_d3, 26.0, T_tham_chieu_C=23.0)
    add_row("Q0", "Q0_gating_khong_D", "Nhập T_tc với |D|=3°C trên mô hình không học D", f"khong_danh_gia_duoc={est_gate.khong_danh_gia_duoc}", "True", est_gate.khong_danh_gia_duoc is True)

    cov_coD, rms_coD, _ = _do_phu_200_mau(mh_co_D, cfg_op, 3.0, True, sigma_T_tc=0.1, seed=15)
    add_row("Q0", "Q0_co_hoc_D_D3", "Đường chuẩn có học D, đo tại D=3°C (200 phép đo)", f"cov={cov_coD*100:.1f}%, RMS={rms_coD:.4f}‰", "cov >= 95% & RMS <= 0.1‰", cov_coD >= 0.95 and rms_coD <= 0.1)

    # ---- Q1 ----
    mp_chay = sinh_anh_mau_mo_phong(ThamSoMoPhong(S_ppt=18.0, T_C=25.0, cuong_do_dinh_goc=245.0, seed=5), cfg=cfg_op, ty_le_kenh=(1.0, 0.20, 0.20))
    kq_chay = do_delta_y_tu_anh(mp_chay.anh, x_ref=mp_chay.x_ref, kenh_laser="auto", tao_anh_ve=False)
    xam_mix_max = int(cv2.cvtColor(mp_chay.anh, cv2.COLOR_BGR2GRAY).max())
    q1_bh_ok = bool(xam_mix_max < 250 and kq_chay.chat_luong.bao_hoa and "R" in kq_chay.chat_luong.kenh_bao_hoa)
    add_row("Q1", "Q1_bao_hoa_kenh_R", "Laser đỏ cháy kênh R (xám trộn <250)", f"max_xam={xam_mix_max}, kenh_bh={kq_chay.chat_luong.kenh_bao_hoa}", "bao_hoa=True & 'R'", q1_bh_ok)

    mp_sach = sinh_anh_mau_mo_phong(ThamSoMoPhong(S_ppt=20.0, T_C=25.0, cuong_do_dinh_goc=180.0, seed=11), cfg=cfg_op, ty_le_kenh=(1.0, 0.35, 0.35))
    kq_r = do_delta_y_tu_anh(mp_sach.anh, x_ref=mp_sach.x_ref, kenh_laser="auto", tao_anh_ve=False)
    kq_x = do_delta_y_tu_anh(mp_sach.anh, x_ref=mp_sach.x_ref, kenh_laser="xam", tao_anh_ve=False)
    err_r = abs(kq_r.delta_y_px - mp_sach.delta_y_ly_thuyet_px)
    q1_clean_ok = bool(kq_r.kenh_su_dung == "R" and kq_r.chat_luong.snr >= kq_x.chat_luong.snr and err_r <= 0.05)
    add_row("Q1", "Q1_sach_SNR_va_sai_so", "Ảnh màu sạch kênh R vs ảnh xám", f"SNR_R={kq_r.chat_luong.snr:.1f} >= {kq_x.chat_luong.snr:.1f}, |err|={err_r:.4f}px", "SNR_R>=SNR_xam & <=0.05px", q1_clean_ok)

    # ---- Q2 (R2: 100 seed cố định 1000..1099, 600x400, y_tc=100) ----
    for spk in (0.1, 0.2):
        n_seed = 100
        hop_le_cnt = 0
        errs_valid = []
        for s in range(1000, 1000 + n_seed):
            mp = sinh_anh_hai_vach_mo_phong(
                ThamSoMoPhong(chieu_cao=400, chieu_rong=600, y_tham_chieu_goc=100.0, S_ppt=20.0, T_C=25.0, speckle_cuong_do=spk, seed=s),
                cfg=cfg_op,
            )
            try:
                kq = do_delta_y_tu_anh(mp.anh, x_ref=mp.x_ref, tao_anh_ve=False)
                if kq.chat_luong.hop_le and np.isfinite(kq.delta_y_px):
                    hop_le_cnt += 1
                    errs_valid.append(abs(kq.delta_y_px - mp.delta_y_ly_thuyet_px))
            except Exception:
                continue
        n_duoi_015 = sum(1 for e in errs_valid if e < 0.15)
        ti_le_hl = hop_le_cnt / n_seed
        ti_le_015 = (n_duoi_015 / hop_le_cnt) if hop_le_cnt else 0.0
        lo_hl, hi_hl = khoang_tin_cay_wilson(hop_le_cnt, n_seed)
        lo_15, hi_15 = khoang_tin_cay_wilson(n_duoi_015, max(hop_le_cnt, 1))
        arr_e = np.asarray(errs_valid, float)
        rms_v = float(np.sqrt(np.mean(arr_e**2)))
        med_v = float(np.median(arr_e))
        p95_v = float(np.percentile(arr_e, 95))
        max_v = float(np.max(arr_e))
        add_row(
            "Q2",
            f"Q2_speckle_{spk}",
            f"100 seed 1000..1099 speckle={spk}, 600x400, S=20‰",
            f"hl={hop_le_cnt}/100 [{lo_hl*100:.1f}..{hi_hl*100:.1f}%], <0.15={ti_le_015*100:.1f}% [{lo_15*100:.1f}..{hi_15*100:.1f}%], RMS={rms_v:.4f}, med={med_v:.4f}, p95={p95_v:.4f}, max={max_v:.4f}",
            "hl>=90% & (<0.15|hl)>=90%",
            ti_le_hl >= 0.90 and ti_le_015 >= 0.90,
        )

    mp_clip = sinh_anh_hai_vach_mo_phong(ThamSoMoPhong(S_ppt=20.0, T_C=25.0, cho_phep_bao_hoa=True, cuong_do_dinh_goc=400.0, seed=1), cfg=cfg_op)
    kq_clip = do_delta_y_tu_anh(mp_clip.anh, x_ref=mp_clip.x_ref, tao_anh_ve=False)
    add_row("Q2", "Q2_clipping_that_400", "Cháy sáng phẳng đỉnh 400 (S=20‰)", f"hop_le={kq_clip.chat_luong.hop_le}, max_run={kq_clip.chat_luong.so_cot_bao_hoa_lien_tiep_max}", "hop_le=False", (kq_clip.chat_luong.bao_hoa and not kq_clip.chat_luong.hop_le))

    # ---- Q3 (R2: 100 seed cố định 1000..1099, 600x400, y_tc=100) ----
    for grad in (40.0, 90.0):
        pass_cnt = 0
        errs_g = []
        nen_cnt = 0
        for s in range(1000, 1100):
            mp = sinh_anh_hai_vach_mo_phong(
                ThamSoMoPhong(chieu_cao=400, chieu_rong=600, y_tham_chieu_goc=100.0, S_ppt=20.0, T_C=25.0, gradient_nen_y=grad, seed=s),
                cfg=cfg_op,
            )
            kq = do_delta_y_tu_anh(mp.anh, x_ref=mp.x_ref, tao_anh_ve=False)
            e = abs(kq.delta_y_px - mp.delta_y_ly_thuyet_px)
            errs_g.append(e)
            co_flag = bool(kq.chat_luong.nen_khong_deu and any(c["ma"] == "NEN_KHONG_DEU" for c in kq.chat_luong.canh_bao_chi_tiet))
            if co_flag:
                nen_cnt += 1
            if e < 0.2 and co_flag:
                pass_cnt += 1
        lo_g, hi_g = khoang_tin_cay_wilson(pass_cnt, 100)
        add_row("Q3", f"Q3_gradient_{int(grad)}", f"100 seed 1000..1099 gradient_nen_y={int(grad)}", f"pass={pass_cnt}/100 [{lo_g*100:.1f}..{hi_g*100:.1f}%], nen_khong_deu={nen_cnt}/100, max|err|={max(errs_g):.4f}px", "100/100 dat & <0.2px", pass_cnt == 100 and max(errs_g) < 0.2)

    h_big, w_big = 3000, 4000
    anh_big = np.full((h_big, w_big), 14, dtype=np.uint8)
    y_idx = np.arange(h_big, dtype=np.float32)[:, None]
    anh_big[:, 150:1850] = np.clip(14.0 + 180.0 * np.exp(-((y_idx - 900.0) ** 2) / (2.0 * 4.5**2)), 0, 255).astype(np.uint8)
    anh_big[:, 2150:3850] = np.clip(14.0 + 180.0 * np.exp(-((y_idx - 1650.25) ** 2) / (2.0 * 4.5**2)), 0, 255).astype(np.uint8)
    t0 = time.perf_counter()
    kq_big = do_delta_y_tu_anh(anh_big, tao_anh_ve=False)
    dt_big = time.perf_counter() - t0
    err_big = abs(kq_big.delta_y_px - 750.25)
    add_row("Q3", "Q3_anh_12MP_4000x3000", "Tốc độ & độ đúng ảnh 4000×3000", f"time={dt_big:.3f}s, |err|={err_big:.4f}px", "<= 3.0s & < 0.2px", dt_big <= 3.0 and err_big < 0.2)

    return pd.DataFrame(rows)


def main() -> None:
    df = chay_tat_ca()
    out_path = ROOT / "outputs" / "kiem_tra_chap_nhan_vong2.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False, encoding="utf-8-sig")

    print("=== KET QUA NGHIEM THU VONG 2 (MO PHONG) ===")
    print(df[["nhom", "ma_kiem_tra", "ket_qua_do", "nguong_chap_nhan", "dat"]].to_string(index=False))
    print(f"\nDa luu bao cao tai: {out_path}")
    tat_ca_dat = bool(df["dat"].all())
    if not tat_ca_dat:
        print("CO TIEU CHI CHUA DAT!", file=sys.stderr)
        sys.exit(1)
    print(f"TONG KET: {int(df['dat'].sum())}/{len(df)} TIEU CHI DAT.")


if __name__ == "__main__":
    main()
