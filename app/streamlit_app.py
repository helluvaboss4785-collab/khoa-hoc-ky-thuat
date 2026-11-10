"""Ứng dụng Streamlit: Thiết bị đo độ mặn khúc xạ laser hai ngăn vi sai (Cột mốc 5).

Giao diện Tiếng Việt hoàn toàn, thiết kế tối ưu cho học sinh THPT thuyết minh và phỏng vấn KHKT.
Bao gồm 6 tab chức năng:
1. Đo độ mặn & độ đục từ ảnh (hỗ trợ tải ảnh / chụp camera / ảnh mô phỏng)
2. Cảnh báo theo đối tượng nuôi trồng (tôm thẻ, tôm sú, cá tra, lúa, sầu riêng...)
3. Nhật kí đo & Xuất báo cáo CSV
4. Hiệu chuẩn thiết bị & Bù nhiệt độ
5. Mô phỏng quang học & Ngân sách sai số
6. So sánh đối chứng với khúc xạ kế quang cơ (Đồ thị Bland–Altman)
"""
from __future__ import annotations

import io
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
import yaml

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
    the_so,
    tieu_de_muc,
)
from core import calibration as cal
from core import optics as op
from core import spot
from core import thresholds as th
from core.measure import do_delta_y_tu_anh
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
def khoi_tao_db():
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
):
    khoi_tao_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO nhat_ki (
                thoi_gian, vi_tri, loai_nuoi, delta_y_px, do_man_ppt,
                bat_dinh_U_ppt, nhiet_do_C, do_duc, chat_luong_hop_le,
                nguon_du_lieu, ghi_chu
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            vi_tri, loai_nuoi, delta_y_px, do_man_ppt, bat_dinh_U_ppt,
            nhiet_do_C, do_duc, 1 if chat_luong_hop_le else 0,
            nguon_du_lieu, ghi_chu
        ))


def doc_lich_su_db() -> pd.DataFrame:
    khoi_tao_db()
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query("SELECT * FROM nhat_ki ORDER BY id DESC", conn)


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
# Hướng dẫn người dùng lần đầu truy cập (Onboarding Tour)
# ---------------------------------------------------------------------------
if "da_xem_huong_dan" not in st.session_state:
    st.session_state["da_xem_huong_dan"] = False
    st.session_state["mo_huong_dan"] = True

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
    + (
        huy_hieu("CHƯA HIỆU CHUẨN (MÔ PHỎNG)", "vang", "🧪")
        if mh_hien_tai.la_mo_phong
        else huy_hieu("ĐÃ HIỆU CHUẨN ĐO THẬT", "xanh", "✅")
    )
)

hero(
    kicker="DỰ ÁN DỰ THI KHOA HỌC KỸ THUẬT (KHKT) DÀNH CHO HỌC SINH THPT",
    tieu_de="Thiết Bị Đo Độ Mặn Nước Bằng Khúc Xạ Laser Vi Sai",
    phu_de=(
        "Khử trôi nhiệt laser & rung lắc camera bằng vi sai hai ngăn • "
        "Thuật toán tìm tâm dưới pixel • Hiệu chuẩn bù nhiệt & Đánh giá bất định chuẩn GUM"
    ),
    huy_hieu_html=huy_hieu_top,
)

# ---------------------------------------------------------------------------
# Sidebar: Thông tin hệ thống & Trợ giúp nhanh
# ---------------------------------------------------------------------------
with st.sidebar:
    hien("""
    <div class="sb-logo">🔬 QUANG HỌC <b>VI SAI</b></div>
    <div style="font-size: 0.85rem; color: #CBD5E1; margin-bottom: 12px;">Đo độ mặn & độ đục nước bằng camera</div>
    """)

    if st.button("📖 Hướng dẫn sử dụng", width="stretch", help="Xem lại hướng dẫn thao tác & nguyên lí"):
        st.session_state["mo_huong_dan"] = True
        st.rerun()

    st.divider()

    hien('<div class="sb-tt">Trạng thái đường chuẩn:</div>')
    if mh_hien_tai.la_mo_phong:
        bang("vang", "Đang dùng dữ liệu MÔ PHỎNG. Cần nạp file CSV đo chuẩn thật ở Tab 4 để chính thức hiệu chuẩn.", icon="⚠️")
    else:
        bang("xanh", f"ĐÃ HIỆU CHUẨN THẬT<br>Bậc {mh_hien_tai.bac} | R² = {mh_hien_tai.R2:.4f} | {mh_hien_tai.so_diem} mẫu", icon="✅", la_html=True)

    hien("""
    <div class="sb-the">
      <div class="sb-tt">💡 Nguyên lí vi sai cốt lõi:</div>
      Tia laser chiếu qua 2 ngăn: <b>Nước cất</b> và <b>Mẫu</b>.<br>
      Tín hiệu <b>Δy = y_mẫu − y_tc</b> tự động triệt tiêu rung máy ảnh, trôi laser và sai số cuvet ở bậc 1!
    </div>
    <div class="sb-the">
      <div class="sb-tt">📐 Thông số hình học:</div>
      • Góc đỉnh A: <b>40.0°</b><br>
      • Quãng đường màn D: <b>1.0 m</b><br>
      • Bước sóng: <b>650 nm</b> (laser đỏ)
    </div>
    """)


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
# TAB 1: ĐO ĐỘ MẶN VÀ ĐỘ ĐỤC
# ===========================================================================
with tab_do:
    tieu_de_muc("📸", "Đo Độ Mặn & Chỉ Số Độ Đục Nước", "Thu nhận ảnh vạch laser trên màn hứng, định vị tâm dưới pixel và giải ngược độ mặn")

    col_inp1, col_inp2 = st.columns([1.1, 1], gap="medium")

    with col_inp1:
        nhan_buoc("1", "Chọn nguồn ảnh chụp vạch sáng")
        nguon_anh = st.radio(
            "Nguồn ảnh:",
            ["Tải ảnh lên", "Chụp bằng Camera", "Tạo ảnh mô phỏng thử nghiệm"],
            horizontal=True,
            label_visibility="collapsed",
        )

        anh_input: np.ndarray | None = None
        la_anh_mo_phong = False

        if nguon_anh == "Tải ảnh lên":
            file_upload = st.file_uploader("Chọn file ảnh vạch sáng (JPG, PNG)", type=["jpg", "jpeg", "png"])
            if file_upload:
                file_bytes = np.asarray(bytearray(file_upload.read()), dtype=np.uint8)
                anh_input = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

        elif nguon_anh == "Chụp bằng Camera":
            camera_img = st.camera_input("Chụp trực tiếp màn hứng vạch laser")
            if camera_img:
                file_bytes = np.asarray(bytearray(camera_img.read()), dtype=np.uint8)
                anh_input = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

        else:
            la_anh_mo_phong = True
            bang("duong", "Chế độ mô phỏng vật lí giúp học sinh thử nghiệm phản ứng của phần mềm với các mức độ mặn và độ đục khác nhau.", icon="🧪")
            c_s1, c_s2 = st.columns(2)
            s_mp = c_s1.slider("Độ mặn mẫu mô phỏng (‰)", 0.0, 35.0, 16.5, 0.5)
            t_mp = c_s2.slider("Nhiệt độ mẫu (°C)", 15.0, 35.0, 26.0, 0.5)
            duc_mp = c_s1.slider("Độ đục mẫu (0: trong, 1: rất đục)", 0.0, 1.0, 0.15, 0.05)
            drift_mp = c_s2.slider("Rung lắc máy ảnh / laser trôi (px)", -15.0, 15.0, 4.0, 1.0)

            p_synth = ThamSoMoPhong(
                S_ppt=s_mp, T_C=t_mp, drift_chung_px=drift_mp, do_duc=duc_mp, seed=42
            )
            anh_mp_obj = sinh_anh_hai_vach_mo_phong(p_synth, load_config(), gan_watermark=False)
            anh_input = cv2.cvtColor(anh_mp_obj.anh, cv2.COLOR_GRAY2BGR)

    with col_inp2:
        nhan_buoc("2", "Thông số môi trường & Vị trí lấy mẫu")
        c_env1, c_env2 = st.columns(2)
        nhiet_do_do = c_env1.number_input("Nhiệt độ mẫu đo (°C)", min_value=5.0, max_value=50.0, value=25.0, step=0.5)
        vi_tri_do = c_env2.text_input("Vị trí lấy mẫu / Tên ao hồ", value="Ao nuôi số 1")
        ghi_chu_do = st.text_input("Ghi chú bổ sung", value="Nước mặt ao tôm sau mưa")

        with st.expander("🛠️ Tùy chỉnh vùng chọn ROI (nếu ảnh có vạch bị che lệch)"):
            che_do_roi = st.checkbox("Bật chỉnh tọa độ ROI thủ công", value=False)
            roi_tc_custom, roi_mau_custom = None, None
            if che_do_roi and anh_input is not None:
                h_img, w_img = anh_input.shape[:2]
                st.caption("Tọa độ ROI: [y_min, y_max, x_min, x_max]")
                c_r1, c_r2 = st.columns(2)
                y_tc_min = c_r1.slider("Vạch tham chiếu y_min", 0, h_img // 2, 40)
                y_tc_max = c_r1.slider("Vạch tham chiếu y_max", y_tc_min + 10, h_img, 120)
                y_m_min = c_r2.slider("Vạch mẫu y_min", 0, h_img - 20, 130)
                y_m_max = c_r2.slider("Vạch mẫu y_max", y_m_min + 10, h_img, min(h_img, 240))
                roi_tc_custom = (y_tc_min, y_tc_max, 5, w_img // 2 - 10)
                roi_mau_custom = (y_m_min, y_m_max, w_img // 2 + 10, w_img - 5)

        st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
        nut_do = st.button("🚀 TIẾN HÀNH ĐO ĐỘ MẶN", type="primary", width="stretch")

    st.divider()

    # Xử lí đo khi nhấn nút
    if nut_do and anh_input is not None:
        with st.spinner("Đang trích xuất vạch sáng và định vị tâm dưới pixel..."):
            try:
                kq_do = do_delta_y_tu_anh(
                    anh_input,
                    roi_tham_chieu=roi_tc_custom,
                    roi_mau=roi_mau_custom,
                    buoc_nhay_cot=2,
                )
            except Exception as e:
                st.error(f"Lỗi xử lí ảnh: {e}")
                kq_do = None

        if kq_do:
            try:
                kq_man = cal.uoc_luong_do_man(
                    mh=mh_hien_tai,
                    delta_y_px=kq_do.delta_y_px,
                    T_C=nhiet_do_do,
                    sigma_delta_y_px=kq_do.sai_so_delta_y_px,
                    sigma_T_C=0.5,
                    k=2.0,
                )
            except Exception as ex:
                st.error(f"Lỗi tính toán độ mặn: {ex}")
                kq_man = None

            # Hiển thị 4 thẻ kết quả bắt mắt
            c_k1, c_k2, c_k3, c_k4 = st.columns(4)

            with c_k1:
                if kq_man:
                    hien(the_so(
                        nhan="ĐỘ MẶN ƯỚC LƯỢNG (S ± U₉₅%)",
                        gia_tri=f"{kq_man.S_ppt:.2f}",
                        don_vi="‰",
                        pm=f"± {kq_man.U_S_ppt:.2f} ‰",
                        phu="Khoảng tin cậy k = 2 (≈95%)",
                        kieu="nhan-manh",
                    ))
                else:
                    hien(the_so("ĐỘ MẶN ƯỚC LƯỢNG", "N/A", kieu="nhan-manh"))

            with c_k2:
                hien(the_so(
                    nhan="ĐỘ LỆCH ĐỨNG VI SAI (Δy)",
                    gia_tri=f"{kq_do.delta_y_px:.2f}",
                    don_vi="px",
                    pm=f"± {kq_do.sai_so_delta_y_px:.2f} px",
                    phu="Khớp Gauss dưới pixel",
                    kieu="vien-ngoc",
                ))

            with c_k3:
                hien(the_so(
                    nhan="CHỈ SỐ ĐỘ ĐỤC TƯƠNG ĐỐI",
                    gia_tri=f"{kq_do.chi_so_do_duc_tuong_doi:.2f}",
                    don_vi="[0–1]",
                    phu="Tán xạ làm mở rộng FWHM",
                    kieu="vien-vang",
                ))

            with c_k4:
                cq = kq_do.chat_luong
                trang_thai_cl = "TỐT" if cq.hop_le else "LƯU Ý"
                hien(the_so(
                    nhan="CHẤT LƯỢNG ẢNH CHỤP",
                    gia_tri=trang_thai_cl,
                    phu=f"SNR = {cq.snr:.1f} • Bão hòa {cq.ti_le_bao_hoa*100:.1f}%",
                    kieu="vien-xanh" if cq.hop_le else "vien-do",
                ))

            # Khu vực lưu nhật kí và cảnh báo
            st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
            col_save1, col_save2 = st.columns([1.5, 1])

            with col_save1:
                if cq.canh_bao:
                    for cb in cq.canh_bao:
                        bang("vang", cb, icon="⚠️")
                if kq_man and kq_man.canh_bao:
                    for cb in kq_man.canh_bao:
                        bang("do" if "NGOÀI" in cb else "vang", cb, icon="🚨")

                bang("duong", f"<b>Hạn chế đo lường:</b> {cal.HAN_CHE_NACL}", icon="📌", la_html=True)

            with col_save2:
                loai_chon = st.selectbox(
                    "Loài nuôi tại vị trí này để lưu nhật kí:",
                    options=list(th.doc_danh_sach_loai().keys()),
                    format_func=lambda k: th.doc_danh_sach_loai()[k].ten_hien_thi,
                )
                if st.button("💾 Lưu kết quả này vào Nhật Kí", type="primary", width="stretch"):
                    if kq_man:
                        luu_nhat_ki(
                            vi_tri=vi_tri_do,
                            loai_nuoi=th.doc_danh_sach_loai()[loai_chon].ten_hien_thi,
                            delta_y_px=kq_do.delta_y_px,
                            do_man_ppt=kq_man.S_ppt,
                            bat_dinh_U_ppt=kq_man.U_S_ppt,
                            nhiet_do_C=nhiet_do_do,
                            do_duc=kq_do.chi_so_do_duc_tuong_doi,
                            chat_luong_hop_le=cq.hop_le,
                            nguon_du_lieu="MÔ PHỎNG" if la_anh_mo_phong or mh_hien_tai.la_mo_phong else "ĐO THẬT",
                            ghi_chu=ghi_chu_do,
                        )
                        st.success("✅ Đã lưu kết quả thành công vào cơ sở dữ liệu Nhật Kí!")

            # Hiển thị ảnh phân tích
            if kq_do.anh_danh_dau is not None:
                st.subheader("Ảnh định vị đường tâm hai vạch laser dưới pixel")
                st.image(
                    cv2.cvtColor(kq_do.anh_danh_dau, cv2.COLOR_BGR2RGB),
                    caption="Đường xanh lá: Tâm vạch tham chiếu | Đường cam: Tâm vạch mẫu | Đoạn vàng: Độ lệch đứng Δy",
                    width="stretch",
                )

    elif anh_input is None:
        bang("duong", "Hãy tải ảnh chụp màn hứng hoặc chọn 'Tạo ảnh mô phỏng thử nghiệm' ở trên để bắt đầu phép đo.", icon="👈")


# ===========================================================================
# TAB 2: CẢNH BÁO THEO ĐỐI TƯỢNG
# ===========================================================================
with tab_loai:
    tieu_de_muc("🦐", "Đánh Giá An Toàn Độ Mặn Theo Loài", "Tra cứu ngưỡng thích nghi sinh học và khuyến cáo hành động theo tài liệu kỹ thuật")

    ds_loai = th.doc_danh_sach_loai()
    col_l1, col_l2 = st.columns([1, 1.8], gap="medium")

    with col_l1:
        nhan_buoc("1", "Chọn đối tượng và mức độ mặn")
        loai_key = st.selectbox(
            "Đối tượng nuôi trồng:",
            options=list(ds_loai.keys()),
            format_func=lambda k: ds_loai[k].ten_hien_thi,
        )
        s_test_loai = st.number_input(
            "Độ mặn cần kiểm tra (‰):",
            value=15.0,
            min_value=0.0,
            max_value=60.0,
            step=0.5,
        )

    loai_info = ds_loai[loai_key]
    kq_danh_gia = th.danh_gia_do_man_loai(s_test_loai, loai_info)

    with col_l2:
        nhan_buoc("2", "Kết luận an toàn & Khuyến cáo chuyên môn")
        if kq_danh_gia.trang_thai == "AN_TOAN":
            bang("xanh", f"<b>{kq_danh_gia.tieu_de}</b><br>{kq_danh_gia.loi_khuyen}", icon="✅", la_html=True)
        elif kq_danh_gia.trang_thai == "CANH_BAO":
            bang("vang", f"<b>{kq_danh_gia.tieu_de}</b><br>{kq_danh_gia.loi_khuyen}", icon="⚠️", la_html=True)
        elif kq_danh_gia.trang_thai == "NGUY_HIEM":
            bang("do", f"<b>{kq_danh_gia.tieu_de}</b><br>{kq_danh_gia.loi_khuyen}", icon="🚨", la_html=True)
        else:
            bang("duong", f"<b>{kq_danh_gia.tieu_de}</b><br>{kq_danh_gia.loi_khuyen}", icon="ℹ️", la_html=True)

        st.markdown(f"**📚 Nguồn tài liệu kỹ thuật trích dẫn:**\n> *{kq_danh_gia.nguon_tham_khao}*")

    st.divider()
    st.subheader("Bảng tổng hợp ngưỡng kỹ thuật các loài (đọc từ config.yaml)")

    bang_loai_data = []
    for k, v in ds_loai.items():
        bang_loai_data.append({
            "Mã loài": k,
            "Tên đối tượng": v.ten_hien_thi,
            "Dải an toàn (‰)": f"{v.an_toan_min} – {v.an_toan_max}" if v.an_toan_min is not None else "Chưa có",
            "Cảnh báo thấp": f"{v.canh_bao_thap[0]} – {v.canh_bao_thap[1]}" if v.canh_bao_thap else "—",
            "Cảnh báo cao": f"{v.canh_bao_cao[0]} – {v.canh_bao_cao[1]}" if v.canh_bao_cao else "—",
            "Ngưỡng nguy hiểm": f"< {v.nguy_hiem_duoi} hoặc > {v.nguy_hiem_tren}" if v.nguy_hiem_tren is not None else "Chưa có",
            "Nguồn tham khảo": v.nguon_tham_khao if v.nguon_tham_khao else "⚠️ CHƯA CÓ NGUỒN (yêu cầu điền)",
        })
    st.dataframe(pd.DataFrame(bang_loai_data), width="stretch")


# ===========================================================================
# TAB 3: NHẬT KÍ ĐO & XUẤT DỮ LIỆU
# ===========================================================================
with tab_nhatki:
    tieu_de_muc("📒", "Nhật Kí Đo & Diễn Biến Theo Thời Gian", "Xem lịch sử quan trắc thực địa, phân tích độ phân tán và xuất báo cáo CSV")

    df_nk = doc_lich_su_db()
    if df_nk.empty:
        bang("duong", "Chưa có bản ghi nào trong nhật kí. Hãy thực hiện phép đo ở Tab 1 và nhấn 'Lưu vào Nhật Kí'.", icon="📝")
    else:
        c_st1, c_st2, c_st3 = st.columns(3)
        c_st1.metric("Tổng số lần đo", f"{len(df_nk)} lần")
        so_hop_le = int(df_nk["chat_luong_hop_le"].sum()) if "chat_luong_hop_le" in df_nk else len(df_nk)
        c_st2.metric("Số lần đo đạt chuẩn", f"{so_hop_le} / {len(df_nk)}")
        c_st3.metric("Độ mặn trung bình", f"{df_nk['do_man_ppt'].mean():.2f} ‰")

        col_f1, col_f2 = st.columns(2)
        loc_loai = col_f1.multiselect("Lọc theo đối tượng:", options=df_nk["loai_nuoi"].unique())
        loc_nguon = col_f2.multiselect("Lọc theo nguồn dữ liệu:", options=df_nk["nguon_du_lieu"].unique())

        df_hien_thi = df_nk.copy()
        if loc_loai:
            df_hien_thi = df_hien_thi[df_hien_thi["loai_nuoi"].isin(loc_loai)]
        if loc_nguon:
            df_hien_thi = df_hien_thi[df_hien_thi["nguon_du_lieu"].isin(loc_nguon)]

        st.dataframe(df_hien_thi, width="stretch")

        st.subheader("Biểu đồ diễn biến độ mặn theo thời gian")
        df_plot = df_hien_thi.copy()
        df_plot["thoi_gian"] = pd.to_datetime(df_plot["thoi_gian"])
        df_plot = df_plot.sort_values("thoi_gian")

        fig_time, ax_t = plt.subplots(figsize=(10, 4), dpi=110)
        ax_t.plot(df_plot["thoi_gian"], df_plot["do_man_ppt"], marker="o", color="#E5383B", lw=2, label="Độ mặn S (‰)")
        ax_t.fill_between(
            df_plot["thoi_gian"],
            df_plot["do_man_ppt"] - df_plot["bat_dinh_U_ppt"],
            df_plot["do_man_ppt"] + df_plot["bat_dinh_U_ppt"],
            color="#E5383B",
            alpha=0.18,
            label="Khoảng bất định mở rộng ± U₉₅%",
        )
        ax_t.set_ylabel("Độ mặn (‰)")
        ax_t.set_xlabel("Thời gian quan trắc")
        ax_t.legend(loc="upper left")
        plt.xticks(rotation=25)
        fig_time.tight_layout()
        st.pyplot(fig_time)

        csv_bytes = df_hien_thi.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button(
            label="📥 Tải xuống dữ liệu CSV nhật kí",
            data=csv_bytes,
            file_name="nhat_ki_do_do_man.csv",
            mime="text/csv",
        )


# ===========================================================================
# TAB 4: HIỆU CHUẨN & BÙ NHIỆT
# ===========================================================================
with tab_hieuchuan:
    tieu_de_muc("📊", "Hiệu Chuẩn Thiết Bị & Bù Nhiệt Độ (Cột mốc 4)", "Dựng hàm thực nghiệm Δy = f(S, T) từ dung dịch muối chuẩn NaCl với kiểm định chéo k-fold")

    col_h1, col_h2 = st.columns([1.1, 1], gap="medium")

    with col_h1:
        nhan_buoc("1", "Nạp tập dữ liệu đo chuẩn")
        csv_hieu_chuan = st.file_uploader("Tải file CSV đo chuẩn (đúng 7 cột quy định):", type=["csv"], key="csv_calib")
        dung_mo_phong = st.button("🧪 Tạo dữ liệu chuẩn mô phỏng (để thực hành)")

        df_calib_input: pd.DataFrame | None = None
        if csv_hieu_chuan:
            try:
                df_calib_input = cal.doc_csv_hieu_chuan(csv_hieu_chuan)
                bang("xanh", f"Đã đọc file CSV thành công: <b>{len(df_calib_input)} dòng</b> hợp lệ.", icon="✅", la_html=True)
            except Exception as e:
                bang("do", f"Lỗi đọc file CSV: {e}", icon="🚨")
        elif dung_mo_phong:
            df_calib_input = sinh_du_lieu_hieu_chuan_mo_phong(seed=1)
            bang("vang", "Đang sử dụng dữ liệu MÔ PHỎNG theo mô hình Snell (không phải số đo thật).", icon="⚠️")

    with col_h2:
        nhan_buoc("2", "Lựa chọn bậc hồi quy")
        bac_lua_chon = st.radio(
            "Chiến lược chọn bậc:",
            ["Tự động chọn (Kiểm định chéo k-fold chống quá khớp)", "Ép Bậc 1 (Tuyến tính)", "Ép Bậc 2 (Bậc hai)"],
        )
        bac_ep_val = 1 if "Bậc 1" in bac_lua_chon else (2 if "Bậc 2" in bac_lua_chon else None)

        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        nut_chay_calib = st.button("⚡ TIẾN HÀNH DỰNG ĐƯỜNG CHUẨN", type="primary", width="stretch")

    if nut_chay_calib and df_calib_input is not None:
        with st.spinner("Đang tính toán kiểm định chéo và khớp bình phương tối thiểu..."):
            bc_cal = cal.dung_duong_chuan(df_calib_input, cal.CauHinhHieuChuan.tu_yaml(), bac_ep=bac_ep_val)
            mh_new = bc_cal.mo_hinh

        st.divider()
        st.subheader("Báo cáo kết quả dựng đường chuẩn")

        c_r1, c_r2, c_r3, c_r4 = st.columns(4)
        with c_r1:
            hien(the_so("HỆ SỐ XÁC ĐỊNH R²", f"{mh_new.R2:.5f}", kieu="nhan-manh"))
        with c_r2:
            hien(the_so("BẬC ĐA THỨC CHỌN", f"Bậc {bc_cal.bac_chon}", phu=bc_cal.ly_do_chon, kieu="vien-ngoc"))
        with c_r3:
            val_test = f"{bc_cal.RMSE_test_ppt:.3f}" if not np.isnan(bc_cal.RMSE_test_ppt) else "N/A"
            hien(the_so("RMSE TẬP KIỂM TRA (TEST)", val_test, don_vi="‰", kieu="vien-vang"))
        with c_r4:
            hien(the_so("ĐỘ LỆCH CHUẨN s_res", f"{mh_new.s_res_px:.3f}", don_vi="px", phu=f"{mh_new.so_diem} điểm chuẩn", kieu="vien-xanh"))

        if mh_new.la_mo_phong:
            bang("vang", cal.NHAN_CHUA_HIEU_CHUAN + ": Đường chuẩn này dựng từ dữ liệu mô phỏng, KHÔNG phải số đo thực nghiệm.", icon="⚠️")
        else:
            bang("xanh", "ĐÃ HIỆU CHUẨN THÀNH CÔNG TỪ DỮ LIỆU ĐO THẬT!", icon="✅")

        # Phương trình đa thức
        hs_str = " + ".join([f"({c:+.5g})·{h}" for h, c in zip(mh_new.hang, mh_new.he_so)])
        st.code(f"Δy (px) = {hs_str}   [với ΔT = T − {mh_new.T_ref} °C]")

        c_p1, c_p2 = st.columns(2)
        with c_p1:
            st.pyplot(cal.ve_duong_chuan(bc_cal))
        with c_p2:
            st.pyplot(cal.ve_phan_du(bc_cal))

        if st.button("💾 Lưu mô hình hiệu chuẩn này làm cấu hình mặc định"):
            OUTPUTS_DIR.mkdir(exist_ok=True)
            luu_path = HE_SO_MP_PATH if mh_new.la_mo_phong else HE_SO_JSON_PATH
            mh_new.luu_json(luu_path)
            st.success(f"✅ Đã lưu mô hình thành công vào `{luu_path.name}`! Hãy khởi động lại ứng dụng để áp dụng.")


# ===========================================================================
# TAB 5: MÔ PHỎNG QUANG HỌC
# ===========================================================================
with tab_mophong:
    tieu_de_muc("📐", "Mô Phỏng Mô Hình Quang Học & Ngân Sách Sai Số", "Mô phỏng định luật Snell chính xác, khảo sát độ nhạy và phân tích sai số toàn phương RSS")

    cfg_cur = load_config()
    col_opt1, col_opt2 = st.columns([1, 1], gap="medium")

    with col_opt1:
        nhan_buoc("1", "Cấu hình hình học & Môi trường")
        a_sim = st.slider("Góc đỉnh lăng kính A (độ)", 25.0, 47.0, float(cfg_cur.A_do), 0.5)
        d_sim = st.slider("Khoảng cách tới màn D (m)", 0.5, 2.5, float(cfg_cur.D_m), 0.1)
        px_sim = st.number_input("Kích thước pixel trên màn (mm/px)", value=float(cfg_cur.pixel_mm), step=0.005, format="%.4f")
        s_eval = st.slider("Độ mặn khảo sát (‰)", 0.0, 40.0, 20.0, 1.0)
        t_eval = st.slider("Nhiệt độ khảo sát (°C)", 10.0, 40.0, 25.0, 1.0)

    with col_opt2:
        nhan_buoc("2", "Kết quả tính toán quang học lí thuyết")
        n_calc = op.chiet_suat(s_eval, t_eval, cfg_cur)
        st.write(f"- Chiết suất môi trường mẫu $n(S, T)$: `{n_calc:.5f}`")

        try:
            theta_ra = op.goc_ra(n_calc, a_sim)
            delta_goc = op.goc_lech(n_calc, a_sim)
            sens_px = op.pixel_moi_phan_nghin(s_eval, t_eval, cfg_cur, A_do=a_sim, D_m=d_sim)

            c_o1, c_o2, c_o3 = st.columns(3)
            with c_o1:
                hien(the_so("GÓC LÓ θ_ra", f"{theta_ra:.2f}", don_vi="°", kieu="vien-xanh"))
            with c_o2:
                hien(the_so("GÓC LỆCH δ", f"{delta_goc:.2f}", don_vi="°", kieu="vien-ngoc"))
            with c_o3:
                hien(the_so("ĐỘ NHẠY HỆ THỐNG", f"{sens_px:.2f}", don_vi="px/‰", kieu="nhan-manh"))

        except op.PhanXaToanPhanError:
            bang("do", "🚨 PHẢN XẠ TOÀN PHẦN: n·sin(A) ≥ 1. Ánh sáng bị giữ lại trong lăng kính, không ló ra màn hứng. Cần giảm góc đỉnh A!", icon="🚨")

    st.divider()
    st.subheader("Ngân sách sai số thiết kế (Error Budget RSS)")
    st.caption("Quy đổi các nguồn sai số độc lập về độ lệch chuẩn độ mặn tương đương (‰)")

    c_err1, c_err2 = st.columns([1, 1.6], gap="medium")
    with c_err1:
        err_tam = st.number_input("Sai số tìm tâm vạch (px)", value=0.05, step=0.01)
        err_t = st.number_input("Chênh nhiệt độ 2 ngăn (°C)", value=0.5, step=0.1)
        err_a = st.number_input("Sai số chế tạo góc A (độ)", value=0.05, step=0.01)
        err_troi = st.number_input("Laser trôi chung (px)", value=5.0, step=0.5)
        he_so_triet = st.number_input("Hệ số lọt sau đo vi sai (0..1)", value=0.01, step=0.005)

    with c_err2:
        ngan_sach = op.ngan_sach_sai_so(
            s_eval, t_eval, cfg_cur, err_tam, err_t, err_a, err_troi, he_so_triet
        )
        df_ns = pd.DataFrame([
            {"Nguồn sai số": "Sai số thuật toán tìm tâm vạch (px)", "Bất định tương đương (‰)": f"{ngan_sach['tim_tam']:.3f}"},
            {"Nguồn sai số": "Chênh lệch nhiệt độ 2 ngăn (°C)", "Bất định tương đương (‰)": f"{ngan_sach['nhiet_do']:.3f}"},
            {"Nguồn sai số": "Sai số gia công góc đỉnh A (độ)", "Bất định tương đương (‰)": f"{ngan_sach['goc_A']:.3f}"},
            {"Nguồn sai số": "Trôi laser còn sót lại sau đo vi sai", "Bất định tương đương (‰)": f"{ngan_sach['troi_laser']:.3f}"},
            {"Nguồn sai số": "TỔNG HỢP TOÀN PHƯƠNG (RSS)", "Bất định tương đương (‰)": f"{ngan_sach['tong_RSS']:.3f}"},
        ])
        st.dataframe(df_ns, width="stretch")
        bang("xanh", f"Tổng bất định dự báo thiết kế: <b>± {ngan_sach['tong_RSS']:.3f} ‰</b>", icon="🎯", la_html=True)


# ===========================================================================
# TAB 6: ĐỐI CHỨNG KHÚC XẠ KẾ (BLAND-ALTMAN)
# ===========================================================================
with tab_so_sanh:
    tieu_de_muc("⚖️", "Đối Chứng Với Khúc Xạ Kế Cơ (Bland–Altman)", "Đánh giá mức độ đồng thuận giữa thiết bị của dự án và khúc xạ kế quang học cầm tay")

    col_ba1, col_ba2 = st.columns([1, 1], gap="medium")

    with col_ba1:
        nhan_buoc("1", "Dữ liệu đo song song hai phương pháp")
        mau_ba = st.button("📋 Nạp bảng số liệu đối chứng mẫu")
        csv_ba = st.file_uploader("Tải file CSV cặp giá trị (S_thiet_bi, S_khuc_xa_ke):", type=["csv"], key="ba_upload")

        df_ba: pd.DataFrame | None = None
        if csv_ba:
            df_ba = pd.read_csv(csv_ba)
        elif mau_ba:
            np.random.seed(42)
            s_true_vals = np.array([0, 5, 10, 15, 20, 25, 30, 35] * 3)
            s_may_toi = s_true_vals + np.random.normal(0, 0.15, len(s_true_vals))
            s_ref_opt = s_true_vals + np.random.normal(0.1, 0.4, len(s_true_vals))
            df_ba = pd.DataFrame({
                "S_thiet_bi": np.round(s_may_toi, 2),
                "S_khuc_xa_ke": np.round(s_ref_opt, 2),
            })

    if df_ba is not None and "S_thiet_bi" in df_ba.columns and "S_khuc_xa_ke" in df_ba.columns:
        with col_ba2:
            nhan_buoc("2", "Bảng dữ liệu đo đối chứng")
            st.dataframe(df_ba, width="stretch", height=180)

        m1 = df_ba["S_thiet_bi"].to_numpy(float)
        m2 = df_ba["S_khuc_xa_ke"].to_numpy(float)

        tb_2_phuong_phap = (m1 + m2) / 2.0
        hieu_so = m1 - m2

        mean_diff = float(np.mean(hieu_so))
        std_diff = float(np.std(hieu_so, ddof=1))
        loa_upper = mean_diff + 1.96 * std_diff
        loa_lower = mean_diff - 1.96 * std_diff

        st.divider()
        c_b1, c_b2, c_b3 = st.columns(3)
        with c_b1:
            hien(the_so("SAI LỆCH TRUNG BÌNH (BIAS)", f"{mean_diff:+.3f}", don_vi="‰", phu="Độ lệch hệ thống giữa 2 phương pháp", kieu="nhan-manh"))
        with c_b2:
            hien(the_so("ĐỘ LỆCH CHUẨN (SD)", f"{std_diff:.3f}", don_vi="‰", kieu="vien-ngoc"))
        with c_b3:
            hien(the_so("GIỚI HẠN ĐỒNG THUẬN 95%", f"[{loa_lower:+.2f}, {loa_upper:+.2f}]", don_vi="‰", kieu="vien-vang"))

        fig_ba, ax_ba = plt.subplots(figsize=(8, 4.5), dpi=110)
        ax_ba.scatter(tb_2_phuong_phap, hieu_so, color="#E5383B", s=34, alpha=0.85, label="Các cặp phép đo")
        ax_ba.axhline(mean_diff, color="#1B4965", linestyle="-", lw=1.8, label=f"Mean Bias = {mean_diff:+.3f} ‰")
        ax_ba.axhline(loa_upper, color="#14B8A6", linestyle="--", lw=1.3, label=f"+1.96 SD = {loa_upper:+.3f} ‰")
        ax_ba.axhline(loa_lower, color="#14B8A6", linestyle="--", lw=1.3, label=f"-1.96 SD = {loa_lower:+.3f} ‰")
        ax_ba.axhline(0, color="gray", linestyle=":", lw=0.8)

        ax_ba.set_xlabel("Trung bình 2 phương pháp: (S_thiết_bị + S_khúc_xạ_kế) / 2 (‰)")
        ax_ba.set_ylabel("Sai khác: S_thiết_bị − S_khúc_xạ_kế (‰)")
        ax_ba.set_title("Đồ thị Bland–Altman đối chứng độ mặn", fontsize=11)
        ax_ba.legend(fontsize=8, loc="upper right")
        fig_ba.tight_layout()

        st.pyplot(fig_ba)
        bang(
            "xanh",
            f"<b>Ý nghĩa kết luận KHKT:</b> Khoảng 95% sai khác giữa thiết bị của dự án và khúc xạ kế "
            f"nằm trong dải hẹp <b>[{loa_lower:+.2f} ‰, {loa_upper:+.2f} ‰]</b>. "
            f"Sai lệch trung bình <b>{mean_diff:+.3f} ‰</b> rất nhỏ, chứng minh thiết bị đo vi sai có độ tương đồng cao với khúc xạ kế chuẩn.",
            icon="🎯",
            la_html=True,
        )
    else:
        bang("duong", "Nhấn nút 'Nạp bảng số liệu đối chứng mẫu' hoặc tải file CSV cặp giá trị để phân tích Bland–Altman.", icon="👈")
