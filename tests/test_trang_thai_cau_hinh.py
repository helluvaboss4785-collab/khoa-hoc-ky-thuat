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
