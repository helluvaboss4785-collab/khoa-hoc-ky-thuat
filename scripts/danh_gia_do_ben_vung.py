"""Đánh giá độ bền vững thuật toán tìm tâm trên ảnh MÔ PHỎNG theo từng hiệu ứng riêng rẽ (T9, cập nhật R2).

LƯU Ý QUAN TRỌNG:
Đây là kiểm thử độ bền vững của thuật toán xử lí ảnh trên dữ liệu MÔ PHỎNG (`N = 100` seed cố định 1000..1099),
KHÔNG phải kết quả đánh giá độ chính xác của thiết bị phần cứng thật.
"""
from __future__ import annotations

import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.measure import do_delta_y_tu_anh  # noqa: E402
from core.optics import CauHinhQuangHoc, pixel_moi_phan_nghin  # noqa: E402
from sim.synth import ThamSoMoPhong, sinh_anh_hai_vach_mo_phong  # noqa: E402


def khoang_tin_cay_wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """Khoảng tin cậy Wilson 95% cho tỉ lệ k/n."""
    if n <= 0:
        return 0.0, 1.0
    p = float(k) / float(n)
    z2 = z * z
    denom = 1.0 + z2 / float(n)
    center = (p + z2 / (2.0 * float(n))) / denom
    half = (z * math.sqrt((p * (1.0 - p) + z2 / (4.0 * float(n))) / float(n))) / denom
    return max(0.0, center - half), min(1.0, center + half)


def _chay_mot_muc(args: tuple[str, str, object, int, float, float, float]) -> dict[str, object]:
    nhom, truong, muc, so_seed, S_muc_tieu, T_muc_tieu, px_per_ppt = args
    cfg = CauHinhQuangHoc.tu_yaml()
    err_all: list[float] = []
    err_hop_le: list[float] = []
    for idx in range(so_seed):
        kw: dict[str, object] = {
            "chieu_cao": 400,
            "chieu_rong": 600,
            "y_tham_chieu_goc": 100.0,
            "S_ppt": S_muc_tieu,
            "T_C": T_muc_tieu,
            "T_tham_chieu_C": T_muc_tieu,
            "seed": 1000 + idx,
        }
        if truong == "speckle_va_gradient":
            spk_v, grad_v = muc  # type: ignore[misc]
            kw["speckle_cuong_do"] = float(spk_v)
            kw["gradient_nen_y"] = float(grad_v)
        elif truong != "co_so":
            kw[truong] = muc
        anh_mp = sinh_anh_hai_vach_mo_phong(ThamSoMoPhong(**kw), cfg=cfg)  # type: ignore[arg-type]
        try:
            kq = do_delta_y_tu_anh(anh_mp.anh, x_ref=anh_mp.x_ref, tao_anh_ve=False)
            if np.isfinite(kq.delta_y_px):
                e = float(kq.delta_y_px - anh_mp.delta_y_ly_thuyet_px)
                err_all.append(e)
                if kq.chat_luong.hop_le:
                    err_hop_le.append(e)
        except Exception:
            continue

    so_hop_le = len(err_hop_le)
    lo_hl, hi_hl = khoang_tin_cay_wilson(so_hop_le, so_seed)
    arr_stat = np.asarray(err_hop_le if err_hop_le else err_all, dtype=float)
    if len(arr_stat) > 0:
        abs_stat = np.abs(arr_stat)
        bias_px = float(np.mean(arr_stat))
        std_px = float(np.std(arr_stat))
        rms_px = float(np.sqrt(np.mean(arr_stat**2)))
        med_abs_px = float(np.median(abs_stat))
        p95_abs_px = float(np.percentile(abs_stat, 95))
        max_abs_px = float(np.max(abs_stat))
        so_duoi_015 = int(np.count_nonzero(abs_stat < 0.15))
        n_stat = len(arr_stat)
        ti_le_015 = so_duoi_015 / float(n_stat)
        lo_015, hi_015 = khoang_tin_cay_wilson(so_duoi_015, n_stat)
    else:
        bias_px = std_px = rms_px = med_abs_px = p95_abs_px = max_abs_px = float("nan")
        so_duoi_015 = 0
        ti_le_015 = lo_015 = hi_015 = 0.0

    muc_str = f"spk={muc[0]}, grad={muc[1]}" if truong == "speckle_va_gradient" else str(muc)  # type: ignore[index]
    return {
        "nguon_du_lieu": "MO_PHONG",
        "hieu_ung": nhom,
        "tham_so": truong,
        "muc": muc_str,
        "so_mau_do_duoc": len(err_all),
        "so_mau_dat_chat_luong": so_hop_le,
        "tong_so_mau": so_seed,
        "ti_le_hop_le": round(so_hop_le / float(so_seed), 4),
        "wilson_hop_le_duoi": round(lo_hl, 4),
        "wilson_hop_le_tren": round(hi_hl, 4),
        "rms_px": round(rms_px, 4) if np.isfinite(rms_px) else None,
        "trung_vi_abs_px": round(med_abs_px, 4) if np.isfinite(med_abs_px) else None,
        "p95_abs_px": round(p95_abs_px, 4) if np.isfinite(p95_abs_px) else None,
        "toi_da_abs_px": round(max_abs_px, 4) if np.isfinite(max_abs_px) else None,
        "so_duoi_015_px": so_duoi_015,
        "ti_le_duoi_015_trong_hop_le": round(ti_le_015, 4),
        "wilson_015_duoi": round(lo_015, 4),
        "wilson_015_tren": round(hi_015, 4),
        "sai_lech_tb_px": round(bias_px, 4) if np.isfinite(bias_px) else None,
        "do_lech_chuan_px": round(std_px, 4) if np.isfinite(std_px) else None,
        "sai_lech_tb_ppt": round(bias_px / px_per_ppt, 4) if np.isfinite(bias_px) else None,
        "do_lech_chuan_ppt": round(std_px / px_per_ppt, 4) if np.isfinite(std_px) else None,
    }


def danh_gia_do_ben_vung(so_seed: int = 100) -> pd.DataFrame:
    cfg = CauHinhQuangHoc.tu_yaml()
    S_muc_tieu = 20.0
    T_muc_tieu = 25.0
    px_per_ppt = pixel_moi_phan_nghin(S_muc_tieu, T_muc_tieu, cfg)

    kich_ban: list[tuple[str, str, list[object]]] = [
        ("Cơ sở (không hiệu ứng phụ)", "co_so", [0.0]),
        ("Đốm laser (speckle_cuong_do)", "speckle_cuong_do", [0.05, 0.10, 0.20]),
        ("Đốm laser + gradient nền", "speckle_va_gradient", [(0.10, 40.0)]),
        ("Méo ống kính (meo_ong_kinh_k1)", "meo_ong_kinh_k1", [-0.10, -0.05, 0.05, 0.10]),
        ("Gradient nền (gradient_nen_y)", "gradient_nen_y", [20.0, 40.0, 50.0, 90.0]),
        ("Độ cong vạch (do_cong_vach px)", "do_cong_vach", [0.5, 1.5, 3.0]),
        ("Chênh sáng hai nửa (chenh_sang_hai_nua)", "chenh_sang_hai_nua", [0.2, 0.4, 0.6]),
        ("Phi tuyến cảm biến (gamma_cam_bien)", "gamma_cam_bien", [0.7, 1.4, 2.0]),
        ("Nén mất dữ liệu (chat_luong_jpeg)", "chat_luong_jpeg", [90, 70, 50]),
    ]

    tasks = [
        (nhom, truong, muc, so_seed, S_muc_tieu, T_muc_tieu, px_per_ppt)
        for nhom, truong, ds_muc in kich_ban
        for muc in ds_muc
    ]

    max_workers = min(12, max(1, (os.cpu_count() or 1) - 2), len(tasks))
    if so_seed >= 20 and max_workers >= 2:
        with ProcessPoolExecutor(max_workers=max_workers) as ex:
            dong = list(ex.map(_chay_mot_muc, tasks))
    else:
        dong = [_chay_mot_muc(t) for t in tasks]
    return pd.DataFrame(dong)


def main() -> None:
    df = danh_gia_do_ben_vung(so_seed=100)
    out_r2 = ROOT / "outputs" / "do_ben_vung_nhieu_seed_MO_PHONG.csv"
    out_legacy = ROOT / "outputs" / "danh_gia_do_ben_vung_MO_PHONG.csv"
    out_r2.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_r2, index=False, encoding="utf-8-sig")
    df.to_csv(out_legacy, index=False, encoding="utf-8-sig")
    print(f"Da luu bang do ben vung nhieu seed MO PHONG tai: {out_r2}")
    print("\n=== BANG DO BEN VUNG THUAT TOAN TREN ANH MO PHONG (600x400, S=20 ppt, T=25 C, N=100/muc, seed 1000..1099) ===")
    cols = [
        "hieu_ung",
        "muc",
        "so_mau_dat_chat_luong",
        "rms_px",
        "trung_vi_abs_px",
        "p95_abs_px",
        "toi_da_abs_px",
        "ti_le_duoi_015_trong_hop_le",
        "wilson_015_duoi",
        "wilson_015_tren",
    ]
    print(df[cols].to_string(index=False))


if __name__ == "__main__":
    main()
