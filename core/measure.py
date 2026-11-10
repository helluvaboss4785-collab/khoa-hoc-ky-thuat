"""Mô-đun đo độ lệch vi sai Δy và chỉ số độ đục từ ảnh (Cột mốc 2).

Vật lí & Nguyên lí đo vi sai:
- Trên màn hứng có 2 đoạn vạch sáng:
  1. Vạch tham chiếu (ngăn nước cất đóng kín): đóng vai trò gốc quy chiếu quang học.
  2. Vạch mẫu (ngăn nước cần đo độ mặn).
- Tín hiệu đo: Δy = y_mau(x_ref) − y_thamchieu(x_ref) (pixel).
- Lợi ích của đo vi sai:
  * Khi laser bị rung cơ học hoặc nhiệt làm trôi chùm tia chung: cả hai vạch cùng dịch
    chuyển một lượng δy_drift, nên Δy = (y_mau + δy_drift) - (y_tc + δy_drift) = y_mau - y_tc.
  * Tương tự, độ rung lắc của điện thoại chụp ảnh hoặc độ nghiêng cuvet bị triệt tiêu ở bậc 1.
- Chỉ số độ đục tương đối (Turbidity Index):
  * Khi nước đục, các hạt lơ lửng gây tán xạ ánh sáng (Tyndall / Mie), làm vạch mẫu
    bị mở rộng (FWHM tăng) và suy giảm cường độ đỉnh trực xạ (theo định luật Beer-Lambert).
  * LƯU Ý QUAN TRỌNG: Chỉ số này là GIÁ TRỊ TƯƠNG ĐỐI (thang 0.0 - 1.0),
    TUYỆT ĐỐI KHÔNG QUY RA ĐƠN VỊ NTU KHI CHƯA CÓ ĐƯỜNG CHUẨN THỰC NGHIỆM VỚI DUNG DỊCH CHUẨN FORMAZIN.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import cv2
import numpy as np

from core.spot import (
    KetQuaUocLuongVach,
    uoc_luong_duong_vach,
)


@dataclass(frozen=True)
class ChatLuongAnh:
    """Đánh giá chất lượng quang học của ảnh chụp vạch laser."""

    hop_le: bool                 # Ảnh có đủ điều kiện để lấy kết quả đo tin cậy không
    bao_hoa: bool                # Cờ báo vạch bị bão hòa (cháy sáng, pixel = 255)
    ti_le_bao_hoa: float         # Tỉ lệ pixel bão hòa trong vùng sáng lõi vạch
    qua_mo: bool                 # Cờ báo vạch quá mờ (tín hiệu yếu)
    snr: float                   # Tỉ số tín hiệu trên nhiễu ước lượng (Peak / Noise_Std)
    nhoe: bool                   # Cờ báo vạch bị nhòe/biến dạng bất thường
    fwhm_mau: float              # FWHM vạch mẫu (px)
    fwhm_tc: float               # FWHM vạch tham chiếu (px)
    canh_bao: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class KetQuaDoDeltaY:
    """Kết quả đo vi sai Δy và độ đục từ một khung hình ảnh."""

    delta_y_px: float                    # Δy = y_mau - y_tc tại x_ref (pixel)
    sai_so_delta_y_px: float             # Bất định ghép sai số chuẩn: sqrt(σ_mau² + σ_tc²)
    x_ref: float                         # Cột tham chiếu thực hiện phép đo vi sai
    vach_tham_chieu: KetQuaUocLuongVach  # Kết quả chi tiết vạch tham chiếu
    vach_mau: KetQuaUocLuongVach         # Kết quả chi tiết vạch mẫu
    chi_so_do_duc_tuong_doi: float       # Chỉ số độ đục tương đối (0.0: trong suốt, 1.0: rất đục)
    chat_luong: ChatLuongAnh             # Đánh giá chất lượng và cảnh báo lỗi
    anh_danh_dau: np.ndarray | None = None  # Ảnh đã vẽ vị trí vạch và tâm để hiển thị UI


@dataclass(frozen=True)
class KetQuaDoDaKhungHinh:
    """Kết quả đo tổng hợp từ chuỗi nhiều khung hình (video hoặc nhiều ảnh chụp)."""

    delta_y_trung_vi_px: float           # Trung vị của Δy qua các khung hình (chống outlier)
    sai_so_thong_ke_px: float            # Sai số chuẩn thực nghiệm: 1.4826 * MAD / sqrt(N)
    so_khung_hop_le: int                 # Số khung đạt tiêu chuẩn chất lượng
    tong_so_khung: int                   # Tổng số khung hình đã phân tích
    danh_sach_delta_y: list[float]       # Chuỗi giá trị Δy từng khung
    chi_so_do_duc_tb: float              # Trung bình chỉ số độ đục
    chat_luong_chung: ChatLuongAnh       # Đánh giá chất lượng chung


def chuyen_anh_xam(anh: np.ndarray) -> np.ndarray:
    """Chuyển ảnh sang mức xám 8-bit chuẩn."""
    if anh.ndim == 2:
        return anh.astype(np.uint8) if anh.dtype != np.uint8 else anh
    if anh.ndim == 3:
        if anh.shape[2] == 4:  # RGBA
            return cv2.cvtColor(anh, cv2.COLOR_RGBA2GRAY)
        return cv2.cvtColor(anh, cv2.COLOR_BGR2GRAY)
    raise ValueError(f"Định dạng ảnh không hợp lệ: shape={anh.shape}")


def kiem_tra_chat_luong_vung(
    anh_xam: np.ndarray,
    roi_tc: tuple[int, int, int, int],
    roi_mau: tuple[int, int, int, int],
    nguong_bao_hoa: int = 250,
    ti_le_bao_hoa_toi_da: float = 0.02,
    snr_toi_thieu: float = 3.0,
    fwhm_toi_thieu: float = 1.2,
    fwhm_toi_da: float = 65.0,
) -> tuple[ChatLuongAnh, float, float]:
    """Kiểm tra và chấm điểm chất lượng ảnh chụp 2 vạch."""
    canh_bao: list[str] = []

    y1_tc, y2_tc, x1_tc, x2_tc = roi_tc
    y1_m, y2_m, x1_m, x2_m = roi_mau

    vung_tc = anh_xam[y1_tc:y2_tc, x1_tc:x2_tc]
    vung_m = anh_xam[y1_m:y2_m, x1_m:x2_m]

    # 1. Kiểm tra bão hòa sáng (clipping)
    px_bao_hoa_tc = np.count_nonzero(vung_tc >= nguong_bao_hoa)
    px_bao_hoa_m = np.count_nonzero(vung_m >= nguong_bao_hoa)
    tong_px = vung_tc.size + vung_m.size
    ti_le_bh = float(px_bao_hoa_tc + px_bao_hoa_m) / max(tong_px, 1)

    co_bao_hoa = ti_le_bh > ti_le_bao_hoa_toi_da
    if co_bao_hoa:
        canh_bao.append(
            f"Vạch sáng bị bão hòa (cháy sáng {ti_le_bh*100:.1f}% pixel > {nguong_bao_hoa}). "
            "Cần giảm phơi sáng máy ảnh hoặc giảm công suất laser để tránh bẹt đỉnh."
        )

    # 2. Kiểm tra tín hiệu / nhiễu (SNR)
    nen_tc = float(np.percentile(vung_tc, 10))
    dinh_tc = float(np.percentile(vung_tc, 99))
    std_nen = float(np.std(vung_tc[vung_tc <= nen_tc + 5])) if np.any(vung_tc <= nen_tc + 5) else 1.0
    std_nen = max(std_nen, 0.5)

    snr_uoc_luong = (dinh_tc - nen_tc) / std_nen
    co_qua_mo = bool(snr_uoc_luong < snr_toi_thieu or (dinh_tc - nen_tc) < 15.0)
    if co_qua_mo:
        canh_bao.append(
            f"Vạch sáng quá mờ (SNR={snr_uoc_luong:.1f} < {snr_toi_thieu} hoặc tương phản yếu). "
            "Cần che bớt ánh sáng môi trường hoặc tăng sáng laser."
        )

    hop_le = not (co_bao_hoa or co_qua_mo)

    # FWHM sẽ được cập nhật sau khi khớp
    chat_luong = ChatLuongAnh(
        hop_le=hop_le,
        bao_hoa=co_bao_hoa,
        ti_le_bao_hoa=ti_le_bh,
        qua_mo=co_qua_mo,
        snr=snr_uoc_luong,
        nhoe=False,
        fwhm_mau=0.0,
        fwhm_tc=0.0,
        canh_bao=canh_bao,
    )
    return chat_luong, nen_tc, dinh_tc


def tinh_chi_so_do_duc_tuong_doi(
    fwhm_tc: float,
    fwhm_mau: float,
    amp_tc: float,
    amp_mau: float,
) -> float:
    """Tính chỉ số độ đục tương đối (0.0 - 1.0) từ sự biến dạng hình học của vạch laser.

    Vật lí:
    - Nước cất (tham chiếu) hầu như không tán xạ ánh sáng đỏ (650 nm), vạch sắc nét.
    - Nước mẫu chứa chất keo/hạt lơ lửng:
      * Tán xạ Mie/Rayleigh làm chùm tia phình to -> fwhm_mau > fwhm_tc.
      * Tán xạ và hấp thụ làm suy giảm biên độ trực xạ -> amp_mau < amp_tc.

    CẢNH BÁO QUAN TRỌNG:
    Đây là thước đo tương đối (relative proxy), KHÔNG PHẢI đơn vị độ đục chuẩn NTU.
    Học sinh cần nêu rõ trong báo cáo khoa học: muốn đổi sang NTU cần chuẩn hóa với
    dung dịch Formazin chuẩn từ 0 đến 400 NTU.
    """
    if fwhm_tc <= 0 or amp_tc <= 0:
        return 0.0

    # Thành phần 1: độ mở rộng vạch do tán xạ
    ty_le_fwhm = max((fwhm_mau - fwhm_tc) / fwhm_tc, 0.0)
    # Chuẩn hóa mềm (tanh) để giới hạn trong [0, 1]
    phan_mo_rong = math.tanh(ty_le_fwhm * 1.5)

    # Thành phần 2: độ suy giảm cường độ trực xạ (Beer-Lambert suy biến)
    ty_le_suy_giam = max(1.0 - (amp_mau / amp_tc), 0.0)

    # Kết hợp bình quyền 2 hiệu ứng
    chi_so = 0.5 * phan_mo_rong + 0.5 * ty_le_suy_giam
    return float(np.clip(chi_so, 0.0, 1.0))


def tu_dong_tim_roi_hai_vach(
    anh_xam: np.ndarray,
    ty_le_sang: float = 0.4,
) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    """Tự động phát hiện 2 vùng quan tâm (ROI) chứa 2 vạch sáng trên ảnh.

    Hỗ trợ cả 2 cấu hình bố trí quang học:
    1. Bố trí ngang (Trái - Phải): Ngăn tham chiếu bên trái, ngăn mẫu bên phải.
       Khi Δy = 0 hai vạch nằm thẳng hàng ngang; khi S > 0 vạch mẫu lệch đứng.
    2. Bố trí đứng (Trên - Dưới): Vạch tham chiếu ở trên, vạch mẫu ở dưới.

    Trả về:
        (roi_tham_chieu, roi_mau)
    """
    h, w = anh_xam.shape
    x_mid = w // 2

    # Không che/xóa vùng nào của ảnh: ảnh thật có thể có vạch ở bất kì đâu.
    blur = cv2.GaussianBlur(anh_xam, (5, 5), 0)
    nguong_val = float(np.percentile(blur, 100.0 * (1.0 - ty_le_sang * 0.08)))
    nguong_val = max(nguong_val, 30.0)

    _, thresh = cv2.threshold(blur, int(nguong_val), 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 3))
    thresh_closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(thresh_closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    ds_vach = []
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        dien_tich = cv2.contourArea(c)
        if cw >= 20 and (cw / max(ch, 1)) >= 1.2 and dien_tich > 80:
            ds_vach.append((x, y, cw, ch, dien_tich))

    if len(ds_vach) >= 2:
        # Sắp xếp theo diện tích lớn nhất
        ds_vach.sort(key=lambda item: item[4], reverse=True)
        v1, v2 = ds_vach[0], ds_vach[1]

        # Kiểm tra bố trí Trái - Phải hay Trên - Dưới
        x1_center = v1[0] + v1[2] / 2.0
        x2_center = v2[0] + v2[2] / 2.0

        if abs(x1_center - x2_center) > w * 0.2:
            # Bố trí Trái - Phải: Vạch bên trái là tham chiếu, bên phải là mẫu
            v_trai = v1 if x1_center < x2_center else v2
            v_phai = v2 if x1_center < x2_center else v1
            
            def tao_roi_ngang(x: int, y: int, cw: int, ch: int) -> tuple[int, int, int, int]:
                y_min = max(0, y - 25)
                y_max = min(h, y + ch + 25)
                x_min = max(0, x - 5)
                x_max = min(w, x + cw + 5)
                return (y_min, y_max, x_min, x_max)

            return tao_roi_ngang(*v_trai[:4]), tao_roi_ngang(*v_phai[:4])
        else:
            # Bố trí Trên - Dưới: Vạch trên (y nhỏ) là tham chiếu, vạch dưới là mẫu
            if v1[1] > v2[1]:
                v1, v2 = v2, v1

            def tao_roi_doc(x: int, y: int, cw: int, ch: int) -> tuple[int, int, int, int]:
                y_min = max(0, y - 15)
                y_max = min(h, y + ch + 15)
                x_min = max(0, x - 5)
                x_max = min(w, x + cw + 5)
                return (y_min, y_max, x_min, x_max)

            return tao_roi_doc(*v1[:4]), tao_roi_doc(*v2[:4])

    elif len(ds_vach) == 1:
        # Trường hợp 1 dải vạch dài duy nhất trải ngang (đặc trưng khi S = 0 trên cấu trúc trái-phải)
        x, y, cw, ch, _ = ds_vach[0]
        y_min = max(0, y - 25)
        y_max = min(h, y + ch + 25)
        # Tách làm 2 nửa trái và phải quanh x_mid
        roi_trai = (y_min, y_max, max(0, x), min(w, x_mid - 10))
        roi_phai = (y_min, y_max, max(0, x_mid + 10), min(w, x + cw))
        return roi_trai, roi_phai

    raise ValueError(
        "Không tự động tìm thấy vạch sáng rõ ràng. "
        "Hãy kéo chọn thủ công 2 vùng ROI vạch tham chiếu và vạch mẫu trên giao diện."
    )


def ve_anh_ket_qua_danh_dau(
    anh_goc: np.ndarray,
    vach_tc: KetQuaUocLuongVach,
    vach_mau: KetQuaUocLuongVach,
    delta_y_px: float,
    x_ref: float,
) -> np.ndarray:
    """Vẽ minh họa vị trí đường tâm hai vạch và khoảng lệch Δy lên ảnh để kiểm chứng trực quan."""
    if anh_goc.ndim == 2:
        anh_out = cv2.cvtColor(anh_goc, cv2.COLOR_GRAY2BGR)
    else:
        anh_out = anh_goc.copy()

    h, w = anh_out.shape[:2]

    # Vẽ đường thẳng vạch tham chiếu (màu xanh lá BGR: 0, 255, 0)
    x_dau = 0
    x_cuoi = w - 1
    y_tc_0 = int(round(vach_tc.do_doc_a * x_dau + vach_tc.he_so_b))
    y_tc_1 = int(round(vach_tc.do_doc_a * x_cuoi + vach_tc.he_so_b))
    cv2.line(anh_out, (x_dau, y_tc_0), (x_cuoi, y_tc_1), (0, 255, 0), 1, cv2.LINE_AA)

    # Vẽ đường thẳng vạch mẫu (màu đỏ cam BGR: 0, 140, 255)
    y_m_0 = int(round(vach_mau.do_doc_a * x_dau + vach_mau.he_so_b))
    y_m_1 = int(round(vach_mau.do_doc_a * x_cuoi + vach_mau.he_so_b))
    cv2.line(anh_out, (x_dau, y_m_0), (x_cuoi, y_m_1), (0, 140, 255), 1, cv2.LINE_AA)

    # Vẽ đoạn đo vi sai Δy tại cột tham chiếu x_ref (màu vàng chanh BGR: 0, 255, 255)
    ix_ref = int(round(x_ref))
    iy_tc = int(round(vach_tc.y_tam))
    iy_m = int(round(vach_mau.y_tam))

    cv2.circle(anh_out, (ix_ref, iy_tc), 3, (0, 255, 0), -1)
    cv2.circle(anh_out, (ix_ref, iy_m), 3, (0, 140, 255), -1)
    cv2.line(anh_out, (ix_ref, iy_tc), (ix_ref, iy_m), (0, 255, 255), 2, cv2.LINE_AA)

    # Chú thích văn bản lên ảnh
    nhan = f"Delta y = {delta_y_px:.2f} px (x_ref={ix_ref})"
    cv2.putText(
        anh_out,
        nhan,
        (max(10, ix_ref - 120), min(h - 15, max(30, iy_tc - 15))),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )
    return anh_out


def do_delta_y_tu_anh(
    anh: np.ndarray,
    roi_tham_chieu: tuple[int, int, int, int] | None = None,
    roi_mau: tuple[int, int, int, int] | None = None,
    x_ref: float | None = None,
    phuong_phap: Literal["gauss", "centroid"] = "gauss",
    buoc_nhay_cot: int = 2,
    nguong_bao_hoa: int = 250,
    ti_le_bao_hoa_toi_da: float = 0.02,
    snr_toi_thieu: float = 3.0,
    tao_anh_ve: bool = True,
) -> KetQuaDoDeltaY:
    """Đo độ lệch vi sai Δy và chỉ số độ đục từ một ảnh chụp.

    Args:
        anh: Mảng ảnh BGR hoặc xám.
        roi_tham_chieu: (y1, y2, x1, x2) của vạch tham chiếu. Nếu None sẽ tự phát hiện.
        roi_mau: (y1, y2, x1, x2) của vạch mẫu. Nếu None sẽ tự phát hiện.
        x_ref: Cột tham chiếu. Nếu None sẽ lấy giao điểm tâm của 2 vạch.
        phuong_phap: "gauss" hoặc "centroid".
        nguong_bao_hoa: Mức xám coi là bão hòa.
        ti_le_bao_hoa_toi_da: Ngưỡng tỉ lệ bão hòa cho phép.
        snr_toi_thieu: Tỉ số SNR tối thiểu.
        tao_anh_ve: Có sinh ảnh đánh dấu trực quan hay không.

    Returns:
        KetQuaDoDeltaY chứa Δy, sai số chuẩn, chỉ số độ đục và cờ chất lượng.
    """
    anh_xam = chuyen_anh_xam(anh)

    # 1. Xác định ROI nếu chưa có
    if roi_tham_chieu is None or roi_mau is None:
        roi_1, roi_2 = tu_dong_tim_roi_hai_vach(anh_xam)
        # Giả định quy ước: vạch trên là tham chiếu, vạch dưới là mẫu (hoặc ngược lại)
        # Mặc định gán vạch trên là tham chiếu nếu người dùng chưa chỉ định
        roi_tham_chieu = roi_1 if roi_tham_chieu is None else roi_tham_chieu
        roi_mau = roi_2 if roi_mau is None else roi_mau

    # 2. Đánh giá chất lượng sơ bộ vùng ảnh
    chat_luong_khoi_tao, _, _ = kiem_tra_chat_luong_vung(
        anh_xam,
        roi_tham_chieu,
        roi_mau,
        nguong_bao_hoa=nguong_bao_hoa,
        ti_le_bao_hoa_toi_da=ti_le_bao_hoa_toi_da,
        snr_toi_thieu=snr_toi_thieu,
    )

    # 3. Xác định cột tham chiếu x_ref chung tối ưu
    y1_tc, y2_tc, x1_tc, x2_tc = roi_tham_chieu
    y1_m, y2_m, x1_m, x2_m = roi_mau

    giao_x1 = max(x1_tc, x1_m)
    giao_x2 = min(x2_tc, x2_m)
    if giao_x1 >= giao_x2:
        # Nếu hai ROI không giao nhau theo trục x, lấy trung điểm tổng
        x_ref_tinh = (min(x1_tc, x1_m) + max(x2_tc, x2_m)) / 2.0
    else:
        x_ref_tinh = (giao_x1 + giao_x2) / 2.0

    if x_ref is not None:
        x_ref_tinh = x_ref

    # 4. Trích xuất và ước lượng từng vạch
    anh_roi_tc = anh_xam[y1_tc:y2_tc, x1_tc:x2_tc]
    anh_roi_m = anh_xam[y1_m:y2_m, x1_m:x2_m]

    try:
        vach_tc = uoc_luong_duong_vach(
            anh_roi_tc,
            x_offset=x1_tc,
            y_offset=y1_tc,
            x_ref=x_ref_tinh,
            phuong_phap=phuong_phap,
            buoc_nhay_cot=buoc_nhay_cot,
        )
        vach_m = uoc_luong_duong_vach(
            anh_roi_m,
            x_offset=x1_m,
            y_offset=y1_m,
            x_ref=x_ref_tinh,
            phuong_phap=phuong_phap,
            buoc_nhay_cot=buoc_nhay_cot,
        )
    except ValueError as e:
        # Nếu không đủ số cột đạt chuẩn để khớp vạch (ảnh quá mờ hoặc nhiễu nặng)
        canh_bao_loi = list(chat_luong_khoi_tao.canh_bao)
        canh_bao_loi.append(f"Không thể định vị vạch: {e}")
        chat_luong_loi = ChatLuongAnh(
            hop_le=False,
            bao_hoa=chat_luong_khoi_tao.bao_hoa,
            ti_le_bao_hoa=chat_luong_khoi_tao.ti_le_bao_hoa,
            qua_mo=True,
            snr=chat_luong_khoi_tao.snr,
            nhoe=True,
            fwhm_mau=0.0,
            fwhm_tc=0.0,
            canh_bao=canh_bao_loi,
        )
        # Tạo kết quả rỗng giả lập
        vach_rong = KetQuaUocLuongVach(
            x_ref=x_ref_tinh,
            y_tam=float("nan"),
            sai_so_y=float("inf"),
            do_doc_a=0.0,
            he_so_b=0.0,
            fwhm_trung_binh=0.0,
            cuong_do_dinh_tb=0.0,
            r2_trung_binh=0.0,
            so_cot_hop_le=0,
            so_cot_tong=0,
            phuong_phap=phuong_phap,
        )
        return KetQuaDoDeltaY(
            delta_y_px=float("nan"),
            sai_so_delta_y_px=float("inf"),
            x_ref=x_ref_tinh,
            vach_tham_chieu=vach_rong,
            vach_mau=vach_rong,
            chi_so_do_duc_tuong_doi=0.0,
            chat_luong=chat_luong_loi,
            anh_danh_dau=anh if tao_anh_ve else None,
        )

    # 5. Tính tín hiệu vi sai Δy và bất định ghép sai số chuẩn
    # Tín hiệu vật lí: Δy = y_mau - y_tc
    delta_y = float(vach_m.y_tam - vach_tc.y_tam)
    sai_so_delta_y = float(math.sqrt(vach_m.sai_so_y**2 + vach_tc.sai_so_y**2))

    # 6. Tính chỉ số độ đục tương đối
    chi_so_do_duc = tinh_chi_so_do_duc_tuong_doi(
        fwhm_tc=vach_tc.fwhm_trung_binh,
        fwhm_mau=vach_m.fwhm_trung_binh,
        amp_tc=vach_tc.cuong_do_dinh_tb,
        amp_mau=vach_m.cuong_do_dinh_tb,
    )

    # 7. Cập nhật cảnh báo độ nhòe và hoàn thiện đối tượng chất lượng
    canh_bao_final = list(chat_luong_khoi_tao.canh_bao)
    co_nhoe = bool(vach_m.fwhm_trung_binh > 50.0 or vach_tc.fwhm_trung_binh > 50.0)
    if co_nhoe:
        canh_bao_final.append(
            f"Vạch bị nhòe lớn (FWHM mẫu = {vach_m.fwhm_trung_binh:.1f} px, FWHM tc = {vach_tc.fwhm_trung_binh:.1f} px). "
            "Cần kiểm tra lại hội tụ của ống kính hoặc mẫu quá đục làm mất biên dạng vạch."
        )

    chat_luong_final = ChatLuongAnh(
        hop_le=bool(chat_luong_khoi_tao.hop_le and not co_nhoe),
        bao_hoa=chat_luong_khoi_tao.bao_hoa,
        ti_le_bao_hoa=chat_luong_khoi_tao.ti_le_bao_hoa,
        qua_mo=chat_luong_khoi_tao.qua_mo,
        snr=chat_luong_khoi_tao.snr,
        nhoe=co_nhoe,
        fwhm_mau=vach_m.fwhm_trung_binh,
        fwhm_tc=vach_tc.fwhm_trung_binh,
        canh_bao=canh_bao_final,
    )

    # 8. Sinh ảnh vẽ kết quả kiểm chứng
    anh_ve = None
    if tao_anh_ve:
        anh_ve = ve_anh_ket_qua_danh_dau(anh, vach_tc, vach_m, delta_y, x_ref_tinh)

    return KetQuaDoDeltaY(
        delta_y_px=delta_y,
        sai_so_delta_y_px=sai_so_delta_y,
        x_ref=x_ref_tinh,
        vach_tham_chieu=vach_tc,
        vach_mau=vach_m,
        chi_so_do_duc_tuong_doi=chi_so_do_duc,
        chat_luong=chat_luong_final,
        anh_danh_dau=anh_ve,
    )


def do_delta_y_da_khung_hinh(
    danh_sach_anh: list[np.ndarray],
    roi_tham_chieu: tuple[int, int, int, int] | None = None,
    roi_mau: tuple[int, int, int, int] | None = None,
    phuong_phap: Literal["gauss", "centroid"] = "gauss",
) -> KetQuaDoDaKhungHinh:
    """Xử lí chuỗi nhiều khung hình (video / multi-shot), lấy trung vị và độ phân tán.

    Giảm sai số ngẫu nhiên do nhiễu sensor hoặc rung động cơ học tạm thời.
    """
    if not danh_sach_anh:
        raise ValueError("Danh sách khung hình trống")

    ds_delta_y: list[float] = []
    ds_do_duc: list[float] = []
    ds_chat_luong: list[ChatLuongAnh] = []

    for img in danh_sach_anh:
        try:
            kq = do_delta_y_tu_anh(
                img,
                roi_tham_chieu=roi_tham_chieu,
                roi_mau=roi_mau,
                phuong_phap=phuong_phap,
                tao_anh_ve=False,
            )
            ds_delta_y.append(kq.delta_y_px)
            ds_do_duc.append(kq.chi_so_do_duc_tuong_doi)
            ds_chat_luong.append(kq.chat_luong)
        except Exception:
            continue

    tong_khung = len(danh_sach_anh)
    so_hop_le = len(ds_delta_y)

    if so_hop_le == 0:
        raise ValueError("Tất cả các khung hình đều bị lỗi hoặc không đo được")

    arr_dy = np.array(ds_delta_y, dtype=float)
    trung_vi = float(np.median(arr_dy))

    # Tính MAD (Median Absolute Deviation) để ước lượng độ phân tán bền vững (robust sigma)
    # sigma ~ 1.4826 * MAD
    mad = float(np.median(np.abs(arr_dy - trung_vi)))
    robust_sigma = 1.4826 * mad
    sai_so_thong_ke = float(robust_sigma / math.sqrt(so_hop_le))

    # Lấy chất lượng của khung hình gần nhất hoặc tổng hợp
    chat_luong_tb = ds_chat_luong[-1]

    return KetQuaDoDaKhungHinh(
        delta_y_trung_vi_px=trung_vi,
        sai_so_thong_ke_px=sai_so_thong_ke,
        so_khung_hop_le=so_hop_le,
        tong_so_khung=tong_khung,
        danh_sach_delta_y=ds_delta_y,
        chi_so_do_duc_tb=float(np.mean(ds_do_duc)),
        chat_luong_chung=chat_luong_tb,
    )
