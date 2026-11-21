"""Kiểm thử R8 & V2: công cụ đối chiếu 10 hệ số Quan–Fry và 3 trạng thái R7 (dữ liệu giả chỉ kiểm logic)."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.optics import HE_SO_QUAN_FRY_TRONG_MA
from core.trang_thai_cau_hinh import XAC_NHAN_QF_MAC_DINH, liet_ke_tham_so_chua_xac_nhan


def _ghi_csv_gia(
    path: Path,
    ghi_de: dict[str, float] | None = None,
    bo_qua: set[str] | None = None,
    bo_trang_bang: set[str] | None = None,
    co_cot_trang_bang: bool = True,
) -> None:
    """Tạo CSV đối chiếu giả trong tmp_path — dữ liệu giả chỉ kiểm logic."""
    ghi_de = ghi_de or {}
    bo_qua = bo_qua or set()
    bo_trang_bang = bo_trang_bang or set()
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if co_cot_trang_bang:
            w.writerow(["he_so", "gia_tri_bai_goc", "trang_bang"])
        else:
            w.writerow(["he_so", "gia_tri_bai_goc"])
        for k, v in HE_SO_QUAN_FRY_TRONG_MA.items():
            if k in bo_qua:
                continue
            val = ghi_de.get(k, v)
            if co_cot_trang_bang:
                tb = "" if k in bo_trang_bang else f"Eq.(1) {k}"
                w.writerow([k, repr(val), tb])
            else:
                w.writerow([k, repr(val)])


def test_v2_doi_chieu_quan_fry_tu_choi_thieu_va_ba_trang_thai_r7(tmp_path: Path):
    """V2: thiếu trang_bang -> từ chối; thiếu người/trích dẫn -> từ chối; lệch 1 hệ số -> !=0; khớp -> đủ 3 trạng thái R7."""
    assert not XAC_NHAN_QF_MAC_DINH.exists(), "Không được tạo sẵn data/xac_nhan_quan_fry.json trong repo"

    # 1. Thiếu trang_bang cho một hệ số (a3) -> từ chối và nêu rõ a3
    csv_thieu_tb = tmp_path / "qf_thieu_tb.csv"
    _ghi_csv_gia(csv_thieu_tb, bo_trang_bang={"a3"})
    file_no = tmp_path / "no_create.json"
    p_tb = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "kiem_tra_quan_fry.py"),
            "--csv",
            str(csv_thieu_tb),
            "--luu-xac-nhan",
            "--nguoi-doi-chieu",
            "HS A",
            "--trich-dan",
            "Quan & Fry 1995 (gia)",
            "--file-xac-nhan",
            str(file_no),
        ],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert p_tb.returncode != 0
    assert "a3" in (p_tb.stdout + p_tb.stderr)
    assert "KHÔNG phải đối chiếu bài gốc" in p_tb.stdout
    assert not file_no.exists()

    # 2. Thiếu cột trang_bang hoàn toàn -> từ chối
    csv_no_col = tmp_path / "qf_no_col.csv"
    _ghi_csv_gia(csv_no_col, co_cot_trang_bang=False)
    p_nc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "kiem_tra_quan_fry.py"), "--csv", str(csv_no_col)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert p_nc.returncode != 0

    # 3. Đủ CSV hợp lệ nhưng thiếu --nguoi-doi-chieu hoặc thiếu --trich-dan khi --luu-xac-nhan -> từ chối, không ghi file
    csv_khop = tmp_path / "qf_khop.csv"
    _ghi_csv_gia(csv_khop)
    p_no_n1 = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "kiem_tra_quan_fry.py"),
            "--csv", str(csv_khop), "--luu-xac-nhan", "--trich-dan", "Quan & Fry 1995", "--file-xac-nhan", str(file_no),
        ],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert p_no_n1.returncode != 0 and not file_no.exists()

    p_no_td = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "kiem_tra_quan_fry.py"),
            "--csv", str(csv_khop), "--luu-xac-nhan", "--nguoi-doi-chieu", "HS A", "--file-xac-nhan", str(file_no),
        ],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert p_no_td.returncode != 0 and not file_no.exists()

    # 4. Đủ thông tin 1 người -> thoát 0, ghi file đủ trường, R7 ở trạng thái xac_nhan_1_nguoi
    file_xn_1 = tmp_path / "xac_nhan_1.json"
    p_ok1 = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "kiem_tra_quan_fry.py"),
            "--csv", str(csv_khop),
            "--luu-xac-nhan",
            "--nguoi-doi-chieu", "Nguyen Van A",
            "--trich-dan", "Quan & Fry, Applied Optics, 1995 (chi kiem logic)",
            "--file-xac-nhan", str(file_xn_1),
        ],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert p_ok1.returncode == 0, p_ok1.stdout + p_ok1.stderr
    assert file_xn_1.exists()
    data1 = json.loads(file_xn_1.read_text(encoding="utf-8"))
    assert data1["nguoi_doi_chieu"] == "Nguyen Van A"
    assert data1["so_nguoi_xac_nhan"] == 1
    assert len(data1["sha256_csv"]) == 64
    assert len(data1["bang_doi_chieu"]) == 10

    # Kiểm 3 trạng thái R7
    st0 = liet_ke_tham_so_chua_xac_nhan(ROOT / "config.yaml", xac_nhan_quan_fry_path=XAC_NHAN_QF_MAC_DINH)
    assert st0["xac_nhan_quan_fry"]["trang_thai"] == "chua_xac_nhan"
    assert "quan_fry.he_so_quan_fry_1995" in {x["ma"] for x in st0["danh_sach"]}

    st1 = liet_ke_tham_so_chua_xac_nhan(ROOT / "config.yaml", xac_nhan_quan_fry_path=file_xn_1)
    assert st1["xac_nhan_quan_fry"]["trang_thai"] == "xac_nhan_1_nguoi"
    ma1 = {x["ma"] for x in st1["danh_sach"]}
    assert "quan_fry.he_so_quan_fry_1995" not in ma1
    assert "quan_fry.xac_nhan_doc_lap_nguoi_2" in ma1
    assert "chưa có người xác nhận thứ hai" in st1["xac_nhan_quan_fry"]["thong_diep"].lower()

    # 5. Đủ thông tin 2 người -> R7 ở trạng thái xac_nhan_2_nguoi (rời hoàn toàn danh sách)
    file_xn_2 = tmp_path / "xac_nhan_2.json"
    p_ok2 = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "kiem_tra_quan_fry.py"),
            "--csv", str(csv_khop),
            "--luu-xac-nhan",
            "--nguoi-doi-chieu", "Nguyen Van A",
            "--nguoi-xac-nhan-2", "Thay GVHD B",
            "--trich-dan", "Quan & Fry, Applied Optics, 1995 (chi kiem logic)",
            "--file-xac-nhan", str(file_xn_2),
        ],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert p_ok2.returncode == 0
    data2 = json.loads(file_xn_2.read_text(encoding="utf-8"))
    assert data2["so_nguoi_xac_nhan"] == 2
    assert data2["nguoi_xac_nhan_2"] == "Thay GVHD B"

    st2 = liet_ke_tham_so_chua_xac_nhan(ROOT / "config.yaml", xac_nhan_quan_fry_path=file_xn_2)
    assert st2["xac_nhan_quan_fry"]["trang_thai"] == "xac_nhan_2_nguoi"
    ma2 = {x["ma"] for x in st2["danh_sach"]}
    assert "quan_fry.he_so_quan_fry_1995" not in ma2
    assert "quan_fry.xac_nhan_doc_lap_nguoi_2" not in ma2

    # 6. Lệch 1 hệ số a5 -> thoát khác 0, nêu rõ a5, không ghi file
    csv_lech = tmp_path / "qf_lech.csv"
    _ghi_csv_gia(csv_lech, ghi_de={"a5": 15.999})
    proc_lech = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "kiem_tra_quan_fry.py"),
            "--csv", str(csv_lech),
            "--luu-xac-nhan",
            "--nguoi-doi-chieu", "HS A",
            "--trich-dan", "Test",
            "--file-xac-nhan", str(file_no),
        ],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc_lech.returncode != 0
    assert "a5" in (proc_lech.stdout + proc_lech.stderr)
    assert not file_no.exists()

    # 7. Thiếu hệ số a9 -> thoát khác 0, nêu rõ a9
    csv_thieu = tmp_path / "qf_thieu.csv"
    _ghi_csv_gia(csv_thieu, bo_qua={"a9"})
    proc_thieu = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "kiem_tra_quan_fry.py"), "--csv", str(csv_thieu)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc_thieu.returncode != 0
    assert "a9" in (proc_thieu.stdout + proc_thieu.stderr)
