"""Kiểm thử mô-đun méo ống kính tùy chọn (Q6): cảnh báo rìa ảnh và hiệu chuẩn bàn cờ."""
from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

from core.measure import do_delta_y_tu_anh
from core.ong_kinh import (
    hieu_chuan_tu_anh_ban_co,
    luu_tham_so_ong_kinh,
    tai_tham_so_ong_kinh,
)
from core.optics import CauHinhQuangHoc
from sim.synth import ThamSoMoPhong, sinh_anh_hai_vach_mo_phong

ROOT = Path(__file__).resolve().parents[1]


def _tao_bo_anh_ban_co_meo_gia(
    w: int = 480,
    h: int = 360,
    k1_true: float = -0.25,
) -> tuple[list[np.ndarray], np.ndarray, np.ndarray]:
    """Sinh 9 góc nhìn bàn cờ 9x6 theo phép chiếu 3D chuẩn K·[R|t] có méo k1_true."""
    cols, rows = 9, 6
    o_mm = 20.0
    px_per_mm_tex = 4.0
    sq = int(round(o_mm * px_per_mm_tex))
    board_w_px = (cols + 3) * sq
    board_h_px = (rows + 3) * sq
    board = np.full((board_h_px, board_w_px), 245, dtype=np.uint8)
    for r in range(rows + 1):
        for c in range(cols + 1):
            if (r + c) % 2 == 0:
                y0, x0 = (r + 1) * sq, (c + 1) * sq
                board[y0:y0 + sq, x0:x0 + sq] = 15

    # Ma trận từ pixel bàn cờ phẳng sang tọa độ thế giới Z=0 tính bằng mm (tâm tại giữa bàn cờ)
    M_b2w = np.array(
        [
            [1.0 / px_per_mm_tex, 0.0, -(board_w_px / 2.0) / px_per_mm_tex],
            [0.0, 1.0 / px_per_mm_tex, -(board_h_px / 2.0) / px_per_mm_tex],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )

    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    f_true = 420.0
    K_true = np.array([[f_true, 0.0, cx], [0.0, f_true, cy], [0.0, 0.0, 1.0]], dtype=np.float64)
    dist_true = np.array([k1_true, 0.0, 0.0, 0.0, 0.0], dtype=np.float64)

    gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    pts = np.stack([gx.ravel(), gy.ravel()], axis=-1).reshape(-1, 1, 2)
    und = cv2.undistortPoints(pts, K_true, dist_true, P=K_true).reshape(h, w, 2)
    map_x, map_y = und[:, :, 0], und[:, :, 1]

    # 9 tư thế 3D [rx, ry, rz, tx_mm, ty_mm, tz_mm] phủ cả vùng gần mép ảnh để calibrate chính xác méo k1
    poses_3d = [
        (0.05, 0.05, 0.0, 0.0, 0.0, 260.0),
        (0.30, -0.20, 0.08, -28.0, 16.0, 275.0),
        (-0.28, 0.25, -0.10, 28.0, -16.0, 270.0),
        (0.22, 0.28, 0.14, -24.0, -18.0, 280.0),
        (-0.32, -0.18, -0.12, 26.0, 18.0, 280.0),
        (0.14, -0.32, 0.04, 32.0, 5.0, 275.0),
        (-0.16, 0.30, -0.05, -32.0, -5.0, 275.0),
        (0.32, 0.10, -0.15, 8.0, 22.0, 285.0),
        (-0.28, 0.12, 0.18, -10.0, -22.0, 285.0),
    ]
    imgs = []
    for rx, ry, rz, tx, ty, tz in poses_3d:
        R, _ = cv2.Rodrigues(np.array([rx, ry, rz], dtype=np.float64))
        tvec = np.array([[tx], [ty], [tz]], dtype=np.float64)
        H_w2c = K_true @ np.hstack([R[:, :2], tvec])
        H_b2c = H_w2c @ M_b2w
        flat = cv2.warpPerspective(board, H_b2c, (w, h), borderValue=225)
        distorted = cv2.remap(flat, map_x, map_y, cv2.INTER_LINEAR, borderValue=225)
        imgs.append(distorted)

    return imgs, K_true, dist_true


def test_q6_canh_bao_meo_vung_ria_co_va_khong_k1():
    """Q6/R3: Vạch gần tâm không cảnh báo; ở rìa chỉ thành thông tin bổ sung nếu chưa có k1, và cảnh báo MEO_ONG_KINH khi có k1 hoặc hiệu chuẩn."""
    cfg = CauHinhQuangHoc.tu_yaml()
    # 1. Hai vạch gần tâm ảnh (h=300, cy=150: y_tc=130, S=4‰ -> y_mau≈150) -> lệch tâm < 30% -> không cảnh báo
    mp_tam = sinh_anh_hai_vach_mo_phong(
        ThamSoMoPhong(S_ppt=4.0, T_C=25.0, y_tham_chieu_goc=130.0, seed=1),
        cfg=cfg,
    )
    kq_tam = do_delta_y_tu_anh(mp_tam.anh, x_ref=mp_tam.x_ref, tao_anh_ve=False)
    assert kq_tam.chat_luong.canh_bao_meo_ong_kinh is False
    assert kq_tam.chat_luong.thong_tin_bo_sung == []

    # 2. Một vạch gần rìa dưới (y_tc=140, S=22‰ -> y_mau≈250 -> lệch 67% > 30%): mặc định không khai báo k1 -> KHÔNG phát MEO_ONG_KINH
    mp_ria = sinh_anh_hai_vach_mo_phong(
        ThamSoMoPhong(S_ppt=22.0, T_C=25.0, y_tham_chieu_goc=140.0, seed=2),
        cfg=cfg,
    )
    kq_no_k1 = do_delta_y_tu_anh(mp_ria.anh, x_ref=mp_ria.x_ref, tao_anh_ve=False)
    assert kq_no_k1.chat_luong.canh_bao_meo_ong_kinh is False
    assert not any(c["ma"] == "MEO_ONG_KINH" for c in kq_no_k1.chat_luong.canh_bao_chi_tiet)
    assert any(c["ma"] == "MEO_ONG_KINH_THONG_TIN" for c in kq_no_k1.chat_luong.thong_tin_bo_sung)

    # 3. Khi khai báo k1 -> phát MEO_ONG_KINH kèm cận trên px
    kq_with_k1 = do_delta_y_tu_anh(
        mp_ria.anh, x_ref=mp_ria.x_ref, he_so_meo_k1_khai_bao=0.08, tao_anh_ve=False
    )
    assert kq_with_k1.chat_luong.canh_bao_meo_ong_kinh is True
    assert any(
        c["ma"] == "MEO_ONG_KINH" and c["cap"] == "can_than" and "px" in c["noi_dung"]
        for c in kq_with_k1.chat_luong.canh_bao_chi_tiet
    )

    # 4. Khi có tham số hiệu chuẩn theo id_dien_thoai (kể cả không truyền k1 trực tiếp) -> vẫn phát cảnh báo
    kq_with_id = do_delta_y_tu_anh(
        mp_ria.anh, x_ref=mp_ria.x_ref, co_tham_so_ong_kinh_id=True, tao_anh_ve=False
    )
    assert kq_with_id.chat_luong.canh_bao_meo_ong_kinh is True
    assert any(c["ma"] == "MEO_ONG_KINH" for c in kq_with_id.chat_luong.canh_bao_chi_tiet)


def test_r3_anh_thong_thuong_khong_phat_canh_bao_meo():
    """R3: 3 ảnh mô phỏng thông thường có vạch xa tâm với cấu hình mặc định đều không phát MEO_ONG_KINH."""
    cfg = CauHinhQuangHoc.tu_yaml()
    for i, s_val in enumerate((18.0, 22.0, 28.0)):
        mp = sinh_anh_hai_vach_mo_phong(
            ThamSoMoPhong(S_ppt=s_val, T_C=25.0, y_tham_chieu_goc=140.0, seed=50 + i),
            cfg=cfg,
        )
        kq = do_delta_y_tu_anh(mp.anh, x_ref=mp.x_ref, tao_anh_ve=False)
        assert kq.chat_luong.canh_bao_meo_ong_kinh is False
        assert not any(c["ma"] == "MEO_ONG_KINH" for c in kq.chat_luong.canh_bao_chi_tiet)


def test_q6_hieu_chuan_ban_co_va_undistort_giam_lech_it_nhat_70_phan_tram(tmp_path):
    """Q6: Sau undistort từ tham số calibrateCamera, sai lệch hệ thống giảm >= 70% so với không sửa."""
    w, h = 480, 360
    k1_true = -0.25
    board_imgs, K_true, dist_true = _tao_bo_anh_ban_co_meo_gia(w=w, h=h, k1_true=k1_true)

    # Lưu ảnh bàn cờ mô phỏng vào thư mục tạm và chạy CLI scripts/hieu_chuan_ong_kinh.py
    board_dir = tmp_path / "ban_co"
    board_dir.mkdir()
    for idx, im in enumerate(board_imgs):
        cv2.imwrite(str(board_dir / f"board_{idx:02d}.png"), im)

    out_dir = tmp_path / "ong_kinh"
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "hieu_chuan_ong_kinh.py"),
            "--thu-muc", str(board_dir),
            "--id-dien-thoai", "test_cam_v2",
            "--nguon", "MO_PHONG",
            "--goc-ngang", "9",
            "--goc-doc", "6",
            "--o-mm", "20",
            "--out-dir", str(out_dir),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc.returncode == 0, f"CLI lỗi: {proc.stderr}"

    ts = tai_tham_so_ong_kinh("test_cam_v2", out_dir)
    assert ts is not None
    assert ts.sai_so_tai_chieu_px < 1.0
    assert ts.he_so_meo[0] < -0.10

    # Tạo ảnh hai vạch sạch rồi áp méo đúng (K_true, dist_true) bằng ánh xạ ngược
    cfg = CauHinhQuangHoc.tu_yaml()
    mp_sach = sinh_anh_hai_vach_mo_phong(
        ThamSoMoPhong(
            chieu_cao=h,
            chieu_rong=w,
            S_ppt=22.0,
            T_C=25.0,
            y_tham_chieu_goc=140.0,
            he_so_poisson=0.0,
            sigma_nhieu_doc=0.2,
            seed=9,
        ),
        cfg=cfg,
        gan_watermark=False,
    )
    gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    pts = np.stack([gx.ravel(), gy.ravel()], axis=-1).reshape(-1, 1, 2)
    und = cv2.undistortPoints(pts, K_true, dist_true, P=K_true).reshape(h, w, 2)
    anh_meo = cv2.remap(
        mp_sach.anh,
        und[:, :, 0],
        und[:, :, 1],
        cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )

    kq_khong_sua = do_delta_y_tu_anh(anh_meo, x_ref=mp_sach.x_ref, tao_anh_ve=False)
    kq_da_sua = do_delta_y_tu_anh(anh_meo, x_ref=mp_sach.x_ref, tham_so_ong_kinh=ts, tao_anh_ve=False)

    err_truoc = abs(kq_khong_sua.delta_y_px - mp_sach.delta_y_ly_thuyet_px)
    err_sau = abs(kq_da_sua.delta_y_px - mp_sach.delta_y_ly_thuyet_px)
    assert err_truoc > 0.3, f"Méo mô phỏng quá nhỏ ({err_truoc:.3f} px), không đủ kiểm chứng"
    giam_ti_le = (err_truoc - err_sau) / err_truoc
    assert giam_ti_le >= 0.70, f"Mức giảm lệch sau undistort chỉ {giam_ti_le*100:.1f}% < 70% (trước={err_truoc:.3f}, sau={err_sau:.3f})"

    # Kiểm thêm trên ảnh sinh trực tiếp với ThamSoMoPhong(meo_ong_kinh_k1=0.08)
    from core.ong_kinh import ThamSoOngKinh
    mp_k1 = sinh_anh_hai_vach_mo_phong(
        ThamSoMoPhong(S_ppt=20.0, T_C=25.0, meo_ong_kinh_k1=0.08, he_so_poisson=0.0, sigma_nhieu_doc=0.2, seed=5),
        cfg=cfg,
    )
    h2, w2 = mp_k1.anh.shape
    cx2, cy2 = (w2 - 1) / 2.0, (h2 - 1) / 2.0
    r_sc = math.hypot(cx2, cy2)
    ts_sim = ThamSoOngKinh(
        id_dien_thoai="sim_k1",
        chieu_rong_px=w2,
        chieu_cao_px=h2,
        ma_tran_camera=[[r_sc, 0.0, cx2], [0.0, r_sc, cy2], [0.0, 0.0, 1.0]],
        he_so_meo=[0.08, 0.0, 0.0, 0.0, 0.0],
        sai_so_tai_chieu_px=0.0,
        so_anh_su_dung=0,
        nguon_du_lieu="MO_PHONG",
    )
    e_raw = abs(do_delta_y_tu_anh(mp_k1.anh, x_ref=mp_k1.x_ref, tao_anh_ve=False).delta_y_px - mp_k1.delta_y_ly_thuyet_px)
    e_fix = abs(do_delta_y_tu_anh(mp_k1.anh, x_ref=mp_k1.x_ref, tham_so_ong_kinh=ts_sim, tao_anh_ve=False).delta_y_px - mp_k1.delta_y_ly_thuyet_px)
    assert e_raw > 0.3 and (e_raw - e_fix) / e_raw >= 0.70
