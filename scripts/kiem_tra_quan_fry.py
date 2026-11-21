"""Công cụ đối chiếu 10 hệ số công thức Quan–Fry (a0..a9) do người dùng tự nhập từ bài gốc."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.optics import HE_SO_QUAN_FRY_TRONG_MA
from core.trang_thai_cau_hinh import XAC_NHAN_QF_MAC_DINH


def doi_chieu_csv_quan_fry(
    csv_path: str | Path,
    tol: float = 1e-9,
    luu_xac_nhan: bool = False,
    file_xac_nhan: str | Path | None = None,
) -> tuple[bool, list[dict[str, Any]], str]:
    """Đọc CSV đối chiếu người dùng điền và so từng hệ số với HE_SO_QUAN_FRY_TRONG_MA.

    Trả `(khop_tat_ca, bang_chi_tiet, thong_diep)`.
    Chỉ ghi file JSON xác nhận khi `khop_tat_ca == True` VÀ `luu_xac_nhan == True`.
    """
    p = Path(csv_path)
    if not p.exists():
        return False, [], f"Không tìm thấy file CSV: {p}"

    with open(p, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return False, [], "File CSV rỗng hoặc thiếu dòng tiêu đề."
        cols = {c.strip(): c for c in reader.fieldnames if c is not None}
        if "he_so" not in cols or "gia_tri_bai_goc" not in cols:
            return (
                False,
                [],
                "CSV phải có ít nhất 2 cột 'he_so' và 'gia_tri_bai_goc' (tùy chọn thêm 'trang_bang').",
            )
        nhap: dict[str, tuple[str, str]] = {}
        trung: list[str] = []
        for row in reader:
            k = str(row[cols["he_so"]] or "").strip()
            if not k:
                continue
            v_str = str(row[cols["gia_tri_bai_goc"]] or "").strip()
            tb = str(row[cols["trang_bang"]] or "").strip() if "trang_bang" in cols else ""
            if k in nhap:
                trung.append(k)
            nhap[k] = (v_str, tb)

    bang: list[dict[str, Any]] = []
    loi_he_so: list[str] = []

    if trung:
        loi_he_so.append(f"trùng dòng: {', '.join(sorted(set(trung)))}")

    for k, ref_val in HE_SO_QUAN_FRY_TRONG_MA.items():
        if k not in nhap or not nhap[k][0]:
            loi_he_so.append(f"{k} (thiếu giá trị)")
            bang.append({
                "he_so": k,
                "trong_ma": ref_val,
                "bai_goc": None,
                "sai_khac_tuyet_doi": None,
                "sai_khac_tuong_doi": None,
                "trang_bang": nhap.get(k, ("", ""))[1],
                "trang_thai": "THIEU",
            })
            continue
        raw_str, tb = nhap[k]
        try:
            user_val = float(raw_str)
        except ValueError:
            loi_he_so.append(f"{k} (không phải số: {raw_str!r})")
            bang.append({
                "he_so": k,
                "trong_ma": ref_val,
                "bai_goc": raw_str,
                "sai_khac_tuyet_doi": None,
                "sai_khac_tuong_doi": None,
                "trang_bang": tb,
                "trang_thai": "LOI_DINH_DANG",
            })
            continue

        diff_abs = abs(user_val - ref_val)
        diff_rel = diff_abs / abs(ref_val) if ref_val != 0.0 else diff_abs
        khop = math.isclose(user_val, ref_val, rel_tol=tol, abs_tol=0.0) and not math.isnan(user_val)
        if not khop:
            loi_he_so.append(f"{k} (mã={ref_val!r}, bài gốc={user_val!r})")
        bang.append({
            "he_so": k,
            "trong_ma": ref_val,
            "bai_goc": user_val,
            "sai_khac_tuyet_doi": diff_abs,
            "sai_khac_tuong_doi": diff_rel,
            "trang_bang": tb,
            "trang_thai": "KHOP" if khop else "LECH",
        })

    la_he_so_la = sorted(set(nhap.keys()) - set(HE_SO_QUAN_FRY_TRONG_MA.keys()))
    if la_he_so_la:
        loi_he_so.append(f"tên hệ số không hợp lệ: {', '.join(la_he_so_la)}")

    khop_tat_ca = len(loi_he_so) == 0 and all(r["trang_thai"] == "KHOP" for r in bang)
    if khop_tat_ca:
        msg = f"ĐỐI CHIẾU KHỚP 10/10 HỆ SỐ QUAN–FRY (tol_rel={tol:g})."
        if luu_xac_nhan:
            out_json = Path(file_xac_nhan) if file_xac_nhan is not None else XAC_NHAN_QF_MAC_DINH
            out_json.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "da_doi_chieu_khop": True,
                "thoi_gian": datetime.now(timezone.utc).isoformat(),
                "csv_nguoi_dung": str(p),
                "tol_rel": float(tol),
                "he_so_da_kiem": list(HE_SO_QUAN_FRY_TRONG_MA.keys()),
            }
            out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            msg += f" Đã lưu xác nhận cục bộ vào: {out_json}"
    else:
        msg = "KHÔNG KHỚP HỆ SỐ QUAN–FRY: " + "; ".join(loi_he_so)

    return khop_tat_ca, bang, msg


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Đối chiếu 10 hệ số Quan–Fry (a0..a9) với CSV người dùng nhập.")
    parser.add_argument("--csv", required=True, help="Đường dẫn file CSV (cột: he_so, gia_tri_bai_goc, [trang_bang])")
    parser.add_argument("--tol", type=float, default=1e-9, help="Dung sai tương đối cho mỗi hệ số (mặc định 1e-9)")
    parser.add_argument(
        "--luu-xac-nhan",
        action="store_true",
        help="Chỉ lưu file xác nhận cục bộ khi 10/10 hệ số đều khớp.",
    )
    parser.add_argument(
        "--file-xac-nhan",
        default=None,
        help="Đường dẫn JSON xác nhận (mặc định data/xac_nhan_quan_fry.json).",
    )
    args = parser.parse_args(argv)

    khop, bang, msg = doi_chieu_csv_quan_fry(
        csv_path=args.csv,
        tol=args.tol,
        luu_xac_nhan=args.luu_xac_nhan,
        file_xac_nhan=args.file_xac_nhan,
    )

    if bang:
        print(f"{'Hệ số':<6} {'Trong mã':>14} {'Bài gốc':>14} {'Lệch tuy.đối':>14} {'Lệch t.đối':>12} {'Trạng thái':<12}")
        print("-" * 78)
        for r in bang:
            bg = f"{r['bai_goc']:>14.6g}" if isinstance(r["bai_goc"], float) else f"{str(r['bai_goc']):>14}"
            da = f"{r['sai_khac_tuyet_doi']:>14.3e}" if isinstance(r["sai_khac_tuyet_doi"], float) else f"{'-':>14}"
            dr = f"{r['sai_khac_tuong_doi']:>12.3e}" if isinstance(r["sai_khac_tuong_doi"], float) else f"{'-':>12}"
            print(f"{r['he_so']:<6} {r['trong_ma']:>14.6g} {bg} {da} {dr} {r['trang_thai']:<12}")
        print()

    print(msg)
    return 0 if khop else 1


if __name__ == "__main__":
    raise SystemExit(main())
