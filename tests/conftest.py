"""Cấu hình dùng chung cho pytest: cô lập sổ sha256 mô phỏng và sổ ảnh đã xử lí vào thư mục tạm."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _co_lap_so_anh_w0(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Không để mọi test và subprocess ghi vào sổ hoặc file kết quả thật trong outputs/ và data/."""
    so_dir = tmp_path / "_so_anh_tam"
    so_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SALINITY_SO_MO_PHONG_PATH", str(so_dir / "so_anh_mo_phong.csv"))
    monkeypatch.setenv("SALINITY_SO_DA_XU_LY_PATH", str(so_dir / "so_anh_da_xu_ly.csv"))
    monkeypatch.setenv("SALINITY_THAM_SO_DO_DUOC_PATH", str(so_dir / "tham_so_do_duoc.json"))
    monkeypatch.setenv("SALINITY_PHAN_TICH_TROI_PATH", str(so_dir / "phan_tich_troi_laser.json"))
    monkeypatch.setenv("SALINITY_PHAN_TICH_CBN_PATH", str(so_dir / "phan_tich_can_bang_nhiet.json"))
    monkeypatch.setenv("SALINITY_DU_LIEU_THUC_CSV_PATH", str(so_dir / "du_lieu_hieu_chuan_thuc.csv"))
    monkeypatch.setenv("SALINITY_ANH_THUC_DIR", str(so_dir / "anh_thuc"))
    monkeypatch.setenv("SALINITY_PHIEN_THU_JSON_PATH", str(so_dir / "phien_thu_du_lieu.json"))
