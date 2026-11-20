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
from scipy.optimize import curve_fit

from core.ong_kinh import ThamSoOngKinh, kiem_tra_vung_meo_ong_kinh, sua_meo_anh
from core.spot import (
    KetQuaUocLuongVach,
    uoc_luong_duong_vach,
)


class AnhKhongHopLeError(ValueError):
    """Ảnh đầu vào rỗng, sai định dạng hoặc không giải mã được."""


class KhongTimThayVachError(ValueError):
    """Không tự động tìm thấy đủ 2 vạch laser rõ ràng trên ảnh."""


@dataclass(frozen=True)
class ChatLuongAnh:
    """Đánh giá chất lượng quang học của ảnh chụp vạch laser."""

    hop_le: bool                 # Ảnh có đủ điều kiện để lấy kết quả đo tin cậy không
    bao_hoa: bool                # Cờ báo vạch bị bão hòa nghiêm trọng / bẹt đỉnh thật (không hợp lệ)
    ti_le_bao_hoa: float         # Tỉ lệ cột có đỉnh >= ngưỡng bão hòa trên các cột có tín hiệu
    qua_mo: bool                 # Cờ báo vạch quá mờ (tín hiệu yếu)
    snr: float                   # Tỉ số tín hiệu trên nhiễu ước lượng (Peak / Noise_Std)
    nhoe: bool                   # Cờ báo vạch bị nhòe/biến dạng bất thường
    fwhm_mau: float              # FWHM vạch mẫu (px)
    fwhm_tc: float               # FWHM vạch tham chiếu (px)
    canh_bao: list[str] = field(default_factory=list)
    kenh_bao_hoa: list[str] = field(default_factory=list)
    co_dom_bao_hoa_cuc_bo: bool = False
    so_cot_bao_hoa_lien_tiep_max: int = 0
    canh_bao_chi_tiet: list[dict[str, str]] = field(default_factory=list)
    nen_khong_deu: bool = False
    bien_thien_nen: float = 0.0
    canh_bao_meo_ong_kinh: bool = False


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
    kenh_su_dung: str = "xam_2d"         # Kênh màu đã trích xuất để định vị vạch ("R"|"G"|"B"|"xam"|"xam_2d")


@dataclass(frozen=True)
class KetQuaDoDaKhungHinh:
    """Kết quả đo tổng hợp từ chuỗi nhiều khung hình (video hoặc nhiều ảnh chụp)."""

    delta_y_trung_vi_px: float           # Trung vị của Δy qua các khung hình (chống outlier)
    sai_so_thong_ke_px: float            # Sai số chuẩn thực nghiệm: 1.4826 * MAD / sqrt(N)
    so_khung_hop_le: int                 # Số khung đạt tiêu chuẩn chất lượng
    tong_so_khung: int                   # Tổng số khung hình đã phân tích
    danh_sach_delta_y: list[float]       # Chuỗi giá trị Δy từng khung
    chi_so_do_duc_tb: float              # Trung bình chỉ số độ đục
    chat_luong_chung: ChatLuongAnh       # Đánh giá chất lượng chung (xấu nhất trên các khung)
    khung_loi: list[tuple[int, str]] = field(default_factory=list)
    do_doc_troi_px_moi_khung: float = 0.0
    sai_so_do_doc_troi: float = 0.0
    canh_bao_troi_theo_thoi_gian: bool = False
    canh_bao_dao_dong_phoi_sang: bool = False
    canh_bao_da_khung: list[str] = field(default_factory=list)
    chi_so_khung_hop_le: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class KetQuaCanBangNhiet:
    """Kết quả khớp đường tiến tới cân bằng nhiệt Δy(t) = Δy∞ + A·exp(−t/τ) (Q5)."""

    tau_s: float | None
    u_tau_s: float | None
    delta_y_vo_cuc_px: float
    u_delta_y_vo_cuc_px: float
    bien_do_A_px: float
    do_doc_con_lai_px_moi_phut: float
    da_on_dinh: bool
    nguong_px_moi_phut: float
    mo_hinh_khop: str
    r2: float
    thoi_gian_da_cho_s: float
    khuyen_nghi: str
    duong_khop_t_s: list[float] = field(default_factory=list)
    duong_khop_dy_px: list[float] = field(default_factory=list)


def chuyen_anh_xam(anh: np.ndarray) -> np.ndarray:
    """Chuyển ảnh sang mức xám 8-bit chuẩn."""
    if anh is None or not hasattr(anh, "ndim") or anh.size == 0:
        raise AnhKhongHopLeError("Ảnh đầu vào rỗng hoặc không hợp lệ.")
    if anh.ndim == 2:
        return anh.astype(np.uint8) if anh.dtype != np.uint8 else anh
    if anh.ndim == 3:
        if anh.shape[2] == 4:  # RGBA
            return cv2.cvtColor(anh, cv2.COLOR_RGBA2GRAY)
        return cv2.cvtColor(anh, cv2.COLOR_BGR2GRAY)
    raise AnhKhongHopLeError(f"Định dạng ảnh không hợp lệ: shape={anh.shape}")


def chon_kenh_laser(
    anh: np.ndarray,
    kenh_laser: str = "auto",
    roi_goi_y: tuple[int, int, int, int] | None = None,
) -> tuple[np.ndarray, str]:
    """Chọn kênh đơn sắc tối ưu cho laser từ ảnh 2D hoặc ảnh màu BGR/BGRA.

    - Ảnh 2D xám: giữ nguyên và trả nhãn 'xam_2d' (hồi quy tuyệt đối với bản cũ).
    - 'auto' trên ảnh màu: tính tương phản (p99.9 - median) từng kênh R, G, B (ưu tiên R nếu hòa).
    - 'R' | 'G' | 'B' | 'xam': lấy đúng kênh chỉ định.
    """
    if anh is None or not hasattr(anh, "ndim") or anh.size == 0:
        raise AnhKhongHopLeError("Ảnh đầu vào rỗng hoặc không hợp lệ.")
    if anh.ndim == 2:
        return (anh.astype(np.uint8) if anh.dtype != np.uint8 else anh), "xam_2d"
    if anh.ndim != 3 or anh.shape[2] not in (3, 4):
        raise AnhKhongHopLeError(f"Định dạng ảnh không hợp lệ: shape={anh.shape}")

    che_do = str(kenh_laser or "auto").strip()
    che_do_lower = che_do.lower()
    if che_do_lower == "xam":
        return chuyen_anh_xam(anh), "xam"

    kenh_map = {"B": 0, "G": 1, "R": 2}
    if che_do.upper() in kenh_map:
        ch = anh[:, :, kenh_map[che_do.upper()]]
        return (ch.astype(np.uint8) if ch.dtype != np.uint8 else ch), che_do.upper()

    if che_do_lower != "auto":
        raise ValueError(f"Tham số kenh_laser '{kenh_laser}' không hợp lệ (chỉ nhận auto|R|G|B|xam).")

    if roi_goi_y is not None:
        y1, y2, x1, x2 = roi_goi_y
        sub = anh[max(0, y1):max(1, y2), max(0, x1):max(1, x2)]
        if sub.size == 0:
            sub = anh
    else:
        sub = anh

    # Thứ tự ưu tiên R -> G -> B khi độ tương phản bằng nhau
    best_name, best_idx, best_contrast = "R", 2, -1.0
    for name, idx in (("R", 2), ("G", 1), ("B", 0)):
        c_sub = sub[:, :, idx]
        if c_sub.shape[0] * c_sub.shape[1] > 1_000_000:
            c_stat = c_sub[::2, ::2]
        else:
            c_stat = c_sub
        contrast = float(np.percentile(c_stat, 99.9) - np.median(c_stat))
        if contrast > best_contrast:
            best_contrast = contrast
            best_name = name
            best_idx = idx
    out = anh[:, :, best_idx]
    return (out.astype(np.uint8) if out.dtype != np.uint8 else out), best_name


def _doan_lien_tiep_toi_da(mask_1d: np.ndarray) -> int:
    """Đếm độ dài đoạn cột True liên tiếp dài nhất (phân biệt speckle rời rạc với bẹt đỉnh rộng)."""
    max_run = 0
    cur_run = 0
    for val in np.asarray(mask_1d, dtype=bool):
        if val:
            cur_run += 1
            if cur_run > max_run:
                max_run = cur_run
        else:
            cur_run = 0
    return int(max_run)


def _danh_gia_vung_don(
    vung: np.ndarray,
    nguong_bao_hoa: int,
) -> tuple[float, int, float, float, float, float]:
    """Tính các chỉ số chất lượng bất biến theo chiều cao ROI cho một vùng đơn.

    - Bão hòa tính theo tỉ lệ CỘT có đỉnh >= ngưỡng bão hòa trên các cột có tín hiệu,
      kèm độ dài đoạn cột bão hòa liên tiếp tối đa để phân biệt speckle nhỏ với bẹt đỉnh thật.
    - SNR và độ tương phản lấy theo trung vị đỉnh cột so với nền để bất biến diện tích ROI.
    """
    if vung.size == 0 or vung.shape[0] < 1 or vung.shape[1] < 1:
        raise AnhKhongHopLeError("Vùng ROI rỗng, không thể đánh giá chất lượng.")

    if vung.size > 300_000:
        v_stat = vung[::2, ::2]
    else:
        v_stat = vung
    nen = float(np.percentile(v_stat, 10))
    col_max = np.max(vung, axis=0)
    cot_co_tin_hieu = col_max >= (nen + 15.0)
    cot_bao_hoa = col_max >= nguong_bao_hoa

    if np.any(cot_co_tin_hieu):
        ti_le_bh = float(np.mean(cot_bao_hoa[cot_co_tin_hieu]))
        dinh = float(np.median(col_max[cot_co_tin_hieu]))
        lien_tiep_max = _doan_lien_tiep_toi_da(cot_bao_hoa[cot_co_tin_hieu])
    else:
        ti_le_bh = float(np.mean(cot_bao_hoa))
        dinh = float(np.max(col_max))
        lien_tiep_max = _doan_lien_tiep_toi_da(cot_bao_hoa)

    nen_mask = v_stat <= (nen + 5.0)
    std_nen = float(np.std(v_stat[nen_mask])) if np.any(nen_mask) else 1.0
    std_nen = max(std_nen, 0.5)

    tuong_phan = dinh - nen
    snr = tuong_phan / std_nen
    return ti_le_bh, lien_tiep_max, snr, tuong_phan, nen, dinh


def kiem_tra_chat_luong_vung(
    anh_xam: np.ndarray,
    roi_tc: tuple[int, int, int, int],
    roi_mau: tuple[int, int, int, int],
    nguong_bao_hoa: int = 250,
    ti_le_bao_hoa_toi_da: float = 0.02,
    snr_toi_thieu: float = 10.0,
    fwhm_toi_thieu: float = 1.2,
    fwhm_toi_da: float = 65.0,
    anh_goc: np.ndarray | None = None,
    ti_le_cot_bao_hoa_nghiem_trong: float = 0.30,
    so_cot_lien_tiep_bao_hoa: int = 15,
) -> tuple[ChatLuongAnh, float, float]:
    """Kiểm tra chất lượng cho CẢ HAI vùng; phân biệt đốm speckle cục bộ với bão hòa bẹt đỉnh."""
    canh_bao_chi_tiet: list[dict[str, str]] = []

    y1_tc, y2_tc, x1_tc, x2_tc = roi_tc
    y1_m, y2_m, x1_m, x2_m = roi_mau

    vung_tc = anh_xam[y1_tc:y2_tc, x1_tc:x2_tc]
    vung_m = anh_xam[y1_m:y2_m, x1_m:x2_m]

    ti_le_bh_tc, run_tc, snr_tc, contrast_tc, nen_tc, dinh_tc = _danh_gia_vung_don(vung_tc, nguong_bao_hoa)
    ti_le_bh_m, run_m, snr_m, contrast_m, _, _ = _danh_gia_vung_don(vung_m, nguong_bao_hoa)

    # 1. Bão hòa sáng theo cột (từng kênh B, G, R gốc nếu ảnh màu) & phân cấp speckle vs bẹt đỉnh rộng
    ti_le_bh = max(ti_le_bh_tc, ti_le_bh_m)
    lien_tiep_max = max(run_tc, run_m)
    kenh_nghiem_trong: list[str] = []
    kenh_dom_cuc_bo: list[str] = []

    def _la_nghiem_trong(bh_val: float, run_val: int) -> bool:
        return (bh_val > ti_le_cot_bao_hoa_nghiem_trong) or (run_val >= so_cot_lien_tiep_bao_hoa)

    if anh_goc is not None and hasattr(anh_goc, "ndim") and anh_goc.ndim == 3 and anh_goc.shape[2] >= 3:
        for ch_name, ch_idx in (("R", 2), ("G", 1), ("B", 0)):
            ch_tc = anh_goc[y1_tc:y2_tc, x1_tc:x2_tc, ch_idx]
            ch_m = anh_goc[y1_m:y2_m, x1_m:x2_m, ch_idx]
            bh_tc_c, run_tc_c, *_ = _danh_gia_vung_don(ch_tc, nguong_bao_hoa)
            bh_m_c, run_m_c, *_ = _danh_gia_vung_don(ch_m, nguong_bao_hoa)
            bh_c = max(bh_tc_c, bh_m_c)
            run_c = max(run_tc_c, run_m_c)
            ti_le_bh = max(ti_le_bh, bh_c)
            lien_tiep_max = max(lien_tiep_max, run_c)
            if _la_nghiem_trong(bh_c, run_c):
                kenh_nghiem_trong.append(ch_name)
            elif bh_c > ti_le_bao_hoa_toi_da:
                kenh_dom_cuc_bo.append(ch_name)
    else:
        if _la_nghiem_trong(ti_le_bh, lien_tiep_max):
            kenh_nghiem_trong.append("xam")
        elif ti_le_bh > ti_le_bao_hoa_toi_da:
            kenh_dom_cuc_bo.append("xam")

    co_bao_hoa = bool(kenh_nghiem_trong) or _la_nghiem_trong(ti_le_bh, lien_tiep_max)
    co_dom_cuc_bo = (not co_bao_hoa) and (bool(kenh_dom_cuc_bo) or (ti_le_bh > ti_le_bao_hoa_toi_da))
    kenh_bao_hoa = kenh_nghiem_trong if co_bao_hoa else kenh_dom_cuc_bo

    if co_bao_hoa:
        kenh_txt = f" (kênh {', '.join(kenh_bao_hoa)})" if kenh_bao_hoa else ""
        canh_bao_chi_tiet.append({
            "ma": "BAO_HOA_NGHIEM_TRONG",
            "cap": "nghiem_trong",
            "noi_dung": (
                f"Vạch sáng bị bão hòa rộng{kenh_txt} ({ti_le_bh*100:.1f}% cột có đỉnh ≥ {nguong_bao_hoa}, "
                f"đoạn liên tiếp dài nhất {lien_tiep_max} cột): đỉnh Gauss bị bẹt. "
                "Cần giảm phơi sáng máy ảnh hoặc giảm công suất laser."
            ),
        })
    elif co_dom_cuc_bo:
        kenh_txt = f" (kênh {', '.join(kenh_bao_hoa)})" if kenh_bao_hoa else ""
        canh_bao_chi_tiet.append({
            "ma": "DOM_BAO_HOA_CUC_BO",
            "cap": "can_than",
            "noi_dung": (
                f"Phát hiện đốm bão hòa cục bộ{kenh_txt} ({ti_le_bh*100:.1f}% cột, đoạn liên tiếp tối đa "
                f"{lien_tiep_max} cột < {so_cot_lien_tiep_bao_hoa}), có thể do hạt đốm laser (speckle); "
                "lõi vạch vẫn định tâm được nhưng nên giảm nhẹ phơi sáng khi chụp tiếp."
            ),
        })

    # 2. Tín hiệu / nhiễu (SNR): tính cho cả hai vùng và lấy giá trị thấp hơn
    snr_uoc_luong = min(snr_tc, snr_m)
    contrast_min = min(contrast_tc, contrast_m)
    co_qua_mo = bool(snr_uoc_luong < snr_toi_thieu or contrast_min < 15.0)
    if co_qua_mo:
        canh_bao_chi_tiet.append({
            "ma": "QUA_MO",
            "cap": "nghiem_trong",
            "noi_dung": (
                f"Vạch sáng quá mờ (SNR tối thiểu giữa 2 vùng = {snr_uoc_luong:.1f} < {snr_toi_thieu} hoặc tương phản yếu). "
                "Cần che bớt ánh sáng môi trường hoặc tăng sáng laser."
            ),
        })

    hop_le = not (co_bao_hoa or co_qua_mo)

    chat_luong = ChatLuongAnh(
        hop_le=hop_le,
        bao_hoa=co_bao_hoa,
        ti_le_bao_hoa=ti_le_bh,
        qua_mo=co_qua_mo,
        snr=snr_uoc_luong,
        nhoe=False,
        fwhm_mau=0.0,
        fwhm_tc=0.0,
        canh_bao=[c["noi_dung"] for c in canh_bao_chi_tiet],
        kenh_bao_hoa=kenh_bao_hoa,
        co_dom_bao_hoa_cuc_bo=co_dom_cuc_bo,
        so_cot_bao_hoa_lien_tiep_max=lien_tiep_max,
        canh_bao_chi_tiet=canh_bao_chi_tiet,
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


def _uoc_luong_nen_hinh_thai(anh_xam: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """Ước lượng nền sáng chậm bằng phép mở hình thái trên ảnh thu gọn ≤ 900 px.

    Trả về:
        (anh_thu_gon, anh_nen_thu_gon, bien_thien_nen_p95_p5)
    """
    if anh_xam is None or anh_xam.size == 0:
        raise AnhKhongHopLeError("Ảnh đầu vào rỗng, không thể ước lượng nền.")
    h, w = anh_xam.shape[:2]
    canh_max = max(h, w)
    if canh_max > 900:
        scale = 900.0 / float(canh_max)
        nw = max(32, int(round(w * scale)))
        nh = max(32, int(round(h * scale)))
        work = cv2.resize(anh_xam, (nw, nh), interpolation=cv2.INTER_AREA)
    else:
        work = anh_xam

    hs, ws = work.shape[:2]
    kh = max(19, min(45, (hs // 7) | 1))
    kw = max(11, min(31, (ws // 12) | 1))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kw, kh))
    nen = cv2.morphologyEx(work, cv2.MORPH_OPEN, kernel)
    nen = cv2.GaussianBlur(nen, (9, 9), 0)
    bien_thien_nen = float(np.percentile(nen, 95) - np.percentile(nen, 5))
    return work, nen, bien_thien_nen


def tu_dong_tim_roi_hai_vach(
    anh_xam: np.ndarray,
    ty_le_sang: float = 0.4,
    nguong_nen_khong_deu: float = 30.0,
) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    """Tự động phát hiện 2 vùng quan tâm (ROI) chứa 2 vạch sáng trên ảnh.

    Cải tiến Q3:
    - Trừ nền hình thái chậm trước khi lấy ngưỡng để không nhận nhầm vùng sáng nền.
    - Xử lí trên bản thu gọn cạnh lớn ≤ 900 px rồi quy đổi tọa độ về ảnh gốc (ảnh 12MP vẫn ≤ 3s).
    - Hỗ trợ cả bố trí ngang (Trái - Phải) và đứng (Trên - Dưới).
    """
    h, w = anh_xam.shape
    work, nen_work, bien_thien_nen = _uoc_luong_nen_hinh_thai(anh_xam)
    hs, ws = work.shape
    sx = float(w) / float(ws)
    sy = float(h) / float(hs)
    x_mid_s = ws // 2

    # Trừ nền không đều để hai vạch laser nổi rõ trên nền sạch
    anh_sach = cv2.subtract(work, nen_work)
    blur = cv2.GaussianBlur(anh_sach, (5, 5), 0)
    nguong_val = float(np.percentile(blur, 100.0 * (1.0 - ty_le_sang * 0.08)))
    nguong_val = max(nguong_val, 22.0)

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

    def _quy_doi_roi(y0_s: int, y1_s: int, x0_s: int, x1_s: int) -> tuple[int, int, int, int]:
        y0 = max(0, min(h - 1, int(math.floor(y0_s * sy))))
        y1 = max(y0 + 1, min(h, int(math.ceil(y1_s * sy))))
        x0 = max(0, min(w - 1, int(math.floor(x0_s * sx))))
        x1 = max(x0 + 1, min(w, int(math.ceil(x1_s * sx))))
        return (y0, y1, x0, x1)

    if len(ds_vach) >= 2:
        # Sắp xếp theo diện tích lớn nhất
        ds_vach.sort(key=lambda item: item[4], reverse=True)
        v1, v2 = ds_vach[0], ds_vach[1]

        # Kiểm tra bố trí Trái - Phải hay Trên - Dưới
        x1_center = v1[0] + v1[2] / 2.0
        x2_center = v2[0] + v2[2] / 2.0

        if abs(x1_center - x2_center) > ws * 0.2:
            v_trai = v1 if x1_center < x2_center else v2
            v_phai = v2 if x1_center < x2_center else v1

            def tao_roi_ngang(x: int, y: int, cw: int, ch: int) -> tuple[int, int, int, int]:
                return _quy_doi_roi(max(0, y - 25), min(hs, y + ch + 25), max(0, x - 5), min(ws, x + cw + 5))

            return tao_roi_ngang(*v_trai[:4]), tao_roi_ngang(*v_phai[:4])
        else:
            if v1[1] > v2[1]:
                v1, v2 = v2, v1

            def tao_roi_doc(x: int, y: int, cw: int, ch: int) -> tuple[int, int, int, int]:
                return _quy_doi_roi(max(0, y - 15), min(hs, y + ch + 15), max(0, x - 5), min(ws, x + cw + 5))

            return tao_roi_doc(*v1[:4]), tao_roi_doc(*v2[:4])

    elif len(ds_vach) == 1:
        x, y, cw, ch, _ = ds_vach[0]
        y_min_s = max(0, y - 25)
        y_max_s = min(hs, y + ch + 25)
        roi_trai = _quy_doi_roi(y_min_s, y_max_s, max(0, x), min(ws, x_mid_s - 10))
        roi_phai = _quy_doi_roi(y_min_s, y_max_s, max(0, x_mid_s + 10), min(ws, x + cw))
        return roi_trai, roi_phai

    if bien_thien_nen > nguong_nen_khong_deu:
        raise KhongTimThayVachError(
            f"Nền sáng không đều (biến thiên nền {bien_thien_nen:.1f} > {nguong_nen_khong_deu:.1f}), "
            "hãy che sáng môi trường hoặc kéo chọn ROI thủ công trên ảnh."
        )
    raise KhongTimThayVachError(
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
    snr_toi_thieu: float = 10.0,
    tao_anh_ve: bool = True,
    kenh_laser: str = "auto",
    ti_le_cot_bao_hoa_nghiem_trong: float = 0.30,
    so_cot_lien_tiep_bao_hoa: int = 15,
    nguong_nen_khong_deu: float = 30.0,
    tham_so_ong_kinh: ThamSoOngKinh | None = None,
    nguong_lech_tam_meo_ti_le: float = 0.30,
    he_so_meo_k1_khai_bao: float | None = None,
) -> KetQuaDoDeltaY:
    """Đo độ lệch vi sai Δy và chỉ số độ đục từ một ảnh chụp (chọn kênh laser tối ưu & kiểm bão hòa gốc)."""
    if tham_so_ong_kinh is not None:
        anh = sua_meo_anh(anh, tham_so_ong_kinh)
    anh_kenh, ten_kenh = chon_kenh_laser(anh, kenh_laser=kenh_laser)

    # 1. Xác định ROI nếu chưa có
    if roi_tham_chieu is None or roi_mau is None:
        roi_1, roi_2 = tu_dong_tim_roi_hai_vach(anh_kenh, nguong_nen_khong_deu=nguong_nen_khong_deu)
        roi_tham_chieu = roi_1 if roi_tham_chieu is None else roi_tham_chieu
        roi_mau = roi_2 if roi_mau is None else roi_mau

    if hasattr(anh, "ndim") and anh.ndim == 3 and str(kenh_laser).strip().lower() == "auto":
        y1_u = min(roi_tham_chieu[0], roi_mau[0])
        y2_u = max(roi_tham_chieu[1], roi_mau[1])
        x1_u = min(roi_tham_chieu[2], roi_mau[2])
        x2_u = max(roi_tham_chieu[3], roi_mau[3])
        anh_kenh, ten_kenh = chon_kenh_laser(anh, kenh_laser="auto", roi_goi_y=(y1_u, y2_u, x1_u, x2_u))

    _, _, bien_thien_nen = _uoc_luong_nen_hinh_thai(anh_kenh)
    nen_khong_deu = bool(bien_thien_nen > nguong_nen_khong_deu)

    # 2. Đánh giá chất lượng sơ bộ vùng ảnh (kiểm bão hòa trên từng kênh RGB gốc)
    chat_luong_khoi_tao, _, _ = kiem_tra_chat_luong_vung(
        anh_kenh,
        roi_tham_chieu,
        roi_mau,
        nguong_bao_hoa=nguong_bao_hoa,
        ti_le_bao_hoa_toi_da=ti_le_bao_hoa_toi_da,
        snr_toi_thieu=snr_toi_thieu,
        anh_goc=anh,
        ti_le_cot_bao_hoa_nghiem_trong=ti_le_cot_bao_hoa_nghiem_trong,
        so_cot_lien_tiep_bao_hoa=so_cot_lien_tiep_bao_hoa,
    )
    if nen_khong_deu:
        ct_nen = list(chat_luong_khoi_tao.canh_bao_chi_tiet)
        ct_nen.append({
            "ma": "NEN_KHONG_DEU",
            "cap": "can_than",
            "noi_dung": (
                f"Nền sáng không đều (biến thiên nền {bien_thien_nen:.1f} > {nguong_nen_khong_deu:.1f}), "
                "hãy che sáng môi trường hoặc chọn ROI thủ công."
            ),
        })
        chat_luong_khoi_tao = ChatLuongAnh(
            hop_le=chat_luong_khoi_tao.hop_le,
            bao_hoa=chat_luong_khoi_tao.bao_hoa,
            ti_le_bao_hoa=chat_luong_khoi_tao.ti_le_bao_hoa,
            qua_mo=chat_luong_khoi_tao.qua_mo,
            snr=chat_luong_khoi_tao.snr,
            nhoe=chat_luong_khoi_tao.nhoe,
            fwhm_mau=chat_luong_khoi_tao.fwhm_mau,
            fwhm_tc=chat_luong_khoi_tao.fwhm_tc,
            canh_bao=[c["noi_dung"] for c in ct_nen],
            kenh_bao_hoa=list(chat_luong_khoi_tao.kenh_bao_hoa),
            co_dom_bao_hoa_cuc_bo=chat_luong_khoi_tao.co_dom_bao_hoa_cuc_bo,
            so_cot_bao_hoa_lien_tiep_max=chat_luong_khoi_tao.so_cot_bao_hoa_lien_tiep_max,
            canh_bao_chi_tiet=ct_nen,
            nen_khong_deu=True,
            bien_thien_nen=bien_thien_nen,
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

    # 4. Trích xuất và ước lượng từng vạch (tự tăng bước nhảy cột cho ảnh > 600 px để giữ <= 3s trên ảnh 12MP)
    anh_roi_tc = anh_kenh[y1_tc:y2_tc, x1_tc:x2_tc]
    anh_roi_m = anh_kenh[y1_m:y2_m, x1_m:x2_m]
    buoc_tc = max(buoc_nhay_cot, (x2_tc - x1_tc) // 140) if (x2_tc - x1_tc) > 600 else buoc_nhay_cot
    buoc_m = max(buoc_nhay_cot, (x2_m - x1_m) // 140) if (x2_m - x1_m) > 600 else buoc_nhay_cot

    try:
        vach_tc = uoc_luong_duong_vach(
            anh_roi_tc,
            x_offset=x1_tc,
            y_offset=y1_tc,
            x_ref=x_ref_tinh,
            phuong_phap=phuong_phap,
            buoc_nhay_cot=buoc_tc,
        )
        vach_m = uoc_luong_duong_vach(
            anh_roi_m,
            x_offset=x1_m,
            y_offset=y1_m,
            x_ref=x_ref_tinh,
            phuong_phap=phuong_phap,
            buoc_nhay_cot=buoc_m,
        )
    except ValueError as e:
        # Nếu không đủ số cột đạt chuẩn để khớp vạch (ảnh quá mờ hoặc nhiễu nặng)
        canh_bao_ct_loi = list(chat_luong_khoi_tao.canh_bao_chi_tiet)
        msg_loi = f"Không thể định vị vạch: {e}"
        canh_bao_ct_loi.append({"ma": "KHONG_DINH_VI_VACH", "cap": "nghiem_trong", "noi_dung": msg_loi})
        chat_luong_loi = ChatLuongAnh(
            hop_le=False,
            bao_hoa=chat_luong_khoi_tao.bao_hoa,
            ti_le_bao_hoa=chat_luong_khoi_tao.ti_le_bao_hoa,
            qua_mo=True,
            snr=chat_luong_khoi_tao.snr,
            nhoe=True,
            fwhm_mau=0.0,
            fwhm_tc=0.0,
            canh_bao=[c["noi_dung"] for c in canh_bao_ct_loi],
            kenh_bao_hoa=list(chat_luong_khoi_tao.kenh_bao_hoa),
            co_dom_bao_hoa_cuc_bo=chat_luong_khoi_tao.co_dom_bao_hoa_cuc_bo,
            so_cot_bao_hoa_lien_tiep_max=chat_luong_khoi_tao.so_cot_bao_hoa_lien_tiep_max,
            canh_bao_chi_tiet=canh_bao_ct_loi,
            nen_khong_deu=nen_khong_deu,
            bien_thien_nen=bien_thien_nen,
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
            kenh_su_dung=ten_kenh,
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

    # 7. Cập nhật cảnh báo độ nhòe, méo ống kính và hoàn thiện đối tượng chất lượng
    canh_bao_ct_final = list(chat_luong_khoi_tao.canh_bao_chi_tiet)
    co_nhoe = bool(vach_m.fwhm_trung_binh > 50.0 or vach_tc.fwhm_trung_binh > 50.0)
    if co_nhoe:
        canh_bao_ct_final.append({
            "ma": "NHOE_VACH",
            "cap": "nghiem_trong",
            "noi_dung": (
                f"Vạch bị nhòe lớn (FWHM mẫu = {vach_m.fwhm_trung_binh:.1f} px, FWHM tc = {vach_tc.fwhm_trung_binh:.1f} px). "
                "Cần kiểm tra lại hội tụ của ống kính hoặc mẫu quá đục làm mất biên dạng vạch."
            ),
        })

    h_anh, w_anh = anh_kenh.shape[:2]
    meo_check = kiem_tra_vung_meo_ong_kinh(
        h_img=h_anh,
        y_tc=vach_tc.y_tam,
        y_mau=vach_m.y_tam,
        nguong_lech_tam_ti_le=nguong_lech_tam_meo_ti_le,
        he_so_meo_k1=he_so_meo_k1_khai_bao,
        chua_sua_meo=(tham_so_ong_kinh is None),
        w_img=w_anh,
    )
    co_meo_ong_kinh = bool(meo_check["canh_bao_meo"])
    if co_meo_ong_kinh and meo_check["noi_dung"]:
        canh_bao_ct_final.append({
            "ma": "MEO_ONG_KINH",
            "cap": str(meo_check["cap"] or "thong_tin"),
            "noi_dung": str(meo_check["noi_dung"]),
        })

    chat_luong_final = ChatLuongAnh(
        hop_le=bool(chat_luong_khoi_tao.hop_le and not co_nhoe),
        bao_hoa=chat_luong_khoi_tao.bao_hoa,
        ti_le_bao_hoa=chat_luong_khoi_tao.ti_le_bao_hoa,
        qua_mo=chat_luong_khoi_tao.qua_mo,
        snr=chat_luong_khoi_tao.snr,
        nhoe=co_nhoe,
        fwhm_mau=vach_m.fwhm_trung_binh,
        fwhm_tc=vach_tc.fwhm_trung_binh,
        canh_bao=[c["noi_dung"] for c in canh_bao_ct_final],
        kenh_bao_hoa=list(chat_luong_khoi_tao.kenh_bao_hoa),
        co_dom_bao_hoa_cuc_bo=chat_luong_khoi_tao.co_dom_bao_hoa_cuc_bo,
        so_cot_bao_hoa_lien_tiep_max=chat_luong_khoi_tao.so_cot_bao_hoa_lien_tiep_max,
        canh_bao_chi_tiet=canh_bao_ct_final,
        nen_khong_deu=nen_khong_deu,
        bien_thien_nen=bien_thien_nen,
        canh_bao_meo_ong_kinh=co_meo_ong_kinh,
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
        kenh_su_dung=ten_kenh,
    )


def do_delta_y_da_khung_hinh(
    danh_sach_anh: list[np.ndarray],
    roi_tham_chieu: tuple[int, int, int, int] | None = None,
    roi_mau: tuple[int, int, int, int] | None = None,
    phuong_phap: Literal["gauss", "centroid"] = "gauss",
    nguong_bao_hoa: int = 250,
    ti_le_bao_hoa_toi_da: float = 0.02,
    snr_toi_thieu: float = 10.0,
    kenh_laser: str = "auto",
    ti_le_cot_bao_hoa_nghiem_trong: float = 0.30,
    so_cot_lien_tiep_bao_hoa: int = 15,
    nguong_nen_khong_deu: float = 30.0,
    tham_so_ong_kinh: ThamSoOngKinh | None = None,
    nguong_lech_tam_meo_ti_le: float = 0.30,
    he_so_meo_k1_khai_bao: float | None = None,
) -> KetQuaDoDaKhungHinh:
    """Xử lí chuỗi nhiều khung hình (video / multi-shot), lấy trung vị và độ phân tán.

    - Ghi rõ khung lỗi kèm lí do (không nuốt ngoại lệ thầm lặng).
    - Chỉ tính khung hợp lệ khi `chat_luong.hop_le` đạt chuẩn; tổng hợp chất lượng xấu nhất.
    - Kiểm tra trôi tuyến tính theo thời gian (dấu hiệu chưa cân bằng nhiệt) và dao động phơi sáng.
    """
    if not danh_sach_anh:
        raise ValueError("Danh sách khung hình trống")

    ds_delta_y: list[float] = []
    ds_do_duc: list[float] = []
    ds_chi_so_khung: list[int] = []
    ds_dinh_tc: list[float] = []
    ds_dinh_m: list[float] = []
    ds_cq_tat_ca: list[ChatLuongAnh] = []
    khung_loi: list[tuple[int, str]] = []

    for idx, img in enumerate(danh_sach_anh):
        try:
            kq = do_delta_y_tu_anh(
                img,
                roi_tham_chieu=roi_tham_chieu,
                roi_mau=roi_mau,
                phuong_phap=phuong_phap,
                nguong_bao_hoa=nguong_bao_hoa,
                ti_le_bao_hoa_toi_da=ti_le_bao_hoa_toi_da,
                snr_toi_thieu=snr_toi_thieu,
                tao_anh_ve=False,
                kenh_laser=kenh_laser,
                ti_le_cot_bao_hoa_nghiem_trong=ti_le_cot_bao_hoa_nghiem_trong,
                so_cot_lien_tiep_bao_hoa=so_cot_lien_tiep_bao_hoa,
                nguong_nen_khong_deu=nguong_nen_khong_deu,
                tham_so_ong_kinh=tham_so_ong_kinh,
                nguong_lech_tam_meo_ti_le=nguong_lech_tam_meo_ti_le,
                he_so_meo_k1_khai_bao=he_so_meo_k1_khai_bao,
            )
        except (AnhKhongHopLeError, KhongTimThayVachError, ValueError) as exc:
            khung_loi.append((idx, str(exc)))
            continue

        ds_cq_tat_ca.append(kq.chat_luong)
        if (not kq.chat_luong.hop_le) or (not math.isfinite(kq.delta_y_px)):
            ly_do = "; ".join(kq.chat_luong.canh_bao) or "Chất lượng ảnh không đạt"
            khung_loi.append((idx, ly_do))
            continue

        ds_chi_so_khung.append(idx)
        ds_delta_y.append(kq.delta_y_px)
        ds_do_duc.append(kq.chi_so_do_duc_tuong_doi)
        ds_dinh_tc.append(kq.vach_tham_chieu.cuong_do_dinh_tb)
        ds_dinh_m.append(kq.vach_mau.cuong_do_dinh_tb)

    tong_khung = len(danh_sach_anh)
    so_hop_le = len(ds_delta_y)

    if so_hop_le == 0:
        chi_tiet = "; ".join(f"Khung {i + 1}: {m}" for i, m in khung_loi[:3])
        raise KhongTimThayVachError(
            f"Tất cả {tong_khung} khung hình đều lỗi hoặc không đạt chất lượng ({chi_tiet})."
        )

    arr_dy = np.array(ds_delta_y, dtype=float)
    trung_vi = float(np.median(arr_dy))
    mad = float(np.median(np.abs(arr_dy - trung_vi)))
    robust_sigma = 1.4826 * mad
    sai_so_thong_ke = float(robust_sigma / math.sqrt(so_hop_le))

    canh_bao_da_khung: list[str] = []
    if khung_loi:
        canh_bao_da_khung.append(
            f"Đã loại {len(khung_loi)}/{tong_khung} khung không đạt: "
            + "; ".join(f"#{i + 1} ({msg})" for i, msg in khung_loi[:3])
        )

    # Kiểm tra trôi tuyến tính theo thời gian (chỉ số khung)
    do_doc_troi = 0.0
    se_doc_troi = 0.0
    co_troi_thoi_gian = False
    if so_hop_le >= 4:
        t_arr = np.asarray(ds_chi_so_khung, dtype=float)
        t_c = t_arr - float(np.mean(t_arr))
        denom = float(np.dot(t_c, t_c))
        if denom > 0.0:
            do_doc_troi = float(np.dot(t_c, arr_dy - float(np.mean(arr_dy))) / denom)
            res_t = arr_dy - (float(np.mean(arr_dy)) + do_doc_troi * t_c)
            s_t = math.sqrt(float(np.dot(res_t, res_t)) / max(len(t_arr) - 2, 1))
            se_doc_troi = float(s_t / math.sqrt(denom))
            tong_troi = abs(do_doc_troi * float(t_arr[-1] - t_arr[0]))
            if abs(do_doc_troi) > 2.5 * max(se_doc_troi, 1e-6) and tong_troi > max(0.15, 2.0 * robust_sigma):
                co_troi_thoi_gian = True
                canh_bao_da_khung.append(
                    f"Phát hiện Δy trôi theo thời gian ({do_doc_troi:+.3f} ± {se_doc_troi:.3f} px/khung, "
                    f"dịch tổng {tong_troi:.2f} px): dấu hiệu hai ngăn chưa cân bằng nhiệt."
                )

    # Kiểm tra dao động độ sáng đỉnh (phơi sáng không ổn định / chưa khóa AE)
    co_dao_dong_sang = False
    if so_hop_le >= 2:
        def _ti_le_dao_dong(vals: list[float]) -> float:
            med = max(float(np.median(vals)), 1.0)
            return float(max(vals) - min(vals)) / med

        bien_thien_sang = max(_ti_le_dao_dong(ds_dinh_tc), _ti_le_dao_dong(ds_dinh_m))
        if bien_thien_sang > 0.15:
            co_dao_dong_sang = True
            canh_bao_da_khung.append(
                f"Mức sáng đỉnh dao động {bien_thien_sang * 100:.1f}% giữa các khung: "
                "cần khóa phơi sáng (AE lock) trước khi chụp."
            )

    # Tổng hợp chất lượng theo mức XẤU NHẤT trong toàn bộ chuỗi
    canh_bao_gop: list[str] = []
    canh_bao_ct_gop: list[dict[str, str]] = []
    for cq_item in ds_cq_tat_ca:
        for w_msg in cq_item.canh_bao:
            if w_msg not in canh_bao_gop:
                canh_bao_gop.append(w_msg)
        for item_ct in cq_item.canh_bao_chi_tiet:
            if item_ct["noi_dung"] not in {x["noi_dung"] for x in canh_bao_ct_gop}:
                canh_bao_ct_gop.append(dict(item_ct))
    for w_dk in canh_bao_da_khung:
        if w_dk not in canh_bao_gop:
            canh_bao_gop.append(w_dk)
            canh_bao_ct_gop.append({"ma": "CANH_BAO_DA_KHUNG", "cap": "can_than", "noi_dung": w_dk})

    kenh_bh_gop: list[str] = []
    for cq_item in ds_cq_tat_ca:
        for ch in cq_item.kenh_bao_hoa:
            if ch not in kenh_bh_gop:
                kenh_bh_gop.append(ch)

    chat_luong_chung = ChatLuongAnh(
        hop_le=all(c.hop_le for c in ds_cq_tat_ca) and (not khung_loi),
        bao_hoa=any(c.bao_hoa for c in ds_cq_tat_ca),
        ti_le_bao_hoa=max(c.ti_le_bao_hoa for c in ds_cq_tat_ca),
        qua_mo=any(c.qua_mo for c in ds_cq_tat_ca),
        snr=min(c.snr for c in ds_cq_tat_ca),
        nhoe=any(c.nhoe for c in ds_cq_tat_ca),
        fwhm_mau=max(c.fwhm_mau for c in ds_cq_tat_ca),
        fwhm_tc=max(c.fwhm_tc for c in ds_cq_tat_ca),
        canh_bao=canh_bao_gop,
        kenh_bao_hoa=kenh_bh_gop,
        co_dom_bao_hoa_cuc_bo=any(c.co_dom_bao_hoa_cuc_bo for c in ds_cq_tat_ca),
        so_cot_bao_hoa_lien_tiep_max=max(c.so_cot_bao_hoa_lien_tiep_max for c in ds_cq_tat_ca),
        canh_bao_chi_tiet=canh_bao_ct_gop,
        nen_khong_deu=any(c.nen_khong_deu for c in ds_cq_tat_ca),
        bien_thien_nen=max(c.bien_thien_nen for c in ds_cq_tat_ca),
        canh_bao_meo_ong_kinh=any(c.canh_bao_meo_ong_kinh for c in ds_cq_tat_ca),
    )

    return KetQuaDoDaKhungHinh(
        delta_y_trung_vi_px=trung_vi,
        sai_so_thong_ke_px=sai_so_thong_ke,
        so_khung_hop_le=so_hop_le,
        tong_so_khung=tong_khung,
        danh_sach_delta_y=ds_delta_y,
        chi_so_do_duc_tb=float(np.mean(ds_do_duc)),
        chat_luong_chung=chat_luong_chung,
        khung_loi=khung_loi,
        do_doc_troi_px_moi_khung=do_doc_troi,
        sai_so_do_doc_troi=se_doc_troi,
        canh_bao_troi_theo_thoi_gian=co_troi_thoi_gian,
        canh_bao_dao_dong_phoi_sang=co_dao_dong_sang,
        canh_bao_da_khung=canh_bao_da_khung,
        chi_so_khung_hop_le=ds_chi_so_khung,
    )


def _ham_mu_can_bang_nhiet(t: np.ndarray, dy_inf: float, amp: float, tau: float) -> np.ndarray:
    """Mô hình truyền nhiệt Newton bậc 1 làm chiết suất và Δy hội tụ theo hàm mũ."""
    return dy_inf + amp * np.exp(-t / np.maximum(tau, 1e-6))


def phan_tich_can_bang_nhiet(
    thoi_gian_s: list[float] | np.ndarray,
    danh_sach_delta_y: list[float] | np.ndarray,
    nguong_on_dinh_px_moi_phut: float = 0.05,
) -> KetQuaCanBangNhiet:
    """Khớp Δy(t) = Δy∞ + A·exp(−t/τ) cho chuỗi đa khung có mốc thời gian (Q5).

    Đánh giá độ dốc còn lại |dΔy/dt| tại thời điểm cuối (px/phút) so với ngưỡng cấu hình.
    TUYỆT ĐỐI không gợi ý thời gian chờ cố định; khuyến nghị hoàn toàn dựa trên tốc độ trôi đo được.
    """
    t_arr = np.asarray(thoi_gian_s, dtype=float)
    y_arr = np.asarray(danh_sach_delta_y, dtype=float)
    if t_arr.ndim != 1 or y_arr.ndim != 1 or len(t_arr) != len(y_arr):
        raise ValueError("Danh sách thời gian và Δy phải cùng chiều dài.")

    hop_le = np.isfinite(t_arr) & np.isfinite(y_arr)
    t_arr = t_arr[hop_le]
    y_arr = y_arr[hop_le]
    if len(t_arr) < 4:
        raise ValueError("Cần ít nhất 4 điểm thời gian hợp lệ để phân tích cân bằng nhiệt.")

    thu_tu = np.argsort(t_arr)
    t_raw = t_arr[thu_tu]
    y = y_arr[thu_tu]
    t0 = float(t_raw[0])
    t_rel = t_raw - t0
    t_span = float(t_rel[-1])
    if t_span <= 0.0:
        raise ValueError("Các mốc thời gian phải trải trên khoảng dương (> 0 giây).")

    nguong = max(float(nguong_on_dinh_px_moi_phut), 1e-6)
    ss_tot = float(np.sum((y - float(np.mean(y))) ** 2))

    # 1. Kiểm tra chuỗi phẳng bằng hồi quy tuyến tính + so sánh độ tán nhiễu từng bước
    t_c = t_rel - float(np.mean(t_rel))
    denom_t = float(np.dot(t_c, t_c))
    slope_lin = float(np.dot(t_c, y - float(np.mean(y))) / denom_t) if denom_t > 0.0 else 0.0
    res_lin = y - (float(np.mean(y)) + slope_lin * t_c)
    s_lin = math.sqrt(float(np.dot(res_lin, res_lin)) / max(len(y) - 2, 1))
    se_slope = s_lin / math.sqrt(max(denom_t, 1e-12))
    do_doc_lin_phut = abs(slope_lin) * 60.0
    sigma_buoc = max(1.4826 * float(np.median(np.abs(np.diff(y)))) / math.sqrt(2.0), 1e-4)

    # Thử khớp hàm mũ đa điểm khởi tạo để so sánh với đường phẳng
    best_fit: tuple[np.ndarray, np.ndarray, float] | None = None
    ymin, ymax = float(np.min(y)), float(np.max(y))
    span_y = max(ymax - ymin, 0.1)
    amp_lim = max(50.0, 20.0 * span_y)
    lb = [ymin - 10.0 * span_y - 20.0, -amp_lim, max(t_span / 200.0, 0.05)]
    ub = [ymax + 10.0 * span_y + 20.0, amp_lim, t_span * 100.0]

    for mult in (0.08, 0.20, 0.45, 1.0, 2.2):
        tau0 = float(np.clip(mult * t_span, lb[2] * 1.1, ub[2] * 0.9))
        e_col = np.exp(-t_rel / tau0)
        mat = np.column_stack([np.ones_like(e_col), e_col])
        try:
            beta, *_ = np.linalg.lstsq(mat, y, rcond=None)
            y_inf0 = float(np.clip(beta[0], lb[0] + 1e-3, ub[0] - 1e-3))
            amp0 = float(np.clip(beta[1], lb[1] + 1e-3, ub[1] - 1e-3))
            popt, pcov = curve_fit(
                _ham_mu_can_bang_nhiet,
                t_rel,
                y,
                p0=[y_inf0, amp0, tau0],
                bounds=(lb, ub),
                maxfev=8000,
            )
            pred = _ham_mu_can_bang_nhiet(t_rel, *popt)
            ssr = float(np.sum((y - pred) ** 2))
            if best_fit is None or ssr < best_fit[2]:
                best_fit = (popt, pcov, ssr)
        except Exception:
            continue

    la_phang = False
    if do_doc_lin_phut <= nguong and abs(slope_lin) <= 2.5 * se_slope:
        bien_thien_exp = 0.0
        if best_fit is not None:
            p_b = best_fit[0]
            bien_thien_exp = abs(float(p_b[1]) * (1.0 - math.exp(-t_span / max(float(p_b[2]), 1e-6))))
        if bien_thien_exp <= max(3.5 * sigma_buoc, (nguong / 60.0) * t_span * 1.5):
            la_phang = True

    t_grid_rel = np.linspace(0.0, t_span, 25)
    t_grid_raw = (t_grid_rel + t0).tolist()

    if la_phang or best_fit is None:
        if la_phang:
            y_med = float(np.median(y))
            mad = float(np.median(np.abs(y - y_med)))
            u_inf = max(1.4826 * mad / math.sqrt(len(y)), s_lin / math.sqrt(len(y)))
            da_on = do_doc_lin_phut <= nguong
            r2_val = 1.0 - (float(np.dot(res_lin, res_lin)) / ss_tot) if ss_tot > 1e-12 else 1.0
            msg = (
                f"Đã ổn định nhiệt (chuỗi phẳng, độ trôi {do_doc_lin_phut:.3f} ≤ {nguong:.3f} px/phút; "
                f"Δy = {y_med:.3f} ± {u_inf:.3f} px). Có thể chốt kết quả đo."
            )
            return KetQuaCanBangNhiet(
                tau_s=None,
                u_tau_s=None,
                delta_y_vo_cuc_px=y_med,
                u_delta_y_vo_cuc_px=float(u_inf),
                bien_do_A_px=0.0,
                do_doc_con_lai_px_moi_phut=float(do_doc_lin_phut),
                da_on_dinh=bool(da_on),
                nguong_px_moi_phut=nguong,
                mo_hinh_khop="phang",
                r2=float(max(min(r2_val, 1.0), 0.0)),
                thoi_gian_da_cho_s=t_span,
                khuyen_nghi=msg,
                duong_khop_t_s=[float(x) for x in t_grid_raw],
                duong_khop_dy_px=[y_med] * len(t_grid_raw),
            )
        # Fallback tuyến tính nếu curve_fit không hội tụ trên dữ liệu dị thường
        y_end = float(np.mean(y) + slope_lin * (t_rel[-1] - float(np.mean(t_rel))))
        u_end = float(s_lin / math.sqrt(max(len(y), 1)))
        da_on = do_doc_lin_phut <= nguong
        r2_val = 1.0 - (float(np.dot(res_lin, res_lin)) / ss_tot) if ss_tot > 1e-12 else 0.0
        msg = (
            f"{'Đã ổn định nhiệt' if da_on else 'Chưa ổn định nhiệt'} theo độ dốc cuối tuyến tính "
            f"({do_doc_lin_phut:.3f} px/phút vs ngưỡng {nguong:.3f} px/phút)."
        )
        return KetQuaCanBangNhiet(
            tau_s=None,
            u_tau_s=None,
            delta_y_vo_cuc_px=y_end,
            u_delta_y_vo_cuc_px=u_end,
            bien_do_A_px=0.0,
            do_doc_con_lai_px_moi_phut=float(do_doc_lin_phut),
            da_on_dinh=bool(da_on),
            nguong_px_moi_phut=nguong,
            mo_hinh_khop="tuyen_tinh_du_phong",
            r2=float(r2_val),
            thoi_gian_da_cho_s=t_span,
            khuyen_nghi=msg,
            duong_khop_t_s=[float(x) for x in t_grid_raw],
            duong_khop_dy_px=[float(np.mean(y) + slope_lin * (tr - float(np.mean(t_rel)))) for tr in t_grid_rel],
        )

    popt_b, pcov_b, ssr_b = best_fit
    y_inf_val = float(popt_b[0])
    amp_val = float(popt_b[1])
    tau_val = float(popt_b[2])
    r2_exp = 1.0 - (ssr_b / ss_tot) if ss_tot > 1e-12 else 1.0

    res_std = math.sqrt(ssr_b / max(len(y) - 3, 1))
    u_inf_val = res_std / math.sqrt(max(len(y), 1))
    u_tau_val = float("nan")
    if pcov_b is not None and pcov_b.shape == (3, 3) and np.all(np.isfinite(pcov_b)):
        if pcov_b[0, 0] >= 0:
            u_inf_val = float(math.sqrt(pcov_b[0, 0]))
        if pcov_b[2, 2] >= 0:
            u_tau_val = float(math.sqrt(pcov_b[2, 2]))

    do_doc_con_lai = float(abs((-amp_val / max(tau_val, 1e-9)) * math.exp(-t_span / max(tau_val, 1e-9))) * 60.0)
    da_on = bool(do_doc_con_lai <= nguong)
    u_tau_out = u_tau_val if math.isfinite(u_tau_val) else None
    tau_txt = f"{tau_val:.1f} ± {u_tau_out:.1f} s" if u_tau_out is not None else f"{tau_val:.1f} s"

    if da_on:
        khuyen_nghi = (
            f"Đã ổn định nhiệt (độ trôi còn lại {do_doc_con_lai:.3f} ≤ {nguong:.3f} px/phút; "
            f"τ = {tau_txt}, Δy∞ = {y_inf_val:.3f} ± {u_inf_val:.3f} px). Có thể dùng kết quả đo."
        )
    else:
        khuyen_nghi = (
            f"Chưa ổn định nhiệt — nên đợi thêm (độ trôi còn lại {do_doc_con_lai:.3f} > {nguong:.3f} px/phút; "
            f"τ = {tau_txt}, Δy∞ ước lượng = {y_inf_val:.3f} ± {u_inf_val:.3f} px) rồi đo tiếp để xác nhận hội tụ."
        )

    duong_khop_y = _ham_mu_can_bang_nhiet(t_grid_rel, y_inf_val, amp_val, tau_val)
    return KetQuaCanBangNhiet(
        tau_s=tau_val,
        u_tau_s=u_tau_out,
        delta_y_vo_cuc_px=y_inf_val,
        u_delta_y_vo_cuc_px=float(u_inf_val),
        bien_do_A_px=amp_val,
        do_doc_con_lai_px_moi_phut=do_doc_con_lai,
        da_on_dinh=da_on,
        nguong_px_moi_phut=nguong,
        mo_hinh_khop="ham_mu",
        r2=float(r2_exp),
        thoi_gian_da_cho_s=t_span,
        khuyen_nghi=khuyen_nghi,
        duong_khop_t_s=[float(x) for x in t_grid_raw],
        duong_khop_dy_px=[float(v) for v in duong_khop_y],
    )
