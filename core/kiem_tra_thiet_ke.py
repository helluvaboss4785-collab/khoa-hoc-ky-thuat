"""Kiểm tra thiết kế thí nghiệm hiệu chuẩn trước khi dựng đường chuẩn (không chặn quy trình)."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from core import calibration as cal
from core.calibration import phat_hien_ban_sao_du_lieu

CAU_HINH_THIET_KE_MAC_DINH: dict[str, Any] = {
    "so_muc_man_toi_thieu": 6,
    "phai_co_muc_0": True,
    "ti_le_phu_dai_man_toi_thieu": 0.8,
    "so_lan_lap_toi_thieu_moi_o": 3,
    "so_me_pha_toi_thieu": 2,
    "so_muc_nhiet_toi_thieu": 3,
    "bien_do_nhiet_toi_thieu_C": 6.0,
    "so_muc_D_toi_thieu_neu_hoc_D": 2,
    "chenh_D_toi_thieu_C": 1.0,
    "ti_le_toi_da_moi_muc": 0.4,
    "ti_le_ban_sao_toi_da": 0.0,
    "dai_man_muc_tieu_ppt": [0.0, 35.0],
}


def tai_cau_hinh_thiet_ke(config_path: Path | str = cal.CONFIG_MAC_DINH) -> dict[str, Any]:
    """Đọc các ngưỡng thiết kế thí nghiệm từ config.yaml (giữ giá trị mặc định nếu thiếu)."""
    cfg = dict(CAU_HINH_THIET_KE_MAC_DINH)
    p = Path(config_path)
    if p.exists():
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        hc = raw.get("hieu_chuan") or {}
        if isinstance(hc.get("dai_man_muc_tieu_ppt"), (list, tuple)) and len(hc["dai_man_muc_tieu_ppt"]) == 2:
            cfg["dai_man_muc_tieu_ppt"] = [float(hc["dai_man_muc_tieu_ppt"][0]), float(hc["dai_man_muc_tieu_ppt"][1])]
        tk = raw.get("thiet_ke_thi_nghiem") or {}
        for k, v in tk.items():
            if k in cfg and v is not None:
                cfg[k] = v
    return {
        "so_muc_man_toi_thieu": int(cfg["so_muc_man_toi_thieu"]),
        "phai_co_muc_0": bool(cfg["phai_co_muc_0"]),
        "ti_le_phu_dai_man_toi_thieu": float(cfg["ti_le_phu_dai_man_toi_thieu"]),
        "so_lan_lap_toi_thieu_moi_o": int(cfg["so_lan_lap_toi_thieu_moi_o"]),
        "so_me_pha_toi_thieu": int(cfg["so_me_pha_toi_thieu"]),
        "so_muc_nhiet_toi_thieu": int(cfg["so_muc_nhiet_toi_thieu"]),
        "bien_do_nhiet_toi_thieu_C": float(cfg["bien_do_nhiet_toi_thieu_C"]),
        "so_muc_D_toi_thieu_neu_hoc_D": int(cfg["so_muc_D_toi_thieu_neu_hoc_D"]),
        "chenh_D_toi_thieu_C": float(cfg["chenh_D_toi_thieu_C"]),
        "ti_le_toi_da_moi_muc": float(cfg["ti_le_toi_da_moi_muc"]),
        "ti_le_ban_sao_toi_da": float(cfg["ti_le_ban_sao_toi_da"]),
        "dai_man_muc_tieu_ppt": list(cfg["dai_man_muc_tieu_ppt"]),
    }


def _chuan_hoa_ten_cot_giu_nguyen_thieu(df: pd.DataFrame) -> pd.DataFrame:
    """Ánh xạ bí danh tên cột sang tên chuẩn nếu cột chuẩn chưa tồn tại (KHÔNG tự điền giá trị mặc định)."""
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    for alias, cot_chuan in cal.BI_DANH_COT.items():
        if alias in out.columns and cot_chuan not in out.columns:
            out = out.rename(columns={alias: cot_chuan})
    return out


def _gom_cum_1d(values: np.ndarray, max_gap: float, max_span: float) -> tuple[np.ndarray, int]:
    """Gom các giá trị thực thành cụm mức thí nghiệm (chịu được nhiễu nhiệt kế mà không tách ở ngưỡng .5).

    Hai phần tử liên tiếp sau sắp xếp cùng một cụm khi khoảng nhảy <= max_gap và bề rộng cụm < max_span.
    """
    n = len(values)
    if n == 0:
        return np.array([], dtype=int), 0
    order = np.argsort(values, kind="mergesort")
    sorted_vals = values[order]
    cids_sorted = np.zeros(n, dtype=int)
    cid = 0
    start_val = float(sorted_vals[0])
    prev_val = float(sorted_vals[0])
    for idx in range(1, n):
        v = float(sorted_vals[idx])
        if (v - prev_val) > max_gap or (v - start_val) >= max_span:
            cid += 1
            start_val = v
        cids_sorted[idx] = cid
        prev_val = v
    cids = np.empty(n, dtype=int)
    cids[order] = cids_sorted
    return cids, cid + 1


def _muc(
    ma: str,
    ten: str,
    trang_thai: str,
    gia_tri_do: str,
    yeu_cau: str,
    goi_y: str = "",
) -> dict[str, str]:
    return {
        "ma": ma,
        "ten": ten,
        "trang_thai": trang_thai,
        "gia_tri_do": gia_tri_do,
        "yeu_cau": yeu_cau,
        "goi_y": goi_y,
    }


def _kiem_tra_me_pha(df_raw: pd.DataFrame, so_me_yeu_cau: int) -> tuple[dict[str, str], int]:
    if cal.COT_MA_ME_PHA not in df_raw.columns:
        return (
            _muc(
                "me_pha",
                "Số mẻ pha dung dịch độc lập",
                "chua_dat",
                "Thiếu cột ma_me_pha",
                f">= {so_me_yeu_cau} mẻ pha",
                "Thêm cột ma_me_pha và pha ít nhất 2 mẻ độc lập ở các lần cân riêng để đánh giá sai số pha chế.",
            ),
            0,
        )
    raw_vals = df_raw[cal.COT_MA_ME_PHA]
    batches: set[str] = set()
    for val in raw_vals:
        if pd.isna(val):
            continue
        s = str(val).strip()
        up = s.upper()
        if not s or up in {"ME_CHUA_GHI", "NAN", "NONE", "NULL"}:
            continue
        batches.add(up)
    n_batches = len(batches)
    ok = n_batches >= so_me_yeu_cau
    return (
        _muc(
            "me_pha",
            "Số mẻ pha dung dịch độc lập",
            "dat" if ok else "chua_dat",
            f"{n_batches} mẻ",
            f">= {so_me_yeu_cau} mẻ pha",
            "" if ok else f"Cần pha thêm mẫu ở ít nhất {so_me_yeu_cau} mẻ cân độc lập khác nhau.",
        ),
        n_batches,
    )


def _kiem_tra_bien_thien_D(
    df_valid: pd.DataFrame,
    t_vals: np.ndarray,
    muon_hoc_D: bool,
    so_muc_D_req: int,
    chenh_D_req: float,
) -> tuple[dict[str, str], int, float]:
    has_tc = cal.COT_NHIET_DO_TC in df_valid.columns
    if not muon_hoc_D:
        ghi_chu = "Có cột T_tc" if has_tc else "Không dùng cột T_tc"
        return (
            _muc(
                "bien_thien_D",
                "Biến thiên chênh nhiệt hai ngăn D = T_mẫu − T_tc",
                "bo_qua",
                f"Bỏ qua ({ghi_chu})",
                "Chỉ bắt buộc khi bật học hệ số D",
                "",
            ),
            0,
            0.0,
        )

    if not has_tc:
        return (
            _muc(
                "bien_thien_D",
                "Biến thiên chênh nhiệt hai ngăn D = T_mẫu − T_tc",
                "chua_dat",
                "Thiếu cột nhiet_do_tham_chieu_C",
                f">= {so_muc_D_req} mức D & biên độ >= {chenh_D_req:.1f} °C",
                "Đo và ghi cột nhiet_do_tham_chieu_C ở các mức chênh nhiệt D khác nhau.",
            ),
            0,
            0.0,
        )

    t_tc_num = pd.to_numeric(df_valid[cal.COT_NHIET_DO_TC], errors="coerce").to_numpy(dtype=float)
    mask_d = np.isfinite(t_vals) & np.isfinite(t_tc_num)
    if not np.any(mask_d):
        return (
            _muc(
                "bien_thien_D",
                "Biến thiên chênh nhiệt hai ngăn D = T_mẫu − T_tc",
                "chua_dat",
                "Cột T_tc toàn giá trị rỗng/lỗi",
                f">= {so_muc_D_req} mức D & biên độ >= {chenh_D_req:.1f} °C",
                "Điền nhiệt độ đo ngăn tham chiếu hợp lệ để học hệ số D.",
            ),
            0,
            0.0,
        )

    d_vals = t_vals[mask_d] - t_tc_num[mask_d]
    _, n_D = _gom_cum_1d(d_vals, max_gap=0.5, max_span=1.0)
    d_span = float(np.max(d_vals) - np.min(d_vals))
    ok = (n_D >= so_muc_D_req) and (d_span >= chenh_D_req - 1e-9)
    return (
        _muc(
            "bien_thien_D",
            "Biến thiên chênh nhiệt hai ngăn D = T_mẫu − T_tc",
            "dat" if ok else "chua_dat",
            f"{n_D} mức D (biên độ {d_span:.2f} °C)",
            f">= {so_muc_D_req} mức D & biên độ >= {chenh_D_req:.1f} °C",
            "" if ok else "Cần thu dữ liệu khi ngăn mẫu và ngăn tham chiếu chênh nhiệt có chủ đích (ví dụ D ≈ 0 °C và ±2..4 °C).",
        ),
        n_D,
        d_span,
    )


def _kiem_tra_px_per_mm(df_raw: pd.DataFrame, don_vi_y: str) -> dict[str, str]:
    dv = str(don_vi_y or "px").strip().lower()
    if cal.COT_PX_PER_MM not in df_raw.columns:
        trang_thai = "chua_dat" if dv == "mm" else "canh_bao"
        return _muc(
            "px_per_mm",
            "Tỉ lệ quy đổi px/mm",
            trang_thai,
            "Thiếu cột px_per_mm",
            "Bắt buộc và đồng nhất khi quy đổi mm; khuyến nghị ghi khi dùng px",
            "Đo thước chia trên màn hứng để điền cột px_per_mm (bắt buộc nếu chọn đơn vị mm).",
        )

    vals = pd.to_numeric(df_raw[cal.COT_PX_PER_MM], errors="coerce").to_numpy(dtype=float)
    invalid = np.any(~np.isfinite(vals) | (vals <= 0.0)) if len(vals) else True
    if invalid:
        trang_thai = "chua_dat" if dv == "mm" else "canh_bao"
        return _muc(
            "px_per_mm",
            "Tỉ lệ quy đổi px/mm",
            trang_thai,
            "Có dòng thiếu hoặc px_per_mm <= 0",
            "Mọi dòng đều > 0 và nhất quán nếu fit theo px",
            "Điền giá trị px_per_mm > 0 cho toàn bộ các phép đo.",
        )

    med = float(np.median(vals))
    rel_spread = float((np.max(vals) - np.min(vals)) / med) if med > 0 else 0.0
    if rel_spread > 0.02:
        if dv == "px":
            return _muc(
                "px_per_mm",
                "Tỉ lệ quy đổi px/mm",
                "chua_dat",
                f"Trộn nhiều giá trị ({np.min(vals):.2f}–{np.max(vals):.2f}, lệch {rel_spread*100:.1f}%)",
                "Biến thiên <= 2% khi khớp theo px",
                "px_per_mm khác nhau giữa các ảnh (do đổi khoảng cách/zoom): hãy chọn don_vi_y='mm' để chuẩn hóa.",
            )
        return _muc(
            "px_per_mm",
            "Tỉ lệ quy đổi px/mm",
            "dat",
            f"Đã quy đổi sang mm ({np.min(vals):.2f}–{np.max(vals):.2f} px/mm)",
            "Có px_per_mm > 0 để quy đổi mm",
            "",
        )

    return _muc(
        "px_per_mm",
        "Tỉ lệ quy đổi px/mm",
        "dat",
        f"{med:.2f} px/mm (ổn định)",
        "Có px_per_mm > 0 và ổn định",
        "",
    )


def _kiem_tra_nguon_du_lieu(df_raw: pd.DataFrame) -> tuple[dict[str, str], list[str]]:
    if cal.COT_NGUON not in df_raw.columns:
        return (
            _muc(
                "nguon_du_lieu",
                "Nhãn nguồn dữ liệu (MO_PHONG / THUC_TE)",
                "chua_dat",
                "Thiếu cột nguon_du_lieu",
                "100% dòng cùng một nhãn MO_PHONG hoặc THUC_TE",
                "Thêm cột nguon_du_lieu và ghi rõ THUC_TE (hoặc MO_PHONG) cho mọi dòng, không để trống.",
            ),
            [],
        )

    raw = df_raw[cal.COT_NGUON]
    vals: list[str] = []
    co_loi = False
    for v in raw:
        if pd.isna(v):
            co_loi = True
            continue
        s = str(v).strip().upper()
        if not s or s not in {cal.NHAN_MO_PHONG, cal.NHAN_THUC_TE}:
            co_loi = True
        else:
            vals.append(s)

    nguon_unique = sorted(set(vals))
    if co_loi or not nguon_unique:
        return (
            _muc(
                "nguon_du_lieu",
                "Nhãn nguồn dữ liệu (MO_PHONG / THUC_TE)",
                "chua_dat",
                f"Có dòng trống hoặc nhãn lạ ({nguon_unique})",
                "Mọi dòng là MO_PHONG hoặc THUC_TE và đồng nhất",
                "Điền đúng nhãn MO_PHONG hoặc THUC_TE cho tất cả các dòng.",
            ),
            nguon_unique,
        )

    if len(nguon_unique) > 1:
        return (
            _muc(
                "nguon_du_lieu",
                "Nhãn nguồn dữ liệu (MO_PHONG / THUC_TE)",
                "chua_dat",
                f"Trộn lẫn: {', '.join(nguon_unique)}",
                "Không trộn lẫn MO_PHONG và THUC_TE",
                "Tách riêng bộ dữ liệu đo thật (THUC_TE) khỏi bộ mô phỏng (MO_PHONG) trước khi dựng đường chuẩn.",
            ),
            nguon_unique,
        )

    nhan = nguon_unique[0]
    return (
        _muc(
            "nguon_du_lieu",
            "Nhãn nguồn dữ liệu (MO_PHONG / THUC_TE)",
            "dat",
            f"Đồng nhất {nhan} ({len(vals)} dòng)",
            "Đồng nhất 1 nguồn dữ liệu",
            "",
        ),
        nguon_unique,
    )


def kiem_tra_thiet_ke_thi_nghiem(
    df: pd.DataFrame,
    config_path: Path | str = cal.CONFIG_MAC_DINH,
    muon_hoc_D: bool = False,
    don_vi_y: str = "px",
) -> dict[str, Any]:
    """Đánh giá tính đầy đủ của thiết kế thí nghiệm hiệu chuẩn trên DataFrame thô.

    LƯU Ý: Hàm chỉ báo cáo khuyến nghị, tuyệt đối KHÔNG ném lỗi để chặn dựng đường chuẩn.
    Phải truyền DataFrame thô (trước khi doc_csv_hieu_chuan điền mặc định) để phát hiện đúng cột thiếu.
    """
    cfg = tai_cau_hinh_thiet_ke(config_path)
    df_raw = _chuan_hoa_ten_cot_giu_nguyen_thieu(df)
    n_raw = int(len(df_raw))

    if cal.COT_DO_MAN in df_raw.columns:
        s_num = pd.to_numeric(df_raw[cal.COT_DO_MAN], errors="coerce")
    else:
        s_num = pd.Series(np.nan, index=df_raw.index, dtype=float)

    if cal.COT_NHIET_DO in df_raw.columns:
        t_num = pd.to_numeric(df_raw[cal.COT_NHIET_DO], errors="coerce")
    else:
        t_num = pd.Series(np.nan, index=df_raw.index, dtype=float)

    valid_mask = s_num.notna() & t_num.notna()
    df_valid = df_raw.loc[valid_mask].copy()
    s_vals = s_num.loc[valid_mask].to_numpy(dtype=float)
    t_vals = t_num.loc[valid_mask].to_numpy(dtype=float)

    # W1: phát hiện bản sao và nghi ngờ gán nhãn lại; tách tập sau loại bản sao cho thống kê số lần lặp
    ban_sao = phat_hien_ban_sao_du_lieu(df_raw)
    mask_bs = ban_sao["mask_ban_sao"]
    non_dup_valid_mask = valid_mask.to_numpy(dtype=bool) & (~mask_bs if len(mask_bs) == len(df_raw) else True)
    s_vals_nodup = s_num.to_numpy(dtype=float)[non_dup_valid_mask]
    t_vals_nodup = t_num.to_numpy(dtype=float)[non_dup_valid_mask]

    s_round = np.round(s_vals, 3)
    s_levels = sorted(set(float(x) for x in s_round))
    n_S = len(s_levels)

    # 1. Số mức độ mặn
    req_S = cfg["so_muc_man_toi_thieu"]
    ok_S = n_S >= req_S
    muc_kiem: list[dict[str, str]] = [
        _muc(
            "so_muc_man",
            "Số mức độ mặn chuẩn S",
            "dat" if ok_S else "chua_dat",
            f"{n_S} mức ({s_levels[0]:.1f}–{s_levels[-1]:.1f}‰)" if n_S else "0 mức",
            f">= {req_S} mức độ mặn",
            "" if ok_S else f"Pha thêm dung dịch chuẩn để có tối thiểu {req_S} mức độ mặn khác nhau.",
        )
    ]

    # 2. Phải có mức 0‰
    co_0 = any(abs(v) <= 0.1 for v in s_vals) if len(s_vals) else False
    if cfg["phai_co_muc_0"]:
        muc_kiem.append(
            _muc(
                "co_muc_0",
                "Điểm gốc nước cất S ≈ 0‰",
                "dat" if co_0 else "chua_dat",
                "Có (≤ 0,1‰)" if co_0 else "Không có mức 0‰",
                "Bắt buộc có mức 0‰",
                "" if co_0 else "Bổ sung phép đo nước cất S = 0‰ làm mốc đối chiếu gốc.",
            )
        )
    else:
        muc_kiem.append(_muc("co_muc_0", "Điểm gốc nước cất S ≈ 0‰", "bo_qua", "Có" if co_0 else "Không", "Không bắt buộc theo cấu hình", ""))

    # 3. Phủ dải độ mặn mục tiêu
    t_min, t_max = cfg["dai_man_muc_tieu_ppt"]
    target_w = max(1e-6, float(t_max) - float(t_min))
    if len(s_vals):
        overlap = max(0.0, min(float(np.max(s_vals)), float(t_max)) - max(float(np.min(s_vals)), float(t_min)))
        phu_ratio = overlap / target_w
        dai_do_str = f"{phu_ratio*100:.0f}% ([{np.min(s_vals):.1f}..{np.max(s_vals):.1f}]‰)"
    else:
        phu_ratio = 0.0
        dai_do_str = "0% (trống)"
    req_phu = cfg["ti_le_phu_dai_man_toi_thieu"]
    ok_phu = phu_ratio >= req_phu - 1e-9
    muc_kiem.append(
        _muc(
            "phu_dai_man",
            f"Độ phủ dải độ mặn mục tiêu [{t_min:.0f}–{t_max:.0f}‰]",
            "dat" if ok_phu else "chua_dat",
            dai_do_str,
            f">= {req_phu*100:.0f}% bề rộng dải",
            "" if ok_phu else f"Mở rộng điểm đo chuẩn phủ ít nhất {req_phu*100:.0f}% dải [{t_min:.0f}..{t_max:.0f}‰].",
        )
    )

    # 4. Cân bằng tỉ lệ mẫu giữa các mức S
    if len(s_round):
        counts_S = pd.Series(s_round).value_counts()
        max_frac = float(counts_S.max() / len(s_round))
        muc_nhieu_nhat = float(counts_S.idxmax())
        cb_str = f"Tối đa {max_frac*100:.1f}% tại S={muc_nhieu_nhat:.1f}‰"
    else:
        max_frac = 1.0
        cb_str = "Không có dữ liệu"
    req_max_frac = cfg["ti_le_toi_da_moi_muc"]
    ok_cb = max_frac <= req_max_frac + 1e-9
    muc_kiem.append(
        _muc(
            "can_bang_muc_man",
            "Cân bằng số điểm giữa các mức S",
            "dat" if ok_cb else "chua_dat",
            cb_str,
            f"Mỗi mức <= {req_max_frac*100:.0f}% tổng số điểm",
            "" if ok_cb else "Phân bổ số phép đo đều hơn giữa các mức S để tránh lệch trọng số hồi quy.",
        )
    )

    # 5 & 6. Nhiệt độ T: số mức và biên độ
    t_cids, n_T = _gom_cum_1d(t_vals, max_gap=0.8, max_span=1.5)
    t_span = float(np.max(t_vals) - np.min(t_vals)) if len(t_vals) else 0.0
    req_T = cfg["so_muc_nhiet_toi_thieu"]
    ok_nT = n_T >= req_T
    muc_kiem.append(
        _muc(
            "so_muc_nhiet",
            "Số mức nhiệt độ khảo sát T",
            "dat" if ok_nT else "chua_dat",
            f"{n_T} mức nhiệt",
            f">= {req_T} mức nhiệt",
            "" if ok_nT else f"Đo thêm ở các mức nhiệt độ nước khác nhau để đạt tối thiểu {req_T} mức.",
        )
    )
    req_span_T = cfg["bien_do_nhiet_toi_thieu_C"]
    ok_span_T = t_span >= req_span_T - 1e-9
    muc_kiem.append(
        _muc(
            "bien_do_nhiet",
            "Biên độ nhiệt độ ΔT (max − min)",
            "dat" if ok_span_T else "chua_dat",
            f"{t_span:.2f} °C" if len(t_vals) else "0.00 °C",
            f">= {req_span_T:.1f} °C",
            "" if ok_span_T else f"Mở rộng dải nhiệt độ mẫu ít nhất {req_span_T:.1f} °C (ví dụ phòng điều hòa ↔ ngoài trời/bể ổn nhiệt).",
        )
    )

    # 7. Số lần lặp mỗi ô (S × T_level) — tính trên tập SAU KHI loại bản sao (W1), hiển thị cả trước và sau
    req_lap = cfg["so_lan_lap_toi_thieu_moi_o"]
    if len(s_round):
        cell_counts_raw: dict[tuple[float, int], int] = {}
        for sv, tc in zip(s_round, t_cids):
            key = (float(sv), int(tc))
            cell_counts_raw[key] = cell_counts_raw.get(key, 0) + 1
        min_lap_truoc = min(cell_counts_raw.values())
        mean_lap_truoc = float(np.mean(list(cell_counts_raw.values())))
    else:
        min_lap_truoc = 0
        mean_lap_truoc = 0.0

    if len(s_vals_nodup):
        s_round_nd = np.round(s_vals_nodup, 3)
        t_cids_nd, n_T_nd = _gom_cum_1d(t_vals_nodup, max_gap=0.8, max_span=1.5)
        n_S_nd = len(set(float(x) for x in s_round_nd))
        cell_counts: dict[tuple[float, int], int] = {}
        for sv, tc in zip(s_round_nd, t_cids_nd):
            key = (float(sv), int(tc))
            cell_counts[key] = cell_counts.get(key, 0) + 1
        min_lap = min(cell_counts.values())
        mean_lap = float(np.mean(list(cell_counts.values())))
        n_cells_thieu = sum(1 for c in cell_counts.values() if c < req_lap)
        if ban_sao["so_dong_ban_sao"] > 0:
            lap_str = (
                f"Tối thiểu {min_lap} lần/ô (TB {mean_lap:.1f} sau loại bản sao; "
                f"trước loại: {min_lap_truoc} lần/ô, TB {mean_lap_truoc:.1f}; "
                f"{len(cell_counts)}/{max(1, n_S_nd * n_T_nd)} ô)"
            )
        else:
            lap_str = f"Tối thiểu {min_lap} lần/ô (TB {mean_lap:.1f}; {len(cell_counts)}/{max(1, n_S_nd * n_T_nd)} ô)"
    else:
        min_lap = 0
        n_cells_thieu = 0
        lap_str = "0 lần/ô"
    ok_lap = min_lap >= req_lap
    muc_kiem.append(
        _muc(
            "so_lan_lap_moi_o",
            "Số lần lặp mỗi ô (S × mức T)",
            "dat" if ok_lap else "chua_dat",
            lap_str,
            f">= {req_lap} ảnh/lần lặp mỗi ô (sau loại bản sao)",
            "" if ok_lap else f"Có {n_cells_thieu} ô dưới {req_lap} lần lặp thực (không tính bản sao); chụp lặp lại tối thiểu {req_lap} ảnh độc lập mỗi ô.",
        )
    )

    # 8. Bản sao dữ liệu & nghi ngờ gán nhãn lại (W1)
    req_ti_le_bs = cfg["ti_le_ban_sao_toi_da"]
    so_bs = int(ban_sao["so_dong_ban_sao"])
    co_gnl = bool(ban_sao["co_nghi_ngo_gan_nhan_lai"])
    ti_le_bs = float(ban_sao["ti_le_ban_sao"])
    ok_bs = (ti_le_bs <= req_ti_le_bs + 1e-9) and (not co_gnl)
    dong_dau_str = ", ".join(str(x) for x in ban_sao["dong_nghi_ngo_dau_tien"])
    if ok_bs:
        bs_val_str = f"0 dòng bản sao ({ban_sao['so_dong_tong']} dòng độc lập)" if so_bs == 0 else f"{so_bs}/{ban_sao['so_dong_tong']} dòng ({ti_le_bs*100:.1f}%)"
        bs_goi_y = ""
    else:
        ly_do_parts = []
        if so_bs > 0:
            ly_do_parts.append(f"{so_bs} dòng bản sao ({ti_le_bs*100:.1f}%)")
        if co_gnl:
            ly_do_parts.append(f"nghi ngờ gán nhãn lại ({ban_sao['so_dong_nghi_gan_nhan_lai']} dòng cùng sha256_anh/ten_file nhưng delta_y_px khác nhau)")
        if dong_dau_str:
            ly_do_parts.append(f"dòng đầu tiên: {dong_dau_str}")
        bs_val_str = "; ".join(ly_do_parts)
        chi_tiet_txt = "; ".join(ban_sao["chi_tiet_nghi_ngo"][:3])
        bs_goi_y = (
            f"Loại bỏ dòng trùng lặp hoặc tách ảnh đúng tên/sha256 trước khi hiệu chuẩn ({chi_tiet_txt})."
            if chi_tiet_txt
            else "Kiểm tra và loại các dòng trùng lặp khỏi bảng CSV."
        )
    muc_kiem.append(
        _muc(
            "ban_sao_du_lieu",
            "Bản sao dữ liệu & nghi ngờ gán nhãn lại",
            "dat" if ok_bs else "chua_dat",
            bs_val_str,
            f"Tỉ lệ bản sao <= {req_ti_le_bs*100:.1f}% và không nghi ngờ gán nhãn lại",
            bs_goi_y,
        )
    )

    # 8. Số mẻ pha độc lập
    muc_me, n_me = _kiem_tra_me_pha(df_raw, cfg["so_me_pha_toi_thieu"])
    muc_kiem.append(muc_me)

    # 9. Biến thiên chênh nhiệt D (chỉ bắt buộc khi muon_hoc_D=True)
    muc_D, n_D, d_span = _kiem_tra_bien_thien_D(
        df_valid,
        t_vals,
        bool(muon_hoc_D),
        cfg["so_muc_D_toi_thieu_neu_hoc_D"],
        cfg["chenh_D_toi_thieu_C"],
    )
    muc_kiem.append(muc_D)

    # 10. px_per_mm
    muc_kiem.append(_kiem_tra_px_per_mm(df_raw, don_vi_y))

    # 11. nguon_du_lieu
    muc_nguon, nguon_list = _kiem_tra_nguon_du_lieu(df_raw)
    muc_kiem.append(muc_nguon)

    so_dat = sum(1 for m in muc_kiem if m["trang_thai"] == "dat")
    so_chua_dat = sum(1 for m in muc_kiem if m["trang_thai"] == "chua_dat")
    so_canh_bao = sum(1 for m in muc_kiem if m["trang_thai"] == "canh_bao")

    return {
        "hop_le_tong_quat": so_chua_dat == 0,
        "so_dat": so_dat,
        "so_chua_dat": so_chua_dat,
        "so_canh_bao": so_canh_bao,
        "tong_hang_muc": len(muc_kiem),
        "muc_kiem": muc_kiem,
        "tom_tat": {
            "so_dong": n_raw,
            "so_dong_hop_le": int(len(df_valid)),
            "so_muc_man": n_S,
            "co_muc_0": co_0,
            "ti_le_phu_dai_man": round(phu_ratio, 4),
            "ti_le_max_moi_muc": round(max_frac, 4),
            "so_muc_nhiet": n_T,
            "bien_do_nhiet_C": round(t_span, 3),
            "min_lap_moi_o": min_lap,
            "min_lap_moi_o_truoc_loai_ban_sao": min_lap_truoc,
            "so_dong_ban_sao": so_bs,
            "so_dong_sau_loai_ban_sao": int(ban_sao["so_dong_sau_loai"]),
            "co_nghi_ngo_gan_nhan_lai": co_gnl,
            "so_me_pha": n_me,
            "so_muc_D": n_D,
            "bien_do_D_C": round(d_span, 3),
            "nguon_du_lieu_list": nguon_list,
            "muon_hoc_D": bool(muon_hoc_D),
            "don_vi_y": str(don_vi_y or "px").strip().lower(),
        },
        "nguong_ap_dung": cfg,
    }


def kiem_tra_thiet_ke_tu_csv(
    csv_nguon: Path | str | io.StringIO | pd.DataFrame,
    config_path: Path | str = cal.CONFIG_MAC_DINH,
    muon_hoc_D: bool = False,
    don_vi_y: str = "px",
) -> dict[str, Any]:
    """Đọc CSV thô (tệp hoặc chuỗi CSV) và kiểm tra thiết kế thí nghiệm."""
    if isinstance(csv_nguon, pd.DataFrame):
        df = csv_nguon.copy()
    elif isinstance(csv_nguon, io.StringIO):
        df = pd.read_csv(io.StringIO(csv_nguon.getvalue().lstrip("\ufeff")))
    elif isinstance(csv_nguon, Path):
        df = pd.read_csv(csv_nguon, encoding="utf-8-sig")
    elif isinstance(csv_nguon, str):
        if "\n" in csv_nguon or "\r" in csv_nguon:
            df = pd.read_csv(io.StringIO(csv_nguon.lstrip("\ufeff")))
        else:
            df = pd.read_csv(Path(csv_nguon), encoding="utf-8-sig")
    else:
        raise TypeError("csv_nguon phải là Path, str, StringIO hoặc DataFrame.")
    return kiem_tra_thiet_ke_thi_nghiem(df, config_path=config_path, muon_hoc_D=muon_hoc_D, don_vi_y=don_vi_y)
