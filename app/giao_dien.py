"""Thành phần giao diện dùng chung: CSS chủ đề "tia laser" và các thẻ HTML nhỏ.

Mô-đun này CHỈ phục vụ trình bày, KHÔNG chứa tính toán vật lí. Mọi con số hiển thị
đều được truyền vào từ các mô-đun core/ (phép đo hoặc đường chuẩn).
"""
from __future__ import annotations

import html

import streamlit as st

# Bảng màu chủ đạo (đỏ laser 650 nm + xanh đêm của phòng thí nghiệm tối)
MAU = {
    "do_laser": "#E5383B",
    "hong": "#C81D6B",
    "xanh_dem": "#0B1D3A",
    "xanh_bien": "#1B4965",
    "ngoc": "#14B8A6",
    "vang": "#F59E0B",
    "xanh_la": "#16A34A",
    "xam": "#64748B",
}

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700;800&display=swap');
html { font-size: 17px; }
.stApp { font-family: 'Be Vietnam Pro', 'Segoe UI', system-ui, -apple-system, sans-serif;
  background: radial-gradient(circle at 100% 0%, #FDECEC 0, transparent 28%), #F4F6FB; }
.block-container { padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1280px; }
#MainMenu, footer { visibility: hidden; }

/* ---------- Banner đầu trang ---------- */
.hero { position: relative; overflow: hidden; border-radius: 24px; padding: 30px 34px 44px; color: #fff;
  background: radial-gradient(circle at 88% 15%, rgba(229,56,59,.45), transparent 42%),
              radial-gradient(circle at 10% 110%, rgba(20,184,166,.25), transparent 40%),
              linear-gradient(135deg, #0B1D3A 0%, #13315C 55%, #1B4965 100%);
  box-shadow: 0 22px 44px -22px rgba(11,29,58,.75); margin-bottom: 20px; }
.hero-kicker { font-size: .78rem; letter-spacing: .18em; text-transform: uppercase; color: #FCA5A5; font-weight: 700; }
.hero-title { font-size: 2.05rem; font-weight: 800; line-height: 1.2; margin: 6px 0 8px; letter-spacing: -.5px; color: #fff; }
.hero-sub { font-size: 1.02rem; color: #CBD5E1; max-width: 760px; }
.hero-badges { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }
.tia { position: absolute; height: 3px; border-radius: 3px;
  background: linear-gradient(90deg, transparent, #ff4d4f 15%, #ffb3b3 50%, #ff4d4f 85%, transparent);
  box-shadow: 0 0 14px 3px rgba(255,77,79,.75); animation: nhap-nhay 3.2s ease-in-out infinite; }
.tia.t1 { left: -4%; width: 50%; bottom: 26px; }
.tia.t2 { left: 52%; width: 52%; bottom: 12px; animation-delay: 1.1s; }
.tia-dy { position: absolute; left: 50.5%; bottom: 12px; height: 15px; border-left: 2px dashed #FDE047; }
.tia-dy-nhan { position: absolute; left: 51.5%; bottom: 10px; font-size: .72rem; color: #FDE047; font-weight: 700; }
@keyframes nhap-nhay { 0%,100% { opacity: .55; } 50% { opacity: 1; } }

/* ---------- Huy hiệu ---------- */
.huy-hieu { display: inline-flex; align-items: center; gap: 6px; padding: 5px 12px; border-radius: 999px;
  font-size: .8rem; font-weight: 600; border: 1px solid transparent; line-height: 1.3; }
.hh-do { background: #FDECEC; color: #B42318; border-color: #F8C9C9; }
.hh-xanh { background: #E7F6EC; color: #166534; border-color: #BFE6CB; }
.hh-vang { background: #FEF6E3; color: #92400E; border-color: #F8DFA6; }
.hh-xam { background: #EEF1F5; color: #334155; border-color: #D9DEE6; }
.hh-duong { background: #EAF2FF; color: #1E3A8A; border-color: #C7DBFF; }
.hh-trong { background: rgba(255,255,255,.12); color: #fff; border-color: rgba(255,255,255,.28); }

/* ---------- Tiêu đề mục ---------- */
.muc { display: flex; align-items: center; gap: 14px; margin: 4px 0 16px; }
.muc-icon { flex: 0 0 48px; height: 48px; border-radius: 14px; display: grid; place-items: center; font-size: 1.45rem;
  background: linear-gradient(135deg, #FDECEC, #FFE4F1); box-shadow: inset 0 0 0 1px #F8C9C9; }
.muc-tt { font-size: 1.4rem; font-weight: 800; color: #0B1D3A; line-height: 1.2; }
.muc-mt { font-size: .92rem; color: #64748B; margin-top: 2px; }
.nhan-buoc { display: inline-flex; align-items: center; gap: 8px; font-weight: 700; color: #0B1D3A; margin: 4px 0 8px; }
.nhan-buoc span { width: 26px; height: 26px; border-radius: 50%; display: grid; place-items: center; font-size: .82rem;
  color: #fff; background: linear-gradient(135deg, #E5383B, #C81D6B); }

/* ---------- Thẻ số liệu ---------- */
.the { background: #fff; border: 1px solid #E6EAF0; border-radius: 20px; padding: 18px 20px 16px;
  box-shadow: 0 10px 24px -18px rgba(15,23,42,.35); height: 100%; margin-bottom: 10px; }
.the-nhan { font-size: .74rem; text-transform: uppercase; letter-spacing: .07em; color: #64748B; font-weight: 700; }
.the-so { font-size: 2.35rem; font-weight: 800; color: #0B1D3A; line-height: 1.15; margin-top: 6px; }
.the-so small { font-size: 1rem; font-weight: 600; color: #475569; margin-left: 4px; }
.the-pm { font-size: 1.08rem; font-weight: 700; color: #E5383B; margin-top: 2px; }
.the-phu { font-size: .84rem; color: #64748B; margin-top: 8px; }
.the.vien-do { border-top: 4px solid #E5383B; }
.the.vien-ngoc { border-top: 4px solid #14B8A6; }
.the.vien-vang { border-top: 4px solid #F59E0B; }
.the.vien-xanh { border-top: 4px solid #1B4965; }
.the.nhan-manh { border: none; background: linear-gradient(135deg, #E5383B 0%, #C81D6B 100%);
  box-shadow: 0 18px 34px -18px rgba(229,56,59,.9); }
.the.nhan-manh .the-nhan, .the.nhan-manh .the-so, .the.nhan-manh small,
.the.nhan-manh .the-pm, .the.nhan-manh .the-phu { color: #fff; }
.the.nhan-manh .the-pm { background: rgba(255,255,255,.18); display: inline-block; padding: 2px 10px; border-radius: 999px; }

/* ---------- Thẻ trạng thái loài ---------- */
.the-tt { border-radius: 20px; padding: 20px 22px; color: #fff; margin-bottom: 12px; }
.the-tt .tt-nhan { font-size: .78rem; letter-spacing: .1em; text-transform: uppercase; opacity: .9; font-weight: 700; }
.the-tt .tt-tieu-de { font-size: 1.35rem; font-weight: 800; margin: 4px 0 6px; line-height: 1.25; }
.the-tt .tt-noi-dung { font-size: .95rem; opacity: .95; }

/* ---------- Dải thông báo ---------- */
.bang { border-radius: 14px; padding: 12px 16px; display: flex; gap: 10px; align-items: flex-start;
  margin: 6px 0 12px; font-size: .93rem; line-height: 1.5; }
.bang-icon { font-size: 1.15rem; line-height: 1.3; }
.bang-do { background: #FDECEC; color: #7A1A12; border: 1px solid #F8C9C9; }
.bang-vang { background: #FEF6E3; color: #7C3A0B; border: 1px solid #F8DFA6; }
.bang-xanh { background: #E7F6EC; color: #14532D; border: 1px solid #BFE6CB; }
.bang-duong { background: #EAF2FF; color: #1E3A8A; border: 1px solid #C7DBFF; }

/* ---------- Thẻ bước hướng dẫn ---------- */
.buoc { display: flex; gap: 14px; padding: 14px 16px; border-radius: 16px; background: #fff;
  border: 1px solid #E6EAF0; margin-bottom: 10px; }
.buoc-so { flex: 0 0 34px; height: 34px; border-radius: 50%; display: grid; place-items: center; font-weight: 800;
  color: #fff; background: linear-gradient(135deg, #E5383B, #C81D6B); }
.buoc-tt { font-weight: 700; color: #0B1D3A; margin-bottom: 2px; }
.buoc-nd { font-size: .92rem; color: #334155; line-height: 1.55; }

/* ---------- Hướng dẫn nhanh (hộp thoại) ---------- */
.hd-cham { display: flex; gap: 6px; justify-content: center; margin: 2px 0 14px; }
.hd-cham i { width: 9px; height: 9px; border-radius: 50%; background: #E2E8F0; display: block; }
.hd-cham i.on { width: 26px; border-radius: 9px; background: linear-gradient(90deg, #E5383B, #C81D6B); }
.hd-dau { text-align: center; }
.hd-icon { font-size: 2.6rem; line-height: 1; }
.hd-tt { font-size: 1.35rem; font-weight: 800; color: #0B1D3A; margin: 6px 0 2px; }
.hd-mt { color: #64748B; font-size: .92rem; margin-bottom: 10px; }
.minh-hoa { position: relative; height: 120px; border-radius: 16px; margin: 6px 0 14px; overflow: hidden;
  background: radial-gradient(circle at 80% 20%, rgba(229,56,59,.35), transparent 50%), #0B1D3A; }
.minh-hoa .v { position: absolute; height: 4px; border-radius: 4px; width: 38%;
  background: linear-gradient(90deg, #ff4d4f, #ffb3b3, #ff4d4f); box-shadow: 0 0 14px 3px rgba(255,77,79,.75); }
.minh-hoa .v1 { left: 7%; top: 40%; }
.minh-hoa .v2 { left: 55%; top: 70%; }
.minh-hoa .dy { position: absolute; left: 51%; top: 40%; height: 30%; border-left: 2px dashed #FDE047; }
.minh-hoa .dy-nhan { position: absolute; left: 52.5%; top: 48%; color: #FDE047; font-weight: 800; font-size: .9rem; }
.minh-hoa .n1, .minh-hoa .n2 { position: absolute; color: #CBD5E1; font-size: .76rem; }
.minh-hoa .n1 { left: 7%; top: 16%; }
.minh-hoa .n2 { left: 55%; top: 82%; }

/* ---------- Thanh tab ---------- */
.stTabs [data-baseweb="tab-list"] { gap: 6px; flex-wrap: wrap; border-bottom: none; }
.stTabs [data-baseweb="tab"] { background: #fff; border: 1px solid #E6EAF0; border-radius: 12px; height: auto;
  padding: 9px 15px; font-weight: 600; box-shadow: 0 4px 10px -8px rgba(15,23,42,.3); }
.stTabs [data-baseweb="tab"] p { font-size: .92rem; font-weight: 600; }
.stTabs [aria-selected="true"] { background: linear-gradient(135deg, #E5383B, #C81D6B); border-color: transparent;
  box-shadow: 0 10px 20px -12px rgba(229,56,59,.95); }
.stTabs [aria-selected="true"] p { color: #fff !important; }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display: none; }
.stTabs [data-baseweb="tab-panel"] { padding-top: 18px; }

/* ---------- Nút bấm, ô nhập, khung ---------- */
.stButton > button, .stDownloadButton > button { border-radius: 12px; font-weight: 700; min-height: 2.8rem;
  transition: transform .08s ease, box-shadow .2s ease; }
.stButton > button:hover, .stDownloadButton > button:hover { transform: translateY(-1px); }
.stButton > button[kind="primary"] { background: linear-gradient(135deg, #E5383B, #C81D6B); border: none;
  box-shadow: 0 12px 24px -14px rgba(229,56,59,.95); }
[data-testid="stMetric"] { background: #fff; border: 1px solid #E6EAF0; border-radius: 16px; padding: 14px 16px; }
[data-testid="stExpander"] details { border-radius: 14px; background: #fff; }
[data-testid="stFileUploaderDropzone"] { border-radius: 14px; }
[data-testid="stImage"] img { border-radius: 14px; }

/* ---------- Thanh bên ---------- */
[data-testid="stSidebar"] { background: linear-gradient(180deg, #0B1D3A 0%, #13315C 100%); }
[data-testid="stSidebar"] p, [data-testid="stSidebar"] li, [data-testid="stSidebar"] span,
[data-testid="stSidebar"] label, [data-testid="stSidebar"] div { color: #E2E8F0; }
[data-testid="stSidebar"] .stButton > button { background: rgba(255,255,255,.1); border: 1px solid rgba(255,255,255,.28); }
[data-testid="stSidebar"] .stButton > button p { color: #fff; }
[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,.15); }
.sb-logo { font-size: 1.3rem; font-weight: 800; color: #fff; line-height: 1.25; }
.sb-logo b { color: #FCA5A5; }
.sb-the { background: rgba(255,255,255,.07); border: 1px solid rgba(255,255,255,.15); border-radius: 14px;
  padding: 12px 14px; font-size: .86rem; line-height: 1.55; margin: 8px 0; }
.sb-the .sb-tt { font-weight: 700; color: #fff; margin-bottom: 4px; }

/* ---------- Điện thoại ---------- */
@media (max-width: 640px) {
  html { font-size: 16px; }
  .hero { padding: 22px 20px 40px; border-radius: 18px; }
  .hero-title { font-size: 1.45rem; }
  .the-so { font-size: 1.95rem; }
  .stTabs [data-baseweb="tab"] { padding: 7px 10px; }
  .stTabs [data-baseweb="tab"] p { font-size: .8rem; }
}
"""


def _gon(s: str) -> str:
    """Ghép HTML nhiều dòng thành một dòng (tránh Markdown hiểu dòng thụt lề là khối code)."""
    return " ".join(dong.strip() for dong in s.splitlines() if dong.strip())


def e(x: object) -> str:
    """Thoát kí tự HTML cho chuỗi do người dùng hoặc mô-đun khác cung cấp (vd. dấu '<')."""
    return html.escape(str(x))


def hien(html_str: str, noi=None) -> None:
    """Hiển thị một đoạn HTML (trong st hoặc trong một cột/khung `noi`)."""
    (noi or st).markdown(_gon(html_str), unsafe_allow_html=True)


def nap_giao_dien() -> None:
    """Nạp CSS chủ đề và kiểu đồ thị Matplotlib thống nhất."""
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)
    _kieu_do_thi()


def _kieu_do_thi() -> None:
    import matplotlib as mpl

    mpl.rcParams.update({
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.edgecolor": "#CBD5E1", "axes.labelcolor": "#334155",
        "axes.titleweight": "bold", "axes.titlesize": 11, "axes.titlecolor": "#0B1D3A",
        "axes.grid": True, "grid.color": "#E2E8F0", "grid.linestyle": "--", "grid.alpha": 1.0,
        "xtick.color": "#475569", "ytick.color": "#475569",
        "axes.prop_cycle": mpl.cycler(color=["#E5383B", "#1B4965", "#14B8A6", "#F59E0B", "#8B5CF6", "#64748B"]),
        "figure.facecolor": "white", "axes.facecolor": "white",
        "legend.frameon": False, "font.size": 10,
    })


def huy_hieu(text: str, loai: str = "xam", icon: str = "") -> str:
    """HTML một huy hiệu bo tròn. loai: do | xanh | vang | xam | duong | trong."""
    return f'<span class="huy-hieu hh-{loai}">{icon} {e(text)}</span>'


def hero(kicker: str, tieu_de: str, phu_de: str, huy_hieu_html: str = "") -> None:
    """Banner đầu trang với hai 'tia laser' lệch nhau Δy (minh hoạ nguyên lí vi sai)."""
    hien(f"""
    <div class="hero">
      <div class="hero-kicker">{e(kicker)}</div>
      <div class="hero-title">{e(tieu_de)}</div>
      <div class="hero-sub">{e(phu_de)}</div>
      <div class="hero-badges">{huy_hieu_html}</div>
      <div class="tia t1"></div><div class="tia t2"></div>
      <div class="tia-dy"></div><div class="tia-dy-nhan">Δy</div>
    </div>""")


def tieu_de_muc(icon: str, tieu_de: str, mo_ta: str = "", noi=None) -> None:
    hien(f"""
    <div class="muc"><div class="muc-icon">{icon}</div>
      <div><div class="muc-tt">{e(tieu_de)}</div><div class="muc-mt">{e(mo_ta)}</div></div>
    </div>""", noi)


def nhan_buoc(so: int | str, text: str, noi=None) -> None:
    hien(f'<div class="nhan-buoc"><span>{e(so)}</span>{e(text)}</div>', noi)


def the_so(nhan: str, gia_tri: str, don_vi: str = "", pm: str = "", phu: str = "", kieu: str = "") -> str:
    """HTML thẻ số liệu lớn. kieu: nhan-manh | vien-do | vien-ngoc | vien-vang | vien-xanh."""
    pm_html = f'<div class="the-pm">{e(pm)}</div>' if pm else ""
    phu_html = f'<div class="the-phu">{e(phu)}</div>' if phu else ""
    return f"""
    <div class="the {kieu}">
      <div class="the-nhan">{e(nhan)}</div>
      <div class="the-so">{e(gia_tri)}<small>{e(don_vi)}</small></div>
      {pm_html}{phu_html}
    </div>"""


def bang(loai: str, noi_dung: str, icon: str = "ℹ️", la_html: bool = False, noi=None) -> None:
    """Dải thông báo màu. loai: do | vang | xanh | duong. Mặc định thoát HTML nội dung."""
    nd = noi_dung if la_html else e(noi_dung)
    hien(f'<div class="bang bang-{loai}"><div class="bang-icon">{icon}</div><div>{nd}</div></div>', noi)


def buoc(so: int | str, tieu_de: str, noi_dung_html: str) -> str:
    """HTML thẻ một bước hướng dẫn (noi_dung_html là HTML tin cậy do lập trình viên viết)."""
    return f"""
    <div class="buoc"><div class="buoc-so">{e(so)}</div>
      <div><div class="buoc-tt">{e(tieu_de)}</div><div class="buoc-nd">{noi_dung_html}</div></div>
    </div>"""


@st.dialog("📖 HƯỚNG DẪN SỬ DỤNG HỆ THỐNG", width="large")
def hop_thoai_huong_dan() -> None:
    """Hộp thoại hướng dẫn sử dụng tự động mở lần đầu và xem lại bất kì lúc nào."""
    hien("""
    <div class="hd-dau">
      <div class="hd-icon">🔬</div>
      <div class="hd-tt">Thiết Bị Đo Độ Mặn Khúc Xạ Laser Vi Sai</div>
      <div class="hd-mt">Dành cho học sinh thuyết minh và người sử dụng hiện trường</div>
    </div>
    <div class="minh-hoa">
      <div class="n1">Ngăn Tham Chiếu (Nước cất)</div>
      <div class="v v1"></div>
      <div class="dy"></div>
      <div class="dy-nhan">Δy</div>
      <div class="v v2"></div>
      <div class="n2">Ngăn Mẫu (Nước mặn) ➜ Lệch đứng</div>
    </div>
    """)

    t1, t2, t3 = st.tabs([
        "⚡ 1. Nguyên lí vi sai",
        "📸 2. Quy trình đo 4 bước",
        "⚠️ 3. Lưu ý nghiên cứu",
    ])

    with t1:
        st.markdown("""
        **1. Khúc xạ Snell chính xác qua lăng kính tam giác:**
        - Tia laser đỏ ($650\\text{ nm}$) chiếu vuông góc mặt vào cuvet lăng kính đỉnh $A = 40^\\circ$.
        - Nước mặn có chiết suất $n > 1{,}333$, góc ló ra không khí lệch theo: $\\sin(\\theta_{ra}) = n \\cdot \\sin(A)$.
        - Tổng góc lệch $\\delta = \\theta_{ra} - A$, tạo độ dịch trên màn $D \\cdot \\tan(\\delta)$ với $D \\approx 1{,}0\\text{ m}$.

        **2. Cấu trúc vi sai hai ngăn:**
        - Ngăn trái: **Nước cất** ($S = 0\\text{ ‰}$) đóng kín làm chuẩn quang học.
        - Ngăn phải: **Mẫu nước cần đo**.
        - Tín hiệu là khoảng cách $\\Delta y = y_{mẫu} - y_{tc}$ giữa 2 vạch sáng. **Rung lắc tay cầm điện thoại hay laser bị trôi nhiệt đều tác động như nhau lên cả 2 vạch nên tự động triệt tiêu hoàn toàn!**
        """)

    with t2:
        hien(buoc(1, "Chuẩn bị phần cứng", "Bật laser vạch, căn vuông góc mặt cuvet. Ngăn tham chiếu đóng kín nước cất; ngăn mẫu tráng 2 lần bằng nước cần thử rồi châm đầy."))
        hien(buoc(2, "Chụp ảnh màn hứng (Tab 1)", "Đưa camera điện thoại chụp vuông góc vào màn hứng. <b>Tránh cháy sáng:</b> giảm EV nếu đỉnh vạch trắng lóa bệt ở mức 255."))
        hien(buoc(3, "Đo & Xem kết quả", "Nhập nhiệt độ nước mẫu đo bằng nhiệt kế ($^\\circ\\text{C}$), nhấn <b>🚀 TIẾN HÀNH ĐO</b>. Hệ thống tự ước lượng tâm dưới pixel và giải ngược độ mặn kèm bất định $\\pm U_{95\\%}$."))
        hien(buoc(4, "Cảnh báo & Nhật kí", "Chuyển sang <b>Tab 2</b> để kiểm tra ngưỡng an toàn cho tôm, cá hoặc cây trồng; bấm <b>Lưu Nhật Kí</b> để vẽ biểu đồ diễn biến theo thời gian."))

    with t3:
        st.warning("""
        **Quy tắc nghiên cứu khoa học bắt buộc:**
        1. **Không bịa số liệu:** Khi chưa nạp file đo dung dịch chuẩn thật, ứng dụng bắt buộc mang nhãn `CHƯA HIỆU CHUẨN – DỮ LIỆU MÔ PHỎNG`.
        2. **Độ mặn tương đương NaCl:** Đường chuẩn dựng bằng dung dịch muối NaCl tinh khiết. Nước tự nhiên có nhiều ion khác nên kết quả đo là độ mặn tương đương NaCl.
        3. **Chỉ số độ đục:** Là thước đo tương đối ($0\\text{--}1$) dựa vào độ phình FWHM của vạch sáng do tán xạ ánh sáng, tuyệt đối không quy đổi sang NTU khi chưa chuẩn hóa với dung dịch Formazin.
        """)

    st.divider()
    c_btn1, c_btn2 = st.columns([2, 1])
    with c_btn1:
        st.caption("💡 Bạn luôn có thể mở lại hướng dẫn này bằng nút **📖 Hướng dẫn sử dụng** ở thanh bên trái.")
    with c_btn2:
        if st.button("✅ Bắt đầu sử dụng ngay", type="primary", width="stretch"):
            st.session_state["da_xem_huong_dan"] = True
            st.session_state["mo_huong_dan"] = False
            st.rerun()


