"""Phân tích chuỗi ảnh độ trôi laser (hai ngăn chứa cùng nước cất) — CLI X2.

Ví dụ chạy:
    python scripts/phan_tich_troi_laser.py --thu-muc data/anh_troi --nguon THUC_TE --nguoi-thuc-hien "Nguyen Van A"
    python scripts/phan_tich_troi_laser.py --thu-muc data/anh_troi --nguon THUC_TE --nguoi-thuc-hien "Nguyen Van A" --ap-dung
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.measure import AnhKhongHoTroDinhDangError
from core.troi_laser import (
    LoiDuLieuTroiKhongDuError,
    ap_dung_troi_laser_vao_tham_so,
    duong_dan_phan_tich_troi,
    phan_tich_chuoi_troi_laser,
    phan_tich_troi_laser_tu_thu_muc,
)
from scripts.xu_ly_thu_muc_anh import LoiAnhMoPhongGanNhanThucTeError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phân tích độ trôi laser và hệ số triệt nhiễu chung κ (X2)")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--thu-muc", help="Thư mục chứa chuỗi ảnh hai ngăn nước cất (≥ 60 ảnh trong ≥ 20 phút)")
    src.add_argument("--csv", help="File CSV có cột thoi_gian_phut, y_tc_px, y_mau_px")
    parser.add_argument("--buoc-thoi-gian-giay", type=float, default=None, help="Khoảng cách giây giữa 2 khung nếu ảnh thiếu EXIF")
    parser.add_argument("--nguon", default="THUC_TE", choices=["THUC_TE", "MO_PHONG"], help="Nguồn dữ liệu ảnh/chuỗi")
    parser.add_argument("--nguoi-thuc-hien", default="", help="Họ tên người thực hiện (bắt buộc khi --ap-dung)")
    parser.add_argument("--ngay", default=None, help="Ngày thực hiện (mặc định giờ hiện tại)")
    parser.add_argument("--output", default=None, help="File JSON kết quả (mặc định data/phan_tich_troi_laser.json)")
    parser.add_argument("--config", default=None, help="Đường dẫn config.yaml")
    parser.add_argument("--ap-dung", action="store_true", help="Áp dụng giá trị bảo thủ 1 − κ_lo vào data/tham_so_do_duoc.json")
    args = parser.parse_args(argv)

    try:
        if args.thu_muc:
            kq = phan_tich_troi_laser_tu_thu_muc(
                args.thu_muc,
                buoc_thoi_gian_giay=args.buoc_thoi_gian_giay,
                nguon_du_lieu=args.nguon,
                nguoi_thuc_hien=args.nguoi_thuc_hien,
                ngay=args.ngay,
                luu_json=True,
                output_path=args.output,
                config_path=args.config,
            )
        else:
            df = pd.read_csv(args.csv)
            kq = phan_tich_chuoi_troi_laser(
                df["thoi_gian_phut"].to_numpy(dtype=float),
                df["y_tc_px"].to_numpy(dtype=float),
                df["y_mau_px"].to_numpy(dtype=float),
                nguon_du_lieu=args.nguon,
                nguoi_thuc_hien=args.nguoi_thuc_hien,
                ngay=args.ngay,
                config_path=args.config,
            )
            out_p = duong_dan_phan_tich_troi(args.output)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(json.dumps(kq, ensure_ascii=False, indent=2), encoding="utf-8")
            kq["duong_dan_json"] = str(out_p)
    except AnhKhongHoTroDinhDangError as exc:
        print(f"[LOI_DINH_DANG_ANH] {exc}", file=sys.stderr)
        return 4
    except (LoiAnhMoPhongGanNhanThucTeError, LoiDuLieuTroiKhongDuError, FileNotFoundError, ValueError) as exc:
        print(f"[LOI] {exc}", file=sys.stderr)
        return 2

    print(
        f"Trạng thái: {kq['trang_thai']} | khung={kq['so_khung']} | "
        f"thời lượng={kq['thoi_luong_phut']:.2f} phút | "
        f"κ={kq['kappa']:.4f} (KTC95% [{kq['ktc_95_kappa'][0]:.4f}, {kq['ktc_95_kappa'][1]:.4f}]) | "
        f"1−κ_lo={kq['he_so_lot_bao_thu']:.4f}"
    )
    for cb in kq.get("canh_bao", []):
        print(f"  [!] {cb}")

    if args.ap_dung:
        try:
            ap_dung_troi_laser_vao_tham_so(kq, nguoi_thuc_hien=args.nguoi_thuc_hien, ngay=args.ngay)
            print("Đã áp dụng he_so_triet_chung (1 − κ_lo) vào data/tham_so_do_duoc.json.")
        except (LoiDuLieuTroiKhongDuError, ValueError) as exc:
            print(f"[TU_CHOI_AP_DUNG] {exc}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
