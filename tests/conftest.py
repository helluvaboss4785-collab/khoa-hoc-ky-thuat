"""Cấu hình dùng chung cho pytest: cô lập sổ sha256 mô phỏng và sổ ảnh đã xử lí vào thư mục tạm."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _co_lap_so_anh_w0(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Không để mọi test và subprocess ghi vào sổ thật outputs/so_anh_mo_phong.csv và data/so_anh_da_xu_ly.csv."""
    so_dir = tmp_path / "_so_anh_tam"
    so_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SALINITY_SO_MO_PHONG_PATH", str(so_dir / "so_anh_mo_phong.csv"))
    monkeypatch.setenv("SALINITY_SO_DA_XU_LY_PATH", str(so_dir / "so_anh_da_xu_ly.csv"))
