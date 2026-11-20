"""Unit tests cho core/thresholds.py: Đánh giá ngưỡng tham chiếu và nguồn tài liệu."""
from __future__ import annotations

from pathlib import Path

from core import thresholds as th


def _ghi_yaml_thu_nghiem(tmp_path: Path) -> Path:
    p = tmp_path / "config_thu_nghiem.yaml"
    p.write_text(
        """
nguong_loai:
  tom_thu_nghiem:
    ten: "Tôm thử nghiệm (GIÁ TRỊ THỬ NGHIỆM, KHÔNG PHẢI NGƯỠNG THẬT)"
    an_toan: [10.0, 25.0]
    canh_bao_thap: [5.0, 10.0]
    canh_bao_cao: [25.0, 35.0]
    nguy_hiem_duoi: 5.0
    nguy_hiem_tren: 35.0
    nguon_tham_khao: "GIÁ TRỊ THỬ NGHIỆM, KHÔNG PHẢI NGƯỠNG THẬT"
    giai_doan:
      - ten: "Giai đoạn giống (GIÁ TRỊ THỬ NGHIỆM)"
        an_toan: [15.0, 22.0]
        canh_bao_thap: [10.0, 15.0]
        canh_bao_cao: [22.0, 28.0]
        nguy_hiem_duoi: 10.0
        nguy_hiem_tren: 28.0
        nguon_tham_khao: "GIÁ TRỊ THỬ NGHIỆM, KHÔNG PHẢI NGƯỠNG THẬT (giai đoạn)"

  cay_thu_nghiem:
    ten: "Cây thử nghiệm (GIÁ TRỊ THỬ NGHIỆM, KHÔNG PHẢI NGƯỠNG THẬT)"
    an_toan: [0.0, 0.5]
    canh_bao_thap: null
    canh_bao_cao: [0.5, 1.0]
    nguy_hiem_duoi: null
    nguy_hiem_tren: 1.0
    nguon_tham_khao: "GIÁ TRỊ THỬ NGHIỆM, KHÔNG PHẢI NGƯỠNG THẬT"

  chua_co_nguon:
    ten: "Loài chưa có nguồn"
    an_toan: null
    canh_bao_thap: null
    canh_bao_cao: null
    nguy_hiem_duoi: null
    nguy_hiem_tren: null
    nguon_tham_khao: ""
""".strip(),
        encoding="utf-8",
    )
    return p


def test_config_that_khong_co_nguong_thieu_nguon():
    """Trong config.yaml thật, không được có ngưỡng khác null mà nguon_tham_khao rỗng."""
    ds = th.doc_danh_sach_loai()
    assert len(ds) >= 5
    for ma, loai in ds.items():
        if loai.co_bat_ky_nguong():
            assert loai.co_du_lieu_nguon, f"Loài '{ma}' có ngưỡng nhưng thiếu nguồn tham khảo!"
        for gd in loai.giai_doan:
            if gd.co_bat_ky_nguong():
                assert gd.co_du_lieu_nguon, f"Giai đoạn '{gd.ten_giai_doan}' của '{ma}' thiếu nguồn!"


def test_loai_chua_co_nguon_phai_canh_bao():
    """Mọi loài trong config.yaml hiện chưa điền nguồn đều phải trả CHUA_CO_NGUON."""
    ds = th.doc_danh_sach_loai()
    cua = ds["cua_bien"]
    assert cua.co_du_lieu_nguon is False

    kq = th.danh_gia_do_man_loai(15.0, cua)
    assert kq.trang_thai == "CHUA_CO_NGUON"
    assert "CHƯA CÓ" in kq.tieu_de
    assert th.TU_VAN_KHUYEN_NONG in kq.loi_khuyen


def test_danh_gia_muc_an_toan_tren_yaml_thu_nghiem(tmp_path: Path):
    """Dùng YAML tạm với GIÁ TRỊ THỬ NGHIỆM để kiểm tra logic phân mức an toàn/cảnh báo/nguy hiểm."""
    ds = th.doc_danh_sach_loai(_ghi_yaml_thu_nghiem(tmp_path))
    tom = ds["tom_thu_nghiem"]

    kq_at = th.danh_gia_do_man_loai(15.0, tom, U=0.25)
    assert kq_at.trang_thai == "AN_TOAN"
    assert "± 0.25" in kq_at.loi_khuyen
    assert th.TU_VAN_KHUYEN_NONG in kq_at.loi_khuyen

    kq_cb = th.danh_gia_do_man_loai(28.0, tom)
    assert kq_cb.trang_thai == "CANH_BAO"

    kq_ng = th.danh_gia_do_man_loai(38.0, tom)
    assert kq_ng.trang_thai == "NGUY_HIEM"
    for cum_tu_cam in ("Đóng ngay cống", "khoáng tạt", "TUYỆT ĐỐI KHÔNG"):
        assert cum_tu_cam not in kq_ng.loi_khuyen
    assert th.TU_VAN_KHUYEN_NONG in kq_ng.loi_khuyen


def test_danh_gia_cay_nhay_cam_va_giai_doan(tmp_path: Path):
    """Kiểm tra ngưỡng thử nghiệm cây nhạy cảm và trường tùy chọn giai_doan."""
    ds = th.doc_danh_sach_loai(_ghi_yaml_thu_nghiem(tmp_path))
    cay = ds["cay_thu_nghiem"]
    assert th.danh_gia_do_man_loai(0.3, cay).trang_thai == "AN_TOAN"
    assert th.danh_gia_do_man_loai(1.2, cay).trang_thai == "NGUY_HIEM"

    tom = ds["tom_thu_nghiem"]
    kq_gd = th.danh_gia_do_man_loai(11.0, tom, giai_doan="Giai đoạn giống (GIÁ TRỊ THỬ NGHIỆM)")
    assert kq_gd.trang_thai == "CANH_BAO"
    assert "Giai đoạn giống" in kq_gd.ten_loai


def test_phan_loai_theo_khoang_bat_dinh_U(tmp_path: Path):
    """T6: Phân loại dựa trên khoảng [S - U, S + U] gồm 3 trường hợp + KHONG_DANH_GIA_DUOC."""
    ds = th.doc_danh_sach_loai(_ghi_yaml_thu_nghiem(tmp_path))
    tom = ds["tom_thu_nghiem"]  # an_toan=[10, 25], canh_bao=[5..10, 25..35], nguy_hiem=<5, >35

    # 1. Chắc chắn nằm gọn trong vùng an toàn: [16, 18] subset [10, 25]
    kq_trong = th.danh_gia_do_man_loai(17.0, tom, U=1.0)
    assert kq_trong.trang_thai == "AN_TOAN"

    # 2. Bắt chéo ranh giới 25.0: [23.5, 25.5]
    kq_ranh = th.danh_gia_do_man_loai(24.5, tom, U=1.0)
    assert kq_ranh.trang_thai == "SAT_RANH_GIOI"
    assert kq_ranh.mau_sac == "#64748b"
    assert "23.50 – 25.50" in kq_ranh.tieu_de

    # 3. U rất lớn phủ nhiều vùng: [0, 37]
    kq_u_lon = th.danh_gia_do_man_loai(17.0, tom, U=20.0)
    assert kq_u_lon.trang_thai == "SAT_RANH_GIOI"

    # 4. Cổng không đánh giá được
    kq_kdg = th.tao_ket_qua_khong_danh_gia_duoc(tom, 15.0, 0.5, ["Ảnh mô phỏng"])
    assert kq_kdg.trang_thai == "KHONG_DANH_GIA_DUOC"
    assert kq_kdg.mau_sac == "#64748b"
