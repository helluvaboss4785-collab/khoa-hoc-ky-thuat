"""Hiệu chuẩn, bù nhiệt và ước lượng bất định (Cột mốc 4).

Ý tưởng vật lí:
- Thiết bị đo ra Δy (pixel). Độ mặn S KHÔNG được tính thẳng từ công thức Snell vì
  các hằng số (n0, dn/dS, dn/dT, D, kích thước pixel, góc A thật) đều chỉ là xấp xỉ.
  Thay vào đó ta ĐO Δy với các dung dịch NaCl đã biết độ mặn (pha bằng cân và bình
  định mức) ở vài nhiệt độ, rồi dựng ĐƯỜNG CHUẨN thực nghiệm:

      Δy = f(S, T)   (đa thức bậc thấp theo S và ΔT = T − T_ref)

  Bậc 1:  Δy = c0 + c_S·S + c_T·ΔT
  Bậc 2:  thêm c_SS·S² + c_ST·S·ΔT + c_TT·ΔT²
  (S·ΔT mô tả việc độ nhạy theo độ mặn thay đổi theo nhiệt độ.)

- Khi đo mẫu chưa biết: giải ngược S = g(Δy, T) bằng cách tìm nghiệm f(S, T) = Δy.
- Bất định của S (truyền sai số bậc 1):

      u_S² = [σ_Δy² + s_res² + u_fit² + (∂f/∂T·σ_T)²] / (∂f/∂S)²

  trong đó s_res là độ tản mát của điểm chuẩn quanh đường chuẩn (độ lặp lại),
  u_fit là bất định do hệ số đường chuẩn (từ ma trận hiệp phương sai).
  Bất định mở rộng U = k·u_S (k = 2 ≈ 95%).

Giới hạn quan trọng (phải nói rõ khi phỏng vấn):
- Đường chuẩn dựng bằng NaCl. Nước tự nhiên chứa nhiều ion khác nên kết quả chỉ là
  "độ mặn tương đương NaCl".
- Ngoài dải S, T đã hiệu chuẩn thì kết quả là NGOẠI SUY, không đáng tin.
- Chỉ dùng numpy/scipy/pandas, không dùng thư viện học máy để học sinh tự giải thích được.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import IO, Any

import numpy as np
import pandas as pd
import yaml

CONFIG_MAC_DINH = Path(__file__).resolve().parents[1] / "config.yaml"


class LoiMoHinhHieuChuanError(ValueError):
    """Lỗi khi giải ngược mô hình đường chuẩn (ngoài miền nghiệm hoặc suy biến)."""

# ---------------------------------------------------------------------------
# Tên cột CSV
# ---------------------------------------------------------------------------
COT_DO_MAN = "do_man_chuan_ppt"        # độ mặn chuẩn của dung dịch (‰)
COT_NHIET_DO = "nhiet_do_C"            # nhiệt độ mẫu khi đo (°C)
COT_NHIET_DO_TC = "nhiet_do_tham_chieu_C"  # nhiệt độ ngăn tham chiếu (°C, tùy chọn)
COT_DELTA_Y = "delta_y_px"             # Δy đo được (pixel)
COT_PX_PER_MM = "px_per_mm"            # thang pixel/mm của ảnh (tùy chọn)
COT_DO_DUC = "do_duc_tuong_doi"        # chỉ số độ đục tương đối (0–1)
COT_MA_ME_PHA = "ma_me_pha"            # mã mẻ dung dịch chuẩn (tùy chọn - dùng chia nhóm GroupKFold)
COT_NGAY_DO = "ngay_do"                # ngày/đợt đo (tùy chọn)
COT_GHI_CHU = "ghi_chu"
COT_ID_THIET_BI = "id_thiet_bi"
COT_ID_DIEN_THOAI = "id_dien_thoai"
COT_NGUON = "nguon_du_lieu"            # (tùy chọn) "THUC_TE" hoặc "MO_PHONG"
COT_KHOA_AE_AF = "khoa_ae_af"          # (tùy chọn) 1/0: đã khóa phơi sáng/lấy nét
COT_OFFSET_NHIET_KE = "offset_nhiet_ke_C"  # (tùy chọn) độ lệch nhiệt kế ngăn tham chiếu − mẫu
COT_NHIET_DO_TC_DOC = "nhiet_do_tham_chieu_doc_C"  # (tùy chọn) số đọc thô trước khi trừ offset
COT_SHA256_ANH = "sha256_anh"
COT_TEN_FILE = "ten_file"

def phat_hien_ban_sao_du_lieu(df_raw: pd.DataFrame) -> dict[str, Any]:
    """Phát hiện dòng bản sao hoặc nghi ngờ gán nhãn lại trên DataFrame hiệu chuẩn (W1).

    Chỉ kiểm ba dấu hiệu định danh tường minh (KHÔNG dùng heuristic độ phân tán nhỏ để tránh dương tính giả):
      (a) Dòng trùng hệt toàn bộ cột;
      (b) Dòng trùng `sha256_anh` (khi có cột), kèm cờ nghi ngờ gán nhãn lại nếu `delta_y_px` khác nhau;
      (c) Dòng trùng `ten_file` (khi có cột) với `delta_y_px` khác nhau (nghi ngờ gán nhãn lại).
    """
    n_tong = int(len(df_raw))
    if n_tong == 0:
        return {
            "co_ban_sao": False,
            "co_nghi_ngo_gan_nhan_lai": False,
            "so_dong_tong": 0,
            "so_dong_ban_sao": 0,
            "so_dong_sau_loai": 0,
            "ti_le_ban_sao": 0.0,
            "so_dong_trung_het": 0,
            "so_dong_trung_sha256": 0,
            "so_dong_trung_ten_file_khac_dy": 0,
            "so_dong_nghi_gan_nhan_lai": 0,
            "mask_ban_sao": np.zeros(0, dtype=bool),
            "dong_nghi_ngo_dau_tien": [],
            "chi_tiet_nghi_ngo": [],
        }

    df = df_raw.copy()
    df.columns = [str(c).strip() for c in df.columns]

    dup_exact = df.duplicated(keep="first").to_numpy(dtype=bool)
    dup_sha = np.zeros(n_tong, dtype=bool)
    dup_ten_khac_dy = np.zeros(n_tong, dtype=bool)
    relabel_mask = np.zeros(n_tong, dtype=bool)
    chi_tiet: list[str] = []

    dy_num = (
        pd.to_numeric(df[COT_DELTA_Y], errors="coerce").to_numpy(dtype=float)
        if COT_DELTA_Y in df.columns
        else None
    )

    def _dy_khac_nhau(pos_list: list[int]) -> bool:
        if dy_num is None or len(pos_list) < 2:
            return False
        vals = dy_num[pos_list]
        finite = vals[np.isfinite(vals)]
        if len(finite) == 0:
            return False
        if len(finite) != len(vals):
            return True
        return float(np.max(finite) - np.min(finite)) > 1e-6

    def _norm_key_series(col: str, lower: bool = True) -> list[str]:
        out: list[str] = []
        for v in df[col]:
            if pd.isna(v):
                out.append("")
                continue
            s = str(v).strip()
            up = s.upper()
            if not s or up in {"NAN", "NONE", "NULL"}:
                out.append("")
            else:
                out.append(s.lower() if lower else s)
        return out

    if COT_SHA256_ANH in df.columns:
        sha_keys = _norm_key_series(COT_SHA256_ANH, lower=True)
        by_sha: dict[str, list[int]] = {}
        for pos, k in enumerate(sha_keys):
            if k:
                by_sha.setdefault(k, []).append(pos)
        for sha_k, idxs in by_sha.items():
            if len(idxs) >= 2:
                for pos in idxs[1:]:
                    dup_sha[pos] = True
                if _dy_khac_nhau(idxs):
                    for pos in idxs:
                        relabel_mask[pos] = True
                    chi_tiet.append(
                        f"sha256_anh={sha_k[:12]}... lặp {len(idxs)} lần với delta_y_px khác nhau (nghi ngờ gán nhãn lại)"
                    )

    if COT_TEN_FILE in df.columns and dy_num is not None:
        tf_keys = _norm_key_series(COT_TEN_FILE, lower=False)
        by_tf: dict[str, list[int]] = {}
        for pos, k in enumerate(tf_keys):
            if k:
                by_tf.setdefault(k, []).append(pos)
        for tf_k, idxs in by_tf.items():
            if len(idxs) >= 2 and _dy_khac_nhau(idxs):
                for pos in idxs[1:]:
                    dup_ten_khac_dy[pos] = True
                for pos in idxs:
                    relabel_mask[pos] = True
                chi_tiet.append(
                    f"ten_file='{tf_k}' lặp {len(idxs)} lần với delta_y_px khác nhau (nghi ngờ gán nhãn lại)"
                )

    mask_ban_sao = dup_exact | dup_sha | dup_ten_khac_dy
    so_dong_ban_sao = int(np.count_nonzero(mask_ban_sao))
    co_gan_nhan_lai = bool(np.any(relabel_mask))
    if np.any(dup_exact) and not chi_tiet:
        chi_tiet.append(f"{int(np.count_nonzero(dup_exact))} dòng trùng hệt toàn bộ cột")

    dong_nghi_ngo_idxs = np.flatnonzero(mask_ban_sao | relabel_mask)
    dong_dau_tien = [int(i) + 1 for i in dong_nghi_ngo_idxs[:5]]

    return {
        "co_ban_sao": so_dong_ban_sao > 0 or co_gan_nhan_lai,
        "co_nghi_ngo_gan_nhan_lai": co_gan_nhan_lai,
        "so_dong_tong": n_tong,
        "so_dong_ban_sao": so_dong_ban_sao,
        "so_dong_sau_loai": n_tong - so_dong_ban_sao,
        "ti_le_ban_sao": (so_dong_ban_sao / float(n_tong)) if n_tong else 0.0,
        "so_dong_trung_het": int(np.count_nonzero(dup_exact)),
        "so_dong_trung_sha256": int(np.count_nonzero(dup_sha)),
        "so_dong_trung_ten_file_khac_dy": int(np.count_nonzero(dup_ten_khac_dy)),
        "so_dong_nghi_gan_nhan_lai": int(np.count_nonzero(relabel_mask)),
        "mask_ban_sao": mask_ban_sao,
        "dong_nghi_ngo_dau_tien": dong_dau_tien,
        "chi_tiet_nghi_ngo": chi_tiet,
    }


COT_BAT_BUOC = [
    COT_DO_MAN, COT_NHIET_DO, COT_DELTA_Y, COT_DO_DUC,
    COT_GHI_CHU, COT_ID_THIET_BI, COT_ID_DIEN_THOAI,
]

# Một số tên cột khác mà học sinh có thể dùng khi tự nhập bảng tính
BI_DANH_COT = {
    "do_man": COT_DO_MAN, "S_ppt": COT_DO_MAN, "do_man_ppt": COT_DO_MAN,
    "nhiet_do": COT_NHIET_DO, "T_C": COT_NHIET_DO,
    "T_tc": COT_NHIET_DO_TC, "nhiet_do_tc": COT_NHIET_DO_TC, "T_tham_chieu_C": COT_NHIET_DO_TC,
    "delta_y": COT_DELTA_Y, "dy_px": COT_DELTA_Y,
    "px_mm": COT_PX_PER_MM, "scale_px_per_mm": COT_PX_PER_MM,
    "me_pha": COT_MA_ME_PHA, "batch_id": COT_MA_ME_PHA,
    "ngay": COT_NGAY_DO, "date": COT_NGAY_DO,
    "ae_af_lock": COT_KHOA_AE_AF,
    "do_duc": COT_DO_DUC,
    "id_dt": COT_ID_DIEN_THOAI, "id_phone": COT_ID_DIEN_THOAI,
}

NHAN_MO_PHONG = "MO_PHONG"
NHAN_THUC_TE = "THUC_TE"
NHAN_CHUA_XAC_DINH = "CHUA_XAC_DINH"
NHAN_CHUA_HIEU_CHUAN = "CHƯA HIỆU CHUẨN – DỮ LIỆU MÔ PHỎNG"
NHAN_CHUA_XAC_NHAN_NGUON = "CHƯA XÁC NHẬN NGUỒN DỮ LIỆU"
NHAN_DA_HIEU_CHUAN_THAT = "ĐÃ HIỆU CHUẨN (dữ liệu đo thật)"
HAN_CHE_NACL = (
    "Đường chuẩn dựng bằng dung dịch NaCl. Nước tự nhiên còn nhiều ion khác "
    "(Mg²⁺, Ca²⁺, K⁺, SO₄²⁻, HCO₃⁻…) và chất hữu cơ hòa tan, nên chiết suất có thể "
    "khác dung dịch NaCl cùng độ mặn. Kết quả chỉ là ĐỘ MẶN TƯƠNG ĐƯƠNG NaCl (ước lượng)."
)


# ---------------------------------------------------------------------------
# Cấu hình
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CauHinhHieuChuan:
    """Tham số dựng đường chuẩn, đọc từ mục `hieu_chuan` của config.yaml."""

    ti_le_test: float = 0.25
    so_fold: int = 5
    nguong_cai_thien_bac2: float = 0.10
    he_so_phu_k: float = 2.0
    sai_so_nhiet_ke_C: float = 0.5
    nguong_lech_T_khong_bu_C: float = 1.0
    nguong_lech_T_hai_ngan_C: float = 0.5
    sigma_D_khi_chua_do_C: float = 2.0
    ap_dung_hieu_chinh_ly_thuyet_D: bool = False
    cho_phep_giam_sigma_D_khi_on_dinh: bool = False
    sigma_D_khi_da_on_dinh_C: float = 1.0
    thoi_gian_on_dinh_toi_thieu_phut: float = 5.0
    nguong_bien_thien_px_per_mm_phan_tram: float = 2.0
    sai_so_dung_dich_chuan_ppt: float | None = None
    nhiet_do_toi_thieu_phu_C: float | None = None
    seed: int = 0

    @classmethod
    def tu_yaml(cls, duong_dan: str | Path = CONFIG_MAC_DINH) -> "CauHinhHieuChuan":
        """Đọc cấu hình; thiếu mục nào thì dùng giá trị mặc định ở trên."""
        with open(duong_dan, encoding="utf-8") as f:
            c = (yaml.safe_load(f) or {}).get("hieu_chuan", {}) or {}
        mac_dinh = cls()
        raw_dd = c.get("sai_so_dung_dich_chuan_ppt", mac_dinh.sai_so_dung_dich_chuan_ppt)
        raw_t_phu = c.get("nhiet_do_toi_thieu_phu_C", mac_dinh.nhiet_do_toi_thieu_phu_C)
        return cls(
            ti_le_test=float(c.get("ti_le_tap_test", mac_dinh.ti_le_test)),
            so_fold=int(c.get("so_fold_kiem_dinh_cheo", mac_dinh.so_fold)),
            nguong_cai_thien_bac2=float(c.get("nguong_cai_thien_bac2", mac_dinh.nguong_cai_thien_bac2)),
            he_so_phu_k=float(c.get("he_so_phu_k", mac_dinh.he_so_phu_k)),
            sai_so_nhiet_ke_C=float(c.get("sai_so_nhiet_ke_C", mac_dinh.sai_so_nhiet_ke_C)),
            nguong_lech_T_khong_bu_C=float(c.get("nguong_lech_T_khong_bu_C", mac_dinh.nguong_lech_T_khong_bu_C)),
            nguong_lech_T_hai_ngan_C=float(c.get("nguong_lech_T_hai_ngan_C", mac_dinh.nguong_lech_T_hai_ngan_C)),
            sigma_D_khi_chua_do_C=float(c.get("sigma_D_khi_chua_do_C", mac_dinh.sigma_D_khi_chua_do_C)),
            ap_dung_hieu_chinh_ly_thuyet_D=bool(
                c.get("ap_dung_hieu_chinh_ly_thuyet_D", mac_dinh.ap_dung_hieu_chinh_ly_thuyet_D)
            ),
            cho_phep_giam_sigma_D_khi_on_dinh=bool(
                c.get("cho_phep_giam_sigma_D_khi_on_dinh", mac_dinh.cho_phep_giam_sigma_D_khi_on_dinh)
            ),
            sigma_D_khi_da_on_dinh_C=float(
                c.get("sigma_D_khi_da_on_dinh_C", mac_dinh.sigma_D_khi_da_on_dinh_C)
            ),
            thoi_gian_on_dinh_toi_thieu_phut=float(
                c.get("thoi_gian_on_dinh_toi_thieu_phut", mac_dinh.thoi_gian_on_dinh_toi_thieu_phut)
            ),
            nguong_bien_thien_px_per_mm_phan_tram=float(
                c.get("nguong_bien_thien_px_per_mm_phan_tram", mac_dinh.nguong_bien_thien_px_per_mm_phan_tram)
            ),
            sai_so_dung_dich_chuan_ppt=float(raw_dd) if raw_dd is not None else None,
            nhiet_do_toi_thieu_phu_C=float(raw_t_phu) if raw_t_phu is not None else None,
            seed=int(c.get("seed", mac_dinh.seed)),
        )


# ---------------------------------------------------------------------------
# Đọc CSV
# ---------------------------------------------------------------------------
def doc_csv_hieu_chuan(nguon: str | Path | IO[Any]) -> pd.DataFrame:
    """Đọc file CSV dữ liệu hiệu chuẩn và kiểm tra hợp lệ.

    Cột bắt buộc: do_man_chuan_ppt, nhiet_do_C, delta_y_px, do_duc_tuong_doi,
    ghi_chu, id_thiet_bi, id_dien_thoai. Cột tùy chọn: nguon_du_lieu.

    - Dòng thiếu S, T hoặc Δy bị loại (số dòng bị loại lưu ở df.attrs["so_dong_bi_loai"]).
    - Nếu không có cột nguon_du_lieu (hoặc để trống) thì gán "CHUA_XAC_DINH",
      TUYỆT ĐỐI KHÔNG mặc định là THUC_TE. Chỉ các dòng ghi rõ "THUC_TE" mới là đo thật.

    Raises:
        ValueError: thiếu cột bắt buộc hoặc không còn dòng hợp lệ.
    """
    df = pd.read_csv(nguon, encoding="utf-8-sig")
    df.columns = [str(c).strip() for c in df.columns]
    df = df.rename(columns={k: v for k, v in BI_DANH_COT.items() if k in df.columns})

    thieu = [c for c in COT_BAT_BUOC if c not in df.columns]
    if thieu:
        raise ValueError(
            f"File CSV thiếu cột bắt buộc: {', '.join(thieu)}. "
            f"Cần đủ các cột: {', '.join(COT_BAT_BUOC)}."
        )

    for c in (COT_DO_MAN, COT_NHIET_DO, COT_DELTA_Y, COT_DO_DUC):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    if COT_PX_PER_MM in df.columns:
        df[COT_PX_PER_MM] = pd.to_numeric(df[COT_PX_PER_MM], errors="coerce")
    if COT_KHOA_AE_AF in df.columns:
        df[COT_KHOA_AE_AF] = df[COT_KHOA_AE_AF].fillna(0)
    for c in (COT_GHI_CHU, COT_ID_THIET_BI, COT_ID_DIEN_THOAI):
        df[c] = df[c].fillna("").astype(str)
    for c_opt in (COT_MA_ME_PHA, COT_NGAY_DO):
        if c_opt in df.columns:
            df[c_opt] = df[c_opt].fillna("").astype(str).str.strip()
    if COT_NGUON not in df.columns:
        df[COT_NGUON] = NHAN_CHUA_XAC_DINH
    else:
        df[COT_NGUON] = (
            df[COT_NGUON]
            .fillna(NHAN_CHUA_XAC_DINH)
            .astype(str)
            .str.strip()
            .str.upper()
            .replace({"": NHAN_CHUA_XAC_DINH, "NAN": NHAN_CHUA_XAC_DINH, "NONE": NHAN_CHUA_XAC_DINH})
        )

    n_truoc = len(df)
    df = df.dropna(subset=[COT_DO_MAN, COT_NHIET_DO, COT_DELTA_Y]).reset_index(drop=True)
    df.attrs["so_dong_bi_loai"] = n_truoc - len(df)

    if COT_OFFSET_NHIET_KE in df.columns:
        df[COT_OFFSET_NHIET_KE] = pd.to_numeric(df[COT_OFFSET_NHIET_KE], errors="coerce")
    if COT_NHIET_DO_TC_DOC in df.columns:
        df[COT_NHIET_DO_TC_DOC] = pd.to_numeric(df[COT_NHIET_DO_TC_DOC], errors="coerce")

    if COT_NHIET_DO_TC not in df.columns:
        if COT_NHIET_DO_TC_DOC in df.columns:
            df[COT_NHIET_DO_TC] = df[COT_NHIET_DO_TC_DOC]
            thieu_tc = bool(df[COT_NHIET_DO_TC].isna().any())
            df[COT_NHIET_DO_TC] = df[COT_NHIET_DO_TC].fillna(df[COT_NHIET_DO])
            df.attrs["gia_dinh_can_bang_nhiet"] = thieu_tc
        else:
            df[COT_NHIET_DO_TC] = df[COT_NHIET_DO]
            df.attrs["gia_dinh_can_bang_nhiet"] = True
    else:
        df[COT_NHIET_DO_TC] = pd.to_numeric(df[COT_NHIET_DO_TC], errors="coerce")
        if COT_NHIET_DO_TC_DOC not in df.columns:
            df[COT_NHIET_DO_TC_DOC] = df[COT_NHIET_DO_TC]
        thieu_tc = bool(df[COT_NHIET_DO_TC].isna().any())
        df[COT_NHIET_DO_TC] = df[COT_NHIET_DO_TC].fillna(df[COT_NHIET_DO])
        df.attrs["gia_dinh_can_bang_nhiet"] = thieu_tc

    if COT_OFFSET_NHIET_KE in df.columns:
        # Giữ nguyên số đọc thô trong COT_NHIET_DO_TC_DOC và hiệu chỉnh T_tc trước khi học số hạng D
        off_vals = df[COT_OFFSET_NHIET_KE].fillna(0.0)
        base_tc_doc = df[COT_NHIET_DO_TC_DOC].fillna(df[COT_NHIET_DO_TC]) if COT_NHIET_DO_TC_DOC in df.columns else df[COT_NHIET_DO_TC]
        df[COT_NHIET_DO_TC] = base_tc_doc - off_vals

    if len(df) == 0:
        raise ValueError("Không còn dòng hợp lệ nào (thiếu S, T hoặc Δy).")
    if (df[COT_DO_MAN] < 0).any():
        raise ValueError("Có độ mặn chuẩn âm – kiểm tra lại dữ liệu.")
    return df


def xac_dinh_nguon_du_lieu(df: pd.DataFrame) -> str:
    """Xác định nguồn dữ liệu chuẩn của DataFrame theo nguyên tắc thận trọng.

    - Nếu có bất kì dòng nào là MO_PHONG / SIMULATED -> MO_PHONG.
    - Chỉ khi có ít nhất 1 dòng và MỌI dòng đều ghi rõ THUC_TE -> THUC_TE.
    - Các trường hợp còn lại (thiếu cột nguồn, có dòng trống hoặc CHUA_XAC_DINH) -> CHUA_XAC_DINH.
    """
    if len(df) == 0 or COT_NGUON not in df.columns:
        return NHAN_CHUA_XAC_DINH
    nguon = df[COT_NGUON].fillna(NHAN_CHUA_XAC_DINH).astype(str).str.strip().str.upper()
    if nguon.isin([NHAN_MO_PHONG, "SIMULATED"]).any():
        return NHAN_MO_PHONG
    if (nguon == NHAN_THUC_TE).all():
        return NHAN_THUC_TE
    return NHAN_CHUA_XAC_DINH


def la_du_lieu_mo_phong(df: pd.DataFrame) -> bool:
    """True nếu BẤT KÌ dòng nào được đánh dấu là mô phỏng (thận trọng: một dòng mô phỏng
    cũng làm cả đường chuẩn bị coi là chưa hiệu chuẩn thật)."""
    return xac_dinh_nguon_du_lieu(df) == NHAN_MO_PHONG


def la_du_lieu_thuc_te(df: pd.DataFrame) -> bool:
    """True chỉ khi mọi dòng đều được đánh dấu tường minh là THUC_TE."""
    return xac_dinh_nguon_du_lieu(df) == NHAN_THUC_TE


# ---------------------------------------------------------------------------
# Đa thức và khớp bình phương tối thiểu
# ---------------------------------------------------------------------------
def chon_so_hang(bac: int, co_T: bool, co_TT: bool, co_D: bool = False) -> list[str]:
    """Danh sách số hạng của đa thức.

    "1": hằng số; "S": S; "T": ΔT = T − T_ref; "D": chênh nhiệt độ hai ngăn T_mẫu − T_tc;
    "SS": S²; "ST": S·ΔT; "TT": ΔT²; "SD": S·D.
    - Không có nhiệt độ thay đổi trong dữ liệu (co_T=False) -> bỏ mọi số hạng chứa T.
    - Chỉ có 2 mức nhiệt độ -> không xác định được ΔT² (co_TT=False).
    - Chênh nhiệt độ hai ngăn D biến thiên (≥ 2 mức, cách nhau ≥ 0,5 °C) -> thêm D (và S·D ở bậc 2).
    """
    hang = ["1", "S"]
    if co_T:
        hang.append("T")
    if co_D:
        hang.append("D")
    if bac >= 2:
        hang.append("SS")
        if co_T:
            hang.append("ST")
            if co_TT:
                hang.append("TT")
        if co_D:
            hang.append("SD")
    return hang


def ma_tran_dac_trung(
    S: Any, T: Any, hang: list[str], T_ref: float, T_tc: Any = None
) -> np.ndarray:
    """Ma trận thiết kế X (mỗi dòng một phép đo, mỗi cột một số hạng)."""
    T_tc_val = T if T_tc is None else T_tc
    S_arr, T_arr, T_tc_arr = np.broadcast_arrays(
        np.atleast_1d(np.asarray(S, float)),
        np.atleast_1d(np.asarray(T, float)),
        np.atleast_1d(np.asarray(T_tc_val, float)),
    )
    dT = T_arr - T_ref
    D = T_arr - T_tc_arr
    gia_tri = {
        "1": np.ones_like(S_arr),
        "S": S_arr,
        "T": dT,
        "D": D,
        "SS": S_arr**2,
        "ST": S_arr * dT,
        "TT": dT**2,
        "SD": S_arr * D,
    }
    return np.column_stack([gia_tri[h] for h in hang])


@dataclass
class KetQuaKhop:
    """Kết quả khớp bình phương tối thiểu."""

    he_so: np.ndarray
    hiep_phuong_sai: np.ndarray
    s_res: float          # độ lệch chuẩn phần dư (px), đã chia cho bậc tự do n − p
    bac_tu_do: int
    phan_du: np.ndarray


def khop_binh_phuong_toi_thieu(
    S: np.ndarray, T: np.ndarray, y: np.ndarray, hang: list[str], T_ref: float,
    T_tc: np.ndarray | None = None,
) -> KetQuaKhop:
    """Khớp y = X·c bằng bình phương tối thiểu thường.

    Hiệp phương sai hệ số: Cov(c) = s_res²·(XᵀX)⁻¹, với s_res² = Σ(phần dư²)/(n − p).
    Giả định: sai số Δy độc lập, cùng phương sai; S, T chính xác hơn Δy nhiều.

    Raises:
        ValueError: nếu số điểm không lớn hơn số hệ số.
    """
    X = ma_tran_dac_trung(S, T, hang, T_ref, T_tc=T_tc)
    n, p = X.shape
    if n <= p:
        raise ValueError(f"Cần nhiều hơn {p} điểm để khớp {p} hệ số (đang có {n}).")
    he_so, *_ = np.linalg.lstsq(X, y, rcond=None)
    phan_du = y - X @ he_so
    bac_tu_do = n - p
    s2 = float(phan_du @ phan_du) / bac_tu_do
    cov = s2 * np.linalg.pinv(X.T @ X)
    return KetQuaKhop(he_so, cov, math.sqrt(s2), bac_tu_do, phan_du)


def _lay_nhom_me_pha(df: pd.DataFrame) -> np.ndarray | None:
    """Trả mảng tên mẻ pha chế nếu cột `ma_me_pha` đầy đủ và có >= 2 mẻ khác nhau."""
    if COT_MA_ME_PHA not in df.columns or len(df) == 0:
        return None
    vals = df[COT_MA_ME_PHA].fillna("").astype(str).str.strip()
    if (vals == "").any():
        return None
    arr = vals.to_numpy(dtype=str)
    if len(np.unique(arr)) < 2:
        return None
    return arr


def rmse_kiem_dinh_cheo(
    S: np.ndarray, T: np.ndarray, y: np.ndarray, hang: list[str], T_ref: float,
    so_fold: int = 5, seed: int = 0, T_tc: np.ndarray | None = None,
    nhom: np.ndarray | None = None,
) -> float:
    """RMSE kiểm định chéo k-phần (k-fold hoặc GroupKFold thuần NumPy theo `nhom`).

    Nếu truyền `nhom` (cùng số phần tử với `y`, >= 2 nhóm), thực hiện GroupKFold: mọi lần
    đo lặp của cùng một mẻ dung dịch luôn đi cùng nhau vào train hoặc validation.
    """
    n = len(y)
    rng = np.random.default_rng(seed)
    sai_so: list[float] = []
    if nhom is not None:
        u_groups = np.unique(nhom).copy()
        if len(u_groups) >= 2:
            rng.shuffle(u_groups)
            k_g = max(2, min(so_fold, len(u_groups)))
            for g_val in np.array_split(u_groups, k_g):
                mask_val = np.isin(nhom, g_val)
                val = np.nonzero(mask_val)[0]
                train = np.nonzero(~mask_val)[0]
                if len(train) <= len(hang) or len(val) == 0:
                    return float("inf")
                tc_tr = None if T_tc is None else T_tc[train]
                tc_val = None if T_tc is None else T_tc[val]
                kq = khop_binh_phuong_toi_thieu(S[train], T[train], y[train], hang, T_ref, T_tc=tc_tr)
                du_doan = ma_tran_dac_trung(S[val], T[val], hang, T_ref, T_tc=tc_val) @ kq.he_so
                sai_so.extend((y[val] - du_doan).tolist())
            return float(np.sqrt(np.mean(np.square(sai_so))))

    k = max(2, min(so_fold, n))
    chi_so = rng.permutation(n)
    for phan in np.array_split(chi_so, k):
        train = np.setdiff1d(chi_so, phan)
        if len(train) <= len(hang):
            return float("inf")
        tc_tr = None if T_tc is None else T_tc[train]
        tc_val = None if T_tc is None else T_tc[phan]
        kq = khop_binh_phuong_toi_thieu(S[train], T[train], y[train], hang, T_ref, T_tc=tc_tr)
        du_doan = ma_tran_dac_trung(S[phan], T[phan], hang, T_ref, T_tc=tc_val) @ kq.he_so
        sai_so.extend((y[phan] - du_doan).tolist())
    return float(np.sqrt(np.mean(np.square(sai_so))))


# ---------------------------------------------------------------------------
# Mô hình đường chuẩn
# ---------------------------------------------------------------------------
@dataclass
class MoHinhHieuChuan:
    """Đường chuẩn Δy = f(S, T) đã khớp, kèm thông tin để đánh giá độ tin cậy."""

    bac: int
    hang: list[str]
    he_so: list[float]
    hiep_phuong_sai: list[list[float]]
    s_res_px: float
    bac_tu_do: int
    T_ref: float
    co_bu_nhiet: bool
    S_min: float
    S_max: float
    T_min: float
    T_max: float
    so_diem: int
    R2: float
    RMSE_px: float
    la_mo_phong: bool
    nguon_du_lieu: str = ""
    co_bu_chenh_T: bool = False
    D_min: float = 0.0
    D_max: float = 0.0
    gia_dinh_can_bang_nhiet: bool = True
    don_vi_y: str = "px"
    id_thiet_bi: list[str] = field(default_factory=list)
    id_dien_thoai: list[str] = field(default_factory=list)
    ngay_tao: str = ""

    def __post_init__(self) -> None:
        if not self.nguon_du_lieu:
            self.nguon_du_lieu = NHAN_MO_PHONG if self.la_mo_phong else NHAN_CHUA_XAC_DINH
        else:
            self.nguon_du_lieu = str(self.nguon_du_lieu).strip().upper()
            if self.la_mo_phong:
                self.nguon_du_lieu = NHAN_MO_PHONG

    # --- tính toán ---------------------------------------------------------
    @property
    def da_xac_nhan_thuc_te(self) -> bool:
        """Chỉ True khi dữ liệu không phải mô phỏng và mọi dòng đều khai báo THUC_TE."""
        return (not self.la_mo_phong) and (self.nguon_du_lieu == NHAN_THUC_TE)

    @property
    def nhan(self) -> str:
        """Nhãn trạng thái hiển thị cho người dùng."""
        if self.la_mo_phong:
            return NHAN_CHUA_HIEU_CHUAN
        if self.da_xac_nhan_thuc_te:
            return NHAN_DA_HIEU_CHUAN_THAT
        return NHAN_CHUA_XAC_NHAN_NGUON

    def du_doan_delta_y(self, S: Any, T: Any, T_tc: Any = None) -> np.ndarray:
        """Δy dự đoán (px) tại (S, T, T_tc)."""
        return ma_tran_dac_trung(S, T, self.hang, self.T_ref, T_tc=T_tc) @ np.asarray(self.he_so)

    def _dao_ham(self, S: float, T: float, theo: str, T_tc: float | None = None) -> float:
        dT = T - self.T_ref
        D = 0.0 if T_tc is None else (T - T_tc)
        if theo == "S":
            d = {"1": 0.0, "S": 1.0, "T": 0.0, "D": 0.0, "SS": 2 * S, "ST": dT, "TT": 0.0, "SD": D}
        elif theo == "D":
            d = {"1": 0.0, "S": 0.0, "T": 0.0, "D": 1.0, "SS": 0.0, "ST": 0.0, "TT": 0.0, "SD": S}
        elif theo == "T_tc":
            d = {"1": 0.0, "S": 0.0, "T": 0.0, "D": -1.0, "SS": 0.0, "ST": 0.0, "TT": 0.0, "SD": -S}
        else:
            phan_d = 1.0 if T_tc is not None else 0.0
            phan_sd = S if T_tc is not None else 0.0
            d = {"1": 0.0, "S": 0.0, "T": 1.0, "D": phan_d, "SS": 0.0, "ST": S, "TT": 2 * dT, "SD": phan_sd}
        return float(sum(c * d[h] for c, h in zip(self.he_so, self.hang)))

    def dao_ham_theo_S(self, S: float, T: float, T_tc: float | None = None) -> float:
        """∂f/∂S (px/‰): độ nhạy thực nghiệm của thiết bị."""
        return self._dao_ham(S, T, "S", T_tc=T_tc)

    def dao_ham_theo_T(self, S: float, T: float, T_tc: float | None = None) -> float:
        """∂f/∂T (px/°C): ảnh hưởng nhiệt độ mẫu cần bù."""
        return self._dao_ham(S, T, "T", T_tc=T_tc)

    def dao_ham_theo_D(self, S: float, T: float, T_tc: float | None = None) -> float:
        """∂f/∂D (px/°C): độ nhạy theo chênh lệch nhiệt độ hai ngăn D = T_mẫu − T_tc."""
        return self._dao_ham(S, T, "D", T_tc=T_tc)

    def dao_ham_theo_T_tc(self, S: float, T: float, T_tc: float | None = None) -> float:
        """∂f/∂T_tc (px/°C): ảnh hưởng nhiệt độ ngăn tham chiếu."""
        return self._dao_ham(S, T, "T_tc", T_tc=T_tc)

    def phuong_sai_du_doan(self, S: float, T: float, T_tc: float | None = None) -> float:
        """u_fit² = xᵀ·Cov·x : phương sai của Δy dự đoán do bất định hệ số."""
        x = ma_tran_dac_trung(S, T, self.hang, self.T_ref, T_tc=T_tc)[0]
        return float(x @ np.asarray(self.hiep_phuong_sai) @ x)

    # --- lưu / đọc ---------------------------------------------------------
    def sang_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["NGUON"] = self.nguon_du_lieu
        d["nguon_du_lieu"] = self.nguon_du_lieu
        d["da_xac_nhan_thuc_te"] = self.da_xac_nhan_thuc_te
        d["nhan"] = self.nhan
        return d

    @classmethod
    def tu_dict(cls, d: dict[str, Any]) -> "MoHinhHieuChuan":
        ten_truong = cls.__dataclass_fields__.keys()
        kw = {k: v for k, v in d.items() if k in ten_truong}
        if not kw.get("nguon_du_lieu"):
            raw_ng = d.get("NGUON")
            if raw_ng:
                kw["nguon_du_lieu"] = str(raw_ng)
            elif d.get("la_mo_phong"):
                kw["nguon_du_lieu"] = NHAN_MO_PHONG
            else:
                kw["nguon_du_lieu"] = NHAN_CHUA_XAC_DINH
        return cls(**kw)

    def luu_json(self, duong_dan: str | Path) -> None:
        """Lưu hệ số đường chuẩn ra file JSON (đọc được bằng mắt)."""
        p = Path(duong_dan)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.sang_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def doc_json(cls, duong_dan: str | Path) -> "MoHinhHieuChuan":
        return cls.tu_dict(json.loads(Path(duong_dan).read_text(encoding="utf-8")))


def _so_muc(gia_tri: np.ndarray, buoc: float) -> int:
    """Đếm số mức khác nhau sau khi làm tròn theo bước `buoc`."""
    return int(len(np.unique(np.round(gia_tri / buoc))))


def _lay_nhiet_do_tc(df: pd.DataFrame) -> np.ndarray:
    if COT_NHIET_DO_TC in df.columns:
        t_tc = pd.to_numeric(df[COT_NHIET_DO_TC], errors="coerce")
        return t_tc.fillna(df[COT_NHIET_DO]).to_numpy(float)
    return df[COT_NHIET_DO].to_numpy(float)


def _xac_dinh_co_bu_nhiet(T: np.ndarray, T_tc: np.ndarray) -> tuple[bool, bool, bool]:
    """Xác định các số hạng nhiệt độ cần bật: (co_T, co_TT, co_D) và tránh đa cộng tuyến."""
    D = T - T_tc
    so_muc_T = _so_muc(T, 0.5)
    so_muc_D = _so_muc(D, 0.5)
    co_D = (so_muc_D >= 2) and (float(D.max() - D.min()) >= 0.5)
    co_T = so_muc_T >= 2
    co_TT = so_muc_T >= 3

    if co_D and co_T:
        so_muc_T_tc = _so_muc(T_tc, 0.5)
        std_T = float(np.std(T))
        std_D = float(np.std(D))
        tuong_quan_cao = (
            std_T > 0.0 and std_D > 0.0 and abs(float(np.corrcoef(T, D)[0, 1])) > 0.995
        )
        if so_muc_T_tc < 2 or tuong_quan_cao:
            # Nếu T_tc cố định khiến D và ΔT cộng tuyến hoàn toàn, ưu tiên số hạng vật lí D
            co_T = False
            co_TT = False

    return co_T, co_TT, co_D


def _lay_y_theo_don_vi(df: pd.DataFrame, don_vi_y: str) -> np.ndarray:
    """Trích xuất trục tung Δy theo đơn vị 'px' hoặc 'mm' (chia cho cột px_per_mm)."""
    y_px = df[COT_DELTA_Y].to_numpy(float)
    if don_vi_y == "mm":
        if COT_PX_PER_MM not in df.columns:
            raise ValueError("Dựng đường chuẩn theo mm yêu cầu cột 'px_per_mm' trong dữ liệu.")
        scale = pd.to_numeric(df[COT_PX_PER_MM], errors="coerce").to_numpy(float)
        bad_idx = [i for i, val in enumerate(scale) if (not math.isfinite(float(val))) or float(val) <= 0.0]
        if bad_idx:
            dong_loi: list[str] = []
            has_note = COT_GHI_CHU in df.columns
            for i in bad_idx[:8]:
                note = str(df[COT_GHI_CHU].iloc[i]).strip() if has_note else ""
                dong_loi.append(f"dòng {i + 1} ({note})" if note else f"dòng {i + 1}")
            extra = f" (+{len(bad_idx) - 8} dòng khác)" if len(bad_idx) > 8 else ""
            raise ValueError(
                f"Dựng đường chuẩn theo mm yêu cầu MỌI dòng có px_per_mm > 0; thiếu hoặc không hợp lệ tại: "
                f"{', '.join(dong_loi)}{extra}."
            )
        return y_px / scale
    if don_vi_y != "px":
        raise ValueError(f"don_vi_y '{don_vi_y}' không hợp lệ (chỉ hỗ trợ 'px' hoặc 'mm').")
    return y_px


def tao_mo_hinh(df: pd.DataFrame, bac: int, don_vi_y: str = "px") -> MoHinhHieuChuan:
    """Khớp đường chuẩn bậc `bac` trên toàn bộ DataFrame theo đơn vị `don_vi_y` ('px' | 'mm').

    - Bù nhiệt T chỉ bật khi dữ liệu có ≥ 2 mức nhiệt độ (cách nhau ≥ 0,5 °C).
    - Bù chênh nhiệt độ hai ngăn D = T_mẫu − T_tc bật khi D có ≥ 2 mức (cách nhau ≥ 0,5 °C).
    - Bậc 2 cần ≥ 3 mức độ mặn khác nhau.
    """
    S = df[COT_DO_MAN].to_numpy(float)
    T = df[COT_NHIET_DO].to_numpy(float)
    T_tc = _lay_nhiet_do_tc(df)
    D = T - T_tc
    y = _lay_y_theo_don_vi(df, don_vi_y)

    co_T, co_TT, co_D = _xac_dinh_co_bu_nhiet(T, T_tc)
    if bac >= 2 and _so_muc(S, 0.01) < 3:
        raise ValueError("Bậc 2 cần ít nhất 3 mức độ mặn chuẩn khác nhau.")

    T_ref = float(np.round(np.mean(T), 1))
    hang = chon_so_hang(bac, co_T, co_TT, co_D=co_D)
    kq = khop_binh_phuong_toi_thieu(S, T, y, hang, T_ref, T_tc=T_tc)

    ss_tot = float(np.sum((y - y.mean()) ** 2))
    ss_res = float(np.sum(kq.phan_du**2))
    nguon_du_lieu = xac_dinh_nguon_du_lieu(df)
    gia_dinh_cb = bool(df.attrs.get("gia_dinh_can_bang_nhiet", COT_NHIET_DO_TC not in df.columns))
    return MoHinhHieuChuan(
        bac=bac, hang=hang,
        he_so=[float(c) for c in kq.he_so],
        hiep_phuong_sai=[[float(v) for v in row] for row in kq.hiep_phuong_sai],
        s_res_px=kq.s_res, bac_tu_do=kq.bac_tu_do, T_ref=T_ref, co_bu_nhiet=co_T,
        S_min=float(S.min()), S_max=float(S.max()),
        T_min=float(T.min()), T_max=float(T.max()),
        so_diem=len(y),
        R2=1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan"),
        RMSE_px=float(np.sqrt(np.mean(kq.phan_du**2))),
        la_mo_phong=(nguon_du_lieu == NHAN_MO_PHONG),
        nguon_du_lieu=nguon_du_lieu,
        co_bu_chenh_T=co_D,
        D_min=float(D.min()),
        D_max=float(D.max()),
        gia_dinh_can_bang_nhiet=gia_dinh_cb,
        don_vi_y=don_vi_y,
        id_thiet_bi=sorted({str(v) for v in df[COT_ID_THIET_BI]} - {""}),
        id_dien_thoai=sorted({str(v) for v in df[COT_ID_DIEN_THOAI]} - {""}),
        ngay_tao=datetime.now().isoformat(timespec="seconds"),
    )


# ---------------------------------------------------------------------------
# Hàm ngược S = g(Δy, T) và bất định
# ---------------------------------------------------------------------------
@dataclass
class KetQuaDoMan:
    """Kết quả ước lượng độ mặn cho một phép đo."""

    S_ppt: float                       # độ mặn ước lượng (‰, tương đương NaCl)
    u_S_ppt: float                     # bất định chuẩn (1σ)
    U_S_ppt: float                     # bất định mở rộng U = k·u
    k: float
    thanh_phan_bat_dinh: dict[str, float]   # đóng góp từng nguồn (‰)
    ngoai_dai_S: bool
    ngoai_dai_T: bool
    la_mo_phong: bool
    nhan: str
    nguon_du_lieu: str = NHAN_CHUA_XAC_DINH
    da_xac_nhan_thuc_te: bool = False
    canh_bao: list[str] = field(default_factory=list)
    han_che: str = HAN_CHE_NACL
    ngoai_dai_D: bool = False
    chenh_T_ngoai_mo_hinh: bool = False
    khong_danh_gia_duoc: bool = False
    canh_bao_chi_tiet: list[dict[str, str]] = field(default_factory=list)
    mo_ta_thanh_phan_bat_dinh: dict[str, str] = field(default_factory=dict)
    giai_thich_bat_dinh: str = ""


def _do_nhay_S_theo_D_ly_thuyet_co_dau(S_ppt: float, T_C: float) -> float:
    """Độ nhạy lí thuyết có dấu ∂S/∂D = −(∂Δy/∂D)/(∂Δy/∂S) (‰/°C) từ core/optics.py.

    Dùng khi đường chuẩn chưa học số hạng D; phản ánh xấp xỉ quang học LÍ THUYẾT,
    KHÔNG phải giá trị đã hiệu chuẩn trên thiết bị thật.
    """
    from core import optics as op

    cfg = op.CauHinhQuangHoc.tu_yaml()
    h = 1e-2
    try:
        # Chú ý: khi D tăng (T_tc giảm), Δy_mẫu − Δy_tc = Δy tăng, nên để S giải ngược giữ nguyên
        # sau khi bị lệch nhiệt +∂Δy/∂D · D, độ lệch S là (∂Δy/∂D)/(∂Δy/∂S) · D.
        dy_dD = (
            op.delta_y_vi_sai_px(S_ppt, T_C, T_C - h, cfg)
            - op.delta_y_vi_sai_px(S_ppt, T_C, T_C + h, cfg)
        ) / (2.0 * h)
        px_per_ppt = op.pixel_moi_phan_nghin(S_ppt, T_C, cfg)
        if abs(px_per_ppt) > 1e-9 and math.isfinite(dy_dD):
            return float(dy_dD / px_per_ppt)
    except Exception:
        pass
    return float(cfg.dn_dT / cfg.dn_dS)


def _do_nhay_S_theo_D_ly_thuyet(S_ppt: float, T_C: float) -> float:
    """Độ nhạy lí thuyết |∂S/∂D| (‰/°C) lấy từ mô hình Snell trong core/optics.py."""
    return abs(_do_nhay_S_theo_D_ly_thuyet_co_dau(S_ppt, T_C))


def _tim_nghiem_S(
    mh: MoHinhHieuChuan, delta_y: float, T: float, T_tc: float | None = None
) -> float:
    """Tìm S sao cho f(S, T, T_tc) = Δy.

    Quét lưới trong khoảng rộng hơn dải hiệu chuẩn 50% mỗi phía để tìm các điểm đổi dấu,
    rồi tinh chỉnh bằng phương pháp chia đôi (brentq). Nếu có nhiều nghiệm (đa thức bậc 2
    không đơn điệu), chọn nghiệm nằm trong dải hiệu chuẩn hoặc gần dải nhất.
    """
    from scipy.optimize import brentq

    nhip = max(mh.S_max - mh.S_min, 1.0)
    lo, hi = mh.S_min - 0.5 * nhip, mh.S_max + 0.5 * nhip
    luoi = np.linspace(lo, hi, 801)
    g = mh.du_doan_delta_y(luoi, T, T_tc=T_tc) - delta_y
    nghiem: list[float] = []
    for i in np.nonzero(np.sign(g[:-1]) * np.sign(g[1:]) <= 0)[0]:
        a, b = luoi[i], luoi[i + 1]
        if g[i] == 0:
            nghiem.append(float(a))
        elif g[i] * g[i + 1] < 0:
            nghiem.append(
                float(brentq(lambda s: float(mh.du_doan_delta_y(s, T, T_tc=T_tc)[0]) - delta_y, a, b))
            )
    if not nghiem:
        raise LoiMoHinhHieuChuanError(
            f"Δy = {delta_y:.3f} ({getattr(mh, 'don_vi_y', 'px')}) nằm quá xa ngoài dải đường chuẩn "
            f"(S {mh.S_min:g}–{mh.S_max:g} ‰). Không ước lượng được độ mặn."
        )
    giua = 0.5 * (mh.S_min + mh.S_max)
    trong_dai = [s for s in nghiem if mh.S_min <= s <= mh.S_max]
    ung_vien = trong_dai or nghiem
    return min(ung_vien, key=lambda s: abs(s - giua))


def uoc_luong_do_man(
    mh: MoHinhHieuChuan,
    delta_y_px: float,
    T_C: float,
    sigma_delta_y_px: float = 0.0,
    sigma_T_C: float = 0.0,
    k: float = 2.0,
    nguong_lech_T_khong_bu_C: float = 1.0,
    T_tham_chieu_C: float | None = None,
    sigma_T_tham_chieu_C: float = 0.0,
    nguong_lech_T_hai_ngan_C: float = 0.5,
    px_per_mm: float | None = None,
    u_px_per_mm: float = 0.0,
    sigma_dung_dich_chuan_ppt: float | None = None,
    sigma_D_khi_chua_do_C: float = 2.0,
    ap_dung_hieu_chinh_ly_thuyet_D: bool = False,
    da_on_dinh_nhiet_gia_dinh: bool = False,
    offset_nhiet_ke_C: float | None = None,
    sigma_offset_nhiet_ke_C: float | None = None,
) -> KetQuaDoMan:
    """Ước lượng độ mặn từ Δy và nhiệt độ hai ngăn, kèm bất định và cờ cảnh báo.

    - Nếu thiếu `T_tham_chieu_C`: cộng thành phần bất định `chenh_nhiet_chua_do = σ_D × |∂S/∂D|`
      (từ mô hình nếu có số hạng D, ngược lại từ lí thuyết `core/optics.py` và ghi rõ).
    - Nếu nhập `T_tham_chieu_C` mà mô hình KHÔNG có số hạng D và |D| > `nguong_lech_T_hai_ngan_C`:
      đánh dấu `chenh_T_ngoai_mo_hinh = True`, `khong_danh_gia_duoc = True`, cộng cận trên độ chệch
      `|D| × |∂S/∂D|` vào u nhưng KHÔNG tự hiệu chỉnh S.
    - Nếu có `offset_nhiet_ke_C`: hiệu chỉnh `T_tc_eff = T_tham_chieu_C − offset` và cộng `σ_offset²`
      vào `σ_Dđo²`; ngược lại giữ nguyên tính toán và thêm cờ `nhiet_ke_chua_hieu_chuan_cheo`.
    - Nếu mô hình có `don_vi_y == "mm"`, bắt buộc truyền `px_per_mm > 0`.
    """
    if not (math.isfinite(delta_y_px) and math.isfinite(T_C)):
        raise ValueError("Δy hoặc nhiệt độ không hợp lệ (NaN/vô cực).")
    if T_tham_chieu_C is not None and not math.isfinite(T_tham_chieu_C):
        raise ValueError("Nhiệt độ ngăn tham chiếu không hợp lệ (NaN/vô cực).")

    off_nk = (
        float(offset_nhiet_ke_C)
        if (offset_nhiet_ke_C is not None and math.isfinite(float(offset_nhiet_ke_C)))
        else None
    )
    sig_off_nk = (
        max(float(sigma_offset_nhiet_ke_C), 0.0)
        if (off_nk is not None and sigma_offset_nhiet_ke_C is not None and math.isfinite(float(sigma_offset_nhiet_ke_C)))
        else 0.0
    )
    T_tc_eff = (float(T_tham_chieu_C) - off_nk) if (T_tham_chieu_C is not None and off_nk is not None) else T_tham_chieu_C

    if getattr(mh, "don_vi_y", "px") == "mm":
        if px_per_mm is None or not math.isfinite(px_per_mm) or px_per_mm <= 0.0:
            raise LoiMoHinhHieuChuanError(
                "Đường chuẩn tính theo mm nhưng chưa có thang px_per_mm (> 0) cho ảnh này."
            )
        y_do = float(delta_y_px) / float(px_per_mm)
        u_do_px = abs(float(sigma_delta_y_px)) / float(px_per_mm)
        u_thang = (abs(float(delta_y_px)) / (float(px_per_mm) ** 2)) * max(float(u_px_per_mm), 0.0)
        sigma_y_do = math.hypot(u_do_px, u_thang)
    else:
        y_do = float(delta_y_px)
        sigma_y_do = abs(float(sigma_delta_y_px))

    S = _tim_nghiem_S(mh, y_do, T_C, T_tc=T_tc_eff)
    f_S = mh.dao_ham_theo_S(S, T_C, T_tc=T_tc_eff)
    if abs(f_S) < 1e-9:
        raise LoiMoHinhHieuChuanError("Độ nhạy ∂Δy/∂S ≈ 0 tại điểm này – không giải ngược được.")
    f_T = (
        mh.dao_ham_theo_T(S, T_C, T_tc=T_tc_eff)
        if (mh.co_bu_nhiet or (T_tc_eff is not None and mh.co_bu_chenh_T))
        else 0.0
    )
    f_T_tc = (
        mh.dao_ham_theo_T_tc(S, T_C, T_tc=T_tc_eff)
        if (mh.co_bu_chenh_T and T_tc_eff is not None)
        else 0.0
    )
    sigma_T_tc_eff = math.hypot(abs(float(sigma_T_tham_chieu_C)), sig_off_nk) if off_nk is not None else sigma_T_tham_chieu_C

    thanh_phan = {
        "do_anh": abs(sigma_y_do / f_S),
        "lap_lai_duong_chuan": abs(mh.s_res_px / f_S),
        "he_so_duong_chuan": math.sqrt(max(mh.phuong_sai_du_doan(S, T_C, T_tc=T_tc_eff), 0.0)) / abs(f_S),
        "nhiet_do": abs(f_T * sigma_T_C / f_S),
    }
    mo_ta_thanh_phan: dict[str, str] = {}
    if T_tc_eff is not None or sigma_T_tham_chieu_C > 0 or mh.co_bu_chenh_T:
        thanh_phan["nhiet_do_tham_chieu"] = abs(f_T_tc * sigma_T_tc_eff / f_S)
    if sigma_dung_dich_chuan_ppt is not None and float(sigma_dung_dich_chuan_ppt) > 0.0:
        thanh_phan["dung_dich_chuan"] = float(sigma_dung_dich_chuan_ppt)

    canh_bao_chi_tiet: list[dict[str, str]] = []

    def _them_canh_bao(ma: str, cap: str, noi_dung: str) -> None:
        canh_bao_chi_tiet.append({"ma": ma, "cap": cap, "noi_dung": noi_dung})

    if off_nk is None:
        _them_canh_bao(
            "nhiet_ke_chua_hieu_chuan_cheo",
            "can_than",
            "Độ lệch hệ thống giữa hai nhiệt kế chưa được xác định nên có thể bị chặn oan hoặc U lớn.",
        )

    if sigma_dung_dich_chuan_ppt is None:
        _them_canh_bao(
            "CHUA_KHAI_BAO_DUNG_DICH_CHUAN",
            "thong_tin",
            "Chưa khai báo bất định của dung dịch chuẩn (hieu_chuan.sai_so_dung_dich_chuan_ppt đang để null).",
        )
    if getattr(mh, "don_vi_y", "px") == "px":
        _them_canh_bao(
            "DON_VI_PX",
            "thong_tin",
            "Đường chuẩn theo pixel: chỉ đúng cho đúng một cấu hình camera và khoảng cách.",
        )

    ngoai_T = not (mh.T_min - 0.5 <= T_C <= mh.T_max + 0.5)
    if ngoai_T:
        _them_canh_bao(
            "NGOAI_DAI_T",
            "nghiem_trong",
            f"Nhiệt độ {T_C:.1f} °C nằm ngoài khoảng đã hiệu chuẩn "
            f"({mh.T_min:.1f}–{mh.T_max:.1f} °C): bù nhiệt là ngoại suy.",
        )
    if not mh.co_bu_nhiet and not mh.co_bu_chenh_T and abs(T_C - mh.T_ref) > nguong_lech_T_khong_bu_C:
        _them_canh_bao(
            "KHONG_BU_NHIET",
            "can_than",
            f"Đường chuẩn chỉ đo ở một nhiệt độ (~{mh.T_ref:.1f} °C) nên KHÔNG bù nhiệt; "
            f"mẫu đang ở {T_C:.1f} °C. Hãy hiệu chuẩn thêm ở nhiều nhiệt độ.",
        )

    ngoai_dai_D = False
    chenh_T_ngoai_mo_hinh = False
    if T_tc_eff is None:
        if mh.co_bu_chenh_T:
            he_so_d = abs(mh.dao_ham_theo_D(S, T_C, T_tc=T_C) / f_S)
            nguon_d = "từ đường chuẩn đã học D"
        else:
            he_so_d = _do_nhay_S_theo_D_ly_thuyet(S, T_C)
            nguon_d = "hệ số ∂S/∂D LÍ THUYẾT (core/optics.py), chưa hiệu chuẩn"
        sig_d = max(float(sigma_D_khi_chua_do_C), 0.0)
        u_chua_do = sig_d * he_so_d
        thanh_phan["chenh_nhiet_chua_do"] = u_chua_do
        if da_on_dinh_nhiet_gia_dinh:
            mo_ta_thanh_phan["chenh_nhiet_chua_do"] = (
                f"Giả định giảm σ_D={sig_d:g} °C nhờ Δy(t) ổn định ({nguon_d}; "
                "LƯU Ý: ổn định Δy không chứng minh D = 0)"
            )
            _them_canh_bao(
                "chenh_nhiet_gia_dinh_on_dinh",
                "can_than",
                f"Đã áp dụng giả định giảm bất định chênh nhiệt còn σ_D={sig_d:g} °C do chuỗi Δy(t) đã ổn định: "
                f"đây chỉ là GIẢ ĐỊNH (ổn định Δy không chứng minh chênh nhiệt hai ngăn D = 0; ±{k * u_chua_do:.2f} ‰ theo {nguon_d}).",
            )
        else:
            mo_ta_thanh_phan["chenh_nhiet_chua_do"] = f"Bất định chênh nhiệt chưa đo (σ_D={sig_d:g} °C, {nguon_d})"
            _them_canh_bao(
                "THIEU_T_THAM_CHIEU",
                "can_than",
                f"Chưa đo nhiệt độ ngăn tham chiếu (giả định cân bằng nhiệt, σ_D={sig_d:g} °C): "
                f"chênh nhiệt hai ngăn có thể làm lệch tới ±{k * u_chua_do:.2f} ‰ ({nguon_d}).",
            )
    else:
        chenh_T = T_C - T_tc_eff
        if not mh.co_bu_chenh_T:
            sigma_D_do = math.sqrt(float(sigma_T_C) ** 2 + float(sigma_T_tham_chieu_C) ** 2 + sig_off_nk ** 2)
            k_D_signed = _do_nhay_S_theo_D_ly_thuyet_co_dau(S, T_C)
            he_so_d_lt = abs(k_D_signed)
            ghi_offset = f", đã trừ offset={off_nk:+.3f}±{sig_off_nk:.3f} °C" if off_nk is not None else ""
            if ap_dung_hieu_chinh_ly_thuyet_D:
                S = S - k_D_signed * chenh_T
                thanh_phan["chenh_nhiet_con_lai"] = he_so_d_lt * sigma_D_do
                mo_ta_thanh_phan["chenh_nhiet_con_lai"] = (
                    f"Bất định còn lại sau hiệu chỉnh lí thuyết −k_D·D "
                    f"(σ_Dđo={sigma_D_do:.2f} °C{ghi_offset}; dùng hệ số ∂S/∂D LÍ THUYẾT từ core/optics.py, không phải đã hiệu chuẩn)"
                )
                if abs(chenh_T) > 0.0:
                    _them_canh_bao(
                        "HIEU_CHINH_LY_THUYET_D",
                        "can_than",
                        f"Đã hiệu chỉnh chênh nhiệt D = {chenh_T:+.2f} °C theo hệ số ∂S/∂D LÍ THUYẾT "
                        f"({k_D_signed:+.3f} ‰/°C từ core/optics.py, chưa hiệu chuẩn thực nghiệm).",
                    )
            elif abs(chenh_T) > nguong_lech_T_hai_ngan_C:
                chenh_T_ngoai_mo_hinh = True
                u_bias = abs(chenh_T) * he_so_d_lt
                thanh_phan["chenh_nhiet_ngoai_mo_hinh"] = u_bias
                mo_ta_thanh_phan["chenh_nhiet_ngoai_mo_hinh"] = (
                    "Cận trên độ chệch theo hệ số LÍ THUYẾT (core/optics.py), chưa hiệu chuẩn; KHÔNG tự hiệu chỉnh S"
                )
                thanh_phan["chenh_nhiet_con_lai"] = he_so_d_lt * sigma_D_do
                mo_ta_thanh_phan["chenh_nhiet_con_lai"] = (
                    f"Bất định đo chênh nhiệt từ độ chính xác nhiệt kế (σ_Dđo={sigma_D_do:.2f} °C{ghi_offset}; "
                    "hệ số ∂S/∂D LÍ THUYẾT từ core/optics.py, không phải đã hiệu chuẩn)"
                )
                _them_canh_bao(
                    "CHENH_NHIET_NGOAI_MO_HINH",
                    "nghiem_trong",
                    f"Chênh nhiệt độ hai ngăn |D| = {abs(chenh_T):.2f} °C > {nguong_lech_T_hai_ngan_C:g} °C "
                    f"nhưng đường chuẩn CHƯA học số hạng D (không hiệu chỉnh tự động; độ chệch ước tính theo lí thuyết tới ±{u_bias:.2f} ‰). "
                    "Hãy đợi cân bằng nhiệt hoặc hiệu chuẩn lại có biến thiên D.",
                )
            else:
                thanh_phan["chenh_nhiet_con_lai"] = he_so_d_lt * math.hypot(chenh_T, sigma_D_do)
                mo_ta_thanh_phan["chenh_nhiet_con_lai"] = (
                    f"Chênh nhiệt hai ngăn còn lại (D={chenh_T:+.2f} °C) và độ chính xác nhiệt kế "
                    f"(σ_Dđo={sigma_D_do:.2f} °C{ghi_offset}); dùng hệ số ∂S/∂D LÍ THUYẾT (core/optics.py), không phải đã hiệu chuẩn"
                )
        else:
            ngoai_dai_D = not (mh.D_min - 0.2 <= chenh_T <= mh.D_max + 0.2)
            if ngoai_dai_D:
                vuot_d = max(mh.D_min - chenh_T, chenh_T - mh.D_max, 0.0)
                he_so_d_mh = abs(mh.dao_ham_theo_D(S, T_C, T_tc=T_tc_eff) / f_S)
                thanh_phan["ngoai_suy_chenh_nhiet"] = vuot_d * he_so_d_mh
                mo_ta_thanh_phan["ngoai_suy_chenh_nhiet"] = "Ngoại suy ngoài dải D của đường chuẩn"
                _them_canh_bao(
                    "NGOAI_DAI_D",
                    "nghiem_trong",
                    f"Chênh nhiệt hai ngăn D = {chenh_T:+.2f} °C vượt dải hiệu chuẩn "
                    f"({mh.D_min:g} đến {mh.D_max:g} °C): bù chênh nhiệt là ngoại suy, kết quả không đáng tin.",
                )
            elif abs(chenh_T) > nguong_lech_T_hai_ngan_C:
                _them_canh_bao(
                    "CHENH_NHIET_LON",
                    "can_than",
                    f"Chênh nhiệt độ hai ngăn |T_mẫu − T_tc| = {abs(chenh_T):.2f} °C > {nguong_lech_T_hai_ngan_C:g} °C: "
                    "đã bù bằng số hạng D của đường chuẩn, nên đợi cân bằng nhiệt để giảm bất định.",
                )

    ngoai_S = not (mh.S_min <= S <= mh.S_max)
    if ngoai_S:
        _them_canh_bao(
            "NGOAI_DAI_S",
            "nghiem_trong",
            f"Độ mặn ước lượng {S:.2f} ‰ nằm NGOÀI dải hiệu chuẩn "
            f"({mh.S_min:g}–{mh.S_max:g} ‰): kết quả là ngoại suy, không đáng tin.",
        )

    u = math.sqrt(sum(v * v for v in thanh_phan.values()))
    giai_thich_bat_dinh = ""
    if u > 0.0 and (thanh_phan.get("chenh_nhiet_con_lai", 0.0) ** 2) / (u * u) > 0.5:
        giai_thich_bat_dinh = "Bất định chủ yếu do chênh nhiệt hai ngăn và độ chính xác nhiệt kế."

    if mh.la_mo_phong:
        _them_canh_bao(
            "MO_PHONG",
            "can_than",
            f"{NHAN_CHUA_HIEU_CHUAN}: con số này KHÔNG phải kết quả đo thật.",
        )
    elif not mh.da_xac_nhan_thuc_te:
        _them_canh_bao(
            "CHUA_XAC_NHAN_NGUON",
            "can_than",
            f"{NHAN_CHUA_XAC_NHAN_NGUON}: thiếu xác nhận nguon_du_lieu=THUC_TE.",
        )
    if f_S <= 0:
        _them_canh_bao(
            "DO_NHAY_AM",
            "nghiem_trong",
            "Đường chuẩn có độ nhạy âm/không đơn điệu tại điểm này – kiểm tra lại dữ liệu.",
        )

    khong_danh_gia_duoc = bool(
        ngoai_S
        or ngoai_T
        or ngoai_dai_D
        or chenh_T_ngoai_mo_hinh
        or mh.la_mo_phong
        or (not mh.da_xac_nhan_thuc_te)
    )
    canh_bao = [item["noi_dung"] for item in canh_bao_chi_tiet]

    return KetQuaDoMan(
        S_ppt=float(S), u_S_ppt=u, U_S_ppt=k * u, k=k,
        thanh_phan_bat_dinh=thanh_phan, ngoai_dai_S=ngoai_S, ngoai_dai_T=ngoai_T,
        la_mo_phong=mh.la_mo_phong, nhan=mh.nhan,
        nguon_du_lieu=mh.nguon_du_lieu, da_xac_nhan_thuc_te=mh.da_xac_nhan_thuc_te,
        canh_bao=canh_bao,
        ngoai_dai_D=ngoai_dai_D,
        chenh_T_ngoai_mo_hinh=chenh_T_ngoai_mo_hinh,
        khong_danh_gia_duoc=khong_danh_gia_duoc,
        canh_bao_chi_tiet=canh_bao_chi_tiet,
        mo_ta_thanh_phan_bat_dinh=mo_ta_thanh_phan,
        giai_thich_bat_dinh=giai_thich_bat_dinh,
    )


def uoc_luong_do_man_bootstrap(
    df: pd.DataFrame,
    bac: int,
    delta_y_px: float,
    T_C: float,
    sigma_delta_y_px: float = 0.0,
    so_lan: int = 500,
    muc_tin_cay: float = 0.95,
    seed: int = 0,
) -> tuple[float, float, float]:
    """Khoảng tin cậy của S bằng bootstrap (cách kiểm tra chéo cho truyền sai số).

    Mỗi lần: rút lại có hoàn lại các điểm chuẩn -> khớp lại đường chuẩn -> cộng nhiễu
    N(0, s_res² + σ_Δy²) vào Δy -> giải ngược S. Lấy phân vị của phân bố S thu được.

    Returns:
        (S_trung_vi, S_duoi, S_tren)
    """
    rng = np.random.default_rng(seed)
    gia_tri: list[float] = []
    n = len(df)
    for _ in range(so_lan):
        mau = df.iloc[rng.integers(0, n, n)]
        try:
            mh = tao_mo_hinh(mau, bac)
            nhieu = rng.normal(0.0, math.sqrt(mh.s_res_px**2 + sigma_delta_y_px**2))
            gia_tri.append(_tim_nghiem_S(mh, delta_y_px + nhieu, T_C))
        except (ValueError, np.linalg.LinAlgError):
            continue  # mẫu rút lại suy biến (vd. thiếu mức S) -> bỏ qua
    if len(gia_tri) < so_lan // 2:
        raise ValueError("Bootstrap thất bại: quá nhiều mẫu rút lại bị suy biến.")
    a = (1.0 - muc_tin_cay) / 2.0
    arr = np.asarray(gia_tri)
    return float(np.median(arr)), float(np.quantile(arr, a)), float(np.quantile(arr, 1 - a))


# ---------------------------------------------------------------------------
# Dựng đường chuẩn hoàn chỉnh: chia train/test, chọn bậc, báo cáo
# ---------------------------------------------------------------------------
@dataclass
class BaoCaoHieuChuan:
    """Toàn bộ kết quả dựng đường chuẩn."""

    mo_hinh: MoHinhHieuChuan             # khớp trên TOÀN BỘ dữ liệu -> dùng để đo
    mo_hinh_train: MoHinhHieuChuan       # khớp chỉ trên tập train -> dùng để đánh giá trên test
    rmse_kiem_dinh_cheo: dict[int, float]
    bac_chon: int
    ly_do_chon: str
    RMSE_test_px: float
    RMSE_test_ppt: float
    sai_so_theo_muc: pd.DataFrame        # sai số từng mức độ mặn (trên toàn bộ dữ liệu)
    bang_test: pd.DataFrame              # từng điểm test: S chuẩn, S ước lượng, sai số
    df_train: pd.DataFrame
    df_test: pd.DataFrame
    canh_bao: list[str] = field(default_factory=list)
    canh_bao_chi_tiet: list[dict[str, str]] = field(default_factory=list)
    co_ban_sao_du_lieu: bool = False
    so_dong_ban_sao: int = 0
    chi_tiet_ban_sao: dict[str, Any] = field(default_factory=dict)


def chia_train_test(
    df: pd.DataFrame, ti_le_test: float = 0.25, seed: int = 0
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Chia train/test theo nhóm `ma_me_pha` (nếu có) hoặc phân tầng theo mức S.

    Khi có `ma_me_pha`: toàn bộ các lần đo lặp của một mẻ pha dung dịch luôn cùng ở train
    hoặc cùng ở test, tránh đánh giá thấp sai số do rò rỉ lặp giữa train và test.
    """
    rng = np.random.default_rng(seed)
    nhom_arr = _lay_nhom_me_pha(df)
    if nhom_arr is not None:
        u_groups = list(dict.fromkeys(nhom_arr.tolist()))
        g_to_idx: dict[str, list[Any]] = {g: [] for g in u_groups}
        g_to_s: dict[str, set[float]] = {g: set() for g in u_groups}
        for idx, g, s_val in zip(df.index.tolist(), nhom_arr.tolist(), df[COT_DO_MAN].to_numpy(float)):
            g_to_idx[g].append(idx)
            g_to_s[g].add(round(float(s_val), 3))

        s_vals_unique = sorted({s for sset in g_to_s.values() for s in sset})
        s_count: dict[float, int] = {s: sum(1 for g in u_groups if s in g_to_s[g]) for s in s_vals_unique}
        s_min_val, s_max_val = s_vals_unique[0], s_vals_unique[-1]

        shuffled = list(u_groups)
        rng.shuffle(shuffled)
        n_test_target = max(1, int(round(len(u_groups) * ti_le_test)))
        max_test_rows = max(1, int(math.floor(len(df) * 0.45)))

        nhom_test: list[str] = []
        s_test_taken: dict[float, int] = {}
        rows_test = 0
        for g in shuffled:
            if len(nhom_test) >= n_test_target:
                break
            g_rows = len(g_to_idx[g])
            if len(df) - (rows_test + g_rows) < 4:
                continue
            if rows_test + g_rows > max_test_rows and nhom_test:
                continue
            # Nếu còn nhiều mức S, giữ nguyên 2 đầu mút S_min/S_max ở train nếu chỉ có 1 mẻ duy nhất
            if len(s_vals_unique) >= 3:
                if (s_min_val in g_to_s[g] and s_count[s_min_val] - s_test_taken.get(s_min_val, 0) <= 1):
                    continue
                if (s_max_val in g_to_s[g] and s_count[s_max_val] - s_test_taken.get(s_max_val, 0) <= 1):
                    continue
            # Tránh rút hết sạch mọi nhóm của cùng một mức S nếu có >1 mẻ ở mức đó
            if any(s_count[s] > 1 and (s_count[s] - s_test_taken.get(s, 0) <= 1) for s in g_to_s[g]):
                continue
            nhom_test.append(g)
            rows_test += g_rows
            for s in g_to_s[g]:
                s_test_taken[s] = s_test_taken.get(s, 0) + 1

        if not nhom_test and len(u_groups) >= 3:
            ung_vien = [
                g for g in shuffled
                if (s_min_val not in g_to_s[g] or s_count[s_min_val] > 1)
                and (s_max_val not in g_to_s[g] or s_count[s_max_val] > 1)
                and len(df) - len(g_to_idx[g]) >= 4
            ]
            if ung_vien:
                nhom_test.append(ung_vien[0])

        chi_so_test = [idx for g in nhom_test for idx in g_to_idx[g]]
        return df.drop(index=chi_so_test), df.loc[chi_so_test]

    chi_so_test = []
    for _, nhom in df.groupby(COT_DO_MAN):
        n_test = min(int(round(len(nhom) * ti_le_test)), len(nhom) - 1)
        if n_test > 0:
            chi_so_test.extend(rng.choice(nhom.index.to_numpy(), n_test, replace=False).tolist())
    return df.drop(index=chi_so_test), df.loc[chi_so_test]


def _bang_sai_so(mh: MoHinhHieuChuan, df: pd.DataFrame, k: float) -> pd.DataFrame:
    """Bảng từng điểm: Δy dự đoán, phần dư, S ước lượng ngược, sai số S."""
    t_tc_arr = _lay_nhiet_do_tc(df)
    don_vi = getattr(mh, "don_vi_y", "px")
    px_mm_arr = (
        pd.to_numeric(df[COT_PX_PER_MM], errors="coerce").to_numpy(float)
        if (don_vi == "mm" and COT_PX_PER_MM in df.columns)
        else None
    )
    dong = []
    for idx, (_, r) in enumerate(df.iterrows()):
        S0, T0, y_px0 = float(r[COT_DO_MAN]), float(r[COT_NHIET_DO]), float(r[COT_DELTA_Y])
        T_tc0 = float(t_tc_arr[idx])
        px_mm0 = float(px_mm_arr[idx]) if px_mm_arr is not None else None
        y0 = (y_px0 / px_mm0) if (don_vi == "mm" and px_mm0) else y_px0
        try:
            S_est = uoc_luong_do_man(
                mh, y_px0, T0, k=k, T_tham_chieu_C=T_tc0, px_per_mm=px_mm0
            ).S_ppt
        except ValueError:
            S_est = float("nan")
        dy_du_doan = float(mh.du_doan_delta_y(S0, T0, T_tc=T_tc0)[0])
        dong.append({
            COT_DO_MAN: S0, COT_NHIET_DO: T0, COT_NHIET_DO_TC: T_tc0, COT_DELTA_Y: y0,
            "delta_y_du_doan_px": dy_du_doan,
            "phan_du_px": y0 - dy_du_doan,
            "S_uoc_luong_ppt": S_est,
            "sai_so_S_ppt": S_est - S0,
        })
    return pd.DataFrame(dong)


def dung_duong_chuan(
    df: pd.DataFrame,
    cau_hinh: CauHinhHieuChuan | None = None,
    bac_ep: int | None = None,
    don_vi_y: str = "px",
) -> BaoCaoHieuChuan:
    """Dựng đường chuẩn từ dữ liệu hiệu chuẩn.

    Quy trình:
      1. Chia train/test phân tầng theo S.
      2. Trên train: tính RMSE kiểm định chéo cho bậc 1 và bậc 2.
      3. Chọn bậc 2 CHỈ KHI nó giảm RMSE kiểm định chéo ≥ ngưỡng (mặc định 10%);
         ngược lại chọn bậc 1 (nguyên tắc "đơn giản nhất đủ dùng", chống quá khớp).
      4. Khớp bậc đã chọn trên train -> đánh giá trên test (số liệu báo cáo trung thực).
      5. Khớp lại trên toàn bộ dữ liệu -> mô hình dùng để đo.
    """
    ch = cau_hinh or CauHinhHieuChuan()
    canh_bao: list[str] = []
    canh_bao_chi_tiet: list[dict[str, str]] = []

    def _them_cb_hieu_chuan(ma: str, cap: str, noi_dung: str) -> None:
        canh_bao.append(noi_dung)
        canh_bao_chi_tiet.append({"ma": ma, "cap": cap, "noi_dung": noi_dung})

    # W1: kiểm tra bản sao / nghi ngờ gán nhãn lại (không tự ý xóa dòng khỏi mô hình)
    info_ban_sao = phat_hien_ban_sao_du_lieu(df)
    info_ban_sao_tom_tat = {k: v for k, v in info_ban_sao.items() if k != "mask_ban_sao"}
    if info_ban_sao["co_ban_sao"]:
        extra_nghi = "; nghi ngờ gán nhãn lại" if info_ban_sao["co_nghi_ngo_gan_nhan_lai"] else ""
        dong_vd = (
            f" (ví dụ dòng {', '.join(str(x) for x in info_ban_sao['dong_nghi_ngo_dau_tien'])})"
            if info_ban_sao["dong_nghi_ngo_dau_tien"]
            else ""
        )
        _them_cb_hieu_chuan(
            "DU_LIEU_CO_BAN_SAO",
            "nghiem_trong",
            f"Phát hiện {info_ban_sao['so_dong_ban_sao']} dòng bản sao trong {info_ban_sao['so_dong_tong']} dòng"
            f"{extra_nghi}{dong_vd}. Đường chuẩn vẫn khớp trên toàn bộ dữ liệu đầu vào; hãy kiểm tra và loại bản sao thủ công.",
        )

    nguon_df = xac_dinh_nguon_du_lieu(df)
    if nguon_df == NHAN_MO_PHONG:
        _them_cb_hieu_chuan("MO_PHONG", "can_than", f"{NHAN_CHUA_HIEU_CHUAN}: đường chuẩn này dựng từ dữ liệu mô phỏng.")
    elif nguon_df != NHAN_THUC_TE:
        _them_cb_hieu_chuan(
            "CHUA_XAC_NHAN_NGUON",
            "can_than",
            f"{NHAN_CHUA_XAC_NHAN_NGUON}: thiếu cột nguon_du_lieu hoặc có dòng chưa ghi rõ THUC_TE.",
        )
    if bool(df.attrs.get("gia_dinh_can_bang_nhiet", COT_NHIET_DO_TC not in df.columns)):
        _them_cb_hieu_chuan(
            "GIA_DINH_CAN_BANG_NHIET",
            "can_than",
            "Thiếu cột nhiet_do_tham_chieu_C: giả định hai ngăn cân bằng nhiệt, chưa đo.",
        )
    if don_vi_y == "px":
        _them_cb_hieu_chuan(
            "DON_VI_PX",
            "thong_tin",
            "Đường chuẩn theo pixel chỉ đúng cho đúng một cấu hình camera và khoảng cách màn.",
        )
    if COT_PX_PER_MM in df.columns and len(df) > 0:
        px_arr = pd.to_numeric(df[COT_PX_PER_MM], errors="coerce").to_numpy(float)
        valid_px = np.isfinite(px_arr) & (px_arr > 0.0)
        if np.any(valid_px) and not np.all(valid_px) and don_vi_y != "mm":
            _them_cb_hieu_chuan(
                "TRON_PX_PER_MM",
                "can_than",
                "Dữ liệu CSV trộn lẫn dòng có và không có px_per_mm: hãy bổ sung đủ thang chuẩn hoặc tách riêng bộ ảnh.",
            )
        if don_vi_y == "px" and int(np.count_nonzero(valid_px)) >= 2:
            df_px = df.loc[valid_px].copy()
            df_px["_px_val"] = px_arr[valid_px]
            grp_cols = [c for c in (COT_ID_THIET_BI, COT_ID_DIEN_THOAI) if c in df_px.columns]
            groups = df_px.groupby(grp_cols, dropna=False) if grp_cols else [((), df_px)]
            for grp_key, grp_df in groups:
                vals_px = grp_df["_px_val"].to_numpy(float)
                if len(vals_px) < 2:
                    continue
                mean_px = float(np.mean(vals_px))
                pct_var = (float(np.max(vals_px) - np.min(vals_px)) / mean_px) * 100.0 if mean_px > 0 else 0.0
                if pct_var > float(ch.nguong_bien_thien_px_per_mm_phan_tram):
                    s_ref_max = max(float(df[COT_DO_MAN].max()), 1.0)
                    err_est_ppt = (pct_var / 100.0) * s_ref_max
                    nhan_nhom = f"nhóm {grp_key}" if grp_cols else "bộ dữ liệu"
                    _them_cb_hieu_chuan(
                        "BIEN_THIEN_PX_PER_MM",
                        "can_than",
                        f"Đường chuẩn pixel chỉ đúng cho đúng một cấu hình camera/khoảng cách: {nhan_nhom} có "
                        f"px_per_mm biến thiên {pct_var:.1f}% (> {ch.nguong_bien_thien_px_per_mm_phan_tram:g}%), "
                        f"ước lượng có thể gây sai lệch tới ±{err_est_ppt:.2f} ‰ ở {s_ref_max:g} ‰. "
                        "Hãy chuyển sang don_vi_y='mm' hoặc cố định lại khoảng cách chụp.",
                    )
    if df.attrs.get("so_dong_bi_loai", 0):
        _them_cb_hieu_chuan("DONG_BI_LOAI", "thong_tin", f"Đã loại {df.attrs['so_dong_bi_loai']} dòng thiếu dữ liệu.")
    if _so_muc(df[COT_DO_MAN].to_numpy(float), 0.01) < 3:
        _them_cb_hieu_chuan("IT_MUC_S", "can_than", "Cần ít nhất 3 mức độ mặn chuẩn; nên dùng 5–8 mức phủ hết dải cần đo.")
    nhom_all = _lay_nhom_me_pha(df)
    if nhom_all is None:
        _them_cb_hieu_chuan(
            "THIEU_MA_ME_PHA",
            "can_than",
            "Không có cột ma_me_pha (hoặc < 2 mẻ pha đầy đủ): các lần đo lặp của cùng một dung dịch "
            "nằm cả ở train và test nên sai số test bị đánh giá thấp.",
        )

    if len(df) >= 8:
        df_train, df_test = chia_train_test(df, ch.ti_le_test, ch.seed)
    else:
        df_train, df_test = df, df.iloc[0:0]
        canh_bao.append("Quá ít điểm (< 8) nên không tách được tập test; chỉ báo cáo sai số trong mẫu.")

    S = df_train[COT_DO_MAN].to_numpy(float)
    T = df_train[COT_NHIET_DO].to_numpy(float)
    T_tc = _lay_nhiet_do_tc(df_train)
    nhom_tr = _lay_nhom_me_pha(df_train)
    y = _lay_y_theo_don_vi(df_train, don_vi_y)
    co_T_tr, co_TT_tr, co_D_tr = _xac_dinh_co_bu_nhiet(T, T_tc)
    T_ref = float(np.round(np.mean(T), 1))

    rmse_cv: dict[int, float] = {}
    for bac in (1, 2):
        if bac == 2 and _so_muc(S, 0.01) < 3:
            continue
        hang = chon_so_hang(bac, co_T_tr, co_TT_tr, co_D=co_D_tr)
        rmse_cv[bac] = rmse_kiem_dinh_cheo(
            S, T, y, hang, T_ref, ch.so_fold, ch.seed, T_tc=T_tc, nhom=nhom_tr
        )

    if bac_ep is not None:
        bac_chon, ly_do = bac_ep, f"Bậc {bac_ep} do người dùng chỉ định."
    elif 2 in rmse_cv and rmse_cv[2] < (1.0 - ch.nguong_cai_thien_bac2) * rmse_cv[1]:
        bac_chon = 2
        ly_do = (f"Bậc 2 giảm RMSE kiểm định chéo từ {rmse_cv[1]:.3f} xuống {rmse_cv[2]:.3f} {don_vi_y} "
                 f"(> {ch.nguong_cai_thien_bac2:.0%}), nên chọn bậc 2.")
    else:
        bac_chon = 1
        r2 = f"{rmse_cv[2]:.3f}" if 2 in rmse_cv else "không tính được"
        ly_do = (f"Bậc 2 (RMSE CV {r2} {don_vi_y}) không tốt hơn bậc 1 (RMSE CV {rmse_cv[1]:.3f} {don_vi_y}) "
                 f"đủ {ch.nguong_cai_thien_bac2:.0%}, nên chọn bậc 1 đơn giản hơn.")

    mh_train = tao_mo_hinh(df_train, bac_chon, don_vi_y=don_vi_y)
    mh_full = tao_mo_hinh(df, bac_chon, don_vi_y=don_vi_y)
    if not mh_full.co_bu_nhiet and not mh_full.co_bu_chenh_T:
        canh_bao.append("Dữ liệu chỉ có một mức nhiệt độ: đường chuẩn KHÔNG bù nhiệt được.")
    dai_T = float(mh_full.T_max - mh_full.T_min)
    if ch.nhiet_do_toi_thieu_phu_C is not None and dai_T < ch.nhiet_do_toi_thieu_phu_C:
        canh_bao.append(
            f"Dải nhiệt độ hiệu chuẩn ({dai_T:.1f} °C) hẹp hơn ngưỡng tối thiểu cấu hình "
            f"({ch.nhiet_do_toi_thieu_phu_C:g} °C): tránh dùng ngoài dải nhiệt độ đã đo."
        )

    if len(df_test):
        bang_test = _bang_sai_so(mh_train, df_test, ch.he_so_phu_k)
        rmse_test_px = float(np.sqrt(np.mean(bang_test["phan_du_px"] ** 2)))
        rmse_test_ppt = float(np.sqrt(np.nanmean(bang_test["sai_so_S_ppt"] ** 2)))
    else:
        bang_test = pd.DataFrame()
        rmse_test_px = rmse_test_ppt = float("nan")

    bang_all = _bang_sai_so(mh_full, df, ch.he_so_phu_k)
    theo_muc = (
        bang_all.groupby(COT_DO_MAN)
        .agg(so_diem=(COT_DELTA_Y, "size"),
             delta_y_tb_px=(COT_DELTA_Y, "mean"),
             do_lech_chuan_px=(COT_DELTA_Y, "std"),
             phan_du_tb_px=("phan_du_px", "mean"),
             S_uoc_luong_tb_ppt=("S_uoc_luong_ppt", "mean"),
             sai_so_S_tb_ppt=("sai_so_S_ppt", "mean"),
             sai_so_S_max_ppt=("sai_so_S_ppt", lambda v: float(np.nanmax(np.abs(v)))))
        .reset_index()
    )

    return BaoCaoHieuChuan(
        mo_hinh=mh_full, mo_hinh_train=mh_train, rmse_kiem_dinh_cheo=rmse_cv,
        bac_chon=bac_chon, ly_do_chon=ly_do,
        RMSE_test_px=rmse_test_px, RMSE_test_ppt=rmse_test_ppt,
        sai_so_theo_muc=theo_muc, bang_test=bang_test,
        df_train=df_train, df_test=df_test, canh_bao=canh_bao, canh_bao_chi_tiet=canh_bao_chi_tiet,
        co_ban_sao_du_lieu=bool(info_ban_sao["co_ban_sao"]),
        so_dong_ban_sao=int(info_ban_sao["so_dong_ban_sao"]),
        chi_tiet_ban_sao=info_ban_sao_tom_tat,
    )


# ---------------------------------------------------------------------------
# Đồ thị (dùng matplotlib.figure.Figure để chạy được cả trong web backend lẫn pytest)
# ---------------------------------------------------------------------------
def ve_duong_chuan(bc: BaoCaoHieuChuan):  # -> matplotlib.figure.Figure
    """Đồ thị Δy theo S: điểm đo (train/test) và đường chuẩn tại từng mức nhiệt độ."""
    from matplotlib.figure import Figure

    mh = bc.mo_hinh
    don_vi = getattr(mh, "don_vi_y", "px")
    fig = Figure(figsize=(7, 4.5), dpi=110)
    ax = fig.add_subplot(111)
    y_tr = _lay_y_theo_don_vi(bc.df_train, don_vi)
    ax.scatter(bc.df_train[COT_DO_MAN], y_tr, s=18, label="Điểm chuẩn (train)")
    if len(bc.df_test):
        y_te = _lay_y_theo_don_vi(bc.df_test, don_vi)
        ax.scatter(bc.df_test[COT_DO_MAN], y_te, s=30, marker="x",
                   color="red", label="Điểm kiểm tra (test)")
    S_luoi = np.linspace(mh.S_min, mh.S_max, 200)
    tat_ca_T = pd.concat([bc.df_train, bc.df_test])[COT_NHIET_DO].to_numpy(float)
    muc_T = sorted(np.unique(np.round(tat_ca_T * 2) / 2))  # làm tròn 0,5 °C
    for T in (muc_T if mh.co_bu_nhiet else [mh.T_ref])[:6]:
        ax.plot(S_luoi, mh.du_doan_delta_y(S_luoi, T), lw=1.2, label=f"Đường chuẩn T = {T:g} °C")
    ax.set_xlabel("Độ mặn chuẩn S (‰)")
    ax.set_ylabel(f"Δy ({don_vi})")
    tieu_de = f"Đường chuẩn bậc {mh.bac}  (R² = {mh.R2:.5f})"
    if mh.la_mo_phong:
        tieu_de += f"\n{NHAN_CHUA_HIEU_CHUAN}"
    elif not mh.da_xac_nhan_thuc_te:
        tieu_de += f"\n{NHAN_CHUA_XAC_NHAN_NGUON}"
    ax.set_title(tieu_de, fontsize=10, color="red" if not mh.da_xac_nhan_thuc_te else "black")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7)
    fig.tight_layout()
    return fig


def ve_phan_du(bc: BaoCaoHieuChuan):  # -> matplotlib.figure.Figure
    """Đồ thị phần dư (Δy đo − Δy dự đoán) theo S. Phần dư tốt: tản mát ngẫu nhiên quanh 0,
    không có dạng cong (nếu cong -> cần bậc cao hơn hoặc có sai số hệ thống)."""
    from matplotlib.figure import Figure

    mh = bc.mo_hinh_train
    fig = Figure(figsize=(7, 3.5), dpi=110)
    ax = fig.add_subplot(111)
    for d, nhan, kieu in ((bc.df_train, "train", "o"), (bc.df_test, "test", "x")):
        if len(d):
            y_thuc = _lay_y_theo_don_vi(d, getattr(mh, "don_vi_y", "px"))
            du = y_thuc - mh.du_doan_delta_y(
                d[COT_DO_MAN].to_numpy(float),
                d[COT_NHIET_DO].to_numpy(float),
                T_tc=_lay_nhiet_do_tc(d),
            )
            ax.scatter(d[COT_DO_MAN], du, s=20, marker=kieu, label=nhan)
    ax.axhline(0, color="k", lw=0.8)
    for dau in (-2, 2):
        ax.axhline(dau * mh.s_res_px, color="gray", ls="--", lw=0.8)
    ax.set_xlabel("Độ mặn chuẩn S (‰)")
    ax.set_ylabel(f"Phần dư ({getattr(mh, 'don_vi_y', 'px')})")
    tieu_de = f"Phần dư (đường nét đứt: ±2·s_res = ±{2 * mh.s_res_px:.3f} px)"
    if mh.la_mo_phong:
        tieu_de += f"\n{NHAN_CHUA_HIEU_CHUAN}"
    elif not mh.da_xac_nhan_thuc_te:
        tieu_de += f"\n{NHAN_CHUA_XAC_NHAN_NGUON}"
    ax.set_title(tieu_de, fontsize=10, color="red" if not mh.da_xac_nhan_thuc_te else "black")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    return fig
