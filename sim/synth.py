"""Bộ sinh ảnh mô phỏng vật lí quang học lăng kính hai ngăn (Cột mốc 3).

Vật lí & Mô hình mô phỏng:
- Mọi ảnh sinh ra từ mô-đun này đều là DỮ LIỆU MÔ PHỎNG (SIMULATED), phục vụ kiểm thử
  thuật toán xử lí ảnh, kiểm tra độ nhạy và độ bền vững trước nhiễu.
- Bố trí thực tế của lăng kính hai ngăn:
  Module laser vạch chiếu ngang qua lăng kính rỗng chia hai ngăn:
  * Nửa bên trái: tia laser đi qua ngăn tham chiếu (nước cất, đóng kín) -> tạo đoạn vạch bên trái.
  * Nửa bên phải: tia laser đi qua ngăn mẫu -> tạo đoạn vạch bên phải.
  * Giữa hai ngăn có vách ngăn mỏng (khoảng 10-20 px không có tia hoặc bị tối).
  * Khi S = 0 (cùng nước cất): hai đoạn vạch nằm thẳng hàng ngang (Δy = 0).
  * Khi S > 0: đoạn vạch bên phải lệch đứng một khoảng Δy theo định luật Snell.
- Mô hình nhiễu cảm biến camera thực tế:
  1. Photon Shot Noise (nhiễu Poisson): bản chất lượng tử của photon tới pixel.
  2. Read Noise (nhiễu đọc cảm biến CMOS): nhiễu Gauss từ mạch khuếch đại và ADC.
  3. Độ trôi chung (Common Drift): mô phỏng nhiệt làm dời nguồn laser hoặc rung tay cầm máy ảnh.
  4. Độ đục môi trường: tán xạ làm phình to độ rộng FWHM và suy giảm cường độ theo Beer-Lambert.
  5. Bão hòa (Clipping): bệt đỉnh tại mức 255 nếu phơi sáng quá mức.
- MỌI ẢNH ĐỀU ĐƯỢC GẮN NHÃN METADATA "SIMULATED" VÀ WATERMARK BẮT BUỘC.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import cv2
import numpy as np

from core.optics import CauHinhQuangHoc, delta_y_vi_sai_px


@dataclass(frozen=True)
class ThamSoMoPhong:
    """Tham số đầu vào để tạo ảnh mô phỏng."""

    S_ppt: float = 15.0                    # Độ mặn ngăn mẫu (‰)
    T_C: float = 25.0                      # Nhiệt độ ngăn mẫu (°C)
    T_tham_chieu_C: float = 25.0           # Nhiệt độ ngăn tham chiếu (°C)
    drift_chung_px: float = 0.0            # Dịch chuyển chung cả 2 vạch (px) do rung/trôi
    do_duc: float = 0.0                    # Chỉ số độ đục mẫu (0.0: nước trong, 1.0: rất đục)
    
    bo_tri: Literal["ngang", "doc"] = "ngang"  # "ngang" (trái-phải thực tế) hoặc "doc" (trên-dưới)
    chieu_cao: int = 300                   # Chiều cao ảnh (px)
    chieu_rong: int = 400                  # Chiều rộng ảnh (px)
    y_tham_chieu_goc: float = 80.0         # Vị trí đứng gốc của vạch tham chiếu (px)
    do_doc_vach: float = 0.01              # Độ nghiêng góc vạch (px/px)
    be_day_vach_ngan_px: int = 16          # Độ rộng khe tối của vách ngăn giữa 2 ngăn
    
    fwhm_goc_px: float = 3.5               # Độ rộng FWHM chuẩn của vạch laser (px)
    cuong_do_dinh_goc: float = 200.0       # Biên độ cường độ laser (0-255)
    cuong_do_nen: float = 15.0             # Mức sáng nền môi trường trung bình
    
    he_so_poisson: float = 0.3             # Cường độ nhiễu Poisson (shot noise)
    sigma_nhieu_doc: float = 1.5           # Độ lệch chuẩn nhiễu đọc Gauss (read noise)
    cho_phep_bao_hoa: bool = False         # Cố tình gây cháy sáng bão hòa tại 255
    seed: int | None = 42                  # Seed ngẫu nhiên để tái lập kết quả


@dataclass(frozen=True)
class AnhMoPhong:
    """Kết quả sinh ảnh mô phỏng kèm dữ liệu chân lí mặt đất (Ground Truth)."""

    anh: np.ndarray                        # Mảng ảnh mức xám uint8 (H, W)
    delta_y_ly_thuyet_px: float            # Δy chân lí mặt đất theo quang học Snell
    y_tc_ly_thuyet: float                  # Vị trí vạch tham chiếu chân lí tại x_ref
    y_mau_ly_thuyet: float                 # Vị trí vạch mẫu chân lí tại x_ref
    x_ref: float                           # Cột tham chiếu trung tâm
    tham_so: ThamSoMoPhong                 # Tham số đầu vào đã dùng
    metadata: dict[str, Any] = field(default_factory=dict)


def sinh_anh_hai_vach_mo_phong(
    p: ThamSoMoPhong,
    cfg: CauHinhQuangHoc | None = None,
    gan_watermark: bool = False,
) -> AnhMoPhong:
    """Sinh ảnh mô phỏng màn hứng 2 đoạn vạch laser dựa trên mô hình quang học chính xác.

    Lưu ý: Mọi ảnh mô phỏng đều được gắn nhãn metadata {"NGUON": "SIMULATED"}.
    """
    if cfg is None:
        cfg = CauHinhQuangHoc.tu_yaml()

    if p.seed is not None:
        rng = np.random.default_rng(p.seed)
    else:
        rng = np.random.default_rng()

    h, w = p.chieu_cao, p.chieu_rong
    x_ref = float(w / 2.0)

    # 1. Tính độ lệch vi sai Δy chân lí từ định luật Snell chính xác (core.optics)
    delta_y_snell = delta_y_vi_sai_px(
        S_ppt=p.S_ppt,
        T_mau_C=p.T_C,
        T_thamchieu_C=p.T_tham_chieu_C,
        cfg=cfg,
    )

    y_tc_ground_truth = p.y_tham_chieu_goc + p.drift_chung_px
    y_mau_ground_truth = p.y_tham_chieu_goc + delta_y_snell + p.drift_chung_px

    # 2. Đặc tính hình dạng vạch
    fwhm_tc = p.fwhm_goc_px
    sigma_tc = fwhm_tc / (2.0 * math.sqrt(2.0 * math.log(2.0)))
    amp_tc = p.cuong_do_dinh_goc

    do_duc_clip = float(np.clip(p.do_duc, 0.0, 1.0))
    fwhm_mau = p.fwhm_goc_px * (1.0 + 2.5 * do_duc_clip)
    sigma_mau = fwhm_mau / (2.0 * math.sqrt(2.0 * math.log(2.0)))
    amp_mau = p.cuong_do_dinh_goc * math.exp(-1.8 * do_duc_clip)

    # 3. Tạo tín hiệu lý thuyết
    img_ideal = np.full((h, w), p.cuong_do_nen, dtype=float)
    y_coords = np.arange(h)[:, None]  # shape (h, 1)

    nua_khe = p.be_day_vach_ngan_px // 2

    for col in range(w):
        dx = col - x_ref
        mu_tc_col = y_tc_ground_truth + p.do_doc_vach * dx
        mu_mau_col = y_mau_ground_truth + p.do_doc_vach * dx

        if p.bo_tri == "ngang":
            # Bố trí lăng kính hai ngăn cạnh nhau theo phương ngang:
            # Ngăn tham chiếu bên trái, ngăn mẫu bên phải
            if col < (x_ref - nua_khe):
                # Chỉ có vạch tham chiếu
                line_tc = amp_tc * np.exp(-((y_coords - mu_tc_col) ** 2) / (2.0 * sigma_tc**2))
                img_ideal[:, col] += line_tc.squeeze()
            elif col > (x_ref + nua_khe):
                # Chỉ có vạch mẫu
                line_mau = amp_mau * np.exp(-((y_coords - mu_mau_col) ** 2) / (2.0 * sigma_mau**2))
                if do_duc_clip > 0.05:
                    sigma_halo = sigma_mau * 4.0
                    amp_halo = amp_tc * 0.25 * do_duc_clip
                    line_mau += amp_halo * np.exp(-((y_coords - mu_mau_col) ** 2) / (2.0 * sigma_halo**2))
                img_ideal[:, col] += line_mau.squeeze()
            else:
                # Khe tối vách ngăn giữa hai ngăn
                pass
        else:
            # Bố trí vạch trên - vạch dưới
            line_tc = amp_tc * np.exp(-((y_coords - mu_tc_col) ** 2) / (2.0 * sigma_tc**2))
            line_mau = amp_mau * np.exp(-((y_coords - mu_mau_col) ** 2) / (2.0 * sigma_mau**2))
            img_ideal[:, col] += (line_tc + line_mau).squeeze()

    # 4. Thêm nhiễu vật lí thực tế
    img_noisy = img_ideal.copy()

    if p.he_so_poisson > 0:
        gain = 5.0 / p.he_so_poisson
        poisson_sample = rng.poisson(np.clip(img_noisy, 0, None) * gain) / gain
        img_noisy = poisson_sample

    if p.sigma_nhieu_doc > 0:
        read_noise = rng.normal(0, p.sigma_nhieu_doc, size=(h, w))
        img_noisy += read_noise

    # 5. Bão hòa (clipping) và lượng tử hóa
    if p.cho_phep_bao_hoa:
        img_noisy = np.clip(img_noisy * 1.6, 0, 255)
    else:
        img_noisy = np.clip(img_noisy, 0, 255)

    img_uint8 = np.round(img_noisy).astype(np.uint8)

    # 6. Gắn watermark rõ ràng nhưng ở góc dưới ảnh để không che mất đường quang học
    if gan_watermark:
        cv2.putText(
            img_uint8,
            "SIMULATED - DU LIEU MO PHONG",
            (10, h - 12),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.40,
            160,
            1,
            cv2.LINE_AA,
        )

    metadata = {
        "NGUON": "SIMULATED",
        "CANH_BAO": "Dữ liệu mô phỏng vật lí, KHÔNG phải số đo thực tế",
        "do_man_S_ppt": p.S_ppt,
        "nhiet_do_T_C": p.T_C,
        "delta_y_ly_thuyet_px": delta_y_snell,
        "y_tc_ly_thuyet": y_tc_ground_truth,
        "y_mau_ly_thuyet": y_mau_ground_truth,
        "x_ref": x_ref,
        "do_duc": p.do_duc,
        "drift_chung_px": p.drift_chung_px,
    }

    return AnhMoPhong(
        anh=img_uint8,
        delta_y_ly_thuyet_px=delta_y_snell,
        y_tc_ly_thuyet=y_tc_ground_truth,
        y_mau_ly_thuyet=y_mau_ground_truth,
        x_ref=x_ref,
        tham_so=p,
        metadata=metadata,
    )


def luu_anh_mo_phong_png(anh_mp: AnhMoPhong, duong_dan: str | Path) -> None:
    """Lưu ảnh mô phỏng ra đĩa với nhãn cảnh báo rõ ràng."""
    p_path = Path(duong_dan)
    p_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(p_path), anh_mp.anh)


def sinh_du_lieu_hieu_chuan_mo_phong(
    cfg: CauHinhQuangHoc | None = None,
    muc_S: tuple[float, ...] = (0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0),
    muc_T: tuple[float, ...] = (22.0, 25.0, 28.0),
    so_lan_lap: int = 3,
    sigma_delta_y_px: float = 0.05,
    sigma_nhiet_ke_C: float = 0.1,
    T_tham_chieu_C: float | None = None,
    seed: int = 0,
) -> "pd.DataFrame":
    """Sinh bảng dữ liệu hiệu chuẩn MÔ PHỎNG (cùng định dạng CSV đo thật).

    - Δy "thật" tính bằng mô hình Snell (core.optics); cộng nhiễu Gauss σ_Δy.
    - Nhiệt độ ghi lại = nhiệt độ thật + sai số nhiệt kế N(0, σ_T).
    - T_tham_chieu_C = None: ngăn tham chiếu cùng nhiệt độ với mẫu (cùng ngâm một chậu nước);
      nếu cho một số: ngăn tham chiếu giữ ở nhiệt độ đó.
    - MỌI DÒNG có nguon_du_lieu = "MO_PHONG" để chương trình hiển thị nhãn
      "CHƯA HIỆU CHUẨN – DỮ LIỆU MÔ PHỎNG". Đây KHÔNG phải số đo.
    """
    import pandas as pd

    from core import calibration as cal

    if cfg is None:
        cfg = CauHinhQuangHoc.tu_yaml()
    rng = np.random.default_rng(seed)
    dong = []
    for S in muc_S:
        for T in muc_T:
            for lap in range(so_lan_lap):
                T_tc = T if T_tham_chieu_C is None else T_tham_chieu_C
                dy = delta_y_vi_sai_px(S, T, T_tc, cfg) + rng.normal(0.0, sigma_delta_y_px)
                dong.append({
                    cal.COT_DO_MAN: float(S),
                    cal.COT_NHIET_DO: float(T + rng.normal(0.0, sigma_nhiet_ke_C)),
                    cal.COT_DELTA_Y: float(dy),
                    cal.COT_DO_DUC: 0.0,
                    cal.COT_GHI_CHU: f"DỮ LIỆU MÔ PHỎNG – KHÔNG PHẢI ĐO THẬT (lần {lap + 1})",
                    cal.COT_ID_THIET_BI: "MO_PHONG",
                    cal.COT_ID_DIEN_THOAI: "MO_PHONG",
                    cal.COT_NGUON: cal.NHAN_MO_PHONG,
                })
    return pd.DataFrame(dong)
