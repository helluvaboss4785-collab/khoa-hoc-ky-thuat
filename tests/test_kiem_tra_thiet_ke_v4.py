"""Kiểm thử V4: kiểm tra thiết kế thí nghiệm (không chặn, đầy đủ điều kiện & API/CLI/báo cáo)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from starlette.testclient import TestClient

from app import web_app
from core import calibration as cal
from core.kiem_tra_thiet_ke import kiem_tra_thiet_ke_thi_nghiem, kiem_tra_thiet_ke_tu_csv
from scripts import kiem_tra_thiet_ke_thi_nghiem as cli_tk
from scripts.xuat_bao_cao import xuat_bo_bao_cao
from sim.synth import sinh_du_lieu_hieu_chuan_mo_phong


def _tao_df_thiet_ke_day_du(
    muc_S: tuple[float, ...] = (0.0, 5.0, 10.0, 15.0, 25.0, 35.0),
    muc_T: tuple[float, ...] = (20.0, 25.0, 30.0),
    so_lan_lap: int = 3,
    co_T_tc: bool = False,
) -> pd.DataFrame:
    """Tạo DataFrame MÔ PHỎNG đạt đủ mọi tiêu chí V4 để làm chuẩn kiểm thử."""
    df = sinh_du_lieu_hieu_chuan_mo_phong(
        muc_S=muc_S,
        muc_T=muc_T,
        so_lan_lap=so_lan_lap,
        sigma_nhiet_ke_C=0.1,
        T_tham_chieu_C=(22.0, 27.0) if co_T_tc else None,
        seed=42,
    )
    df[cal.COT_MA_ME_PHA] = ["ME_01" if (i % 2 == 0) else "ME_02" for i in range(len(df))]
    df[cal.COT_PX_PER_MM] = 20.0
    return df


def _trang_thai_theo_ma(kq: dict) -> dict[str, str]:
    return {m["ma"]: m["trang_thai"] for m in kq["muc_kiem"]}


def _make_request(payload: dict) -> object:
    raw = json.dumps(payload).encode("utf-8")

    async def receive():
        return {"type": "http.request", "body": raw, "more_body": False}

    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/kiem-tra-thiet-ke",
        "headers": [(b"content-type", b"application/json")],
    }
    return Request(scope, receive)


def test_v4_bo_day_du_dat_100_phan_tram():
    df = _tao_df_thiet_ke_day_du()
    kq = kiem_tra_thiet_ke_thi_nghiem(df, muon_hoc_D=False, don_vi_y="px")
    assert kq["hop_le_tong_quat"] is True
    assert kq["so_chua_dat"] == 0
    assert kq["so_canh_bao"] == 0
    st = _trang_thai_theo_ma(kq)
    assert st["bien_thien_D"] == "bo_qua"
    for ma, val in st.items():
        if ma != "bien_thien_D":
            assert val == "dat", f"Mục {ma} phải đạt nhưng là {val}"

    df_d = _tao_df_thiet_ke_day_du(co_T_tc=True)
    kq_d = kiem_tra_thiet_ke_thi_nghiem(df_d, muon_hoc_D=True, don_vi_y="mm")
    assert kq_d["hop_le_tong_quat"] is True
    assert all(m["trang_thai"] == "dat" for m in kq_d["muc_kiem"])


def test_v4_1_muc_do_man_that_bai():
    df = _tao_df_thiet_ke_day_du(muc_S=(15.0,))
    kq = kiem_tra_thiet_ke_thi_nghiem(df)
    st = _trang_thai_theo_ma(kq)
    assert kq["hop_le_tong_quat"] is False
    assert st["so_muc_man"] == "chua_dat"
    assert st["co_muc_0"] == "chua_dat"
    assert st["phu_dai_man"] == "chua_dat"
    assert st["can_bang_muc_man"] == "chua_dat"


def test_v4_1_me_pha_va_thieu_cot_ma_me_pha_tho():
    df = _tao_df_thiet_ke_day_du()
    df[cal.COT_MA_ME_PHA] = "ME_DUY_NHAT"
    kq_1_me = kiem_tra_thiet_ke_thi_nghiem(df)
    assert kq_1_me["hop_le_tong_quat"] is False
    assert _trang_thai_theo_ma(kq_1_me)["me_pha"] == "chua_dat"

    # CSV thô không có cột ma_me_pha: phải bắt được TRƯỚC khi doc_csv_hieu_chuan tự điền
    df_thieu_cot = df.drop(columns=[cal.COT_MA_ME_PHA])
    csv_text = df_thieu_cot.to_csv(index=False)
    kq_csv = kiem_tra_thiet_ke_tu_csv(csv_text)
    assert _trang_thai_theo_ma(kq_csv)["me_pha"] == "chua_dat"


def test_v4_dai_nhiet_hep_va_gom_cum_nhiet_duong_nua_do():
    df_hep = _tao_df_thiet_ke_day_du(muc_T=(24.5, 25.0, 25.5))
    kq_hep = kiem_tra_thiet_ke_thi_nghiem(df_hep)
    st_hep = _trang_thai_theo_ma(kq_hep)
    assert kq_hep["hop_le_tong_quat"] is False
    assert st_hep["bien_do_nhiet"] == "chua_dat"
    assert st_hep["so_muc_nhiet"] == "chua_dat"

    # Kiểm tra ranh giới .5 °C (22.5, 25.5, 28.5) không bị round() tách đôi làm sai số lần lặp/ô
    df_half = _tao_df_thiet_ke_day_du(muc_T=(22.5, 25.5, 28.5), so_lan_lap=3)
    kq_half = kiem_tra_thiet_ke_thi_nghiem(df_half)
    assert kq_half["tom_tat"]["so_muc_nhiet"] == 3
    assert kq_half["tom_tat"]["min_lap_moi_o"] == 3
    assert _trang_thai_theo_ma(kq_half)["so_lan_lap_moi_o"] == "dat"


def test_v4_it_lap_va_thieu_muc_0():
    df_it = _tao_df_thiet_ke_day_du(so_lan_lap=2)
    kq_it = kiem_tra_thiet_ke_thi_nghiem(df_it)
    assert _trang_thai_theo_ma(kq_it)["so_lan_lap_moi_o"] == "chua_dat"

    df_no0 = _tao_df_thiet_ke_day_du(muc_S=(3.0, 10.0, 15.0, 20.0, 25.0, 35.0))
    kq_no0 = kiem_tra_thiet_ke_thi_nghiem(df_no0)
    assert _trang_thai_theo_ma(kq_no0)["co_muc_0"] == "chua_dat"


def test_v4_nguon_du_lieu_thieu_hoac_tron_lan():
    df = _tao_df_thiet_ke_day_du()
    csv_no_src = df.drop(columns=[cal.COT_NGUON]).to_csv(index=False)
    kq_no_src = kiem_tra_thiet_ke_tu_csv(csv_no_src)
    assert _trang_thai_theo_ma(kq_no_src)["nguon_du_lieu"] == "chua_dat"

    df_mix = df.copy()
    # Chỉ kiểm logic trộn nhãn, toàn bộ số liệu vẫn là mô phỏng
    df_mix.loc[df_mix.index[:3], cal.COT_NGUON] = cal.NHAN_THUC_TE
    kq_mix = kiem_tra_thiet_ke_thi_nghiem(df_mix)
    assert _trang_thai_theo_ma(kq_mix)["nguon_du_lieu"] == "chua_dat"


def test_v4_bien_thien_D_va_px_per_mm_va_can_bang():
    df = _tao_df_thiet_ke_day_du()
    # muon_hoc_D=True nhưng thiếu cột T_tc
    kq_no_tc = kiem_tra_thiet_ke_thi_nghiem(df, muon_hoc_D=True)
    assert _trang_thai_theo_ma(kq_no_tc)["bien_thien_D"] == "chua_dat"

    # Có T_tc nhưng D ≈ 0 mọi điểm (không biến thiên)
    df_d0 = df.copy()
    df_d0[cal.COT_NHIET_DO_TC] = df_d0[cal.COT_NHIET_DO]
    kq_d0 = kiem_tra_thiet_ke_thi_nghiem(df_d0, muon_hoc_D=True)
    assert _trang_thai_theo_ma(kq_d0)["bien_thien_D"] == "chua_dat"

    # Thiếu px_per_mm: cảnh báo nếu px, chưa đạt nếu mm
    df_no_px = df.drop(columns=[cal.COT_PX_PER_MM])
    assert _trang_thai_theo_ma(kiem_tra_thiet_ke_thi_nghiem(df_no_px, don_vi_y="px"))["px_per_mm"] == "canh_bao"
    assert _trang_thai_theo_ma(kiem_tra_thiet_ke_thi_nghiem(df_no_px, don_vi_y="mm"))["px_per_mm"] == "chua_dat"

    # Trộn px_per_mm nhiều khoảng cách: chưa đạt nếu px, đạt nếu mm
    df_mix_px = df.copy()
    df_mix_px.loc[df_mix_px.index[:10], cal.COT_PX_PER_MM] = 30.0
    assert _trang_thai_theo_ma(kiem_tra_thiet_ke_thi_nghiem(df_mix_px, don_vi_y="px"))["px_per_mm"] == "chua_dat"
    assert _trang_thai_theo_ma(kiem_tra_thiet_ke_thi_nghiem(df_mix_px, don_vi_y="mm"))["px_per_mm"] == "dat"

    # Mất cân bằng tỷ lệ các mức S (> 40% tại 1 mức)
    extra = df[df[cal.COT_DO_MAN] == 0.0].copy()
    df_unbal = pd.concat([df] + [extra] * 8, ignore_index=True)
    assert _trang_thai_theo_ma(kiem_tra_thiet_ke_thi_nghiem(df_unbal))["can_bang_muc_man"] == "chua_dat"


def test_v4_khong_chan_dung_duong_chuan_cli_va_xuat_bao_cao(tmp_path: Path, capsys):
    # Tập ít mức, 1 nhiệt độ -> thiếu nhiều hạng mục nhưng dung_duong_chuan KHÔNG chặn
    df_thieu = _tao_df_thiet_ke_day_du(muc_S=(0.0, 15.0, 30.0), muc_T=(25.0,), so_lan_lap=3)
    df_thieu = df_thieu.drop(columns=[cal.COT_MA_ME_PHA])
    csv_path = tmp_path / "thieu_thiet_ke.csv"
    df_thieu.to_csv(csv_path, index=False, encoding="utf-8-sig")

    bc = cal.dung_duong_chuan(cal.doc_csv_hieu_chuan(csv_path))
    assert bc.mo_hinh.R2 > 0.99

    # CLI không chặn trả mã 0; --strict trả mã 1
    assert cli_tk.main(["--csv", str(csv_path), "--json"]) == 0
    out_json = json.loads(capsys.readouterr().out)
    assert out_json["hop_le_tong_quat"] is False
    assert _trang_thai_theo_ma(out_json)["me_pha"] == "chua_dat"
    assert cli_tk.main(["--csv", str(csv_path), "--strict"]) == 1

    # Báo cáo V4 xuất kiem_tra_thiet_ke.csv và mục 6 trong tong_hop_bao_cao.md
    kq_bc = xuat_bo_bao_cao(csv_hieu_chuan=csv_path, out_dir=tmp_path / "bao_cao")
    assert Path(kq_bc["kiem_tra_thiet_ke_csv"]).exists()
    md_text = Path(kq_bc["tong_hop_bao_cao_md"]).read_text(encoding="utf-8")
    assert "## 6. Kiểm tra thiết kế thí nghiệm hiệu chuẩn" in md_text
    assert _trang_thai_theo_ma(kq_bc["kiem_tra_thiet_ke"])["me_pha"] == "chua_dat"


def test_v4_api_make_request_va_testclient():
    df_ok = _tao_df_thiet_ke_day_du()
    csv_ok = df_ok.to_csv(index=False)

    # 1. Kiểm trực tiếp coroutine handler bằng _make_request
    resp_direct = asyncio.run(
        web_app.api_kiem_tra_thiet_ke(_make_request({"mode": "csv", "csv_text": csv_ok, "don_vi_y": "px"}))
    )
    assert resp_direct.status_code == 200
    body_direct = json.loads(resp_direct.body.decode("utf-8"))
    assert body_direct["hop_le_tong_quat"] is True

    # 2. Kiểm qua Starlette TestClient thật
    client = TestClient(web_app.app)
    r_sim = client.post("/api/kiem-tra-thiet-ke", json={"mode": "sim", "muon_hoc_D": False})
    assert r_sim.status_code == 200
    assert "muc_kiem" in r_sim.json()

    r_cal = client.post(
        "/api/calibrate",
        json={"mode": "csv", "csv_text": csv_ok, "file_name": "sim_ok.csv", "activate": False},
    )
    assert r_cal.status_code == 200
    j_cal = r_cal.json()
    assert j_cal["kiem_tra_thiet_ke"]["hop_le_tong_quat"] is True

    # Tập thiết kế chưa đạt vẫn trả 200 ở /api/calibrate (không chặn) và kèm chi tiết chưa đạt
    csv_bad = df_ok[df_ok[cal.COT_DO_MAN] <= 10.0].drop(columns=[cal.COT_MA_ME_PHA]).to_csv(index=False)
    r_cal_bad = client.post(
        "/api/calibrate",
        json={"mode": "csv", "csv_text": csv_bad, "file_name": "sim_bad.csv", "activate": False},
    )
    assert r_cal_bad.status_code == 200
    assert r_cal_bad.json()["kiem_tra_thiet_ke"]["hop_le_tong_quat"] is False
