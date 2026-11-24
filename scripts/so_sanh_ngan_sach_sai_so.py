"""Đối chiếu ngân sách sai số thực nghiệm với lí thuyết — CLI X5.

Ví dụ chạy:
    python scripts/so_sanh_ngan_sach_sai_so.py --csv data/du_lieu_hieu_chuan_thuc.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.so_sanh_ngan_sach import bang_doi_chieu_df, so_sanh_ngan_sach_sai_so


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Đối chiếu ngân sách sai số thực nghiệm với lí thuyết (X5)")
    parser.add_argument("--csv", required=True, help="File CSV dữ liệu hiệu chuẩn")
    parser.add_argument("--don-vi-y", default="px", choices=["px", "mm"], help="Đơn vị Δy khi khớp đường chuẩn")
    parser.add_argument("--config", default=None, help="Đường dẫn config.yaml")
    parser.add_argument("--output-json", default=None, help="Xuất kết quả JSON")
    parser.add_argument("--output-csv", default=None, help="Xuất bảng đối chiếu CSV")
    args = parser.parse_args(argv)

    kq = so_sanh_ngan_sach_sai_so(
        args.csv,
        don_vi_y=args.don_vi_y,
        config_path=args.config,
        luu_json_path=args.output_json,
    )
    df_b = bang_doi_chieu_df(kq)
    if args.output_csv:
        p_csv = Path(args.output_csv)
        p_csv.parent.mkdir(parents=True, exist_ok=True)
        df_b.to_csv(p_csv, index=False, encoding="utf-8-sig")

    print(
        f"Thực nghiệm 1σ = {kq['sigma_tong_thuc_nghiem_ppt']:.4f} ‰ | "
        f"Lí thuyết RSS = {kq['sigma_tong_ly_thuyet_ppt']:.4f} ‰ | "
        f"Tỉ lệ = {kq['ty_le_thuc_tren_ly_thuyet']:.2f}×"
    )
    for _, r in df_b.iterrows():
        print(f"  - {r['hang_muc']}: thuc={r['thuc_nghiem_ppt']} | ly_thuyet={r['ly_thuyet_ppt']} ({r['ghi_chu']})")
    for cb in kq.get("canh_bao_chi_tiet", []):
        print(f"  [!] ({cb['ma']}) {cb['thong_diep']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
