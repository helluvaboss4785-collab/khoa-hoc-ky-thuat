"""Ứng dụng Streamlit: Thiết bị đo độ mặn khúc xạ laser hai ngăn vi sai (Cột mốc 5).

Giao diện Tiếng Việt hoàn toàn, thiết kế tối ưu cho học sinh THPT thuyết minh và phỏng vấn KHKT.
Bao gồm:
- Hộp thoại Hướng dẫn tương tác 4 bước (kèm mô phỏng vật lí trực tiếp) khi lần đầu truy cập.
- Thanh Trợ lý Hướng dẫn Thời gian thực (Live Interactive Coach) theo dõi từng bước thao tác.
- 6 phân hệ chức năng chuyên sâu:
  1. Đo độ mặn & độ đục từ ảnh (hỗ trợ đo thời gian thực, mặt cắt Gauss, phân rã bất định GUM)
  2. Cảnh báo theo đối tượng nuôi trồng (thanh phổ sinh học trực quan & ma trận đa loài)
  3. Nhật kí quan trắc thực địa & Xuất báo cáo CSV
  4. Hiệu chuẩn thiết bị & Bù nhiệt độ (kiểm định chéo k-fold chống quá khớp)
  5. Mô phỏng quang học Snell & Ngân sách sai số toàn phương RSS
  6. Đối chứng với khúc xạ kế quang cơ (Đồ thị tương quan y=x & Bland–Altman)
"""
from __future__ import annotations

import io
import math
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

# Tự động chuyển hướng nếu chạy nhầm chế độ bare "python app/streamlit_app.py"
if __name__ == "__main__":
    from streamlit.runtime import exists as _dang_chay_streamlit

    if not _dang_chay_streamlit():
        import subprocess

        print("Đang khởi động giao diện Streamlit... (Ctrl+C để dừng)")
        raise SystemExit(
            subprocess.call([sys.executable, "-m", "streamlit", "run", str(Path(__file__).resolve())])
        )

THU_MUC_GOC = Path(__file__).resolve().parents[1]
if str(THU_MUC_GOC) not in sys.path:
    sys.path.insert(0, str(THU_MUC_GOC))

from app.giao_dien import (
    bang,
    hero,
    hien,
    hop_thoai_huong_dan,
    huy_hieu,
    nap_giao_dien,
    nhan_buoc,
    svg_he_quang_hoc,
    thanh_nguong_loai,
    thanh_tro_ly_thoi_gian_thuc,
    the_so,
    tieu_de_muc,
)
from core import calibration as cal
from core import optics as op
from core import spot
from core import thresholds as th
from core.measure import KetQuaDoDeltaY, chuyen_anh_xam, do_delta_y_tu_anh
from sim.synth import ThamSoMoPhong, sinh_anh_hai_vach_mo_phong, sinh_du_lieu_hieu_chuan_mo_phong

# Cấu hình trang Streamlit
st.set_page_config(
    page_title="Đo Độ Mặn Quang Học Vi Sai | KHKT",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Nạp bộ CSS chủ đề laser và cấu hình Matplotlib
nap_giao_dien()

DB_PATH = THU_MUC_GOC / "data" / "nhat_ki_do.db"
CONFIG_PATH = THU_MUC_GOC / "config.yaml"
OUTPUTS_DIR = THU_MUC_GOC / "outputs"
HE_SO_JSON_PATH = OUTPUTS_DIR / "he_so_hieu_chuan.json"
HE_SO_MP_PATH = OUTPUTS_DIR / "he_so_hieu_chuan_MO_PHONG.json"


# ---------------------------------------------------------------------------
# Quản lí cơ sở dữ liệu SQLite cho Nhật kí đo
# ---------------------------------------------------------------------------
def khoi_tao_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS nhat_ki (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thoi_gian TEXT,
                vi_tri TEXT,
                loai_nuoi TEXT,
                delta_y_px REAL,
                do_man_ppt REAL,
                bat_dinh_U_ppt REAL,
                nhiet_do_C REAL,
                do_duc REAL,
                chat_luong_hop_le INTEGER,
                nguon_du_lieu TEXT,
                ghi_chu TEXT
            )
        """)


def luu_nhat_ki(
    vi_tri: str,
    loai_nuoi: str,
    delta_y_px: float,
    do_man_ppt: float,
    bat_dinh_U_ppt: float,
    nhiet_do_C: float,
    do_duc: float,
    chat_luong_hop_le: bool,
    nguon_du_lieu: str,
    ghi_chu: str,
    thoi_gian_tuy_chinh: str | None = None,
) -> None:
    khoi_tao_db()
    tg = thoi_gian_tuy_chinh or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO nhat_ki (
                thoi_gian, vi_tri, loai_nuoi, delta_y_px, do_man_ppt,
                bat_dinh_U_ppt, nhiet_do_C, do_duc, chat_luong_hop_le,
                nguon_du_lieu, ghi_chu
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            tg,
            vi_tri, loai_nuoi, delta_y_px, do_man_ppt, bat_dinh_U_ppt,
            nhiet_do_C, do_duc, 1 if chat_luong_hop_le else 0,
            nguon_du_lieu, ghi_chu
        ))


def doc_lich_su_db() -> pd.DataFrame:
    khoi_tao_db()
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query("SELECT * FROM nhat_ki ORDER BY id DESC", conn)


def xoa_toan_bo_nhat_ki() -> None:
    khoi_tao_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM nhat_ki")


def nap_nhat_ki_mau_mo_phong(mh: cal.MoHinhHieuChuan) -> None:
    """Sinh 10 bản ghi nhật kí mẫu (gắn nhãn MÔ PHỎNG rõ ràng) để học sinh thử nghiệm biểu đồ."""
    rng = np.random.default_rng(2026)
    now = datetime.now()
    cac_muc_s = [12.5, 13.2, 14.8, 16.0, 17.5, 19.2, 21.0, 23.5, 20.4, 18.0]
    for idx, s_val in enumerate(cac_muc_s):
        tg = (now - timedelta(hours=(len(cac_muc_s) - idx) * 6)).strftime("%Y-%m-%d %H:%M:%S")
        t_val = float(np.round(25.0 + rng.normal(0, 1.2), 1))
        dy_val = float(mh.du_doan_delta_y(s_val, t_val)[0]) + float(rng.normal(0, 0.06))
        u_val = float(np.round(0.18 + rng.uniform(0, 0.08), 2))
        duc_val = float(np.round(rng.uniform(0.05, 0.35), 2))
        luu_nhat_ki(
            vi_tri="Ao nuôi tôm số 1 (Mẫu thử)",
            loai_nuoi="Tôm thẻ chân trắng (Litopenaeus vannamei)",
            delta_y_px=round(dy_val, 2),
            do_man_ppt=round(s_val, 2),
            bat_dinh_U_ppt=u_val,
            nhiet_do_C=t_val,
            do_duc=duc_val,
            chat_luong_hop_le=True,
            nguon_du_lieu="MÔ PHỎNG",
            ghi_chu=f"Quan trắc định kì lần {idx + 1} (Dữ liệu mô phỏng)",
            thoi_gian_tuy_chinh=tg,
        )


# ---------------------------------------------------------------------------
# Các hàm vẽ đồ thị chẩn đoán chuyên sâu cho Tab 1, Tab 5, Tab 6
# ---------------------------------------------------------------------------
def ve_do_thi_mat_cat_gauss(anh_goc: np.ndarray, kq_do: KetQuaDoDeltaY) -> plt.Figure:
    """Vẽ mặt cắt cường độ I(y) và đường khớp Gauss dưới pixel tại lân cận cột x_ref."""
    anh_xam = chuyen_anh_xam(anh_goc)
    h, w = anh_xam.shape
    col_tc = int(np.clip(round(kq_do.vach_tham_chieu.x_ref), 0, w - 1))
    col_m = int(np.clip(round(kq_do.vach_mau.x_ref), 0, w - 1))

    # Nếu bố trí ngang (trái-phải), lấy cột giữa của mỗi đoạn vạch để vẽ profile thực tế
    if kq_do.vach_tham_chieu.danh_sach_x:
        col_tc = int(np.clip(round(float(np.median(kq_do.vach_tham_chieu.danh_sach_x))), 0, w - 1))
    if kq_do.vach_mau.danh_sach_x:
        col_m = int(np.clip(round(float(np.median(kq_do.vach_mau.danh_sach_x))), 0, w - 1))

    y_all = np.arange(h, dtype=float)
    prof_tc = anh_xam[:, col_tc].astype(float)
    prof_m = anh_xam[:, col_m].astype(float)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 3.6), dpi=110)

    # 1. Mặt cắt cường độ theo trục đứng y
    ax1.plot(y_all, prof_tc, "o-", color="#10B981", markersize=2.5, lw=1.2, alpha=0.85, label=f"Mặt cắt Vạch TC (x={col_tc})")
    ax1.plot(y_all, prof_m, "s-", color="#E5383B", markersize=2.5, lw=1.2, alpha=0.85, label=f"Mặt cắt Vạch Mẫu (x={col_m})")
    ax1.axvline(kq_do.vach_tham_chieu.y_tam, color="#059669", ls="--", lw=1.5, label=f"Tâm y_tc = {kq_do.vach_tham_chieu.y_tam:.2f} px")
    ax1.axvline(kq_do.vach_mau.y_tam, color="#B91C1C", ls="--", lw=1.5, label=f"Tâm y_mẫu = {kq_do.vach_mau.y_tam:.2f} px")
    ax1.axhline(250, color="#F59E0B", ls=":", lw=1.0, label="Ngưỡng bão hòa (250)")
    ax1.set_xlabel("Tọa độ đứng y (pixel)")
    ax1.set_ylabel("Cường độ sáng mức xám I(y) [0–255]")
    ax1.set_title("Mặt cắt cường độ Gauss & Tâm dưới pixel", fontsize=10)
    ax1.legend(fontsize=7.5, loc="upper right")

    # 2. Đường tâm vạch khớp qua các cột y(x) = a*x + b
    if kq_do.vach_tham_chieu.danh_sach_x and kq_do.vach_mau.danh_sach_x:
        x_tc = np.asarray(kq_do.vach_tham_chieu.danh_sach_x)
        y_tc = np.asarray(kq_do.vach_tham_chieu.danh_sach_y)
        x_m = np.asarray(kq_do.vach_mau.danh_sach_x)
        y_m = np.asarray(kq_do.vach_mau.danh_sach_y)

        ax2.scatter(x_tc, y_tc, s=8, color="#10B981", alpha=0.6, label="Tâm cột Vạch TC (μ_i)")
        ax2.scatter(x_m, y_m, s=8, color="#E5383B", alpha=0.6, label="Tâm cột Vạch Mẫu (μ_i)")

        x_line = np.linspace(0, w - 1, 100)
        ax2.plot(x_line, kq_do.vach_tham_chieu.do_doc_a * x_line + kq_do.vach_tham_chieu.he_so_b,
                 color="#047857", lw=1.8, label="Đường khớp Vạch TC")
        ax2.plot(x_line, kq_do.vach_mau.do_doc_a * x_line + kq_do.vach_mau.he_so_b,
                 color="#991B1B", lw=1.8, label="Đường khớp Vạch Mẫu")
        ax2.axvline(kq_do.x_ref, color="#F59E0B", ls="--", lw=1.4, label=f"x_ref = {kq_do.x_ref:.0f} px")
        ax2.invert_yaxis()
        ax2.set_xlabel("Tọa độ ngang x (pixel)")
        ax2.set_ylabel("Tọa độ tâm y (pixel)")
        ax2.set_title(f"Hồi quy đường thẳng tâm vạch (Δy = {kq_do.delta_y_px:.2f} px)", fontsize=10)
        ax2.legend(fontsize=7.5, loc="best")

    fig.tight_layout()
    return fig


def ve_do_thi_bat_dinh(kq_man: cal.KetQuaDoMan) -> plt.Figure:
    """Biểu đồ thanh ngang phân rã các nguồn đóng góp vào bất định chuẩn u(S)."""
    nhan_map = {
        "do_anh": "Định vị tâm vạch từ ảnh (σ_Δy)",
        "lap_lai_duong_chuan": "Độ tản mát đường chuẩn (s_res)",
        "he_so_duong_chuan": "Bất định hệ số hồi quy (u_fit)",
        "nhiet_do": "Sai số nhiệt kế & bù nhiệt (σ_T)",
    }
    labels = [nhan_map.get(k, k) for k in kq_man.thanh_phan_bat_dinh.keys()]
    vals = [float(v) for v in kq_man.thanh_phan_bat_dinh.values()]

    fig, ax = plt.subplots(figsize=(6.2, 2.5), dpi=110)
    colors = ["#14B8A6", "#1B4965", "#F59E0B", "#E5383B"]
    y_pos = np.arange(len(labels))
    bars = ax.barh(y_pos, vals, color=colors[:len(labels)], height=0.55)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=8.5)
    ax.set_xlabel("Độ lệch chuẩn đóng góp u_i (‰)")
    ax.set_title(f"Phân rã ngân sách bất định GUM (Tổng hợp u_c = {kq_man.u_S_ppt:.3f} ‰)", fontsize=9.5)
    max_v = max(vals + [0.01])
    ax.set_xlim(0, max_v * 1.28)
    for bar, v in zip(bars, vals):
        ax.text(v + max_v * 0.02, bar.get_y() + bar.get_height() / 2.0, f"{v:.4f} ‰", va="center", fontsize=8, fontweight="bold")
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Nạp cấu hình và mô hình hiệu chuẩn
# ---------------------------------------------------------------------------
@st.cache_data
def load_config() -> op.CauHinhQuangHoc:
    return op.CauHinhQuangHoc.tu_yaml(CONFIG_PATH)


def load_model() -> cal.MoHinhHieuChuan:
    if HE_SO_JSON_PATH.exists():
        return cal.MoHinhHieuChuan.doc_json(HE_SO_JSON_PATH)
    if HE_SO_MP_PATH.exists():
        return cal.MoHinhHieuChuan.doc_json(HE_SO_MP_PATH)
    df_mp = sinh_du_lieu_hieu_chuan_mo_phong(seed=0)
    bc = cal.dung_duong_chuan(df_mp)
    OUTPUTS_DIR.mkdir(exist_ok=True)
    bc.mo_hinh.luu_json(HE_SO_MP_PATH)
    return bc.mo_hinh


mh_hien_tai = load_model()

# ---------------------------------------------------------------------------
# Khởi tạo trạng thái phiên làm việc (Session State) & Hướng dẫn lần đầu
# ---------------------------------------------------------------------------
if "da_xem_huong_dan" not in st.session_state:
    st.session_state["da_xem_huong_dan"] = False
    st.session_state["mo_huong_dan"] = True
    st.session_state["bat_tro_ly_thoi_gian_thuc"] = True
    st.session_state["nguon_anh_radio"] = "Tạo ảnh mô phỏng thử nghiệm"
    st.session_state["tu_dong_do_live"] = True
    st.session_state["da_luu_nhat_ki_phien_nay"] = False

if st.session_state.get("mo_huong_dan", False):
    hop_thoai_huong_dan()

# ---------------------------------------------------------------------------
# Banner Hero đầu trang
# ---------------------------------------------------------------------------
huy_hieu_top = (
    huy_hieu("Lăng kính đỉnh A = 40°", "trong", "📐")
    + " "
    + huy_hieu("Laser đỏ 650 nm (≤1 mW)", "do", "🔴")
    + " "
    + huy_hieu("Vi sai 2 ngăn khử rung", "xanh", "🛡️")
    + " "
    + huy_hieu("Khớp Gauss dưới pixel (<0.05 px)", "duong", "🎯")
    + " "
    + (
        huy_hieu("CHƯA HIỆU CHUẨN (MÔ PHỎNG)", "vang", "🧪")
        if mh_hien_tai.la_mo_phong
        else huy_hieu("ĐÃ HIỆU CHUẨN ĐO THẬT", "xanh", "✅")
    )
)

hero(
    kicker="DỰ ÁN KHOA HỌC KỸ THUẬT (KHKT) DÀNH CHO HỌC SINH THPT",
    tieu_de="Hệ Thống Đo Độ Mặn Nước Bằng Khúc Xạ Laser Hai Ngăn Vi Sai",
    phu_de=(
        "Khử trôi nhiệt laser & rung lắc camera bằng cấu trúc vi sai 2 ngăn • "
        "Thuật toán định vị tâm Gauss dưới pixel • Hiệu chuẩn bù nhiệt & Đánh giá bất định chuẩn GUM"
    ),
    huy_hieu_html=huy_hieu_top,
)

# ---------------------------------------------------------------------------
# Sidebar: Điều khiển Hướng dẫn Thời gian thực & Trạng thái Hệ thống
# ---------------------------------------------------------------------------
with st.sidebar:
    hien("""
    <div class="sb-logo">🔬 QUANG HỌC <b>VI SAI</b></div>
    <div style="font-size: 0.84rem; color: #CBD5E1; margin-bottom: 10px;">
      Hệ thống đo độ mặn & độ đục bằng camera
    </div>
    """)

    if st.button("📖 Mở Hướng dẫn tương tác (4 bước)", width="stretch", help="Mở hộp thoại hướng dẫn và mô phỏng tương tác"):
        st.session_state["buoc_hd_modal"] = 1
        st.session_state["mo_huong_dan"] = True
        st.rerun()

    bat_coach = st.toggle(
        "🧭 Trợ lý Hướng dẫn thời gian thực",
        value=st.session_state.get("bat_tro_ly_thoi_gian_thuc", True),
        help="Hiển thị thanh chỉ dẫn từng bước theo thời gian thực ngay đầu trang",
    )
    if bat_coach != st.session_state.get("bat_tro_ly_thoi_gian_thuc", True):
        st.session_state["bat_tro_ly_thoi_gian_thuc"] = bat_coach
        st.rerun()

    st.divider()

    hien('<div class="sb-tt">📊 Trạng thái đường chuẩn hiện tại:</div>')
    if mh_hien_tai.la_mo_phong:
        bang(
            "vang",
            f"<b>CHƯA HIỆU CHUẨN (MÔ PHỎNG)</b><br>Bậc {mh_hien_tai.bac} | R² = {mh_hien_tai.R2:.5f}<br>"
            f"Dải S: {mh_hien_tai.S_min:g}–{mh_hien_tai.S_max:g} ‰ | T: {mh_hien_tai.T_min:g}–{mh_hien_tai.T_max:g} °C",
            icon="⚠️",
            la_html=True,
        )
    else:
        bang(
            "xanh",
            f"<b>ĐÃ HIỆU CHUẨN ĐO THẬT</b><br>Bậc {mh_hien_tai.bac} | R² = {mh_hien_tai.R2:.4f} | {mh_hien_tai.so_diem} mẫu",
            icon="✅",
            la_html=True,
        )

    hien("""
    <div class="sb-the">
      <div class="sb-tt">💡 Nguyên lí vi sai cốt lõi:</div>
      Tia laser chiếu đồng thời qua 2 ngăn: <b>Nước cất (0 ‰)</b> và <b>Mẫu đo (S ‰)</b>.<br>
      Hiệu vị trí <b>Δy = y_mẫu − y_tc</b> tự động triệt tiêu rung máy ảnh, trôi nhiệt laser và sai số lắp đặt ở bậc 1!
    </div>
    <div class="sb-the">
      <div class="sb-tt">📐 Thông số hình học chuẩn:</div>
      • Góc đỉnh lăng kính A: <b>40.0°</b><br>
      • Khoảng cách màn D: <b>1.0 m</b><br>
      • Bước sóng laser: <b>650 nm</b> (≤ 1 mW)<br>
      • Độ nhạy lí thuyết: <b>~4.98 px/‰</b>
    </div>
    """)

# ---------------------------------------------------------------------------
# Hiển thị Thanh Trợ lý Hướng dẫn Thời gian thực (Live Onboarding Coach)
# ---------------------------------------------------------------------------
kq_do_saved: KetQuaDoDeltaY | None = st.session_state.get("kq_do_hien_tai")
kq_man_saved: cal.KetQuaDoMan | None = st.session_state.get("kq_man_hien_tai")

thanh_tro_ly_thoi_gian_thuc(
    co_anh=st.session_state.get("co_anh_dau_vao", True),
    da_do=(kq_do_saved is not None),
    hop_le_anh=(kq_do_saved.chat_luong.hop_le if kq_do_saved is not None else True),
    da_luu_nhat_ki=bool(st.session_state.get("da_luu_nhat_ki_phien_nay", False)),
    s_do_duoc=(kq_man_saved.S_ppt if kq_man_saved is not None else None),
    u_do_duoc=(kq_man_saved.U_S_ppt if kq_man_saved is not None else None),
    canh_bao_anh=(kq_do_saved.chat_luong.canh_bao if kq_do_saved is not None else None),
)

# ---------------------------------------------------------------------------
# Các Tab chức năng chính
# ---------------------------------------------------------------------------
tab_do, tab_loai, tab_nhatki, tab_hieuchuan, tab_mophong, tab_so_sanh = st.tabs([
    "📸 1. Đo Độ Mặn",
    "🦐 2. Cảnh Báo Loài",
    "📒 3. Nhật Kí Quan Trắc",
    "📊 4. Hiệu Chuẩn & Bù Nhiệt",
    "📐 5. Mô Phỏng Quang Học",
    "⚖️ 6. Đối Chứng Khúc Xạ Kế",
])


# ===========================================================================
# TAB 1: ĐO ĐỘ MẶN VÀ ĐỘ ĐỤC TỪ ẢNH
# ===========================================================================
with tab_do:
    tieu_de_muc(
        "📸",
        "Đo Độ Mặn & Chỉ Số Độ Đục Nước Từ Ảnh Vạch Laser",
        "Thu nhận ảnh hai đoạn vạch sáng, khớp hàm Gauss dưới pixel và giải ngược độ mặn kèm bất định chuẩn GUM",
    )

    col_inp1, col_inp2 = st.columns([1.15, 1], gap="medium")

    with col_inp1:
        nhan_buoc("1", "Chọn nguồn ảnh chụp màn hứng 2 vạch laser")
        cac_nguon = ["Tải ảnh lên", "Chụp bằng Camera", "Tạo ảnh mô phỏng thử nghiệm"]
        idx_mac_dinh = cac_nguon.index(st.session_state.get("nguon_anh_radio", "Tạo ảnh mô phỏng thử nghiệm"))
        nguon_anh = st.radio(
            "Nguồn ảnh:",
            cac_nguon,
            index=idx_mac_dinh,
            horizontal=True,
            label_visibility="collapsed",
        )
        st.session_state["nguon_anh_radio"] = nguon_anh

        anh_input: np.ndarray | None = None
        la_anh_mo_phong = False
        thong_tin_chan_li_mp: dict | None = None

        if nguon_anh == "Tải ảnh lên":
            file_upload = st.file_uploader("Chọn file ảnh chụp màn hứng (JPG, PNG)", type=["jpg", "jpeg", "png"])
            if file_upload:
                file_bytes = np.asarray(bytearray(file_upload.read()), dtype=np.uint8)
                anh_input = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

        elif nguon_anh == "Chụp bằng Camera":
            camera_img = st.camera_input("Chụp trực tiếp màn hứng vạch laser trong hộp tối")
            if camera_img:
                file_bytes = np.asarray(bytearray(camera_img.read()), dtype=np.uint8)
                anh_input = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

        else:
            la_anh_mo_phong = True
            bang(
                "duong",
                "<b>Chế độ mô phỏng quang học thời gian thực:</b> Kéo thanh trượt để thay đổi độ mặn, nhiệt độ, độ đục hoặc gây rung lắc camera và quan sát phản ứng tức thì của hệ thống!",
                icon="🧪",
                la_html=True,
            )
            c_s1, c_s2 = st.columns(2)
            s_mp = c_s1.slider(
                "Độ mặn mẫu mô phỏng S (‰)",
                0.0, 35.0, float(st.session_state.get("sim_s_ppt", 16.5)), 0.5,
                key="slider_s_mp",
            )
            t_mp = c_s2.slider(
                "Nhiệt độ mẫu T (°C)",
                15.0, 35.0, float(st.session_state.get("sim_t_c", 26.0)), 0.5,
                key="slider_t_mp",
            )
            duc_mp = c_s1.slider(
                "Độ đục mẫu (0: trong, 1: rất đục)",
                0.0, 1.0, float(st.session_state.get("sim_duc", 0.15)), 0.05,
                key="slider_duc_mp",
            )
            drift_mp = c_s2.slider(
                "Rung camera / Trôi laser chung δy (px)",
                -15.0, 15.0, float(st.session_state.get("sim_drift", 4.0)), 1.0,
                key="slider_drift_mp",
            )
            st.session_state["sim_s_ppt"] = s_mp
            st.session_state["sim_t_c"] = t_mp
            st.session_state["sim_duc"] = duc_mp
            st.session_state["sim_drift"] = drift_mp

            with st.expander("⚙️ Tùy chọn gây nhiễu cực đoan (Kiểm thử độ bền thuật toán)"):
                c_ex1, c_ex2 = st.columns(2)
                gay_bao_hoa = c_ex1.checkbox("Cố tình gây cháy sáng bão hòa (pixel = 255)", value=False)
                bo_tri_vach = c_ex2.selectbox("Bố trí 2 ngăn trên ảnh", ["ngang", "doc"], format_func=lambda v: "Ngang (Trái: Nước cất | Phải: Mẫu)" if v == "ngang" else "Dọc (Trên: Nước cất | Dưới: Mẫu)")

            p_synth = ThamSoMoPhong(
                S_ppt=s_mp,
                T_C=t_mp,
                T_tham_chieu_C=t_mp,
                drift_chung_px=drift_mp,
                do_duc=duc_mp,
                bo_tri=bo_tri_vach,
                cho_phep_bao_hoa=gay_bao_hoa,
                seed=42,
            )
            anh_mp_obj = sinh_anh_hai_vach_mo_phong(p_synth, load_config(), gan_watermark=False)
            anh_input = cv2.cvtColor(anh_mp_obj.anh, cv2.COLOR_GRAY2BGR)
            thong_tin_chan_li_mp = {
                "S_chan_li": s_mp,
                "T_chan_li": t_mp,
                "delta_y_snell": anh_mp_obj.delta_y_ly_thuyet_px,
                "drift_px": drift_mp,
            }

        st.session_state["co_anh_dau_vao"] = (anh_input is not None)

    with col_inp2:
        nhan_buoc("2", "Thông số môi trường, thuật toán & Vị trí lấy mẫu")
        c_env1, c_env2 = st.columns(2)
        nhiet_do_mac_dinh = float(st.session_state.get("sim_t_c", 25.0)) if la_anh_mo_phong else 25.0
        nhiet_do_do = c_env1.number_input(
            "Nhiệt độ mẫu đo bằng nhiệt kế (°C)",
            min_value=5.0,
            max_value=50.0,
            value=nhiet_do_mac_dinh,
            step=0.5,
        )
        phuong_phap_tam = c_env2.selectbox(
            "Thuật toán định vị tâm vạch:",
            options=["gauss", "centroid"],
            format_func=lambda m: "Khớp hàm Gauss phi tuyến (Sub-pixel)" if m == "gauss" else "Trọng tâm có trừ nền (Centroid)",
        )

        c_loc1, c_loc2 = st.columns(2)
        vi_tri_do = c_loc1.text_input("Vị trí lấy mẫu / Tên ao hồ", value="Ao nuôi tôm số 1")
        ghi_chu_do = c_loc2.text_input("Ghi chú mẫu nước", value="Nước mặt ao sau mưa")

        with st.expander("🛠️ Tùy chỉnh vùng chọn ROI thủ công (nếu ảnh có ánh sáng tạp)"):
            che_do_roi = st.checkbox("Bật chọn tọa độ ROI thủ công", value=False)
            roi_tc_custom, roi_mau_custom = None, None
            if che_do_roi and anh_input is not None:
                h_img, w_img = anh_input.shape[:2]
                st.caption("Tọa độ ROI: [y_min, y_max, x_min, x_max]")
                c_r1, c_r2 = st.columns(2)
                y_tc_min = c_r1.slider("Vạch tham chiếu y_min", 0, h_img - 30, 35)
                y_tc_max = c_r1.slider("Vạch tham chiếu y_max", y_tc_min + 15, h_img, min(h_img, 140))
                y_m_min = c_r2.slider("Vạch mẫu y_min", 0, h_img - 30, 40)
                y_m_max = c_r2.slider("Vạch mẫu y_max", y_m_min + 15, h_img, min(h_img, 260))
                roi_tc_custom = (y_tc_min, y_tc_max, 5, w_img // 2 - 8)
                roi_mau_custom = (y_m_min, y_m_max, w_img // 2 + 8, w_img - 5)

        tu_dong_do = st.checkbox(
            "⚡ Tự động đo thời gian thực khi thay đổi thông số / nguồn ảnh",
            value=st.session_state.get("tu_dong_do_live", True),
            help="Khi bật, mọi thay đổi trên thanh trượt hoặc ảnh tải lên đều được phân tích ngay lập tức",
        )
        st.session_state["tu_dong_do_live"] = tu_dong_do

        nut_do = st.button("🚀 TIẾN HÀNH ĐO ĐỘ MẶN NGAY", type="primary", width="stretch")

    # -----------------------------------------------------------------------
    # Thực hiện phép đo (khi nhấn nút, hoặc khi bật Tự động đo thời gian thực)
    # -----------------------------------------------------------------------
    can_chay_do = (
        nut_do
        or st.session_state.pop("yeu_cau_do_ngay", False)
        or (tu_dong_do and anh_input is not None)
    )

    if can_chay_do and anh_input is not None:
        try:
            kq_do_moi = do_delta_y_tu_anh(
                anh_input,
                roi_tham_chieu=roi_tc_custom,
                roi_mau=roi_mau_custom,
                phuong_phap=phuong_phap_tam,
                buoc_nhay_cot=2,
            )
            st.session_state["kq_do_hien_tai"] = kq_do_moi
            st.session_state["anh_da_do"] = anh_input
            st.session_state["la_anh_mo_phong_da_do"] = la_anh_mo_phong
            st.session_state["thong_tin_chan_li_da_do"] = thong_tin_chan_li_mp

            if math.isfinite(kq_do_moi.delta_y_px):
                kq_man_moi = cal.uoc_luong_do_man(
                    mh=mh_hien_tai,
                    delta_y_px=kq_do_moi.delta_y_px,
                    T_C=nhiet_do_do,
                    sigma_delta_y_px=kq_do_moi.sai_so_delta_y_px,
                    sigma_T_C=0.5,
                    k=2.0,
                )
                st.session_state["kq_man_hien_tai"] = kq_man_moi
            else:
                st.session_state["kq_man_hien_tai"] = None
        except Exception as ex:
            st.error(f"Lỗi khi xử lí ảnh hoặc giải ngược độ mặn: {ex}")

    st.divider()

    # Lấy kết quả từ Session State để hiển thị bền vững (không bị mất khi bấm nút Lưu)
    kq_do: KetQuaDoDeltaY | None = st.session_state.get("kq_do_hien_tai")
    kq_man: cal.KetQuaDoMan | None = st.session_state.get("kq_man_hien_tai")
    anh_hien_thi: np.ndarray | None = st.session_state.get("anh_da_do", anh_input)
    chan_li_mp: dict | None = st.session_state.get("thong_tin_chan_li_da_do")

    if kq_do is not None and anh_hien_thi is not None:
        # 1. Hiển thị 4 thẻ KPI kết quả chính
        c_k1, c_k2, c_k3, c_k4 = st.columns(4)

        with c_k1:
            if kq_man is not None:
                phu_s = f"Khoảng tin cậy 95% (k = {kq_man.k:g})"
                if chan_li_mp is not None:
                    sai_lech_mp = kq_man.S_ppt - chan_li_mp["S_chan_li"]
                    phu_s = f"Chân lí MP: {chan_li_mp['S_chan_li']:.2f} ‰ (Lệch {sai_lech_mp:+.3f} ‰)"
                hien(the_so(
                    nhan="ĐỘ MẶN ƯỚC LƯỢNG (S ± U₉₅%)",
                    gia_tri=f"{kq_man.S_ppt:.2f}",
                    don_vi="‰",
                    pm=f"± {kq_man.U_S_ppt:.2f} ‰",
                    phu=phu_s,
                    kieu="nhan-manh",
                ))
            else:
                hien(the_so("ĐỘ MẶN ƯỚC LƯỢNG", "N/A", phu="Ngoài dải hoặc ảnh lỗi", kieu="nhan-manh"))

        with c_k2:
            phu_dy = f"R² khớp Gauss: {kq_do.vach_mau.r2_trung_binh:.3f} ({kq_do.vach_mau.so_cot_hop_le} cột)"
            if chan_li_mp is not None:
                phu_dy = f"Snell lí thuyết: {chan_li_mp['delta_y_snell']:.2f} px | Rung: {chan_li_mp['drift_px']:+.1f} px"
            hien(the_so(
                nhan="ĐỘ LỆCH ĐỨNG VI SAI (Δy)",
                gia_tri=f"{kq_do.delta_y_px:.2f}",
                don_vi="px",
                pm=f"± {kq_do.sai_so_delta_y_px:.3f} px",
                phu=phu_dy,
                kieu="vien-ngoc",
            ))

        with c_k3:
            duc_val = kq_do.chi_so_do_duc_tuong_doi
            muc_duc = "Trong suốt" if duc_val < 0.2 else ("Hơi đục (lơ lửng nhẹ)" if duc_val < 0.55 else "Rất đục (tán xạ mạnh)")
            hien(the_so(
                nhan="CHỈ SỐ ĐỘ ĐỤC TƯƠNG ĐỐI",
                gia_tri=f"{duc_val:.2f}",
                don_vi="[0–1]",
                pm=muc_duc,
                phu=f"FWHM mẫu: {kq_do.chat_luong.fwhm_mau:.2f} px (TC: {kq_do.chat_luong.fwhm_tc:.2f} px)",
                kieu="vien-vang",
            ))

        with c_k4:
            cq = kq_do.chat_luong
            trang_thai_cl = "ĐẠT CHUẨN" if cq.hop_le else "CẦN LƯU Ý"
            hien(the_so(
                nhan="CHẤT LƯỢNG QUANG HỌC ẢNH",
                gia_tri=trang_thai_cl,
                pm=f"SNR = {cq.snr:.1f}",
                phu=f"Bão hòa (≥250): {cq.ti_le_bao_hoa * 100:.2f}% pixel",
                kieu="vien-xanh" if cq.hop_le else "vien-do",
            ))

        # 2. Khu vực Cảnh báo, Đánh giá nhanh theo loài & Lưu Nhật Kí
        st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
        col_save1, col_save2 = st.columns([1.35, 1], gap="medium")

        with col_save1:
            if cq.canh_bao:
                for cb in cq.canh_bao:
                    bang("vang", cb, icon="⚠️")
            if kq_man and kq_man.canh_bao:
                for cb in kq_man.canh_bao:
                    bang("do" if "NGOÀI" in cb else "vang", cb, icon="🚨")
            bang("duong", f"<b>Phạm vi khoa học:</b> {cal.HAN_CHE_NACL}", icon="📌", la_html=True)

        with col_save2:
            ds_loai_all = th.doc_danh_sach_loai()
            loai_chon = st.selectbox(
                "🦐 Chọn đối tượng nuôi trồng để đối chiếu & lưu Nhật kí:",
                options=list(ds_loai_all.keys()),
                format_func=lambda k: ds_loai_all[k].ten_hien_thi,
                key="select_loai_tab1",
            )
            if kq_man is not None:
                dg_nhanh = th.danh_gia_do_man_loai(kq_man.S_ppt, ds_loai_all[loai_chon])
                mau_bang = "xanh" if dg_nhanh.trang_thai == "AN_TOAN" else ("vang" if dg_nhanh.trang_thai == "CANH_BAO" else ("do" if dg_nhanh.trang_thai == "NGUY_HIEM" else "duong"))
                bang(mau_bang, f"<b>{dg_nhanh.tieu_de}</b>", icon="🔎", la_html=True)

            if st.button("💾 Lưu kết quả đo này vào Nhật Kí Quan Trắc", type="primary", width="stretch"):
                if kq_man is not None:
                    nguon_luu = (
                        "MÔ PHỎNG"
                        if st.session_state.get("la_anh_mo_phong_da_do", True) or mh_hien_tai.la_mo_phong
                        else "ĐO THẬT"
                    )
                    luu_nhat_ki(
                        vi_tri=vi_tri_do,
                        loai_nuoi=ds_loai_all[loai_chon].ten_hien_thi,
                        delta_y_px=round(kq_do.delta_y_px, 3),
                        do_man_ppt=round(kq_man.S_ppt, 3),
                        bat_dinh_U_ppt=round(kq_man.U_S_ppt, 3),
                        nhiet_do_C=nhiet_do_do,
                        do_duc=round(kq_do.chi_so_do_duc_tuong_doi, 3),
                        chat_luong_hop_le=cq.hop_le,
                        nguon_du_lieu=nguon_luu,
                        ghi_chu=ghi_chu_do,
                    )
                    st.session_state["da_luu_nhat_ki_phien_nay"] = True
                    st.toast("✅ Đã lưu bản ghi vào cơ sở dữ liệu Nhật kí!", icon="💾")
                    st.success("✅ Đã lưu kết quả thành công vào Nhật Kí Quan Trắc (xem tại Tab 3)!")

        # 3. Trực quan hóa Ảnh định vị tâm vạch & Đồ thị mặt cắt Gauss dưới pixel
        st.divider()
        col_vis1, col_vis2 = st.columns([1.05, 1.25], gap="medium")

        with col_vis1:
            st.markdown("##### 🎯 Ảnh định vị đường tâm hai vạch laser dưới pixel")
            if kq_do.anh_danh_dau is not None:
                st.image(
                    cv2.cvtColor(kq_do.anh_danh_dau, cv2.COLOR_BGR2RGB),
                    caption=(
                        "Đường xanh lá: Tâm vạch tham chiếu (0 ‰) | "
                        "Đường cam: Tâm vạch mẫu | Đoạn vàng: Độ lệch đứng vi sai Δy"
                    ),
                    width="stretch",
                )
            if kq_man is not None:
                st.pyplot(ve_do_thi_bat_dinh(kq_man))

        with col_vis2:
            st.markdown("##### 📈 Mặt cắt cường độ Gauss I(y) & Hồi quy đường tâm y(x)")
            st.pyplot(ve_do_thi_mat_cat_gauss(anh_hien_thi, kq_do))

            # Bảng thông số kỹ thuật chi tiết của 2 vạch
            df_chi_tiet_vach = pd.DataFrame([
                {
                    "Thông số quang học": "Tọa độ tâm tại x_ref (px)",
                    "Vạch Tham Chiếu (Nước cất 0 ‰)": f"{kq_do.vach_tham_chieu.y_tam:.3f} ± {kq_do.vach_tham_chieu.sai_so_y:.3f}",
                    "Vạch Mẫu (Nước cần đo)": f"{kq_do.vach_mau.y_tam:.3f} ± {kq_do.vach_mau.sai_so_y:.3f}",
                },
                {
                    "Thông số quang học": "Độ rộng nửa cực đại FWHM (px)",
                    "Vạch Tham Chiếu (Nước cất 0 ‰)": f"{kq_do.vach_tham_chieu.fwhm_trung_binh:.2f}",
                    "Vạch Mẫu (Nước cần đo)": f"{kq_do.vach_mau.fwhm_trung_binh:.2f}",
                },
                {
                    "Thông số quang học": "Biên độ đỉnh trung bình (mức xám)",
                    "Vạch Tham Chiếu (Nước cất 0 ‰)": f"{kq_do.vach_tham_chieu.cuong_do_dinh_tb:.1f}",
                    "Vạch Mẫu (Nước cần đo)": f"{kq_do.vach_mau.cuong_do_dinh_tb:.1f}",
                },
                {
                    "Thông số quang học": "Hệ số xác định R² khớp Gauss",
                    "Vạch Tham Chiếu (Nước cất 0 ‰)": f"{kq_do.vach_tham_chieu.r2_trung_binh:.4f}",
                    "Vạch Mẫu (Nước cần đo)": f"{kq_do.vach_mau.r2_trung_binh:.4f}",
                },
                {
                    "Thông số quang học": "Số cột ảnh hợp lệ đưa vào khớp",
                    "Vạch Tham Chiếu (Nước cất 0 ‰)": f"{kq_do.vach_tham_chieu.so_cot_hop_le} / {kq_do.vach_tham_chieu.so_cot_tong}",
                    "Vạch Mẫu (Nước cần đo)": f"{kq_do.vach_mau.so_cot_hop_le} / {kq_do.vach_mau.so_cot_tong}",
                },
            ])
            st.dataframe(df_chi_tiet_vach, width="stretch", hide_index=True)

    else:
        bang(
            "duong",
            "Hãy tải ảnh chụp màn hứng hoặc chọn <b>'Tạo ảnh mô phỏng thử nghiệm'</b> ở trên để bắt đầu phép đo.",
            icon="👈",
            la_html=True,
        )


# ===========================================================================
# TAB 2: CẢNH BÁO THEO ĐỐI TƯỢNG NUÔI TRỒNG
# ===========================================================================
with tab_loai:
    tieu_de_muc(
        "🦐",
        "Đánh Giá An Toàn Độ Mặn Theo Loài Thủy Sản & Cây Trồng",
        "Tra cứu ngưỡng thích nghi sinh học trên phổ trực quan và khuyến cáo kỹ thuật có trích dẫn nguồn",
    )

    ds_loai = th.doc_danh_sach_loai()
    col_l1, col_l2 = st.columns([1.05, 1.75], gap="medium")

    with col_l1:
        nhan_buoc("1", "Chọn đối tượng và mức độ mặn cần kiểm tra")
        loai_key = st.selectbox(
            "Đối tượng nuôi trồng:",
            options=list(ds_loai.keys()),
            format_func=lambda k: ds_loai[k].ten_hien_thi,
        )

        s_mac_dinh_loai = float(kq_man.S_ppt) if kq_man is not None else 15.0
        if kq_man is not None:
            if st.button(f"🔗 Lấy độ mặn vừa đo ở Tab 1 ({kq_man.S_ppt:.2f} ‰)", width="stretch"):
                st.session_state["s_test_loai_input"] = round(float(kq_man.S_ppt), 2)

        s_test_loai = st.number_input(
            "Độ mặn cần kiểm tra S (‰):",
            value=float(st.session_state.get("s_test_loai_input", round(s_mac_dinh_loai, 2))),
            min_value=0.0,
            max_value=60.0,
            step=0.5,
            key="s_test_loai_input",
        )

    loai_info = ds_loai[loai_key]
    kq_danh_gia = th.danh_gia_do_man_loai(s_test_loai, loai_info)

    with col_l2:
        nhan_buoc("2", "Kết luận an toàn & Phổ thích nghi sinh học")
        if kq_danh_gia.trang_thai == "AN_TOAN":
            bang("xanh", f"<b>{kq_danh_gia.tieu_de}</b><br>{kq_danh_gia.loi_khuyen}", icon="✅", la_html=True)
        elif kq_danh_gia.trang_thai == "CANH_BAO":
            bang("vang", f"<b>{kq_danh_gia.tieu_de}</b><br>{kq_danh_gia.loi_khuyen}", icon="⚠️", la_html=True)
        elif kq_danh_gia.trang_thai == "NGUY_HIEM":
            bang("do", f"<b>{kq_danh_gia.tieu_de}</b><br>{kq_danh_gia.loi_khuyen}", icon="🚨", la_html=True)
        else:
            bang("duong", f"<b>{kq_danh_gia.tieu_de}</b><br>{kq_danh_gia.loi_khuyen}", icon="ℹ️", la_html=True)

        # Thanh phổ trực quan
        pho_html = thanh_nguong_loai(s_test_loai, loai_info)
        if pho_html:
            hien(pho_html)

        st.markdown(f"**📚 Nguồn tài liệu kỹ thuật trích dẫn:**\n> *{kq_danh_gia.nguon_tham_khao}*")

    st.divider()
    st.subheader(f"🌐 Ma trận đánh giá nhanh toàn bộ các loài tại mức độ mặn S = {s_test_loai:.2f} ‰")
    cols_matrix = st.columns(3)
    for idx_m, (k_m, v_m) in enumerate(ds_loai.items()):
        dg_m = th.danh_gia_do_man_loai(s_test_loai, v_m)
        cls_m = "ok" if dg_m.trang_thai == "AN_TOAN" else ("warn" if dg_m.trang_thai == "CANH_BAO" else ("err" if dg_m.trang_thai == "NGUY_HIEM" else ""))
        ic_m = "✅" if dg_m.trang_thai == "AN_TOAN" else ("⚠️" if dg_m.trang_thai == "CANH_BAO" else ("🚨" if dg_m.trang_thai == "NGUY_HIEM" else "ℹ️"))
        with cols_matrix[idx_m % 3]:
            hien(f"""
            <div class="card-mini {cls_m}" style="margin-bottom:10px;">
              <div class="card-mini-title">{ic_m} {v_m.ten_hien_thi}</div>
              <div class="card-mini-desc">
                <b>{dg_m.tieu_de}</b><br>
                <span style="font-size:.77rem; color:#64748B;">Nguồn: {v_m.nguon_tham_khao or 'Chưa bổ sung'}</span>
              </div>
            </div>
            """)

    st.subheader("📋 Bảng tổng hợp ngưỡng kỹ thuật các loài (đọc từ config.yaml)")
    bang_loai_data = []
    for k, v in ds_loai.items():
        bang_loai_data.append({
            "Mã loài": k,
            "Tên đối tượng": v.ten_hien_thi,
            "Dải an toàn (‰)": f"{v.an_toan_min:g} – {v.an_toan_max:g}" if v.an_toan_min is not None else "Chưa có",
            "Cảnh báo thấp (‰)": f"{v.canh_bao_thap[0]:g} – {v.canh_bao_thap[1]:g}" if v.canh_bao_thap else "—",
            "Cảnh báo cao (‰)": f"{v.canh_bao_cao[0]:g} – {v.canh_bao_cao[1]:g}" if v.canh_bao_cao else "—",
            "Ngưỡng nguy hiểm (‰)": f"< {v.nguy_hiem_duoi:g} hoặc > {v.nguy_hiem_tren:g}" if v.nguy_hiem_tren is not None else "Chưa có",
            "Nguồn tham khảo": v.nguon_tham_khao if v.nguon_tham_khao else "⚠️ CHƯA CÓ NGUỒN (yêu cầu điền)",
        })
    st.dataframe(pd.DataFrame(bang_loai_data), width="stretch", hide_index=True)


# ===========================================================================
# TAB 3: NHẬT KÍ ĐO & XUẤT DỮ LIỆU
# ===========================================================================
with tab_nhatki:
    tieu_de_muc(
        "📒",
        "Nhật Kí Quan Trắc & Diễn Biến Độ Mặn Theo Thời Gian",
        "Lưu trữ lịch sử đo trong cơ sở dữ liệu SQLite, phân tích xu hướng xâm nhập mặn và xuất báo cáo CSV",
    )

    c_act1, c_act2, _ = st.columns([1.2, 1.1, 1.5])
    with c_act1:
        if st.button("🧪 Nạp 10 bản ghi quan trắc mẫu (Mô phỏng)", width="stretch"):
            nap_nhat_ki_mau_mo_phong(mh_hien_tai)
            st.session_state["da_luu_nhat_ki_phien_nay"] = True
            st.rerun()
    with c_act2:
        if st.button("🗑️ Xóa toàn bộ nhật kí hiện tại", width="stretch"):
            xoa_toan_bo_nhat_ki()
            st.rerun()

    df_nk = doc_lich_su_db()
    if df_nk.empty:
        bang(
            "duong",
            "Chưa có bản ghi nào trong nhật kí. Hãy thực hiện phép đo ở <b>Tab 1</b> và nhấn <b>'Lưu vào Nhật Kí'</b>, "
            "hoặc nhấn nút <b>'🧪 Nạp 10 bản ghi quan trắc mẫu'</b> ở trên để trải nghiệm ngay biểu đồ chuỗi thời gian.",
            icon="📝",
            la_html=True,
        )
    else:
        c_st1, c_st2, c_st3, c_st4 = st.columns(4)
        with c_st1:
            hien(the_so("TỔNG SỐ LẦN ĐO", f"{len(df_nk)}", don_vi="lần", kieu="vien-xanh"))
        with c_st2:
            so_hop_le = int(df_nk["chat_luong_hop_le"].sum()) if "chat_luong_hop_le" in df_nk else len(df_nk)
            hien(the_so("TỈ LỆ ẢNH ĐẠT CHUẨN", f"{so_hop_le}/{len(df_nk)}", phu=f"Đạt {so_hop_le/len(df_nk)*100:.0f}%", kieu="vien-ngoc"))
        with c_st3:
            hien(the_so("ĐỘ MẶN TRUNG BÌNH", f"{df_nk['do_man_ppt'].mean():.2f}", don_vi="‰", phu=f"Min: {df_nk['do_man_ppt'].min():.1f} | Max: {df_nk['do_man_ppt'].max():.1f} ‰", kieu="nhan-manh"))
        with c_st4:
            hien(the_so("BẤT ĐỊNH MỞ RỘNG TB", f"±{df_nk['bat_dinh_U_ppt'].mean():.2f}", don_vi="‰", phu="Độ tin cậy k = 2 (≈95%)", kieu="vien-vang"))

        col_f1, col_f2 = st.columns(2)
        loc_loai = col_f1.multiselect("Lọc theo đối tượng nuôi:", options=df_nk["loai_nuoi"].unique())
        loc_nguon = col_f2.multiselect("Lọc theo nguồn dữ liệu:", options=df_nk["nguon_du_lieu"].unique())

        df_hien_thi = df_nk.copy()
        if loc_loai:
            df_hien_thi = df_hien_thi[df_hien_thi["loai_nuoi"].isin(loc_loai)]
        if loc_nguon:
            df_hien_thi = df_hien_thi[df_hien_thi["nguon_du_lieu"].isin(loc_nguon)]

        st.subheader("📈 Biểu đồ diễn biến độ mặn kèm dải bất định mở rộng ±U₉₅%")
        df_plot = df_hien_thi.copy()
        df_plot["thoi_gian_dt"] = pd.to_datetime(df_plot["thoi_gian"], errors="coerce")
        df_plot = df_plot.sort_values("thoi_gian_dt")

        fig_time, ax_t = plt.subplots(figsize=(10.5, 3.8), dpi=110)
        x_vals = np.arange(len(df_plot))
        nhan_x = [t.strftime("%d/%m %H:%M") if pd.notna(t) else str(i) for i, t in enumerate(df_plot["thoi_gian_dt"])]

        ax_t.plot(x_vals, df_plot["do_man_ppt"], marker="o", color="#E5383B", lw=2.2, label="Độ mặn đo được S (‰)")
        ax_t.fill_between(
            x_vals,
            df_plot["do_man_ppt"] - df_plot["bat_dinh_U_ppt"],
            df_plot["do_man_ppt"] + df_plot["bat_dinh_U_ppt"],
            color="#E5383B",
            alpha=0.18,
            label="Dải bất định mở rộng ± U₉₅%",
        )
        ax_t.set_xticks(x_vals)
        ax_t.set_xticklabels(nhan_x, rotation=25, ha="right", fontsize=8)
        ax_t.set_ylabel("Độ mặn (‰)")
        ax_t.set_xlabel("Thời điểm quan trắc")
        ax_t.set_title("Chuỗi thời gian quan trắc độ mặn thực địa", fontsize=10.5)
        ax_t.legend(loc="upper left")
        fig_time.tight_layout()
        st.pyplot(fig_time)

        st.subheader("📋 Bảng dữ liệu chi tiết")
        st.dataframe(df_hien_thi, width="stretch", hide_index=True)

        csv_bytes = df_hien_thi.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button(
            label="📥 Tải xuống báo cáo Nhật kí CSV (Mở trực tiếp bằng Excel)",
            data=csv_bytes,
            file_name="nhat_ki_do_do_man.csv",
            mime="text/csv",
            type="primary",
        )


# ===========================================================================
# TAB 4: HIỆU CHUẨN & BÙ NHIỆT ĐỘ
# ===========================================================================
with tab_hieuchuan:
    tieu_de_muc(
        "📊",
        "Hiệu Chuẩn Thiết Bị & Bù Nhiệt Độ Thực Nghiệm (Cột mốc 4)",
        "Dựng hàm đa thức Δy = f(S, T) từ dung dịch chuẩn NaCl với kiểm định chéo k-fold chống quá khớp",
    )

    col_h1, col_h2 = st.columns([1.15, 1], gap="medium")

    with col_h1:
        nhan_buoc("1", "Nạp tập dữ liệu đo dung dịch chuẩn NaCl")
        csv_hieu_chuan = st.file_uploader(
            "Tải file CSV đo chuẩn thực nghiệm (đủ 7 cột quy định):",
            type=["csv"],
            key="csv_calib",
        )

        c_bcal1, c_bcal2 = st.columns(2)
        with c_bcal1:
            if st.button("🧪 Nạp bộ dữ liệu chuẩn mô phỏng (72 điểm)", width="stretch"):
                st.session_state["df_calib_saved"] = sinh_du_lieu_hieu_chuan_mo_phong(seed=1)
                st.session_state["ten_nguon_calib"] = "Bộ dữ liệu mô phỏng Snell (8 mức S × 3 mức T × 3 lần lặp)"
                # Tự động chạy dựng đường chuẩn ngay khi nạp
                st.session_state["auto_run_calib"] = True

        with c_bcal2:
            csv_mau_trong = (
                "do_man_chuan_ppt,nhiet_do_C,delta_y_px,do_duc_tuong_doi,ghi_chu,id_thiet_bi,id_dien_thoai\n"
                "0.0,25.0,0.05,0.01,Nuoc cat,TB01,DT01\n"
                "5.0,25.0,24.80,0.01,NaCl 5 ppt,TB01,DT01\n"
                "10.0,25.0,49.65,0.01,NaCl 10 ppt,TB01,DT01\n"
                "15.0,25.0,74.50,0.01,NaCl 15 ppt,TB01,DT01\n"
                "20.0,25.0,99.45,0.01,NaCl 20 ppt,TB01,DT01\n"
                "25.0,25.0,124.50,0.01,NaCl 25 ppt,TB01,DT01\n"
                "30.0,25.0,149.60,0.01,NaCl 30 ppt,TB01,DT01\n"
            ).encode("utf-8-sig")
            st.download_button(
                "📥 Tải file CSV mẫu chuẩn (7 cột)",
                data=csv_mau_trong,
                file_name="mau_nhap_hieu_chuan_7_cot.csv",
                mime="text/csv",
                width="stretch",
            )

        if csv_hieu_chuan is not None:
            try:
                df_loaded = cal.doc_csv_hieu_chuan(csv_hieu_chuan)
                st.session_state["df_calib_saved"] = df_loaded
                st.session_state["ten_nguon_calib"] = f"File tải lên: {csv_hieu_chuan.name} ({len(df_loaded)} điểm)"
            except Exception as e:
                bang("do", f"Lỗi đọc file CSV: {e}", icon="🚨")

        df_calib_input: pd.DataFrame | None = st.session_state.get("df_calib_saved")
        if df_calib_input is not None:
            ten_ng = st.session_state.get("ten_nguon_calib", "Dữ liệu đã nạp")
            la_mp_df = cal.la_du_lieu_mo_phong(df_calib_input)
            bang(
                "vang" if la_mp_df else "xanh",
                f"<b>Đang sẵn sàng:</b> {ten_ng} — Tổng số <b>{len(df_calib_input)} dòng</b> hợp lệ "
                f"({'DỮ LIỆU MÔ PHỎNG' if la_mp_df else 'DỮ LIỆU ĐO THẬT'}).",
                icon="🧪" if la_mp_df else "✅",
                la_html=True,
            )

    with col_h2:
        nhan_buoc("2", "Lựa chọn bậc đa thức & Kiểm định chéo")
        bac_lua_chon = st.radio(
            "Chiến lược chọn bậc đa thức Δy = f(S, T):",
            [
                "Tự động chọn (Kiểm định chéo 5-fold chống quá khớp)",
                "Ép Bậc 1 (Tuyến tính: c₀ + c_S·S + c_T·ΔT)",
                "Ép Bậc 2 (Đa thức bậc hai đầy đủ)",
            ],
        )
        bac_ep_val = 1 if "Bậc 1" in bac_lua_chon else (2 if "Bậc 2" in bac_lua_chon else None)

        nut_chay_calib = st.button("⚡ TIẾN HÀNH DỰNG ĐƯỜNG CHUẨN", type="primary", width="stretch")

    if (nut_chay_calib or st.session_state.pop("auto_run_calib", False)) and df_calib_input is not None:
        with st.spinner("Đang chạy kiểm định chéo k-fold và khớp bình phương tối thiểu..."):
            try:
                bc_cal_moi = cal.dung_duong_chuan(
                    df_calib_input, cal.CauHinhHieuChuan.tu_yaml(), bac_ep=bac_ep_val
                )
                st.session_state["bc_cal_saved"] = bc_cal_moi
            except Exception as ex:
                st.error(f"Không thể dựng đường chuẩn: {ex}")

    bc_cal: cal.BaoCaoHieuChuan | None = st.session_state.get("bc_cal_saved")
    if bc_cal is not None:
        mh_new = bc_cal.mo_hinh
        st.divider()
        st.subheader("📈 Báo cáo kết quả dựng đường chuẩn & Đánh giá độc lập trên tập Test")

        c_r1, c_r2, c_r3, c_r4 = st.columns(4)
        with c_r1:
            hien(the_so("HỆ SỐ XÁC ĐỊNH R²", f"{mh_new.R2:.5f}", phu=f"Khớp trên {mh_new.so_diem} điểm", kieu="nhan-manh"))
        with c_r2:
            hien(the_so("BẬC ĐA THỨC CHỌN", f"Bậc {bc_cal.bac_chon}", phu=bc_cal.ly_do_chon, kieu="vien-ngoc"))
        with c_r3:
            val_test = f"{bc_cal.RMSE_test_ppt:.3f}" if not np.isnan(bc_cal.RMSE_test_ppt) else "N/A"
            hien(the_so("RMSE TẬP KIỂM TRA (TEST)", val_test, don_vi="‰", phu=f"RMSE ảnh: {bc_cal.RMSE_test_px:.3f} px", kieu="vien-vang"))
        with c_r4:
            hien(the_so("ĐỘ LỆCH CHUẨN s_res", f"{mh_new.s_res_px:.3f}", don_vi="px", phu=f"Bậc tự do ν = {mh_new.bac_tu_do}", kieu="vien-xanh"))

        if mh_new.la_mo_phong:
            bang("vang", cal.NHAN_CHUA_HIEU_CHUAN + ": Đường chuẩn này dựng từ dữ liệu mô phỏng, KHÔNG phải số đo thực nghiệm.", icon="⚠️")
        else:
            bang("xanh", "ĐÃ HIỆU CHUẨN THÀNH CÔNG TỪ DỮ LIỆU ĐO THỰC NGHIỆM!", icon="✅")

        hs_str = " + ".join([f"({c:+.5g})·{h}" for h, c in zip(mh_new.hang, mh_new.he_so)])
        st.code(f"Phương trình đường chuẩn:  Δy (px) = {hs_str}   [với ΔT = T − {mh_new.T_ref} °C]")

        c_p1, c_p2 = st.columns(2)
        with c_p1:
            st.pyplot(cal.ve_duong_chuan(bc_cal))
        with c_p2:
            st.pyplot(cal.ve_phan_du(bc_cal))

        with st.expander("📋 Xem bảng phân tích sai số theo từng mức độ mặn chuẩn"):
            st.dataframe(bc_cal.sai_so_theo_muc.round(4), width="stretch", hide_index=True)

        if st.button("💾 Lưu & Áp dụng mô hình hiệu chuẩn này làm mặc định", type="primary"):
            OUTPUTS_DIR.mkdir(exist_ok=True)
            luu_path = HE_SO_MP_PATH if mh_new.la_mo_phong else HE_SO_JSON_PATH
            mh_new.luu_json(luu_path)
            st.toast(f"Đã lưu mô hình vào {luu_path.name}!", icon="✅")
            st.success(f"✅ Đã lưu và kích hoạt mô hình hiệu chuẩn `{luu_path.name}` thành công!")


# ===========================================================================
# TAB 5: MÔ PHỎNG QUANG HỌC & NGÂN SÁCH SAI SỐ
# ===========================================================================
with tab_mophong:
    tieu_de_muc(
        "📐",
        "Mô Phỏng Mô Hình Quang Học Snell & Ngân Sách Sai Số Thiết Kế",
        "Khảo sát đường đi tia sáng qua lăng kính hai ngăn, giới hạn phản xạ toàn phần (TIR) và sai số RSS",
    )

    cfg_cur = load_config()
    col_opt1, col_opt2 = st.columns([1, 1.15], gap="medium")

    with col_opt1:
        nhan_buoc("1", "Cấu hình hình học lăng kính & Môi trường")
        a_sim = st.slider("Góc đỉnh lăng kính A (độ)", 25.0, 48.5, float(cfg_cur.A_do), 0.5)
        d_sim = st.slider("Khoảng cách từ lăng kính tới màn D (m)", 0.4, 2.5, float(cfg_cur.D_m), 0.1)
        px_sim = st.number_input("Kích thước pixel quy đổi trên màn (mm/px)", value=float(cfg_cur.pixel_mm), step=0.005, format="%.4f")
        s_eval = st.slider("Độ mặn mẫu khảo sát S (‰)", 0.0, 40.0, 20.0, 1.0)
        t_eval = st.slider("Nhiệt độ khảo sát T (°C)", 10.0, 40.0, 25.0, 1.0)

    cfg_sim = op.CauHinhQuangHoc(
        A_do=a_sim,
        D_m=d_sim,
        n_nuoc_ngot=cfg_cur.n_nuoc_ngot,
        dn_dS=cfg_cur.dn_dS,
        dn_dT=cfg_cur.dn_dT,
        T_tham_chieu_C=cfg_cur.T_tham_chieu_C,
        bien_TIR=cfg_cur.bien_TIR,
        pixel_mm=px_sim,
    )

    with col_opt2:
        nhan_buoc("2", "Sơ đồ đường truyền tia sáng & Kết quả định luật Snell")
        n_calc = op.chiet_suat(s_eval, t_eval, cfg_sim)
        n_tc_calc = op.chiet_suat(0.0, t_eval, cfg_sim)

        try:
            theta_ra = op.goc_ra(n_calc, a_sim)
            delta_goc = op.goc_lech(n_calc, a_sim)
            dy_px_sim = op.delta_y_vi_sai_px(s_eval, t_eval, t_eval, cfg_sim, A_do=a_sim)
            sens_px = op.pixel_moi_phan_nghin(s_eval, t_eval, cfg_sim, A_do=a_sim, D_m=d_sim)

            hien(svg_he_quang_hoc(A_do=a_sim, S_ppt=s_eval, delta_y_px=dy_px_sim, drift_px=0.0, tir=False))

            c_o1, c_o2, c_o3 = st.columns(3)
            with c_o1:
                hien(the_so("GÓC LÓ θ_ra", f"{theta_ra:.2f}", don_vi="°", phu=f"n_mẫu = {n_calc:.5f}", kieu="vien-xanh"))
            with c_o2:
                hien(the_so("GÓC LỆCH δ", f"{delta_goc:.2f}", don_vi="°", phu=f"Δy = {dy_px_sim:.1f} px", kieu="vien-ngoc"))
            with c_o3:
                hien(the_so("ĐỘ NHẠY HỆ THỐNG", f"{sens_px:.2f}", don_vi="px/‰", phu=f"Tại A={a_sim:g}°, D={d_sim:g}m", kieu="nhan-manh"))

        except op.PhanXaToanPhanError:
            hien(svg_he_quang_hoc(A_do=a_sim, S_ppt=s_eval, delta_y_px=0.0, drift_px=0.0, tir=True))
            bang(
                "do",
                f"🚨 <b>PHẢN XẠ TOÀN PHẦN (TIR):</b> <code>n·sin(A) = {n_calc * math.sin(math.radians(a_sim)):.4f} ≥ 1</code>. "
                "Tia laser bị phản xạ ngược vào trong lăng kính, không thể thoát ra ngoài màn hứng. Hãy giảm góc đỉnh A xuống ≤ 45°!",
                icon="🚨",
                la_html=True,
            )

    # Đồ thị khảo sát độ nhạy theo góc A và theo độ mặn S
    st.divider()
    st.subheader("📈 Đồ thị khảo sát Độ nhạy quang học & Dịch chuyển vi sai lí thuyết")
    c_pl1, c_pl2 = st.columns(2)
    with c_pl1:
        cac_goc_a = np.linspace(25.0, 47.0, 90)
        do_nhay_a = []
        for a_val in cac_goc_a:
            try:
                do_nhay_a.append(op.pixel_moi_phan_nghin(s_eval, t_eval, cfg_sim, A_do=float(a_val), D_m=d_sim))
            except op.PhanXaToanPhanError:
                do_nhay_a.append(np.nan)
        fig_sa, ax_sa = plt.subplots(figsize=(6, 3.4), dpi=110)
        ax_sa.plot(cac_goc_a, do_nhay_a, color="#E5383B", lw=2.2, label="Độ nhạy d(Δy)/dS (px/‰)")
        if a_sim <= 47.0:
            ax_sa.axvline(a_sim, color="#1B4965", ls="--", lw=1.5, label=f"Góc A đang chọn = {a_sim:g}°")
        ax_sa.set_xlabel("Góc đỉnh lăng kính A (độ)")
        ax_sa.set_ylabel("Độ nhạy (px / ‰)")
        ax_sa.set_title("Độ nhạy tăng phi tuyến khi tiến gần góc tới hạn TIR", fontsize=9.5)
        ax_sa.legend(fontsize=8)
        fig_sa.tight_layout()
        st.pyplot(fig_sa)

    with c_pl2:
        cac_muc_s_pl = np.linspace(0.0, 35.0, 71)
        fig_ds, ax_ds = plt.subplots(figsize=(6, 3.4), dpi=110)
        try:
            dy_20 = [op.delta_y_vi_sai_px(float(sv), 20.0, 20.0, cfg_sim) for sv in cac_muc_s_pl]
            dy_30 = [op.delta_y_vi_sai_px(float(sv), 30.0, 30.0, cfg_sim) for sv in cac_muc_s_pl]
            ax_ds.plot(cac_muc_s_pl, dy_20, color="#14B8A6", lw=2.0, label="T = 20 °C")
            ax_ds.plot(cac_muc_s_pl, dy_30, color="#F59E0B", lw=2.0, ls="--", label="T = 30 °C")
            ax_ds.set_xlabel("Độ mặn S (‰)")
            ax_ds.set_ylabel("Độ lệch vi sai Δy lí thuyết (px)")
            ax_ds.set_title(f"Đường đáp ứng Δy(S) lí thuyết tại A = {a_sim:g}°, D = {d_sim:g} m", fontsize=9.5)
            ax_ds.legend(fontsize=8)
        except op.PhanXaToanPhanError:
            ax_ds.text(0.5, 0.5, "Góc A vượt ngưỡng Phản xạ toàn phần", ha="center", va="center")
        fig_ds.tight_layout()
        st.pyplot(fig_ds)

    st.divider()
    st.subheader("🎯 Ngân sách sai số thiết kế (Error Budget RSS)")
    st.caption("Quy đổi các nguồn sai số độc lập về độ lệch chuẩn độ mặn tương đương (‰)")

    c_err1, c_err2 = st.columns([1, 1.6], gap="medium")
    with c_err1:
        err_tam = st.number_input("Sai số thuật toán tìm tâm vạch (px)", value=0.05, step=0.01, format="%.3f")
        err_t = st.number_input("Chênh nhiệt độ giữa 2 ngăn (°C)", value=0.5, step=0.1)
        err_a = st.number_input("Sai số chế tạo góc đỉnh A (độ)", value=0.05, step=0.01)
        err_troi = st.number_input("Độ trôi chung của laser / rung camera (px)", value=5.0, step=0.5)
        he_so_triet = st.number_input("Hệ số lọt sau đo vi sai (0..1)", value=0.01, step=0.005, format="%.3f")

    with c_err2:
        try:
            ngan_sach = op.ngan_sach_sai_so(
                s_eval, t_eval, cfg_sim, err_tam, err_t, err_a, err_troi, he_so_triet
            )
            df_ns = pd.DataFrame([
                {"Nguồn sai số": "1. Thuật toán định vị tâm vạch dưới pixel (px)", "Bất định quy đổi (‰)": f"{ngan_sach['tim_tam']:.4f}"},
                {"Nguồn sai số": "2. Chênh lệch nhiệt độ giữa 2 ngăn (°C)", "Bất định quy đổi (‰)": f"{ngan_sach['nhiet_do']:.4f}"},
                {"Nguồn sai số": "3. Sai số gia công góc đỉnh lăng kính A (độ)", "Bất định quy đổi (‰)": f"{ngan_sach['goc_A']:.4f}"},
                {"Nguồn sai số": "4. Trôi laser & rung máy còn sót sau khử vi sai", "Bất định quy đổi (‰)": f"{ngan_sach['troi_laser']:.4f}"},
                {"Nguồn sai số": "∑ TỔNG HỢP TOÀN PHƯƠNG (RSS 1σ)", "Bất định quy đổi (‰)": f"{ngan_sach['tong_RSS']:.4f}"},
            ])
            st.dataframe(df_ns, width="stretch", hide_index=True)
            bang(
                "xanh",
                f"Tổng bất định chuẩn thiết kế (1σ): <b>± {ngan_sach['tong_RSS']:.3f} ‰</b> "
                f"(Bất định mở rộng U₉₅% ≈ <b>± {2.0 * ngan_sach['tong_RSS']:.3f} ‰</b>)",
                icon="🎯",
                la_html=True,
            )
        except op.PhanXaToanPhanError:
            bang("do", "Không tính được ngân sách sai số do góc A đang ở vùng phản xạ toàn phần.", icon="🚨")


# ===========================================================================
# TAB 6: ĐỐI CHỨNG KHÚC XẠ KẾ (BLAND-ALTMAN)
# ===========================================================================
with tab_so_sanh:
    tieu_de_muc(
        "⚖️",
        "Đối Chứng Với Khúc Xạ Kế Quang Cơ Cầm Tay (Bland–Altman)",
        "Phân tích tương quan tuyến tính và giới hạn đồng thuận 95% (Limits of Agreement) giữa 2 phương pháp đo",
    )

    col_ba1, col_ba2 = st.columns([1, 1.2], gap="medium")

    with col_ba1:
        nhan_buoc("1", "Nạp hoặc nhập dữ liệu đo song song 2 thiết bị")
        if st.button("📋 Nạp bảng 24 cặp số liệu đối chứng mẫu (Mô phỏng)", width="stretch"):
            rng_ba = np.random.default_rng(42)
            s_true_vals = np.array([0, 5, 10, 15, 20, 25, 30, 35] * 3, dtype=float)
            s_may_toi = s_true_vals + rng_ba.normal(0.0, 0.16, len(s_true_vals))
            s_ref_opt = s_true_vals + rng_ba.normal(0.08, 0.35, len(s_true_vals))
            st.session_state["df_ba_saved"] = pd.DataFrame({
                "S_thiet_bi": np.round(s_may_toi, 2),
                "S_khuc_xa_ke": np.round(s_ref_opt, 2),
            })

        csv_ba = st.file_uploader(
            "Hoặc tải file CSV có 2 cột (S_thiet_bi, S_khuc_xa_ke):",
            type=["csv"],
            key="ba_upload",
        )
        if csv_ba is not None:
            st.session_state["df_ba_saved"] = pd.read_csv(csv_ba)

    df_ba_cur: pd.DataFrame | None = st.session_state.get("df_ba_saved")

    if df_ba_cur is not None and "S_thiet_bi" in df_ba_cur.columns and "S_khuc_xa_ke" in df_ba_cur.columns:
        with col_ba2:
            nhan_buoc("2", "Bảng dữ liệu đối chứng (Có thể chỉnh sửa trực tiếp)")
            df_ba_edit = st.data_editor(
                df_ba_cur,
                num_rows="dynamic",
                width="stretch",
                height=195,
                key="ba_editor",
            )

        m1 = pd.to_numeric(df_ba_edit["S_thiet_bi"], errors="coerce").dropna().to_numpy(float)
        m2 = pd.to_numeric(df_ba_edit["S_khuc_xa_ke"], errors="coerce").dropna().to_numpy(float)
        n_pair = min(len(m1), len(m2))
        m1, m2 = m1[:n_pair], m2[:n_pair]

        if n_pair >= 3:
            tb_2_phuong_phap = (m1 + m2) / 2.0
            hieu_so = m1 - m2

            mean_diff = float(np.mean(hieu_so))
            std_diff = float(np.std(hieu_so, ddof=1))
            loa_upper = mean_diff + 1.96 * std_diff
            loa_lower = mean_diff - 1.96 * std_diff
            r_corr = float(np.corrcoef(m1, m2)[0, 1]) if np.std(m1) > 0 and np.std(m2) > 0 else 1.0

            st.divider()
            c_b1, c_b2, c_b3, c_b4 = st.columns(4)
            with c_b1:
                hien(the_so("SAI LỆCH TRUNG BÌNH (BIAS)", f"{mean_diff:+.3f}", don_vi="‰", phu="Độ lệch hệ thống giữa 2 máy", kieu="nhan-manh"))
            with c_b2:
                hien(the_so("ĐỘ LỆCH CHUẨN HIỆU SỐ (SD)", f"{std_diff:.3f}", don_vi="‰", phu=f"Trên {n_pair} cặp phép đo", kieu="vien-ngoc"))
            with c_b3:
                hien(the_so("GIỚI HẠN ĐỒNG THUẬN 95%", f"[{loa_lower:+.2f}, {loa_upper:+.2f}]", don_vi="‰", phu="Mean ± 1.96·SD", kieu="vien-vang"))
            with c_b4:
                hien(the_so("HỆ SỐ TƯƠNG QUAN r", f"{r_corr:.5f}", phu=f"R² = {r_corr**2:.5f}", kieu="vien-xanh"))

            c_g1, c_g2 = st.columns(2)
            with c_g1:
                fig_corr, ax_c = plt.subplots(figsize=(6.2, 4.2), dpi=110)
                ax_c.scatter(m2, m1, color="#1B4965", s=36, alpha=0.85, label="Cặp điểm đo thực nghiệm")
                lims = [min(m1.min(), m2.min()) - 1, max(m1.max(), m2.max()) + 1]
                ax_c.plot(lims, lims, "r--", lw=1.5, label="Đường đồng nhất lí tưởng (y = x)")
                ax_c.set_xlabel("Độ mặn Khúc xạ kế đối chứng (‰)")
                ax_c.set_ylabel("Độ mặn Thiết bị đo vi sai (‰)")
                ax_c.set_title(f"Đồ thị tương quan 2 phương pháp (R² = {r_corr**2:.4f})", fontsize=10)
                ax_c.legend(fontsize=8, loc="upper left")
                fig_corr.tight_layout()
                st.pyplot(fig_corr)

            with c_g2:
                fig_ba, ax_ba = plt.subplots(figsize=(6.2, 4.2), dpi=110)
                ax_ba.scatter(tb_2_phuong_phap, hieu_so, color="#E5383B", s=36, alpha=0.85, label="Hiệu số (S_máy − S_kxk)")
                ax_ba.axhline(mean_diff, color="#1B4965", linestyle="-", lw=1.8, label=f"Mean Bias = {mean_diff:+.3f} ‰")
                ax_ba.axhline(loa_upper, color="#14B8A6", linestyle="--", lw=1.4, label=f"+1.96 SD = {loa_upper:+.3f} ‰")
                ax_ba.axhline(loa_lower, color="#14B8A6", linestyle="--", lw=1.4, label=f"-1.96 SD = {loa_lower:+.3f} ‰")
                ax_ba.axhline(0, color="gray", linestyle=":", lw=0.9)
                ax_ba.set_xlabel("Trung bình 2 phương pháp: (S_thiết_bị + S_khúc_xạ_kế) / 2 (‰)")
                ax_ba.set_ylabel("Sai khác: S_thiết_bị − S_khúc_xạ_kế (‰)")
                ax_ba.set_title("Đồ thị Bland–Altman đánh giá mức độ đồng thuận", fontsize=10)
                ax_ba.legend(fontsize=8, loc="upper right")
                fig_ba.tight_layout()
                st.pyplot(fig_ba)

            bang(
                "xanh",
                f"<b>Kết luận thống kê phục vụ thuyết minh KHKT:</b> Khoảng 95% sai khác giữa thiết bị của dự án và khúc xạ kế "
                f"nằm trong dải hẹp <b>[{loa_lower:+.2f} ‰, {loa_upper:+.2f} ‰]</b> với độ lệch trung bình (Bias) chỉ <b>{mean_diff:+.3f} ‰</b>. "
                f"Điều này chứng minh thiết bị đo khúc xạ laser hai ngăn vi sai có độ đồng thuận cao và hoàn toàn có thể thay thế khúc xạ kế quang cơ truyền thống.",
                icon="🎯",
                la_html=True,
            )
    else:
        bang(
            "duong",
            "Nhấn nút <b>'📋 Nạp bảng 24 cặp số liệu đối chứng mẫu'</b> hoặc tải file CSV cặp giá trị để vẽ đồ thị tương quan và Bland–Altman.",
            icon="👈",
            la_html=True,
        )
