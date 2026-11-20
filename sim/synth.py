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
- MỌI ẢNH ĐỀU ĐƯỢC GẮN METADATA `{"NGUON": "SIMULATED"}`; khi gọi trực tiếp trong bộ nhớ `gan_watermark` mặc định `False` để không che nhiễu kiểm thử, và mặc định bật watermark + file JSON đi kèm khi lưu ảnh ra file.
"""
from __future__ import annotations

import json
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

    # Hiệu ứng quang học / cảm biến nâng cao (T9 — mặc định TẮT để giữ nguyên test cơ sở)
    speckle_cuong_do: float = 0.0          # Đốm laser nhân tính tương quan không gian (0 = tắt)
    meo_ong_kinh_k1: float = 0.0           # Méo xuyên tâm ống kính bậc 1 k1 (0 = tắt)
    gradient_nen_y: float = 0.0            # Gradient ánh sáng nền theo trục y (mức xám, 0 = tắt)
    do_cong_vach: float = 0.0              # Độ cong parabol của vạch tại hai rìa ảnh (px, 0 = tắt)
    chenh_sang_hai_nua: float = 0.0        # Độ suy giảm biên độ nửa trái vạch (0..0.95, 0 = tắt)
    gamma_cam_bien: float = 1.0            # Đáp ứng phi tuyến cảm biến I^(1/gamma) (1.0 = tuyến tính)
    chat_luong_jpeg: int | None = None     # Chất lượng nén JPEG (1..100; None = không nén mất dữ liệu)


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


def _ve_watermark_mo_phong(img: np.ndarray) -> np.ndarray:
    """Đóng nhãn SIMULATED rõ ràng ở góc dưới ảnh."""
    h = img.shape[0]
    cv2.putText(
        img,
        "SIMULATED - DU LIEU MO PHONG",
        (10, max(16, h - 12)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.40,
        160,
        1,
        cv2.LINE_AA,
    )
    return img


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

    # 3. Tạo tín hiệu lý thuyết (kèm gradient nền, độ cong, chênh sáng hai nửa nếu bật)
    img_ideal = np.full((h, w), p.cuong_do_nen, dtype=float)
    y_coords = np.arange(h)[:, None]  # shape (h, 1)
    if p.gradient_nen_y != 0.0:
        img_ideal += float(p.gradient_nen_y) * (y_coords / max(h - 1, 1))

    nua_khe = p.be_day_vach_ngan_px // 2
    nua_rong = max(w / 2.0, 1.0)
    x_mid_tc = (x_ref - nua_khe) / 2.0
    x_mid_m = (x_ref + nua_khe + w) / 2.0
    he_so_giam_nua = max(0.05, 1.0 - float(np.clip(p.chenh_sang_hai_nua, 0.0, 0.95)))

    for col in range(w):
        dx = col - x_ref
        cong = float(p.do_cong_vach) * ((dx / nua_rong) ** 2) if p.do_cong_vach != 0.0 else 0.0
        mu_tc_col = y_tc_ground_truth + p.do_doc_vach * dx + cong
        mu_mau_col = y_mau_ground_truth + p.do_doc_vach * dx + cong

        if p.bo_tri == "ngang":
            # Ngăn tham chiếu bên trái, ngăn mẫu bên phải
            if col < (x_ref - nua_khe):
                ty_le_tc = he_so_giam_nua if (p.chenh_sang_hai_nua > 0.0 and col < x_mid_tc) else 1.0
                line_tc = (amp_tc * ty_le_tc) * np.exp(-((y_coords - mu_tc_col) ** 2) / (2.0 * sigma_tc**2))
                img_ideal[:, col] += line_tc.squeeze()
            elif col > (x_ref + nua_khe):
                ty_le_m = he_so_giam_nua if (p.chenh_sang_hai_nua > 0.0 and col < x_mid_m) else 1.0
                line_mau = (amp_mau * ty_le_m) * np.exp(-((y_coords - mu_mau_col) ** 2) / (2.0 * sigma_mau**2))
                if do_duc_clip > 0.05:
                    sigma_halo = sigma_mau * 4.0
                    amp_halo = amp_tc * 0.25 * do_duc_clip * ty_le_m
                    line_mau += amp_halo * np.exp(-((y_coords - mu_mau_col) ** 2) / (2.0 * sigma_halo**2))
                img_ideal[:, col] += line_mau.squeeze()
        else:
            ty_le = he_so_giam_nua if (p.chenh_sang_hai_nua > 0.0 and col < x_ref) else 1.0
            line_tc = (amp_tc * ty_le) * np.exp(-((y_coords - mu_tc_col) ** 2) / (2.0 * sigma_tc**2))
            line_mau = (amp_mau * ty_le) * np.exp(-((y_coords - mu_mau_col) ** 2) / (2.0 * sigma_mau**2))
            img_ideal[:, col] += (line_tc + line_mau).squeeze()

    # 3b. Đốm laser (speckle tương quan không gian, nhiễu nhân tính) & méo ống kính bậc k1
    if p.speckle_cuong_do > 0.0:
        sp_raw = rng.normal(0.0, 1.0, size=(h, w))
        sp_corr = cv2.GaussianBlur(sp_raw, (5, 5), 1.2)
        sp_std = max(float(np.std(sp_corr)), 1e-6)
        img_ideal = img_ideal * np.clip(1.0 + float(p.speckle_cuong_do) * (sp_corr / sp_std), 0.0, None)

    if p.meo_ong_kinh_k1 != 0.0:
        cx = (w - 1) / 2.0
        cy = (h - 1) / 2.0
        scale_r = max(math.hypot(cx, cy), 1.0)
        gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
        r2 = ((gx - cx) / scale_r) ** 2 + ((gy - cy) / scale_r) ** 2
        map_x = (cx + (gx - cx) * (1.0 - float(p.meo_ong_kinh_k1) * r2)).astype(np.float32)
        map_y = (cy + (gy - cy) * (1.0 - float(p.meo_ong_kinh_k1) * r2)).astype(np.float32)
        img_ideal = cv2.remap(img_ideal, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

    # 4. Thêm nhiễu vật lí thực tế
    img_noisy = img_ideal.copy()

    if p.he_so_poisson > 0:
        gain = 5.0 / p.he_so_poisson
        poisson_sample = rng.poisson(np.clip(img_noisy, 0, None) * gain) / gain
        img_noisy = poisson_sample

    if p.sigma_nhieu_doc > 0:
        read_noise = rng.normal(0, p.sigma_nhieu_doc, size=(h, w))
        img_noisy += read_noise

    # 5. Bão hòa (clipping), đáp ứng phi tuyến (gamma) và lượng tử hóa
    if p.cho_phep_bao_hoa:
        img_noisy = np.clip(img_noisy * 1.6, 0, 255)
    else:
        img_noisy = np.clip(img_noisy, 0, 255)

    if p.gamma_cam_bien != 1.0 and p.gamma_cam_bien > 0.0:
        img_noisy = 255.0 * ((np.clip(img_noisy, 0.0, 255.0) / 255.0) ** (1.0 / float(p.gamma_cam_bien)))

    img_uint8 = np.round(np.clip(img_noisy, 0.0, 255.0)).astype(np.uint8)

    if p.chat_luong_jpeg is not None:
        q = int(np.clip(p.chat_luong_jpeg, 1, 100))
        ok_jpg, buf_jpg = cv2.imencode(".jpg", img_uint8, [cv2.IMWRITE_JPEG_QUALITY, q])
        if ok_jpg:
            decoded = cv2.imdecode(buf_jpg, cv2.IMREAD_GRAYSCALE)
            if decoded is not None:
                img_uint8 = decoded

    # 6. Gắn watermark rõ ràng nhưng ở góc dưới ảnh để không che mất đường quang học
    if gan_watermark:
        _ve_watermark_mo_phong(img_uint8)

    metadata = {
        "NGUON": "SIMULATED",
        "CANH_BAO": "Dữ liệu mô phỏng vật lí, KHÔNG phải số đo thực tế",
        "da_gan_watermark": bool(gan_watermark),
        "do_man_S_ppt": p.S_ppt,
        "nhiet_do_T_C": p.T_C,
        "nhiet_do_tham_chieu_C": p.T_tham_chieu_C,
        "delta_y_ly_thuyet_px": delta_y_snell,
        "y_tc_ly_thuyet": y_tc_ground_truth,
        "y_mau_ly_thuyet": y_mau_ground_truth,
        "x_ref": x_ref,
        "do_duc": p.do_duc,
        "drift_chung_px": p.drift_chung_px,
        "speckle_cuong_do": p.speckle_cuong_do,
        "meo_ong_kinh_k1": p.meo_ong_kinh_k1,
        "gradient_nen_y": p.gradient_nen_y,
        "do_cong_vach": p.do_cong_vach,
        "chenh_sang_hai_nua": p.chenh_sang_hai_nua,
        "gamma_cam_bien": p.gamma_cam_bien,
        "chat_luong_jpeg": p.chat_luong_jpeg,
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


def sinh_anh_mau_mo_phong(
    p: ThamSoMoPhong,
    cfg: CauHinhQuangHoc | None = None,
    ty_le_kenh: tuple[float, float, float] = (1.0, 0.35, 0.35),
    gan_watermark: bool = False,
) -> AnhMoPhong:
    """Sinh ảnh MÀU BGR 3 kênh mô phỏng laser đỏ/lục (mặc định R=1.0, G=B=0.35).

    Dùng để kiểm chứng hiện tượng trộn ảnh xám làm giảm tương phản hoặc che lấp bão hòa ở một kênh đơn sắc.
    """
    base = sinh_anh_hai_vach_mo_phong(p, cfg=cfg, gan_watermark=False)
    r_w, g_w, b_w = float(ty_le_kenh[0]), float(ty_le_kenh[1]), float(ty_le_kenh[2])
    raw_f = base.anh.astype(float)
    tin_hieu = np.clip(raw_f - float(p.cuong_do_nen), 0.0, None)
    img_bgr = np.empty((p.chieu_cao, p.chieu_rong, 3), dtype=np.uint8)
    for ch_idx, w_ch in ((0, b_w), (1, g_w), (2, r_w)):
        val_ch = float(p.cuong_do_nen) + tin_hieu * w_ch
        img_bgr[:, :, ch_idx] = np.round(np.clip(val_ch, 0.0, 255.0)).astype(np.uint8)
    if gan_watermark:
        cv2.putText(
            img_bgr,
            "SIMULATED - DU LIEU MO PHONG",
            (10, max(16, p.chieu_cao - 12)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.40,
            (160, 160, 160),
            1,
            cv2.LINE_AA,
        )
    meta = dict(base.metadata)
    meta["da_gan_watermark"] = bool(gan_watermark)
    meta["ty_le_kenh_RGB"] = [r_w, g_w, b_w]
    return AnhMoPhong(
        anh=img_bgr,
        delta_y_ly_thuyet_px=base.delta_y_ly_thuyet_px,
        y_tc_ly_thuyet=base.y_tc_ly_thuyet,
        y_mau_ly_thuyet=base.y_mau_ly_thuyet,
        x_ref=base.x_ref,
        tham_so=p,
        metadata=meta,
    )


def luu_anh_mo_phong_png(
    anh_mp: AnhMoPhong,
    duong_dan: str | Path,
    gan_watermark: bool = True,
) -> Path:
    """Lưu ảnh mô phỏng ra đĩa: mặc định bật watermark và luôn ghi file .json cạnh ảnh."""
    p_path = Path(duong_dan)
    p_path.parent.mkdir(parents=True, exist_ok=True)
    img_out = anh_mp.anh.copy()
    da_wm = bool(anh_mp.metadata.get("da_gan_watermark", False))
    if gan_watermark and not da_wm:
        _ve_watermark_mo_phong(img_out)
        da_wm = True
    cv2.imwrite(str(p_path), img_out)
    meta_out = {"simulated": True, **anh_mp.metadata, "da_gan_watermark": da_wm}
    p_path.with_suffix(".json").write_text(
        json.dumps(meta_out, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return p_path


def sinh_du_lieu_hieu_chuan_mo_phong(
    cfg: CauHinhQuangHoc | None = None,
    muc_S: tuple[float, ...] = (0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0),
    muc_T: tuple[float, ...] = (22.0, 25.0, 28.0),
    so_lan_lap: int = 3,
    sigma_delta_y_px: float = 0.05,
    sigma_nhiet_ke_C: float = 0.1,
    T_tham_chieu_C: float | tuple[float, ...] | list[float] | None = None,
    seed: int = 0,
) -> "pd.DataFrame":
    """Sinh bảng dữ liệu hiệu chuẩn MÔ PHỎNG (cùng định dạng CSV đo thật).

    - Δy "thật" tính bằng mô hình Snell (core.optics); cộng nhiễu Gauss σ_Δy.
    - Nhiệt độ ghi lại = nhiệt độ thật + sai số nhiệt kế N(0, σ_T).
    - T_tham_chieu_C = None: giả định ngăn tham chiếu cân bằng nhiệt với mẫu (không ghi cột T_tc).
      Nếu truyền số hoặc danh sách nhiệt độ ngăn tham chiếu: ghi cột nhiet_do_tham_chieu_C độc lập.
    - MỌI DÒNG có nguon_du_lieu = "MO_PHONG" để chương trình hiển thị nhãn
      "CHƯA HIỆU CHUẨN – DỮ LIỆU MÔ PHỎNG". Đây KHÔNG phải số đo.
    """
    import pandas as pd

    from core import calibration as cal

    if cfg is None:
        cfg = CauHinhQuangHoc.tu_yaml()
    rng = np.random.default_rng(seed)

    if T_tham_chieu_C is None:
        ds_T_tc: list[float | None] = [None]
    elif isinstance(T_tham_chieu_C, (tuple, list)):
        ds_T_tc = [float(x) for x in T_tham_chieu_C]
    else:
        ds_T_tc = [float(T_tham_chieu_C)]

    dong = []
    for S in muc_S:
        for T in muc_T:
            for T_tc_muc in ds_T_tc:
                for lap in range(so_lan_lap):
                    T_tc_that = T if T_tc_muc is None else T_tc_muc
                    dy = delta_y_vi_sai_px(S, T, T_tc_that, cfg) + rng.normal(0.0, sigma_delta_y_px)
                    rec = {
                        cal.COT_DO_MAN: float(S),
                        cal.COT_NHIET_DO: float(T + rng.normal(0.0, sigma_nhiet_ke_C)),
                        cal.COT_DELTA_Y: float(dy),
                        cal.COT_DO_DUC: 0.0,
                        cal.COT_GHI_CHU: f"DỮ LIỆU MÔ PHỎNG – KHÔNG PHẢI ĐO THẬT (lần {lap + 1})",
                        cal.COT_ID_THIET_BI: "MO_PHONG",
                        cal.COT_ID_DIEN_THOAI: "MO_PHONG",
                        cal.COT_NGUON: cal.NHAN_MO_PHONG,
                    }
                    if T_tc_muc is not None:
                        rec[cal.COT_NHIET_DO_TC] = float(T_tc_muc + rng.normal(0.0, sigma_nhiet_ke_C))
                    dong.append(rec)
    df = pd.DataFrame(dong)
    df.attrs["gia_dinh_can_bang_nhiet"] = T_tham_chieu_C is None
    return df
