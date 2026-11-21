"""Kiểm thử R10: kiểm tra scripts/dong_goi.py và tùy chọn --kiem-tra."""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dong_goi import kiem_tra_goi_zip, tao_file_zip_nop_bai


def test_r10_dong_goi_va_kiem_tra_dat(tmp_path: Path):
    """Đóng gói thử một thư mục dự án giả có sẵn file cấm -> gói sạch đạt --kiem-tra."""
    fake_proj = tmp_path / "proj"
    (fake_proj / "core").mkdir(parents=True)
    (fake_proj / "core" / "sample.py").write_text("x = 1\n", encoding="utf-8")
    (fake_proj / ".venv" / "Lib").mkdir(parents=True)
    (fake_proj / ".venv" / "Lib" / "pkg.py").write_text("y = 2\n", encoding="utf-8")
    (fake_proj / ".git").mkdir()
    (fake_proj / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (fake_proj / "__pycache__").mkdir()
    (fake_proj / "__pycache__" / "a.pyc").write_bytes(b"123")
    (fake_proj / ".pytest_cache").mkdir()
    (fake_proj / ".pytest_cache" / "v").write_text("cache", encoding="utf-8")
    (fake_proj / "data").mkdir()
    (fake_proj / "data" / "nhat_ki.db").write_bytes(b"sqlite")
    (fake_proj / "data" / "nhat_ki.db-wal").write_bytes(b"wal")

    out_zip = tmp_path / "clean.zip"
    _, dem = tao_file_zip_nop_bai(out_zip, fake_proj)
    assert dem == 1
    dat, vi_pham, size_mb = kiem_tra_goi_zip(out_zip, gioi_han_mb=20.0)
    assert dat is True
    assert vi_pham == []
    assert size_mb < 1.0


def test_r10_kiem_tra_goi_phat_hien_vi_pham_va_cli(tmp_path: Path):
    """Phát hiện zip chứa *.db*, __pycache__, .venv, .pytest_cache, hoặc vượt ngưỡng dung lượng."""
    for bad_name in (
        "data/lich_su.db",
        "data/lich_su.db-shm",
        "core/__pycache__/mod.cpython-311.pyc",
        ".venv/Scripts/python.exe",
        ".git/index",
        ".pytest_cache/README.md",
    ):
        zp = tmp_path / f"{bad_name.replace('/', '_')}.zip"
        with zipfile.ZipFile(zp, "w") as zf:
            zf.writestr(bad_name, b"bad")
        dat, vi_pham, _ = kiem_tra_goi_zip(zp, gioi_han_mb=20.0)
        assert dat is False, f"Phải bắt được {bad_name}"
        assert len(vi_pham) >= 1

    # Vượt dung lượng giới hạn (tạo zip với giới hạn rất nhỏ 0.0001 MB)
    zp_big = tmp_path / "over_limit.zip"
    with zipfile.ZipFile(zp_big, "w") as zf:
        zf.writestr("readme.txt", "abc" * 500)
    dat_big, vi_pham_big, _ = kiem_tra_goi_zip(zp_big, gioi_han_mb=0.0001)
    assert dat_big is False
    assert any("Dung lượng" in m for m in vi_pham_big)

    # Kiểm CLI thực trên repo hiện tại với --kiem-tra
    zip_repo = tmp_path / "repo_submit.zip"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "dong_goi.py"), "--out", str(zip_repo), "--kiem-tra"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "KIỂM TRA ĐẠT" in proc.stdout
    assert zip_repo.exists()
