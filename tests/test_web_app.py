"""Kiem thu cac route va API chinh cua giao dien Web 2.5D (app/web_app.py)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Coroutine

import pandas as pd
from starlette.requests import Request

from app import web_app


def _run_coro(coro: Coroutine[Any, Any, Any]) -> Any:
    """Chay coroutine dong bo khong can event loop/socketpair."""
    try:
        while True:
            coro.send(None)
    except StopIteration as exc:
        return exc.value


def _make_request(method: str, path: str, body: dict | None = None) -> Request:
    raw_body = json.dumps(body).encode("utf-8") if body is not None else b""
    headers = [(b"host", b"testserver")]
    if body is not None:
        headers.append((b"content-type", b"application/json"))
        headers.append((b"content-length", str(len(raw_body)).encode("ascii")))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 0),
        "server": ("testserver", 80),
    }

    sent_once = False

    async def receive() -> dict:
        nonlocal sent_once
        if not sent_once:
            sent_once = True
            return {"type": "http.request", "body": raw_body, "more_body": False}
        return {"type": "http.disconnect"}

    return Request(scope, receive)


def test_static_and_pwa_routes() -> None:
    for fn, expected_file in (
        (web_app.index, "index.html"),
        (web_app.manifest_json, "manifest.json"),
        (web_app.service_worker_js, "sw.js"),
    ):
        resp = _run_coro(fn(_make_request("GET", "/")))
        assert resp.status_code == 200
        assert Path(resp.path).name == expected_file
        assert Path(resp.path).is_file()


def test_api_bootstrap() -> None:
    resp = _run_coro(web_app.api_bootstrap(_make_request("GET", "/api/bootstrap")))
    assert resp.status_code == 200
    data = json.loads(resp.body.decode("utf-8"))
    assert "quang_hoc" in data
    assert "danh_sach_loai" in data
    assert len(data["danh_sach_loai"]) >= 1
    assert "mo_hinh" in data


def test_api_species_eval() -> None:
    resp = _run_coro(
        web_app.api_species_eval(_make_request("POST", "/api/species-eval", {"S_ppt": 15.0}))
    )
    assert resp.status_code == 200
    data = json.loads(resp.body.decode("utf-8"))
    assert data["S_ppt"] == 15.0
    assert "chi_tiet" in data
    assert "ma_tran" in data
    assert len(data["ma_tran"]) >= 1


def test_api_optics_sim() -> None:
    resp = _run_coro(
        web_app.api_optics_sim(
            _make_request(
                "POST",
                "/api/optics-sim",
                {"A_deg": 40.0, "D_m": 1.0, "S_ppt": 20.0, "T_C": 25.0},
            )
        )
    )
    assert resp.status_code == 200
    data = json.loads(resp.body.decode("utf-8"))
    assert len(data) > 0


def test_api_logs_and_template_csv() -> None:
    resp_logs = _run_coro(web_app.api_logs_list(_make_request("GET", "/api/logs")))
    assert resp_logs.status_code == 200
    logs_data = json.loads(resp_logs.body.decode("utf-8"))
    assert isinstance(logs_data, dict)

    resp_tpl = _run_coro(
        web_app.api_calibrate_template_csv(_make_request("GET", "/api/calibrate/template-csv"))
    )
    assert resp_tpl.status_code == 200
    assert "csv" in resp_tpl.media_type
    assert b"do_man_chuan_ppt" in resp_tpl.body


def test_mau_hieu_chuan_csv_valid() -> None:
    csv_path = Path(__file__).resolve().parents[1] / "data" / "mau_hieu_chuan.csv"
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    assert len(df) == 0
    assert {"do_man_chuan_ppt", "nhiet_do_C", "delta_y_px", "nguon_du_lieu"}.issubset(df.columns)


def test_api_calibrate_thieu_nguon_khong_gan_do_that() -> None:
    csv_text = (
        "do_man_chuan_ppt,nhiet_do_C,delta_y_px,do_duc_tuong_doi,ghi_chu,id_thiet_bi,id_dien_thoai\n"
        "0,25,0.0,0,a,TB1,DT1\n"
        "5,25,25.0,0,b,TB1,DT1\n"
        "10,25,50.0,0,c,TB1,DT1\n"
        "15,25,75.0,0,d,TB1,DT1\n"
        "20,25,100.0,0,e,TB1,DT1\n"
        "25,25,125.0,0,f,TB1,DT1\n"
        "30,25,150.0,0,g,TB1,DT1\n"
        "35,25,175.0,0,h,TB1,DT1\n"
    )
    resp = _run_coro(
        web_app.api_calibrate(
            _make_request("POST", "/api/calibrate", {"mode": "csv", "csv_text": csv_text, "activate": False})
        )
    )
    assert resp.status_code == 200
    data = json.loads(resp.body.decode("utf-8"))
    mh = data["mo_hinh"]
    assert mh["da_xac_nhan_thuc_te"] is False
    assert mh["nhan"] == "CHƯA XÁC NHẬN NGUỒN DỮ LIỆU"


def test_api_measure_bat_buoc_nhiet_do_va_khong_do_nhiet_do() -> None:
    resp_thieu = _run_coro(
        web_app.api_measure(_make_request("POST", "/api/measure", {"mode": "sim", "S_ppt": 15.0}))
    )
    assert resp_thieu.status_code == 400

    resp_no_t = _run_coro(
        web_app.api_measure(
            _make_request("POST", "/api/measure", {"mode": "sim", "S_ppt": 15.0, "khong_do_nhiet_do": True})
        )
    )
    assert resp_no_t.status_code == 200
    d_no_t = json.loads(resp_no_t.body.decode("utf-8"))
    assert d_no_t["khong_do_nhiet_do"] is True
    assert d_no_t["danh_gia_loai"] is None
    assert d_no_t["khong_danh_gia_duoc"] is True
    assert any("CHƯA ĐO NHIỆT ĐỘ" in w for w in d_no_t["mo_hinh_man"]["canh_bao"])


def test_cong_chat_luong_va_phan_loai_loi_api_measure() -> None:
    import base64
    import cv2
    import numpy as np

    # 1. Đo ảnh mô phỏng -> khong_danh_gia_duoc=True, KHONG gán màu an toàn/cảnh báo
    resp_sim = _run_coro(
        web_app.api_measure(
            _make_request("POST", "/api/measure", {"mode": "sim", "S_ppt": 15.0, "nhiet_do_do": 25.0})
        )
    )
    assert resp_sim.status_code == 200
    d_sim = json.loads(resp_sim.body.decode("utf-8"))
    assert d_sim["khong_danh_gia_duoc"] is True
    assert d_sim["danh_gia_loai"]["trang_thai"] == "KHONG_DANH_GIA_DUOC"

    # 2. Ảnh base64 hỏng -> 400 ANH_KHONG_HOP_LE
    resp_bad = _run_coro(
        web_app.api_measure(
            _make_request(
                "POST",
                "/api/measure",
                {"mode": "upload", "image_base64": "data:image/png;base64,NOT_A_VALID_IMG", "nhiet_do_do": 25.0},
            )
        )
    )
    assert resp_bad.status_code == 400
    assert json.loads(resp_bad.body.decode("utf-8"))["loai_loi"] == "ANH_KHONG_HOP_LE"

    # 3. Ảnh đen hoàn toàn không có vạch -> 422 KHONG_TIM_THAY_VACH
    black = np.zeros((80, 120, 3), dtype=np.uint8)
    ok, buf = cv2.imencode(".png", black)
    assert ok
    b64_black = "data:image/png;base64," + base64.b64encode(buf.tobytes()).decode("ascii")
    resp_novach = _run_coro(
        web_app.api_measure(
            _make_request(
                "POST",
                "/api/measure",
                {"mode": "upload", "image_base64": b64_black, "nhiet_do_do": 25.0},
            )
        )
    )
    assert resp_novach.status_code == 422
    assert json.loads(resp_novach.body.decode("utf-8"))["loai_loi"] == "KHONG_TIM_THAY_VACH"


def test_api_measure_multi_voi_khung_hong() -> None:
    import base64
    import cv2
    import numpy as np
    from core.optics import CauHinhQuangHoc
    from sim.synth import ThamSoMoPhong, sinh_anh_hai_vach_mo_phong

    cfg = CauHinhQuangHoc.tu_yaml()
    imgs_b64 = []
    for i in range(3):
        obj = sinh_anh_hai_vach_mo_phong(
            ThamSoMoPhong(S_ppt=15.0, T_C=25.0, T_tham_chieu_C=25.0, seed=50 + i),
            cfg,
            gan_watermark=False,
        )
        ok, buf = cv2.imencode(".png", obj.anh)
        assert ok
        imgs_b64.append("data:image/png;base64," + base64.b64encode(buf.tobytes()).decode("ascii"))

    # Thêm 1 ảnh đen không có vạch làm khung lỗi
    ok_b, buf_b = cv2.imencode(".png", np.zeros((80, 120, 3), dtype=np.uint8))
    assert ok_b
    imgs_b64.append("data:image/png;base64," + base64.b64encode(buf_b.tobytes()).decode("ascii"))

    resp = _run_coro(
        web_app.api_measure_multi(
            _make_request(
                "POST",
                "/api/measure-multi",
                {"mode": "upload", "images_base64": imgs_b64, "nhiet_do_do": 25.0, "nhiet_do_tham_chieu": 25.0},
            )
        )
    )
    assert resp.status_code == 200
    d = json.loads(resp.body.decode("utf-8"))
    assert d["da_khung_hinh"] is True
    assert d["so_khung_hop_le"] == 3
    assert d["tong_so_khung"] == 4
    assert len(d["khung_loi"]) == 1
    assert d["khung_loi"][0]["khung"] == 3
    assert d["delta_y_px"] > 0


def test_api_logs_toc_do_bien_doi_do_man(tmp_path: Path, monkeypatch) -> None:
    import math
    import pytest

    monkeypatch.setattr(web_app, "DB_PATH", tmp_path / "test_logs_t11.db")
    monkeypatch.setattr(web_app, "_DB_INIT_PATH", None)

    # 2 bản ghi cùng ao & cùng nguồn cách nhau 2 giờ; 1 bản ghi khác nguồn
    web_app.luu_nhat_ki(
        vi_tri="Ao_A",
        loai_nuoi="Tôm thử",
        delta_y_px=50.0,
        do_man_ppt=10.0,
        bat_dinh_U_ppt=0.3,
        nhiet_do_C=25.0,
        do_duc=0.1,
        chat_luong_hop_le=True,
        nguon_du_lieu="ĐO THẬT",
        ghi_chu="lan 1",
        thoi_gian_tuy_chinh="2026-11-20 08:00:00",
    )
    web_app.luu_nhat_ki(
        vi_tri="Ao_A",
        loai_nuoi="Tôm thử",
        delta_y_px=70.0,
        do_man_ppt=14.0,
        bat_dinh_U_ppt=0.4,
        nhiet_do_C=26.0,
        do_duc=0.1,
        chat_luong_hop_le=True,
        nguon_du_lieu="ĐO THẬT",
        ghi_chu="lan 2",
        thoi_gian_tuy_chinh="2026-11-20 10:00:00",
    )
    web_app.luu_nhat_ki(
        vi_tri="Ao_A",
        loai_nuoi="Tôm thử",
        delta_y_px=100.0,
        do_man_ppt=20.0,
        bat_dinh_U_ppt=0.5,
        nhiet_do_C=26.0,
        do_duc=0.1,
        chat_luong_hop_le=True,
        nguon_du_lieu="MÔ PHỎNG",
        ghi_chu="khac nguon",
        thoi_gian_tuy_chinh="2026-11-20 11:00:00",
    )

    resp = _run_coro(web_app.api_logs_list(_make_request("GET", "/api/logs")))
    assert resp.status_code == 200
    data = json.loads(resp.body.decode("utf-8"))
    by_note = {r["ghi_chu"]: r for r in data["rows"]}
    assert by_note["lan 1"]["toc_do_ppt_gio"] is None
    assert by_note["lan 2"]["toc_do_ppt_gio"] == pytest.approx(2.0)
    assert by_note["lan 2"]["u_toc_do_ppt_gio"] == pytest.approx(math.hypot(0.3, 0.4) / 2.0)
    assert by_note["khac nguon"]["toc_do_ppt_gio"] is None


def test_q5_api_measure_multi_can_bang_nhiet():
    """Q5: Endpoint /api/measure-multi trả phân tích cân bằng nhiệt khi gửi kèm mốc thời gian."""
    import base64
    import math
    import cv2
    from core import optics as op
    from sim.synth import ThamSoMoPhong, sinh_anh_hai_vach_mo_phong

    cfg = op.CauHinhQuangHoc.tu_yaml()
    times_s = [0.0, 15.0, 30.0, 45.0, 60.0]
    imgs_b64 = []
    for i, t_sec in enumerate(times_s):
        # Mô phỏng nhiệt độ mẫu hạ dần về 25°C (chênh nhiệt ban đầu +8°C, τ = 35s)
        t_mau = 25.0 + 8.0 * math.exp(-t_sec / 35.0)
        obj = sinh_anh_hai_vach_mo_phong(
            ThamSoMoPhong(S_ppt=20.0, T_C=t_mau, T_tham_chieu_C=25.0, seed=70 + i),
            cfg=cfg,
            gan_watermark=False,
        )
        ok, buf = cv2.imencode(".png", obj.anh)
        assert ok
        imgs_b64.append("data:image/png;base64," + base64.b64encode(buf.tobytes()).decode("ascii"))

    resp = _run_coro(
        web_app.api_measure_multi(
            _make_request(
                "POST",
                "/api/measure-multi",
                {
                    "mode": "upload",
                    "images_base64": imgs_b64,
                    "thoi_gian_s": times_s,
                    "nhiet_do_do": 25.0,
                    "nhiet_do_tham_chieu": 25.0,
                },
            )
        )
    )
    assert resp.status_code == 200
    d = json.loads(resp.body.decode("utf-8"))
    cb = d.get("can_bang_nhiet")
    assert isinstance(cb, dict)
    assert cb["da_on_dinh"] is False
    assert len(cb["thoi_gian_hop_le_s"]) == 5
    assert len(cb["duong_khop_t_s"]) == 25


def test_q7_api_optics_sim_quan_fry_va_canh_bao_ngoai_dai():
    """Q7: Tab mô phỏng hỗ trợ tuyến tính | Quan-Fry và phát cảnh báo khi ngoài dải 0-30°C, 0-35‰, 400-700nm."""
    # 1. Mặc định giữ tuyến tính
    r_lin = _run_coro(web_app.api_optics_sim(_make_request("POST", "/api/optics-sim", {"S_ppt": 20.0, "T_C": 25.0})))
    assert r_lin.status_code == 200
    d_lin = json.loads(r_lin.body.decode("utf-8"))
    assert d_lin["mo_hinh_chiet_suat"] == "tuyen_tinh"
    assert d_lin["canh_bao_mo_hinh"] == []

    # 2. Quan-Fry trong dải -> không cảnh báo ngoài dải
    r_qf_ok = _run_coro(
        web_app.api_optics_sim(
            _make_request(
                "POST",
                "/api/optics-sim",
                {"S_ppt": 20.0, "T_C": 25.0, "mo_hinh_chiet_suat": "quan_fry", "buoc_song_nm": 650},
            )
        )
    )
    assert r_qf_ok.status_code == 200
    d_qf_ok = json.loads(r_qf_ok.body.decode("utf-8"))
    assert d_qf_ok["mo_hinh_chiet_suat"] == "quan_fry"
    assert d_qf_ok["canh_bao_mo_hinh"] == []

    # 3. Quan-Fry ngoài dải T=35°C -> cảnh báo rõ ràng
    r_qf_bad = _run_coro(
        web_app.api_optics_sim(
            _make_request(
                "POST",
                "/api/optics-sim",
                {"S_ppt": 20.0, "T_C": 35.0, "mo_hinh_chiet_suat": "quan_fry", "buoc_song_nm": 650},
            )
        )
    )
    assert r_qf_bad.status_code == 200
    d_qf_bad = json.loads(r_qf_bad.body.decode("utf-8"))
    assert len(d_qf_bad["canh_bao_mo_hinh"]) >= 1
    assert any("0–30 °C" in m for m in d_qf_bad["canh_bao_mo_hinh"])


def test_q8_gioi_han_dau_vao_413_va_lam_sach_ten_file(monkeypatch):
    """Q8: Ảnh quá dung lượng / quá nhiều khung / quá MP trả HTTP 413 ANH_QUA_LON; file giả trả 400; tên file được làm sạch."""
    import base64
    import cv2
    import numpy as np

    # 1. Tên file chứa path traversal và null byte phải được làm sạch
    clean = web_app._lam_sach_ten_file("../../etc/passwd\x00..\\abc def?.png")
    assert ".." not in clean and "/" not in clean and "\\" not in clean and "\x00" not in clean

    # 2. File không phải ảnh -> 400 ANH_KHONG_HOP_LE
    not_img_b64 = base64.b64encode(b"day khong phai la anh png hay jpg").decode("ascii")
    r_bad = _run_coro(
        web_app.api_measure(
            _make_request("POST", "/api/measure", {"mode": "upload", "image_base64": not_img_b64, "nhiet_do_do": 25.0})
        )
    )
    assert r_bad.status_code == 400
    assert json.loads(r_bad.body.decode("utf-8"))["loai_loi"] == "ANH_KHONG_HOP_LE"

    # 3. Quá số khung tối đa (> 60) -> 413 ANH_QUA_LON
    img_ok = np.zeros((40, 40, 3), dtype=np.uint8)
    ok, buf = cv2.imencode(".png", img_ok)
    assert ok
    img_ok_b64 = base64.b64encode(buf.tobytes()).decode("ascii")
    r_frames = _run_coro(
        web_app.api_measure_multi(
            _make_request(
                "POST",
                "/api/measure-multi",
                {"mode": "upload", "images_base64": [img_ok_b64] * 61, "nhiet_do_do": 25.0},
            )
        )
    )
    assert r_frames.status_code == 413
    assert json.loads(r_frames.body.decode("utf-8"))["loai_loi"] == "ANH_QUA_LON"

    # 4. Quá dung lượng MB (test qua giới hạn thấp monkeypatch để không cấp phát >25MB RAM giả) -> 413 ANH_QUA_LON
    monkeypatch.setattr(
        web_app,
        "load_limits_config",
        lambda: {"dung_luong_anh_MB": 0.0001, "so_khung_toi_da": 60, "so_megapixel_toi_da": 60.0},
    )
    r_mb = _run_coro(
        web_app.api_measure(
            _make_request("POST", "/api/measure", {"mode": "upload", "image_base64": img_ok_b64, "nhiet_do_do": 25.0})
        )
    )
    assert r_mb.status_code == 413
    assert json.loads(r_mb.body.decode("utf-8"))["loai_loi"] == "ANH_QUA_LON"

    # 5. Quá Megapixel (ảnh 200x200 = 0.04 MP vượt ngưỡng 0.01 MP) -> 413 ANH_QUA_LON
    monkeypatch.setattr(
        web_app,
        "load_limits_config",
        lambda: {"dung_luong_anh_MB": 25.0, "so_khung_toi_da": 60, "so_megapixel_toi_da": 0.01},
    )
    big_ok, big_buf = cv2.imencode(".png", np.zeros((200, 200, 3), dtype=np.uint8))
    assert big_ok
    big_b64 = base64.b64encode(big_buf.tobytes()).decode("ascii")
    r_mp = _run_coro(
        web_app.api_measure(
            _make_request("POST", "/api/measure", {"mode": "upload", "image_base64": big_b64, "nhiet_do_do": 25.0})
        )
    )
    assert r_mp.status_code == 413
    assert json.loads(r_mp.body.decode("utf-8"))["loai_loi"] == "ANH_QUA_LON"


def test_r1_can_bang_nhiet_giam_sigma_D_ba_nhanh(monkeypatch):
    """R1: Cờ tắt -> U giữ nguyên; cờ bật + ổn định >=5 phút -> U giảm & có cờ cảnh báo; chưa ổn định/ngắn -> giữ nguyên."""
    import base64
    import math
    import cv2
    import pytest
    from core import calibration as cal, optics as op
    from sim.synth import ThamSoMoPhong, sinh_anh_hai_vach_mo_phong

    cfg_op = op.CauHinhQuangHoc.tu_yaml()

    def _tao_chuoi(times_s, decaying: bool) -> list[str]:
        out = []
        for i, t_sec in enumerate(times_s):
            t_mau = (25.0 + 8.0 * math.exp(-t_sec / 300.0)) if decaying else 25.0
            obj = sinh_anh_hai_vach_mo_phong(
                ThamSoMoPhong(S_ppt=20.0, T_C=t_mau, T_tham_chieu_C=25.0, sigma_nhieu_doc=0.5, he_so_poisson=0.0, seed=100 + i),
                cfg=cfg_op,
                gan_watermark=False,
            )
            ok, buf = cv2.imencode(".png", obj.anh)
            assert ok
            out.append("data:image/png;base64," + base64.b64encode(buf.tobytes()).decode("ascii"))
        return out

    times_long = [0.0, 90.0, 180.0, 270.0, 360.0]  # 6 phút >= 5 phút
    times_short = [0.0, 30.0, 60.0, 90.0, 120.0]     # 2 phút < 5 phút
    imgs_flat_long = _tao_chuoi(times_long, decaying=False)
    imgs_flat_short = _tao_chuoi(times_short, decaying=False)
    imgs_decay_long = _tao_chuoi(times_long, decaying=True)

    # 1. Cờ tắt (mặc định) -> không giảm σ_D và có ghi chú rõ
    cfg_off = cal.CauHinhHieuChuan(cho_phep_giam_sigma_D_khi_on_dinh=False, sigma_D_khi_chua_do_C=2.0)
    monkeypatch.setattr(web_app, "load_calib_config", lambda: cfg_off)
    r_off = _run_coro(
        web_app.api_measure_multi(
            _make_request(
                "POST",
                "/api/measure-multi",
                {"mode": "upload", "images_base64": imgs_flat_long, "thoi_gian_s": times_long, "nhiet_do_do": 25.0},
            )
        )
    )
    assert r_off.status_code == 200
    d_off = json.loads(r_off.body.decode("utf-8"))
    assert d_off["can_bang_nhiet"]["da_on_dinh"] is True
    assert d_off["can_bang_nhiet"]["da_ap_dung_giam_sigma_D"] is False
    assert "chưa áp dụng giảm bất định" in d_off["can_bang_nhiet"]["ghi_chu_giam_bat_dinh"].lower()
    u_off = d_off["mo_hinh_man"]["U_S_ppt"]

    # 2. Cờ bật + chuỗi phẳng >= 5 phút + không nhập T_tc -> giảm σ_D còn 1.0°C và có cờ chenh_nhiet_gia_dinh_on_dinh
    cfg_on = cal.CauHinhHieuChuan(
        cho_phep_giam_sigma_D_khi_on_dinh=True,
        sigma_D_khi_chua_do_C=2.0,
        sigma_D_khi_da_on_dinh_C=1.0,
        thoi_gian_on_dinh_toi_thieu_phut=5.0,
    )
    monkeypatch.setattr(web_app, "load_calib_config", lambda: cfg_on)
    r_on = _run_coro(
        web_app.api_measure_multi(
            _make_request(
                "POST",
                "/api/measure-multi",
                {"mode": "upload", "images_base64": imgs_flat_long, "thoi_gian_s": times_long, "nhiet_do_do": 25.0},
            )
        )
    )
    assert r_on.status_code == 200
    d_on = json.loads(r_on.body.decode("utf-8"))
    assert d_on["can_bang_nhiet"]["da_ap_dung_giam_sigma_D"] is True
    assert d_on["mo_hinh_man"]["U_S_ppt"] < u_off * 0.7
    assert any(
        c["ma"] == "chenh_nhiet_gia_dinh_on_dinh" and c["cap"] == "can_than"
        for c in d_on["mo_hinh_man"]["canh_bao_chi_tiet"]
    )

    # 3. Cờ bật nhưng chuỗi quá ngắn (< 5 phút) hoặc chưa ổn định -> σ_D không đổi
    r_short = _run_coro(
        web_app.api_measure_multi(
            _make_request(
                "POST",
                "/api/measure-multi",
                {"mode": "upload", "images_base64": imgs_flat_short, "thoi_gian_s": times_short, "nhiet_do_do": 25.0},
            )
        )
    )
    d_short = json.loads(r_short.body.decode("utf-8"))
    assert d_short["can_bang_nhiet"]["da_ap_dung_giam_sigma_D"] is False
    assert d_short["mo_hinh_man"]["thanh_phan_bat_dinh"]["chenh_nhiet_chua_do"] == pytest.approx(
        d_off["mo_hinh_man"]["thanh_phan_bat_dinh"]["chenh_nhiet_chua_do"], rel=0.05
    )

    r_decay = _run_coro(
        web_app.api_measure_multi(
            _make_request(
                "POST",
                "/api/measure-multi",
                {"mode": "upload", "images_base64": imgs_decay_long, "thoi_gian_s": times_long, "nhiet_do_do": 25.0},
            )
        )
    )
    d_decay = json.loads(r_decay.body.decode("utf-8"))
    assert d_decay["can_bang_nhiet"]["da_on_dinh"] is False
    assert d_decay["can_bang_nhiet"]["da_ap_dung_giam_sigma_D"] is False
    assert d_decay["mo_hinh_man"]["U_S_ppt"] >= u_off * 0.95




