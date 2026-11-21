"""CLI kiểm tra thiết kế thí nghiệm hiệu chuẩn trước khi dựng đường chuẩn (không chặn quy trình)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import calibration as cal  # noqa: E402
from core.kiem_tra_thiet_ke import kiem_tra_thiet_ke_thi_nghiem, kiem_tra_thiet_ke_tu_csv  # noqa: E402
from sim.synth import sinh_du_lieu_hieu_chuan_mo_phong  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Kiểm tra thiết kế thí nghiệm của tập dữ liệu hiệu chuẩn (báo cáo không chặn)."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--csv", help="Đường dẫn tới file CSV hiệu chuẩn.")
    group.add_argument("--mo-phong", action="store_true", help="Kiểm tra trên tập 72 điểm mô phỏng mặc định.")
    parser.add_argument("--muon-hoc-D", action="store_true", help="Bắt buộc kiểm tra biến thiên chênh nhiệt D = T_mau - T_tc.")
    parser.add_argument("--don-vi-y", choices=("px", "mm"), default="px", help="Đơn vị trục y khi dựng đường chuẩn.")
    parser.add_argument("--config", default=str(cal.CONFIG_MAC_DINH), help="Đường dẫn file config.yaml.")
    parser.add_argument("--json", action="store_true", help="In đầu ra dạng JSON.")
    parser.add_argument("--strict", action="store_true", help="Trả mã thoát 1 nếu còn hạng mục CHƯA ĐẠT.")
    args = parser.parse_args(argv)

    if args.mo_phong:
        df = sinh_du_lieu_hieu_chuan_mo_phong()
        kq = kiem_tra_thiet_ke_thi_nghiem(
            df,
            config_path=args.config,
            muon_hoc_D=args.muon_hoc_D,
            don_vi_y=args.don_vi_y,
        )
    else:
        kq = kiem_tra_thiet_ke_tu_csv(
            args.csv,
            config_path=args.config,
            muon_hoc_D=args.muon_hoc_D,
            don_vi_y=args.don_vi_y,
        )

    if args.json:
        print(json.dumps(kq, ensure_ascii=False, indent=2))
    else:
        print("=== KIỂM TRA THIẾT KẾ THÍ NGHIỆM HIỆU CHUẨN (KHÔNG CHẶN) ===")
        for item in kq["muc_kiem"]:
            tag = {
                "dat": "ĐẠT",
                "chua_dat": "CHƯA ĐẠT",
                "canh_bao": "CẢNH BÁO",
                "bo_qua": "BỎ QUA",
            }.get(item["trang_thai"], item["trang_thai"].upper())
            print(f" - [{tag:8s}] {item['ten']}: {item['gia_tri_do']} (yêu cầu: {item['yeu_cau']})")
            if item["goi_y"]:
                print(f"     -> Gợi ý: {item['goi_y']}")
        print(
            f"Tổng kết: hợp lệ={kq['hop_le_tong_quat']} | "
            f"Đạt={kq['so_dat']}, Chưa đạt={kq['so_chua_dat']}, Cảnh báo={kq['so_canh_bao']}"
        )

    if args.strict and not kq["hop_le_tong_quat"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
