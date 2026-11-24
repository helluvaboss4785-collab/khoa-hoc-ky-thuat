"""Phân tích khả năng chuyển đường chuẩn giữa điện thoại (LOPO) và mẻ pha (LOBO) — CLI X4.

Ví dụ chạy:
    python scripts/phan_tich_chuyen_duong_chuan.py --csv data/du_lieu_hieu_chuan_thuc.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.chuyen_duong_chuan import bang_tom_tat_chuyen_duong_chuan, phan_tich_chuyen_duong_chuan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phân tích chuyển đường chuẩn giữa điện thoại và mẻ pha (X4)")
    parser.add_argument("--csv", required=True, help="File CSV hiệu chuẩn (có id_dien_thoai, ma_me_pha, px_per_mm)")
    parser.add_argument("--config", default=None, help="Đường dẫn config.yaml")
    parser.add_argument("--output-json", default=None, help="Xuất kết quả JSON chi tiết")
    parser.add_argument("--output-csv", default=None, help="Xuất bảng tóm tắt CSV")
    args = parser.parse_args(argv)

    kq = phan_tich_chuyen_duong_chuan(
        args.csv,
        config_path=args.config,
        luu_json_path=args.output_json,
    )
    df_bang = bang_tom_tat_chuyen_duong_chuan(kq)
    if args.output_csv:
        p_csv = Path(args.output_csv)
        p_csv.parent.mkdir(parents=True, exist_ok=True)
        df_bang.to_csv(p_csv, index=False, encoding="utf-8-sig")

    print(f"Trạng thái: {kq['trang_thai']} | Nguồn: {kq['nguon_du_lieu']} | Ngưỡng RMS: {kq['nguong_RMS_ppt']} ‰")
    for _, r in df_bang.iterrows():
        print(
            f"  - {r['truc']} [{r['don_vi_y']}]: {r['trang_thai']} | "
            f"nhóm={r['so_nhom']} | RMS={r['rms_ppt']} | bias={r['bias_ppt']}"
        )
    for cb in kq.get("canh_bao_chi_tiet", []):
        print(f"  [!] ({cb['cap']}) {cb['thong_diep']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
