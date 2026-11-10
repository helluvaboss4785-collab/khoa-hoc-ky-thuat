"""Mô-đun quản lí ngưỡng độ mặn theo đối tượng nuôi trồng và cảnh báo rủi ro (Cột mốc 5).

Nguyên tắc bắt buộc:
- Mọi ngưỡng đều được nạp từ config.yaml.
- Mỗi ngưỡng PHẢI kèm trường nguồn tham khảo (tài liệu chuyên môn, quy chuẩn kỹ thuật).
- Đối tượng nào chưa có nguồn thì để trống và cảnh báo rõ "chưa có nguồn tham khảo, yêu cầu người dùng điền".
  TUYỆT ĐỐI KHÔNG TỰ BỊA RA CÁC CON SỐ NGƯỠNG.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

CONFIG_MAC_DINH = Path(__file__).resolve().parents[1] / "config.yaml"


@dataclass(frozen=True)
class ThongTinLoai:
    """Thông tin ngưỡng sinh học của một đối tượng nuôi trồng."""

    ma_loai: str
    ten_hien_thi: str
    an_toan_min: float | None
    an_toan_max: float | None
    canh_bao_thap: tuple[float, float] | None
    canh_bao_cao: tuple[float, float] | None
    nguy_hiem_duoi: float | None
    nguy_hiem_tren: float | None
    nguon_tham_khao: str

    @property
    def co_du_lieu_nguon(self) -> bool:
        """Kiểm tra loài đã có trích dẫn nguồn tài liệu tham khảo hay chưa."""
        return bool(self.nguon_tham_khao.strip())


@dataclass(frozen=True)
class KetQuaDanhGiaLoai:
    """Kết quả phân tích mức an toàn độ mặn đối với loài được chọn."""

    ma_loai: str
    ten_loai: str
    trang_thai: Literal["AN_TOAN", "CANH_BAO", "NGUY_HIEM", "CHUA_CO_NGUON"]
    mau_sac: str                  # mã màu hiển thị giao diện ("#28a745", "#ffc107", "#dc3545", "#6c757d")
    tieu_de: str                  # thông điệp ngắn gọn
    loi_khuyen: str               # hành động khuyến cáo người nuôi/trồng
    nguon_tham_khao: str          # tài liệu tham khảo để học sinh bảo vệ luận điểm


def doc_danh_sach_loai(duong_dan_yaml: str | Path = CONFIG_MAC_DINH) -> dict[str, ThongTinLoai]:
    """Đọc toàn bộ danh mục ngưỡng sinh học từ config.yaml."""
    p = Path(duong_dan_yaml)
    if not p.exists():
        return {}

    with open(p, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    raw_nguong = data.get("nguong_loai", {})
    ket_qua = {}

    for k, v in raw_nguong.items():
        if not isinstance(v, dict):
            continue

        an_toan = v.get("an_toan")
        at_min = float(an_toan[0]) if an_toan and len(an_toan) >= 2 and an_toan[0] is not None else None
        at_max = float(an_toan[1]) if an_toan and len(an_toan) >= 2 and an_toan[1] is not None else None

        cb_thap = v.get("canh_bao_thap")
        cb_thap_tup = (float(cb_thap[0]), float(cb_thap[1])) if cb_thap and len(cb_thap) >= 2 and cb_thap[0] is not None else None

        cb_cao = v.get("canh_bao_cao")
        cb_cao_tup = (float(cb_cao[0]), float(cb_cao[1])) if cb_cao and len(cb_cao) >= 2 and cb_cao[0] is not None else None

        nguy_duoi = float(v["nguy_hiem_duoi"]) if v.get("nguy_hiem_duoi") is not None else None
        nguy_tren = float(v["nguy_hiem_tren"]) if v.get("nguy_hiem_tren") is not None else None

        ket_qua[k] = ThongTinLoai(
            ma_loai=k,
            ten_hien_thi=v.get("ten", k),
            an_toan_min=at_min,
            an_toan_max=at_max,
            canh_bao_thap=cb_thap_tup,
            canh_bao_cao=cb_cao_tup,
            nguy_hiem_duoi=nguy_duoi,
            nguy_hiem_tren=nguy_tren,
            nguon_tham_khao=str(v.get("nguon_tham_khao") or "").strip(),
        )

    return ket_qua


def danh_gia_do_man_loai(S_ppt: float, loai: ThongTinLoai) -> KetQuaDanhGiaLoai:
    """Đánh giá độ an toàn của mức độ mặn đối với một loài cụ thể."""
    if not loai.co_du_lieu_nguon:
        return KetQuaDanhGiaLoai(
            ma_loai=loai.ma_loai,
            ten_loai=loai.ten_hien_thi,
            trang_thai="CHUA_CO_NGUON",
            mau_sac="#6c757d",
            tieu_de="CHƯA CÓ DỮ LIỆU TÀI LIỆU CHUẨN",
            loi_khuyen="Đối tượng này chưa có nguồn tài liệu trích dẫn chuẩn trong config.yaml. Học sinh cần tra cứu tài liệu nông - thủy sản chính thức và điền vào trước khi sử dụng kết quả.",
            nguon_tham_khao="Chưa có - Cần bổ sung trong config.yaml",
        )

    # 1. Kiểm tra mức NGUY HIỂM
    if loai.nguy_hiem_duoi is not None and S_ppt < loai.nguy_hiem_duoi:
        return KetQuaDanhGiaLoai(
            ma_loai=loai.ma_loai,
            ten_loai=loai.ten_hien_thi,
            trang_thai="NGUY_HIEM",
            mau_sac="#dc3545",
            tieu_de=f"NGUY HIỂM: Độ mặn quá thấp (< {loai.nguy_hiem_duoi:g} ‰)",
            loi_khuyen=f"Độ mặn {S_ppt:.1f} ‰ thấp hơn ngưỡng chịu đựng tối thiểu ({loai.nguy_hiem_duoi:g} ‰). Nguy cơ sốc nhược áp, chậm lớn hoặc chết hàng loạt. Cần có biện pháp nâng mặn khẩn cấp hoặc di dời.",
            nguon_tham_khao=loai.nguon_tham_khao,
        )

    if loai.nguy_hiem_tren is not None and S_ppt > loai.nguy_hiem_tren:
        return KetQuaDanhGiaLoai(
            ma_loai=loai.ma_loai,
            ten_loai=loai.ten_hien_thi,
            trang_thai="NGUY_HIEM",
            mau_sac="#dc3545",
            tieu_de=f"NGUY HIỂM: Xâm nhập mặn vượt ngưỡng chết (> {loai.nguy_hiem_tren:g} ‰)",
            loi_khuyen=f"Độ mặn {S_ppt:.1f} ‰ vượt quá giới hạn chịu mặn tối đa ({loai.nguy_hiem_tren:g} ‰). TUYỆT ĐỐI KHÔNG lấy nước tưới hoặc cấp vào ao. Đóng ngay cống ngăn mặn.",
            nguon_tham_khao=loai.nguon_tham_khao,
        )

    # 2. Kiểm tra mức CẢNH BÁO
    if loai.canh_bao_thap and loai.canh_bao_thap[0] <= S_ppt < loai.canh_bao_thap[1]:
        return KetQuaDanhGiaLoai(
            ma_loai=loai.ma_loai,
            ten_loai=loai.ten_hien_thi,
            trang_thai="CANH_BAO",
            mau_sac="#ffc107",
            tieu_de=f"CẢNH BÁO: Độ mặn hơi thấp ({loai.canh_bao_thap[0]:g} - {loai.canh_bao_thap[1]:g} ‰)",
            loi_khuyen=f"Độ mặn {S_ppt:.1f} ‰ nằm ở vùng cận dưới tối ưu. Cần theo dõi sát sao chu kì lột xác / sức ăn của vật nuôi hoặc chuẩn bị khoáng tạt bổ sung.",
            nguon_tham_khao=loai.nguon_tham_khao,
        )

    if loai.canh_bao_cao and loai.canh_bao_cao[0] < S_ppt <= loai.canh_bao_cao[1]:
        return KetQuaDanhGiaLoai(
            ma_loai=loai.ma_loai,
            ten_loai=loai.ten_hien_thi,
            trang_thai="CANH_BAO",
            mau_sac="#ffc107",
            tieu_de=f"CẢNH BÁO: Độ mặn tăng cao ({loai.canh_bao_cao[0]:g} - {loai.canh_bao_cao[1]:g} ‰)",
            loi_khuyen=f"Độ mặn {S_ppt:.1f} ‰ bắt đầu vượt ngưỡng tối ưu. Có nguy cơ ngộ độc mặn rễ cây hoặc chậm tăng trưởng ở tôm/cá. Hạn chế lấy thêm nước ngoài kênh vào thời điểm này.",
            nguon_tham_khao=loai.nguon_tham_khao,
        )

    # 3. Kiểm tra mức AN TOÀN
    if loai.an_toan_min is not None and loai.an_toan_max is not None:
        if loai.an_toan_min <= S_ppt <= loai.an_toan_max:
            return KetQuaDanhGiaLoai(
                ma_loai=loai.ma_loai,
                ten_loai=loai.ten_hien_thi,
                trang_thai="AN_TOAN",
                mau_sac="#28a745",
                tieu_de=f"AN TOÀN: Nằm trong dải tối ưu ({loai.an_toan_min:g} - {loai.an_toan_max:g} ‰)",
                loi_khuyen=f"Độ mặn {S_ppt:.1f} ‰ rất phù hợp cho sự sinh trưởng và phát triển sinh lí bình thường của {loai.ten_hien_thi}.",
                nguon_tham_khao=loai.nguon_tham_khao,
            )

    return KetQuaDanhGiaLoai(
        ma_loai=loai.ma_loai,
        ten_loai=loai.ten_hien_thi,
        trang_thai="CANH_BAO",
        mau_sac="#ffc107",
        tieu_de="CHƯA XÁC ĐỊNH PHÂN VÙNG",
        loi_khuyen="Giá trị độ mặn nằm ngoài các khoảng quy định trong cấu hình hiện tại.",
        nguon_tham_khao=loai.nguon_tham_khao,
    )

