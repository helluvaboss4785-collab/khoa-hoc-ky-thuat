"""Kiểm thử X4 — đánh giá khả năng chuyển đường chuẩn giữa điện thoại (LOPO) và mẻ pha (LOBO).

Mọi dữ liệu trong file test này là MÔ PHỎNG tổng hợp (fixed seeds) dùng để kiểm
chứng logic quy đổi px -> mm, phát hiện lệch thang giữa điện thoại, cờ cảnh báo
DUONG_CHUAN_KHONG_CHUYEN_DUOC, xử lí an toàn khi < 2 nhóm, API và xuất báo cáo.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from starlette.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.web_app import app
from core import calibration as cal
from core import optics as op
from core.chuyen_duong_chuan import phan_tich_chuyen_duong_chuan
from scripts.kiem_tra_chap_nhan_vong3 import khoang_tin_cay_wilson
from scripts.phan_tich_chuyen_duong_chuan import main as cli_chuyen_main
from scripts.xuat_bao_cao import xuat_bo_bao_cao


def _tao_bo_du_lieu_3_dien_thoai(
    cfg: op.CauHinhQuangHoc,
    rng: np.random.Generator,
    *,
    lech_scale_dt_c: float = 0.05,
) -> pd.DataFrame:
    """Sinh 1 bộ dữ liệu gọn (3 điện thoại × 5 S × 2 T × 2 lặp = 60 điểm) có lệch thang px_per_mm."""
    px_mm_goc = 1.0 / cfg.pixel_mm  # 20.0 px/mm
    phones = [
        ("DT_A", px_mm_goc),
        ("DT_B", px_mm_goc),
        ("DT_C", px_mm_goc * (1.0 + lech_scale_dt_c)),
    ]
    rows: list[dict[str, object]] = []
    idx_me = 0
    for dt_id, px_mm in phones:
        scale_rel = px_mm / px_mm_goc
        for S in (0.0, 8.0, 16.0, 24.0, 32.0):
            for T in (20.0, 30.0):
                for _ in range(2):
                    dy_mm = op.delta_y_vi_sai_px(S, T, 25.0, cfg) / px_mm_goc
                    dy_px = dy_mm * px_mm + float(rng.normal(0.0, 0.08 * scale_rel))
                    rows.append({
                        cal.COT_DO_MAN: S,
                        cal.COT_NHIET_DO: T,
                        cal.COT_NHIET_DO_TC: 25.0,
                        cal.COT_DELTA_Y: dy_px,
                        cal.COT_PX_PER_MM: px_mm,
                        cal.COT_DO_DUC: 0.0,
                        cal.COT_GHI_CHU: "mo_phong_x4",
                        cal.COT_ID_THIET_BI: "TB_X4",
                        cal.COT_MA_ME_PHA: f"ME_{(idx_me % 2) + 1:02d}",
                        cal.COT_ID_DIEN_THOAI: dt_id,
                        cal.COT_NGUON: "MO_PHONG",
                    })
                    idx_me += 1
    return pd.DataFrame(rows)


def test_x4_100_bo_du_lieu_lopo_mm_giam_rms_so_voi_px() -> None:
    """100 bộ dữ liệu mô phỏng lệch thang 5%: quy đổi mm giảm RMS LOPO rõ rệt và px bật cờ cảnh báo."""
    cfg = op.CauHinhQuangHoc.tu_yaml()
    rng = np.random.default_rng(202620)

    rms_px_list: list[float] = []
    rms_mm_list: list[float] = []
    dat_giam = 0
    bat_co_px = 0

    for _ in range(100):
        df = _tao_bo_du_lieu_3_dien_thoai(cfg, rng, lech_scale_dt_c=0.05)
        kq = phan_tich_chuyen_duong_chuan(df, nguong_RMS_ppt=0.5)
        cmp = kq["so_sanh_lopo_px_vs_mm"]
        assert cmp["kha_dung"] is True
        r_px = cmp["rms_lopo_px_ppt"]
        r_mm = cmp["rms_lopo_mm_ppt"]
        rms_px_list.append(r_px)
        rms_mm_list.append(r_mm)
        if r_mm < r_px:
            dat_giam += 1
        if kq["ket_qua_theo_don_vi"]["px"]["lopo_dien_thoai"]["tong_hop"]["vuot_nguong"]:
            bat_co_px += 1

    w_giam = khoang_tin_cay_wilson(dat_giam, 100)
    assert dat_giam == 100, f"Không phải mọi bộ đều giảm RMS khi đổi sang mm: {w_giam}"
    assert float(np.mean(rms_px_list)) > 0.5
    assert float(np.mean(rms_mm_list)) < 0.25
    assert bat_co_px >= 95
    assert any(
        c["ma"] == "DUONG_CHUAN_KHONG_CHUYEN_DUOC" and c["cap"] == "can_than"
        for c in kq["canh_bao_chi_tiet"]
    )


def test_x4_khong_du_nhom_va_tich_hop_cli_api_xuat_bao_cao(tmp_path: Path) -> None:
    """Khi < 2 điện thoại hoặc < 2 mẻ pha không lỗi; kiểm CLI, API và xuat_bao_cao."""
    cfg = op.CauHinhQuangHoc.tu_yaml()
    rng = np.random.default_rng(202621)
    df = _tao_bo_du_lieu_3_dien_thoai(cfg, rng, lech_scale_dt_c=0.05)

    # Nhóm chỉ có 1 điện thoại và 1 mẻ pha
    df_1 = df[df[cal.COT_ID_DIEN_THOAI] == "DT_A"].copy()
    df_1[cal.COT_MA_ME_PHA] = "ME_DUY_NHAT"
    kq_1 = phan_tich_chuyen_duong_chuan(df_1)
    assert kq_1["trang_thai"] == "KHONG_DU_NHOM"
    assert kq_1["ket_qua_theo_don_vi"]["px"]["lopo_dien_thoai"]["trang_thai"] == "KHONG_DU_NHOM"
    assert kq_1["ket_qua_theo_don_vi"]["px"]["lobo_me_pha"]["trang_thai"] == "KHONG_DU_NHOM"

    # CLI
    csv_p = tmp_path / "cdc.csv"
    df.to_csv(csv_p, index=False)
    out_json = tmp_path / "cdc.json"
    out_csv = tmp_path / "cdc_summary.csv"
    assert cli_chuyen_main(["--csv", str(csv_p), "--output-json", str(out_json), "--output-csv", str(out_csv)]) == 0
    assert out_json.exists() and out_csv.exists()

    # API
    client = TestClient(app)
    r_api = client.post("/api/chuyen-duong-chuan", json={"mode": "csv", "csv_text": df.to_csv(index=False)})
    assert r_api.status_code == 200
    js = r_api.json()
    assert js["ok"] is True
    assert js["ket_qua"]["co_canh_bao_khong_chuyen_duoc"] is True

    # xuat_bo_bao_cao
    out_dir = tmp_path / "bao_cao_x4"
    res_bc = xuat_bo_bao_cao(
        csv_hieu_chuan=csv_p,
        out_dir=out_dir,
    )
    assert res_bc["chuyen_duong_chuan_csv"].exists()
    assert res_bc["chuyen_duong_chuan_png"].exists()
    md_text = res_bc["tong_hop_bao_cao_md"].read_text(encoding="utf-8")
    assert "DUONG_CHUAN_KHONG_CHUYEN_DUOC" in md_text or "Cảnh báo (can_than)" in md_text
