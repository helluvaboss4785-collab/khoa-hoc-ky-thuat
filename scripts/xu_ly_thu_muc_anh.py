"""Công cụ hàng loạt xử lí thư mục ảnh thực nghiệm / mô phỏng thành CSV hiệu chuẩn (Q4).

Cách dùng:
    # 1. Dùng metadata.csv đi kèm thư mục ảnh đo thật:
    python scripts/xu_ly_thu_muc_anh.py --thu-muc data/anh_that --nguon THUC_TE --metadata data/anh_that/metadata.csv

    # 2. Đọc S, T, lần đo từ tên file mẫu `<độmặn>_<nhiệtđộ>_<lầnđo>.<ext>` (vd 20_28_01.jpg):
    python scripts/xu_ly_thu_muc_anh.py --thu-muc data/anh_mo_phong --nguon MO_PHONG --tu-ten-file

LƯU Ý TRUNG THỰC DỮ LIỆU:
- Tham số `--nguon` BẮT BUỘC phải khai báo tường minh (`THUC_TE` hoặc `MO_PHONG`), KHÔNG có mặc định.
- Mọi ảnh không đạt ngưỡng chất lượng đều bị loại khỏi CSV hiệu chuẩn và ghi lí do vào báo cáo chất lượng.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import calibration as cal  # noqa: E402
from core import thang  # noqa: E402
from core.measure import AnhKhongHopLeError, KhongTimThayVachError, do_delta_y_tu_anh  # noqa: E402

DUOI_ANH_HOP_LE = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
MAU_TEN_FILE_RE = re.compile(r"^(\d+(?:\.\d+)?)_(\d+(?:\.\d+)?)_(\d+)$")

COT_CSV_HIEU_CHUAN = [
    cal.COT_DO_MAN,
    cal.COT_NHIET_DO,
    cal.COT_NHIET_DO_TC,
    cal.COT_DELTA_Y,
    cal.COT_PX_PER_MM,
    cal.COT_DO_DUC,
    cal.COT_MA_ME_PHA,
    cal.COT_NGAY_DO,
    cal.COT_GHI_CHU,
    cal.COT_ID_THIET_BI,
    cal.COT_ID_DIEN_THOAI,
    cal.COT_NGUON,
    cal.COT_KHOA_AE_AF,
]


def _doc_cau_hinh_anh(config_path: Path = ROOT / "config.yaml") -> dict[str, Any]:
    if not config_path.exists():
        return {}
    with open(config_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return dict(raw.get("xu_ly_anh", {}) or {})


def phan_tich_ten_file(ten_file: Path | str) -> tuple[float, float, int]:
    """Đọc (do_man_ppt, nhiet_do_C, lan_do) từ tên file chuẩn `<độmặn>_<nhiệtđộ>_<lầnđo>.<ext>`.

    Không đoán nếu sai định dạng; báo lỗi ValueError rõ ràng cho từng file.
    """
    p = Path(ten_file)
    m = MAU_TEN_FILE_RE.match(p.stem.strip())
    if not m:
        raise ValueError(
            f"Tên file '{p.name}' không khớp mẫu '<độmặn>_<nhiệtđộ>_<lầnđo>.<ext>' (ví dụ '20_28_01.jpg')."
        )
    s_ppt = float(m.group(1))
    t_c = float(m.group(2))
    lan = int(m.group(3))
    return s_ppt, t_c, lan


def _parse_roi_tu_chuoi(raw: Any) -> tuple[int, int, int, int] | None:
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return None
    txt = str(raw).strip()
    if not txt:
        return None
    parts = [int(float(x.strip())) for x in txt.replace(";", ",").split(",") if x.strip()]
    if len(parts) != 4:
        raise ValueError(f"Chuỗi ROI '{txt}' phải gồm đủ 4 số y0,y1,x0,x1.")
    y0, y1, x0, x1 = parts
    if y1 <= y0 or x1 <= x0:
        raise ValueError(f"ROI không hợp lệ (y1<=y0 hoặc x1<=x0): {parts}")
    return (y0, y1, x0, x1)


def _doc_bang_roi(roi_path: Path | None) -> dict[str, tuple[tuple[int, int, int, int], tuple[int, int, int, int]]]:
    if roi_path is None:
        return {}
    df = pd.read_csv(roi_path, encoding="utf-8-sig")
    df.columns = [str(c).strip() for c in df.columns]
    if "ten_file" not in df.columns:
        raise ValueError("File roi.csv phải có cột 'ten_file'.")
    ket_qua: dict[str, tuple[tuple[int, int, int, int], tuple[int, int, int, int]]] = {}
    for _, row in df.iterrows():
        key = str(row["ten_file"]).strip()
        if not key:
            continue
        if "roi_tc" in df.columns and "roi_mau" in df.columns:
            r_tc = _parse_roi_tu_chuoi(row["roi_tc"])
            r_m = _parse_roi_tu_chuoi(row["roi_mau"])
        elif all(c in df.columns for c in ("y0_tc", "y1_tc", "x0_tc", "x1_tc", "y0_mau", "y1_mau", "x0_mau", "x1_mau")):
            r_tc = (int(row["y0_tc"]), int(row["y1_tc"]), int(row["x0_tc"]), int(row["x1_tc"]))
            r_m = (int(row["y0_mau"]), int(row["y1_mau"]), int(row["x0_mau"]), int(row["x1_mau"]))
        else:
            raise ValueError("File roi.csv cần cột 'roi_tc, roi_mau' hoặc đủ 8 cột y0_tc..x1_mau.")
        if r_tc is not None and r_m is not None:
            ket_qua[key] = (r_tc, r_m)
    return ket_qua


def _la_bool_int(val: Any, mac_dinh: int = 0) -> int:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return mac_dinh
    s = str(val).strip().lower()
    if s in ("1", "true", "co", "yes", "y"):
        return 1
    if s in ("0", "false", "khong", "no", "n", ""):
        return 0
    return int(float(s) != 0)


def xu_ly_thu_muc_anh(
    thu_muc: Path,
    nguon: str,
    metadata_csv: Path | None = None,
    roi_csv: Path | None = None,
    tu_ten_file: bool = False,
    out_csv: Path | None = None,
    out_report: Path | None = None,
    config_path: Path = ROOT / "config.yaml",
) -> tuple[pd.DataFrame, pd.DataFrame, Path, Path]:
    """Xử lí toàn bộ ảnh trong `thu_muc`, xuất CSV hiệu chuẩn (13 cột) và báo cáo chất lượng."""
    if nguon not in ("THUC_TE", "MO_PHONG"):
        raise ValueError(f"Tham số --nguon không hợp lệ: '{nguon}' (chỉ nhận THUC_TE hoặc MO_PHONG).")
    if not thu_muc.exists() or not thu_muc.is_dir():
        raise FileNotFoundError(f"Không tìm thấy thư mục ảnh: {thu_muc}")
    if metadata_csv is None and not tu_ten_file:
        raise ValueError("Phải cung cấp --metadata <file.csv> hoặc bật --tu-ten-file để đọc S, T.")

    img_cfg = _doc_cau_hinh_anh(config_path)
    roi_map = _doc_bang_roi(roi_csv)

    meta_by_name: dict[str, dict[str, Any]] = {}
    if metadata_csv is not None:
        df_meta = pd.read_csv(metadata_csv, encoding="utf-8-sig")
        df_meta.columns = [str(c).strip() for c in df_meta.columns]
        if "ten_file" not in df_meta.columns:
            raise ValueError("File metadata.csv bắt buộc phải có cột 'ten_file'.")
        for _, row in df_meta.iterrows():
            tf = str(row["ten_file"]).strip()
            if tf:
                meta_by_name[tf] = row.to_dict()

    ds_anh = sorted(
        p for p in thu_muc.iterdir() if p.is_file() and p.suffix.lower() in DUOI_ANH_HOP_LE
    )
    if not ds_anh:
        raise ValueError(f"Không tìm thấy ảnh hợp lệ ({', '.join(sorted(DUOI_ANH_HOP_LE))}) trong {thu_muc}.")

    if out_csv is None:
        duoi = "_MO_PHONG" if nguon == "MO_PHONG" else "_THUC_TE"
        out_csv = thu_muc / f"du_lieu_hieu_chuan{duoi}.csv"
    if out_report is None:
        out_report = out_csv.with_name(f"{out_csv.stem}_bao_cao_chat_luong.csv")

    cal_rows: list[dict[str, Any]] = []
    report_rows: list[dict[str, Any]] = []

    for img_path in ds_anh:
        meta = meta_by_name.get(img_path.name)
        s_val: float | None = None
        t_val: float | None = None
        lan_do: int | None = None

        if tu_ten_file:
            s_val, t_val, lan_do = phan_tich_ten_file(img_path)

        if meta is not None:
            if pd.notna(meta.get("do_man_chuan_ppt")):
                s_val = float(meta["do_man_chuan_ppt"])
            if pd.notna(meta.get("nhiet_do_C")):
                t_val = float(meta["nhiet_do_C"])
        elif metadata_csv is not None and not tu_ten_file:
            raise ValueError(f"Ảnh '{img_path.name}' không có dòng tương ứng trong {metadata_csv.name}.")

        if s_val is None or t_val is None:
            raise ValueError(f"Thiếu độ mặn chuẩn hoặc nhiệt độ cho ảnh '{img_path.name}'.")

        raw_bytes = img_path.read_bytes()
        exif_info = thang.doc_exif_phoi_sang(raw_bytes)
        arr = np.frombuffer(raw_bytes, dtype=np.uint8)
        img_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR) if arr.size > 0 else None

        meta_dict = meta or {}
        t_tc_raw = meta_dict.get("nhiet_do_tham_chieu_C")
        t_tc_val = float(t_tc_raw) if (t_tc_raw is not None and pd.notna(t_tc_raw) and str(t_tc_raw).strip() != "") else None
        px_raw = meta_dict.get("px_per_mm")
        px_val: float | None = None
        if px_raw is not None and pd.notna(px_raw) and str(px_raw).strip() != "":
            try:
                px_cand = float(px_raw)
                if np.isfinite(px_cand) and px_cand > 0.0:
                    px_val = px_cand
            except (TypeError, ValueError):
                px_val = None
        co_thuoc = _la_bool_int(meta_dict.get("co_thuoc"), 0) == 1
        txt_thuoc = f"{img_path.stem} {meta_dict.get('ghi_chu', '')}".lower()
        co_dau_hieu_thuoc = co_thuoc or any(tok in txt_thuoc for tok in ("thuoc", "thước", "ruler"))
        cb_thang = (
            "Ảnh có thước nhưng thiếu hoặc sai giá trị px_per_mm trong metadata"
            if (co_dau_hieu_thuoc and px_val is None)
            else ""
        )
        ma_me = str(meta_dict.get("ma_me_pha", "") if pd.notna(meta_dict.get("ma_me_pha", "")) else "").strip()
        ngay_do = str(meta_dict.get("ngay_do", "") if pd.notna(meta_dict.get("ngay_do", "")) else "").strip()
        id_tb = str(meta_dict.get("id_thiet_bi", "") if pd.notna(meta_dict.get("id_thiet_bi", "")) else "").strip()
        id_dt = str(meta_dict.get("id_dien_thoai", "") if pd.notna(meta_dict.get("id_dien_thoai", "")) else "").strip()
        khoa_ae = _la_bool_int(meta_dict.get("khoa_ae_af"), 0)
        ghi_chu_parts = []
        if meta_dict.get("ghi_chu") and pd.notna(meta_dict.get("ghi_chu")):
            ghi_chu_parts.append(str(meta_dict["ghi_chu"]).strip())
        if lan_do is not None:
            ghi_chu_parts.append(f"lan_do={lan_do}")
        ghi_chu_parts.append(f"file={img_path.name}")

        kw_measure: dict[str, Any] = {
            "nguong_bao_hoa": int(img_cfg.get("nguong_bao_hoa", 250)),
            "ti_le_bao_hoa_toi_da": float(img_cfg.get("ti_le_bao_hoa_toi_da", 0.02)),
            "ti_le_cot_bao_hoa_nghiem_trong": float(img_cfg.get("ti_le_cot_bao_hoa_nghiem_trong", 0.30)),
            "so_cot_lien_tiep_bao_hoa": int(img_cfg.get("so_cot_lien_tiep_bao_hoa", 15)),
            "nguong_nen_khong_deu": float(img_cfg.get("nguong_nen_khong_deu", 30.0)),
            "snr_toi_thieu": float(img_cfg.get("snr_toi_thieu", 10.0)),
            "kenh_laser": str(img_cfg.get("kenh_laser", "auto")),
            "tao_anh_ve": False,
        }

        kq_do = None
        dung_roi_fallback = False
        err_msg = ""
        try:
            if img_bgr is None or img_bgr.size == 0:
                raise AnhKhongHopLeError("Không giải mã được định dạng ảnh.")
            kq_do = do_delta_y_tu_anh(img_bgr, **kw_measure)
        except (KhongTimThayVachError, AnhKhongHopLeError, ValueError) as exc:
            if img_bgr is not None and img_path.name in roi_map:
                try:
                    r_tc, r_m = roi_map[img_path.name]
                    kq_do = do_delta_y_tu_anh(img_bgr, roi_tham_chieu=r_tc, roi_mau=r_m, **kw_measure)
                    dung_roi_fallback = True
                except Exception as exc2:
                    err_msg = str(exc2)
            else:
                err_msg = str(exc)

        if kq_do is not None and not kq_do.chat_luong.hop_le and img_bgr is not None and img_path.name in roi_map and not dung_roi_fallback:
            try:
                r_tc, r_m = roi_map[img_path.name]
                kq_fb = do_delta_y_tu_anh(img_bgr, roi_tham_chieu=r_tc, roi_mau=r_m, **kw_measure)
                if kq_fb.chat_luong.hop_le:
                    kq_do = kq_fb
                    dung_roi_fallback = True
            except Exception:
                pass

        if kq_do is None:
            report_rows.append({
                "ten_file": img_path.name,
                "nguon_du_lieu": nguon,
                "trang_thai": "LOI_DO",
                "hop_le": False,
                "dung_roi_fallback": False,
                "delta_y_px": None,
                "kenh_su_dung": "",
                "bao_hoa": None,
                "qua_mo": None,
                "nhoe": None,
                "nen_khong_deu": None,
                "exif_exposure": exif_info.get("exposure_str", ""),
                "exif_iso": exif_info.get("iso", ""),
                "canh_bao_thang": cb_thang,
                "ly_do_loai": err_msg,
            })
            continue

        cq = kq_do.chat_luong
        hop_le_cuoi = bool(cq.hop_le and np.isfinite(kq_do.delta_y_px))
        ly_do = "" if hop_le_cuoi else ("; ".join(cq.canh_bao) or "Chất lượng ảnh không đạt ngưỡng")
        report_rows.append({
            "ten_file": img_path.name,
            "nguon_du_lieu": nguon,
            "trang_thai": "CHAP_NHAN" if hop_le_cuoi else "LOAI_CHAT_LUONG",
            "hop_le": hop_le_cuoi,
            "dung_roi_fallback": dung_roi_fallback,
            "delta_y_px": round(float(kq_do.delta_y_px), 4) if np.isfinite(kq_do.delta_y_px) else None,
            "kenh_su_dung": kq_do.kenh_su_dung,
            "bao_hoa": cq.bao_hoa,
            "qua_mo": cq.qua_mo,
            "nhoe": cq.nhoe,
            "nen_khong_deu": cq.nen_khong_deu,
            "exif_exposure": exif_info.get("exposure_str", ""),
            "exif_iso": exif_info.get("iso", ""),
            "canh_bao_thang": cb_thang,
            "ly_do_loai": ly_do,
        })

        if hop_le_cuoi:
            cal_rows.append({
                cal.COT_DO_MAN: s_val,
                cal.COT_NHIET_DO: t_val,
                cal.COT_NHIET_DO_TC: t_tc_val if t_tc_val is not None else "",
                cal.COT_DELTA_Y: round(float(kq_do.delta_y_px), 5),
                cal.COT_PX_PER_MM: px_val if px_val is not None else "",
                cal.COT_DO_DUC: round(float(kq_do.chi_so_do_duc_tuong_doi), 5),
                cal.COT_MA_ME_PHA: ma_me,
                cal.COT_NGAY_DO: ngay_do,
                cal.COT_GHI_CHU: "; ".join(ghi_chu_parts),
                cal.COT_ID_THIET_BI: id_tb,
                cal.COT_ID_DIEN_THOAI: id_dt,
                cal.COT_NGUON: nguon,
                cal.COT_KHOA_AE_AF: khoa_ae,
            })

    df_cal = pd.DataFrame(cal_rows, columns=COT_CSV_HIEU_CHUAN)
    df_report = pd.DataFrame(report_rows)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_report.parent.mkdir(parents=True, exist_ok=True)
    df_cal.to_csv(out_csv, index=False, encoding="utf-8-sig")
    df_report.to_csv(out_report, index=False, encoding="utf-8-sig")
    return df_cal, df_report, out_csv, out_report


def main() -> None:
    ap = argparse.ArgumentParser(description="Xử lí hàng loạt ảnh đo Δy thành CSV hiệu chuẩn (Q4)")
    ap.add_argument("--thu-muc", type=Path, required=True, help="Thư mục chứa các file ảnh chụp")
    ap.add_argument(
        "--nguon",
        required=True,
        choices=["THUC_TE", "MO_PHONG"],
        help="BẮT BUỘC: nguồn gốc ảnh (THUC_TE cho ảnh máy thật, MO_PHONG cho ảnh tổng hợp)",
    )
    ap.add_argument("--metadata", type=Path, default=None, help="File metadata.csv mô tả các ảnh")
    ap.add_argument("--roi", type=Path, default=None, help="File roi.csv dự phòng khi ROI tự động thất bại")
    ap.add_argument(
        "--tu-ten-file",
        action="store_true",
        help="Đọc độ mặn, nhiệt độ, lần đo từ tên file mẫu <độmặn>_<nhiệtđộ>_<lầnđo>.<ext>",
    )
    ap.add_argument("--out-csv", type=Path, default=None, help="Đường dẫn file CSV hiệu chuẩn đầu ra")
    ap.add_argument("--out-report", type=Path, default=None, help="Đường dẫn file CSV báo cáo chất lượng")
    args = ap.parse_args()

    try:
        df_cal, df_report, csv_p, rep_p = xu_ly_thu_muc_anh(
            thu_muc=args.thu_muc,
            nguon=args.nguon,
            metadata_csv=args.metadata,
            roi_csv=args.roi,
            tu_ten_file=args.tu_ten_file,
            out_csv=args.out_csv,
            out_report=args.out_report,
        )
    except Exception as exc:
        print(f"LOI: {exc}", file=sys.stderr)
        sys.exit(2)

    tong = len(df_report)
    dat = len(df_cal)
    print(f"[{args.nguon}] Da xu ly {tong} anh: {dat} dat chuan, {tong - dat} bi loai.")
    print(f"- CSV hieu chuan ({len(df_cal)} dong): {csv_p}")
    print(f"- Bao cao chat luong: {rep_p}")


if __name__ == "__main__":
    main()
