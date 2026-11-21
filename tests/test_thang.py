"""Kiem thu module thang pixel-sang-mm va doc EXIF phoi sang (T5)."""
from __future__ import annotations

import base64
import io
import json
import math

import numpy as np
import pandas as pd
import pytest
from PIL import Image

from app import web_app
from core import calibration as cal
from core import thang
from core.optics import CauHinhQuangHoc
from sim.synth import ThamSoMoPhong, sinh_anh_hai_vach_mo_phong


def _jpeg_bytes_with_exif(exposure: tuple[int, int] | None = (1, 125), iso: int | None = 200) -> bytes:
    img = Image.new("RGB", (64, 48), color=(20, 30, 40))
    buf = io.BytesIO()
    if exposure is None and iso is None:
        img.save(buf, format="JPEG")
        return buf.getvalue()
    exif = Image.Exif()
    if exposure is not None:
        exif[33434] = exposure
    if iso is not None:
        exif[34855] = iso
    img.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


def test_tinh_thang_tu_hai_diem_va_quy_doi_mm() -> None:
    kq = thang.tinh_thang_tu_hai_diem((10.0, 20.0), (10.0, 120.0), 10.0, sigma_diem_px=0.5, sigma_mm=0.1)
    assert kq.khoang_cach_px == pytest.approx(100.0)
    assert kq.px_per_mm == pytest.approx(10.0)
    assert kq.mm_per_px == pytest.approx(0.1)
    assert kq.u_px_per_mm > 0.0 and math.isfinite(kq.u_px_per_mm)

    dy_mm, u_dy_mm = thang.quy_doi_delta_y_sang_mm(
        50.0,
        kq.px_per_mm,
        sigma_delta_y_px=0.2,
        u_px_per_mm=kq.u_px_per_mm,
    )
    assert dy_mm == pytest.approx(5.0)
    assert u_dy_mm > 0.02

    with pytest.raises(ValueError):
        thang.tinh_thang_tu_hai_diem((5.0, 5.0), (5.0, 5.0), 10.0)
    with pytest.raises(ValueError):
        thang.tinh_thang_tu_hai_diem((0.0, 0.0), (0.0, 50.0), 0.0)


def test_doc_exif_phoi_sang() -> None:
    raw_exif = _jpeg_bytes_with_exif((1, 125), 200)
    info = thang.doc_exif_phoi_sang(raw_exif)
    assert info["exposure_time_s"] == pytest.approx(1.0 / 125.0)
    assert info["exposure_str"] == "1/125 s"
    assert info["iso"] == 200

    assert thang.doc_exif_phoi_sang(_jpeg_bytes_with_exif(None, None)) == {}
    assert thang.doc_exif_phoi_sang(b"not-an-image") == {}


def test_hieu_chuan_mm_on_dinh_qua_cac_muc_phong_dai() -> None:
    rows = []
    # Hai nhom du lieu o 2 khoang cach/phong dai camera khac nhau (10 px/mm va 15 px/mm)
    for idx, S in enumerate([0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0]):
        for zoom in (10.0, 15.0):
            dy_mm = 0.4 * S
            rows.append(
                {
                    cal.COT_DO_MAN: S,
                    cal.COT_NHIET_DO: 25.0 + (idx % 3 - 1),
                    cal.COT_NHIET_DO_TC: 25.0 + (idx % 3 - 1),
                    cal.COT_DELTA_Y: dy_mm * zoom,
                    cal.COT_PX_PER_MM: zoom,
                    cal.COT_ID_THIET_BI: "TB1",
                    cal.COT_ID_DIEN_THOAI: "DT1",
                    cal.COT_NGUON: cal.NHAN_THUC_TE,
                }
            )
    df = pd.DataFrame(rows)
    bc = cal.dung_duong_chuan(df, bac_ep=1, don_vi_y="mm")
    mh = bc.mo_hinh
    assert mh.don_vi_y == "mm"
    assert mh.R2 > 0.9999

    # Do o muc phong dai moi (12.5 px/mm) -> giai nguoc ve S = 22.0 ppt chinh xac
    zoom_new = 12.5
    dy_px_new = (0.4 * 22.0) * zoom_new
    est = cal.uoc_luong_do_man(
        mh,
        delta_y_px=dy_px_new,
        T_C=25.0,
        sigma_delta_y_px=0.2,
        T_tham_chieu_C=25.0,
        px_per_mm=zoom_new,
        u_px_per_mm=0.05,
    )
    assert est.S_ppt == pytest.approx(22.0, abs=0.05)


def test_api_measure_thang_exif_va_canh_bao_ae_af() -> None:
    from tests.test_web_app import _make_request, _run_coro

    cfg = CauHinhQuangHoc.tu_yaml()
    anh_obj = sinh_anh_hai_vach_mo_phong(
        ThamSoMoPhong(S_ppt=15.0, T_C=25.0, T_tham_chieu_C=25.0, sigma_nhieu_doc=0.5, seed=7),
        cfg,
        gan_watermark=False,
    )
    pil_img = Image.fromarray(anh_obj.anh).convert("RGB")
    exif = Image.Exif()
    exif[33434] = (1, 100)
    exif[34855] = 400
    buf = io.BytesIO()
    pil_img.save(buf, format="JPEG", quality=98, exif=exif)
    b64 = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

    req_unlocked = _make_request(
        "POST",
        "/api/measure",
        {
            "mode": "upload",
            "image_base64": b64,
            "nhiet_do_do": 25.0,
            "nhiet_do_tham_chieu": 25.0,
            "khoa_ae_af": False,
            "diem_thang_1": [0, 0],
            "diem_thang_2": [0, 100],
            "khoang_cach_thang_mm": 10.0,
        },
    )
    resp = _run_coro(web_app.api_measure(req_unlocked))
    assert resp.status_code == 200
    d = json.loads(resp.body.decode("utf-8"))
    assert d["exif"]["iso"] == 400
    assert d["exif"]["exposure_str"] == "1/100 s"
    assert d["thang_anh"]["px_per_mm"] == pytest.approx(10.0)
    assert d["delta_y_mm"] == pytest.approx(d["delta_y_px"] / 10.0)
    assert any("AE/AF lock" in w for w in d["chat_luong"]["canh_bao"])

    req_locked = _make_request(
        "POST",
        "/api/measure",
        {
            "mode": "upload",
            "image_base64": b64,
            "nhiet_do_do": 25.0,
            "nhiet_do_tham_chieu": 25.0,
            "khoa_ae_af": True,
        },
    )
    resp2 = _run_coro(web_app.api_measure(req_locked))
    assert resp2.status_code == 200
    d2 = json.loads(resp2.body.decode("utf-8"))
    assert not any("AE/AF lock" in w for w in d2["chat_luong"]["canh_bao"])


def test_r6_xu_ly_thu_muc_anh_ghi_px_per_mm_va_canh_bao_thieu_thang(tmp_path) -> None:
    """R6: xu_ly_thu_muc_anh ghi px_per_mm từ metadata và cảnh báo ảnh có thước nhưng thiếu px_per_mm."""
    import cv2
    from scripts.xu_ly_thu_muc_anh import xu_ly_thu_muc_anh

    cfg = CauHinhQuangHoc.tu_yaml()
    img_dir = tmp_path / "anh_r6"
    img_dir.mkdir()
    meta_rows = []
    for idx, (ten, px_val, co_thuoc) in enumerate([
        ("mau_01.png", 12.5, 1),
        ("mau_co_thuoc_02.png", "", 1),
    ]):
        mp = sinh_anh_hai_vach_mo_phong(
            ThamSoMoPhong(S_ppt=15.0, T_C=25.0, T_tham_chieu_C=25.0, seed=60 + idx),
            cfg=cfg,
            gan_watermark=False,
        )
        cv2.imwrite(str(img_dir / ten), mp.anh)
        meta_rows.append({
            "ten_file": ten,
            "do_man_chuan_ppt": 15.0,
            "nhiet_do_C": 25.0,
            "nhiet_do_tham_chieu_C": 25.0,
            "px_per_mm": px_val,
            "co_thuoc": co_thuoc,
            "id_thiet_bi": "TB1",
            "id_dien_thoai": "DT1",
        })
    meta_p = tmp_path / "meta.csv"
    pd.DataFrame(meta_rows).to_csv(meta_p, index=False, encoding="utf-8-sig")

    df_cal, df_rep, _, _ = xu_ly_thu_muc_anh(
        thu_muc=img_dir,
        nguon="MO_PHONG",
        metadata_csv=meta_p,
        out_csv=tmp_path / "cal.csv",
        out_report=tmp_path / "rep.csv",
    )
    assert df_cal[cal.COT_PX_PER_MM].iloc[0] == pytest.approx(12.5)
    assert df_cal[cal.COT_PX_PER_MM].iloc[1] == ""
    rep_by_name = {r["ten_file"]: r for _, r in df_rep.iterrows()}
    assert rep_by_name["mau_01.png"]["canh_bao_thang"] == ""
    assert "px_per_mm" in str(rep_by_name["mau_co_thuoc_02.png"]["canh_bao_thang"])

