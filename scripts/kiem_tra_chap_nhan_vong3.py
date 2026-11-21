"""Kiểm chứng chấp nhận Vòng 3 (R0–R10) trên dữ liệu MÔ PHỎNG với seed cố định.

Xuất `outputs/kiem_tra_chap_nhan_vong3.csv` (mọi dòng đều ghi rõ nguồn MO_PHONG).
"""

from __future__ import annotations

import csv
import math
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import calibration as cal, optics as op
from core.measure import do_delta_y_tu_anh
from core.trang_thai_cau_hinh import XAC_NHAN_QF_MAC_DINH, liet_ke_tham_so_chua_xac_nhan
from sim.synth import (
    ThamSoMoPhong,
    sinh_anh_hai_vach_mo_phong,
    sinh_du_lieu_hieu_chuan_mo_phong,
)


def khoang_tin_cay_wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """Khoảng tin cậy Wilson 95% cho tỉ lệ nhị thức k/n."""
    if n <= 0:
        return 0.0, 0.0
    p = k / n
    z2 = z * z
    mau = 1.0 + z2 / n
    tam = (p + z2 / (2.0 * n)) / mau
    bien = (z * math.sqrt((p * (1.0 - p) + z2 / (4.0 * n)) / n)) / mau
    return max(0.0, tam - bien), min(1.0, tam + bien)


def _chay_mot_anh_r2(args: tuple[int, float, float]) -> tuple[bool, float]:
    seed, spk, grad = args
    cfg = op.CauHinhQuangHoc.tu_yaml()
    ts = ThamSoMoPhong(
        chieu_cao=400,
        chieu_rong=600,
        S_ppt=20.0,
        T_C=25.0,
        T_tham_chieu_C=25.0,
        y_tham_chieu_goc=100.0,
        speckle_cuong_do=spk,
        gradient_nen_y=grad,
        seed=seed,
    )
    obj = sinh_anh_hai_vach_mo_phong(ts, cfg=cfg, gan_watermark=False)
    kq = do_delta_y_tu_anh(obj.anh, x_ref=obj.x_ref, tao_anh_ve=False)
    return bool(kq.chat_luong.hop_le), float(kq.delta_y_px - obj.delta_y_ly_thuyet_px)


def _mo_hinh_chua_hoc_D() -> tuple[cal.MoHinhHieuChuan, op.CauHinhQuangHoc]:
    cfg = op.CauHinhQuangHoc.tu_yaml()
    df = sinh_du_lieu_hieu_chuan_mo_phong(cfg=cfg, T_tham_chieu_C=None, sigma_delta_y_px=0.05, sigma_nhiet_ke_C=0.0, seed=7)
    mh = cal.dung_duong_chuan(df, cal.CauHinhHieuChuan(), bac_ep=1).mo_hinh
    assert "D" not in mh.hang
    return mh, cfg


def _mo_hinh_co_D() -> tuple[cal.MoHinhHieuChuan, op.CauHinhQuangHoc]:
    cfg = op.CauHinhQuangHoc.tu_yaml()
    rows = []
    rng = np.random.default_rng(77)
    for me, S in enumerate((0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0)):
        for T_m in (22.0, 25.0, 28.0):
            for T_tc in (22.0, 25.0, 28.0):
                dy = op.delta_y_vi_sai_px(S, T_m, T_tc, cfg) + float(rng.normal(0.0, 0.04))
                rows.append({
                    cal.COT_DO_MAN: S,
                    cal.COT_NHIET_DO: T_m,
                    cal.COT_NHIET_DO_TC: T_tc,
                    cal.COT_DELTA_Y: dy,
                    cal.COT_NGUON: cal.NHAN_MO_PHONG,
                    "ma_me_pha": f"ME_{me % 2}",
                    cal.COT_ID_THIET_BI: "",
                    cal.COT_ID_DIEN_THOAI: "",
                })
    mh = cal.dung_duong_chuan(pd.DataFrame(rows), cal.CauHinhHieuChuan()).mo_hinh
    assert "D" in mh.hang
    return mh, cfg


def _chay_kich_ban_r0(
    ten: str,
    mh: cal.MoHinhHieuChuan,
    cfg_op: op.CauHinhQuangHoc,
    n_mau: int,
    seed: int,
    bien_d: float,
    sigma_T: float,
    co_nhap_T_tc: bool,
    hieu_chinh_ly_thuyet_D: bool,
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    err_all: list[float] = []
    err_unblocked: list[float] = []
    cov_hits = 0
    u_unblocked: list[float] = []

    for _ in range(n_mau):
        S_true = float(rng.uniform(2.0, 33.0))
        T_m_true = float(rng.uniform(23.0, 27.0))
        D_true = float(rng.uniform(-bien_d, bien_d))
        T_tc_true = T_m_true - D_true
        dy_meas = op.delta_y_vi_sai_px(S_true, T_m_true, T_tc_true, cfg_op) + float(rng.normal(0.0, 0.05))
        T_m_meas = T_m_true + float(rng.normal(0.0, sigma_T)) if sigma_T > 0 else T_m_true
        T_tc_meas = (T_tc_true + float(rng.normal(0.0, sigma_T))) if (co_nhap_T_tc and sigma_T > 0) else (T_tc_true if co_nhap_T_tc else None)

        kq = cal.uoc_luong_do_man(
            mh=mh,
            delta_y_px=dy_meas,
            T_C=T_m_meas,
            sigma_delta_y_px=0.05,
            sigma_T_C=sigma_T,
            T_tham_chieu_C=T_tc_meas,
            sigma_T_tham_chieu_C=sigma_T if co_nhap_T_tc else 0.0,
            nguong_lech_T_hai_ngan_C=0.5,
            sigma_D_khi_chua_do_C=2.0,
            ap_dung_hieu_chinh_ly_thuyet_D=hieu_chinh_ly_thuyet_D,
        )
        err = float(kq.S_ppt - S_true)
        err_all.append(err)
        bi_chan_vat_li = bool(
            kq.chenh_T_ngoai_mo_hinh or kq.ngoai_dai_S or kq.ngoai_dai_T or kq.ngoai_dai_D or (not co_nhap_T_tc and kq.khong_danh_gia_duoc)
        )
        if not bi_chan_vat_li:
            err_unblocked.append(err)
            u_unblocked.append(float(kq.U_S_ppt))
            if abs(err) <= kq.U_S_ppt:
                cov_hits += 1

    n_ok = len(err_unblocked)
    cov = (cov_hits / n_ok) if n_ok else 0.0
    ci_lo, ci_hi = khoang_tin_cay_wilson(cov_hits, n_ok)
    rms_ok = float(np.sqrt(np.mean(np.square(err_unblocked)))) if n_ok else float("nan")
    rms_all = float(np.sqrt(np.mean(np.square(err_all))))
    u_tb = float(np.mean(u_unblocked)) if n_ok else float("nan")
    return {
        "ten": ten,
        "seed": seed,
        "n_tong": n_mau,
        "n_khong_bi_chan": n_ok,
        "cov": cov,
        "cov_ci_lo": ci_lo,
        "cov_ci_hi": ci_hi,
        "rms_khong_bi_chan": rms_ok,
        "rms_toan_bo": rms_all,
        "max_khong_bi_chan": float(np.max(np.abs(err_unblocked))) if n_ok else float("nan"),
        "U_tb": u_tb,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    mh_no_d, cfg_op = _mo_hinh_chua_hoc_D()
    mh_co_d, _ = _mo_hinh_co_D()

    rows_csv: list[dict[str, Any]] = []

    def _add(nhom: str, ma: str, chi_tiet: str, gia_tri: str, dat: bool) -> None:
        rows_csv.append({
            "nhom": nhom,
            "tieu_chi": ma,
            "chi_tiet": chi_tiet,
            "gia_tri_do": gia_tri,
            "ket_luan": "DAT" if dat else "KHONG_DAT",
            "nguon_du_lieu": "MO_PHONG",
        })

    # --- R0 ----------------------------------------------------------------
    kb_A = _chay_kich_ban_r0("A_D0.5_chua_hoc_D", mh_no_d, cfg_op, 300, 3001, 0.5, 0.2, True, False)
    kb_B = _chay_kich_ban_r0("B_D1.5_chua_hoc_D", mh_no_d, cfg_op, 300, 3002, 1.5, 0.2, True, False)
    kb_C_ideal = _chay_kich_ban_r0("C_co_D_sigT0.0", mh_co_d, cfg_op, 300, 3003, 1.5, 0.0, True, False)
    kb_C_02 = _chay_kich_ban_r0("C_co_D_sigT0.2", mh_co_d, cfg_op, 300, 3003, 1.5, 0.2, True, False)
    kb_D = _chay_kich_ban_r0("D_khong_T_tc", mh_no_d, cfg_op, 300, 3004, 0.5, 0.2, False, False)
    kb_E = _chay_kich_ban_r0("E_hieu_chinh_ly_thuyet_D", mh_no_d, cfg_op, 300, 3005, 1.5, 0.2, True, True)

    for kb, req_cov in ((kb_A, 0.95), (kb_B, 0.95), (kb_C_ideal, 0.95), (kb_C_02, 0.95), (kb_E, 0.95)):
        _add(
            "R0",
            f"R0_{kb['ten']}",
            f"seed={kb['seed']}, n_ok={kb['n_khong_bi_chan']}/{kb['n_tong']}, RMS_ok={kb['rms_khong_bi_chan']:.4f}‰, RMS_all={kb['rms_toan_bo']:.4f}‰, U_tb={kb['U_tb']:.4f}‰",
            f"cov={kb['cov']*100:.1f}% [95%CI {kb['cov_ci_lo']*100:.1f}%-{kb['cov_ci_hi']*100:.1f}%]",
            kb["cov"] >= req_cov,
        )

    # C baseline trước sửa tại sigma_T=0.0 là 0.0280‰ và sigma_T=0.2 là 0.3453‰
    _add(
        "R0",
        "R0_C_RMS_va_U_vs_co_so",
        "Kich ban C sigma_T=0.0 (co so U_tb=0.0280‰) va sigma_T=0.2 (co so U_tb=0.3453‰)",
        f"RMS(sigT=0)={kb_C_ideal['rms_khong_bi_chan']:.4f}‰, U(sigT=0)={kb_C_ideal['U_tb']:.4f}‰, U(sigT=0.2)={kb_C_02['U_tb']:.4f}‰",
        (kb_C_ideal["rms_khong_bi_chan"] <= 0.1) and (kb_C_ideal["U_tb"] <= 1.5 * 0.0280) and (kb_C_02["U_tb"] <= 1.5 * 0.3453),
    )

    dy0 = op.delta_y_vi_sai_px(20.0, 25.0, 25.0, cfg_op)
    u_mono = [
        cal.uoc_luong_do_man(mh_no_d, dy0, 25.0, sigma_delta_y_px=0.05, sigma_T_C=s, T_tham_chieu_C=25.0, sigma_T_tham_chieu_C=s).U_S_ppt
        for s in (0.1, 0.2, 0.5)
    ]
    _add(
        "R0",
        "R0_don_dieu_nhiet_ke_D0",
        "U tang nghiem ngat theo sigma_T (0.1 < 0.2 < 0.5 C) tai D_do = 0",
        f"U(0.1)={u_mono[0]:.4f}, U(0.2)={u_mono[1]:.4f}, U(0.5)={u_mono[2]:.4f}‰",
        u_mono[0] < u_mono[1] < u_mono[2],
    )

    _add(
        "R0",
        "R0_D_hoi_quy_khong_nhap_T_tc",
        "Khong nhap T_tc giu nguyen sigma_D=2.0 C va chan ket luan",
        f"n_ok={kb_D['n_khong_bi_chan']}/{kb_D['n_tong']}, RMS_toan_bo={kb_D['rms_toan_bo']:.4f}‰",
        kb_D["n_khong_bi_chan"] == 0,
    )

    giam_ok = (kb_B["rms_khong_bi_chan"] - kb_E["rms_khong_bi_chan"]) / kb_B["rms_khong_bi_chan"]
    giam_all = (kb_B["rms_toan_bo"] - kb_E["rms_toan_bo"]) / kb_B["rms_toan_bo"]
    _add(
        "R0",
        "R0_E_giam_RMS_vs_B_toan_bo",
        f"Toan bo 300 phep do D in [-1.5, +1.5]: RMS_E={kb_E['rms_toan_bo']:.4f}‰ vs RMS_B={kb_B['rms_toan_bo']:.4f}‰",
        f"giam_toan_bo={giam_all*100:.1f}% (yeu cau >= 50%)",
        giam_all >= 0.5,
    )
    _add(
        "R0",
        "R0_E_giam_RMS_vs_B_khong_bi_chan",
        f"Tap con khong bi chan (|D_do|<=0.5): RMS_E={kb_E['rms_khong_bi_chan']:.4f}‰ vs RMS_B={kb_B['rms_khong_bi_chan']:.4f}‰ (san nhiet ke |k_D|*sigma_Ddo ~ 0.171‰)",
        f"giam_khong_bi_chan={giam_ok*100:.1f}%",
        giam_ok >= 0.5,
    )

    # --- R1 ----------------------------------------------------------------
    u_r1_off = cal.uoc_luong_do_man(mh_no_d, dy0, 25.0, sigma_delta_y_px=0.05, T_tham_chieu_C=None, sigma_D_khi_chua_do_C=2.0).U_S_ppt
    kq_r1_on = cal.uoc_luong_do_man(
        mh_no_d, dy0, 25.0, sigma_delta_y_px=0.05, T_tham_chieu_C=None,
        sigma_D_khi_chua_do_C=1.0, da_on_dinh_nhiet_gia_dinh=True,
    )
    _add(
        "R1",
        "R1_ba_nhanh_sigma_D",
        "Co tat U_off vs co bat + chuoi on dinh du dai (sigma_D=1.0 C)",
        f"U_off={u_r1_off:.4f}‰, U_on={kq_r1_on.U_S_ppt:.4f}‰, co_co_can_than={any(c['ma']=='chenh_nhiet_gia_dinh_on_dinh' for c in kq_r1_on.canh_bao_chi_tiet)}",
        (kq_r1_on.U_S_ppt < u_r1_off * 0.65) and any(c["ma"] == "chenh_nhiet_gia_dinh_on_dinh" for c in kq_r1_on.canh_bao_chi_tiet),
    )

    # --- R2: 100 seed cố định 1000..1099 -------------------------------------
    seeds = list(range(1000, 1100))
    configs_r2 = [
        ("speckle_0.1", 0.1, 0.0, True),
        ("speckle_0.2", 0.2, 0.0, True),
        ("gradient_40", 0.0, 40.0, False),
        ("speckle_0.1_gradient_40", 0.1, 40.0, False),
    ]
    out_r2_rows: list[dict[str, Any]] = []
    with ProcessPoolExecutor() as pool:
        for nhan, spk, grad, bat_buoc in configs_r2:
            res = list(pool.map(_chay_mot_anh_r2, [(s, spk, grad) for s in seeds]))
            n_tot = len(res)
            hop_le = [e for ok, e in res if ok]
            n_ok = len(hop_le)
            n_duoi = sum(1 for e in hop_le if abs(e) < 0.15)
            abs_ok = np.abs(hop_le) if n_ok else np.array([float("nan")])
            rms = float(np.sqrt(np.mean(np.square(hop_le)))) if n_ok else float("nan")
            med = float(np.median(abs_ok))
            p95 = float(np.percentile(abs_ok, 95))
            mx = float(np.max(abs_ok))
            p_ok = n_ok / n_tot
            ci_ok = khoang_tin_cay_wilson(n_ok, n_tot)
            p_lt = (n_duoi / n_ok) if n_ok else 0.0
            ci_lt = khoang_tin_cay_wilson(n_duoi, n_ok)
            dat_r2 = (p_ok >= 0.90 and p_lt >= 0.90) if bat_buoc else (n_ok >= 90)
            _add(
                "R2",
                f"R2_{nhan}",
                f"seeds=1000..1099, hop_le={n_ok}/{n_tot} ({p_ok*100:.1f}% [CI {ci_ok[0]*100:.1f}%-{ci_ok[1]*100:.1f}%]), <0.15px={n_duoi}/{n_ok} ({p_lt*100:.1f}% [CI {ci_lt[0]*100:.1f}%-{ci_lt[1]*100:.1f}%])",
                f"RMS={rms:.4f}px, med={med:.4f}px, p95={p95:.4f}px, max={mx:.4f}px",
                dat_r2,
            )
            out_r2_rows.append((nhan, n_ok, n_tot, p_ok, ci_ok, n_duoi, p_lt, ci_lt, rms, med, p95, mx))

    # --- R3 ----------------------------------------------------------------
    obj_ria = sinh_anh_hai_vach_mo_phong(
        ThamSoMoPhong(S_ppt=5.0, T_C=25.0, T_tham_chieu_C=25.0, y_tham_chieu_goc=45.0, seed=55),
        cfg=cfg_op,
        gan_watermark=False,
    )
    kq_r3_def = do_delta_y_tu_anh(obj_ria.anh, he_so_meo_k1_khai_bao=None)
    kq_r3_k1 = do_delta_y_tu_anh(obj_ria.anh, he_so_meo_k1_khai_bao=-0.1)
    _add(
        "R3",
        "R3_meo_ong_kinh_ria",
        "Mac dinh chi vao thong_tin_bo_sung; khi co k1 moi vao canh_bao_chi_tiet kem px",
        f"def_cb={any(c['ma']=='MEO_ONG_KINH' for c in kq_r3_def.chat_luong.canh_bao_chi_tiet)}, k1_cb={any(c['ma']=='MEO_ONG_KINH' for c in kq_r3_k1.chat_luong.canh_bao_chi_tiet)}",
        all(c["ma"] != "MEO_ONG_KINH" for c in kq_r3_def.chat_luong.canh_bao_chi_tiet)
        and any(x["ma"] == "MEO_ONG_KINH_THONG_TIN" for x in kq_r3_def.chat_luong.thong_tin_bo_sung)
        and any(c["ma"] == "MEO_ONG_KINH" for c in kq_r3_k1.chat_luong.canh_bao_chi_tiet),
    )

    # --- R7 & Tiêu chí chung #3 --------------------------------------------
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        raw_cfg = yaml.safe_load(f) or {}
    thieu_nguon = [
        k for k, v in (raw_cfg.get("nguong_loai", {}) or {}).items()
        if isinstance(v, dict) and v.get("an_toan") is not None and not str(v.get("nguon_tham_khao") or "").strip()
    ]
    st_r7 = liet_ke_tham_so_chua_xac_nhan(ROOT / "config.yaml", xac_nhan_quan_fry_path=XAC_NHAN_QF_MAC_DINH)
    ma_r7 = {item["ma"] for item in st_r7["danh_sach"]}
    can_co_r7 = {
        "hieu_chuan.ap_dung_hieu_chinh_ly_thuyet_D",
        "hieu_chuan.cho_phep_giam_sigma_D_khi_on_dinh",
        "hieu_chuan.sigma_D_khi_da_on_dinh_C",
        "hieu_chuan.thoi_gian_on_dinh_toi_thieu_phut",
        "hieu_chuan.nguong_bien_thien_px_per_mm_phan_tram",
        "quang_hoc.nhiet_do_chuan_chiet_suat_C",
        "quan_fry.he_so_quan_fry_1995",
    }
    _add(
        "R7",
        "R7_nguong_loai_va_gia_dinh",
        f"thieu_nguon={thieu_nguon}, tong_chua_xac_nhan={st_r7['so_tham_so_chua_xac_nhan']}, qf_json_ton_tai={XAC_NHAN_QF_MAC_DINH.exists()}",
        f"thieu_ma={sorted(can_co_r7 - ma_r7)}",
        (len(thieu_nguon) == 0) and can_co_r7.issubset(ma_r7) and (not XAC_NHAN_QF_MAC_DINH.exists()),
    )

    out_csv = ROOT / "outputs" / "kiem_tra_chap_nhan_vong3.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["nhom", "tieu_chi", "chi_tiet", "gia_tri_do", "ket_luan", "nguon_du_lieu"])
        w.writeheader()
        w.writerows(rows_csv)

    print("=== KET QUA NGHIEM THU VONG 3 (MO PHONG) ===")
    for r in rows_csv:
        print(f"[{r['ket_luan']:9s}] {r['tieu_chi']}: {r['gia_tri_do']} | {r['chi_tiet']}")
    so_dat = sum(1 for r in rows_csv if r["ket_luan"] == "DAT")
    print(f"\nTong hop: {so_dat}/{len(rows_csv)} tieu chi DAT. Da xuat: {out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
