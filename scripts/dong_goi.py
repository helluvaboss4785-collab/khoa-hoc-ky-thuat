"""Đóng gói mã nguồn dự án thành file .zip sạch để nộp bài (T12).

Loại trừ: .venv, .git, __pycache__, .pytest_cache, *.db*, *.pyc, *.zip.
"""
from __future__ import annotations

import argparse
import fnmatch
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

THU_MUC_LOAI_TRU = {
    ".venv",
    "venv",
    "env",
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

MAU_FILE_LOAI_TRU = (
    "*.db",
    "*.db-wal",
    "*.db-shm",
    "*.sqlite3",
    "*.pyc",
    "*.pyo",
    "*.zip",
)


def co_nen_bo_qua(rel_path: Path) -> bool:
    for part in rel_path.parts[:-1]:
        if part in THU_MUC_LOAI_TRU:
            return True
    name = rel_path.name
    if rel_path.parts[0] in THU_MUC_LOAI_TRU:
        return True
    return any(fnmatch.fnmatch(name, pat) for pat in MAU_FILE_LOAI_TRU)


def tao_file_zip_nop_bai(duong_dan_zip: str | Path, goc: Path = ROOT) -> tuple[Path, int]:
    out = Path(duong_dan_zip).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    goc_resolved = goc.resolve()

    so_file = 0
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for item in sorted(goc_resolved.rglob("*")):
            if not item.is_file():
                continue
            if item.resolve() == out:
                continue
            rel = item.relative_to(goc_resolved)
            if co_nen_bo_qua(rel):
                continue
            zf.write(item, rel.as_posix())
            so_file += 1
    return out, so_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Tạo file zip nộp bài KHKT sạch")
    parser.add_argument(
        "--out",
        default=str(ROOT / "outputs" / "du_an_khkt_nop_bai.zip"),
        help="Đường dẫn file .zip đầu ra",
    )
    args = parser.parse_args()
    out_path, count = tao_file_zip_nop_bai(args.out)
    print(f"Da dong goi {count} file vao: {out_path} ({out_path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
