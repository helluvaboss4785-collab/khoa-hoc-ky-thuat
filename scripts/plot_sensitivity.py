"""Vẽ biểu đồ độ nhạy (DỰ BÁO LÍ THUYẾT từ mô hình, KHÔNG phải số đo).

Chạy:  python scripts/plot_sensitivity.py   (từ thư mục salinity/)
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import optics as op  # noqa: E402

NHAN = "MÔ HÌNH LÍ THUYẾT - giả định trong config.yaml, chưa hiệu chuẩn"
RA = Path(__file__).resolve().parents[1] / "outputs"


def _luu(fig, ten: str) -> None:
    fig.text(0.5, 0.01, NHAN, ha="center", fontsize=7, color="red")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(RA / ten, dpi=150)
    plt.close(fig)


def main() -> None:
    cfg = op.CauHinhQuangHoc.tu_yaml()
    RA.mkdir(exist_ok=True)

    # 1) Độ nhạy theo góc A (ở S = 17,5‰, nhiệt độ tham chiếu)
    A = np.linspace(25, 47, 100)
    y = [op.pixel_moi_phan_nghin(17.5, cfg.T_tham_chieu_C, cfg, A_do=a) for a in A]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(A, y)
    ax.axvline(cfg.A_do, ls="--", c="gray", label=f"A hiện tại = {cfg.A_do}°")
    ax.set(xlabel="Góc đỉnh A (độ)", ylabel="Độ nhạy (px/‰)", title="Độ nhạy theo góc A")
    ax.legend()
    _luu(fig, "do_nhay_theo_A.png")

    # 2) Độ nhạy theo D
    D = np.linspace(0.3, 2.0, 100)
    y = [op.pixel_moi_phan_nghin(17.5, cfg.T_tham_chieu_C, cfg, D_m=d) for d in D]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(D, y)
    ax.set(xlabel="Khoảng cách tới màn D (m)", ylabel="Độ nhạy (px/‰)", title="Độ nhạy theo D")
    _luu(fig, "do_nhay_theo_D.png")

    # 3) Dịch chuyển Δy theo độ mặn 0-35‰
    S = np.linspace(0, 35, 71)
    y = [op.delta_y_vi_sai_px(s, cfg.T_tham_chieu_C, cfg.T_tham_chieu_C, cfg) for s in S]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(S, y)
    ax.set(xlabel="Độ mặn S (‰)", ylabel="Δy dự báo (px)", title="Dịch chuyển vi sai theo độ mặn")
    _luu(fig, "dich_chuyen_theo_do_man.png")
    print("Đã lưu 3 biểu đồ vào", RA)


if __name__ == "__main__":
    main()
