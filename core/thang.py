"""Mô-đun tính thang quy đổi pixel/mm theo từng ảnh và đọc EXIF phơi sáng (T5).

Ý tưởng vật lí & đo lường:
- Trên màn hứng vạch laser có đặt hai vạch chuẩn biết trước khoảng cách thật L (mm)
  (ví dụ vạch chia trên thước hoặc hai dấu mực cố định).
- Người dùng chọn 2 điểm P1(x1, y1), P2(x2, y2) trên ảnh và nhập L (mm) =>
  px_per_mm = ||P2 - P1|| / L.
- Khi đo Δy theo mm (Δy_mm = Δy_px / px_per_mm), đường chuẩn theo mm KHÔNG phụ thuộc
  vào khoảng cách đặt điện thoại hay độ phóng đại (zoom) của từng bức ảnh.
- Đọc EXIF (ExposureTime, ISO) bằng Pillow để ghi nhận điều kiện phơi sáng nếu có;
  ảnh không có EXIF thì bỏ qua an toàn, không báo lỗi.
"""
from __future__ import annotations

import io
import math
from dataclasses import dataclass
from typing import Any

from PIL import Image


@dataclass(frozen=True)
class KetQuaThangAnh:
    """Kết quả quy đổi thang pixel/mm từ hai điểm chuẩn trên một ảnh."""

    diem_1: tuple[float, float]
    diem_2: tuple[float, float]
    khoang_cach_px: float
    khoang_cach_mm: float
    px_per_mm: float
    u_px_per_mm: float
    mm_per_px: float


def tinh_thang_tu_hai_diem(
    diem_1: tuple[float, float],
    diem_2: tuple[float, float],
    khoang_cach_mm: float,
    sigma_diem_px: float = 0.5,
    sigma_mm: float = 0.1,
) -> KetQuaThangAnh:
    """Tính hệ số quy đổi `px_per_mm` và bất định từ 2 điểm trên ảnh và khoảng cách thật (mm)."""
    x1, y1 = float(diem_1[0]), float(diem_1[1])
    x2, y2 = float(diem_2[0]), float(diem_2[1])
    L_mm = float(khoang_cach_mm)
    if not (math.isfinite(x1) and math.isfinite(y1) and math.isfinite(x2) and math.isfinite(y2)):
        raise ValueError("Tọa độ hai điểm thang chuẩn không hợp lệ.")
    if not math.isfinite(L_mm) or L_mm <= 0.0:
        raise ValueError("Khoảng cách chuẩn (mm) phải lớn hơn 0.")

    d_px = math.hypot(x2 - x1, y2 - y1)
    if d_px <= 1.0:
        raise ValueError("Hai điểm chọn trên ảnh quá gần nhau (<= 1 px), không tính được thang.")

    px_per_mm = d_px / L_mm
    mm_per_px = L_mm / d_px
    sigma_d_px = math.sqrt(2.0) * max(float(sigma_diem_px), 0.0)
    rel_u = math.hypot(sigma_d_px / d_px, max(float(sigma_mm), 0.0) / L_mm)
    u_px_per_mm = px_per_mm * rel_u

    return KetQuaThangAnh(
        diem_1=(x1, y1),
        diem_2=(x2, y2),
        khoang_cach_px=d_px,
        khoang_cach_mm=L_mm,
        px_per_mm=px_per_mm,
        u_px_per_mm=u_px_per_mm,
        mm_per_px=mm_per_px,
    )


def quy_doi_delta_y_sang_mm(
    delta_y_px: float,
    px_per_mm: float,
    sigma_delta_y_px: float = 0.0,
    u_px_per_mm: float = 0.0,
) -> tuple[float, float]:
    """Quy đổi Δy (px) sang mm kèm truyền sai số bậc 1 theo bất định thang."""
    if not math.isfinite(px_per_mm) or px_per_mm <= 0.0:
        raise ValueError("Hệ số px_per_mm phải lớn hơn 0.")
    if not math.isfinite(delta_y_px):
        raise ValueError("Δy (px) không hợp lệ.")
    dy_mm = float(delta_y_px) / float(px_per_mm)
    u_tu_dy = abs(float(sigma_delta_y_px)) / float(px_per_mm)
    u_tu_thang = (abs(float(delta_y_px)) / (float(px_per_mm) ** 2)) * max(float(u_px_per_mm), 0.0)
    return dy_mm, math.hypot(u_tu_dy, u_tu_thang)


def _dinh_dang_exposure(val: Any) -> tuple[float | None, str]:
    try:
        if hasattr(val, "numerator") and hasattr(val, "denominator"):
            if val.denominator == 0:
                return None, ""
            sec = float(val.numerator) / float(val.denominator)
        elif isinstance(val, (tuple, list)) and len(val) == 2 and float(val[1]) != 0:
            sec = float(val[0]) / float(val[1])
        else:
            sec = float(val)
        if not math.isfinite(sec) or sec <= 0:
            return None, ""
        if sec < 1.0:
            return sec, f"1/{round(1.0 / sec)} s"
        return sec, f"{sec:g} s"
    except Exception:
        return None, ""


def doc_exif_phoi_sang(raw_bytes: bytes) -> dict[str, Any]:
    """Đọc thông tin ExposureTime và ISO từ EXIF ảnh gốc nếu có; thiếu EXIF thì trả {}."""
    if not raw_bytes:
        return {}
    try:
        with Image.open(io.BytesIO(raw_bytes)) as img:
            exif = img.getexif()
            if not exif:
                return {}
            ifd = exif.get_ifd(0x8769) if hasattr(exif, "get_ifd") else {}
            raw_exp = exif.get(33434) or (ifd.get(33434) if ifd else None)
            raw_iso = exif.get(34855) or (ifd.get(34855) if ifd else None)
    except Exception:
        return {}

    ket_qua: dict[str, Any] = {}
    if raw_exp is not None:
        sec, exp_str = _dinh_dang_exposure(raw_exp)
        if sec is not None:
            ket_qua["exposure_time_s"] = sec
            ket_qua["exposure_str"] = exp_str
    if raw_iso is not None:
        try:
            iso_val = raw_iso[0] if isinstance(raw_iso, (tuple, list)) else raw_iso
            iso_int = int(iso_val)
            if iso_int > 0:
                ket_qua["iso"] = iso_int
        except Exception:
            pass
    return ket_qua
