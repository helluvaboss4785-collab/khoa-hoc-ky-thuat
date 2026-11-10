"""Dựng đường chuẩn từ file CSV đo thật (hoặc dữ liệu mô phỏng nếu chưa có).

Cách chạy (trong thư mục salinity/):
    python scripts/dung_duong_chuan.py --csv data/hieu_chuan_cua_toi.csv
    python scripts/dung_duong_chuan.py            # chưa có dữ liệu -> dùng MÔ PHỎNG

Kết quả lưu trong outputs/: duong_chuan.png, phan_du.png, he_so_hieu_chuan*.json,
sai_so_theo_muc.csv.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

GOC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GOC))

from core import calibration as cal  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Dựng đường chuẩn Δy = f(S, T)")
    ap.add_argument("--csv", type=Path, default=None, help="File CSV dữ liệu hiệu chuẩn đo thật")
    ap.add_argument("--bac", type=int, choices=(1, 2), default=None, help="Ép bậc đa thức (mặc định: tự chọn)")
    args = ap.parse_args()

    if args.csv is None:
        from sim.synth import sinh_du_lieu_hieu_chuan_mo_phong
        print("!!! Không có file CSV -> dùng", cal.NHAN_CHUA_HIEU_CHUAN)
        df = sinh_du_lieu_hieu_chuan_mo_phong()
    else:
        df = cal.doc_csv_hieu_chuan(args.csv)

    bc = cal.dung_duong_chuan(df, cal.CauHinhHieuChuan.tu_yaml(), bac_ep=args.bac)
    mh = bc.mo_hinh
    out = GOC / "outputs"
    out.mkdir(exist_ok=True)

    print("=" * 70)
    print("TRẠNG THÁI:", mh.nhan)
    print(f"Số điểm: {mh.so_diem} (train {len(bc.df_train)}, test {len(bc.df_test)})")
    print("RMSE kiểm định chéo (px):", {k: round(v, 4) for k, v in bc.rmse_kiem_dinh_cheo.items()})
    print("Chọn:", bc.ly_do_chon)
    print("Hệ số (ΔT = T −", mh.T_ref, "°C):")
    for h, c in zip(mh.hang, mh.he_so):
        print(f"   {h:>3}: {c:+.6g}")
    print(f"R² = {mh.R2:.6f} | RMSE trong mẫu = {mh.RMSE_px:.4f} px | s_res = {mh.s_res_px:.4f} px")
    print(f"Tập test: RMSE = {bc.RMSE_test_px:.4f} px = {bc.RMSE_test_ppt:.4f} ‰")
    print("\nSai số theo từng mức độ mặn:")
    print(bc.sai_so_theo_muc.round(4).to_string(index=False))
    for c in bc.canh_bao:
        print("CẢNH BÁO:", c)
    print("=" * 70)

    duoi = "_MO_PHONG" if mh.la_mo_phong else ""
    mh.luu_json(out / f"he_so_hieu_chuan{duoi}.json")
    bc.sai_so_theo_muc.to_csv(out / f"sai_so_theo_muc{duoi}.csv", index=False, encoding="utf-8-sig")
    cal.ve_duong_chuan(bc).savefig(out / f"duong_chuan{duoi}.png")
    cal.ve_phan_du(bc).savefig(out / f"phan_du{duoi}.png")
    print("Đã lưu kết quả vào", out)


if __name__ == "__main__":
    main()

