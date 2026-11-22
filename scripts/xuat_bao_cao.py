"""Xuất bộ tài liệu cho báo cáo KHKT và poster (tái sử dụng core.calibration, optics, trang_thai_cau_hinh)."""

from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from matplotlib.figure import Figure

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import calibration as cal
from core.kiem_tra_thiet_ke import kiem_tra_thiet_ke_thi_nghiem, kiem_tra_thiet_ke_tu_csv
from core.optics import CauHinhQuangHoc, ngan_sach_sai_so
from core.trang_thai_cau_hinh import XAC_NHAN_QF_MAC_DINH, liet_ke_tham_so_chua_xac_nhan
from sim.synth import sinh_du_lieu_hieu_chuan_mo_phong

# Hằng số nhãn bắt buộc — tuyệt đối KHÔNG cho phép tắt bằng tham số hay cờ CLI
BANNER_MO_PHONG = "DỮ LIỆU MÔ PHỎNG / CHƯA XÁC NHẬN"


def _them_watermark(ax: Any, text: str = BANNER_MO_PHONG) -> None:
    """Gắn watermark chéo lên axes khi dữ liệu chưa được xác nhận là đo thật."""
    ax.text(
        0.5,
        0.5,
        text,
        transform=ax.transAxes,
        fontsize=15,
        fontweight="bold",
        color="#c62828",
        alpha=0.22,
        ha="center",
        va="center",
        rotation=22,
        zorder=10,
    )


def ve_hinh_duong_chuan_va_phan_du(
    bc: cal.BaoCaoHieuChuan,
    chua_xac_nhan: bool,
    k: float = 2.0,
) -> Figure:
    """Vẽ 2 khung gộp: đường chuẩn kèm băng bất định (±k·u) và phần dư theo S."""
    mh = bc.mo_hinh
    don_vi = getattr(mh, "don_vi_y", "px")
    fig = Figure(figsize=(8.2, 7.0), dpi=130)
    ax1 = fig.add_subplot(211)
    ax2 = fig.add_subplot(212, sharex=ax1)

    y_tr = cal._lay_y_theo_don_vi(bc.df_train, don_vi)
    ax1.scatter(bc.df_train[cal.COT_DO_MAN], y_tr, s=22, label="Điểm chuẩn (train)", zorder=3)
    if len(bc.df_test):
        y_te = cal._lay_y_theo_don_vi(bc.df_test, don_vi)
        ax1.scatter(
            bc.df_test[cal.COT_DO_MAN],
            y_te,
            s=36,
            marker="x",
            color="#d32f2f",
            label="Điểm kiểm tra (test)",
            zorder=4,
        )

    S_luoi = np.linspace(mh.S_min, mh.S_max, 200)
    tat_ca_T = pd.concat([bc.df_train, bc.df_test])[cal.COT_NHIET_DO].to_numpy(float)
    muc_T = sorted(np.unique(np.round(tat_ca_T * 2) / 2))
    for T in (muc_T if mh.co_bu_nhiet else [mh.T_ref])[:6]:
        ax1.plot(S_luoi, mh.du_doan_delta_y(S_luoi, T), lw=1.3, label=f"Đường chuẩn T = {T:g} °C")

    # Vẽ băng bất định dự đoán ±k·√(u_fit² + s_res²) tại T_ref để minh họa độ tin cậy của khớp
    y_ref = mh.du_doan_delta_y(S_luoi, mh.T_ref)
    u_pred = np.array(
        [math.sqrt(max(0.0, mh.phuong_sai_du_doan(float(s), mh.T_ref)) + mh.s_res_px**2) for s in S_luoi],
        dtype=float,
    )
    ax1.fill_between(
        S_luoi,
        y_ref - k * u_pred,
        y_ref + k * u_pred,
        color="#90caf9",
        alpha=0.28,
        label=f"Vùng dự đoán ±{k:g}·u (T={mh.T_ref:g} °C)",
    )

    tieu_de = f"Đường chuẩn bậc {mh.bac} (R² = {mh.R2:.5f}, s_res = {mh.s_res_px:.3f} {don_vi})"
    if chua_xac_nhan:
        tieu_de = f"{BANNER_MO_PHONG}\n{tieu_de}"
    ax1.set_title(tieu_de, fontsize=10.5, fontweight="bold" if chua_xac_nhan else "normal", color="#c62828" if chua_xac_nhan else "#111111")
    ax1.set_ylabel(f"Δy ({don_vi})")
    ax1.grid(alpha=0.3)
    ax1.legend(fontsize=7.5, loc="best")

    mh_train = bc.mo_hinh_train
    for d, nhan, kieu in ((bc.df_train, "train", "o"), (bc.df_test, "test", "x")):
        if len(d):
            y_thuc = cal._lay_y_theo_don_vi(d, don_vi)
            du = y_thuc - mh_train.du_doan_delta_y(
                d[cal.COT_DO_MAN].to_numpy(float),
                d[cal.COT_NHIET_DO].to_numpy(float),
                T_tc=cal._lay_nhiet_do_tc(d),
            )
            ax2.scatter(d[cal.COT_DO_MAN], du, s=22, marker=kieu, label=nhan)
    ax2.axhline(0.0, color="#111111", lw=0.9)
    for dau in (-2.0, 2.0):
        ax2.axhline(dau * mh_train.s_res_px, color="#616161", ls="--", lw=0.9)
    ax2.set_xlabel("Độ mặn chuẩn S (‰)")
    ax2.set_ylabel(f"Phần dư ({don_vi})")
    ax2.set_title(f"Phần dư (±2·s_res = ±{2.0 * mh_train.s_res_px:.3f} {don_vi})", fontsize=9.5)
    ax2.grid(alpha=0.3)
    ax2.legend(fontsize=8)

    if chua_xac_nhan:
        _them_watermark(ax1)
        _them_watermark(ax2)

    fig.tight_layout()
    return fig


def phan_tich_bland_altman_csv(csv_path: str | Path) -> dict[str, Any]:
    """Đọc CSV so sánh (S_thiet_bi, S_khuc_xa_ke, [nguon_du_lieu]) và tính Bias + 95% LoA."""
    df_raw = pd.read_csv(csv_path, encoding="utf-8-sig")
    if "S_thiet_bi" not in df_raw.columns or "S_khuc_xa_ke" not in df_raw.columns:
        raise ValueError("File --so-sanh phải có 2 cột S_thiet_bi và S_khuc_xa_ke.")

    df = df_raw.copy()
    df["S_thiet_bi"] = pd.to_numeric(df["S_thiet_bi"], errors="coerce")
    df["S_khuc_xa_ke"] = pd.to_numeric(df["S_khuc_xa_ke"], errors="coerce")
    df = df.dropna(subset=["S_thiet_bi", "S_khuc_xa_ke"]).reset_index(drop=True)
    if len(df) < 3:
        raise ValueError("Cần ít nhất 3 cặp hợp lệ trong CSV so sánh để vẽ Bland–Altman.")

    if "nguon_du_lieu" in df.columns:
        nguon = df["nguon_du_lieu"].fillna("CHUA_XAC_DINH").astype(str).str.strip().str.upper()
        chua_xac_nhan = not bool((nguon == cal.NHAN_THUC_TE).all())
        nguon_col = nguon.tolist()
    else:
        chua_xac_nhan = True
        nguon_col = ["CHUA_XAC_DINH"] * len(df)

    m1 = df["S_thiet_bi"].to_numpy(float)
    m2 = df["S_khuc_xa_ke"].to_numpy(float)
    tb = (m1 + m2) / 2.0
    hieu = m1 - m2
    bias = float(np.mean(hieu))
    sd = float(np.std(hieu, ddof=1))
    loa_tren = bias + 1.96 * sd
    loa_duoi = bias - 1.96 * sd
    r_corr = float(np.corrcoef(m1, m2)[0, 1]) if np.std(m1) > 0 and np.std(m2) > 0 else 1.0

    return {
        "n_pair": len(df),
        "m1": m1,
        "m2": m2,
        "trung_binh": tb,
        "hieu": hieu,
        "bias": bias,
        "sd": sd,
        "loa_tren": loa_tren,
        "loa_duoi": loa_duoi,
        "r_corr": r_corr,
        "nguon_col": nguon_col,
        "chua_xac_nhan": chua_xac_nhan,
    }


def ve_hinh_bland_altman(ba: dict[str, Any]) -> Figure:
    """Vẽ đồ thị Bland–Altman từ kết quả phân tích."""
    fig = Figure(figsize=(7.5, 4.8), dpi=130)
    ax = fig.add_subplot(111)
    ax.scatter(ba["trung_binh"], ba["hieu"], s=28, alpha=0.85, label="Cặp đo (S_tb − S_khúc_xạ_kế)")
    ax.axhline(ba["bias"], color="#1565c0", lw=1.4, label=f"Bias = {ba['bias']:+.3f} ‰")
    ax.axhline(ba["loa_tren"], color="#c62828", ls="--", lw=1.2, label=f"+1.96·SD = {ba['loa_tren']:+.3f} ‰")
    ax.axhline(ba["loa_duoi"], color="#c62828", ls="--", lw=1.2, label=f"−1.96·SD = {ba['loa_duoi']:+.3f} ‰")
    ax.axhline(0.0, color="#616161", ls=":", lw=0.9)

    chua_xn = bool(ba["chua_xac_nhan"])
    tieu_de = f"Bland–Altman (n = {ba['n_pair']}, Bias = {ba['bias']:+.3f} ‰, LoA = [{ba['loa_duoi']:+.3f}, {ba['loa_tren']:+.3f}] ‰)"
    if chua_xn:
        tieu_de = f"{BANNER_MO_PHONG}\n{tieu_de}"
        _them_watermark(ax)
    ax.set_title(tieu_de, fontsize=10.5, fontweight="bold" if chua_xn else "normal", color="#c62828" if chua_xn else "#111111")
    ax.set_xlabel("Trung bình (S_thiết_bị + S_khúc_xạ_kế) / 2 (‰)")
    ax.set_ylabel("Hiệu (S_thiết_bị − S_khúc_xạ_kế) (‰)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="best")
    fig.tight_layout()
    return fig


def _tinh_bang_sai_so_theo_muc(bc: cal.BaoCaoHieuChuan, df: pd.DataFrame, k: float) -> pd.DataFrame:
    """Tính bảng sai số từng mức độ mặn kèm độ lệch chuẩn S (‰) và Δy."""
    bang_all = cal._bang_sai_so(bc.mo_hinh, df, k)
    dong: list[dict[str, Any]] = []
    for S0, nhom in bang_all.groupby(cal.COT_DO_MAN):
        n = int(len(nhom))
        dy_vals = nhom[cal.COT_DELTA_Y].to_numpy(float)
        s_vals = nhom["S_uoc_luong_ppt"].to_numpy(float)
        err_vals = nhom["sai_so_S_ppt"].to_numpy(float)
        std_px = float(np.std(dy_vals, ddof=1)) if n >= 2 else 0.0
        s_hop_le = s_vals[np.isfinite(s_vals)]
        std_s = float(np.std(s_hop_le, ddof=1)) if len(s_hop_le) >= 2 else 0.0
        dong.append({
            "S_chuan_ppt": float(S0),
            "so_diem": n,
            "delta_y_tb": float(np.mean(dy_vals)),
            "do_lech_chuan_px": std_px,
            "S_uoc_luong_tb_ppt": float(np.nanmean(s_vals)) if len(s_hop_le) else float("nan"),
            "do_lech_chuan_S_ppt": std_s,
            "sai_so_S_tb_ppt": float(np.nanmean(err_vals)) if np.any(np.isfinite(err_vals)) else float("nan"),
            "sai_so_S_max_ppt": float(np.nanmax(np.abs(err_vals))) if np.any(np.isfinite(err_vals)) else float("nan"),
        })
    return pd.DataFrame(dong)


def _ghi_csv_co_chu_thich(path: Path, df: pd.DataFrame, chu_thich: list[str]) -> None:
    """Ghi DataFrame ra CSV kèm các dòng chú thích `# ...` ở đầu file."""
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        for line in chu_thich:
            f.write(f"# {line}\n")
        df.to_csv(f, index=False)


def _df_to_markdown_table(df: pd.DataFrame) -> str:
    """Chuyển DataFrame thành bảng Markdown thuần (không phụ thuộc thư viện tabulate)."""
    cols = [str(c) for c in df.columns]
    lines = [
        "| " + " | ".join(cols) + " |",
        "| " + " | ".join(["---"] * len(cols)) + " |",
    ]
    for _, row in df.iterrows():
        cells = []
        for c in df.columns:
            v = row[c]
            if isinstance(v, (float, np.floating)):
                cells.append(f"{float(v):.4g}" if math.isfinite(float(v)) else "nan")
            else:
                cells.append(str(v).replace("|", "\\|"))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def xuat_bo_bao_cao(
    csv_hieu_chuan: str | Path | None = None,
    mo_phong: bool = False,
    csv_so_sanh: str | Path | None = None,
    out_dir: str | Path = ROOT / "outputs" / "bao_cao",
    don_vi_y: str = "px",
    config_path: str | Path = ROOT / "config.yaml",
    xac_nhan_quan_fry_path: str | Path | None = XAC_NHAN_QF_MAC_DINH,
) -> dict[str, Any]:
    """Chạy toàn bộ quy trình xuất 6 tài liệu báo cáo vào thư mục `out_dir`."""
    if not mo_phong and csv_hieu_chuan is None:
        raise ValueError("Phải truyền --csv <đường dẫn> hoặc --mo-phong.")

    cfg_path = Path(config_path)
    ch = cal.CauHinhHieuChuan.tu_yaml(cfg_path)
    qh = CauHinhQuangHoc.tu_yaml(cfg_path)
    with open(cfg_path, encoding="utf-8") as f:
        raw_cfg = yaml.safe_load(f) or {}

    if csv_hieu_chuan is not None:
        df = cal.doc_csv_hieu_chuan(csv_hieu_chuan)
        kq_thiet_ke = kiem_tra_thiet_ke_tu_csv(csv_hieu_chuan, config_path=cfg_path, don_vi_y=don_vi_y)
    else:
        df = sinh_du_lieu_hieu_chuan_mo_phong()
        kq_thiet_ke = kiem_tra_thiet_ke_thi_nghiem(df, config_path=cfg_path, don_vi_y=don_vi_y)

    bc = cal.dung_duong_chuan(df, ch, don_vi_y=don_vi_y)
    mh = bc.mo_hinh

    # Bất kì dòng nào không phải THUC_TE HOẶC mang dấu vết mô phỏng ở cột phụ -> bắt buộc đóng dấu MÔ PHỎNG / CHƯA XÁC NHẬN
    co_dong_khong_thuc = (
        cal.COT_NGUON not in df.columns
        or any(str(v).strip().upper() != cal.NHAN_THUC_TE for v in df[cal.COT_NGUON].fillna(""))
    )
    co_dau_vet_mp_cot_phu = any(
        any(tok in str(v).upper() for tok in ("MO_PHONG", "SIMULATED", "MÔ PHỎNG"))
        for col in (cal.COT_ID_THIET_BI, cal.COT_ID_DIEN_THOAI, cal.COT_GHI_CHU)
        if col in df.columns
        for v in df[col].fillna("")
    )
    chua_xac_nhan_hc = (not mh.da_xac_nhan_thuc_te) or co_dong_khong_thuc or co_dau_vet_mp_cot_phu

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # 1. Đồ thị đường chuẩn & phần dư + băng bất định
    fig_hc = ve_hinh_duong_chuan_va_phan_du(bc, chua_xac_nhan=chua_xac_nhan_hc, k=ch.he_so_phu_k)
    duong_chuan_png = out_path / "duong_chuan_va_phan_du.png"
    fig_hc.savefig(duong_chuan_png, dpi=150)

    # 2. Bảng sai số theo từng mức độ mặn
    df_muc = _tinh_bang_sai_so_theo_muc(bc, df, ch.he_so_phu_k)
    bang_muc_csv = out_path / "bang_sai_so_theo_muc.csv"
    chu_thich_muc = [BANNER_MO_PHONG] if chua_xac_nhan_hc else ["NGUON_DU_LIEU=THUC_TE (theo nhan CSV dau vao)"]
    _ghi_csv_co_chu_thich(bang_muc_csv, df_muc, chu_thich_muc)

    # 3. Đồ thị & bảng Bland–Altman (nếu có CSV so sánh)
    ba_info: dict[str, Any] | None = None
    fig_ba: Figure | None = None
    bland_png: Path | None = None
    bland_csv: Path | None = None
    chua_xac_nhan_ba = False
    if csv_so_sanh is not None:
        ba_info = phan_tich_bland_altman_csv(csv_so_sanh)
        chua_xac_nhan_ba = bool(ba_info["chua_xac_nhan"])
        fig_ba = ve_hinh_bland_altman(ba_info)
        bland_png = out_path / "bland_altman.png"
        fig_ba.savefig(bland_png, dpi=150)

        df_ba = pd.DataFrame({
            "S_thiet_bi": ba_info["m1"],
            "S_khuc_xa_ke": ba_info["m2"],
            "trung_binh_ppt": ba_info["trung_binh"],
            "sai_khac_S_tb_tru_kxk_ppt": ba_info["hieu"],
            "bias_ppt": ba_info["bias"],
            "sd_ppt": ba_info["sd"],
            "loa_duoi_ppt": ba_info["loa_duoi"],
            "loa_tren_ppt": ba_info["loa_tren"],
            "nguon_du_lieu": ba_info["nguon_col"],
        })
        bland_csv = out_path / "bang_bland_altman.csv"
        chu_thich_ba = [BANNER_MO_PHONG] if chua_xac_nhan_ba else ["NGUON_DU_LIEU=THUC_TE (theo nhan CSV so sanh)"]
        _ghi_csv_co_chu_thich(bland_csv, df_ba, chu_thich_ba)

    # 4. Bảng ngân sách sai số lí thuyết (từ giả định trong config.yaml)
    ps = raw_cfg.get("phan_tich_sai_so", {}) or {}
    sai_so_tam = float(ps.get("sai_so_tim_tam_px", 0.05))
    lech_t = float(ps.get("lech_nhiet_do_hai_ngan_C", 0.5))
    sai_a = float(ps.get("sai_so_goc_A_do", 0.05))
    troi = float(ps.get("troi_laser_chung_px", 5.0))
    triet = float(ps.get("he_so_triet_chung", 0.01))
    T_ngan_sach = float(qh.T_tham_chieu_C)
    ns_rows: list[dict[str, Any]] = []
    for s_val in (5.0, 20.0, 35.0):
        bd = ngan_sach_sai_so(
            S_ppt=s_val,
            T_C=T_ngan_sach,
            cfg=qh,
            sai_so_tim_tam_px=sai_so_tam,
            lech_nhiet_do_C=lech_t,
            sai_so_goc_A_do=sai_a,
            troi_laser_px=troi,
            he_so_triet_chung=triet,
        )
        ns_rows.append({
            "S_ppt": s_val,
            "T_C": T_ngan_sach,
            "tim_tam_ppt": bd["tim_tam"],
            "nhiet_do_ppt": bd["nhiet_do"],
            "goc_A_ppt": bd["goc_A"],
            "troi_laser_ppt": bd["troi_laser"],
            "tong_hop_rss_ppt": bd["tong_RSS"],
        })
    df_ns = pd.DataFrame(ns_rows)
    ngan_sach_csv = out_path / "ngan_sach_sai_so.csv"
    chu_thich_ns = [
        "PHAN TICH DO NHAY TU GIA DINH TRONG config.yaml - KHONG PHAI KET QUA DO THUC",
        (
            f"Gia dinh dau vao: sai_so_tim_tam_px={sai_so_tam}, lech_nhiet_do_hai_ngan_C={lech_t}, "
            f"sai_so_goc_A_do={sai_a}, troi_laser_chung_px={troi}, he_so_triet_chung={triet}, "
            f"nhiet_do_chuan_chiet_suat_C={T_ngan_sach}"
        ),
    ]
    _ghi_csv_co_chu_thich(ngan_sach_csv, df_ns, chu_thich_ns)

    # 5. Bảng tham số còn là giả định / chưa xác nhận (R7)
    trang_thai_r7 = liet_ke_tham_so_chua_xac_nhan(cfg_path, xac_nhan_quan_fry_path=xac_nhan_quan_fry_path)
    df_r7 = pd.DataFrame(trang_thai_r7["danh_sach"])
    gia_dinh_csv = out_path / "tham_so_gia_dinh.csv"
    _ghi_csv_co_chu_thich(
        gia_dinh_csv,
        df_r7,
        [f"Tong so tham so chua xac nhan trong config.yaml: {trang_thai_r7['so_tham_so_chua_xac_nhan']}"],
    )

    # 6. File Markdown tổng hợp cho báo cáo / poster (không tự khẳng định độ chính xác thiết bị)
    md_lines: list[str] = ["# TỔNG HỢP SỐ LIỆU ĐẦU VÀO CHO BÁO CÁO & POSTER KHKT", ""]
    if chua_xac_nhan_hc or chua_xac_nhan_ba:
        md_lines.extend([f"> **CẢNH BÁO BẮT BUỘC: {BANNER_MO_PHONG}**", ""])

    so_bs_tk = int(kq_thiet_ke.get("tom_tat", {}).get("so_dong_ban_sao", 0))
    if bc.co_ban_sao_du_lieu or so_bs_tk > 0:
        n_bs_in = max(int(bc.so_dong_ban_sao), so_bs_tk)
        cb_bs_txt = next(
            (c["noi_dung"] for c in bc.canh_bao_chi_tiet if c.get("ma") == "DU_LIEU_CO_BAN_SAO"),
            f"Phát hiện {n_bs_in} dòng bản sao trong dữ liệu hiệu chuẩn.",
        )
        md_lines.extend([
            "## Cảnh báo dữ liệu trùng lặp",
            "",
            f"> **NGHIÊM TRỌNG (`DU_LIEU_CO_BAN_SAO`):** {cb_bs_txt}",
            "",
        ])

    md_lines.extend([
        "## 1. Tóm tắt mô hình đường chuẩn từ dữ liệu đầu vào",
        "",
        f"- Nguồn dữ liệu hiệu chuẩn: `{mh.nguon_du_lieu}` (số điểm dùng khớp: `{mh.so_diem}`, train: `{len(bc.df_train)}`, test: `{len(bc.df_test)}`)",
        f"- Dòng bản sao đã loại khi khớp: `{bc.so_dong_loai}` | Dòng dùng khớp: `{bc.so_dong_dung}`"
        + (f" | Đã loại thủ công: `{bc.so_dong_da_loai_thu_cong}` lần đo (lí do: {'; '.join(dict.fromkeys(bc.tom_tat_ly_do_loai)) or 'không ghi'})" if bc.so_dong_da_loai_thu_cong > 0 else ""),
        f"- Bậc đa thức chọn: `{bc.bac_chon}` (`don_vi_y = {getattr(mh, 'don_vi_y', 'px')}`)",
        f"- Hệ số xác định `R²`: `{mh.R2:.6f}` | `s_res`: `{mh.s_res_px:.4f} {getattr(mh, 'don_vi_y', 'px')}`",
        (
            f"- Trên tập test đầu vào: `RMSE_test_px = {bc.RMSE_test_px:.4f} px`, `RMSE_test_ppt = {bc.RMSE_test_ppt:.4f} ‰`"
            if math.isfinite(bc.RMSE_test_px)
            else "- Tập kiểm tra tách riêng không đủ điểm."
        ),
        "",
        "![Đồ thị đường chuẩn và phần dư](duong_chuan_va_phan_du.png)",
        "",
        "## 2. Thống kê theo từng mức độ mặn (từ dữ liệu đầu vào)",
        "",
    ])
    if chua_xac_nhan_hc:
        md_lines.extend([f"**[{BANNER_MO_PHONG}]**", ""])
    md_lines.extend([_df_to_markdown_table(df_muc), ""])

    if ba_info is not None:
        md_lines.extend([
            "## 3. So sánh Bland–Altman với khúc xạ kế (từ dữ liệu cặp đo đầu vào)",
            "",
        ])
        if chua_xac_nhan_ba:
            md_lines.extend([f"**[{BANNER_MO_PHONG}]**", ""])
        md_lines.extend([
            f"- Số cặp hợp lệ: `{ba_info['n_pair']}`",
            f"- Độ lệch trung bình (Bias): `{ba_info['bias']:+.4f} ‰` | Độ lệch chuẩn hiệu: `{ba_info['sd']:.4f} ‰`",
            f"- Giới hạn đồng thuận 95% (LoA = Bias ± 1.96·SD): `[{ba_info['loa_duoi']:+.4f}, {ba_info['loa_tren']:+.4f}] ‰` | Tương quan `r = {ba_info['r_corr']:.4f}`",
            "",
            "![Đồ thị Bland–Altman](bland_altman.png)",
            "",
        ])

    md_lines.extend([
        "## 4. Phân tích độ nhạy (ngân sách sai số theo giả định trong `config.yaml`)",
        "",
        f"Giả định đầu vào từ `{cfg_path.name}` (khác với bất định đo thực nghiệm): "
        f"`sai_so_tim_tam_px={sai_so_tam}`, `lech_nhiet_do_hai_ngan_C={lech_t}`, "
        f"`sai_so_goc_A_do={sai_a}`, `troi_laser_chung_px={troi}`, `he_so_triet_chung={triet}`, "
        f"`nhiet_do_chuan_chiet_suat_C={T_ngan_sach}`.",
        "",
        _df_to_markdown_table(df_ns),
        "",
        "## 5. Danh sách tham số giả định / chưa xác nhận (`config.yaml`)",
        "",
        f"Hiện còn **{trang_thai_r7['so_tham_so_chua_xac_nhan']}** mục chưa xác nhận (chi tiết xem [tham_so_gia_dinh.csv](tham_so_gia_dinh.csv)).",
        "",
        _df_to_markdown_table(df_r7),
        "",
    ])

    thiet_ke_csv = out_path / "kiem_tra_thiet_ke.csv"
    df_tk = pd.DataFrame(kq_thiet_ke["muc_kiem"])
    df_tk.to_csv(thiet_ke_csv, index=False, encoding="utf-8-sig")

    md_lines.extend([
        "## 6. Kiểm tra thiết kế thí nghiệm hiệu chuẩn",
        "",
        f"- Kết luận tổng quát (chỉ khuyến nghị, không chặn đường chuẩn): "
        f"**{'Đạt' if kq_thiet_ke['hop_le_tong_quat'] else 'Chưa đạt'}** "
        f"(Đạt={kq_thiet_ke['so_dat']}, Chưa đạt={kq_thiet_ke['so_chua_dat']}, Cảnh báo={kq_thiet_ke['so_canh_bao']}).",
        "- Chi tiết từng hạng mục xem [kiem_tra_thiet_ke.csv](kiem_tra_thiet_ke.csv).",
        "",
        _df_to_markdown_table(df_tk),
        "",
    ])

    md_path = out_path / "tong_hop_bao_cao.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    return {
        "out_dir": out_path,
        "chua_xac_nhan_hc": chua_xac_nhan_hc,
        "chua_xac_nhan_ba": chua_xac_nhan_ba,
        "fig_duong_chuan": fig_hc,
        "fig_bland_altman": fig_ba,
        "duong_chuan_png": duong_chuan_png,
        "bang_sai_so_theo_muc_csv": bang_muc_csv,
        "bland_altman_png": bland_png,
        "bang_bland_altman_csv": bland_csv,
        "ngan_sach_sai_so_csv": ngan_sach_csv,
        "tham_so_gia_dinh_csv": gia_dinh_csv,
        "kiem_tra_thiet_ke_csv": thiet_ke_csv,
        "kiem_tra_thiet_ke": kq_thiet_ke,
        "tong_hop_bao_cao_md": md_path,
    }


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Xuất tài liệu báo cáo và poster vào outputs/bao_cao.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--csv", help="File CSV hiệu chuẩn đầu vào.")
    group.add_argument("--mo-phong", action="store_true", help="Chạy trên dữ liệu mô phỏng Snell.")
    parser.add_argument("--so-sanh", default=None, help="File CSV so sánh với khúc xạ kế (S_thiet_bi, S_khuc_xa_ke, [nguon_du_lieu]).")
    parser.add_argument("--out-dir", default=str(ROOT / "outputs" / "bao_cao"), help="Thư mục lưu đầu ra.")
    parser.add_argument("--don-vi-y", choices=("px", "mm"), default="px", help="Đơn vị trục tung của đường chuẩn.")
    parser.add_argument("--config", default=str(ROOT / "config.yaml"), help="Đường dẫn file cấu hình config.yaml.")
    args = parser.parse_args(argv)

    kq = xuat_bo_bao_cao(
        csv_hieu_chuan=args.csv,
        mo_phong=args.mo_phong,
        csv_so_sanh=args.so_sanh,
        out_dir=args.out_dir,
        don_vi_y=args.don_vi_y,
        config_path=args.config,
    )
    print(f"Đã xuất tài liệu báo cáo vào: {kq['out_dir']}")
    if kq["chua_xac_nhan_hc"] or kq["chua_xac_nhan_ba"]:
        print(f"CẢNH BÁO: Đã đóng dấu '{BANNER_MO_PHONG}' lên hình/bảng.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
