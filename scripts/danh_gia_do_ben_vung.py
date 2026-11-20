"""Đánh giá độ bền vững thuật toán tìm tâm trên ảnh MÔ PHỎNG theo từng hiệu ứng riêng rẽ (T9).

LƯU Ý QUAN TRỌNG:
Đây là kiểm thử độ bền vững của thuật toán xử lí ảnh trên dữ liệu MÔ PHỎNG,
KHÔNG phải kết quả đánh giá độ chính xác của thiết bị phần cứng thật.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.measure import do_delta_y_tu_anh
from core.optics import CauHinhQuangHoc, pixel_moi_phan_nghin
from sim.synth import ThamSoMoPhong, sinh_anh_hai_vach_mo_phong


def danh_gia_do_ben_vung(so_seed: int = 10) -> pd.DataFrame:
    cfg = CauHinhQuangHoc.tu_yaml()
    S_muc_tieu = 20.0
    T_muc_tieu = 25.0
    px_per_ppt = pixel_moi_phan_nghin(S_muc_tieu, T_muc_tieu, cfg)

    kich_ban: list[tuple[str, str, list[object]]] = [
        ("Cơ sở (không hiệu ứng phụ)", "co_so", [0.0]),
        ("Đốm laser (speckle_cuong_do)", "speckle_cuong_do", [0.05, 0.10, 0.20]),
        ("Méo ống kính (meo_ong_kinh_k1)", "meo_ong_kinh_k1", [-0.10, -0.05, 0.05, 0.10]),
        ("Gradient nền (gradient_nen_y)", "gradient_nen_y", [20.0, 50.0, 90.0]),
        ("Độ cong vạch (do_cong_vach px)", "do_cong_vach", [0.5, 1.5, 3.0]),
        ("Chênh sáng hai nửa (chenh_sang_hai_nua)", "chenh_sang_hai_nua", [0.2, 0.4, 0.6]),
        ("Phi tuyến cảm biến (gamma_cam_bien)", "gamma_cam_bien", [0.7, 1.4, 2.0]),
        ("Nén mất dữ liệu (chat_luong_jpeg)", "chat_luong_jpeg", [90, 70, 50]),
    ]

    dong: list[dict[str, object]] = []
    for nhom, truong, ds_muc in kich_ban:
        for muc in ds_muc:
            err_px: list[float] = []
            so_hop_le = 0
            for idx in range(so_seed):
                kw: dict[str, object] = {
                    "S_ppt": S_muc_tieu,
                    "T_C": T_muc_tieu,
                    "T_tham_chieu_C": T_muc_tieu,
                    "seed": 1000 + idx,
                }
                if truong != "co_so":
                    kw[truong] = muc
                anh_mp = sinh_anh_hai_vach_mo_phong(ThamSoMoPhong(**kw), cfg=cfg)  # type: ignore[arg-type]
                try:
                    kq = do_delta_y_tu_anh(anh_mp.anh, x_ref=anh_mp.x_ref, tao_anh_ve=False)
                    if np.isfinite(kq.delta_y_px):
                        err_px.append(float(kq.delta_y_px - anh_mp.delta_y_ly_thuyet_px))
                        if kq.chat_luong.hop_le:
                            so_hop_le += 1
                except Exception:
                    continue

            if err_px:
                arr = np.asarray(err_px, dtype=float)
                bias_px = float(np.mean(arr))
                std_px = float(np.std(arr))
            else:
                bias_px = float("nan")
                std_px = float("nan")

            dong.append(
                {
                    "nguon_du_lieu": "MO_PHONG",
                    "hieu_ung": nhom,
                    "tham_so": truong,
                    "muc": str(muc),
                    "so_mau_do_duoc": len(err_px),
                    "so_mau_dat_chat_luong": so_hop_le,
                    "tong_so_mau": so_seed,
                    "sai_lech_tb_px": round(bias_px, 4) if np.isfinite(bias_px) else None,
                    "do_lech_chuan_px": round(std_px, 4) if np.isfinite(std_px) else None,
                    "sai_lech_tb_ppt": round(bias_px / px_per_ppt, 4) if np.isfinite(bias_px) else None,
                    "do_lech_chuan_ppt": round(std_px / px_per_ppt, 4) if np.isfinite(std_px) else None,
                }
            )
    return pd.DataFrame(dong)


def main() -> None:
    df = danh_gia_do_ben_vung(so_seed=10)
    out_path = ROOT / "outputs" / "danh_gia_do_ben_vung_MO_PHONG.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"Da luu bang do ben vung MO PHONG tai: {out_path}")
    print("\n=== BANG DO BEN VUNG THUAT TOAN TREN ANH MO PHONG (S=20 ppt, T=25 C, N=10/muc) ===")
    cols = [
        "hieu_ung",
        "muc",
        "so_mau_dat_chat_luong",
        "sai_lech_tb_px",
        "do_lech_chuan_px",
        "sai_lech_tb_ppt",
        "do_lech_chuan_ppt",
    ]
    print(df[cols].to_string(index=False))


if __name__ == "__main__":
    main()
