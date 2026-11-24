"""Phân tích khả năng chuyển đường chuẩn giữa các điện thoại (LOPO) và mẻ pha (LOBO) — X4.

Mục đích vật lí:
- Nếu chỉ giữ đơn vị pixel (px), khi đổi điện thoại hoặc khoảng cách đặt camera,
  hệ số phóng đại ảnh `px_per_mm` thay đổi làm đường chuẩn bị lệch hệ thống (scale shift).
  Quy đổi sang mm tại màn hứng (`delta_y_mm = delta_y_px / px_per_mm`) giúp chuẩn hóa
  độ nhạy hình học giữa các điện thoại khác nhau.
- Đánh giá chéo Leave-One-Phone-Out (`id_dien_thoai`) và Leave-One-Batch-Out (`ma_me_pha`)
  trên cả hai đơn vị `px` và `mm`: nếu RMS ngoài nhóm vượt ngưỡng `nguong_RMS_ppt`,
  hệ thống bật cờ cảnh báo `DUONG_CHUAN_KHONG_CHUYEN_DUOC` (`cap="can_than"`).
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from core import calibration as cal
from scripts.kiem_tra_chap_nhan_vong3 import khoang_tin_cay_wilson

ROOT = Path(__file__).resolve().parents[1]
CONFIG_MAC_DINH = ROOT / "config.yaml"


def tai_cau_hinh_chuyen_duong_chuan(config_path: str | Path | None = None) -> dict[str, Any]:
    """Đọc ngưỡng RMS chuyển đường chuẩn từ config.yaml."""
    cfg_p = Path(config_path) if config_path else CONFIG_MAC_DINH
    raw: dict[str, Any] = {}
    if cfg_p.exists():
        raw = yaml.safe_load(cfg_p.read_text(encoding="utf-8")) or {}
    cdc = raw.get("chuyen_duong_chuan") or {}
    return {
        "nguong_RMS_ppt": float(cdc.get("nguong_RMS_ppt", 0.5)),
    }


def _loc_du_lieu_hieu_chuan_sach(
    nguon: pd.DataFrame | str | Path,
    cfg_hc: cal.CauHinhHieuChuan,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Chuẩn hóa bảng, loại dòng `da_loai=True` và bản sao (nếu bật) trước khi chia LOPO/LOBO."""
    if isinstance(nguon, pd.DataFrame):
        df = nguon.copy()
    else:
        df = cal.doc_csv_hieu_chuan(nguon)

    so_truoc = len(df)
    so_loai_thu_cong = 0
    if "da_loai" in df.columns:
        mask_loai = df["da_loai"].astype(str).str.strip().str.lower().isin({"true", "1", "yes", "co"})
        so_loai_thu_cong = int(mask_loai.sum())
        if so_loai_thu_cong:
            df = df.loc[~mask_loai].copy()

    so_ban_sao_loai = 0
    if cfg_hc.loai_ban_sao_khi_khop and len(df) > 1:
        bs = cal.phat_hien_ban_sao_du_lieu(df)
        if bs.get("co_ban_sao") and bs.get("chi_so_dong_trung"):
            idx_bo = set(int(i) for i in bs["chi_so_dong_trung"])
            so_ban_sao_loai = len(idx_bo)
            df = df.drop(index=list(idx_bo), errors="ignore").copy()

    df = df.reset_index(drop=True)
    return df, {
        "so_dong_ban_dau": so_truoc,
        "so_dong_loai_thu_cong": so_loai_thu_cong,
        "so_ban_sao_loai": so_ban_sao_loai,
        "so_dong_hop_le": len(df),
    }


def _danh_gia_leave_one_group_out(
    df: pd.DataFrame,
    cot_nhom: str,
    ten_truc: str,
    don_vi_y: str,
    cfg_hc: cal.CauHinhHieuChuan,
    nguong_rms: float,
    bac_ep: int | None = None,
) -> dict[str, Any]:
    """Chạy Leave-One-Group-Out (LOPO hoặc LOBO) cho 1 cột nhóm và 1 đơn vị y ('px'/'mm')."""
    if cot_nhom not in df.columns:
        return {
            "truc": ten_truc,
            "cot_nhom": cot_nhom,
            "don_vi_y": don_vi_y,
            "trang_thai": "KHONG_DU_NHOM",
            "so_nhom": 0,
            "chi_tiet_nhom": [],
            "tong_hop": None,
            "canh_bao": [f"Thiếu cột '{cot_nhom}' để kiểm tra chuyển đường chuẩn."],
        }

    nhom_series = df[cot_nhom].astype(object).fillna("").astype(str).str.strip()
    nhom_hop_le = sorted({g for g in nhom_series.tolist() if g})
    if len(nhom_hop_le) < 2:
        return {
            "truc": ten_truc,
            "cot_nhom": cot_nhom,
            "don_vi_y": don_vi_y,
            "trang_thai": "KHONG_DU_NHOM",
            "so_nhom": len(nhom_hop_le),
            "danh_sach_nhom": nhom_hop_le,
            "chi_tiet_nhom": [],
            "tong_hop": None,
            "canh_bao": [
                f"Chỉ có {len(nhom_hop_le)} nhóm hợp lệ ở '{cot_nhom}' (cần ≥ 2) để kiểm tra {ten_truc}."
            ],
        }

    if don_vi_y == "mm":
        if cal.COT_PX_PER_MM not in df.columns:
            return {
                "truc": ten_truc,
                "cot_nhom": cot_nhom,
                "don_vi_y": "mm",
                "trang_thai": "THIEU_PX_PER_MM",
                "so_nhom": len(nhom_hop_le),
                "chi_tiet_nhom": [],
                "tong_hop": None,
                "canh_bao": ["Thiếu cột px_per_mm nên không thể quy đổi sang đơn vị mm."],
            }
        px_vals = pd.to_numeric(df[cal.COT_PX_PER_MM], errors="coerce")
        if not bool(np.all(np.isfinite(px_vals) & (px_vals > 0))):
            return {
                "truc": ten_truc,
                "cot_nhom": cot_nhom,
                "don_vi_y": "mm",
                "trang_thai": "THIEU_PX_PER_MM",
                "so_nhom": len(nhom_hop_le),
                "chi_tiet_nhom": [],
                "tong_hop": None,
                "canh_bao": ["Một số dòng thiếu px_per_mm hợp lệ (> 0), không thể quy đổi sang mm."],
            }

    chi_tiet_nhom: list[dict[str, Any]] = []
    err_tat_ca: list[float] = []
    phu_tat_ca: list[bool] = []

    for g in nhom_hop_le:
        mask_test = nhom_series == g
        df_train = df.loc[~mask_test].copy().reset_index(drop=True)
        df_test = df.loc[mask_test].copy().reset_index(drop=True)
        if len(df_train) < 6 or df_test.empty:
            continue

        bc = cal.dung_duong_chuan(df_train, cau_hinh=cfg_hc, bac_ep=bac_ep, don_vi_y=don_vi_y)
        mh = bc.mo_hinh

        errs_g: list[float] = []
        phu_g: list[bool] = []
        t_tc_col = cal.COT_NHIET_DO_TC if cal.COT_NHIET_DO_TC in df_test.columns else None
        px_col = cal.COT_PX_PER_MM if cal.COT_PX_PER_MM in df_test.columns else None

        for _, row in df_test.iterrows():
            s_true = float(row[cal.COT_DO_MAN])
            dy = float(row[cal.COT_DELTA_Y])
            t_c = float(row[cal.COT_NHIET_DO])
            t_tc = float(row[t_tc_col]) if (t_tc_col and pd.notna(row[t_tc_col])) else None
            px_mm = float(row[px_col]) if (px_col and pd.notna(row[px_col])) else None
            kq = cal.uoc_luong_do_man(
                mh,
                delta_y_px=dy,
                T_C=t_c,
                T_tham_chieu_C=t_tc,
                px_per_mm=px_mm if don_vi_y == "mm" else None,
            )
            e = float(kq.S_ppt - s_true)
            u_1sigma = max(float(kq.u_S_ppt), 1e-12)
            trong_2s = abs(e) <= 2.0 * u_1sigma
            errs_g.append(e)
            phu_g.append(trong_2s)

        arr_e = np.asarray(errs_g, dtype=float)
        k_phu = int(sum(phu_g))
        n_g = len(arr_e)
        w_lo, w_hi = khoang_tin_cay_wilson(k_phu, n_g)
        rms_g = float(np.sqrt(np.mean(arr_e * arr_e)))
        chi_tiet_nhom.append({
            "nhom": g,
            "so_diem_kiem": n_g,
            "bias_ppt": float(np.mean(arr_e)),
            "rms_ppt": rms_g,
            "max_abs_err_ppt": float(np.max(np.abs(arr_e))),
            "so_diem_phu_2sigma": k_phu,
            "ty_le_phu_2sigma": k_phu / max(n_g, 1),
            "wilson_95_phu_2sigma": [w_lo, w_hi],
            "vuot_nguong": bool(rms_g > nguong_rms),
        })
        err_tat_ca.extend(errs_g)
        phu_tat_ca.extend(phu_g)

    if not err_tat_ca:
        return {
            "truc": ten_truc,
            "cot_nhom": cot_nhom,
            "don_vi_y": don_vi_y,
            "trang_thai": "KHONG_DU_DU_LIEU_CHIA_FOLD",
            "so_nhom": len(nhom_hop_le),
            "chi_tiet_nhom": [],
            "tong_hop": None,
            "canh_bao": [f"Không đủ điểm huấn luyện để chạy {ten_truc} ({don_vi_y})."],
        }

    arr_all = np.asarray(err_tat_ca, dtype=float)
    k_all = int(sum(phu_tat_ca))
    n_all = len(arr_all)
    w_lo_all, w_hi_all = khoang_tin_cay_wilson(k_all, n_all)
    rms_all = float(np.sqrt(np.mean(arr_all * arr_all)))
    vuot = bool(rms_all > nguong_rms)

    return {
        "truc": ten_truc,
        "cot_nhom": cot_nhom,
        "don_vi_y": don_vi_y,
        "trang_thai": "HOP_LE",
        "so_nhom": len(nhom_hop_le),
        "chi_tiet_nhom": chi_tiet_nhom,
        "tong_hop": {
            "so_diem_kiem": n_all,
            "bias_ppt": float(np.mean(arr_all)),
            "rms_ppt": rms_all,
            "max_abs_err_ppt": float(np.max(np.abs(arr_all))),
            "so_diem_phu_2sigma": k_all,
            "ty_le_phu_2sigma": k_all / max(n_all, 1),
            "wilson_95_phu_2sigma": [w_lo_all, w_hi_all],
            "nguong_RMS_ppt": float(nguong_rms),
            "vuot_nguong": vuot,
        },
        "canh_bao": (
            [f"{ten_truc} ({don_vi_y}): RMS = {rms_all:.3f} ‰ > ngưỡng {nguong_rms:.3f} ‰."]
            if vuot
            else []
        ),
    }


def phan_tich_chuyen_duong_chuan(
    nguon: pd.DataFrame | str | Path,
    *,
    bac_ep: int | None = None,
    nguong_RMS_ppt: float | None = None,
    config_path: str | Path | None = None,
    luu_json_path: str | Path | None = None,
) -> dict[str, Any]:
    """Đánh giá khả năng chuyển đường chuẩn giữa điện thoại (LOPO) và mẻ pha (LOBO) trên cả `px` và `mm`."""
    cfg_cdc = tai_cau_hinh_chuyen_duong_chuan(config_path)
    nguong = float(nguong_RMS_ppt if nguong_RMS_ppt is not None else cfg_cdc["nguong_RMS_ppt"])
    cfg_hc = cal.CauHinhHieuChuan.tu_yaml(config_path if config_path else CONFIG_MAC_DINH)

    df_sach, thong_ke_loc = _loc_du_lieu_hieu_chuan_sach(nguon, cfg_hc)
    nguon_du_lieu = "KHONG_RO"
    if cal.COT_NGUON in df_sach.columns and len(df_sach):
        vals = {str(v).strip().upper() for v in df_sach[cal.COT_NGUON].dropna().tolist() if str(v).strip()}
        if vals == {"THUC_TE"}:
            nguon_du_lieu = "THUC_TE"
        elif "MO_PHONG" in vals:
            nguon_du_lieu = "MO_PHONG"
        elif vals:
            nguon_du_lieu = ", ".join(sorted(vals))

    ket_qua_don_vi: dict[str, dict[str, Any]] = {}
    canh_bao_chi_tiet: list[dict[str, str]] = []

    for dv in ("px", "mm"):
        lopo = _danh_gia_leave_one_group_out(
            df_sach, cal.COT_ID_DIEN_THOAI, "LOPO_dien_thoai", dv, cfg_hc, nguong, bac_ep=bac_ep
        )
        lobo = _danh_gia_leave_one_group_out(
            df_sach, cal.COT_MA_ME_PHA, "LOBO_me_pha", dv, cfg_hc, nguong, bac_ep=bac_ep
        )
        ket_qua_don_vi[dv] = {"lopo_dien_thoai": lopo, "lobo_me_pha": lobo}
        for muc in (lopo, lobo):
            th = muc.get("tong_hop")
            if th and th.get("vuot_nguong"):
                canh_bao_chi_tiet.append({
                    "ma": "DUONG_CHUAN_KHONG_CHUYEN_DUOC",
                    "cap": "can_than",
                    "truc": muc["truc"],
                    "don_vi_y": dv,
                    "thong_diep": (
                        f"Cẩn thận: {muc['truc']} dùng đơn vị {dv} có RMS = {th['rms_ppt']:.3f} ‰ "
                        f"vượt ngưỡng {nguong:.3f} ‰ — đường chuẩn không chuyển trực tiếp sang nhóm mới được."
                    ),
                })

    lopo_px = ket_qua_don_vi["px"]["lopo_dien_thoai"].get("tong_hop")
    lopo_mm = ket_qua_don_vi["mm"]["lopo_dien_thoai"].get("tong_hop")
    so_sanh_px_mm: dict[str, Any] = {"kha_dung": False}
    if lopo_px and lopo_mm:
        rms_px = float(lopo_px["rms_ppt"])
        rms_mm = float(lopo_mm["rms_ppt"])
        so_sanh_px_mm = {
            "kha_dung": True,
            "rms_lopo_px_ppt": rms_px,
            "rms_lopo_mm_ppt": rms_mm,
            "giam_rms_ppt": rms_px - rms_mm,
            "ty_le_giam_pct": ((rms_px - rms_mm) / max(rms_px, 1e-12)) * 100.0,
            "mm_tot_hon_px": bool(rms_mm < rms_px),
        }

    co_hop_le = any(
        ket_qua_don_vi[dv][k]["trang_thai"] == "HOP_LE"
        for dv in ("px", "mm")
        for k in ("lopo_dien_thoai", "lobo_me_pha")
    )
    out = {
        "nguon_du_lieu": nguon_du_lieu,
        "trang_thai": "HOP_LE" if co_hop_le else "KHONG_DU_NHOM",
        "nguong_RMS_ppt": nguong,
        "thong_ke_loc": thong_ke_loc,
        "ket_qua_theo_don_vi": ket_qua_don_vi,
        "so_sanh_lopo_px_vs_mm": so_sanh_px_mm,
        "co_canh_bao_khong_chuyen_duoc": any(
            c["ma"] == "DUONG_CHUAN_KHONG_CHUYEN_DUOC" for c in canh_bao_chi_tiet
        ),
        "canh_bao_chi_tiet": canh_bao_chi_tiet,
    }
    if luu_json_path is not None:
        p_out = Path(luu_json_path)
        p_out.parent.mkdir(parents=True, exist_ok=True)
        p_out.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def bang_tom_tat_chuyen_duong_chuan(kq: dict[str, Any]) -> pd.DataFrame:
    """Chuyển kết quả LOPO/LOBO theo px & mm thành bảng DataFrame phẳng để xuất CSV/Markdown."""
    dong: list[dict[str, Any]] = []
    theo_dv = kq.get("ket_qua_theo_don_vi") or {}
    for dv in ("px", "mm"):
        for khoa in ("lopo_dien_thoai", "lobo_me_pha"):
            muc = (theo_dv.get(dv) or {}).get(khoa) or {}
            th = muc.get("tong_hop")
            if th:
                dong.append({
                    "truc": muc.get("truc", khoa),
                    "don_vi_y": dv,
                    "trang_thai": muc.get("trang_thai"),
                    "so_nhom": muc.get("so_nhom"),
                    "so_diem_kiem": th["so_diem_kiem"],
                    "bias_ppt": round(th["bias_ppt"], 4),
                    "rms_ppt": round(th["rms_ppt"], 4),
                    "max_abs_err_ppt": round(th["max_abs_err_ppt"], 4),
                    "ty_le_phu_2sigma": round(th["ty_le_phu_2sigma"], 4),
                    "vuot_nguong": th["vuot_nguong"],
                })
            else:
                dong.append({
                    "truc": muc.get("truc", khoa),
                    "don_vi_y": dv,
                    "trang_thai": muc.get("trang_thai", "KHONG_DU_NHOM"),
                    "so_nhom": muc.get("so_nhom", 0),
                    "so_diem_kiem": 0,
                    "bias_ppt": None,
                    "rms_ppt": None,
                    "max_abs_err_ppt": None,
                    "ty_le_phu_2sigma": None,
                    "vuot_nguong": False,
                })
    return pd.DataFrame(dong)


def ve_bieu_do_chuyen_duong_chuan(
    kq: dict[str, Any],
    duong_dan_png: str | Path,
    *,
    mo_phong: bool = False,
) -> Path:
    """Vẽ biểu đồ cột so sánh RMS LOPO/LOBO theo px và mm kèm đường ngưỡng và watermark nếu mô phỏng."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    df_b = bang_tom_tat_chuyen_duong_chuan(kq)
    out = Path(duong_dan_png)
    out.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(7.2, 4.2), dpi=130)
    labels = ["LOPO điện thoại", "LOBO mẻ pha"]
    x = np.arange(len(labels))
    width = 0.34

    def _lay_rms(truc: str, dv: str) -> float:
        sub = df_b[(df_b["truc"] == truc) & (df_b["don_vi_y"] == dv)]
        if sub.empty or pd.isna(sub.iloc[0]["rms_ppt"]):
            return 0.0
        return float(sub.iloc[0]["rms_ppt"])

    rms_px = [_lay_rms("LOPO_dien_thoai", "px"), _lay_rms("LOBO_me_pha", "px")]
    rms_mm = [_lay_rms("LOPO_dien_thoai", "mm"), _lay_rms("LOBO_me_pha", "mm")]

    ax.bar(x - width / 2, rms_px, width, label="Đơn vị px", color="#d97706")
    ax.bar(x + width / 2, rms_mm, width, label="Đơn vị mm (đã chuẩn hóa thang)", color="#0284c7")
    nguong = float(kq.get("nguong_RMS_ppt", 0.5))
    ax.axhline(nguong, color="#dc2626", linestyle="--", linewidth=1.4, label=f"Ngưỡng cảnh báo ({nguong:.2f} ‰)")

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("RMS ngoài nhóm (‰)")
    ax.set_title("Đánh giá chuyển đường chuẩn giữa điện thoại và mẻ pha")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(axis="y", alpha=0.25)

    if mo_phong or str(kq.get("nguon_du_lieu", "")).upper() != "THUC_TE":
        fig.text(
            0.5,
            0.5,
            "DU LIEU MO PHONG / CHUA XAC THUC THUC NGHIEM",
            ha="center",
            va="center",
            fontsize=11,
            color="#94a3b8",
            alpha=0.35,
            rotation=18,
            weight="bold",
        )

    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)
    return out

