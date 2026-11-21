"""Kiểm thử R8: công cụ đối chiếu 10 hệ số Quan–Fry (dữ liệu giả chỉ kiểm logic)."""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.optics import HE_SO_QUAN_FRY_TRONG_MA
from core.trang_thai_cau_hinh import XAC_NHAN_QF_MAC_DINH, liet_ke_tham_so_chua_xac_nhan


def _ghi_csv_gia(path: Path, ghi_de: dict[str, float] | None = None, bo_qua: set[str] | None = None) -> None:
    """Tạo CSV đối chiếu giả trong tmp_path — dữ liệu giả chỉ kiểm logic."""
    ghi_de = ghi_de or {}
    bo_qua = bo_qua or set()
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["he_so", "gia_tri_bai_goc", "trang_bang"])
        for k, v in HE_SO_QUAN_FRY_TRONG_MA.items():
            if k in bo_qua:
                continue
            val = ghi_de.get(k, v)
            w.writerow([k, repr(val), "test-gia"])


def test_r8_doi_chieu_quan_fry_khop_va_lech_va_thieu(tmp_path: Path):
    """Kiểm logic kịch bản khớp 10/10, lệch 1 hệ số và thiếu hệ số (dữ liệu giả chỉ kiểm logic)."""
    assert not XAC_NHAN_QF_MAC_DINH.exists(), "Không được tạo sẵn data/xac_nhan_quan_fry.json trong repo"

    csv_khop = tmp_path / "qf_khop.csv"
    _ghi_csv_gia(csv_khop)
    file_xn = tmp_path / "xac_nhan_quan_fry.json"

    proc_ok = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "kiem_tra_quan_fry.py"),
            "--csv",
            str(csv_khop),
            "--luu-xac-nhan",
            "--file-xac-nhan",
            str(file_xn),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc_ok.returncode == 0, proc_ok.stdout + proc_ok.stderr
    assert file_xn.exists()

    # Sau khi file xác nhận cục bộ hợp lệ tồn tại, mục quan_fry rời khỏi danh sách R7
    st_truoc = liet_ke_tham_so_chua_xac_nhan(ROOT / "config.yaml", xac_nhan_quan_fry_path=XAC_NHAN_QF_MAC_DINH)
    ma_truoc = {x["ma"] for x in st_truoc["danh_sach"]}
    assert "quan_fry.he_so_quan_fry_1995" in ma_truoc

    st_sau = liet_ke_tham_so_chua_xac_nhan(ROOT / "config.yaml", xac_nhan_quan_fry_path=file_xn)
    ma_sau = {x["ma"] for x in st_sau["danh_sach"]}
    assert "quan_fry.he_so_quan_fry_1995" not in ma_sau

    # Trường hợp 2: lệch 1 hệ số a5 -> phải thoát khác 0, nêu rõ a5 và KHÔNG ghi file xác nhận
    csv_lech = tmp_path / "qf_lech.csv"
    _ghi_csv_gia(csv_lech, ghi_de={"a5": 15.999})
    file_xn_lech = tmp_path / "xac_nhan_khong_duoc_tao.json"
    proc_lech = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "kiem_tra_quan_fry.py"),
            "--csv",
            str(csv_lech),
            "--luu-xac-nhan",
            "--file-xac-nhan",
            str(file_xn_lech),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc_lech.returncode != 0
    assert "a5" in (proc_lech.stdout + proc_lech.stderr)
    assert not file_xn_lech.exists()

    # Trường hợp 3: thiếu hệ số a9 -> thoát khác 0, nêu rõ a9
    csv_thieu = tmp_path / "qf_thieu.csv"
    _ghi_csv_gia(csv_thieu, bo_qua={"a9"})
    proc_thieu = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "kiem_tra_quan_fry.py"),
            "--csv",
            str(csv_thieu),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc_thieu.returncode != 0
    assert "a9" in (proc_thieu.stdout + proc_thieu.stderr)
