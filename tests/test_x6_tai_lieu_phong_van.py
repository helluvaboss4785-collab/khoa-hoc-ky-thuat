"""Kiểm thử X6 — xác minh tài liệu phỏng vấn `docs/GIAI_THICH_CHO_PHONG_VAN.md`.

Kiểm tra:
1. Mọi chuỗi nằm trong dấu backtick `` `...` `` đều là đường dẫn file thật, định danh
   (module/class/hàm/tham số/thuộc tính/hằng số/mã lỗi) có trong AST codebase hoặc khóa
   trong `config.yaml` (không có tên bịa).
2. Ví dụ số chạy trực tiếp trên ảnh mô phỏng `seed=42` khớp với các số ghi trong tài liệu
   trong sai số ≤ 1e-6.
3. Tài liệu có đủ 5 mục, đủ 10 câu hỏi–đáp, gắn nhãn MÔ PHỎNG cho ví dụ và không khẳng
   định sai số thiết bị thật.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import calibration as cal
from core.measure import do_delta_y_tu_anh
from sim.synth import ThamSoMoPhong, sinh_anh_hai_vach_mo_phong, sinh_du_lieu_hieu_chuan_mo_phong

DOC_PATH = ROOT / "docs" / "GIAI_THICH_CHO_PHONG_VAN.md"


def _thu_thap_dinh_danh_va_khoa() -> set[str]:
    """Thu thập toàn bộ tên file, định danh AST trong repo và khóa trong config.yaml."""
    tokens: set[str] = set()

    # 1. File / thư mục trong repo
    for sub in ("core", "sim", "app", "scripts", "docs"):
        tokens.add(f"{sub}/")
        base = ROOT / sub
        if base.exists():
            for p in base.rglob("*"):
                rel = p.relative_to(ROOT).as_posix()
                tokens.add(rel)
                tokens.add(p.name)
                if p.suffix == ".py":
                    tokens.add(p.stem)
    for top in ("config.yaml", "README.md", "BAO_CAO_THAY_DOI.md", "requirements.txt"):
        if (ROOT / top).exists():
            tokens.add(top)
    for rel_data in ("data/tham_so_do_duoc.json", "data/phan_tich_troi_laser.json", "data/phan_tich_can_bang_nhiet.json"):
        tokens.add(rel_data)

    # 2. AST từ các file Python
    for folder in ("core", "sim", "app", "scripts"):
        for py in (ROOT / folder).rglob("*.py"):
            src = py.read_text(encoding="utf-8")
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    tokens.add(node.name)
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        for arg in node.args.args + node.args.kwonlyargs:
                            tokens.add(arg.arg)
                elif isinstance(node, ast.Name):
                    tokens.add(node.id)
                elif isinstance(node, ast.Attribute):
                    tokens.add(node.attr)
                elif isinstance(node, ast.Assign):
                    for tgt in node.targets:
                        if isinstance(tgt, ast.Name):
                            tokens.add(tgt.id)
                elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if re.fullmatch(r"[A-Za-z0-9_./\-]+", node.value):
                        tokens.add(node.value)

    # 3. Khóa từ config.yaml
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8")) or {}

    def _walk_yaml(obj: object, prefix: str = "") -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                k_str = str(k)
                tokens.add(k_str)
                full = f"{prefix}.{k_str}" if prefix else k_str
                tokens.add(full)
                _walk_yaml(v, full)
        elif isinstance(obj, list):
            for item in obj:
                _walk_yaml(item, prefix)

    _walk_yaml(cfg)
    return tokens


def test_x6_moi_backtick_ton_tai_trong_codebase_va_config() -> None:
    """Mọi token trong `` `...` `` của GIAI_THICH_CHO_PHONG_VAN.md phải tồn tại thật trong repo."""
    text = DOC_PATH.read_text(encoding="utf-8")
    valid_tokens = _thu_thap_dinh_danh_va_khoa()

    raw_bt = re.findall(r"`([^`\n]+)`", text)
    assert len(raw_bt) >= 40, "Tài liệu phải tham chiếu đầy đủ các symbol trong codebase."

    khong_hop_le: list[str] = []
    for bt in raw_bt:
        s = bt.strip()
        if s in valid_tokens:
            continue
        # Cho phép dạng biểu thức gán đơn giản `ten = gia_tri` hoặc `doi_so==gia_tri` nếu vế trái là symbol thật
        m_eq = re.match(r"^([A-Za-z_][A-Za-z0-9_.]*)\s*(?:==|=)\s*([0-9.\-]+)$", s)
        if m_eq and m_eq.group(1) in valid_tokens:
            continue
        khong_hop_le.append(s)

    assert not khong_hop_le, f"Phát hiện các token trong backtick không có trong codebase: {khong_hop_le}"


def test_x6_vi_du_so_seed_42_khop_tuyet_doi_va_du_5_muc() -> None:
    """Tái lập ví dụ số `seed=42` trong tài liệu: sai lệch ≤ 1e-6 và đủ 5 mục phỏng vấn."""
    text = DOC_PATH.read_text(encoding="utf-8")

    # Kiểm đủ 5 mục và 10 câu hỏi
    for idx in range(1, 6):
        assert f"## {idx}." in text
    for q_idx in range(1, 11):
        assert f"{q_idx}. **" in text
    assert "MÔ PHỎNG" in text
    assert "KHÔNG" in text and "không phải kết quả đo của thiết bị thật" in text.lower()

    # Tái chạy ví dụ seed=42
    df = sinh_du_lieu_hieu_chuan_mo_phong(seed=42)
    bc = cal.dung_duong_chuan(df)
    mp = sinh_anh_hai_vach_mo_phong(ThamSoMoPhong(S_ppt=15.0, T_C=25.0, T_tham_chieu_C=25.0, seed=42))
    kq_dy = do_delta_y_tu_anh(mp.anh, tao_anh_ve=False)
    kq_s = cal.uoc_luong_do_man(bc.mo_hinh, kq_dy.delta_y_px, 25.0, T_tham_chieu_C=25.0)

    expected = {
        "delta_y_ly_thuyet_px": mp.delta_y_ly_thuyet_px,
        "x_ref": kq_dy.x_ref,
        "y_tam_tc": kq_dy.vach_tham_chieu.y_tam,
        "y_tam_mau": kq_dy.vach_mau.y_tam,
        "delta_y_px": kq_dy.delta_y_px,
        "sai_so_delta_y_px": kq_dy.sai_so_delta_y_px,
        "S_ppt": kq_s.S_ppt,
        "u_S_ppt": kq_s.u_S_ppt,
        "U_S_ppt": kq_s.U_S_ppt,
    }
    patterns = {
        "delta_y_ly_thuyet_px": r"delta_y_ly_thuyet_px = ([0-9.]+)",
        "x_ref": r"x_ref = ([0-9.]+)",
        "y_tam_tc": r"vach_tham_chieu`\): `y_tam = ([0-9.]+)`",
        "y_tam_mau": r"vach_mau`\): `y_tam = ([0-9.]+)`",
        "delta_y_px": r"delta_y_px = ([0-9.]+)` px",
        "sai_so_delta_y_px": r"sai_so_delta_y_px = ([0-9.]+)",
        "S_ppt": r"S_ppt = ([0-9.]+)",
        "u_S_ppt": r"u_S_ppt = ([0-9.]+)",
        "U_S_ppt": r"U_S_ppt = ([0-9.]+)",
    }
    for key, pat in patterns.items():
        m = re.search(pat, text)
        assert m is not None, f"Không tìm thấy số cho {key} trong tài liệu"
        val_doc = float(m.group(1))
        assert abs(val_doc - expected[key]) <= 1e-6, f"Sai lệch {key}: doc={val_doc}, live={expected[key]}"
