"""Công cụ CLI hiệu chuẩn chéo hai nhiệt kế (ngăn mẫu vs ngăn tham chiếu) — V1.

Cách dùng:
    python scripts/hieu_chuan_cheo_nhiet_ke.py --csv data/cap_nhiet_ke.csv --nguon THUC_TE --nguoi-thuc-hien "Nguyen Van A"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.nhiet_ke import (
    CONFIG_MAC_DINH,
    FILE_HIEU_CHUAN_NHIET_KE_MAC_DINH,
    doc_do_phan_giai_toi_da_yaml,
    doc_nguong_nhiet_ke_cheo_yaml,
    hieu_chuan_cheo_tu_df,
    luu_hieu_chuan_cheo_nhiet_ke,
    tinh_sha256_file,
)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Hiệu chuẩn chéo độ lệch giữa 2 nhiệt kế (ngăn tham chiếu vs mẫu).")
    parser.add_argument("--csv", required=True, help="CSV các cặp số đọc trong cùng cốc nước khuấy đều.")
    parser.add_argument("--nguoi-thuc-hien", required=True, help="Bắt buộc: tên người đo hiệu chuẩn chéo.")
    parser.add_argument("--nguon", choices=("THUC_TE", "MO_PHONG"), default=None, help="Nguồn dữ liệu (THUC_TE hoặc MO_PHONG).")
    parser.add_argument("--out", default=str(FILE_HIEU_CHUAN_NHIET_KE_MAC_DINH), help="File JSON lưu kết quả.")
    parser.add_argument("--config", default=str(CONFIG_MAC_DINH), help="Đường dẫn file config.yaml.")
    parser.add_argument("--do-phan-giai-mau", type=float, default=None, help="Độ phân giải nhiệt kế mẫu (°C); bỏ trống để tự suy ra.")
    parser.add_argument("--do-phan-giai-tc", type=float, default=None, help="Độ phân giải nhiệt kế tham chiếu (°C); bỏ trống để tự suy ra.")
    args = parser.parse_args(argv)

    p_csv = Path(args.csv)
    if not p_csv.exists():
        print(f"LỖI: Không tìm thấy file CSV '{p_csv}'.", file=sys.stderr)
        return 1

    so_cap_min, so_muc_min = doc_nguong_nhiet_ke_cheo_yaml(args.config)
    r_max = doc_do_phan_giai_toi_da_yaml(args.config)
    try:
        df = pd.read_csv(p_csv, encoding="utf-8-sig")
        kq = hieu_chuan_cheo_tu_df(
            df,
            nguoi_thuc_hien=args.nguoi_thuc_hien,
            nguon_du_lieu=args.nguon,
            so_cap_toi_thieu=so_cap_min,
            so_muc_nhiet_toi_thieu=so_muc_min,
            sha256_csv=tinh_sha256_file(p_csv),
            do_phan_giai_mau_C=args.do_phan_giai_mau,
            do_phan_giai_tc_C=args.do_phan_giai_tc,
            do_phan_giai_toi_da_C=r_max,
        )
    except Exception as exc:
        print(f"LỖI HIỆU CHUẨN CHÉO NHIỆT KẾ: {exc}", file=sys.stderr)
        return 1

    out_path = luu_hieu_chuan_cheo_nhiet_ke(kq, args.out)
    nguon_pg = "tự suy ra từ dữ liệu" if kq.phan_giai_suy_ra else "khai báo thủ công"
    print("=== KẾT QUẢ HIỆU CHUẨN CHÉO HAI NHIỆT KẾ ===")
    print(f"- Nguồn dữ liệu: {kq.nguon_du_lieu} | Người thực hiện: {kq.nguoi_thuc_hien} | Ngày: {kq.ngay}")
    print(f"- Số cặp hợp lệ: {kq.so_cap} (yêu cầu >= {so_cap_min}) | Số mức nhiệt: {kq.so_muc_nhiet} (>= {so_muc_min})")
    print(f"- Offset trung bình (T_tc_đọc − T_mẫu_đọc): {kq.offset_C:+.4f} ± {kq.sigma_offset_C:.4f} °C")
    print(
        f"- Độ phân giải ({nguon_pg}): r_mẫu={kq.do_phan_giai_mau_C:g} °C, "
        f"r_tc={kq.do_phan_giai_tc_C:g} °C | sàn lượng tử hóa σ_pg={kq.sigma_phan_giai_C:.4f} °C"
    )
    for cb in kq.canh_bao_chi_tiet:
        print(f"- [CẢNH BÁO {cb['ma']}] {cb['thong_diep']}")
    if kq.b_ci95 is not None and kq.p_value_b is not None:
        print(
            f"- Hồi quy offset(T) = {kq.he_so_a:+.4f} {kq.he_so_b:+.5f}·T | "
            f"CI95(b)=[{kq.b_ci95[0]:+.5f}, {kq.b_ci95[1]:+.5f}], p={kq.p_value_b:.4g}"
        )
    if kq.phu_thuoc_nhiet_do:
        print("- CỜ: phu_thuoc_nhiet_do = True -> áp dụng mô hình tuyến tính offset(T) = a + b·T.")
    else:
        print("- Mô hình áp dụng: offset hằng số.")
    print(f"- Đã lưu kết quả tại: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
