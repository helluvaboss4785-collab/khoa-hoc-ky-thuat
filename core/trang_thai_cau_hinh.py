"""Theo dõi tường minh các tham số còn là GIẢ ĐỊNH hoặc chưa xác nhận trong config (R7).

Nguyên tắc:
- Không suy đoán từ comment YAML; dùng danh sách khai báo tường minh ở đây để
  học sinh, người dùng và giám khảo thấy rõ phần nào chưa có số đo thực nghiệm.
- Hệ số Quan–Fry chỉ rời danh sách khi có file xác nhận đối chiếu cục bộ hợp lệ
  (do người dùng tự tạo qua công cụ R8 `scripts/kiem_tra_quan_fry.py`).
"""
from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from core.nhiet_ke import FILE_HIEU_CHUAN_NHIET_KE_MAC_DINH, tai_hieu_chuan_cheo_nhiet_ke

CONFIG_MAC_DINH = Path(__file__).resolve().parents[1] / "config.yaml"
XAC_NHAN_QF_MAC_DINH = Path(__file__).resolve().parents[1] / "data" / "xac_nhan_quan_fry.json"
GHI_CHU_GIOI_HAN_QUAN_FRY = (
    "Xác nhận do người dùng tự khai, hệ thống không kiểm chứng độc lập nội dung bài báo gốc"
)


def _chuan_hoa_ten_r7(ten: str) -> str:
    s = " ".join(str(ten or "").strip().split()).replace("đ", "d").replace("Đ", "D")
    nfd = unicodedata.normalize("NFD", s)
    return " ".join("".join(ch for ch in nfd if unicodedata.category(ch) != "Mn").lower().split())


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
    MucGiaDinhKhaiBao(
        nhom="hieu_chuan",
        khoa="nhiet_ke_cheo.so_cap_toi_thieu",
        ten_hien_thi="Số cặp tối thiểu khi hiệu chuẩn chéo hai nhiệt kế",
        trang_thai="GIA_DINH",
        viec_can_lam="Điều chỉnh cùng giáo viên theo thực tế lặp nhiệt độ khi ngâm chung hai nhiệt kế.",
    ),
    MucGiaDinhKhaiBao(
        nhom="hieu_chuan",
        khoa="nhiet_ke_cheo.so_muc_nhiet_toi_thieu",
        ten_hien_thi="Số mức nhiệt độ tối thiểu khi hiệu chuẩn chéo hai nhiệt kế",
        trang_thai="GIA_DINH",
        viec_can_lam="Chọn số mức nhiệt độ tối thiểu phủ hết dải nhiệt độ cần đo.",
    ),
    MucGiaDinhKhaiBao(
        nhom="hieu_chuan",
        khoa="dai_man_muc_tieu_ppt",
        ten_hien_thi="Dải độ mặn mục tiêu khi đánh giá thiết kế hiệu chuẩn (‰)",
        trang_thai="GIA_DINH",
        viec_can_lam="Điều chỉnh dải mục tiêu [S_min, S_max] theo đối tượng nuôi/nguồn nước khảo sát thực tế.",
    ),
    MucGiaDinhKhaiBao(
        nhom="thiet_ke_thi_nghiem",
        khoa="so_muc_man_toi_thieu",
        ten_hien_thi="Số mức độ mặn S chuẩn tối thiểu trong bộ hiệu chuẩn",
        trang_thai="GIA_DINH",
        viec_can_lam="Thảo luận cùng giáo viên hướng dẫn để chốt số mức nồng độ chuẩn phù hợp đường chuẩn bậc 1/2.",
    ),
    MucGiaDinhKhaiBao(
        nhom="thiet_ke_thi_nghiem",
        khoa="phai_co_muc_0",
        ten_hien_thi="Bắt buộc có điểm gốc nước cất S ≈ 0‰ trong thiết kế",
        trang_thai="GIA_DINH",
        viec_can_lam="Giữ bật để có mốc đối chứng 0‰, hoặc chỉnh trong config.yaml nếu khảo sát dải hẹp riêng.",
    ),
    MucGiaDinhKhaiBao(
        nhom="thiet_ke_thi_nghiem",
        khoa="ti_le_phu_dai_man_toi_thieu",
        ten_hien_thi="Tỉ lệ phủ tối thiểu của dải độ mặn mục tiêu",
        trang_thai="GIA_DINH",
        viec_can_lam="Điều chỉnh cùng giáo viên theo bề rộng dải nồng độ pha được trong phòng thí nghiệm.",
    ),
    MucGiaDinhKhaiBao(
        nhom="thiet_ke_thi_nghiem",
        khoa="so_lan_lap_toi_thieu_moi_o",
        ten_hien_thi="Số ảnh lặp lại tối thiểu tại mỗi ô (S × mức T)",
        trang_thai="GIA_DINH",
        viec_can_lam="Điều chỉnh theo độ ổn định chụp ảnh thật của bộ giá đỡ thiết bị.",
    ),
    MucGiaDinhKhaiBao(
        nhom="thiet_ke_thi_nghiem",
        khoa="so_me_pha_toi_thieu",
        ten_hien_thi="Số mẻ pha dung dịch độc lập tối thiểu (ma_me_pha)",
        trang_thai="GIA_DINH",
        viec_can_lam="Pha ít nhất 2 mẻ độc lập (hoặc nhiều hơn nếu sai số cân pha chế lớn) để tách GroupKFold.",
    ),
    MucGiaDinhKhaiBao(
        nhom="thiet_ke_thi_nghiem",
        khoa="so_muc_nhiet_toi_thieu",
        ten_hien_thi="Số mức nhiệt độ khảo sát T tối thiểu khi hiệu chuẩn",
        trang_thai="GIA_DINH",
        viec_can_lam="Chọn số mức nhiệt phù hợp biên độ nhiệt thực tế của ao nuôi/nguồn nước.",
    ),
    MucGiaDinhKhaiBao(
        nhom="thiet_ke_thi_nghiem",
        khoa="bien_do_nhiet_toi_thieu_C",
        ten_hien_thi="Biên độ nhiệt độ ΔT tối thiểu cần phủ khi hiệu chuẩn (°C)",
        trang_thai="GIA_DINH",
        viec_can_lam="Đặt theo biến động nhiệt ngày–đêm và mùa vụ thực tế ngoài hiện trường.",
    ),
    MucGiaDinhKhaiBao(
        nhom="thiet_ke_thi_nghiem",
        khoa="so_muc_D_toi_thieu_neu_hoc_D",
        ten_hien_thi="Số mức chênh nhiệt D = T_mẫu − T_tc tối thiểu (khi học D)",
        trang_thai="GIA_DINH",
        viec_can_lam="Chọn cùng giáo viên khi lập kế hoạch thí nghiệm có chủ đích lệch nhiệt hai ngăn.",
    ),
    MucGiaDinhKhaiBao(
        nhom="thiet_ke_thi_nghiem",
        khoa="chenh_D_toi_thieu_C",
        ten_hien_thi="Biên độ chênh nhiệt D tối thiểu cần đạt (khi học D, °C)",
        trang_thai="GIA_DINH",
        viec_can_lam="Đặt theo dải lệch nhiệt độ mẫu vs tham chiếu thực tế cần bù.",
    ),
    MucGiaDinhKhaiBao(
        nhom="thiet_ke_thi_nghiem",
        khoa="ti_le_toi_da_moi_muc",
        ten_hien_thi="Tỉ lệ mẫu tối đa cho phép tại một mức độ mặn đơn lẻ",
        trang_thai="GIA_DINH",
        viec_can_lam="Đảm bảo các điểm hiệu chuẩn phân bố cân bằng, tránh dồn quá nhiều mẫu vào một mức S.",
    ),
    MucGiaDinhKhaiBao(
        nhom="thiet_ke_thi_nghiem",
        khoa="ti_le_ban_sao_toi_da",
        ten_hien_thi="Tỉ lệ dòng bản sao tối đa cho phép trong bộ hiệu chuẩn",
        trang_thai="GIA_DINH",
        viec_can_lam="Giữ 0.0 để mọi dòng trùng hệt, trùng sha256_anh hoặc nghi ngờ gán nhãn lại đều bị phát hiện và làm sạch.",
    ),
    MucGiaDinhKhaiBao(
        nhom="nhap_anh",
        khoa="thu_muc_mo_phong",
        ten_hien_thi="Danh sách thư mục ảnh mô phỏng bị chặn khi nhập --nguon THUC_TE",
        trang_thai="GIA_DINH",
        viec_can_lam="Kiểm tra và bổ sung các thư mục lưu ảnh thử nghiệm/mô phỏng của nhóm vào config.yaml để tránh nhầm nguồn.",
    ),
    MucGiaDinhKhaiBao(
        nhom="hieu_chuan",
        khoa="nhiet_ke_cheo.do_phan_giai_toi_da_C",
        ten_hien_thi="Độ phân giải tối đa của nhiệt kế khi hiệu chuẩn chéo (°C)",
        trang_thai="GIA_DINH",
        viec_can_lam="Kiểm tra độ chia nhỏ nhất thực tế của cả 2 nhiệt kế; nếu thô hơn ngưỡng này phần mềm bật cảnh báo và nâng sàn σ_pg.",
    ),
)


def _lay_gia_tri_long(section: dict[str, Any], khoa_path: str) -> tuple[bool, Any]:
    """Đọc khóa có thể lồng nhau theo dấu chấm (vd 'nhiet_ke_cheo.so_cap_toi_thieu')."""
    cur: Any = section
    for part in str(khoa_path).split("."):
        if not isinstance(cur, dict) or part not in cur:
            return False, None
        cur = cur[part]
    return True, cur


def phan_tich_xac_nhan_quan_fry(
    xac_nhan_path: str | Path | None = XAC_NHAN_QF_MAC_DINH,
) -> dict[str, Any]:
    """Phân tích chi tiết 3 trạng thái đối chiếu Quan–Fry: chua_xac_nhan | xac_nhan_1_nguoi | xac_nhan_2_nguoi."""
    mac_dinh: dict[str, Any] = {
        "trang_thai": "chua_xac_nhan",
        "da_doi_chieu_khop": False,
        "so_nguoi_xac_nhan": 0,
        "nguoi_doi_chieu": "",
        "nguoi_xac_nhan_2": "",
        "ngay": "",
        "trich_dan": "",
        "trung_chuoi_ma": False,
        "ghi_chu_gioi_han": GHI_CHU_GIOI_HAN_QUAN_FRY,
        "thong_diep": f"Chưa chạy đối chiếu 10 hệ số Quan–Fry với bài gốc (1995). ({GHI_CHU_GIOI_HAN_QUAN_FRY})",
    }
    if xac_nhan_path is None:
        return {**mac_dinh, "thong_diep": f"Chưa có đường dẫn file xác nhận đối chiếu. ({GHI_CHU_GIOI_HAN_QUAN_FRY})"}
    p = Path(xac_nhan_path)
    if not p.exists():
        return mac_dinh
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not bool(data.get("da_doi_chieu_khop")):
            return {**mac_dinh, "thong_diep": f"File xác nhận Quan–Fry chưa hợp lệ hoặc chưa khớp toàn bộ. ({GHI_CHU_GIOI_HAN_QUAN_FRY})"}
        ngay = str(data.get("thoi_gian") or "").strip()
        td = str(data.get("trich_dan") or "").strip()
        ghi_chu_gl = str(data.get("ghi_chu_gioi_han") or GHI_CHU_GIOI_HAN_QUAN_FRY).strip()
        trung_chuoi = bool(data.get("trung_chuoi_ma", False))
        if "nguoi_doi_chieu" in data:
            n1 = str(data.get("nguoi_doi_chieu") or "").strip()
            if not n1 or not td:
                return {**mac_dinh, "thong_diep": f"File xác nhận thiếu tên người đối chiếu hoặc trích dẫn bài gốc. ({ghi_chu_gl})"}
        else:
            # Tương thích định dạng tối giản của kiểm thử R7 cũ, vẫn yêu cầu người xác nhận 2
            n1 = "(bản ghi R7 cũ, chưa ghi tên người 1)"
        n2 = str(data.get("nguoi_xac_nhan_2") or "").strip()
        if n2 and _chuan_hoa_ten_r7(n2) != _chuan_hoa_ten_r7(n1):
            return {
                "trang_thai": "xac_nhan_2_nguoi",
                "da_doi_chieu_khop": True,
                "so_nguoi_xac_nhan": 2,
                "nguoi_doi_chieu": n1,
                "nguoi_xac_nhan_2": n2,
                "ngay": ngay,
                "trich_dan": td,
                "trung_chuoi_ma": trung_chuoi,
                "ghi_chu_gioi_han": ghi_chu_gl,
                "thong_diep": f"Đã đối chiếu khớp (2/2 người: {n1}; {n2}, {ngay}). {ghi_chu_gl}.",
            }
        return {
            "trang_thai": "xac_nhan_1_nguoi",
            "da_doi_chieu_khop": True,
            "so_nguoi_xac_nhan": 1,
            "nguoi_doi_chieu": n1,
            "nguoi_xac_nhan_2": "",
            "ngay": ngay,
            "trich_dan": td,
            "trung_chuoi_ma": trung_chuoi,
            "ghi_chu_gioi_han": ghi_chu_gl,
            "thong_diep": f"Đã đối chiếu bởi {n1} ({ngay}), chưa có người xác nhận thứ hai (1/2 người). {ghi_chu_gl}.",
        }
    except Exception:
        return {**mac_dinh, "thong_diep": "File xác nhận Quan–Fry bị lỗi định dạng."}


def kiem_tra_xac_nhan_quan_fry(
    xac_nhan_path: str | Path | None = XAC_NHAN_QF_MAC_DINH,
) -> tuple[bool, str]:
    """Kiểm tra file xác nhận đối chiếu hệ số Quan–Fry (tương thích R7/R8)."""
    info = phan_tich_xac_nhan_quan_fry(xac_nhan_path)
    return bool(info["da_doi_chieu_khop"]), str(info["thong_diep"])


def liet_ke_tham_so_chua_xac_nhan(
    config_path: str | Path = CONFIG_MAC_DINH,
    xac_nhan_quan_fry_path: str | Path | None = XAC_NHAN_QF_MAC_DINH,
    hieu_chuan_nhiet_ke_path: str | Path | None = FILE_HIEU_CHUAN_NHIET_KE_MAC_DINH,
) -> dict[str, Any]:
    """Trả danh sách các tham số còn là giả định hoặc để trống cần người dùng xác nhận."""
    cfg_path = Path(config_path)
    with open(cfg_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    danh_sach: list[dict[str, Any]] = []
    for item in DANH_MUC_GIA_DINH:
        section = raw.get(item.nhom, {}) or {}
        has_key, val = _lay_gia_tri_long(section, item.khoa)
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

    # Kiểm tra hiệu chuẩn chéo hai nhiệt kế (V1) & giả định độ phân giải (W3)
    hc_nk = tai_hieu_chuan_cheo_nhiet_ke(hieu_chuan_nhiet_ke_path)
    if hc_nk is None:
        danh_sach.append({
            "ma": "hieu_chuan.hieu_chuan_cheo_nhiet_ke",
            "nhom": "hieu_chuan",
            "ten_tham_so": "Hiệu chuẩn chéo độ lệch giữa hai nhiệt kế (ngăn tham chiếu vs mẫu)",
            "gia_tri_hien_tai": "chưa có file",
            "trang_thai": "CHƯA HIỆU CHUẨN CHÉO",
            "viec_can_lam": (
                "Nhúng chung hai đầu đo vào cùng cốc nước khuấy đều ở nhiều nhiệt độ "
                "và chạy scripts/hieu_chuan_cheo_nhiet_ke.py."
            ),
        })
    danh_sach.append({
        "ma": "hieu_chuan.nhiet_ke_cheo.gia_dinh_doc_lap_phan_giai",
        "nhom": "hieu_chuan",
        "ten_tham_so": "Giả định lượng tử hóa độc lập giữa các mức nhiệt trong sàn σ_pg",
        "gia_tri_hien_tai": "σ_pg = √(r_mẫu² + r_tc²) / √(12 · số_mức)",
        "trang_thai": "GIẢ ĐỊNH",
        "viec_can_lam": (
            "Giả định sai số làm tròn phân bố đều và độc lập giữa các mức nhiệt; "
            "nên dùng nhiệt kế ≤ 0.1 °C và đo ở nhiều mức nhiệt khác nhau."
        ),
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

    # Kiểm tra 3 trạng thái đối chiếu Quan–Fry (V2)
    qf_info = phan_tich_xac_nhan_quan_fry(xac_nhan_quan_fry_path)
    if qf_info["trang_thai"] == "chua_xac_nhan":
        danh_sach.append({
            "ma": "quan_fry.he_so_quan_fry_1995",
            "nhom": "quan_fry",
            "ten_tham_so": "10 hệ số a0..a9 công thức Quan–Fry (1995) trong core/optics.py",
            "gia_tri_hien_tai": "10 hằng số tạm từ nhóm",
            "trang_thai": "CHƯA ĐỐI CHIẾU BÀI GỐC",
            "viec_can_lam": (
                f"{qf_info['thong_diep']} Mở docs/DOI_CHIEU_QUAN_FRY.md, đối chiếu bài gốc Quan & Fry (1995) "
                "(đủ trang/bảng) và chạy scripts/kiem_tra_quan_fry.py --luu-xac-nhan --nguoi-doi-chieu ... --trich-dan ...."
            ),
        })
    elif qf_info["trang_thai"] == "xac_nhan_1_nguoi":
        danh_sach.append({
            "ma": "quan_fry.xac_nhan_doc_lap_nguoi_2",
            "nhom": "quan_fry",
            "ten_tham_so": "Xác nhận độc lập lần 2 cho 10 hệ số Quan–Fry (GVHD / thành viên thứ hai)",
            "gia_tri_hien_tai": f"Người 1: {qf_info['nguoi_doi_chieu']} ({qf_info['ngay']})",
            "trang_thai": "CHƯA CÓ NGƯỜI XÁC NHẬN THỨ HAI",
            "viec_can_lam": (
                f"Đã có người 1 xác nhận (trích dẫn: {qf_info['trich_dan'] or 'n/a'}), nhưng chưa có người xác nhận thứ hai. "
                "Chạy lại scripts/kiem_tra_quan_fry.py với --nguoi-xac-nhan-2."
            ),
        })

    return {
        "so_tham_so_chua_xac_nhan": len(danh_sach),
        "xac_nhan_quan_fry": qf_info,
        "danh_sach": danh_sach,
    }
