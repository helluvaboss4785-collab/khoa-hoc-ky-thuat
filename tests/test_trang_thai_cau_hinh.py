"""Kiểm thử mô-đun theo dõi các tham số giả định / chưa xác nhận (R7)."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from core import trang_thai_cau_hinh as tt


def test_r7_liet_ke_du_tham_so_gia_dinh_va_null_tren_config_mac_dinh() -> None:
    res = tt.liet_ke_tham_so_chua_xac_nhan()
    mas = {it["ma"]: it for it in res["danh_sach"]}
    assert res["so_tham_so_chua_xac_nhan"] == len(res["danh_sach"])
    assert res["so_tham_so_chua_xac_nhan"] >= 25

    cac_ma_bat_buoc = {
        "hieu_chuan.sigma_D_khi_chua_do_C",
        "hieu_chuan.sai_so_nhiet_ke_C",
        "hieu_chuan.sai_so_dung_dich_chuan_ppt",
        "hieu_chuan.nhiet_do_toi_thieu_phu_C",
        "hieu_chuan.dai_man_muc_tieu_ppt",
        "hieu_chuan.nhiet_ke_cheo.so_cap_toi_thieu",
        "hieu_chuan.nhiet_ke_cheo.so_muc_nhiet_toi_thieu",
        "hieu_chuan.hieu_chuan_cheo_nhiet_ke",
        "phan_tich_sai_so.sai_so_tim_tam_px",
        "phan_tich_sai_so.lech_nhiet_do_hai_ngan_C",
        "phan_tich_sai_so.sai_so_goc_A_do",
        "phan_tich_sai_so.troi_laser_chung_px",
        "phan_tich_sai_so.he_so_triet_chung",
        "thiet_ke_thi_nghiem.so_muc_man_toi_thieu",
        "thiet_ke_thi_nghiem.phai_co_muc_0",
        "thiet_ke_thi_nghiem.ti_le_phu_dai_man_toi_thieu",
        "thiet_ke_thi_nghiem.so_lan_lap_toi_thieu_moi_o",
        "thiet_ke_thi_nghiem.so_me_pha_toi_thieu",
        "thiet_ke_thi_nghiem.so_muc_nhiet_toi_thieu",
        "thiet_ke_thi_nghiem.bien_do_nhiet_toi_thieu_C",
        "thiet_ke_thi_nghiem.so_muc_D_toi_thieu_neu_hoc_D",
        "thiet_ke_thi_nghiem.chenh_D_toi_thieu_C",
        "thiet_ke_thi_nghiem.ti_le_toi_da_moi_muc",
        "thiet_ke_thi_nghiem.ti_le_ban_sao_toi_da",
        "nhap_anh.thu_muc_mo_phong",
        "hieu_chuan.nhiet_ke_cheo.do_phan_giai_toi_da_C",
        "hieu_chuan.nhiet_ke_cheo.gia_dinh_doc_lap_phan_giai",
        "xu_ly_anh.ti_le_cot_bao_hoa_nghiem_trong",
        "xu_ly_anh.so_cot_lien_tiep_bao_hoa",
        "xu_ly_anh.nguong_nen_khong_deu",
        "xu_ly_anh.nguong_on_dinh_nhiet_px_moi_phut",
        "xu_ly_anh.nguong_lech_tam_meo_ti_le",
        "nguong_loai.tom_the_chan_trang",
        "nguong_loai.tom_su",
        "nguong_loai.ca_tra",
        "nguong_loai.lua",
        "nguong_loai.sau_rieng",
        "nguong_loai.cua_bien",
        "quan_fry.he_so_quan_fry_1995",
    }
    assert cac_ma_bat_buoc.issubset(mas.keys())
    qf_ghichu = str(res["xac_nhan_quan_fry"].get("ghi_chu_gioi_han") or "").lower()
    assert qf_ghichu and ("tự khai" in qf_ghichu or "độc lập" in qf_ghichu)


def test_r7_dien_tham_so_roi_khoi_danh_sach(tmp_path: Path) -> None:
    cfg_raw = yaml.safe_load(Path(tt.CONFIG_MAC_DINH).read_text(encoding="utf-8"))
    cfg_raw["hieu_chuan"]["sai_so_dung_dich_chuan_ppt"] = 0.15
    cfg_raw["hieu_chuan"]["nhiet_do_toi_thieu_phu_C"] = 10.0
    cfg_raw["nguong_loai"]["lua"]["an_toan"] = [0.0, 4.0]
    cfg_raw["nguong_loai"]["lua"]["nguon_tham_khao"] = "Tai lieu kiem logic (test R7)"

    cfg_tmp = tmp_path / "config_r7.yaml"
    cfg_tmp.write_text(yaml.safe_dump(cfg_raw, allow_unicode=True), encoding="utf-8")

    qf_json = tmp_path / "xac_nhan_qf.json"
    qf_json.write_text(json.dumps({"da_doi_chieu_khop": True, "thoi_gian": "2026-11-21"}), encoding="utf-8")

    res = tt.liet_ke_tham_so_chua_xac_nhan(config_path=cfg_tmp, xac_nhan_quan_fry_path=qf_json)
    mas = {it["ma"] for it in res["danh_sach"]}
    assert "hieu_chuan.sai_so_dung_dich_chuan_ppt" not in mas
    assert "hieu_chuan.nhiet_do_toi_thieu_phu_C" not in mas
    assert "nguong_loai.lua" not in mas
    assert "quan_fry.he_so_quan_fry_1995" not in mas
    assert "hieu_chuan.sigma_D_khi_chua_do_C" in mas
    assert "nguong_loai.tom_the_chan_trang" in mas


def test_v6_xac_nhan_hai_nguoi_quan_fry_va_hieu_chuan_cheo_roi_danh_sach(tmp_path: Path) -> None:
    from core.nhiet_ke import HieuChuanCheoNhietKe, luu_hieu_chuan_cheo_nhiet_ke

    nk_json = tmp_path / "hc_nk.json"
    luu_hieu_chuan_cheo_nhiet_ke(
        HieuChuanCheoNhietKe(
            offset_C=0.45,
            sigma_offset_C=0.08,
            phu_thuoc_nhiet_do=False,
            so_cap=8,
            so_muc_nhiet=3,
            ngay="2026-11-21",
            nguon_du_lieu="MO_PHONG",
            nguoi_thuc_hien="Hoc sinh kiem logic",
        ),
        nk_json,
    )

    qf_2 = tmp_path / "qf_2nguoi.json"
    qf_2.write_text(
        json.dumps(
            {
                "da_doi_chieu_khop": True,
                "nguoi_doi_chieu": "HS A",
                "nguoi_xac_nhan_2": "GV B",
                "so_nguoi_xac_nhan": 2,
                "trich_dan": "Quan & Fry (1995), Applied Optics 34(18), Table 1",
                "thoi_gian": "2026-11-21T10:00:00",
            }
        ),
        encoding="utf-8",
    )

    res = tt.liet_ke_tham_so_chua_xac_nhan(
        xac_nhan_quan_fry_path=qf_2,
        hieu_chuan_nhiet_ke_path=nk_json,
    )
    mas = {it["ma"] for it in res["danh_sach"]}
    assert res["xac_nhan_quan_fry"]["trang_thai"] == "xac_nhan_2_nguoi"
    assert "hieu_chuan.hieu_chuan_cheo_nhiet_ke" not in mas
    assert "quan_fry.he_so_quan_fry_1995" not in mas
    assert "quan_fry.xac_nhan_doc_lap_nguoi_2" not in mas
