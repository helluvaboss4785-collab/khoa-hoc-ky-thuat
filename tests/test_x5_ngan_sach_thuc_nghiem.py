"""Kiểm thử X5 — đối chiếu ngân sách sai số thực nghiệm với lí thuyết.

Mọi dữ liệu trong file test này là MÔ PHỎNG tổng hợp (fixed seeds) dùng để kiểm
chứng phân rã phương sai ANOVA (lặp lại, mẻ pha, điện thoại), cảnh báo
SAI_SO_THUC_VUOT_LY_THUYET, ghi chú "không tách được" khi 1 nhóm, CLI và xuat_bo_bao_cao.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import calibration as cal
from core import optics as op
from core.so_sanh_ngan_sach import phan_ra_phuong_sai_phan_du, so_sanh_ngan_sach_sai_so
from scripts.so_sanh_ngan_sach_sai_so import main as cli_ss_main
from scripts.xuat_bao_cao import xuat_bo_bao_cao


def _tao_bo_phan_du_nhieu_nguon(
    cfg: op.CauHinhQuangHoc,
    rng: np.random.Generator,
    *,
    sigma_lap_ppt: float = 0.25,
    sigma_me_ppt: float = 0.20,
    sigma_dt_ppt: float = 0.15,
    n_me: int = 8,
    n_dt: int = 6,
) -> pd.DataFrame:
    """Sinh bộ dữ liệu gọn có đủ các nguồn phương sai biết trước theo ‰ (quy đổi sang Δy px)."""
    # Chọn (mẻ, điện thoại) theo thiết kế cân bằng 8 mẻ × 6 điện thoại × 3 mức S × 2 lặp = 288 điểm
    # Lưu ý: giữ n_me, n_dt đủ lớn để ước lượng phương sai thành phần trung bình đạt ≤ 25% sai số tương đối.
    b_me = rng.normal(0.0, sigma_me_ppt, size=n_me)
    b_dt = rng.normal(0.0, sigma_dt_ppt, size=n_dt)
    rows: list[dict[str, object]] = []
    px_ppt_ref = op.pixel_moi_phan_nghin(15.0, 25.0, cfg)

    for i_m in range(n_me):
        for i_d in range(n_dt):
            for S in (5.0, 15.0, 25.0):
                dy_chuan = op.delta_y_vi_sai_px(S, 25.0, 25.0, cfg)
                for _ in range(2):
                    e_ppt = b_me[i_m] + b_dt[i_d] + float(rng.normal(0.0, sigma_lap_ppt))
                    dy_px = dy_chuan + e_ppt * px_ppt_ref
                    rows.append({
                        cal.COT_DO_MAN: S,
                        cal.COT_NHIET_DO: 25.0,
                        cal.COT_NHIET_DO_TC: 25.0,
                        cal.COT_DELTA_Y: dy_px,
                        cal.COT_PX_PER_MM: 1.0 / cfg.pixel_mm,
                        cal.COT_DO_DUC: 0.0,
                        cal.COT_GHI_CHU: "mo_phong_x5",
                        cal.COT_ID_THIET_BI: "TB_X5",
                        cal.COT_MA_ME_PHA: f"ME_{i_m:02d}",
                        cal.COT_ID_DIEN_THOAI: f"DT_{i_d:02d}",
                        cal.COT_NGUON: "MO_PHONG",
                    })
    return pd.DataFrame(rows)


def test_x5_100_bo_phan_ra_phuong_sai_sai_so_tuong_doi_duoi_25_phan_tram() -> None:
    """100 bộ mô phỏng: ước lượng σ_lặp, σ_mẻ_pha, σ_điện_thoại bám sát giá trị đặt (≤ 25%)."""
    cfg = op.CauHinhQuangHoc.tu_yaml()
    rng = np.random.default_rng(202630)

    s_lap_true, s_me_true, s_dt_true = 0.25, 0.20, 0.15
    s_tong_true = math.sqrt(s_lap_true ** 2 + s_me_true ** 2 + s_dt_true ** 2)

    est_lap: list[float] = []
    est_me: list[float] = []
    est_dt: list[float] = []
    est_tong: list[float] = []

    for _ in range(100):
        df = _tao_bo_phan_du_nhieu_nguon(
            cfg,
            rng,
            sigma_lap_ppt=s_lap_true,
            sigma_me_ppt=s_me_true,
            sigma_dt_ppt=s_dt_true,
        )
        pr = phan_ra_phuong_sai_phan_du(df, bac_ep=2)
        assert pr["sigma_lap_lai_ppt"] is not None
        assert pr["sigma_me_pha_ppt"] is not None
        assert pr["sigma_dien_thoai_ppt"] is not None
        est_lap.append(pr["sigma_lap_lai_ppt"])
        est_me.append(pr["sigma_me_pha_ppt"])
        est_dt.append(pr["sigma_dien_thoai_ppt"])
        est_tong.append(pr["sigma_tong_thuc_nghiem_ppt"])

    assert abs(float(np.mean(est_lap)) - s_lap_true) / s_lap_true <= 0.25
    assert abs(float(np.mean(est_me)) - s_me_true) / s_me_true <= 0.25
    assert abs(float(np.mean(est_dt)) - s_dt_true) / s_dt_true <= 0.25
    assert abs(float(np.mean(est_tong)) - s_tong_true) / s_tong_true <= 0.25


def test_x5_phong_dai_nhieu_3x_kich_hoat_canh_bao_va_khong_tach_duoc(tmp_path: Path) -> None:
    """Phóng đại nhiễu 3× kích hoạt SAI_SO_THUC_VUOT_LY_THUYET; 1 nhóm ghi chú 'không tách được'."""
    cfg = op.CauHinhQuangHoc.tu_yaml()
    rng = np.random.default_rng(202631)

    # Phóng đại nhiễu thực nghiệm lên rất lớn (σ_lặp = 1.8 ‰) -> vượt xa lí thuyết
    df_lon = _tao_bo_phan_du_nhieu_nguon(cfg, rng, sigma_lap_ppt=1.8, sigma_me_ppt=0.8, sigma_dt_ppt=0.5)
    kq_vuot = so_sanh_ngan_sach_sai_so(df_lon, bac_ep=2)
    assert kq_vuot["sai_so_thuc_vuot_ly_thuyet"] is True
    assert kq_vuot["ty_le_thuc_tren_ly_thuyet"] > kq_vuot["he_so_canh_bao"]
    assert any(c["ma"] == "SAI_SO_THUC_VUOT_LY_THUYET" for c in kq_vuot["canh_bao_chi_tiet"])

    # Trường hợp chỉ có 1 mẻ pha và 1 điện thoại -> ghi chú "không tách được"
    df_1 = df_lon[(df_lon[cal.COT_MA_ME_PHA] == "ME_00") & (df_lon[cal.COT_ID_DIEN_THOAI] == "DT_00")].copy()
    kq_1 = so_sanh_ngan_sach_sai_so(df_1, bac_ep=2)
    assert kq_1["thuc_nghiem"]["sigma_me_pha_ppt"] is None
    assert "không tách được" in kq_1["thuc_nghiem"]["ghi_chu_me_pha"]
    assert kq_1["thuc_nghiem"]["sigma_dien_thoai_ppt"] is None
    assert "không tách được" in kq_1["thuc_nghiem"]["ghi_chu_dien_thoai"]

    # CLI & xuat_bo_bao_cao
    csv_p = tmp_path / "x5.csv"
    df_lon.to_csv(csv_p, index=False)
    out_json = tmp_path / "x5.json"
    out_csv = tmp_path / "x5_bang.csv"
    assert cli_ss_main(["--csv", str(csv_p), "--output-json", str(out_json), "--output-csv", str(out_csv)]) == 0
    assert out_json.exists() and out_csv.exists()

    out_dir = tmp_path / "bao_cao_x5"
    res_bc = xuat_bo_bao_cao(csv_hieu_chuan=csv_p, out_dir=out_dir)
    assert res_bc["doi_chieu_ngan_sach_csv"].exists()
    md = res_bc["tong_hop_bao_cao_md"].read_text(encoding="utf-8")
    assert "SAI_SO_THUC_VUOT_LY_THUYET" in md
