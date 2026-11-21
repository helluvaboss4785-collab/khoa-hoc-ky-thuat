"""Kiểm thử R9: bộ xuất tài liệu cho báo cáo và poster (nhánh mô phỏng vs nhánh kiểm logic THUC_TE)."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.xuat_bao_cao import BANNER_MO_PHONG, xuat_bo_bao_cao
from sim.synth import sinh_du_lieu_hieu_chuan_mo_phong


def _tat_ca_chu_tren_figure(fig) -> str:
    """Thu thập toàn bộ chuỗi văn bản (title, watermark, text, legend) từ Matplotlib Figure."""
    parts: list[str] = []
    if getattr(fig, "_suptitle", None) is not None:
        parts.append(fig._suptitle.get_text())
    for ax in fig.axes:
        parts.append(ax.get_title())
        for t in ax.texts:
            parts.append(t.get_text())
    return "\n".join(parts)


def test_r9_xuat_bao_cao_du_lieu_mo_phong_bat_buoc_watermark(tmp_path: Path):
    """Nhánh 1 (dữ liệu mô phỏng): xuất đủ 6 tài liệu và đóng dấu mô phỏng trên cả hình, bảng, Markdown."""
    csv_ss = tmp_path / "so_sanh_mo_phong.csv"
    with open(csv_ss, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["S_thiet_bi", "S_khuc_xa_ke"])  # thiếu nguon_du_lieu -> bắt buộc đóng dấu chưa xác nhận
        for s_tb, s_kx in [(5.1, 5.0), (15.2, 15.0), (24.8, 25.0), (30.1, 30.0)]:
            w.writerow([s_tb, s_kx])

    out_dir = tmp_path / "bao_cao_mp"
    kq = xuat_bo_bao_cao(mo_phong=True, csv_so_sanh=csv_ss, out_dir=out_dir)

    assert kq["chua_xac_nhan_hc"] is True
    assert kq["chua_xac_nhan_ba"] is True
    for key in (
        "duong_chuan_png",
        "bang_sai_so_theo_muc_csv",
        "bland_altman_png",
        "bang_bland_altman_csv",
        "ngan_sach_sai_so_csv",
        "tham_so_gia_dinh_csv",
        "tong_hop_bao_cao_md",
    ):
        assert kq[key] is not None and Path(kq[key]).exists()

    txt_hc = _tat_ca_chu_tren_figure(kq["fig_duong_chuan"])
    txt_ba = _tat_ca_chu_tren_figure(kq["fig_bland_altman"])
    assert BANNER_MO_PHONG in txt_hc
    assert BANNER_MO_PHONG in txt_ba
    assert "DỮ LIỆU MÔ PHỎNG / CHƯA XÁC NHẬN" in kq["bang_sai_so_theo_muc_csv"].read_text(encoding="utf-8-sig").splitlines()[0]
    assert "DỮ LIỆU MÔ PHỎNG / CHƯA XÁC NHẬN" in kq["bang_bland_altman_csv"].read_text(encoding="utf-8-sig").splitlines()[0]
    md_text = kq["tong_hop_bao_cao_md"].read_text(encoding="utf-8")
    assert BANNER_MO_PHONG in md_text
    assert "sai số của thiết bị là" not in md_text.lower()


def test_r9_xuat_bao_cao_chi_kiem_logic_nhan_thuc_te_khong_watermark(tmp_path: Path):
    """Nhánh 2 (chỉ kiểm logic, dữ liệu vẫn là mô phỏng): toàn bộ dòng CSV gắn THUC_TE -> không có watermark mô phỏng."""
    # Tái sử dụng bộ sinh mô phỏng chỉ để lấy tọa độ số liệu tổng hợp, rồi gán nhãn THUC_TE để kiểm logic nhánh.
    df_sim = sinh_du_lieu_hieu_chuan_mo_phong()
    df_sim["nguon_du_lieu"] = "THUC_TE"
    csv_hc = tmp_path / "hc_thuc_te_chi_kiem_logic.csv"
    df_sim.to_csv(csv_hc, index=False, encoding="utf-8")

    csv_ss = tmp_path / "ss_thuc_te_chi_kiem_logic.csv"
    with open(csv_ss, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["S_thiet_bi", "S_khuc_xa_ke", "nguon_du_lieu"])
        for s_tb, s_kx in [(5.05, 5.0), (15.1, 15.0), (24.95, 25.0), (30.0, 30.0)]:
            w.writerow([s_tb, s_kx, "THUC_TE"])

    out_dir = tmp_path / "bao_cao_tt"
    kq = xuat_bo_bao_cao(csv_hieu_chuan=csv_hc, csv_so_sanh=csv_ss, out_dir=out_dir)

    assert kq["chua_xac_nhan_hc"] is False
    assert kq["chua_xac_nhan_ba"] is False
    txt_hc = _tat_ca_chu_tren_figure(kq["fig_duong_chuan"])
    txt_ba = _tat_ca_chu_tren_figure(kq["fig_bland_altman"])
    assert BANNER_MO_PHONG not in txt_hc
    assert BANNER_MO_PHONG not in txt_ba
    assert BANNER_MO_PHONG not in kq["bang_sai_so_theo_muc_csv"].read_text(encoding="utf-8-sig")
    assert BANNER_MO_PHONG not in kq["bang_bland_altman_csv"].read_text(encoding="utf-8-sig")
    assert BANNER_MO_PHONG not in kq["tong_hop_bao_cao_md"].read_text(encoding="utf-8")
