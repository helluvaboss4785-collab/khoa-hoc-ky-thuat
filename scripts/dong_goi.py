"""Đóng gói mã nguồn sạch để nộp bài / gửi giám khảo.

Giữ lại đầy đủ mã nguồn, `docs/`, biểu mẫu `data/mau_*.csv` và các tệp cấu hình/xác nhận
`data/*.json` do người dùng tự tạo (nếu có); loại trừ `.venv`, `.git`, `__pycache__`,
`.pytest_cache`, CSDL `*.db*` và file `.zip`.
"""

from __future__ import annotations

import argparse
import fnmatch
import sys
import zipfile
from datetime import datetime
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
MAU_FILE_LOAI_TRU = ("*.db", "*.db-wal", "*.db-shm", "*.db-*", "*.sqlite3", "*.sqlite", "*.pyc", "*.pyo", "*.zip")
FILE_TUONG_DOI_LOAI_TRU = {"outputs/so_anh_mo_phong.csv"}
THU_MUC_CAM_TRONG_ZIP = {".venv", "venv", "env", ".git", "__pycache__", ".pytest_cache"}
MAU_FILE_CAM_TRONG_ZIP = ("*.db", "*.db-wal", "*.db-shm", "*.sqlite3", "*.sqlite", "*.db-*")


def _can_loai_tru(rel_path: Path) -> bool:
    """True nếu đường dẫn tương đối thuộc thư mục/mẫu file cần loại trừ khỏi gói nộp."""
    if rel_path.as_posix() in FILE_TUONG_DOI_LOAI_TRU:
        return True
    if any(part in THU_MUC_LOAI_TRU for part in rel_path.parts):
        return True
    name = rel_path.name
    return any(fnmatch.fnmatch(name, pat) for pat in MAU_FILE_LOAI_TRU)


def tao_file_zip_nop_bai(
    duong_dan_zip: str | Path,
    goc: Path = ROOT,
    *,
    kem_anh_thuc: bool = True,
) -> tuple[Path, int]:
    """Tạo file zip sạch từ thư mục dự án, trả `(duong_dan_zip, so_file)`."""
    out = Path(duong_dan_zip).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    goc_res = Path(goc).resolve()
    dem = 0
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(goc_res.rglob("*")):
            if not p.is_file():
                continue
            if p.resolve() == out:
                continue
            rel = p.relative_to(goc_res)
            if _can_loai_tru(rel):
                continue
            if not kem_anh_thuc and rel.as_posix().startswith("data/anh_thuc/"):
                continue
            zf.write(p, arcname=rel.as_posix())
            dem += 1
    return out, dem


def kiem_tra_goi_zip(
    duong_dan_zip: str | Path,
    gioi_han_mb: float = 20.0,
) -> tuple[bool, list[str], float]:
    """Kiểm tra gói zip nộp bài: không chứa .venv/.git/__pycache__/.pytest_cache/*.db* và < gioi_han_mb MB.

    Trả `(dat, danh_sach_vi_pham, dung_luong_mb)`.
    """
    p = Path(duong_dan_zip)
    if not p.exists():
        return False, [f"Không tìm thấy file zip: {p}"], 0.0

    size_mb = p.stat().st_size / (1024.0 * 1024.0)
    vi_pham: list[str] = []
    if size_mb >= gioi_han_mb:
        vi_pham.append(f"Dung lượng {size_mb:.2f} MB >= giới hạn {gioi_han_mb:g} MB.")

    with zipfile.ZipFile(p, "r") as zf:
        for info in zf.infolist():
            norm = info.filename.replace("\\", "/")
            parts = [part for part in norm.split("/") if part]
            if not parts:
                continue
            if any(part in THU_MUC_CAM_TRONG_ZIP for part in parts):
                vi_pham.append(f"Chứa thư mục cấm: {info.filename}")
                continue
            ten = parts[-1]
            if any(fnmatch.fnmatch(ten.lower(), pat) for pat in MAU_FILE_CAM_TRONG_ZIP):
                vi_pham.append(f"Chứa file CSDL cấm: {info.filename}")

    return len(vi_pham) == 0, vi_pham, size_mb


def canh_bao_out_trong_du_an(out_path: Path, root: Path = ROOT) -> str | None:
    """Trả về thông báo cảnh báo nếu `--out` nằm bên trong thư mục dự án `root`."""
    try:
        out_res = out_path.resolve()
        root_res = root.resolve()
        if out_res.is_relative_to(root_res):
            return (
                f"[CẢNH BÁO] Đường dẫn --out ({out_res}) nằm bên trong thư mục dự án ({root_res}); "
                "nên lưu file .zip ra thư mục cha (bỏ --out) để tránh nhầm lẫn khi nộp bài."
            )
    except Exception:
        return None
    return None


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Tạo file zip nộp bài KHKT sạch")
    parser.add_argument("--out", default=None, help="Đường dẫn file .zip đầu ra")
    parser.add_argument(
        "--kiem-tra",
        action="store_true",
        help="Xác nhận gói zip sau khi đóng gói không chứa file/thư mục cấm và < 20 MB.",
    )
    parser.add_argument(
        "--gioi-han-mb",
        type=float,
        default=20.0,
        help="Giới hạn dung lượng tối đa (MB) cho chế độ --kiem-tra (mặc định 20 MB).",
    )
    parser.add_argument(
        "--khong-kem-anh",
        action="store_true",
        help="Loại trừ thư mục ảnh thực data/anh_thuc/ để giữ gói zip nhẹ khi chỉ nộp mã nguồn & CSV/JSON.",
    )
    args = parser.parse_args(argv)

    if args.out:
        out_path = Path(args.out)
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = ROOT.parent / f"khkt_do_man_vi_sai_{stamp}.zip"

    msg_canh_bao = canh_bao_out_trong_du_an(out_path, ROOT)
    if msg_canh_bao:
        print(msg_canh_bao)

    out, dem = tao_file_zip_nop_bai(out_path, ROOT, kem_anh_thuc=not args.khong_kem_anh)
    size_mb = out.stat().st_size / (1024.0 * 1024.0)
    print(f"Đã đóng gói {dem} tệp vào: {out} ({size_mb:.2f} MB)")

    if args.kiem_tra:
        dat, vi_pham, _ = kiem_tra_goi_zip(out, gioi_han_mb=args.gioi_han_mb)
        if not dat:
            print("VI PHẠM GÓI NỘP:")
            for v in vi_pham:
                print(f" - {v}")
            return 1
        print(
            f"KIỂM TRA ĐẠT: Giữ docs/, data/mau_*.csv, data/*.json (khi có); "
            f"không chứa .venv/.git/__pycache__/.pytest_cache/*.db* và < {args.gioi_han_mb:g} MB."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
