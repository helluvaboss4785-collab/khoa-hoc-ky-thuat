"""Kiểm thử X1: Chế độ thu dữ liệu có hướng dẫn (chỉ kiểm logic, dữ liệu vẫn là mô phỏng)."""

from __future__ import annotations

import hashlib
import io
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from PIL import Image
from starlette.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import web_app
from core import calibration as cal
from core import nhiet_ke, optics as op, thu_du_lieu
from scripts.xuat_bao_cao import xuat_bo_bao_cao
from sim.synth import (
    ThamSoMoPhong,
    luu_anh_mo_phong_jpeg,
    sinh_anh_hai_vach_mo_phong,
)


def _tao_jpeg_exif_sach_chi_kiem_logic(
    s_ppt: float,
    t_mau: float,
    t_tc: float,
    seed: int,
    cfg: op.CauHinhQuangHoc,
) -> bytes:
    """Sinh JPEG sạch có EXIF máy ảnh giả lập từ ảnh mô phỏng — chỉ kiểm logic, dữ liệu vẫn là mô phỏng."""
    obj = sinh_anh_hai_vach_mo_phong(
        ThamSoMoPhong(
            S_ppt=s_ppt,
            T_C=t_mau,
            T_tham_chieu_C=t_tc,
            sigma_nhieu_doc=0.2,
            he_so_poisson=0.0,
            seed=seed,
        ),
        cfg=cfg,
        gan_watermark=False,
    )
    rgb = cv2.cvtColor(obj.anh, cv2.COLOR_GRAY2RGB)
    pil_im = Image.fromarray(rgb)
    ex = Image.Exif()
    ex[271] = "TestCam-X1"
    ex[272] = "MockModel-X1"
    ex[36867] = "2026:11:22 10:00:00"
    ex[34855] = 100
    buf = io.BytesIO()
    pil_im.save(buf, format="JPEG", quality=95, exif=ex.tobytes())
    return buf.getvalue()


def test_x1_thu_du_lieu_24_lan_chan_trung_va_minh_bach_loai_bo_chi_kiem_logic(monkeypatch, tmp_path: Path):
    """X1 (chỉ kiểm logic, dữ liệu vẫn là mô phỏng): thu 24 lần đo, chặn trùng sha256, chặn thiếu T_tc, chặn ảnh nhãn mô phỏng, đánh dấu loại không xóa dòng, xuất CSV dựng đường chuẩn."""
    cfg = op.CauHinhQuangHoc.tu_yaml()
    hc_nk = nhiet_ke.HieuChuanCheoNhietKe(
        offset_C=0.4,
        sigma_offset_C=0.03,
        phu_thuoc_nhiet_do=False,
        so_cap=8,
        so_muc_nhiet=3,
        ngay="2026-11-22",
        nguon_du_lieu="MO_PHONG",
        nguoi_thuc_hien="HS Kiem X1",
    )
    p_nk = nhiet_ke.luu_hieu_chuan_cheo_nhiet_ke(hc_nk, tmp_path / "hc_nk_x1.json")
    monkeypatch.setattr(web_app, "FILE_HIEU_CHUAN_NHIET_KE", p_nk)

    with TestClient(web_app.app) as client:
        # Tạo 2 phiên thu dữ liệu cho 2 mẻ pha khác nhau (12 lần mỗi mẻ = 24 lần)
        r_s1 = client.post(
            "/api/thu-du-lieu/phien",
            json={
                "ma_me_pha": "ME_X1_01",
                "id_thiet_bi": "TB_KIEM_LOGIC",
                "id_dien_thoai": "DT_KIEM_LOGIC",
                "nguoi_do": "Hoc sinh X1",
                "px_per_mm": 20.0,
                "nguon_du_lieu": "THUC_TE",
            },
        )
        assert r_s1.status_code == 200
        pid1 = r_s1.json()["phien"]["phien_id"]

        r_s2 = client.post(
            "/api/thu-du-lieu/phien",
            json={
                "ma_me_pha": "ME_X1_02",
                "id_thiet_bi": "TB_KIEM_LOGIC",
                "id_dien_thoai": "DT_KIEM_LOGIC",
                "nguoi_do": "Hoc sinh X1",
                "px_per_mm": 20.0,
                "nguon_du_lieu": "THUC_TE",
            },
        )
        assert r_s2.status_code == 200
        pid2 = r_s2.json()["phien"]["phien_id"]

        muc_s = [0.0, 10.0, 20.0, 35.0]
        muc_t = [20.0, 25.0, 30.0]
        seed_cnt = 100
        recorded_shas: list[str] = []
        first_raw_bytes: bytes | None = None

        for me_idx, pid in enumerate((pid1, pid2), start=1):
            for s_val in muc_s:
                for t_val in muc_t:
                    seed_cnt += 1
                    raw_jpg = _tao_jpeg_exif_sach_chi_kiem_logic(
                        s_ppt=s_val,
                        t_mau=t_val,
                        t_tc=t_val + 0.4,  # sau trừ offset +0.4 sẽ cân bằng T_tc = t_val
                        seed=seed_cnt,
                        cfg=cfg,
                    )
                    if first_raw_bytes is None:
                        first_raw_bytes = raw_jpg
                    form_data = {
                        "phien_id": pid,
                        "nhiet_do_C": str(t_val),
                        "nhiet_do_tham_chieu_C": str(t_val + 0.4),
                        "khoa_ae_af": "true",
                    }
                    # Dùng tính từ khối lượng cho vài mẫu để kiểm tra nhãn
                    if me_idx == 1 and s_val == 20.0 and t_val == 25.0:
                        form_data["khoi_luong_muoi_g"] = "2.0"
                        form_data["khoi_luong_nuoc_g"] = "98.0"
                    else:
                        form_data["do_man_chuan_ppt"] = str(s_val)

                    r_rec = client.post(
                        "/api/thu-du-lieu/ghi",
                        files={"file": (f"mau_{seed_cnt}.jpg", raw_jpg, "image/jpeg")},
                        data=form_data,
                    )
                    assert r_rec.status_code == 200, r_rec.text
                    js = r_rec.json()
                    recorded_shas.append(js["row"]["sha256_anh"])
                    # Kiểm tra lưu nguyên byte gốc
                    saved_p = Path(js["anh_da_luu"])
                    assert saved_p.exists()
                    assert saved_p.read_bytes() == raw_jpg
                    assert js["hieu_chuan_nhiet_ke_ap_dung"] is True
                    assert abs(float(js["row"]["nhiet_do_tham_chieu_C"]) - t_val) < 1e-3

        assert len(recorded_shas) == 24
        csv_p = thu_du_lieu.duong_dan_du_lieu_thuc_csv()
        df_saved = pd.read_csv(csv_p, encoding="utf-8-sig")
        assert len(df_saved) == 24
        assert any("tính từ khối lượng" in str(g) for g in df_saved["ghi_chu"])

        # 1. Ảnh trùng sha256 phải bị chặn (HTTP 409 ANH_TRUNG_SHA256)
        r_dup = client.post(
            "/api/thu-du-lieu/ghi",
            files={"file": ("trung.jpg", first_raw_bytes, "image/jpeg")},
            data={
                "phien_id": pid1,
                "do_man_chuan_ppt": "0.0",
                "nhiet_do_C": "20.0",
                "nhiet_do_tham_chieu_C": "20.4",
            },
        )
        assert r_dup.status_code == 409
        assert r_dup.json()["loai_loi"] == "ANH_TRUNG_SHA256"

        # 2. Thiếu nhiệt độ ngăn tham chiếu phải bị từ chối (HTTP 400)
        raw_new = _tao_jpeg_exif_sach_chi_kiem_logic(15.0, 25.0, 25.0, seed=999, cfg=cfg)
        r_no_ttc = client.post(
            "/api/thu-du-lieu/ghi",
            files={"file": ("no_ttc.jpg", raw_new, "image/jpeg")},
            data={
                "phien_id": pid1,
                "do_man_chuan_ppt": "15.0",
                "nhiet_do_C": "25.0",
            },
        )
        assert r_no_ttc.status_code == 400

        # 3. Ảnh có nhãn mô phỏng nhúng SIMULATED phải bị chặn ở chế độ THUC_TE
        obj_sim = sinh_anh_hai_vach_mo_phong(ThamSoMoPhong(S_ppt=15.0, T_C=25.0, seed=888), cfg=cfg, gan_watermark=False)
        p_sim_jpg = luu_anh_mo_phong_jpeg(obj_sim, tmp_path / "anh_gia_sim.jpg", gan_watermark=False)
        r_sim_blk = client.post(
            "/api/thu-du-lieu/ghi",
            files={"file": ("anh_chup_sach.jpg", p_sim_jpg.read_bytes(), "image/jpeg")},
            data={
                "phien_id": pid1,
                "do_man_chuan_ppt": "15.0",
                "nhiet_do_C": "25.0",
                "nhiet_do_tham_chieu_C": "25.0",
            },
        )
        assert r_sim_blk.status_code == 422
        assert r_sim_blk.json()["loai_loi"] == "ANH_MO_PHONG_BI_CHAN"

        # 4. Đánh dấu loại bỏ 1 dòng kèm lí do: không xóa dòng, dòng bị loại không vào đường chuẩn nhưng có trong báo cáo
        sha_rej = recorded_shas[5]
        r_rej_empty = client.post(
            "/api/thu-du-lieu/loai-bo",
            json={"sha256_anh": sha_rej, "ly_do_loai": "   "},
        )
        assert r_rej_empty.status_code == 400

        r_rej = client.post(
            "/api/thu-du-lieu/loai-bo",
            json={"sha256_anh": sha_rej, "ly_do_loai": "Bọt khí bám thành ngăn mẫu khi kiểm lại ảnh"},
        )
        assert r_rej.status_code == 200
        df_after_rej = pd.read_csv(csv_p, encoding="utf-8-sig")
        assert len(df_after_rej) == 24  # không xóa dòng!

        # 5. Tiến độ thiết kế V4 hiển thị đúng các ô còn thiếu
        r_st = client.get("/api/thu-du-lieu/trang-thai")
        assert r_st.status_code == 200
        td = r_st.json()["tien_do"]
        assert td["tong_dong"] == 24
        assert td["so_dong_da_loai"] == 1
        assert len(td["o_con_thieu"]) > 0
        assert td["goi_y_tiep_theo"] is not None

        # 6. CSV xuất ra nạp được bằng doc_csv_hieu_chuan (chỉ giữ 23 dòng chưa loại) và dựng đường chuẩn thành công
        r_csv = client.get("/api/thu-du-lieu/csv")
        assert r_csv.status_code == 200
        df_nap = cal.doc_csv_hieu_chuan(io.BytesIO(r_csv.content))
        assert len(df_nap) == 23
        assert df_nap.attrs["so_dong_da_loai_thu_cong"] == 1
        bc = cal.dung_duong_chuan(df_nap, cal.CauHinhHieuChuan())
        assert bc.so_dong_da_loai_thu_cong == 1
        assert bc.mo_hinh.so_diem == 23
        assert bc.mo_hinh.R2 > 0.99

        # Báo cáo xuất ra ghi nhận minh bạch số dòng đã loại thủ công và lí do
        bc_res = xuat_bo_bao_cao(csv_hieu_chuan=csv_p, out_dir=tmp_path / "bao_cao_x1")
        md_txt = Path(bc_res["tong_hop_bao_cao_md"]).read_text(encoding="utf-8")
        assert "Đã loại thủ công: `1` lần đo" in md_txt
        assert "Bọt khí bám thành ngăn mẫu" in md_txt
