"""Kiểm tra chấp nhận Vòng 6 (X0–X7) — dữ liệu mô phỏng kiểm chứng thuật toán & quy trình.

Xuất bảng tổng hợp kết quả từng tiêu chí ra `outputs/kiem_tra_chap_nhan_vong6.csv`.
"""
from __future__ import annotations

import math
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import calibration as cal
from core import optics as op
from core.can_bang_nhiet import phan_tich_can_bang_nhiet_tu_df
from core.chuyen_duong_chuan import phan_tich_chuyen_duong_chuan
from core.measure import AnhKhongHoTroDinhDangError, nhan_dien_dinh_dang_anh_bytes
from core.so_sanh_ngan_sach import so_sanh_ngan_sach_sai_so
from core.trang_thai_cau_hinh import liet_ke_tham_so_chua_xac_nhan
from core.troi_laser import phan_tich_chuoi_troi_laser


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    ket_qua: list[dict[str, object]] = []

    def ghi(ma: str, mo_ta: str, dat: bool, chi_tiet: str) -> None:
        ket_qua.append({
            "tieu_chi": ma,
            "mo_ta": mo_ta,
            "trang_thai": "DAT" if dat else "KHONG_DAT",
            "chi_tiet": chi_tiet,
        })

    # X0: loại bản sao + nhận diện HEIC/WebP
    df_72 = pd.DataFrame({
        cal.COT_DO_MAN: np.tile([0, 5, 10, 15, 20, 25, 30, 35], 9).astype(float),
        cal.COT_NHIET_DO: np.repeat([20.0, 25.0, 30.0], 24),
        cal.COT_NHIET_DO_TC: np.repeat([20.0, 25.0, 30.0], 24),
        cal.COT_DELTA_Y: np.zeros(72, dtype=float),
        cal.COT_DO_DUC: np.zeros(72, dtype=float),
        cal.COT_GHI_CHU: ["ok"] * 72,
        cal.COT_ID_THIET_BI: ["TB1"] * 72,
        cal.COT_ID_DIEN_THOAI: ["DT1"] * 72,
        cal.COT_MA_ME_PHA: ["ME1"] * 72,
        cal.COT_NGUON: ["MO_PHONG"] * 72,
    })
    cfg = op.CauHinhQuangHoc.tu_yaml()
    df_72[cal.COT_DELTA_Y] = [
        op.delta_y_vi_sai_px(s, t, t, cfg) + (i % 3 - 1) * 0.03
        for i, (s, t) in enumerate(zip(df_72[cal.COT_DO_MAN], df_72[cal.COT_NHIET_DO]))
    ]
    df_144 = pd.concat([df_72, df_72], ignore_index=True)
    bc_x0 = cal.dung_duong_chuan(df_144, cal.CauHinhHieuChuan(loai_ban_sao_khi_khop=True))
    ghi("X0_loai_ban_sao", "Loại 72 bản sao khi khớp đường chuẩn", bc_x0.so_dong_dung == 72 and bc_x0.so_dong_loai == 72, f"dung={bc_x0.so_dong_dung}, loai={bc_x0.so_dong_loai}")

    webp_ok = nhan_dien_dinh_dang_anh_bytes(b"RIFF\x10\x00\x00\x00WEBP" + b"\x00" * 16) == "WebP"
    heic_ok = nhan_dien_dinh_dang_anh_bytes((24).to_bytes(4, "big") + b"ftypheic\x00\x00\x00\x00" + b"\x00" * 16) == "HEIC/HEIF"
    ghi("X0_chan_heic_webp", "Nhận diện HEIC/HEIF và WebP qua chữ kí byte", webp_ok and heic_ok, f"webp={webp_ok}, heic={heic_ok}")

    # X2: trôi chung vs trôi độc lập vs chuỗi ngắn
    rng = np.random.default_rng(202606)
    t_p = np.linspace(0.0, 24.0, 60)
    drift = 20.0 * (t_p / 24.0)
    kq_chung = phan_tich_chuoi_troi_laser(t_p, 200.0 + drift + rng.normal(0, 0.05, 60), 260.0 + drift + rng.normal(0, 0.05, 60), nguon_du_lieu="MO_PHONG")
    kq_doc = phan_tich_chuoi_troi_laser(t_p, 200.0 - 0.5 * drift + rng.normal(0, 0.05, 60), 260.0 + drift + rng.normal(0, 0.05, 60), nguon_du_lieu="MO_PHONG")
    kq_ngan = phan_tich_chuoi_troi_laser(np.linspace(0.0, 5.0, 60), 200.0 + rng.normal(0, 0.05, 60), 260.0 + rng.normal(0, 0.05, 60), nguon_du_lieu="MO_PHONG")
    ghi("X2_kappa_troi_chung", "Trôi chung 20 px cho κ cao (> 0.95)", kq_chung["kappa"] > 0.95 and kq_chung["hop_le"], f"kappa={kq_chung['kappa']:.4f}")
    ghi("X2_kappa_doc_lap", "Trôi độc lập cho κ thấp (≤ 0.2) và chặn chuỗi 5p", kq_doc["kappa"] <= 0.2 and kq_ngan["trang_thai"] == "CHUA_DU_DU_LIEU", f"kappa_doc={kq_doc['kappa']:.4f}, ngan={kq_ngan['trang_thai']}")

    # X3: cân bằng nhiệt
    t_grid = np.arange(0.0, 390.0, 30.0)
    rows_cbn = []
    for m in range(5):
        for tg in t_grid:
            rows_cbn.append({"ma_lan_do": f"M{m}", "thoi_gian_giay": tg, "D_C": 0.2 + 4.0 * math.exp(-tg / 90.0) + float(rng.normal(0, 0.05))})
    for tg in (0.0, 30.0, 60.0):
        rows_cbn.append({"ma_lan_do": "M_THIEU", "thoi_gian_giay": tg, "D_C": 2.0})
    kq_cbn = phan_tich_can_bang_nhiet_tu_df(pd.DataFrame(rows_cbn), nguon_du_lieu="MO_PHONG", luu_json=False)
    ghi("X3_can_bang_nhiet", "Khớp τ≈90s, D_∞≈0.2°C và loại lần < 5 điểm", kq_cbn["so_lan_do_hop_le"] == 5 and kq_cbn["so_lan_do_bi_loai"] == 1 and abs(kq_cbn["median_tau_giay"] - 90.0) < 10.0, f"tau={kq_cbn['median_tau_giay']:.1f}s, loai={kq_cbn['so_lan_do_bi_loai']}")

    # X4: chuyển đường chuẩn LOPO px vs mm
    px_goc = 1.0 / cfg.pixel_mm
    rows_x4 = []
    for idx_d, (dt, pxm) in enumerate((("DT1", px_goc), ("DT2", px_goc), ("DT3", px_goc * 1.05))):
        for S in (0.0, 8.0, 16.0, 24.0, 32.0):
            for T in (20.0, 30.0):
                for rep in range(2):
                    dy = (op.delta_y_vi_sai_px(S, T, 25.0, cfg) / px_goc) * pxm
                    rows_x4.append({
                        cal.COT_DO_MAN: S, cal.COT_NHIET_DO: T, cal.COT_NHIET_DO_TC: 25.0,
                        cal.COT_DELTA_Y: dy, cal.COT_PX_PER_MM: pxm, cal.COT_DO_DUC: 0.0,
                        cal.COT_GHI_CHU: "v6", cal.COT_ID_THIET_BI: "TB1",
                        cal.COT_MA_ME_PHA: f"ME_{(rep % 2) + 1}", cal.COT_ID_DIEN_THOAI: dt, cal.COT_NGUON: "MO_PHONG",
                    })
    kq_x4 = phan_tich_chuyen_duong_chuan(pd.DataFrame(rows_x4))
    cmp = kq_x4["so_sanh_lopo_px_vs_mm"]
    ghi("X4_lopo_px_vs_mm", "LOPO mm giảm RMS so với px và px bật cờ cảnh báo", bool(cmp.get("mm_tot_hon_px")) and kq_x4["co_canh_bao_khong_chuyen_duoc"], f"rms_px={cmp.get('rms_lopo_px_ppt'):.3f}, rms_mm={cmp.get('rms_lopo_mm_ppt'):.3f}")

    # X5: đối chiếu ngân sách sai số
    df_x5 = pd.DataFrame(rows_x4).copy()
    df_x5[cal.COT_DELTA_Y] += rng.normal(0.0, 1.5 * op.pixel_moi_phan_nghin(15.0, 25.0, cfg), size=len(df_x5))
    kq_x5 = so_sanh_ngan_sach_sai_so(df_x5, bac_ep=2)
    ghi("X5_doi_chieu_ngan_sach", "Phóng đại nhiễu kích hoạt SAI_SO_THUC_VUOT_LY_THUYET", bool(kq_x5["sai_so_thuc_vuot_ly_thuyet"]), f"ty_le={kq_x5['ty_le_thuc_tren_ly_thuyet']:.2f}x")

    # X6 & X7: tài liệu phỏng vấn + 8 khóa R7 mới
    doc_ok = (ROOT / "docs" / "GIAI_THICH_CHO_PHONG_VAN.md").exists()
    r7 = liet_ke_tham_so_chua_xac_nhan()
    mas = {m["ma"] for m in r7["danh_sach"]}
    r7_ok = {
        "hieu_chuan.loai_ban_sao_khi_khop",
        "hieu_chuan.ti_le_ban_sao_kich_hoat_loai",
        "phan_tich_sai_so.so_khung_toi_thieu_troi",
        "phan_tich_sai_so.thoi_luong_toi_thieu_phut",
        "can_bang_nhiet.nguong_D_C",
        "can_bang_nhiet.so_diem_toi_thieu_lan_do",
        "chuyen_duong_chuan.nguong_RMS_ppt",
        "ngan_sach_so_sanh.he_so_canh_bao",
    }.issubset(mas)
    ghi("X6_X7_tai_lieu_va_r7", "Tài liệu phỏng vấn và đủ 8 khóa giả định X0–X5 trong R7", doc_ok and r7_ok, f"doc={doc_ok}, so_muc_r7={len(r7['danh_sach'])}")

    out_csv = ROOT / "outputs" / "kiem_tra_chap_nhan_vong6.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(ket_qua).to_csv(out_csv, index=False, encoding="utf-8-sig")

    so_dat = sum(1 for x in ket_qua if x["trang_thai"] == "DAT")
    print(f"Nghiệm thu Vòng 6: {so_dat}/{len(ket_qua)} tiêu chí DAT -> {out_csv}")
    for x in ket_qua:
        print(f"  - {x['tieu_chi']}: {x['trang_thai']} ({x['chi_tiet']})")
    return 0 if so_dat == len(ket_qua) else 1


if __name__ == "__main__":
    raise SystemExit(main())
