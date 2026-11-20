"""Mô-đun quản lí ngưỡng độ mặn theo đối tượng nuôi trồng và đối chiếu rủi ro (Cột mốc 5).

Nguyên tắc bắt buộc:
- Mọi ngưỡng đều được nạp từ config.yaml.
- Mỗi ngưỡng PHẢI kèm trường nguồn tham khảo (tác giả, năm, số trang/DOI hoặc số hiệu văn bản).
- Đối tượng nào chưa có nguồn thì để trống/null và báo "Chưa có nguồn tham khảo, yêu cầu người dùng điền".
  TUYỆT ĐỐI KHÔNG TỰ BỊA NGƯỠNG HAY ĐƯA LỜI KHUYÊN HÀNH ĐỘNG KHÔNG CÓ NGUỒN.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

CONFIG_MAC_DINH = Path(__file__).resolve().parents[1] / "config.yaml"
TU_VAN_KHUYEN_NONG = "Liên hệ cán bộ khuyến nông/khuyến ngư để được tư vấn."


@dataclass(frozen=True)
class ThongTinGiaiDoan:
    """Khoảng ngưỡng tham chiếu riêng cho một giai đoạn sinh trưởng của loài."""

    ten_giai_doan: str
    an_toan_min: float | None
    an_toan_max: float | None
    canh_bao_thap: tuple[float, float] | None
    canh_bao_cao: tuple[float, float] | None
    nguy_hiem_duoi: float | None
    nguy_hiem_tren: float | None
    nguon_tham_khao: str

    @property
    def co_du_lieu_nguon(self) -> bool:
        return bool(self.nguon_tham_khao.strip())

    def co_bat_ky_nguong(self) -> bool:
        return any(
            x is not None
            for x in (
                self.an_toan_min,
                self.an_toan_max,
                self.canh_bao_thap,
                self.canh_bao_cao,
                self.nguy_hiem_duoi,
                self.nguy_hiem_tren,
            )
        )


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
    giai_doan: tuple[ThongTinGiaiDoan, ...] = ()

    @property
    def co_du_lieu_nguon(self) -> bool:
        """Kiểm tra loài đã có trích dẫn nguồn tài liệu tham khảo hay chưa."""
        return bool(self.nguon_tham_khao.strip())

    def co_bat_ky_nguong(self) -> bool:
        return any(
            x is not None
            for x in (
                self.an_toan_min,
                self.an_toan_max,
                self.canh_bao_thap,
                self.canh_bao_cao,
                self.nguy_hiem_duoi,
                self.nguy_hiem_tren,
            )
        )


@dataclass(frozen=True)
class KetQuaDanhGiaLoai:
    """Kết quả đối chiếu mức độ mặn với ngưỡng tham chiếu của loài được chọn."""

    ma_loai: str
    ten_loai: str
    trang_thai: Literal[
        "AN_TOAN",
        "CANH_BAO",
        "NGUY_HIEM",
        "SAT_RANH_GIOI",
        "CHUA_CO_NGUON",
        "KHONG_DANH_GIA_DUOC",
    ]
    mau_sac: str                  # mã màu hiển thị giao diện ("#28a745", "#ffc107", "#dc3545", "#64748b", "#6c757d")
    tieu_de: str                  # thông điệp ngắn gọn
    loi_khuyen: str               # tóm tắt trạng thái, khoảng tham chiếu, giá trị đo, nguồn & hướng dẫn liên hệ
    nguon_tham_khao: str          # tài liệu tham khảo để học sinh bảo vệ luận điểm


def _tach_khoang_2(raw: Any) -> tuple[float, float] | None:
    if raw and len(raw) >= 2 and raw[0] is not None and raw[1] is not None:
        return (float(raw[0]), float(raw[1]))
    return None


def doc_danh_sach_loai(duong_dan_yaml: str | Path = CONFIG_MAC_DINH) -> dict[str, ThongTinLoai]:
    """Đọc toàn bộ danh mục ngưỡng sinh học từ config.yaml."""
    p = Path(duong_dan_yaml)
    if not p.exists():
        return {}

    with open(p, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    raw_nguong = data.get("nguong_loai", {}) or {}
    ket_qua: dict[str, ThongTinLoai] = {}

    for k, v in raw_nguong.items():
        if not isinstance(v, dict):
            continue

        at_tup = _tach_khoang_2(v.get("an_toan"))
        at_min = at_tup[0] if at_tup else None
        at_max = at_tup[1] if at_tup else None
        cb_thap_tup = _tach_khoang_2(v.get("canh_bao_thap"))
        cb_cao_tup = _tach_khoang_2(v.get("canh_bao_cao"))
        nguy_duoi = float(v["nguy_hiem_duoi"]) if v.get("nguy_hiem_duoi") is not None else None
        nguy_tren = float(v["nguy_hiem_tren"]) if v.get("nguy_hiem_tren") is not None else None

        ds_gd: list[ThongTinGiaiDoan] = []
        for gd in v.get("giai_doan") or []:
            if not isinstance(gd, dict):
                continue
            gd_at = _tach_khoang_2(gd.get("an_toan"))
            ds_gd.append(
                ThongTinGiaiDoan(
                    ten_giai_doan=str(gd.get("ten") or gd.get("ten_giai_doan") or "").strip() or "Giai đoạn",
                    an_toan_min=gd_at[0] if gd_at else None,
                    an_toan_max=gd_at[1] if gd_at else None,
                    canh_bao_thap=_tach_khoang_2(gd.get("canh_bao_thap")),
                    canh_bao_cao=_tach_khoang_2(gd.get("canh_bao_cao")),
                    nguy_hiem_duoi=float(gd["nguy_hiem_duoi"]) if gd.get("nguy_hiem_duoi") is not None else None,
                    nguy_hiem_tren=float(gd["nguy_hiem_tren"]) if gd.get("nguy_hiem_tren") is not None else None,
                    nguon_tham_khao=str(gd.get("nguon_tham_khao") or "").strip(),
                )
            )

        ket_qua[k] = ThongTinLoai(
            ma_loai=k,
            ten_hien_thi=str(v.get("ten", k)),
            an_toan_min=at_min,
            an_toan_max=at_max,
            canh_bao_thap=cb_thap_tup,
            canh_bao_cao=cb_cao_tup,
            nguy_hiem_duoi=nguy_duoi,
            nguy_hiem_tren=nguy_tren,
            nguon_tham_khao=str(v.get("nguon_tham_khao") or "").strip(),
            giai_doan=tuple(ds_gd),
        )

    return ket_qua


def _chon_muc_tieu(loai: ThongTinLoai, ten_giai_doan: str | None) -> tuple[Any, str]:
    if ten_giai_doan and loai.giai_doan:
        for gd in loai.giai_doan:
            if gd.ten_giai_doan.lower() == ten_giai_doan.strip().lower():
                return gd, f"{loai.ten_hien_thi} ({gd.ten_giai_doan})"
    return loai, loai.ten_hien_thi


def _dinh_dang_gia_tri_do(S_ppt: float, U: float) -> str:
    if U and U > 0:
        return f"{S_ppt:.2f} ± {U:.2f} ‰"
    return f"{S_ppt:.2f} ‰"


def _thong_diep_khach_quan(
    trang_thai_nhan: str,
    khoang_tham_chieu: str,
    S_ppt: float,
    U: float,
    nguon: str,
) -> str:
    return (
        f"Trạng thái: {trang_thai_nhan}. "
        f"Khoảng tham chiếu: {khoang_tham_chieu}. "
        f"Giá trị đo: {_dinh_dang_gia_tri_do(S_ppt, U)}. "
        f"Nguồn: {nguon}. "
        f"{TU_VAN_KHUYEN_NONG}"
    )


def _phan_vung_diem(val: float, muc_tieu: Any) -> str:
    """Xác định phân vùng cho một giá trị độ mặn đơn lẻ."""
    if muc_tieu.nguy_hiem_duoi is not None and val < muc_tieu.nguy_hiem_duoi:
        return "NGUY_HIEM_DUOI"
    if muc_tieu.nguy_hiem_tren is not None and val > muc_tieu.nguy_hiem_tren:
        return "NGUY_HIEM_TREN"
    if muc_tieu.canh_bao_thap and muc_tieu.canh_bao_thap[0] <= val < muc_tieu.canh_bao_thap[1]:
        return "CANH_BAO_THAP"
    if muc_tieu.canh_bao_cao and muc_tieu.canh_bao_cao[0] < val <= muc_tieu.canh_bao_cao[1]:
        return "CANH_BAO_CAO"
    if muc_tieu.an_toan_min is not None and muc_tieu.an_toan_max is not None:
        if muc_tieu.an_toan_min <= val <= muc_tieu.an_toan_max:
            return "AN_TOAN"
    return "CHUA_XAC_DINH"


def _cac_ranh_gioi(muc_tieu: Any) -> list[float]:
    moc: list[float] = []
    for v in (muc_tieu.nguy_hiem_duoi, muc_tieu.nguy_hiem_tren, muc_tieu.an_toan_min, muc_tieu.an_toan_max):
        if v is not None:
            moc.append(float(v))
    if muc_tieu.canh_bao_thap:
        moc.extend([float(muc_tieu.canh_bao_thap[0]), float(muc_tieu.canh_bao_thap[1])])
    if muc_tieu.canh_bao_cao:
        moc.extend([float(muc_tieu.canh_bao_cao[0]), float(muc_tieu.canh_bao_cao[1])])
    return moc


def tao_ket_qua_khong_danh_gia_duoc(
    loai: ThongTinLoai,
    S_ppt: float | None,
    U: float,
    ly_do: list[str],
    giai_doan: str | None = None,
) -> KetQuaDanhGiaLoai:
    """Trả kết quả trung tính KHONG_DANH_GIA_DUOC khi dữ liệu/ảnh/mô hình chưa đủ tin cậy."""
    muc_tieu, ten_day_du = _chon_muc_tieu(loai, giai_doan)
    val_str = _dinh_dang_gia_tri_do(S_ppt, U) if S_ppt is not None else "Không xác định"
    ly_do_str = "; ".join(ly_do) if ly_do else "Chưa đủ điều kiện tin cậy."
    return KetQuaDanhGiaLoai(
        ma_loai=loai.ma_loai,
        ten_loai=ten_day_du,
        trang_thai="KHONG_DANH_GIA_DUOC",
        mau_sac="#64748b",
        tieu_de="KHÔNG ĐÁNH GIÁ ĐƯỢC",
        loi_khuyen=(
            f"Không phân loại an toàn cho '{ten_day_du}' do: {ly_do_str}. "
            f"Giá trị ước lượng tham khảo: {val_str}. {TU_VAN_KHUYEN_NONG}"
        ),
        nguon_tham_khao=muc_tieu.nguon_tham_khao or "Chưa có nguồn tài liệu",
    )


def danh_gia_do_man_loai(
    S_ppt: float,
    loai: ThongTinLoai,
    U: float = 0.0,
    giai_doan: str | None = None,
) -> KetQuaDanhGiaLoai:
    """Đối chiếu khoảng bất định [S - U, S + U] với ngưỡng tham chiếu của loài."""
    muc_tieu, ten_day_du = _chon_muc_tieu(loai, giai_doan)
    if not muc_tieu.co_du_lieu_nguon or not muc_tieu.co_bat_ky_nguong():
        return KetQuaDanhGiaLoai(
            ma_loai=loai.ma_loai,
            ten_loai=ten_day_du,
            trang_thai="CHUA_CO_NGUON",
            mau_sac="#6c757d",
            tieu_de="CHƯA CÓ NGUỒN THAM KHẢO",
            loi_khuyen=(
                f"Đối tượng '{ten_day_du}' chưa có ngưỡng và nguồn trích dẫn trong config.yaml. "
                f"Giá trị đo: {_dinh_dang_gia_tri_do(S_ppt, U)}. "
                f"{TU_VAN_KHUYEN_NONG}"
            ),
            nguon_tham_khao="Chưa có - Cần bổ sung trong config.yaml",
        )

    nguon = muc_tieu.nguon_tham_khao
    u_val = max(float(U), 0.0)
    S_lo = max(0.0, S_ppt - u_val) if S_ppt >= 0.0 else (S_ppt - u_val)
    S_hi = S_ppt + u_val

    if u_val > 0.0:
        v_lo = _phan_vung_diem(S_lo, muc_tieu)
        v_giua = _phan_vung_diem(S_ppt, muc_tieu)
        v_hi = _phan_vung_diem(S_hi, muc_tieu)
        bat_cheo = (
            (v_lo != v_hi)
            or (v_lo != v_giua)
            or any(S_lo < moc < S_hi for moc in _cac_ranh_gioi(muc_tieu))
        )
        if bat_cheo:
            khoang_gt = f"[{S_lo:.2f} – {S_hi:.2f} ‰]"
            return KetQuaDanhGiaLoai(
                ma_loai=loai.ma_loai,
                ten_loai=ten_day_du,
                trang_thai="SAT_RANH_GIOI",
                mau_sac="#64748b",
                tieu_de=f"SÁT RANH GIỚI: Khoảng {khoang_gt} bắt chéo ngưỡng",
                loi_khuyen=_thong_diep_khach_quan(
                    f"SÁT RANH GIỚI (khoảng {khoang_gt})",
                    f"{v_lo} → {v_hi}",
                    S_ppt,
                    u_val,
                    nguon,
                ),
                nguon_tham_khao=nguon,
            )

    # 1. Kiểm tra mức NGUY HIỂM (cả khoảng [S - U, S + U] nằm trong vùng)
    if muc_tieu.nguy_hiem_duoi is not None and S_hi < muc_tieu.nguy_hiem_duoi:
        khoang = f"< {muc_tieu.nguy_hiem_duoi:g} ‰"
        return KetQuaDanhGiaLoai(
            ma_loai=loai.ma_loai,
            ten_loai=ten_day_du,
            trang_thai="NGUY_HIEM",
            mau_sac="#dc3545",
            tieu_de=f"NGUY HIỂM: Dưới ngưỡng tham chiếu ({khoang})",
            loi_khuyen=_thong_diep_khach_quan("NGUY HIỂM (dưới ngưỡng)", khoang, S_ppt, U, nguon),
            nguon_tham_khao=nguon,
        )

    if muc_tieu.nguy_hiem_tren is not None and S_lo > muc_tieu.nguy_hiem_tren:
        khoang = f"> {muc_tieu.nguy_hiem_tren:g} ‰"
        return KetQuaDanhGiaLoai(
            ma_loai=loai.ma_loai,
            ten_loai=ten_day_du,
            trang_thai="NGUY_HIEM",
            mau_sac="#dc3545",
            tieu_de=f"NGUY HIỂM: Vượt ngưỡng tham chiếu ({khoang})",
            loi_khuyen=_thong_diep_khach_quan("NGUY HIỂM (vượt ngưỡng)", khoang, S_ppt, U, nguon),
            nguon_tham_khao=nguon,
        )

    # 2. Kiểm tra mức CẢNH BÁO
    if muc_tieu.canh_bao_thap and muc_tieu.canh_bao_thap[0] <= S_lo and S_hi < muc_tieu.canh_bao_thap[1]:
        khoang = f"{muc_tieu.canh_bao_thap[0]:g} – {muc_tieu.canh_bao_thap[1]:g} ‰"
        return KetQuaDanhGiaLoai(
            ma_loai=loai.ma_loai,
            ten_loai=ten_day_du,
            trang_thai="CANH_BAO",
            mau_sac="#ffc107",
            tieu_de=f"CẢNH BÁO THẤP ({khoang})",
            loi_khuyen=_thong_diep_khach_quan("CẢNH BÁO THẤP", khoang, S_ppt, U, nguon),
            nguon_tham_khao=nguon,
        )

    if muc_tieu.canh_bao_cao and muc_tieu.canh_bao_cao[0] < S_lo and S_hi <= muc_tieu.canh_bao_cao[1]:
        khoang = f"{muc_tieu.canh_bao_cao[0]:g} – {muc_tieu.canh_bao_cao[1]:g} ‰"
        return KetQuaDanhGiaLoai(
            ma_loai=loai.ma_loai,
            ten_loai=ten_day_du,
            trang_thai="CANH_BAO",
            mau_sac="#ffc107",
            tieu_de=f"CẢNH BÁO CAO ({khoang})",
            loi_khuyen=_thong_diep_khach_quan("CẢNH BÁO CAO", khoang, S_ppt, U, nguon),
            nguon_tham_khao=nguon,
        )

    # 3. Kiểm tra mức AN TOÀN (chỉ khi toàn bộ [S - U, S + U] nằm trong an_toan)
    if muc_tieu.an_toan_min is not None and muc_tieu.an_toan_max is not None:
        if muc_tieu.an_toan_min <= S_lo and S_hi <= muc_tieu.an_toan_max:
            khoang = f"{muc_tieu.an_toan_min:g} – {muc_tieu.an_toan_max:g} ‰"
            return KetQuaDanhGiaLoai(
                ma_loai=loai.ma_loai,
                ten_loai=ten_day_du,
                trang_thai="AN_TOAN",
                mau_sac="#28a745",
                tieu_de=f"AN TOÀN: Nằm trong khoảng tham chiếu ({khoang})",
                loi_khuyen=_thong_diep_khach_quan("AN TOÀN", khoang, S_ppt, U, nguon),
                nguon_tham_khao=nguon,
            )

    # Trường hợp U == 0 nằm đúng tại biên không khớp nghiêm ngặt các nhánh trên
    v_pt = _phan_vung_diem(S_ppt, muc_tieu)
    if v_pt == "NGUY_HIEM_DUOI":
        khoang = f"< {muc_tieu.nguy_hiem_duoi:g} ‰"
        return KetQuaDanhGiaLoai(
            ma_loai=loai.ma_loai, ten_loai=ten_day_du, trang_thai="NGUY_HIEM", mau_sac="#dc3545",
            tieu_de=f"NGUY HIỂM: Dưới ngưỡng tham chiếu ({khoang})",
            loi_khuyen=_thong_diep_khach_quan("NGUY HIỂM (dưới ngưỡng)", khoang, S_ppt, U, nguon),
            nguon_tham_khao=nguon,
        )
    if v_pt == "NGUY_HIEM_TREN":
        khoang = f"> {muc_tieu.nguy_hiem_tren:g} ‰"
        return KetQuaDanhGiaLoai(
            ma_loai=loai.ma_loai, ten_loai=ten_day_du, trang_thai="NGUY_HIEM", mau_sac="#dc3545",
            tieu_de=f"NGUY HIỂM: Vượt ngưỡng tham chiếu ({khoang})",
            loi_khuyen=_thong_diep_khach_quan("NGUY HIỂM (vượt ngưỡng)", khoang, S_ppt, U, nguon),
            nguon_tham_khao=nguon,
        )

    return KetQuaDanhGiaLoai(
        ma_loai=loai.ma_loai,
        ten_loai=ten_day_du,
        trang_thai="CANH_BAO",
        mau_sac="#ffc107",
        tieu_de="CHƯA XÁC ĐỊNH PHÂN VÙNG",
        loi_khuyen=_thong_diep_khach_quan(
            "CHƯA XÁC ĐỊNH PHÂN VÙNG", "ngoài các khoảng cấu hình", S_ppt, U, nguon
        ),
        nguon_tham_khao=nguon,
    )
