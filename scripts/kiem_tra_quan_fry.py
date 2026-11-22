"""Công cụ đối chiếu 10 hệ số công thức Quan–Fry (a0..a9) do người dùng tự nhập từ bài gốc (R8 + siết V2)."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.optics import HE_SO_QUAN_FRY_TRONG_MA
from core.trang_thai_cau_hinh import GHI_CHU_GIOI_HAN_QUAN_FRY, XAC_NHAN_QF_MAC_DINH

CANH_BAO_KHONG_CHEP_TU_MA = (
    "CẢNH BÁO: Nếu giá trị bạn nhập chép y hệt từ mã hoặc từ tài liệu hướng dẫn "
    "thì đây KHÔNG phải đối chiếu bài gốc."
)
CANH_BAO_TRUNG_CHUOI_MA = (
    "Cả 10 giá trị trùng hệt từng ký tự với chuỗi trong mã; hãy chắc rằng bạn đã đọc từ bài gốc."
)
TRANG_BANG_VO_NGHIA = {"x", "xx", "xxx", "na", "n/a", "-", "--", "---", "...", "none", "null", "todo", "tbd", "?"}


def _chuan_hoa_ten(ten: str) -> str:
    """Chuẩn hóa tên người để so sánh trùng: bỏ dấu tiếng Việt (kể cả đ), hạ chữ thường, gom khoảng trắng."""
    s = " ".join(str(ten or "").strip().split())
    s = s.replace("đ", "d").replace("Đ", "D")
    nfd = unicodedata.normalize("NFD", s)
    khong_dau = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    return " ".join(khong_dau.lower().split())


def _kiem_tra_dinh_dang_trang_bang(tb: str) -> str | None:
    """Trả thông báo lỗi nếu `trang_bang` quá ngắn, vô nghĩa hoặc thiếu chữ số; trả None nếu hợp lệ."""
    s = " ".join(str(tb or "").strip().split())
    if s.lower() in TRANG_BANG_VO_NGHIA:
        return f"chuỗi vô nghĩa ({s!r})"
    if len(s) < 3:
        return f"quá ngắn ({len(s)} < 3 ký tự)"
    if not re.search(r"\d", s):
        return "thiếu ít nhất một chữ số (số trang hoặc số bảng)"
    return None


def doi_chieu_csv_quan_fry(
    csv_path: str | Path,
    tol: float = 1e-9,
    luu_xac_nhan: bool = False,
    file_xac_nhan: str | Path | None = None,
    nguoi_doi_chieu: str | None = None,
    nguoi_xac_nhan_2: str | None = None,
    trich_dan: str | None = None,
) -> tuple[bool, list[dict[str, Any]], str]:
    """Đọc CSV đối chiếu người dùng điền và so từng hệ số với HE_SO_QUAN_FRY_TRONG_MA.

    Bắt buộc mọi hệ số a0..a9 đều có cả `gia_tri_bai_goc` VÀ `trang_bang` không rỗng.
    Khi `luu_xac_nhan=True`, bắt buộc `nguoi_doi_chieu` và `trich_dan` không rỗng.
    Trả `(khop_tat_ca, bang_chi_tiet, thong_diep)`.
    """
    p = Path(csv_path)
    if not p.exists():
        return False, [], f"Không tìm thấy file CSV: {p}"

    raw_bytes = p.read_bytes()
    sha256_csv = hashlib.sha256(raw_bytes).hexdigest()

    with open(p, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return False, [], "File CSV rỗng hoặc thiếu dòng tiêu đề."
        cols = {c.strip(): c for c in reader.fieldnames if c is not None}
        if "he_so" not in cols or "gia_tri_bai_goc" not in cols or "trang_bang" not in cols:
            return (
                False,
                [],
                "CSV bắt buộc phải có đủ 3 cột 'he_so', 'gia_tri_bai_goc' và 'trang_bang' (trang/bảng trong bài gốc).",
            )
        nhap: dict[str, tuple[str, str]] = {}
        trung: list[str] = []
        for row in reader:
            k = str(row[cols["he_so"]] or "").strip()
            if not k:
                continue
            v_str = str(row[cols["gia_tri_bai_goc"]] or "").strip()
            tb = str(row[cols["trang_bang"]] or "").strip()
            if k in nhap:
                trung.append(k)
            nhap[k] = (v_str, tb)

    bang: list[dict[str, Any]] = []
    loi_he_so: list[str] = []
    chuoi_nhap_raw: dict[str, str] = {}

    if trung:
        loi_he_so.append(f"trùng dòng: {', '.join(sorted(set(trung)))}")

    for k, ref_val in HE_SO_QUAN_FRY_TRONG_MA.items():
        if k not in nhap or not nhap[k][0]:
            loi_he_so.append(f"{k} (thiếu giá_tri_bai_goc)")
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
        chuoi_nhap_raw[k] = raw_str
        if not tb:
            loi_he_so.append(f"{k} (thiếu trang_bang trong bài gốc)")
            bang.append({
                "he_so": k,
                "trong_ma": ref_val,
                "bai_goc": raw_str,
                "sai_khac_tuyet_doi": None,
                "sai_khac_tuong_doi": None,
                "trang_bang": "",
                "trang_thai": "THIEU_TRANG_BANG",
            })
            continue

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
    if not khop_tat_ca:
        return False, bang, "KHÔNG KHỚP HỆ SỐ QUAN–FRY: " + "; ".join(loi_he_so)

    trung_chuoi_ma = len(chuoi_nhap_raw) == len(HE_SO_QUAN_FRY_TRONG_MA) and all(
        chuoi_nhap_raw[k] == repr(ref_val) for k, ref_val in HE_SO_QUAN_FRY_TRONG_MA.items()
    )
    msg = f"ĐỐI CHIẾU KHỚP 10/10 HỆ SỐ QUAN–FRY (tol_rel={tol:g})."
    if trung_chuoi_ma:
        msg += f" CẢNH BÁO: {CANH_BAO_TRUNG_CHUOI_MA}"

    if luu_xac_nhan:
        loi_luu: list[str] = []
        for r in bang:
            err_tb = _kiem_tra_dinh_dang_trang_bang(str(r.get("trang_bang") or ""))
            if err_tb:
                loi_luu.append(f"{r['he_so']} (trang_bang {err_tb})")

        n1 = " ".join(str(nguoi_doi_chieu or "").strip().split())
        n2 = " ".join(str(nguoi_xac_nhan_2 or "").strip().split())
        n1_norm = _chuan_hoa_ten(n1)
        n2_norm = _chuan_hoa_ten(n2)
        if not n1:
            loi_luu.append("thiếu tên --nguoi-doi-chieu")
        elif len(n1_norm) < 3:
            loi_luu.append(f"tên --nguoi-doi-chieu ({n1!r}) quá ngắn (sau chuẩn hóa cần >= 3 ký tự)")

        if n2:
            if len(n2_norm) < 3:
                loi_luu.append(f"tên --nguoi-xac-nhan-2 ({n2!r}) quá ngắn (sau chuẩn hóa cần >= 3 ký tự)")
            if n1_norm and n2_norm == n1_norm:
                loi_luu.append("--nguoi-xac-nhan-2 phải là người khác với --nguoi-doi-chieu (khác sau chuẩn hóa dấu/hoa thường)")

        td = " ".join(str(trich_dan or "").strip().split())
        if not td:
            loi_luu.append("thiếu --trich-dan đầy đủ bài gốc")
        else:
            if len(td) < 25:
                loi_luu.append(f"--trich-dan quá ngắn ({len(td)} < 25 ký tự)")
            if not re.search(r"\b(?:19|20)\d{2}\b", td):
                loi_luu.append("--trich-dan phải chứa năm xuất bản 4 chữ số (19xx hoặc 20xx)")

        if loi_luu:
            return False, bang, "TỪ CHỐI LƯU XÁC NHẬN (W2): " + "; ".join(loi_luu) + "."

        out_json = Path(file_xac_nhan) if file_xac_nhan is not None else XAC_NHAN_QF_MAC_DINH
        out_json.parent.mkdir(parents=True, exist_ok=True)
        so_nguoi = 2 if n2 else 1
        payload = {
            "da_doi_chieu_khop": True,
            "nguoi_doi_chieu": n1,
            "nguoi_xac_nhan_2": n2 or None,
            "so_nguoi_xac_nhan": so_nguoi,
            "trich_dan": td,
            "trung_chuoi_ma": bool(trung_chuoi_ma),
            "ghi_chu_gioi_han": GHI_CHU_GIOI_HAN_QUAN_FRY,
            "thoi_gian": datetime.now(timezone.utc).isoformat(),
            "sha256_csv": sha256_csv,
            "csv_nguoi_dung": str(p),
            "tol_rel": float(tol),
            "bang_doi_chieu": [
                {
                    "he_so": r["he_so"],
                    "trong_ma": r["trong_ma"],
                    "bai_goc": r["bai_goc"],
                    "trang_bang": r["trang_bang"],
                    "trang_thai": r["trang_thai"],
                }
                for r in bang
            ],
            "he_so_da_kiem": list(HE_SO_QUAN_FRY_TRONG_MA.keys()),
        }
        out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        msg += f" Đã lưu xác nhận cục bộ ({so_nguoi} người) vào: {out_json}"

    return True, bang, msg


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Đối chiếu 10 hệ số Quan–Fry (a0..a9) với CSV người dùng nhập.")
    parser.add_argument("--csv", required=True, help="Đường dẫn file CSV (bắt buộc đủ 3 cột: he_so, gia_tri_bai_goc, trang_bang)")
    parser.add_argument("--tol", type=float, default=1e-9, help="Dung sai tương đối cho mỗi hệ số (mặc định 1e-9)")
    parser.add_argument(
        "--luu-xac-nhan",
        action="store_true",
        help="Chỉ lưu file xác nhận cục bộ khi 10/10 hệ số khớp, đủ trang_bang, --nguoi-doi-chieu và --trich-dan.",
    )
    parser.add_argument("--nguoi-doi-chieu", default=None, help="Bắt buộc khi --luu-xac-nhan: tên người trực tiếp đối chiếu.")
    parser.add_argument("--nguoi-xac-nhan-2", default=None, help="Tùy chọn: tên người xác nhận thứ hai (GVHD/thành viên khác).")
    parser.add_argument("--trich-dan", default=None, help="Bắt buộc khi --luu-xac-nhan: trích dẫn đầy đủ bài gốc.")
    parser.add_argument(
        "--file-xac-nhan",
        default=None,
        help="Đường dẫn JSON xác nhận (mặc định data/xac_nhan_quan_fry.json).",
    )
    args = parser.parse_args(argv)

    print(CANH_BAO_KHONG_CHEP_TU_MA)
    print()

    khop, bang, msg = doi_chieu_csv_quan_fry(
        csv_path=args.csv,
        tol=args.tol,
        luu_xac_nhan=args.luu_xac_nhan,
        file_xac_nhan=args.file_xac_nhan,
        nguoi_doi_chieu=args.nguoi_doi_chieu,
        nguoi_xac_nhan_2=args.nguoi_xac_nhan_2,
        trich_dan=args.trich_dan,
    )

    if bang:
        print(f"{'Hệ số':<6} {'Trong mã':>14} {'Bài gốc':>14} {'Trang/Bảng':<14} {'Trạng thái':<16}")
        print("-" * 70)
        for r in bang:
            bg = f"{r['bai_goc']:>14.6g}" if isinstance(r["bai_goc"], float) else f"{str(r['bai_goc']):>14}"
            tb = str(r.get("trang_bang") or "")[:14]
            print(f"{r['he_so']:<6} {r['trong_ma']:>14.6g} {bg} {tb:<14} {r['trang_thai']:<16}")
        print()

    print(msg)
    return 0 if khop else 1


if __name__ == "__main__":
    raise SystemExit(main())
