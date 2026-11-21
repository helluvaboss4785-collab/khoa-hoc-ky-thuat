"""So sánh hiệu năng các kênh màu ("R", "G", "B", "xam", "Y", "auto") trên ảnh JPEG (R5).

LƯU Ý TRUNG THỰC DỮ LIỆU:
- Tham số `--nguon` (`THUC_TE` hoặc `MO_PHONG`) là BẮT BUỘC.
- Kết quả trên ảnh JPEG MÔ PHỎNG KHÔNG thể dùng để kết luận kênh nào tốt hơn trên điện thoại thật;
  người dùng phải chạy script này trên chính thư mục ảnh chụp thật của nhóm bằng `--nguon THUC_TE`.

Cách chạy:
    python scripts/so_sanh_kenh.py --nguon MO_PHONG --so-anh 10
    python scripts/so_sanh_kenh.py --nguon THUC_TE --thu-muc data/anh_that
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.measure import do_delta_y_tu_anh  # noqa: E402
from core.optics import CauHinhQuangHoc  # noqa: E402
from scripts.danh_gia_do_ben_vung import khoang_tin_cay_wilson  # noqa: E402
from sim.synth import ThamSoMoPhong, sinh_anh_mau_mo_phong  # noqa: E402

DUOI_ANH_HOP_LE = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
CAC_KENH = ("R", "G", "B", "xam", "Y", "auto")


def _tai_mau_jpeg_sim(
    so_anh: int,
    cfg: CauHinhQuangHoc,
) -> list[tuple[str, np.ndarray, float]]:
    """Sinh tập ảnh màu JPEG mô phỏng qua các mức nén & lấy mẫu màu 4:4:4 / 4:2:2 / 4:2:0."""
    has_sampling = hasattr(cv2, "IMWRITE_JPEG_SAMPLING_FACTOR")
    sampling_modes: list[tuple[str, int | None]]
    if has_sampling:
        sampling_modes = [
            ("444", int(getattr(cv2, "IMWRITE_JPEG_SAMPLING_FACTOR_444"))),
            ("422", int(getattr(cv2, "IMWRITE_JPEG_SAMPLING_FACTOR_422"))),
            ("420", int(getattr(cv2, "IMWRITE_JPEG_SAMPLING_FACTOR_420"))),
        ]
    else:
        sampling_modes = [("mac_dinh_opencv", None)]

    qualities = (95, 80, 60)
    mau_list: list[tuple[str, np.ndarray, float]] = []
    for idx in range(so_anh):
        mp = sinh_anh_mau_mo_phong(
            ThamSoMoPhong(
                chieu_cao=320,
                chieu_rong=440,
                y_tham_chieu_goc=90.0,
                S_ppt=20.0,
                T_C=25.0,
                T_tham_chieu_C=25.0,
                seed=5000 + idx,
            ),
            cfg=cfg,
            ty_le_kenh=(1.0, 0.35, 0.35),
            gan_watermark=False,
        )
        for q in qualities:
            for s_name, s_flag in sampling_modes:
                params = [cv2.IMWRITE_JPEG_QUALITY, int(q)]
                if s_flag is not None:
                    params.extend([cv2.IMWRITE_JPEG_SAMPLING_FACTOR, int(s_flag)])
                ok, buf = cv2.imencode(".jpg", mp.anh, params)
                if not ok:
                    continue
                img_dec = cv2.imdecode(buf, cv2.IMREAD_COLOR)
                if img_dec is None:
                    continue
                dieu_kien = f"JPEG_Q{q}_{s_name}"
                mau_list.append((dieu_kien, img_dec, float(mp.delta_y_ly_thuyet_px)))
    return mau_list


def _doc_thu_muc_anh(thu_muc: Path) -> list[tuple[str, np.ndarray, float | None]]:
    if not thu_muc.exists() or not thu_muc.is_dir():
        raise FileNotFoundError(f"Không tìm thấy thư mục ảnh: {thu_muc}")
    files = sorted(p for p in thu_muc.iterdir() if p.is_file() and p.suffix.lower() in DUOI_ANH_HOP_LE)
    if not files:
        raise ValueError(f"Không tìm thấy ảnh hợp lệ trong {thu_muc}.")
    out: list[tuple[str, np.ndarray, float | None]] = []
    for p in files:
        arr = np.frombuffer(p.read_bytes(), dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR) if arr.size > 0 else None
        if img is not None:
            out.append(("thu_muc_anh", img, None))
    if not out:
        raise ValueError("Không giải mã được ảnh nào trong thư mục.")
    return out


def so_sanh_kenh(
    nguon: str,
    thu_muc: Path | None = None,
    so_anh: int = 15,
) -> pd.DataFrame:
    if nguon not in ("THUC_TE", "MO_PHONG"):
        raise ValueError("--nguon bắt buộc phải là THUC_TE hoặc MO_PHONG.")
    if nguon == "THUC_TE" and thu_muc is None:
        raise ValueError("Khi --nguon THUC_TE bắt buộc truyền --thu-muc chứa ảnh thật của nhóm.")

    cfg = CauHinhQuangHoc.tu_yaml()
    if thu_muc is not None:
        ds_anh = _doc_thu_muc_anh(thu_muc)
    else:
        ds_anh = [(dk, im, dy_t) for dk, im, dy_t in _tai_mau_jpeg_sim(so_anh, cfg)]

    nhom_dk: dict[str, list[tuple[np.ndarray, float | None]]] = {}
    for dk, im, dy_t in ds_anh:
        nhom_dk.setdefault(dk, []).append((im, dy_t))

    rows: list[dict[str, Any]] = []
    for dk, items in nhom_dk.items():
        n_tot = len(items)
        for kenh in CAC_KENH:
            dys: list[float] = []
            errs: list[float] = []
            bhs: list[float] = []
            snrs: list[float] = []
            hop_le_cnt = 0
            for im, dy_true in items:
                try:
                    kq = do_delta_y_tu_anh(im, kenh_laser=kenh, tao_anh_ve=False)
                except Exception:
                    continue
                if np.isfinite(kq.delta_y_px):
                    dys.append(float(kq.delta_y_px))
                    if dy_true is not None:
                        errs.append(float(kq.delta_y_px - dy_true))
                bhs.append(float(kq.chat_luong.ti_le_bao_hoa))
                if np.isfinite(kq.chat_luong.snr):
                    snrs.append(float(kq.chat_luong.snr))
                if kq.chat_luong.hop_le:
                    hop_le_cnt += 1

            std_dy = float(np.std(dys, ddof=1)) if len(dys) >= 2 else (0.0 if len(dys) == 1 else float("nan"))
            lo_hl, hi_hl = khoang_tin_cay_wilson(hop_le_cnt, n_tot)
            rows.append({
                "nguon_du_lieu": nguon,
                "dieu_kien": dk,
                "kenh": kenh,
                "so_anh": n_tot,
                "so_hop_le": hop_le_cnt,
                "ti_le_hop_le": round(hop_le_cnt / float(n_tot), 4) if n_tot else 0.0,
                "wilson_hop_le_duoi": round(lo_hl, 4),
                "wilson_hop_le_tren": round(hi_hl, 4),
                "do_lap_lai_std_px": round(std_dy, 5) if np.isfinite(std_dy) else None,
                "delta_y_tb_px": round(float(np.mean(dys)), 4) if dys else None,
                "sai_so_tb_px": round(float(np.mean(errs)), 5) if errs else None,
                "ti_le_cot_bao_hoa_tb": round(float(np.mean(bhs)), 4) if bhs else None,
                "snr_tb": round(float(np.mean(snrs)), 2) if snrs else None,
            })
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description="So sánh các kênh màu laser trên ảnh JPEG (R5)")
    ap.add_argument("--nguon", required=True, choices=["THUC_TE", "MO_PHONG"], help="Bắt buộc khai báo nguồn ảnh")
    ap.add_argument("--thu-muc", type=Path, default=None, help="Thư mục ảnh (bắt buộc nếu THUC_TE)")
    ap.add_argument("--so-anh", type=int, default=15, help="Số ảnh mỗi điều kiện khi sinh JPEG mô phỏng")
    ap.add_argument("--out-csv", type=Path, default=None, help="Đường dẫn file CSV đầu ra")
    args = ap.parse_args()

    try:
        df = so_sanh_kenh(nguon=args.nguon, thu_muc=args.thu_muc, so_anh=args.so_anh)
    except Exception as exc:
        print(f"LOI: {exc}", file=sys.stderr)
        sys.exit(2)

    out_path = args.out_csv or (ROOT / "outputs" / f"so_sanh_kenh_{args.nguon}.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False, encoding="utf-8-sig")

    print(f"=== SO SANH KENH MAU ({args.nguon}) -> {out_path} ===")
    print(df[["dieu_kien", "kenh", "so_hop_le", "so_anh", "do_lap_lai_std_px", "ti_le_cot_bao_hoa_tb", "snr_tb"]].to_string(index=False))
    if args.nguon == "MO_PHONG":
        print(
            "\nLUU Y: Day la so lieu MO PHONG, KHONG ket luan kenh nao tot hon tren anh that.\n"
            "Hay chay tren anh chup that cua nhom: python scripts/so_sanh_kenh.py --nguon THUC_TE --thu-muc <thu_muc_anh_that>"
        )


if __name__ == "__main__":
    main()
