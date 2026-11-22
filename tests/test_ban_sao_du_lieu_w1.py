"""Kiểm thử W1: phát hiện nhân bản dòng, trùng sha256_anh / ten_file nghi ngờ gán nhãn lại (không dương tính giả)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
from starlette.testclient import TestClient

from app import web_app
from core import calibration as cal
from core.kiem_tra_thiet_ke import kiem_tra_thiet_ke_thi_nghiem
from scripts.xuat_bao_cao import xuat_bo_bao_cao
from sim.synth import sinh_du_lieu_hieu_chuan_mo_phong


def _tao_bo_72_dong_thiet_ke(seed: int = 42, ghi_nhan_thuc_te_chi_kiem_logic: bool = True) -> pd.DataFrame:
    """Tạo 72 dòng dữ liệu mô phỏng (8 mức S x 3 mức T x 3 lần lặp).

    Gắn `THUC_TE` chỉ để kiểm logic giống bối cảnh báo cáo W1; toàn bộ số liệu vẫn là mô phỏng Snell.
    """
    df = sinh_du_lieu_hieu_chuan_mo_phong(
        muc_S=(0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0),
        muc_T=(20.0, 25.0, 30.0),
        so_lan_lap=3,
        sigma_nhiet_ke_C=0.1,
        seed=seed,
    )
    df[cal.COT_MA_ME_PHA] = ["ME_01" if (i % 2 == 0) else "ME_02" for i in range(len(df))]
    df[cal.COT_PX_PER_MM] = 20.0
    if ghi_nhan_thuc_te_chi_kiem_logic:
        df[cal.COT_NGUON] = cal.NHAN_THUC_TE
        df[cal.COT_ID_THIET_BI] = "TB_KIEM_LOGIC"
        df[cal.COT_ID_DIEN_THOAI] = "DT_KIEM_LOGIC"
    return df


def _map_muc(kq: dict) -> dict[str, dict]:
    return {m["ma"]: m for m in kq["muc_kiem"]}


def test_w1_bo_72_dong_sach_va_nhan_ba_thanh_216_dong(tmp_path: Path):
    """W1: 72 dòng gốc sạch -> dat & 3/ô; nhân ba thành 216 dòng -> chua_dat (144 bản sao), so_lan_lap=3/ô, DU_LIEU_CO_BAN_SAO, báo cáo cảnh báo."""
    df_72 = _tao_bo_72_dong_thiet_ke()
    kq_72 = kiem_tra_thiet_ke_thi_nghiem(df_72)
    m72 = _map_muc(kq_72)
    assert m72["ban_sao_du_lieu"]["trang_thai"] == "dat"
    assert m72["so_lan_lap_moi_o"]["trang_thai"] == "dat"
    assert kq_72["tom_tat"]["min_lap_moi_o"] == 3
    assert kq_72["tom_tat"]["so_dong_ban_sao"] == 0
    assert kq_72["hop_le_tong_quat"] is True

    # Nhân 3 lần thành 216 dòng (144 dòng trùng hệt)
    df_216 = pd.concat([df_72, df_72, df_72], ignore_index=True)
    kq_216 = kiem_tra_thiet_ke_thi_nghiem(df_216)
    m216 = _map_muc(kq_216)
    assert kq_216["hop_le_tong_quat"] is False
    assert m216["ban_sao_du_lieu"]["trang_thai"] == "chua_dat"
    assert "144 dòng bản sao" in m216["ban_sao_du_lieu"]["gia_tri_do"]
    assert kq_216["tom_tat"]["so_dong_ban_sao"] == 144
    # Thống kê số lần lặp tính SAU loại bản sao = 3/ô (không phải 9/ô), hiển thị cả trước và sau
    assert kq_216["tom_tat"]["min_lap_moi_o"] == 3
    assert kq_216["tom_tat"]["min_lap_moi_o_truoc_loai_ban_sao"] == 9
    assert "3 lần/ô" in m216["so_lan_lap_moi_o"]["gia_tri_do"]
    assert "9 lần/ô" in m216["so_lan_lap_moi_o"]["gia_tri_do"]

    # Khi chỉ có 1 lần lặp/ô nhân 3 thành 3 lần/ô: trước loại là 3, sau loại là 1 -> chua_dat!
    df_1lap = _tao_bo_72_dong_thiet_ke()[::3].copy()
    df_1lap_x3 = pd.concat([df_1lap, df_1lap, df_1lap], ignore_index=True)
    kq_1lap = kiem_tra_thiet_ke_thi_nghiem(df_1lap_x3)
    assert kq_1lap["tom_tat"]["min_lap_moi_o"] == 1
    assert _map_muc(kq_1lap)["so_lan_lap_moi_o"]["trang_thai"] == "chua_dat"

    # X0(b): mặc định loai_ban_sao_khi_khop=True loại 144 bản sao và chỉ khớp trên 72 dòng gốc; khi tắt cờ vẫn khớp 216 dòng
    bc = cal.dung_duong_chuan(df_216, cal.CauHinhHieuChuan())
    assert bc.mo_hinh.so_diem == 72
    assert bc.so_dong_loai == 144
    assert bc.so_dong_dung == 72
    assert bc.da_loai_ban_sao_khi_khop is True
    assert bc.co_ban_sao_du_lieu is True
    assert bc.so_dong_ban_sao == 144
    assert any(c["ma"] == "DU_LIEU_CO_BAN_SAO" and c["cap"] == "nghiem_trong" for c in bc.canh_bao_chi_tiet)

    bc_giu = cal.dung_duong_chuan(df_216, cal.CauHinhHieuChuan(loai_ban_sao_khi_khop=False))
    assert bc_giu.mo_hinh.so_diem == 216
    assert bc_giu.da_loai_ban_sao_khi_khop is False

    # Xuất báo cáo có mục "Cảnh báo dữ liệu trùng lặp" ở đầu
    p_csv = tmp_path / "cal_216.csv"
    df_216.to_csv(p_csv, index=False, encoding="utf-8-sig")
    kq_bc = xuat_bo_bao_cao(csv_hieu_chuan=p_csv, out_dir=tmp_path / "bao_cao_w1")
    md = Path(kq_bc["tong_hop_bao_cao_md"]).read_text(encoding="utf-8")
    assert "## Cảnh báo dữ liệu trùng lặp" in md
    assert md.index("## Cảnh báo dữ liệu trùng lặp") < md.index("## 1. Tóm tắt mô hình đường chuẩn")

    # Web API trả đầy đủ thông tin bản sao
    client = TestClient(web_app.app)
    r_cal = client.post("/api/calibrate", json={"mode": "csv", "csv_text": df_216.to_csv(index=False), "activate": False})
    assert r_cal.status_code == 200
    j = r_cal.json()
    assert j["co_ban_sao_du_lieu"] is True
    assert j["so_dong_ban_sao"] == 144
    assert any(c["ma"] == "DU_LIEU_CO_BAN_SAO" for c in j["canh_bao_chi_tiet"])


def test_w1_trung_sha256_hoac_ten_file_khac_delta_y_va_khong_duong_tinh_gia():
    """W1: 10 dòng cùng sha256_anh (hoặc ten_file) nhưng delta_y_px khác -> nghi ngờ gán nhãn lại; 72 sha256 hợp lệ khác nhau -> sạch."""
    df_72 = _tao_bo_72_dong_thiet_ke()
    df_72["sha256_anh"] = [hashlib.sha256(f"anh_{i}".encode("utf-8")).hexdigest() for i in range(len(df_72))]
    df_72["ten_file"] = [f"img_{i:03d}.png" for i in range(len(df_72))]
    kq_clean = kiem_tra_thiet_ke_thi_nghiem(df_72)
    m_clean = _map_muc(kq_clean)
    assert m_clean["ban_sao_du_lieu"]["trang_thai"] == "dat"
    assert kq_clean["tom_tat"]["so_dong_ban_sao"] == 0
    assert kq_clean["tom_tat"]["co_nghi_ngo_gan_nhan_lai"] is False

    # 10 dòng đầu cùng 1 sha256_anh nhưng delta_y_px khác nhau -> nghi ngờ gán nhãn lại
    df_sha_dup = df_72.copy()
    sha_chung = hashlib.sha256(b"anh_chung").hexdigest()
    df_sha_dup.loc[df_sha_dup.index[:10], "sha256_anh"] = sha_chung
    kq_sha = kiem_tra_thiet_ke_thi_nghiem(df_sha_dup)
    m_sha = _map_muc(kq_sha)
    assert m_sha["ban_sao_du_lieu"]["trang_thai"] == "chua_dat"
    assert "nghi ngờ gán nhãn lại" in m_sha["ban_sao_du_lieu"]["gia_tri_do"]
    assert kq_sha["tom_tat"]["so_dong_ban_sao"] == 9
    assert kq_sha["tom_tat"]["co_nghi_ngo_gan_nhan_lai"] is True

    # Trùng ten_file với delta_y_px khác nhau -> nghi ngờ gán nhãn lại
    df_tf_dup = df_72.drop(columns=["sha256_anh"]).copy()
    df_tf_dup.loc[df_tf_dup.index[:5], "ten_file"] = "20_25_01.jpg"
    kq_tf = kiem_tra_thiet_ke_thi_nghiem(df_tf_dup)
    m_tf = _map_muc(kq_tf)
    assert m_tf["ban_sao_du_lieu"]["trang_thai"] == "chua_dat"
    assert "nghi ngờ gán nhãn lại" in m_tf["ban_sao_du_lieu"]["gia_tri_do"]
