"""Kiểm thử X3 — phân tích cân bằng nhiệt hai ngăn sau khi đổ mẫu thực nghiệm.

Mọi dữ liệu trong file test này đều là MÔ PHỎNG tổng hợp (fixed seeds) dùng để
kiểm chứng phục hồi tham số (τ, D_∞, t_chờ), độ phủ KTC 95%, tỉ lệ loại bỏ minh bạch,
CLI --ap-dung, API và ưu tiên tham số đo được trong core/optics.py. Các test truyền
nhãn THUC_TE chỉ kiểm logic đường ống, KHÔNG phải số liệu đo thật.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from starlette.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.web_app import app
from core import optics as op
from core.can_bang_nhiet import (
    LoiCanBangNhietKhongHopLeError,
    ap_dung_can_bang_nhiet_vao_tham_so,
    duong_dan_phan_tich_can_bang_nhiet,
    phan_tich_can_bang_nhiet_tu_df,
)
from core.troi_laser import duong_dan_tham_so_do_duoc
from scripts.kiem_tra_chap_nhan_vong3 import khoang_tin_cay_wilson
from scripts.phan_tich_can_bang_nhiet_thuc_nghiem import main as cli_cbn_main


def test_x3_200_lan_do_mau_mo_phong_phuc_hoi_va_ktc_95() -> None:
    """200 lần đổ mẫu mô phỏng (σ_T = 0.05°C, D_∞ = 0.2°C): phục hồi τ, D_∞, t_chờ và KTC 95% ≥ 90%."""
    rng = np.random.default_rng(202610)
    tau_true = 90.0
    d0_true = 4.0
    d_inf_true = 0.2
    nguong = 0.3
    t_cho_true = tau_true * math.log(abs(d0_true) / nguong)
    t_grid = np.arange(0.0, 390.0, 30.0)  # 13 điểm từ 0 đến 360 giây

    rows: list[dict[str, object]] = []
    for i in range(200):
        nhieu_tc = rng.normal(0.0, 0.05, size=len(t_grid))
        nhieu_mau = rng.normal(0.0, 0.05, size=len(t_grid))
        t_tc = 25.0 + nhieu_tc
        t_mau = 25.0 + d_inf_true + d0_true * np.exp(-t_grid / tau_true) + nhieu_mau
        for tg, tm, ttc in zip(t_grid, t_mau, t_tc):
            rows.append({
                "ma_lan_do": f"LAN_{i:03d}",
                "thoi_gian_giay": float(tg),
                "T_mau_C": float(tm),
                "T_tham_chieu_C": float(ttc),
            })

    kq = phan_tich_can_bang_nhiet_tu_df(
        pd.DataFrame(rows),
        nguong_D_C=nguong,
        nguon_du_lieu="MO_PHONG",
        luu_json=False,
    )
    assert kq["trang_thai"] == "HOP_LE"
    assert kq["so_lan_do_hop_le"] == 200
    assert kq["so_lan_do_bi_loai"] == 0

    err_tau = [abs(x["tau_giay"] - tau_true) for x in kq["cac_lan_do_hop_le"]]
    err_dinf = [abs(x["D_inf_C"] - d_inf_true) for x in kq["cac_lan_do_hop_le"]]
    err_tcho = [abs(x["t_cho_giay"] - t_cho_true) for x in kq["cac_lan_do_hop_le"]]

    phu_tau = sum(lo <= tau_true <= hi for lo, hi in (x["ktc_95_tau_giay"] for x in kq["cac_lan_do_hop_le"]))
    phu_dinf = sum(lo <= d_inf_true <= hi for lo, hi in (x["ktc_95_D_inf_C"] for x in kq["cac_lan_do_hop_le"]))
    phu_tcho = sum(lo <= t_cho_true <= hi for lo, hi in (x["ktc_95_t_cho_giay"] for x in kq["cac_lan_do_hop_le"]))

    w_tau = khoang_tin_cay_wilson(phu_tau, 200)
    w_dinf = khoang_tin_cay_wilson(phu_dinf, 200)
    w_tcho = khoang_tin_cay_wilson(phu_tcho, 200)

    assert abs(kq["median_tau_giay"] - tau_true) < 2.0
    assert abs(kq["D_inf_trung_binh_C"] - d_inf_true) < 0.02
    assert abs(kq["median_t_cho_giay"] - t_cho_true) < 5.0
    assert float(np.sqrt(np.mean(np.square(err_tau)))) < 5.0
    assert float(np.sqrt(np.mean(np.square(err_dinf)))) < 0.06
    assert float(np.sqrt(np.mean(np.square(err_tcho)))) < 12.0

    assert phu_tau / 200 >= 0.90, f"Phủ KTC95% tau={phu_tau}/200 {w_tau}"
    assert phu_dinf / 200 >= 0.90, f"Phủ KTC95% D_inf={phu_dinf}/200 {w_dinf}"
    assert phu_tcho / 200 >= 0.90, f"Phủ KTC95% t_cho={phu_tcho}/200 {w_tcho}"

    # Phản ánh đầy đủ D_inf = 0.2 °C != 0
    assert kq["sigma_D_khi_da_on_dinh_C"] >= 0.2
    assert kq["sigma_D_khi_chua_do_C"] > kq["sigma_D_khi_da_on_dinh_C"]


def test_x3_loai_minh_bach_lan_thieu_diem_va_khong_hoi_tu() -> None:
    """Lần đo < 5 điểm và lần đo nhiễu phẳng không suy giảm mũ phải bị loại minh bạch."""
    rows = []
    # Lần 1 hợp lệ
    for t in range(0, 361, 30):
        rows.append({"ma_lan_do": "LAN_OK", "thoi_gian_giay": t, "D_C": 0.2 + 3.5 * math.exp(-t / 80.0)})
    # Lần 2 chỉ có 4 điểm (< 5)
    for t in (0, 30, 60, 90):
        rows.append({"ma_lan_do": "LAN_THIEU", "thoi_gian_giay": t, "D_C": 3.0 * math.exp(-t / 80.0)})
    # Lần 3 nhiễu phẳng hoàn toàn (không thể định danh τ)
    rng = np.random.default_rng(77)
    for t in range(0, 301, 30):
        rows.append({"ma_lan_do": "LAN_PHANG", "thoi_gian_giay": t, "D_C": float(rng.normal(0.0, 0.002))})

    kq = phan_tich_can_bang_nhiet_tu_df(pd.DataFrame(rows), nguon_du_lieu="MO_PHONG", luu_json=False)
    assert kq["so_lan_do_hop_le"] == 1
    assert kq["so_lan_do_bi_loai"] == 2
    ma_loai = {x["ma_lan_do"] for x in kq["danh_sach_loai"]}
    assert ma_loai == {"LAN_THIEU", "LAN_PHANG"}


def test_x3_cli_api_va_optics_uu_tien_sigma_D(tmp_path: Path) -> None:
    """Kiểm CLI --ap-dung, API /api/can-bang-nhiet-thuc-nghiem và optics.ngan_sach_sai_so;

    chỉ kiểm logic đường ống, dữ liệu vẫn là mô phỏng.
    """
    csv_p = tmp_path / "cbn.csv"
    rows = []
    for m in range(1, 3):
        for t in range(0, 361, 30):
            rows.append({
                "ma_lan_do": f"M{m}",
                "thoi_gian_giay": t,
                "T_mau_C": 25.2 + 3.5 * math.exp(-t / 85.0),
                "T_tham_chieu_C": 25.0,
            })
    pd.DataFrame(rows).to_csv(csv_p, index=False)

    rc = cli_cbn_main([
        "--csv",
        str(csv_p),
        "--nguon",
        "THUC_TE",
        "--nguoi-thuc-hien",
        "Hoc Sinh B",
        "--ap-dung",
    ])
    assert rc == 0
    assert duong_dan_phan_tich_can_bang_nhiet().exists()
    assert duong_dan_tham_so_do_duoc().exists()

    tham_so = json.loads(duong_dan_tham_so_do_duoc().read_text(encoding="utf-8"))
    assert "sigma_D_khi_da_on_dinh_C" in tham_so["tham_so"]
    assert "sigma_D_khi_chua_do_C" in tham_so["tham_so"]
    sigma_on_dinh = tham_so["tham_so"]["sigma_D_khi_da_on_dinh_C"]["gia_tri"]

    cfg_qh = op.CauHinhQuangHoc.tu_yaml()
    ns = op.ngan_sach_sai_so(15.0, 25.0, cfg_qh, 0.05, 0.5, 0.05, 5.0, 0.01)
    assert ns.nguon["nhiet_do"] == "đo được"
    assert ns.tham_so_su_dung["lech_nhiet_do_C"] == pytest.approx(sigma_on_dinh)

    # Từ chối áp dụng khi không có lần hợp lệ
    bad_df = pd.DataFrame([{"ma_lan_do": "ONLY_3", "thoi_gian_giay": k * 10, "D_C": 1.0} for k in range(3)])
    kq_bad = phan_tich_can_bang_nhiet_tu_df(bad_df, nguon_du_lieu="MO_PHONG", luu_json=False)
    assert kq_bad["trang_thai"] == "CHUA_DU_DU_LIEU"
    with pytest.raises(LoiCanBangNhietKhongHopLeError):
        ap_dung_can_bang_nhiet_vao_tham_so(kq_bad, nguoi_thuc_hien="Hoc Sinh B")

    client = TestClient(app)
    r_get = client.get("/api/can-bang-nhiet-thuc-nghiem/trang-thai")
    assert r_get.status_code == 200
    assert r_get.json()["bao_cao"]["trang_thai"] == "HOP_LE"

    r_post_bad = client.post(
        "/api/can-bang-nhiet-thuc-nghiem",
        json={"rows": bad_df.to_dict(orient="records"), "ap_dung": True, "nguoi_thuc_hien": "Hoc Sinh B"},
    )
    assert r_post_bad.status_code == 422
    assert r_post_bad.json()["loai_loi"] == "CHUA_DU_DU_LIEU"
