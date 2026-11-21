"""Kiểm thử V5: tài liệu quy trình thu dữ liệu thực nghiệm và 2 file CSV mẫu (trống)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from core import nhiet_ke as nk

ROOT = Path(__file__).resolve().parents[1]


def test_v5_tai_lieu_quy_trinh_thu_du_lieu_day_du():
    doc_path = ROOT / "docs" / "QUY_TRINH_THU_DU_LIEU.md"
    assert doc_path.exists()
    text = doc_path.read_text(encoding="utf-8")

    # Phải giải thích rõ mọi ngưỡng là gợi ý khởi điểm, chỉnh cùng GVHD, trỏ config.yaml
    assert "gợi ý khởi điểm" in text
    assert "config.yaml" in text
    assert "thiet_ke_thi_nghiem" in text
    assert "hieu_chuan.nhiet_ke_cheo" in text

    # Phải có đủ hướng dẫn hiệu chuẩn chéo nhiệt kế, nước đá xay, 2 mẻ pha và danh sách điều cấm
    assert "nước đá xay" in text
    assert "ma_me_pha" in text
    assert "px_per_mm" in text
    assert "THUC_TE" in text
    assert "MO_PHONG" in text
    assert "TUYỆT ĐỐI KHÔNG" in text
    assert "mau_cap_nhiet_ke.csv" in text
    assert "mau_ghi_chep_thi_nghiem.csv" in text


def test_v5_hai_csv_mau_chi_co_header_khong_bia_so():
    p_nk = ROOT / "data" / "mau_cap_nhiet_ke.csv"
    p_tn = ROOT / "data" / "mau_ghi_chep_thi_nghiem.csv"
    assert p_nk.exists()
    assert p_tn.exists()

    df_nk = pd.read_csv(p_nk, encoding="utf-8-sig")
    assert len(df_nk) == 0
    assert list(df_nk.columns) == [
        nk.COT_T_MAU_DOC,
        nk.COT_T_TC_DOC,
        nk.COT_T_CHUAN,
        nk.COT_NGUON_NK,
        nk.COT_GHI_CHU_NK,
    ]

    df_tn = pd.read_csv(p_tn, encoding="utf-8-sig")
    assert len(df_tn) == 0
    assert list(df_tn.columns) == [
        "ngay_do",
        "nguoi_do",
        "ma_me_pha",
        "khoi_luong_muoi_g",
        "khoi_luong_nuoc_g",
        "do_man_muc_tieu_ppt",
        "nhiet_do_phong_C",
        "khoa_ae_af",
        "ten_file_anh",
        "ghi_chu",
    ]


def test_v5_readme_lien_ket_tai_lieu_va_mau():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/QUY_TRINH_THU_DU_LIEU.md" in readme
    assert "data/mau_cap_nhiet_ke.csv" in readme
    assert "data/mau_ghi_chep_thi_nghiem.csv" in readme
