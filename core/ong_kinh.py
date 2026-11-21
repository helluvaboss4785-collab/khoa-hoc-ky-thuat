"""Mô-đun tùy chọn hiệu chuẩn và cảnh báo méo ống kính xuyên tâm (Q6).

Ý tưởng vật lí:
- Ống kính điện thoại (đặc biệt camera góc rộng) có méo xuyên tâm rìa ảnh (hệ số k1):
  điểm càng xa tâm quang học (cx, cy) càng bị kéo cong vào (k1 < 0, méo thùng) hoặc phình ra (k1 > 0, méo gối).
- Nếu một vạch laser nằm gần tâm ảnh còn vạch kia nằm gần mép ảnh, độ lệch Δy = y_mẫu - y_tc
  có thể bị sai hệ thống (khoảng 0,3–0,8 px trong mô phỏng với |k1| = 0,05..0,1).
- Mặc định tính năng tự sửa méo (`cv2.undistort`) TẮT cho tới khi người dùng chụp bộ ảnh bàn cờ
  và hiệu chuẩn riêng cho mã điện thoại (`id_dien_thoai`).
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np


@dataclass(frozen=True)
class ThamSoOngKinh:
    """Thông số nội tại và hệ số méo ống kính chuẩn OpenCV theo từng điện thoại."""

    id_dien_thoai: str
    chieu_rong_px: int
    chieu_cao_px: int
    ma_tran_camera: list[list[float]]  # 3x3 [[fx, 0, cx], [0, fy, cy], [0, 0, 1]]
    he_so_meo: list[float]             # [k1, k2, p1, p2, k3]
    sai_so_tai_chieu_px: float
    so_anh_su_dung: int
    nguon_du_lieu: str = "THUC_TE"
    co_goc_ban_co: tuple[int, int] = (9, 6)
    kich_thuoc_o_mm: float = 20.0


def _ten_file_an_toan(id_dien_thoai: str) -> str:
    ten = re.sub(r"[^a-zA-Z0-9._-]+", "_", str(id_dien_thoai).strip()).strip("._")
    if not ten:
        raise ValueError("id_dien_thoai không hợp lệ hoặc rỗng.")
    return ten


def luu_tham_so_ong_kinh(tham_so: ThamSoOngKinh, thu_muc: str | Path) -> Path:
    """Lưu thông số ống kính ra file `<id_dien_thoai>.json` trong thư mục chỉ định."""
    out_dir = Path(thu_muc)
    out_dir.mkdir(parents=True, exist_ok=True)
    ten = _ten_file_an_toan(tham_so.id_dien_thoai)
    out_path = out_dir / f"{ten}.json"
    out_path.write_text(json.dumps(asdict(tham_so), ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def tai_tham_so_ong_kinh(id_dien_thoai: str, thu_muc: str | Path) -> ThamSoOngKinh | None:
    """Nạp thông số ống kính của `id_dien_thoai` nếu file tồn tại; ngược lại trả `None`."""
    if not id_dien_thoai or not str(id_dien_thoai).strip():
        return None
    ten = _ten_file_an_toan(id_dien_thoai)
    path = Path(thu_muc) / f"{ten}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    co_goc = data.get("co_goc_ban_co", [9, 6])
    return ThamSoOngKinh(
        id_dien_thoai=str(data["id_dien_thoai"]),
        chieu_rong_px=int(data["chieu_rong_px"]),
        chieu_cao_px=int(data["chieu_cao_px"]),
        ma_tran_camera=[[float(v) for v in row] for row in data["ma_tran_camera"]],
        he_so_meo=[float(v) for v in data["he_so_meo"]],
        sai_so_tai_chieu_px=float(data.get("sai_so_tai_chieu_px", 0.0)),
        so_anh_su_dung=int(data.get("so_anh_su_dung", 0)),
        nguon_du_lieu=str(data.get("nguon_du_lieu", "THUC_TE")),
        co_goc_ban_co=(int(co_goc[0]), int(co_goc[1])),
        kich_thuoc_o_mm=float(data.get("kich_thuoc_o_mm", 20.0)),
    )


def hieu_chuan_tu_anh_ban_co(
    danh_sach_anh: list[np.ndarray],
    id_dien_thoai: str,
    co_goc_ban_co: tuple[int, int] = (9, 6),
    kich_thuoc_o_mm: float = 20.0,
    nguon_du_lieu: str = "THUC_TE",
) -> ThamSoOngKinh:
    """Hiệu chuẩn nội tại camera & hệ số méo bằng `cv2.calibrateCamera` từ ảnh bàn cờ."""
    if nguon_du_lieu not in ("THUC_TE", "MO_PHONG"):
        raise ValueError("nguon_du_lieu phải là 'THUC_TE' hoặc 'MO_PHONG'.")
    if not danh_sach_anh:
        raise ValueError("Danh sách ảnh bàn cờ trống.")

    cols, rows = int(co_goc_ban_co[0]), int(co_goc_ban_co[1])
    if cols < 3 or rows < 3:
        raise ValueError("Kích thước góc trong bàn cờ phải >= 3x3.")
    if kich_thuoc_o_mm <= 0:
        raise ValueError("Kích thước ô bàn cờ (mm) phải > 0.")

    objp = np.zeros((cols * rows, 3), np.float32)
    objp[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2) * float(kich_thuoc_o_mm)

    objpoints: list[np.ndarray] = []
    imgpoints: list[np.ndarray] = []
    img_size: tuple[int, int] | None = None
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

    for anh in danh_sach_anh:
        if anh is None or anh.size == 0:
            continue
        gray = cv2.cvtColor(anh, cv2.COLOR_BGR2GRAY) if anh.ndim == 3 else anh
        h, w = gray.shape[:2]
        if img_size is None:
            img_size = (w, h)
        elif img_size != (w, h):
            raise ValueError(f"Mọi ảnh bàn cờ phải cùng kích thước: nhận {(w, h)} khác {img_size}.")

        found, corners = cv2.findChessboardCorners(
            gray,
            (cols, rows),
            cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE,
        )
        if not found:
            continue
        corners_sub = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
        objpoints.append(objp)
        imgpoints.append(corners_sub)

    if img_size is None or len(objpoints) < 3:
        raise ValueError(
            f"Chỉ tìm thấy bàn cờ ở {len(objpoints)} ảnh (cần tối thiểu 3 ảnh rõ đủ {cols}x{rows} góc trong)."
        )

    rms, mtx, dist, _, _ = cv2.calibrateCamera(
        objpoints, imgpoints, img_size, None, None, flags=cv2.CALIB_FIX_K3
    )
    return ThamSoOngKinh(
        id_dien_thoai=str(id_dien_thoai).strip(),
        chieu_rong_px=int(img_size[0]),
        chieu_cao_px=int(img_size[1]),
        ma_tran_camera=[[float(v) for v in row] for row in mtx.tolist()],
        he_so_meo=[float(v) for v in dist.ravel().tolist()],
        sai_so_tai_chieu_px=float(rms),
        so_anh_su_dung=len(objpoints),
        nguon_du_lieu=nguon_du_lieu,
        co_goc_ban_co=(cols, rows),
        kich_thuoc_o_mm=float(kich_thuoc_o_mm),
    )


def sua_meo_anh(anh: np.ndarray, tham_so: ThamSoOngKinh) -> np.ndarray:
    """Khử méo xuyên tâm ảnh chụp bằng `cv2.undistort` với ma trận camera đã hiệu chuẩn."""
    if anh is None or anh.size == 0:
        raise ValueError("Ảnh đầu vào rỗng, không thể sửa méo.")
    h, w = anh.shape[:2]
    K = np.array(tham_so.ma_tran_camera, dtype=np.float64)
    if (w != tham_so.chieu_rong_px or h != tham_so.chieu_cao_px) and tham_so.chieu_rong_px > 0 and tham_so.chieu_cao_px > 0:
        sx = float(w) / float(tham_so.chieu_rong_px)
        sy = float(h) / float(tham_so.chieu_cao_px)
        K = K.copy()
        K[0, 0] *= sx
        K[0, 2] *= sx
        K[1, 1] *= sy
        K[1, 2] *= sy
    dist = np.array(tham_so.he_so_meo, dtype=np.float64)
    return cv2.undistort(anh, K, dist)


def kiem_tra_vung_meo_ong_kinh(
    h_img: int,
    y_tc: float,
    y_mau: float,
    nguong_lech_tam_ti_le: float = 0.30,
    he_so_meo_k1: float | None = None,
    chua_sua_meo: bool = True,
    w_img: int | None = None,
    co_tham_so_ong_kinh: bool = False,
) -> dict[str, Any]:
    """Kiểm tra hai vạch có nằm ở vùng rìa dễ méo ống kính hay không (R3: chỉ cảnh báo khi có k1/hiệu chuẩn)."""
    cy = max(float(h_img) / 2.0, 1.0)
    ti_le_tc = abs(float(y_tc) - cy) / cy
    ti_le_mau = abs(float(y_mau) - cy) / cy
    ti_le_max = max(ti_le_tc, ti_le_mau)
    vuot_nguong = bool(chua_sua_meo and math.isfinite(ti_le_max) and ti_le_max > float(nguong_lech_tam_ti_le))

    if not vuot_nguong:
        return {
            "canh_bao_meo": False,
            "la_thong_tin_bo_sung": False,
            "ti_le_lech_tam_max": float(ti_le_max),
            "can_tren_sai_so_px": None,
            "cap": None,
            "noi_dung": "",
        }

    co_k1 = he_so_meo_k1 is not None and math.isfinite(float(he_so_meo_k1))
    if not co_k1 and not co_tham_so_ong_kinh:
        return {
            "canh_bao_meo": False,
            "la_thong_tin_bo_sung": True,
            "ti_le_lech_tam_max": float(ti_le_max),
            "can_tren_sai_so_px": None,
            "cap": "thong_tin",
            "noi_dung": (
                f"Vạch laser nằm khá xa tâm ảnh (lệch tâm đứng {ti_le_max * 100:.0f}% > {nguong_lech_tam_ti_le * 100:.0f}%): "
                "khu vực rìa dễ bị méo ống kính (chưa khai báo k1 và chưa có hiệu chuẩn ống kính theo id_dien_thoai)."
            ),
        }

    if not co_k1:
        return {
            "canh_bao_meo": True,
            "la_thong_tin_bo_sung": False,
            "ti_le_lech_tam_max": float(ti_le_max),
            "can_tren_sai_so_px": None,
            "cap": "can_than",
            "noi_dung": (
                f"Vạch nằm ở vùng rìa dễ méo ống kính (lệch tâm {ti_le_max * 100:.0f}% > {nguong_lech_tam_ti_le * 100:.0f}%) "
                "và điện thoại đã có thông số hiệu chuẩn ống kính nhưng đang tắt tự sửa méo."
            ),
        }

    k1_abs = abs(float(he_so_meo_k1))
    half_w = float(w_img) / 2.0 if (w_img is not None and w_img > 0) else cy * 1.333
    r_diag2 = max(half_w**2 + cy**2, 1.0)
    # Cận trên lệch xuyên tâm tính theo rìa ngang 0.5*half_w đặc trưng của đoạn vạch laser
    r2_tc = ((float(y_tc) - cy) ** 2 + (0.5 * half_w) ** 2) / r_diag2
    r2_m = ((float(y_mau) - cy) ** 2 + (0.5 * half_w) ** 2) / r_diag2
    can_tren_px = float(k1_abs * abs((float(y_mau) - cy) * r2_m - (float(y_tc) - cy) * r2_tc))
    return {
        "canh_bao_meo": True,
        "la_thong_tin_bo_sung": False,
        "ti_le_lech_tam_max": float(ti_le_max),
        "can_tren_sai_so_px": can_tren_px,
        "cap": "can_than",
        "noi_dung": (
            f"Vạch nằm ở vùng rìa dễ méo ống kính (lệch tâm {ti_le_max * 100:.0f}% > {nguong_lech_tam_ti_le * 100:.0f}%, "
            f"k1 = {float(he_so_meo_k1):+g}): cận trên sai lệch hệ thống ước lượng ≈ ±{can_tren_px:.2f} px. "
            "Có thể cân nhắc hiệu chuẩn ống kính bằng bàn cờ."
        ),
    }
