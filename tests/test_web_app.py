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
