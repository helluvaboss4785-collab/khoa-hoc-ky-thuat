"""Công cụ CLI hiệu chuẩn méo ống kính từ thư mục ảnh bàn cờ (Q6).

Cách dùng:
    python scripts/hieu_chuan_ong_kinh.py --thu-muc data/ban_co_phone1 --id-dien-thoai iphone_13 --nguon THUC_TE
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.ong_kinh import hieu_chuan_tu_anh_ban_co, luu_tham_so_ong_kinh  # noqa: E402

DUOI_ANH_HOP_LE = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def main() -> None:
    ap = argparse.ArgumentParser(description="Hiệu chuẩn ma trận camera và hệ số méo ống kính bằng ảnh bàn cờ")
    ap.add_argument("--thu-muc", type=Path, required=True, help="Thư mục chứa ảnh bàn cờ (tối thiểu 3 ảnh)")
    ap.add_argument("--id-dien-thoai", required=True, help="Mã nhận diện điện thoại (ví dụ: iphone_13)")
    ap.add_argument(
        "--nguon",
        required=True,
        choices=["THUC_TE", "MO_PHONG"],
        help="BẮT BUỘC: nguồn gốc bộ ảnh bàn cờ (THUC_TE hoặc MO_PHONG)",
    )
    ap.add_argument("--goc-ngang", type=int, default=9, help="Số góc trong theo chiều ngang bàn cờ (mặc định 9)")
    ap.add_argument("--goc-doc", type=int, default=6, help="Số góc trong theo chiều dọc bàn cờ (mặc định 6)")
    ap.add_argument("--o-mm", type=float, default=20.0, help="Kích thước cạnh ô bàn cờ thật (mm, mặc định 20)")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "data" / "ong_kinh", help="Thư mục lưu file JSON")
    args = ap.parse_args()

    if not args.thu_muc.exists() or not args.thu_muc.is_dir():
        print(f"LOI: Khong tim thay thu muc: {args.thu_muc}", file=sys.stderr)
        sys.exit(2)

    ds_anh = []
    for p in sorted(args.thu_muc.iterdir()):
        if p.is_file() and p.suffix.lower() in DUOI_ANH_HOP_LE:
            img = cv2.imread(str(p), cv2.IMREAD_COLOR)
            if img is not None:
                ds_anh.append(img)

    try:
        ts = hieu_chuan_tu_anh_ban_co(
            ds_anh,
            id_dien_thoai=args.id_dien_thoai,
            co_goc_ban_co=(args.goc_ngang, args.goc_doc),
            kich_thuoc_o_mm=args.o_mm,
            nguon_du_lieu=args.nguon,
        )
        out_path = luu_tham_so_ong_kinh(ts, args.out_dir)
    except Exception as exc:
        print(f"LOI: {exc}", file=sys.stderr)
        sys.exit(2)

    print(f"[{ts.nguon_du_lieu}] Hieu chuan thanh cong {ts.id_dien_thoai} tu {ts.so_anh_su_dung} anh ban co:")
    print(f"- Sai so tai chieu RMS: {ts.sai_so_tai_chieu_px:.4f} px")
    print(f"- He so meo [k1, k2, p1, p2, k3]: {[round(v, 5) for v in ts.he_so_meo]}")
    print(f"- Da luu tai: {out_path}")


if __name__ == "__main__":
    main()
