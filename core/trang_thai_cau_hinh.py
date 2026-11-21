"""Theo dõi tường minh các tham số còn là GIẢ ĐỊNH hoặc chưa xác nhận trong config (R7).

Nguyên tắc:
- Không suy đoán từ comment YAML; dùng danh sách khai báo tường minh ở đây để
  học sinh, người dùng và giám khảo thấy rõ phần nào chưa có số đo thực nghiệm.
- Hệ số Quan–Fry chỉ rời danh sách khi có file xác nhận đối chiếu cục bộ hợp lệ
  (do người dùng tự tạo qua công cụ R8 `scripts/kiem_tra_quan_fry.py`).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

CONFIG_MAC_DINH = Path(__file__).resolve().parents[1] / "config.yaml"
XAC_NHAN_QF_MAC_DINH = Path(__file__).resolve().parents[1] / "data" / "xac_nhan_quan_fry.json"


@dataclass(frozen=True)
class MucGiaDinhKhaiBao:
    """Khai báo một tham số mặc định/giả định cần người dùng đo hoặc xác nhận."""

    nhom: str
    khoa: str
    ten_hien_thi: str
    trang_thai: str  # "GIA_DINH" hoặc "CHUA_DIEN_NULL"
    viec_can_lam: str


# Danh mục khai báo tường minh (không tự suy luận từ comment)
DANH_MUC_GIA_DINH: tuple[MucGiaDinhKhaiBao, ...] = (
    MucGiaDinhKhaiBao(
        nhom="quang_hoc",
        khoa="khoang_cach_man_D_m",
        ten_hien_thi="Khoảng cách từ lăng kính tới màn D (m)",
        trang_thai="GIA_DINH",
        viec_can_lam="Đo khoảng cách thực tế trên khung gá thiết bị bằng thước.",
    ),
    MucGiaDinhKhaiBao(
        nhom="quang_hoc",
        khoa="chiet_suat_nuoc_ngot",
        ten_hien_thi="Chiết suất nước ngọt chuẩn n0",
        trang_thai="GIA_DINH",
        viec_can_lam="Xác nhận theo tài liệu chuẩn hoặc thay thế hoàn toàn bằng đường chuẩn NaCl thật.",
    ),
    MucGiaDinhKhaiBao(
        nhom="quang_hoc",
        khoa="dn_dS_moi_phan_nghin",
        ten_hien_thi="Độ nhạy chiết suất theo độ mặn dn/dS (1/‰)",
        trang_thai="GIA_DINH",
        viec_can_lam="Đối chiếu tài liệu quang học và kiểm chứng qua độ dốc đường chuẩn thực nghiệm.",
    ),
    MucGiaDinhKhaiBao(
        nhom="quang_hoc",
        khoa="dn_dT_moi_do_C",
        ten_hien_thi="Hệ số nhiệt chiết suất dn/dT (1/°C)",
        trang_thai="GIA_DINH",
        viec_can_lam="Xác nhận từ tài liệu tham khảo (Quan & Fry 1995) và đo đường chuẩn ở nhiều nhiệt độ.",
    ),
    MucGiaDinhKhaiBao(
        nhom="quang_hoc",
        khoa="nhiet_do_chuan_chiet_suat_C",
        ten_hien_thi="Nhiệt độ chuẩn của công thức chiết suất (°C)",
        trang_thai="GIA_DINH",
        viec_can_lam="Xác nhận nhiệt độ tham chiếu tương ứng với giá trị n0 trong tài liệu.",
    ),
    MucGiaDinhKhaiBao(
        nhom="anh",
        khoa="kich_thuoc_pixel_mm",
        ten_hien_thi="Kích thước quy đổi pixel trên màn (mm/px)",
        trang_thai="GIA_DINH",
        viec_can_lam="Đo trực tiếp trên từng ảnh bằng thước chuẩn (Tab 1 / cột px_per_mm) thay cho giá trị tĩnh.",
    ),
    MucGiaDinhKhaiBao(
        nhom="phan_tich_sai_so",
        khoa="sai_so_tim_tam_px",
        ten_hien_thi="Độ lệch chuẩn định vị tâm vạch giả định (px)",
        trang_thai="GIA_DINH",
        viec_can_lam="Thay bằng độ lặp lại đo được khi chụp lặp trên ảnh thật của thiết bị.",
    ),
    MucGiaDinhKhaiBao(
        nhom="phan_tich_sai_so",
        khoa="lech_nhiet_do_hai_ngan_C",
        ten_hien_thi="Chênh nhiệt độ điển hình hai ngăn trong ngân sách sai số (°C)",
        trang_thai="GIA_DINH",
        viec_can_lam="Đo thực tế ΔT giữa ngăn mẫu và ngăn tham chiếu trong suốt phiên đo.",
    ),
    MucGiaDinhKhaiBao(
        nhom="phan_tich_sai_so",
        khoa="sai_so_goc_A_do",
        ten_hien_thi="Sai số góc đỉnh lăng kính A (độ)",
        trang_thai="GIA_DINH",
        viec_can_lam="Đo dung sai chế tạo thực tế của lăng kính.",
    ),
    MucGiaDinhKhaiBao(
        nhom="phan_tich_sai_so",
        khoa="troi_laser_chung_px",
        ten_hien_thi="Độ trôi chung của tia laser (px)",
        trang_thai="GIA_DINH",
        viec_can_lam="Đo độ dịch tuyệt đối của vạch nước cất theo thời gian trên thiết bị thật.",
    ),
    MucGiaDinhKhaiBao(
        nhom="phan_tich_sai_so",
        khoa="he_so_triet_chung",
        ten_hien_thi="Hệ số trôi chung còn lọt vào Δy sau đo vi sai",
        trang_thai="GIA_DINH",
        viec_can_lam="Khảo sát thực nghiệm bằng cách rung/làm nóng nhẹ laser trên mẫu nước cất (0‰) ở hai ngăn.",
    ),
    MucGiaDinhKhaiBao(
        nhom="xu_ly_anh",
        khoa="ti_le_cot_bao_hoa_nghiem_trong",
        ten_hien_thi="Ngưỡng tỉ lệ cột bão hòa nghiêm trọng",
        trang_thai="GIA_DINH",
        viec_can_lam="Kiểm chỉnh bằng ảnh chụp laser bị phơi sáng lóa thật trên điện thoại của nhóm.",
    ),
    MucGiaDinhKhaiBao(
        nhom="xu_ly_anh",
        khoa="so_cot_lien_tiep_bao_hoa",
        ten_hien_thi="Số cột bão hòa liên tiếp tối thiểu phân biệt bẹt đỉnh",
        trang_thai="GIA_DINH",
        viec_can_lam="Kiểm chỉnh giữa ảnh đốm speckle thật và ảnh lóa đỉnh bẹt từ camera điện thoại.",
    ),
    MucGiaDinhKhaiBao(
        nhom="xu_ly_anh",
        khoa="nguong_nen_khong_deu",
        ten_hien_thi="Ngưỡng biến thiên nền p95−p5 báo nền không đều",
        trang_thai="GIA_DINH",
        viec_can_lam="Đo phân bố nền trên ảnh chụp ngoài hiện trường (trời râm/nắng nhẹ).",
    ),
    MucGiaDinhKhaiBao(
        nhom="xu_ly_anh",
        khoa="nguong_on_dinh_nhiet_px_moi_phut",
        ten_hien_thi="Ngưỡng tốc độ trôi Δy coi là ổn định nhiệt (px/phút)",
        trang_thai="GIA_DINH",
        viec_can_lam="Theo dõi đường cân bằng nhiệt thật của hai ngăn và đo lại tốc độ trôi dư.",
    ),
    MucGiaDinhKhaiBao(
        nhom="xu_ly_anh",
        khoa="nguong_lech_tam_meo_ti_le",
        ten_hien_thi="Ngưỡng tỉ lệ lệch tâm ảnh vùng rìa dễ méo ống kính",
        trang_thai="GIA_DINH",
        viec_can_lam="Chụp bảng bàn cờ qua camera thật để biết vùng bắt đầu méo đáng kể.",
    ),
    MucGiaDinhKhaiBao(
        nhom="xu_ly_anh",
        khoa="snr_toi_thieu",
        ten_hien_thi="Ngưỡng SNR tối thiểu chấp nhận vạch laser",
        trang_thai="GIA_DINH",
        viec_can_lam="Xác nhận trên ảnh vạch thật ở điều kiện nước đục nhất cần đo.",
    ),
    MucGiaDinhKhaiBao(
        nhom="gioi_han",
        khoa="dung_luong_anh_MB",
        ten_hien_thi="Giới hạn dung lượng mỗi ảnh tải lên (MB)",
        trang_thai="GIA_DINH",
        viec_can_lam="Điều chỉnh phù hợp với dung lượng ảnh thực tế của điện thoại nhóm.",
    ),
    MucGiaDinhKhaiBao(
        nhom="gioi_han",
        khoa="so_khung_toi_da",
        ten_hien_thi="Số khung tối đa trong chế độ đa khung",
        trang_thai="GIA_DINH",
        viec_can_lam="Chỉnh theo số khung tối đa cần dùng khi theo dõi cân bằng nhiệt.",
    ),
    MucGiaDinhKhaiBao(
        nhom="gioi_han",
        khoa="so_megapixel_toi_da",
        ten_hien_thi="Độ phân giải tối đa mỗi ảnh (MP)",
        trang_thai="GIA_DINH",
        viec_can_lam="Kiểm tra khớp với độ phân giải camera điện thoại sử dụng.",
    ),
    MucGiaDinhKhaiBao(
        nhom="hieu_chuan",
        khoa="sai_so_nhiet_ke_C",
        ten_hien_thi="Độ bất định chuẩn của nhiệt kế (°C)",
        trang_thai="GIA_DINH",
        viec_can_lam="Lấy đúng sai số cho phép từ nhãn/giấy kiểm định của nhiệt kế đang dùng.",
    ),
    MucGiaDinhKhaiBao(
        nhom="hieu_chuan",
        khoa="sigma_D_khi_chua_do_C",
        ten_hien_thi="Bất định chênh nhiệt hai ngăn khi chưa đo T_tc (°C)",
        trang_thai="GIA_DINH",
        viec_can_lam="Khảo sát chênh nhiệt ΔT điển hình giữa ngăn mẫu và ngăn tham chiếu rồi thay bằng số đo.",
    ),
    MucGiaDinhKhaiBao(
        nhom="hieu_chuan",
        khoa="ap_dung_hieu_chinh_ly_thuyet_D",
        ten_hien_thi="Cờ tự hiệu chỉnh theo ∂S/∂D lí thuyết khi mô hình chưa học D",
        trang_thai="GIA_DINH",
        viec_can_lam="Thực nghiệm hiệu chuẩn có thay đổi D giữa hai ngăn để dùng hệ số D đo được thay vì lí thuyết.",
    ),
    MucGiaDinhKhaiBao(
        nhom="hieu_chuan",
        khoa="cho_phep_giam_sigma_D_khi_on_dinh",
        ten_hien_thi="Cho phép giảm σ_D khi chuỗi Δy(t) ổn định",
        trang_thai="GIA_DINH",
        viec_can_lam="Đo thực chứng sau khi chờ ổn định Δy xem |ΔT| còn lại giữa hai ngăn là bao nhiêu.",
    ),
    MucGiaDinhKhaiBao(
        nhom="hieu_chuan",
        khoa="sigma_D_khi_da_on_dinh_C",
        ten_hien_thi="Giả định σ_D sau khi ổn định Δy (°C)",
        trang_thai="GIA_DINH",
        viec_can_lam="Đo độ chênh nhiệt còn sót sau thời gian chờ ổn định thực tế trên thiết bị.",
    ),
    MucGiaDinhKhaiBao(
        nhom="hieu_chuan",
        khoa="thoi_gian_on_dinh_toi_thieu_phut",
        ten_hien_thi="Thời gian theo dõi ổn định tối thiểu (phút)",
        trang_thai="GIA_DINH",
        viec_can_lam="Đo hằng số thời gian cân bằng nhiệt τ trên bình thật để đặt thời gian tối thiểu phù hợp.",
    ),
    MucGiaDinhKhaiBao(
        nhom="hieu_chuan",
        khoa="nguong_bien_thien_px_per_mm_phan_tram",
        ten_hien_thi="Ngưỡng biến thiên thang px/mm cảnh báo (%)",
        trang_thai="GIA_DINH",
        viec_can_lam="Đặt lại theo sai số đo chiều dài mục tiêu khi chụp trên gá đỡ thật.",
    ),
    MucGiaDinhKhaiBao(
        nhom="hieu_chuan",
        khoa="sai_so_dung_dich_chuan_ppt",
        ten_hien_thi="Bất định dung dịch NaCl chuẩn (‰)",
        trang_thai="CHUA_DIEN_NULL",
        viec_can_lam="Tính từ sai số cân điện tử + bình định mức khi pha dung dịch chuẩn NaCl và điền vào config.yaml.",
    ),
    MucGiaDinhKhaiBao(
        nhom="hieu_chuan",
        khoa="nhiet_do_toi_thieu_phu_C",
        ten_hien_thi="Dải nhiệt độ tối thiểu cần phủ khi hiệu chuẩn (°C)",
        trang_thai="CHUA_DIEN_NULL",
        viec_can_lam="Xác định theo biên độ nhiệt độ ao nuôi/nguồn nước thực tế cần đo và điền vào config.yaml.",
    ),
)


def kiem_tra_xac_nhan_quan_fry(
    xac_nhan_path: str | Path | None = XAC_NHAN_QF_MAC_DINH,
) -> tuple[bool, str]:
    """Kiểm tra file xác nhận đối chiếu hệ số Quan–Fry (chỉ do người dùng tự tạo qua R8)."""
    if xac_nhan_path is None:
        return False, "Chưa có đường dẫn file xác nhận đối chiếu."
    p = Path(xac_nhan_path)
    if not p.exists():
        return False, "Chưa chạy đối chiếu 10 hệ số Quan–Fry với bài gốc (1995)."
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if bool(data.get("da_doi_chieu_khop")):
            ngay = str(data.get("thoi_gian") or "").strip()
            return True, f"Đã đối chiếu khớp theo ghi nhận cục bộ ({ngay})."
    except Exception:
        pass
    return False, "File xác nhận Quan–Fry chưa hợp lệ hoặc chưa khớp toàn bộ."


def liet_ke_tham_so_chua_xac_nhan(
    config_path: str | Path = CONFIG_MAC_DINH,
    xac_nhan_quan_fry_path: str | Path | None = XAC_NHAN_QF_MAC_DINH,
) -> dict[str, Any]:
    """Trả danh sách các tham số còn là giả định hoặc để trống cần người dùng xác nhận."""
    cfg_path = Path(config_path)
    with open(cfg_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    danh_sach: list[dict[str, Any]] = []
    for item in DANH_MUC_GIA_DINH:
        section = raw.get(item.nhom, {}) or {}
        has_key = item.khoa in section
        val = section.get(item.khoa)
        if item.trang_thai == "CHUA_DIEN_NULL":
            # Chỉ rời danh sách khi người dùng đã điền giá trị số / non-null hợp lệ
            if has_key and val is not None and str(val).strip() != "":
                continue
        danh_sach.append({
            "ma": f"{item.nhom}.{item.khoa}",
            "nhom": item.nhom,
            "ten_tham_so": item.ten_hien_thi,
            "gia_tri_hien_tai": "null" if val is None else str(val),
            "trang_thai": "CHƯA ĐIỀN (null)" if val is None else "GIẢ ĐỊNH",
            "viec_can_lam": item.viec_can_lam,
        })

    # Kiểm tra từng loài trong nguong_loai
    nguong_loai = raw.get("nguong_loai", {}) or {}
    for ma_loai, info in nguong_loai.items():
        if not isinstance(info, dict):
            continue
        an_toan = info.get("an_toan")
        nguon = str(info.get("nguon_tham_khao") or "").strip()
        co_nguong = isinstance(an_toan, (list, tuple)) and len(an_toan) == 2 and all(x is not None for x in an_toan)
        if co_nguong and nguon:
            continue
        ten_loai = str(info.get("ten") or ma_loai)
        danh_sach.append({
            "ma": f"nguong_loai.{ma_loai}",
            "nhom": "nguong_loai",
            "ten_tham_so": f"Ngưỡng sinh học & nguồn tài liệu: {ten_loai}",
            "gia_tri_hien_tai": "an_toan=null" if not co_nguong else f"an_toan={an_toan}, thiếu nguồn",
            "trang_thai": "CHƯA CÓ NGƯỠNG / NGUỒN",
            "viec_can_lam": "Đọc tài liệu khoa học hoặc quy chuẩn gốc, điền dải an toàn và trích dẫn đủ tác giả, năm, trang/DOI.",
        })

    # Kiểm tra đối chiếu hệ số Quan–Fry (luôn nằm trong danh sách cho tới khi file đối chiếu hợp lệ tồn tại)
    da_khop_qf, msg_qf = kiem_tra_xac_nhan_quan_fry(xac_nhan_quan_fry_path)
    if not da_khop_qf:
        danh_sach.append({
            "ma": "quan_fry.he_so_quan_fry_1995",
            "nhom": "quan_fry",
            "ten_tham_so": "10 hệ số a0..a9 công thức Quan–Fry (1995) trong core/optics.py",
            "gia_tri_hien_tai": "10 hằng số tạm từ nhóm",
            "trang_thai": "CHƯA ĐỐI CHIẾU BÀI GỐC",
            "viec_can_lam": (
                f"{msg_qf} Mở docs/DOI_CHIEU_QUAN_FRY.md, đối chiếu bài gốc Quan & Fry (1995) "
                "và chạy scripts/kiem_tra_quan_fry.py --luu-xac-nhan."
            ),
        })

    return {
        "so_tham_so_chua_xac_nhan": len(danh_sach),
        "danh_sach": danh_sach,
    }
