"""So sánh độ nhạy nhiệt vi sai giữa mô hình chiết suất tuyến tính và Quan–Fry (T10)."""
from __future__ import annotations

import sys
import warnings
from dataclasses import replace
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.optics import CauHinhQuangHoc, delta_y_vi_sai_px, pixel_moi_phan_nghin


def so_sanh_quan_fry() -> pd.DataFrame:
    cfg_lin = replace(CauHinhQuangHoc.tu_yaml(), mo_hinh_chiet_suat="tuyen_tinh")
    cfg_qf = replace(cfg_lin, mo_hinh_chiet_suat="quan_fry")

    h = 0.05  # bước sai phân (°C)
    dong: list[dict[str, object]] = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for S in (0.0, 15.0, 30.0):
            for T_mau in (15.0, 20.0, 25.0, 30.0, 35.0):
                T_tc = 25.0
                # 1. Cả hai ngăn cùng thay đổi nhiệt độ (đo lường ảnh hưởng chung còn dư)
                d_cung_lin = (
                    delta_y_vi_sai_px(S, T_mau + h, T_mau + h, cfg_lin)
                    - delta_y_vi_sai_px(S, T_mau - h, T_mau - h, cfg_lin)
                ) / (2.0 * h)
                d_cung_qf = (
                    delta_y_vi_sai_px(S, T_mau + h, T_mau + h, cfg_qf)
                    - delta_y_vi_sai_px(S, T_mau - h, T_mau - h, cfg_qf)
                ) / (2.0 * h)

                # 2. Chênh lệch nhiệt độ hai ngăn (T_tc cố định ở 25 °C)
                d_chenh_lin = (
                    delta_y_vi_sai_px(S, T_mau + h, T_tc, cfg_lin)
                    - delta_y_vi_sai_px(S, T_mau - h, T_tc, cfg_lin)
                ) / (2.0 * h)
                d_chenh_qf = (
                    delta_y_vi_sai_px(S, T_mau + h, T_tc, cfg_qf)
                    - delta_y_vi_sai_px(S, T_mau - h, T_tc, cfg_qf)
                ) / (2.0 * h)

                sens_lin = pixel_moi_phan_nghin(S, T_mau, cfg_lin)
                sens_qf = pixel_moi_phan_nghin(S, T_mau, cfg_qf)

                dong.append(
                    {
                        "S_ppt": S,
                        "T_mau_C": T_mau,
                        "T_tc_C": T_tc,
                        "do_nhay_S_lin_px_ppt": round(sens_lin, 4),
                        "do_nhay_S_qf_px_ppt": round(sens_qf, 4),
                        "d_dy_dT_cung_nhiet_lin_px_C": round(d_cung_lin, 4),
                        "d_dy_dT_cung_nhiet_qf_px_C": round(d_cung_qf, 4),
                        "d_dy_dD_chenh_lin_px_C": round(d_chenh_lin, 4),
                        "d_dy_dD_chenh_qf_px_C": round(d_chenh_qf, 4),
                    }
                )
    return pd.DataFrame(dong)


def main() -> None:
    df = so_sanh_quan_fry()
    out_path = ROOT / "outputs" / "so_sanh_quan_fry.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"Da luu bang so sanh Quan-Fry tai: {out_path}\n")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
