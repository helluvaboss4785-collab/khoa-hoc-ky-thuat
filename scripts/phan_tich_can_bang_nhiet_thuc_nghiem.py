"""Phân tích cân bằng nhiệt hai ngăn sau khi đổ mẫu thực nghiệm — CLI X3.

Ví dụ chạy:
    python scripts/phan_tich_can_bang_nhiet_thuc_nghiem.py --csv data/nhiet_do_sau_do.csv --nguon THUC_TE --nguoi-thuc-hien "Nguyen Van A"
    python scripts/phan_tich_can_bang_nhiet_thuc_nghiem.py --csv data/nhiet_do_sau_do.csv --nguon THUC_TE --nguoi-thuc-hien "Nguyen Van A" --ap-dung
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.can_bang_nhiet import (
    LoiCanBangNhietKhongHopLeError,
    ap_dung_can_bang_nhiet_vao_tham_so,
    phan_tich_can_bang_nhiet_tu_csv,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phân tích cân bằng nhiệt hai ngăn sau khi đổ mẫu (X3)")
    parser.add_argument("--csv", required=True, help="File CSV chuỗi nhiệt độ theo ma_lan_do và thoi_gian_giay")
    parser.add_argument("--nguon", default="THUC_TE", choices=["THUC_TE", "MO_PHONG"], help="Nguồn dữ liệu")
    parser.add_argument("--nguoi-thuc-hien", default="", help="Họ tên người thực hiện (bắt buộc khi --ap-dung)")
    parser.add_argument("--ngay", default=None, help="Ngày thực hiện")
    parser.add_argument("--output", default=None, help="File JSON kết quả (mặc định data/phan_tich_can_bang_nhiet.json)")
    parser.add_argument("--config", default=None, help="Đường dẫn config.yaml")
    parser.add_argument("--ap-dung", action="store_true", help="Áp dụng sigma_D vào data/tham_so_do_duoc.json")
    args = parser.parse_args(argv)

    try:
        kq = phan_tich_can_bang_nhiet_tu_csv(
            args.csv,
            nguon_du_lieu=args.nguon,
            nguoi_thuc_hien=args.nguoi_thuc_hien,
            ngay=args.ngay,
            luu_json=True,
            output_path=args.output,
            config_path=args.config,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"[LOI] {exc}", file=sys.stderr)
        return 2

    if kq["hop_le"]:
        print(
            f"Trạng thái: {kq['trang_thai']} | hợp lệ={kq['so_lan_do_hop_le']}/{kq['so_lan_do_tong']} | "
            f"median τ={kq['median_tau_giay']:.1f}s (p90={kq['p90_tau_giay']:.1f}s) | "
            f"p90 t_chờ={kq['p90_t_cho_giay']:.1f}s | "
            f"σ_D(chưa)={kq['sigma_D_khi_chua_do_C']:.3f}°C | σ_D(ổn định)={kq['sigma_D_khi_da_on_dinh_C']:.3f}°C"
        )
    else:
        print(f"Trạng thái: {kq['trang_thai']} | hợp lệ=0/{kq['so_lan_do_tong']}")
    for cb in kq.get("canh_bao", []):
        print(f"  [!] {cb}")

    if args.ap_dung:
        try:
            ap_dung_can_bang_nhiet_vao_tham_so(kq, nguoi_thuc_hien=args.nguoi_thuc_hien, ngay=args.ngay)
            print("Đã áp dụng sigma_D_khi_chua_do_C và sigma_D_khi_da_on_dinh_C vào data/tham_so_do_duoc.json.")
        except (LoiCanBangNhietKhongHopLeError, ValueError) as exc:
            print(f"[TU_CHOI_AP_DUNG] {exc}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
