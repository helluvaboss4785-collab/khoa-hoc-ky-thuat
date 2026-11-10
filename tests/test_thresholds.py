"""Unit tests cho core/thresholds.py: Đánh giá ngưỡng an toàn theo đối tượng nuôi trồng."""
from __future__ import annotations

import pytest

from core import thresholds as th


def test_doc_danh_sach_loai_tu_config():
    """Kiểm tra đọc đúng các loài từ config.yaml."""
    ds = th.doc_danh_sach_loai()
    assert "tom_the_chan_trang" in ds
    assert "sau_rieng" in ds
    assert "cua_bien" in ds

    tôm = ds["tom_the_chan_trang"]
    assert tôm.an_toan_min == 10.0
    assert tôm.an_toan_max == 25.0
    assert tôm.co_du_lieu_nguon is True
    assert "TCVN" in tôm.nguon_tham_khao


def test_loai_chua_co_nguon_phai_canh_bao():
    """Loài chưa có nguồn tham khảo (cua_bien) phải trả về CHUA_CO_NGUON và không bịa kết luận."""
    ds = th.doc_danh_sach_loai()
    cua = ds["cua_bien"]
    assert cua.co_du_lieu_nguon is False

    kq = th.danh_gia_do_man_loai(15.0, cua)
    assert kq.trang_thai == "CHUA_CO_NGUON"
    assert "CHƯA CÓ" in kq.tieu_de
    assert "bổ sung" in kq.nguon_tham_khao.lower() or "điền vào" in kq.loi_khuyen.lower()


def test_danh_gia_muc_an_toan_tom_the():
    """Kiểm tra đánh giá an toàn, cảnh báo, nguy hiểm trên tôm thẻ chân trắng."""
    ds = th.doc_danh_sach_loai()
    tom = ds["tom_the_chan_trang"]

    # 1. An toàn: 15 ppt (nằm trong 10-25)
    kq_at = th.danh_gia_do_man_loai(15.0, tom)
    assert kq_at.trang_thai == "AN_TOAN"
    assert "AN TOÀN" in kq_at.tieu_de

    # 2. Cảnh báo cao: 28 ppt (nằm trong 25-35)
    kq_cb = th.danh_gia_do_man_loai(28.0, tom)
    assert kq_cb.trang_thai == "CANH_BAO"

    # 3. Nguy hiểm: 38 ppt (> 35)
    kq_ng = th.danh_gia_do_man_loai(38.0, tom)
    assert kq_ng.trang_thai == "NGUY_HIEM"


def test_danh_gia_sau_rieng_nhay_cam():
    """Cây sầu riêng nhạy cảm mặn: > 1 ppt là nguy hiểm."""
    ds = th.doc_danh_sach_loai()
    sr = ds["sau_rieng"]

    kq_at = th.danh_gia_do_man_loai(0.3, sr)
    assert kq_at.trang_thai == "AN_TOAN"

    kq_ng = th.danh_gia_do_man_loai(1.2, sr)
    assert kq_ng.trang_thai == "NGUY_HIEM"
    assert "SOFRI" in kq_ng.nguon_tham_khao
