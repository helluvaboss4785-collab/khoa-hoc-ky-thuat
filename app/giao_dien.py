"""Thành phần giao diện dùng chung: CSS chủ đề "tia laser", minh họa SVG quang học,
thanh trợ lý hướng dẫn thời gian thực và hộp thoại hướng dẫn tương tác.

Mô-đun này CHỈ phục vụ trình bày và trải nghiệm người dùng, KHÔNG tự bịa số liệu đo.
Mọi con số vật lí hiển thị đều được truyền vào từ các mô-đun core/ (optics, measure, calibration, thresholds).
"""
from __future__ import annotations

import html
import math

import streamlit as st

from core import optics as op
from core import thresholds as th

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
@import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap');
html { font-size: 16px; scroll-behavior: smooth; }
.stApp {
  font-family: 'Be Vietnam Pro', 'Segoe UI', system-ui, -apple-system, sans-serif;
  background-color: #EEF2F7;
  background-image:
    radial-gradient(circle at 96% 2%, rgba(229,56,59,.08) 0, transparent 28%),
    radial-gradient(circle at 4% 92%, rgba(20,184,166,.08) 0, transparent 30%),
    radial-gradient(rgba(15,23,42,.06) 1px, transparent 1px);
  background-size: 100% 100%, 100% 100%, 22px 22px;
}
[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 1.0rem; padding-bottom: 2.8rem; max-width: 1340px; }
#MainMenu, footer { visibility: hidden; }

/* ---------- Khung Panel 2.5D (st.container(border=True)) ---------- */
[data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stVerticalBlock"][class*="st-key-panel_"] {
  background: linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%) !important;
  border: 1.5px solid #CBD5E1 !important;
  border-radius: 20px !important;
  padding: 18px 20px !important;
  box-shadow:
    0 5px 0 #CBD5E1,
    0 12px 24px -8px rgba(15,23,42,.12),
    inset 0 1px 0 #FFFFFF !important;
}

/* ---------- Banner đầu trang 2.5D (Instrument Console Header) ---------- */
.hero {
  position: relative; overflow: hidden; border-radius: 22px; padding: 20px 26px 34px; color: #fff;
  background:
    radial-gradient(circle at 88% 18%, rgba(229,56,59,.42), transparent 40%),
    radial-gradient(circle at 12% 105%, rgba(20,184,166,.28), transparent 42%),
    linear-gradient(135deg, #071326 0%, #0B1D3A 50%, #163B5C 100%);
  box-shadow:
    0 7px 0 #040B16,
    0 22px 44px -16px rgba(11,29,58,.75),
    inset 0 1.5px 0 rgba(255,255,255,.16);
  margin-bottom: 14px; border: 1.5px solid rgba(255,255,255,.14);
}
.hero-grid { display: flex; justify-content: space-between; align-items: center; gap: 20px; flex-wrap: wrap; position: relative; z-index: 2; }
.hero-left { flex: 1 1 560px; }
.hero-right {
  flex: 0 0 296px;
  background: linear-gradient(180deg, rgba(15,35,68,.78) 0%, rgba(7,19,38,.9) 100%);
  border: 1.5px solid rgba(255,255,255,.18);
  border-radius: 16px; padding: 12px 15px; backdrop-filter: blur(8px);
  box-shadow: 0 4px 0 rgba(2,6,23,.65), inset 0 1px 0 rgba(255,255,255,.15);
}
.hero-kicker {
  display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px; border-radius: 999px;
  background: rgba(229,56,59,.24); border: 1px solid rgba(252,165,165,.42);
  font-size: .72rem; letter-spacing: .12em; text-transform: uppercase; color: #FECACA; font-weight: 700;
  box-shadow: 0 2px 0 rgba(127,29,29,.55), inset 0 1px 0 rgba(255,255,255,.2);
}
.hero-title { font-size: 1.78rem; font-weight: 800; line-height: 1.22; margin: 8px 0 6px; letter-spacing: -.4px; color: #fff; }
.hero-sub { font-size: .9rem; color: #CBD5E1; max-width: 780px; line-height: 1.5; }
.hero-badges { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 11px; }
.tia {
  position: absolute; height: 3px; border-radius: 3px;
  background: linear-gradient(90deg, transparent, #ff4d4f 15%, #ffb3b3 50%, #ff4d4f 85%, transparent);
  box-shadow: 0 0 14px 3px rgba(255,77,79,.75); animation: nhap-nhay 3.2s ease-in-out infinite;
}
.tia.t1 { left: -2%; width: 49%; bottom: 20px; }
.tia.t2 { left: 51%; width: 51%; bottom: 8px; animation-delay: 1.1s; }
.tia-dy { position: absolute; left: 49.5%; bottom: 8px; height: 13px; border-left: 2px dashed #FDE047; }
.tia-dy-nhan { position: absolute; left: 50.3%; bottom: 6px; font-size: .7rem; color: #FDE047; font-weight: 700; font-family: 'JetBrains Mono', monospace; }
@keyframes nhap-nhay { 0%,100% { opacity: .55; } 50% { opacity: 1; } }

/* ---------- Thanh Trợ lý Hướng dẫn Thời gian thực 2.5D (Compact Workflow Strip) ---------- */
.coach-wrap {
  background: linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%);
  border: 1.5px solid #CBD5E1; border-left: 6px solid #E5383B;
  border-radius: 18px; padding: 12px 16px; margin-bottom: 10px;
  box-shadow: 0 5px 0 #CBD5E1, 0 12px 24px -12px rgba(11,29,58,.22), inset 0 1px 0 #FFFFFF;
  position: relative;
}
.coach-head { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 9px; }
.coach-badge {
  display: inline-flex; align-items: center; gap: 7px;
  background: linear-gradient(180deg, #FF5255 0%, #E5383B 55%, #C81D55 100%);
  color: #fff; font-size: .72rem; font-weight: 800; text-transform: uppercase; letter-spacing: .07em;
  padding: 4px 12px; border-radius: 999px; border: 1px solid #9F1239;
  box-shadow: 0 3px 0 #881337, inset 0 1px 0 rgba(255,255,255,.35);
}
.coach-pulse {
  width: 7px; height: 7px; border-radius: 50%; background: #fff;
  box-shadow: 0 0 0 0 rgba(255,255,255,.8); animation: pulse-dot 1.6s infinite;
}
@keyframes pulse-dot {
  0% { box-shadow: 0 0 0 0 rgba(255,255,255,.85); }
  70% { box-shadow: 0 0 0 6px rgba(255,255,255,0); }
  100% { box-shadow: 0 0 0 0 rgba(255,255,255,0); }
}
.coach-steps {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 9px;
}
.c-step {
  display: flex; align-items: center; gap: 8px; padding: 7px 10px; border-radius: 12px;
  background: linear-gradient(180deg, #F8FAFC 0%, #EEF2F7 100%);
  border: 1.5px solid #CBD5E1; font-size: .79rem; color: #475569; font-weight: 700;
  box-shadow: 0 2.5px 0 #CBD5E1, inset 0 1px 0 #FFFFFF;
  transition: all .18s ease;
}
.c-step .c-num {
  flex: 0 0 22px; height: 22px; border-radius: 50%; display: grid; place-items: center;
  font-size: .72rem; font-weight: 800; background: #CBD5E1; color: #334155;
  box-shadow: inset 0 1px 2px rgba(15,23,42,.15);
}
.c-step.done {
  background: linear-gradient(180deg, #ECFDF5 0%, #D1FAE5 100%);
  border-color: #6EE7B7; color: #065F46; box-shadow: 0 2.5px 0 #10B981, inset 0 1px 0 #FFFFFF;
}
.c-step.done .c-num { background: #059669; color: #fff; box-shadow: 0 2px 0 #064E3B; }
.c-step.active {
  background: linear-gradient(180deg, #FFF1F2 0%, #FFE4E6 100%);
  border-color: #FDA4AF; color: #9F1239;
  box-shadow: 0 3px 0 #E5383B, 0 6px 12px -4px rgba(229,56,59,.25), inset 0 1px 0 #FFFFFF;
  transform: translateY(-1px);
}
.c-step.active .c-num {
  background: linear-gradient(180deg, #FF5255, #C81D55); color: #fff;
  box-shadow: 0 2px 0 #881337;
}
.coach-body {
  display: flex; align-items: center; gap: 12px;
  background: #F1F5F9; border: 1px solid #CBD5E1; border-radius: 12px; padding: 9px 13px;
  box-shadow: inset 0 2px 4px rgba(15,23,42,.06);
}
.coach-icon { font-size: 1.35rem; line-height: 1; flex-shrink: 0; }
.coach-msg-title { font-weight: 800; color: #0B1D3A; font-size: .9rem; margin-bottom: 1px; }
.coach-msg-desc { font-size: .82rem; color: #334155; line-height: 1.42; }

/* ---------- Huy hiệu 2.5D ---------- */
.huy-hieu {
  display: inline-flex; align-items: center; gap: 5px; padding: 4px 11px; border-radius: 999px;
  font-size: .76rem; font-weight: 700; border: 1.5px solid transparent; line-height: 1.3;
  box-shadow: 0 2.5px 0 rgba(15,23,42,.15), inset 0 1px 0 rgba(255,255,255,.65);
}
.hh-do { background: linear-gradient(180deg, #FEF2F2, #FEE2E2); color: #B42318; border-color: #FCA5A5; box-shadow: 0 2.5px 0 #EF4444, inset 0 1px 0 #FFF; }
.hh-xanh { background: linear-gradient(180deg, #ECFDF5, #D1FAE5); color: #166534; border-color: #6EE7B7; box-shadow: 0 2.5px 0 #10B981, inset 0 1px 0 #FFF; }
.hh-vang { background: linear-gradient(180deg, #FFFBEB, #FEF3C7); color: #92400E; border-color: #FCD34D; box-shadow: 0 2.5px 0 #D97706, inset 0 1px 0 #FFF; }
.hh-xam { background: linear-gradient(180deg, #F8FAFC, #E2E8F0); color: #334155; border-color: #CBD5E1; box-shadow: 0 2.5px 0 #94A3B8, inset 0 1px 0 #FFF; }
.hh-duong { background: linear-gradient(180deg, #EFF6FF, #DBEAFE); color: #1E3A8A; border-color: #93C5FD; box-shadow: 0 2.5px 0 #3B82F6, inset 0 1px 0 #FFF; }
.hh-trong {
  background: rgba(255,255,255,.15); color: #fff; border-color: rgba(255,255,255,.3); backdrop-filter: blur(4px);
  box-shadow: 0 2.5px 0 rgba(2,6,23,.5), inset 0 1px 0 rgba(255,255,255,.25);
}

/* ---------- Tiêu đề mục & Nhãn bước 2.5D ---------- */
.muc {
  display: flex; align-items: center; gap: 14px; margin: 2px 0 14px;
  padding: 10px 14px; border-radius: 16px;
  background: linear-gradient(180deg, #FFFFFF 0%, #F1F5F9 100%);
  border: 1.5px solid #CBD5E1;
  box-shadow: 0 4px 0 #CBD5E1, inset 0 1px 0 #FFFFFF;
}
.muc-icon {
  flex: 0 0 44px; height: 44px; border-radius: 13px; display: grid; place-items: center; font-size: 1.35rem;
  background: linear-gradient(180deg, #FFF1F2 0%, #FFE4E6 100%);
  border: 1.5px solid #FDA4AF;
  box-shadow: 0 4px 0 #F43F5E, inset 0 1.5px 0 #FFFFFF;
}
.muc-tt { font-size: 1.24rem; font-weight: 800; color: #0B1D3A; line-height: 1.22; }
.muc-mt { font-size: .86rem; color: #475569; margin-top: 2px; }
.nhan-buoc {
  display: flex; align-items: center; gap: 10px; font-weight: 800; color: #0B1D3A;
  margin: 0 0 12px; font-size: .92rem; padding: 6px 12px 6px 7px; border-radius: 12px;
  background: linear-gradient(180deg, #F8FAFC 0%, #EEF2F7 100%);
  border: 1px solid #CBD5E1;
  box-shadow: 0 2.5px 0 #CBD5E1, inset 0 1px 0 #FFFFFF;
}
.nhan-buoc span {
  flex: 0 0 26px; height: 26px; border-radius: 8px; display: grid; place-items: center; font-size: .78rem; font-weight: 800;
  color: #fff; background: linear-gradient(180deg, #FF5255, #E5383B, #C81D55);
  border: 1px solid #9F1239;
  box-shadow: 0 3px 0 #881337, inset 0 1px 0 rgba(255,255,255,.4);
}

/* ---------- Thẻ số liệu 2.5D (KPI Cards) ---------- */
.the {
  background: linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%);
  border: 1.5px solid #CBD5E1; border-radius: 18px; padding: 16px 18px 15px;
  box-shadow: 0 5px 0 #CBD5E1, 0 10px 20px -8px rgba(15,23,42,.14), inset 0 1px 0 #FFFFFF;
  height: 100%; margin-bottom: 10px;
  transition: transform .15s ease, box-shadow .15s ease;
}
.the:hover { transform: translateY(-2px); }
.the-nhan { font-size: .71rem; text-transform: uppercase; letter-spacing: .07em; color: #64748B; font-weight: 800; }
.the-so { font-size: 2.15rem; font-weight: 800; color: #0B1D3A; line-height: 1.15; margin-top: 6px; font-family: 'Be Vietnam Pro', sans-serif; }
.the-so small { font-size: .95rem; font-weight: 700; color: #475569; margin-left: 4px; }
.the-pm {
  display: inline-block; padding: 2px 10px; border-radius: 999px; margin-top: 5px;
  background: #FFF1F2; border: 1px solid #FECDD3; font-size: .92rem; font-weight: 700; color: #BE123C;
}
.the-phu { font-size: .8rem; color: #64748B; margin-top: 8px; line-height: 1.4; }
.the.vien-do {
  border-color: #FDA4AF; border-top: 3px solid #E5383B;
  box-shadow: 0 5px 0 #E5383B, 0 10px 20px -8px rgba(229,56,59,.22), inset 0 1px 0 #FFFFFF;
}
.the.vien-ngoc {
  border-color: #99F6E4; border-top: 3px solid #14B8A6;
  box-shadow: 0 5px 0 #0D9488, 0 10px 20px -8px rgba(20,184,166,.22), inset 0 1px 0 #FFFFFF;
}
.the.vien-ngoc .the-pm { background: #F0FDFA; border-color: #99F6E4; color: #0F766E; }
.the.vien-vang {
  border-color: #FDE68A; border-top: 3px solid #F59E0B;
  box-shadow: 0 5px 0 #D97706, 0 10px 20px -8px rgba(245,158,11,.22), inset 0 1px 0 #FFFFFF;
}
.the.vien-vang .the-pm { background: #FFFBEB; border-color: #FDE68A; color: #B45309; }
.the.vien-xanh {
  border-color: #BAE6FD; border-top: 3px solid #0284C7;
  box-shadow: 0 5px 0 #0284C7, 0 10px 20px -8px rgba(2,132,199,.22), inset 0 1px 0 #FFFFFF;
}
.the.vien-xanh .the-pm { background: #F0F9FF; border-color: #BAE6FD; color: #0369A1; }
.the.nhan-manh {
  border: 1.5px solid #991B1B;
  background: linear-gradient(145deg, #FF5255 0%, #E5383B 50%, #B91C1C 100%);
  box-shadow: 0 6px 0 #7F1D1D, 0 14px 28px -8px rgba(229,56,59,.5), inset 0 1.5px 0 rgba(255,255,255,.35);
}
.the.nhan-manh .the-nhan, .the.nhan-manh .the-so, .the.nhan-manh small,
.the.nhan-manh .the-pm, .the.nhan-manh .the-phu { color: #fff; }
.the.nhan-manh .the-pm {
  background: rgba(255,255,255,.22); border-color: rgba(255,255,255,.38);
  box-shadow: inset 0 1px 0 rgba(255,255,255,.25);
}

/* ---------- Dải thông báo 2.5D ---------- */
.bang {
  border-radius: 15px; padding: 11px 15px; display: flex; gap: 10px; align-items: flex-start;
  margin: 6px 0 10px; font-size: .89rem; line-height: 1.48;
  box-shadow: 0 3.5px 0 rgba(15,23,42,.12), inset 0 1px 0 rgba(255,255,255,.7);
}
.bang-icon { font-size: 1.12rem; line-height: 1.3; flex-shrink: 0; }
.bang-do { background: linear-gradient(180deg, #FEF2F2, #FEE2E2); color: #7A1A12; border: 1.5px solid #FCA5A5; box-shadow: 0 3.5px 0 #EF4444, inset 0 1px 0 #FFF; }
.bang-vang { background: linear-gradient(180deg, #FFFBEB, #FEF3C7); color: #7C3A0B; border: 1.5px solid #FCD34D; box-shadow: 0 3.5px 0 #D97706, inset 0 1px 0 #FFF; }
.bang-xanh { background: linear-gradient(180deg, #ECFDF5, #D1FAE5); color: #14532D; border: 1.5px solid #6EE7B7; box-shadow: 0 3.5px 0 #10B981, inset 0 1px 0 #FFF; }
.bang-duong { background: linear-gradient(180deg, #EFF6FF, #DBEAFE); color: #1E3A8A; border: 1.5px solid #93C5FD; box-shadow: 0 3.5px 0 #3B82F6, inset 0 1px 0 #FFF; }

/* ---------- Thẻ bước hướng dẫn 2.5D ---------- */
.buoc {
  display: flex; gap: 14px; padding: 14px 16px; border-radius: 16px;
  background: linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%);
  border: 1.5px solid #CBD5E1; margin-bottom: 10px;
  box-shadow: 0 4px 0 #CBD5E1, 0 8px 16px -10px rgba(15,23,42,.16), inset 0 1px 0 #FFFFFF;
}
.buoc-so {
  flex: 0 0 34px; height: 34px; border-radius: 10px; display: grid; place-items: center; font-weight: 800;
  color: #fff; background: linear-gradient(180deg, #FF5255, #E5383B, #C81D55);
  border: 1px solid #9F1239; box-shadow: 0 3px 0 #881337, inset 0 1px 0 rgba(255,255,255,.35);
}
.buoc-tt { font-weight: 700; color: #0B1D3A; margin-bottom: 2px; }
.buoc-nd { font-size: .89rem; color: #334155; line-height: 1.52; }

/* ---------- Hộp thoại Hướng dẫn Tương tác (Onboarding Modal) ---------- */
.hd-cham { display: flex; gap: 7px; justify-content: center; align-items: center; margin: 4px 0 12px; }
.hd-cham i { width: 9px; height: 9px; border-radius: 50%; background: #CBD5E1; display: inline-block; transition: all .25s ease; }
.hd-cham i.done { background: #10B981; }
.hd-cham i.on { width: 28px; border-radius: 9px; background: linear-gradient(90deg, #E5383B, #C81D6B); }
.hd-dau { text-align: center; margin-bottom: 8px; }
.hd-icon { font-size: 2.3rem; line-height: 1; }
.hd-tt { font-size: 1.32rem; font-weight: 800; color: #0B1D3A; margin: 4px 0 2px; }
.hd-mt { color: #64748B; font-size: .9rem; margin-bottom: 8px; }

/* ---------- Thẻ mini 2.5D & Bản đồ Tab ---------- */
.grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 8px 0; }
.grid-2 { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin: 8px 0; }
.card-mini {
  background: linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%);
  border: 1.5px solid #CBD5E1; border-radius: 15px; padding: 12px 14px;
  box-shadow: 0 4px 0 #CBD5E1, 0 8px 14px -10px rgba(15,23,42,.15), inset 0 1px 0 #FFFFFF;
}
.card-mini.ok { border-color: #6EE7B7; border-top: 3px solid #10B981; box-shadow: 0 4px 0 #10B981, inset 0 1px 0 #FFFFFF; }
.card-mini.err { border-color: #FCA5A5; border-top: 3px solid #EF4444; box-shadow: 0 4px 0 #EF4444, inset 0 1px 0 #FFFFFF; }
.card-mini.warn { border-color: #FCD34D; border-top: 3px solid #F59E0B; box-shadow: 0 4px 0 #D97706, inset 0 1px 0 #FFFFFF; }
.card-mini-title { font-weight: 800; font-size: .88rem; color: #0B1D3A; margin-bottom: 4px; display: flex; align-items: center; gap: 6px; }
.card-mini-desc { font-size: .8rem; color: #475569; line-height: 1.44; }

/* ---------- Thanh phổ ngưỡng sinh học 2.5D (Tab 2) ---------- */
.pho-wrap {
  background: linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%);
  border: 1.5px solid #CBD5E1; border-radius: 18px; padding: 16px 18px 14px;
  margin: 10px 0 12px;
  box-shadow: 0 5px 0 #CBD5E1, 0 10px 20px -10px rgba(15,23,42,.15), inset 0 1px 0 #FFFFFF;
}
.pho-bar {
  position: relative; height: 22px; border-radius: 999px; overflow: hidden;
  display: flex; width: 100%; margin: 24px 0 10px;
  border: 1px solid #94A3B8;
  box-shadow: inset 0 3px 6px rgba(0,0,0,.22), 0 1px 0 #FFFFFF;
}
.pho-pin {
  position: absolute; top: -24px; transform: translateX(-50%);
  background: linear-gradient(180deg, #1E293B, #0B1D3A); color: #fff; font-size: .74rem; font-weight: 800;
  padding: 2px 9px; border-radius: 7px; white-space: nowrap; z-index: 5;
  border: 1px solid rgba(255,255,255,.25);
  box-shadow: 0 3px 0 #020617, 0 5px 10px rgba(11,29,58,.35);
}
.pho-pin::after {
  content: ""; position: absolute; bottom: -5px; left: 50%; transform: translateX(-50%);
  border-width: 5px 5px 0; border-style: solid; border-color: #0B1D3A transparent transparent;
}
.pho-ticks { display: flex; justify-content: space-between; font-size: .75rem; color: #64748B; font-weight: 600; }

/* ---------- Thanh tab 2.5D (Recessed Tray + Tactile Keycaps) ---------- */
.stTabs [data-baseweb="tab-list"] {
  gap: 8px; flex-wrap: wrap; border-bottom: none;
  background: #E2E8F0; padding: 7px 8px; border-radius: 18px; border: 1px solid #CBD5E1;
  box-shadow: inset 0 2px 5px rgba(15,23,42,.12), 0 1px 0 #FFFFFF;
}
.stTabs [data-baseweb="tab"] {
  background: linear-gradient(180deg, #FFFFFF 0%, #F1F5F9 100%);
  border: 1.5px solid #CBD5E1; border-radius: 12px; height: auto;
  padding: 8px 15px; font-weight: 700;
  box-shadow: 0 3px 0 #94A3B8, 0 4px 8px rgba(15,23,42,.08), inset 0 1px 0 #FFFFFF;
  transition: transform .12s ease, box-shadow .12s ease, border-color .12s ease;
}
.stTabs [data-baseweb="tab"]:hover {
  border-color: #FDA4AF; transform: translateY(-2px);
  box-shadow: 0 5px 0 #94A3B8, 0 8px 14px rgba(15,23,42,.12), inset 0 1px 0 #FFFFFF;
}
.stTabs [data-baseweb="tab"] p { font-size: .89rem; font-weight: 700; color: #1E293B; }
.stTabs [data-baseweb="tab"][aria-selected="true"] {
  background: linear-gradient(180deg, #FF5255 0%, #E5383B 55%, #C81D55 100%) !important;
  border-color: #9F1239 !important;
  box-shadow: 0 4px 0 #881337, 0 8px 16px rgba(229,56,59,.35), inset 0 1.5px 0 rgba(255,255,255,.4) !important;
  transform: translateY(-1px);
}
.stTabs [data-baseweb="tab"][aria-selected="true"] p { color: #FFFFFF !important; font-weight: 700 !important; }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display: none; }
.stTabs [data-baseweb="tab-panel"] { padding-top: 14px; }

/* ---------- Nút bấm 2.5D, ô nhập & khung phụ ---------- */
.stButton > button, .stDownloadButton > button {
  background: linear-gradient(180deg, #FFFFFF 0%, #F1F5F9 100%);
  color: #0F172A; border: 1.5px solid #CBD5E1; border-radius: 14px;
  font-weight: 700; min-height: 2.8rem;
  box-shadow: 0 4px 0 #94A3B8, 0 7px 14px -4px rgba(15,23,42,.14), inset 0 1px 0 #FFFFFF;
  transition: transform .12s ease, box-shadow .12s ease, border-color .12s ease, color .12s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover {
  transform: translateY(-2px); border-color: #94A3B8; color: #E5383B;
  box-shadow: 0 6px 0 #64748B, 0 12px 20px -6px rgba(15,23,42,.2), inset 0 1px 0 #FFFFFF;
}
.stButton > button:active, .stDownloadButton > button:active {
  transform: translateY(3px);
  box-shadow: 0 1px 0 #64748B, 0 2px 5px rgba(15,23,42,.15);
}
.stButton > button[kind="primary"],
.stButton > button[data-testid="stBaseButton-primary"],
.stDownloadButton > button[kind="primary"],
.stDownloadButton > button[data-testid="stBaseButton-primary"] {
  background: linear-gradient(180deg, #FF5255 0%, #E5383B 52%, #C81D55 100%) !important;
  color: #FFFFFF !important; border: 1.5px solid #9F1239 !important;
  box-shadow: 0 5px 0 #881337, 0 10px 20px -4px rgba(229,56,59,.45), inset 0 1.5px 0 rgba(255,255,255,.4) !important;
}
.stButton > button[kind="primary"]:hover,
.stButton > button[data-testid="stBaseButton-primary"]:hover,
.stDownloadButton > button[kind="primary"]:hover,
.stDownloadButton > button[data-testid="stBaseButton-primary"]:hover {
  transform: translateY(-2px); color: #FFFFFF !important;
  box-shadow: 0 7px 0 #881337, 0 14px 24px -4px rgba(229,56,59,.55), inset 0 1.5px 0 rgba(255,255,255,.5) !important;
}
.stButton > button[kind="primary"]:active,
.stButton > button[data-testid="stBaseButton-primary"]:active,
.stDownloadButton > button[kind="primary"]:active,
.stDownloadButton > button[data-testid="stBaseButton-primary"]:active {
  transform: translateY(3px);
  box-shadow: 0 2px 0 #881337, 0 4px 8px rgba(229,56,59,.3) !important;
}
.stButton > button[kind="primary"] p,
.stButton > button[data-testid="stBaseButton-primary"] p,
.stDownloadButton > button[kind="primary"] p,
.stDownloadButton > button[data-testid="stBaseButton-primary"] p { color: #FFFFFF !important; }

[data-testid="stMetric"] {
  background: linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%);
  border: 1.5px solid #CBD5E1; border-radius: 16px; padding: 14px 16px;
  box-shadow: 0 4px 0 #CBD5E1, inset 0 1px 0 #FFFFFF;
}
[data-testid="stExpander"] details {
  border-radius: 15px; background: linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%);
  border: 1.5px solid #CBD5E1; box-shadow: 0 3px 0 #CBD5E1, inset 0 1px 0 #FFFFFF;
}
[data-testid="stFileUploaderDropzone"] {
  border-radius: 15px; background: #F8FAFC; border: 1.5px dashed #94A3B8;
  box-shadow: inset 0 2px 5px rgba(15,23,42,.06);
}
[data-testid="stImage"] img {
  border-radius: 14px; border: 1.5px solid #CBD5E1;
  box-shadow: 0 5px 0 #CBD5E1, 0 10px 20px -10px rgba(15,23,42,.25);
}

/* ---------- Thanh bên 2.5D (Dark Instrument Sidebar) ---------- */
[data-testid="stSidebar"] { background: linear-gradient(180deg, #060F1E 0%, #0B1D3A 55%, #122E57 100%); border-right: 1.5px solid rgba(255,255,255,.1); }
[data-testid="stSidebar"] p, [data-testid="stSidebar"] li, [data-testid="stSidebar"] span,
[data-testid="stSidebar"] label, [data-testid="stSidebar"] div { color: #E2E8F0; }
[data-testid="stSidebar"] .stButton > button {
  background: linear-gradient(180deg, rgba(255,255,255,.16) 0%, rgba(255,255,255,.08) 100%);
  border: 1.5px solid rgba(255,255,255,.24); border-radius: 14px; backdrop-filter: blur(6px);
  box-shadow: 0 4px 0 rgba(2,6,23,.78), inset 0 1px 0 rgba(255,255,255,.22);
}
[data-testid="stSidebar"] .stButton > button:hover {
  transform: translateY(-2px);
  background: linear-gradient(180deg, rgba(229,56,59,.55) 0%, rgba(200,29,107,.45) 100%);
  border-color: rgba(252,165,165,.6);
  box-shadow: 0 6px 0 rgba(2,6,23,.82), inset 0 1px 0 rgba(255,255,255,.3);
}
[data-testid="stSidebar"] .stButton > button:active {
  transform: translateY(3px);
  box-shadow: 0 1px 0 rgba(2,6,23,.8);
}
[data-testid="stSidebar"] .stButton > button p { color: #fff !important; }
[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,.14); }
.sb-logo { font-size: 1.24rem; font-weight: 800; color: #fff; line-height: 1.25; letter-spacing: -.3px; }
.sb-logo b { color: #FCA5A5; }
.sb-the {
  background: linear-gradient(180deg, rgba(255,255,255,.09) 0%, rgba(255,255,255,.04) 100%);
  border: 1.5px solid rgba(255,255,255,.16); border-radius: 14px;
  padding: 12px 14px; font-size: .83rem; line-height: 1.52; margin: 8px 0;
  box-shadow: 0 4px 0 rgba(2,6,23,.55), inset 0 1px 0 rgba(255,255,255,.14);
}
.sb-the .sb-tt { font-weight: 700; color: #fff; margin-bottom: 4px; font-size: .86rem; }

/* ---------- Điện thoại & Màn hình nhỏ ---------- */
@media (max-width: 768px) {
  html { font-size: 15px; }
  .hero { padding: 18px 16px 30px; border-radius: 18px; }
  .hero-title { font-size: 1.35rem; }
  .hero-right { flex: 1 1 100%; }
  .coach-steps { grid-template-columns: repeat(2, 1fr); }
  .grid-3, .grid-2 { grid-template-columns: 1fr; }
  .the-so { font-size: 1.85rem; }
  .stTabs [data-baseweb="tab"] { padding: 7px 10px; }
  .stTabs [data-baseweb="tab"] p { font-size: .79rem; }
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
        "axes.grid": True, "grid.color": "#E2E8F0", "grid.linestyle": "--", "grid.alpha": 0.9,
        "xtick.color": "#475569", "ytick.color": "#475569",
        "axes.prop_cycle": mpl.cycler(color=["#E5383B", "#1B4965", "#14B8A6", "#F59E0B", "#8B5CF6", "#64748B"]),
        "figure.facecolor": "white", "axes.facecolor": "white",
        "legend.frameon": True, "legend.facecolor": "#F8FAFC", "legend.edgecolor": "#E2E8F0",
        "font.size": 9.5,
    })


def huy_hieu(text: str, loai: str = "xam", icon: str = "") -> str:
    """HTML một huy hiệu bo tròn. loai: do | xanh | vang | xam | duong | trong."""
    ic = f"{icon} " if icon else ""
    return f'<span class="huy-hieu hh-{loai}">{ic}{e(text)}</span>'


def hero(kicker: str, tieu_de: str, phu_de: str, huy_hieu_html: str = "") -> None:
    """Banner đầu trang với hai 'tia laser' lệch nhau Δy và tóm tắt nguyên lí vi sai."""
    hien(f"""
    <div class="hero">
      <div class="hero-grid">
        <div class="hero-left">
          <div class="hero-kicker">🔬 {e(kicker)}</div>
          <div class="hero-title">{e(tieu_de)}</div>
          <div class="hero-sub">{e(phu_de)}</div>
          <div class="hero-badges">{huy_hieu_html}</div>
        </div>
        <div class="hero-right">
          <div style="font-size:.74rem; color:#FCA5A5; font-weight:700; text-transform:uppercase; letter-spacing:.08em; margin-bottom:4px;">
            ⚡ Cấu hình đo vi sai 2 ngăn
          </div>
          <div style="font-size:.82rem; color:#E2E8F0; line-height:1.5;">
            • <b>Ngăn trái:</b> Nước cất chuẩn (0 ‰)<br>
            • <b>Ngăn phải:</b> Mẫu nước cần đo (S ‰)<br>
            • <b>Tín hiệu:</b> <code style="color:#FDE047; background:rgba(255,255,255,.1); padding:1px 5px; border-radius:4px;">Δy = y_mẫu − y_tc</code><br>
            • <b>Ưu điểm:</b> Tự triệt tiêu rung & trôi nhiệt
          </div>
        </div>
      </div>
      <div class="tia t1"></div><div class="tia t2"></div>
      <div class="tia-dy"></div><div class="tia-dy-nhan">Δy = y_mẫu − y_tc</div>
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


def svg_he_quang_hoc(
    A_do: float = 40.0,
    S_ppt: float = 16.5,
    delta_y_px: float = 82.0,
    drift_px: float = 0.0,
    do_duc: float = 0.1,
    tir: bool = False,
) -> str:
    """Sinh sơ đồ SVG trực quan hệ quang học lăng kính 2 ngăn và màn hứng 2 vạch laser.

    Cập nhật động theo độ mặn S_ppt, độ trôi chung drift_px, độ đục do_duc và góc đỉnh A_do.
    """
    # Quy đổi tọa độ hiển thị trên màn hứng trong khung SVG (cao 190px)
    y_base = 65.0 + float(drift_px) * 1.6
    y_tc_svg = max(28.0, min(145.0, y_base))
    dy_svg = max(0.0, min(68.0, float(delta_y_px) * 0.42))
    y_mau_svg = max(28.0, min(168.0, y_tc_svg + dy_svg))
    stroke_mau = max(2.5, min(9.0, 3.0 + float(do_duc) * 6.5))
    opacity_mau = max(0.45, 1.0 - float(do_duc) * 0.45)

    if tir:
        tia_lo_svg = """
        <line x1="215" y1="95" x2="170" y2="155" stroke="#EF4444" stroke-width="2.5" stroke-dasharray="5,4"/>
        <text x="240" y="100" fill="#FCA5A5" font-size="12" font-weight="700">🚨 PHẢN XẠ TOÀN PHẦN (n·sinA ≥ 1)</text>
        """
    else:
        tia_lo_svg = f"""
        <!-- Tia ló ngăn tham chiếu (Nước cất S=0) -->
        <line x1="218" y1="82" x2="430" y2="{y_tc_svg:.1f}" stroke="#34D399" stroke-width="2.2" stroke-dasharray="4,3" opacity="0.85"/>
        <!-- Tia ló ngăn mẫu (Nước mặn S>0) -->
        <line x1="218" y1="108" x2="430" y2="{y_mau_svg:.1f}" stroke="#FF4D4F" stroke-width="2.5" opacity="0.9"/>
        """

    return f"""
    <div style="background:linear-gradient(135deg,#071326 0%,#0B1D3A 100%); border-radius:18px; padding:12px 14px; border:1.5px solid rgba(148,163,184,.26); box-shadow:0 5px 0 #040B16, inset 0 1px 0 rgba(255,255,255,.14); margin:6px 0 12px;">
      <svg viewBox="0 0 680 186" width="100%" height="186" xmlns="http://www.w3.org/2000/svg" style="display:block;">
        <defs>
          <filter id="laserGlow" x="-20%" y="-50%" width="140%" height="200%">
            <feGaussianBlur stdDeviation="3.2" result="blur"/>
            <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
          </filter>
          <linearGradient id="prismFront" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="rgba(56,189,248,0.26)"/>
            <stop offset="100%" stop-color="rgba(14,165,233,0.08)"/>
          </linearGradient>
        </defs>

        <!-- Nguồn Laser 650nm dạng khối 2.5D -->
        <polygon points="14,76 24,68 82,68 72,76" fill="#475569" stroke="#94A3B8" stroke-width="1"/>
        <polygon points="72,76 82,68 82,104 72,112" fill="#0F172A" stroke="#64748B" stroke-width="1"/>
        <rect x="14" y="76" width="58" height="36" rx="6" fill="#1E293B" stroke="#94A3B8" stroke-width="1.5"/>
        <text x="43" y="92" fill="#F8FAFC" font-size="9.5" font-weight="700" text-anchor="middle">LASER</text>
        <text x="43" y="104" fill="#FCA5A5" font-size="8.5" text-anchor="middle">650 nm</text>

        <!-- Chùm tia tới vuông góc mặt vào -->
        <line x1="72" y1="86" x2="155" y2="86" stroke="#FF4D4F" stroke-width="2.4" filter="url(#laserGlow)"/>
        <line x1="72" y1="102" x2="155" y2="102" stroke="#FF4D4F" stroke-width="2.4" filter="url(#laserGlow)"/>

        <!-- Lăng kính rỗng 2 ngăn khối 2.5D (Góc đỉnh A) -->
        <polygon points="155,36 167,28 260,86 248,94" fill="rgba(125,211,252,0.18)" stroke="#7DD3FC" stroke-width="1.2"/>
        <polygon points="155,152 248,94 260,86 167,144" fill="rgba(14,165,233,0.12)" stroke="#38BDF8" stroke-width="1"/>
        <polygon points="155,36 155,152 248,94" fill="url(#prismFront)" stroke="#38BDF8" stroke-width="2"/>
        <line x1="155" y1="94" x2="248" y2="94" stroke="#CBD5E1" stroke-width="1.5" stroke-dasharray="3,3"/>
        <text x="196" y="21" fill="#7DD3FC" font-size="10.5" font-weight="700" text-anchor="middle">Lăng kính 2 ngăn (A = {A_do:.1f}°)</text>
        <text x="180" y="75" fill="#A7F3D0" font-size="8.5" font-weight="600">Ngăn TC (0‰)</text>
        <text x="180" y="118" fill="#FECACA" font-size="8.5" font-weight="600">Ngăn Mẫu ({S_ppt:.1f}‰)</text>

        {tia_lo_svg}

        <!-- Màn hứng / Khung ảnh Camera 2.5D -->
        <rect x="446" y="19" width="222" height="158" rx="12" fill="#020617" stroke="#334155" stroke-width="1"/>
        <rect x="442" y="14" width="222" height="158" rx="12" fill="#071122" stroke="#64748B" stroke-width="1.8"/>
        <text x="553" y="31" fill="#CBD5E1" font-size="10" font-weight="700" text-anchor="middle">MÀN HỨNG / ẢNH CAMERA</text>
        <line x1="553" y1="38" x2="553" y2="164" stroke="#334155" stroke-width="1" stroke-dasharray="3,3"/>

        <!-- Vạch tham chiếu (bên trái màn) -->
        <line x1="458" y1="{y_tc_svg:.1f}" x2="544" y2="{y_tc_svg:.1f}" stroke="#FF4D4F" stroke-width="3.2" stroke-linecap="round" filter="url(#laserGlow)"/>
        <line x1="458" y1="{y_tc_svg:.1f}" x2="544" y2="{y_tc_svg:.1f}" stroke="#34D399" stroke-width="1.2" stroke-dasharray="2,2"/>
        <text x="460" y="{max(46.0, y_tc_svg - 8.0):.1f}" fill="#6EE7B7" font-size="9.5" font-weight="700">Vạch TC (0‰)</text>

        <!-- Vạch mẫu (bên phải màn) -->
        <line x1="562" y1="{y_mau_svg:.1f}" x2="648" y2="{y_mau_svg:.1f}" stroke="#FF4D4F" stroke-width="{stroke_mau:.1f}" stroke-opacity="{opacity_mau:.2f}" stroke-linecap="round" filter="url(#laserGlow)"/>
        <text x="562" y="{min(164.0, y_mau_svg + 15.0):.1f}" fill="#FCA5A5" font-size="9.5" font-weight="700">Vạch Mẫu ({S_ppt:.1f}‰)</text>

        <!-- Đoạn đo vi sai Δy -->
        <line x1="553" y1="{y_tc_svg:.1f}" x2="553" y2="{y_mau_svg:.1f}" stroke="#FDE047" stroke-width="2.2"/>
        <circle cx="553" cy="{y_tc_svg:.1f}" r="3" fill="#34D399"/>
        <circle cx="553" cy="{y_mau_svg:.1f}" r="3" fill="#FF4D4F"/>
        <rect x="506" y="{(y_tc_svg + y_mau_svg)/2.0 - 9.0:.1f}" width="94" height="18" rx="5" fill="rgba(15,23,42,0.9)" stroke="#FDE047" stroke-width="1"/>
        <text x="553" y="{(y_tc_svg + y_mau_svg)/2.0 + 3.5:.1f}" fill="#FDE047" font-size="9.5" font-weight="800" text-anchor="middle">Δy = {delta_y_px:.1f} px</text>
      </svg>
    </div>
    """


def thanh_nguong_loai(S_ppt: float, loai: th.ThongTinLoai) -> str:
    """HTML thanh phổ trực quan hiển thị phân vùng An toàn / Cảnh báo / Nguy hiểm của loài."""
    if not loai.co_du_lieu_nguon or loai.an_toan_min is None or loai.an_toan_max is None:
        return ""

    s_max_scale = max(
        40.0,
        (loai.nguy_hiem_tren or 0.0) * 1.25,
        (loai.an_toan_max or 0.0) * 1.5,
        S_ppt * 1.15,
    )
    if s_max_scale <= 5.0:
        s_max_scale = 4.0  # Dành cho cây nhạy mặn như lúa, sầu riêng

    def pct(val: float) -> float:
        return max(0.0, min(100.0, (val / s_max_scale) * 100.0))

    p_nguy_duoi = pct(loai.nguy_hiem_duoi or 0.0)
    p_at_min = pct(loai.an_toan_min)
    p_at_max = pct(loai.an_toan_max)
    p_nguy_tren = pct(loai.nguy_hiem_tren if loai.nguy_hiem_tren is not None else s_max_scale)
    p_cur = max(2.0, min(98.0, pct(S_ppt)))

    w1 = p_nguy_duoi
    w2 = max(0.0, p_at_min - p_nguy_duoi)
    w3 = max(0.0, p_at_max - p_at_min)
    w4 = max(0.0, p_nguy_tren - p_at_max)
    w5 = max(0.0, 100.0 - p_nguy_tren)

    return f"""
    <div class="pho-wrap">
      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
        <div style="font-weight:800; color:#0B1D3A; font-size:.92rem;">
          📏 Phổ thích nghi sinh học: <span style="color:#E5383B;">{e(loai.ten_hien_thi)}</span>
        </div>
        <div style="font-size:.8rem; color:#475569;">
          Dải tối ưu: <b>{loai.an_toan_min:g} – {loai.an_toan_max:g} ‰</b>
        </div>
      </div>
      <div style="position:relative; margin-top:28px;">
        <div class="pho-pin" style="left:{p_cur:.1f}%;">Mẫu: {S_ppt:.2f} ‰</div>
        <div class="pho-bar">
          <div style="width:{w1:.2f}%; background:#EF4444;" title="Nguy hiểm dưới"></div>
          <div style="width:{w2:.2f}%; background:#F59E0B;" title="Cảnh báo thấp"></div>
          <div style="width:{w3:.2f}%; background:#10B981;" title="An toàn tối ưu"></div>
          <div style="width:{w4:.2f}%; background:#F59E0B;" title="Cảnh báo cao"></div>
          <div style="width:{w5:.2f}%; background:#EF4444;" title="Nguy hiểm trên"></div>
        </div>
      </div>
      <div class="pho-ticks">
        <span>0 ‰</span>
        <span>🟢 An toàn ({loai.an_toan_min:g}–{loai.an_toan_max:g} ‰)</span>
        <span>🟡 Cảnh báo</span>
        <span>🔴 Nguy hiểm (&gt; {loai.nguy_hiem_tren if loai.nguy_hiem_tren is not None else s_max_scale:g} ‰)</span>
        <span>{s_max_scale:g} ‰</span>
      </div>
    </div>
    """


def thanh_tro_ly_thoi_gian_thuc(
    co_anh: bool,
    da_do: bool,
    hop_le_anh: bool,
    da_luu_nhat_ki: bool,
    s_do_duoc: float | None = None,
    u_do_duoc: float | None = None,
    canh_bao_anh: list[str] | None = None,
) -> None:
    """Hiển thị thanh Trợ lý Hướng dẫn Thời gian thực (Live Interactive Coach) đầu trang.

    Tự động theo dõi trạng thái thao tác thực tế của người dùng để gợi ý bước kế tiếp.
    """
    if not st.session_state.get("bat_tro_ly_thoi_gian_thuc", True):
        return

    # Xác định bước hiện tại trong quy trình 4 bước
    if not co_anh:
        buoc_ht = 1
        icon_ht = "👋"
        tieu_de_ht = "Bước 1/4: Chọn nguồn ảnh vạch laser để bắt đầu"
        mo_ta_ht = (
            "Chọn tải ảnh, chụp Camera, hoặc dùng chế độ <b>Mô phỏng</b> / nhấn <b>⚡ Mẫu thử 16.5 ‰ & Đo ngay</b> bên dưới."
        )
    elif not da_do:
        buoc_ht = 2
        icon_ht = "📸"
        tieu_de_ht = "Bước 2/4: Kiểm tra nhiệt độ mẫu và Tiến hành đo"
        mo_ta_ht = (
            "Kiểm tra <b>Nhiệt độ mẫu (°C)</b> ở khung bên phải rồi nhấn <b>🚀 TIẾN HÀNH ĐO ĐỘ MẶN</b>."
        )
    elif not da_luu_nhat_ki:
        buoc_ht = 3
        if hop_le_anh and s_do_duoc is not None:
            icon_ht = "✅"
            u_str = f" ± {u_do_duoc:.2f}" if u_do_duoc is not None else ""
            tieu_de_ht = f"Bước 3/4: Đã định vị tâm vạch thành công — Độ mặn S = {s_do_duoc:.2f}{u_str} ‰"
            mo_ta_ht = (
                "Quan sát ảnh tâm vạch &amp; mặt cắt Gauss bên dưới, chọn đối tượng nuôi và nhấn <b>💾 Lưu kết quả vào Nhật Kí</b>."
            )
        else:
            icon_ht = "⚠️"
            cb_text = canh_bao_anh[0] if canh_bao_anh else "Ảnh có độ tương phản thấp hoặc cháy sáng."
            tieu_de_ht = "Bước 3/4: Lưu ý chất lượng quang học của ảnh chụp"
            mo_ta_ht = (
                f"Phát hiện: <b>{e(cb_text)}</b> Điều chỉnh phơi sáng hoặc vùng ROI rồi lưu Nhật kí."
            )
    else:
        buoc_ht = 4
        icon_ht = "🎉"
        tieu_de_ht = "Bước 4/4: Hoàn tất quy trình đo và lưu Nhật kí quan trắc!"
        mo_ta_ht = (
            "Bản ghi đã lưu vào SQLite. Có thể xem tiếp ở <b>Tab 2 (Cảnh báo loài)</b>, <b>Tab 3 (Nhật kí)</b> hoặc <b>Tab 4–6</b>."
        )

    def cls_step(idx: int) -> str:
        if idx < buoc_ht or (buoc_ht == 4 and idx == 4):
            return "c-step done"
        if idx == buoc_ht:
            return "c-step active"
        return "c-step"

    def lbl_num(idx: int) -> str:
        if idx < buoc_ht or (buoc_ht == 4 and idx == 4):
            return "✓"
        return str(idx)

    hien(f"""
    <div class="coach-wrap">
      <div class="coach-head">
        <div class="coach-badge"><span class="coach-pulse"></span> TRỢ LÝ QUY TRÌNH ĐO (4 BƯỚC)</div>
        <div style="font-size:.78rem; color:#475569; font-weight:700;">
          Tiến độ: <b>{min(buoc_ht, 4)}/4 bước hoàn thành</b>
        </div>
      </div>
      <div class="coach-steps">
        <div class="{cls_step(1)}"><div class="c-num">{lbl_num(1)}</div><div>1. Nguồn ảnh</div></div>
        <div class="{cls_step(2)}"><div class="c-num">{lbl_num(2)}</div><div>2. Thông số &amp; Đo</div></div>
        <div class="{cls_step(3)}"><div class="c-num">{lbl_num(3)}</div><div>3. Phân tích Gauss</div></div>
        <div class="{cls_step(4)}"><div class="c-num">{lbl_num(4)}</div><div>4. Lưu Nhật kí</div></div>
      </div>
      <div class="coach-body">
        <div class="coach-icon">{icon_ht}</div>
        <div>
          <div class="coach-msg-title">{e(tieu_de_ht)}</div>
          <div class="coach-msg-desc">{mo_ta_ht}</div>
        </div>
      </div>
    </div>
    """)

    # Hàng nút thao tác nhanh 2.5D ngay dưới thanh trợ lý
    c_qa1, c_qa2, c_qa3, c_qa4 = st.columns([1.3, 1.3, 1.1, 0.9], gap="small")
    with c_qa1:
        if st.button("⚡ Mẫu thử 16.5 ‰ & Đo ngay", width="stretch", help="Tự động chuyển sang ảnh mô phỏng 16.5 ‰ và thực hiện phép đo mẫu"):
            st.session_state["nguon_anh_radio"] = "Tạo ảnh mô phỏng thử nghiệm"
            st.session_state["sim_s_ppt"] = 16.5
            st.session_state["sim_t_c"] = 26.0
            st.session_state["sim_duc"] = 0.15
            st.session_state["sim_drift"] = 4.0
            st.session_state["yeu_cau_do_ngay"] = True
            st.rerun()
    with c_qa2:
        if st.button("📳 Kiểm chứng Chống rung (+12 px)", width="stretch", help="Thử dịch cả 2 vạch đi +12 px do rung camera để kiểm chứng Δy không đổi"):
            st.session_state["nguon_anh_radio"] = "Tạo ảnh mô phỏng thử nghiệm"
            st.session_state["sim_drift"] = 12.0
            st.session_state["yeu_cau_do_ngay"] = True
            st.rerun()
    with c_qa3:
        if st.button("📖 Hướng dẫn tương tác 4 bước", width="stretch"):
            st.session_state["mo_huong_dan"] = True
            st.rerun()
    with c_qa4:
        if st.button("✖ Thu gọn trợ lý", width="stretch"):
            st.session_state["bat_tro_ly_thoi_gian_thuc"] = False
            st.rerun()
    st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)


@st.dialog("📖 HƯỚNG DẪN TƯƠNG TÁC & LÀM QUEN HỆ THỐNG", width="large")
def hop_thoai_huong_dan() -> None:
    """Hộp thoại hướng dẫn tương tác 4 bước tự động mở khi lần đầu truy cập."""
    if "buoc_hd_modal" not in st.session_state:
        st.session_state["buoc_hd_modal"] = 1

    buoc_ht = int(st.session_state["buoc_hd_modal"])

    # Chấm tiến trình (Step indicator)
    cham_html = "".join(
        f'<i class="{"on" if i == buoc_ht else ("done" if i < buoc_ht else "")}"></i>'
        for i in range(1, 5)
    )
    hien(f"""
    <div class="hd-dau">
      <div class="hd-icon">🔬</div>
      <div class="hd-tt">Thiết Bị Đo Độ Mặn Khúc Xạ Laser Hai Ngăn Vi Sai</div>
      <div class="hd-mt">Hướng dẫn tương tác thời gian thực • Bước {buoc_ht} / 4</div>
      <div class="hd-cham">{cham_html}</div>
    </div>
    """)

    # Thanh chọn bước nhanh
    cols_nav = st.columns(4)
    nhan_buoc_ds = [
        "1️⃣ Nguyên lí Vi sai",
        "2️⃣ Quy trình Chụp & Đo",
        "3️⃣ Bản đồ 6 Phân hệ",
        "4️⃣ Quy chuẩn KHKT",
    ]
    for idx, col in enumerate(cols_nav, start=1):
        with col:
            if st.button(
                nhan_buoc_ds[idx - 1],
                type="primary" if buoc_ht == idx else "secondary",
                width="stretch",
                key=f"btn_step_nav_{idx}",
            ):
                st.session_state["buoc_hd_modal"] = idx
                st.rerun()

    st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)

    # -----------------------------------------------------------------------
    # BƯỚC 1: TƯƠNG TÁC TRỰC TIẾP NGUYÊN LÍ KHÚC XẠ & VI SAI HAI NGĂN
    # -----------------------------------------------------------------------
    if buoc_ht == 1:
        bang(
            "duong",
            "<b>Trải nghiệm thời gian thực ngay tại đây:</b> Hãy kéo thử 2 thanh trượt bên dưới để xem tia laser khúc xạ qua lăng kính và cách cấu trúc vi sai 2 ngăn triệt tiêu hoàn toàn rung lắc camera!",
            icon="✨",
            la_html=True,
        )
        c_d1, c_d2 = st.columns(2)
        s_demo = c_d1.slider("🌊 Thử thay đổi Độ mặn ngăn mẫu S (‰):", 0.0, 35.0, 18.0, 1.0, key="hd_s_demo")
        drift_demo = c_d2.slider("📳 Thử gây Rung camera / Trôi laser δy_drift (px):", -12.0, 12.0, 0.0, 1.0, key="hd_drift_demo")

        cfg_demo = op.CauHinhQuangHoc.tu_yaml()
        dy_demo = op.delta_y_vi_sai_px(s_demo, 25.0, 25.0, cfg_demo)
        y_tc_demo = 80.0 + drift_demo
        y_m_demo = 80.0 + dy_demo + drift_demo

        hien(svg_he_quang_hoc(A_do=cfg_demo.A_do, S_ppt=s_demo, delta_y_px=dy_demo, drift_px=drift_demo, do_duc=0.05))

        hien(f"""
        <div class="grid-3">
          <div class="card-mini">
            <div class="card-mini-title">🟢 Vị trí Vạch Tham Chiếu</div>
            <div class="card-mini-desc">
              <code>y_tc = 80.0 + ({drift_demo:+.1f}) = <b>{y_tc_demo:.1f} px</b></code><br>
              Dịch chuyển theo rung lắc <code>δy_drift</code>.
            </div>
          </div>
          <div class="card-mini">
            <div class="card-mini-title">🔴 Vị trí Vạch Mẫu ({s_demo:.0f} ‰)</div>
            <div class="card-mini-desc">
              <code>y_mẫu = {80.0 + dy_demo:.1f} + ({drift_demo:+.1f}) = <b>{y_m_demo:.1f} px</b></code><br>
              Cùng chịu chung độ trôi <code>δy_drift</code>.
            </div>
          </div>
          <div class="card-mini ok">
            <div class="card-mini-title">🛡️ Tín hiệu Vi sai Δy</div>
            <div class="card-mini-desc">
              <code>Δy = y_mẫu − y_tc = <b>{dy_demo:.2f} px</b></code><br>
              <b>Bất biến tuyệt đối</b> dù rung lắc = {drift_demo:+.1f} px!
            </div>
          </div>
        </div>
        """)

    # -----------------------------------------------------------------------
    # BƯỚC 2: QUY TRÌNH ĐO 4 BƯỚC & NHẬN DIỆN CHẤT LƯỢNG ẢNH
    # -----------------------------------------------------------------------
    elif buoc_ht == 2:
        hien(buoc(1, "Chuẩn bị cuvet lăng kính 2 ngăn", "Ngăn tham chiếu (trái) chứa <b>nước cất 0 ‰</b> đóng kín. Ngăn mẫu (phải) tráng sạch 2 lần bằng nước cần đo rồi châm đầy."))
        hien(buoc(2, "Chụp ảnh màn hứng đúng kỹ thuật", "Đặt camera vuông góc với màn hứng trong hộp tối. Giảm độ phơi sáng (EV) trên điện thoại nếu thấy lõi vạch bị trắng lóa."))
        hien(buoc(3, "Định vị tâm Gauss dưới pixel & Giải ngược độ mặn", "Phần mềm tự động khớp hàm Gauss dọc hàng trăm cột ảnh (độ chính xác <code>&lt; 0.05 px</code>) và giải ngược phương trình đường chuẩn kèm bù nhiệt độ."))

        hien("""
        <div style="font-weight:800; color:#0B1D3A; margin:10px 0 6px; font-size:.92rem;">
          📸 Cách nhận biết nhanh chất lượng ảnh chụp vạch laser:
        </div>
        <div class="grid-3">
          <div class="card-mini ok">
            <div class="card-mini-title">✅ Ảnh Đạt Chuẩn Tốt</div>
            <div class="card-mini-desc">
              Đỉnh cường độ <b>80 – 245</b> (không chạm 255), nền tối, SNR &gt; 3. Khớp Gauss đạt <code>R² &gt; 0.90</code>.
            </div>
          </div>
          <div class="card-mini err">
            <div class="card-mini-title">🚨 Ảnh Bão Hòa (Cháy sáng)</div>
            <div class="card-mini-desc">
              Đỉnh vạch bị cắt phẳng ở mức xám <b>255</b> làm sai lệch tâm. <b>Cách sửa:</b> Kéo giảm thanh EV camera hoặc dán giấy mờ.
            </div>
          </div>
          <div class="card-mini warn">
            <div class="card-mini-title">⚠️ Ảnh Quá Mờ / Nhiễu</div>
            <div class="card-mini-desc">
              Ánh sáng phòng quá mạnh làm SNR &lt; 3. <b>Cách sửa:</b> Đậy nắp hộp quang học hoặc dùng vùng chọn ROI thủ công.
            </div>
          </div>
        </div>
        """)

    # -----------------------------------------------------------------------
    # BƯỚC 3: BẢN ĐỒ 6 PHÂN HỆ CHỨC NĂNG
    # -----------------------------------------------------------------------
    elif buoc_ht == 3:
        hien("""
        <div class="grid-2">
          <div class="card-mini ok">
            <div class="card-mini-title">📸 Tab 1: Đo Độ Mặn & Độ Đục Từ Ảnh</div>
            <div class="card-mini-desc">
              Tải ảnh / chụp camera / tạo ảnh mô phỏng. Xem đường tâm dưới pixel, mặt cắt khớp Gauss <code>I(y)</code>, bất định chuẩn mở rộng <code>±U₉₅%</code> và lưu nhật kí.
            </div>
          </div>
          <div class="card-mini ok">
            <div class="card-mini-title">🦐 Tab 2: Cảnh Báo An Toàn Theo Loài</div>
            <div class="card-mini-desc">
              Tra cứu tự động ngưỡng chịu mặn cho Tôm thẻ, Tôm sú, Cá tra, Lúa, Sầu riêng... trên thanh phổ trực quan kèm trích dẫn quy chuẩn TCVN / QCVN.
            </div>
          </div>
          <div class="card-mini">
            <div class="card-mini-title">📒 Tab 3: Nhật Kí Quan Trắc & Xuất CSV</div>
            <div class="card-mini-desc">
              Quản lí lịch sử đo thực địa trong cơ sở dữ liệu SQLite, lọc theo vị trí/đối tượng, vẽ đồ thị diễn biến độ mặn theo thời gian và xuất báo cáo Excel/CSV.
            </div>
          </div>
          <div class="card-mini">
            <div class="card-mini-title">📊 Tab 4: Hiệu Chuẩn & Bù Nhiệt Độ</div>
            <div class="card-mini-desc">
              Dựng đường chuẩn thực nghiệm <code>Δy = f(S, T)</code> từ dung dịch NaCl chuẩn với kiểm định chéo k-fold chống quá khớp và đồ thị phần dư.
            </div>
          </div>
          <div class="card-mini">
            <div class="card-mini-title">📐 Tab 5: Mô Phỏng Quang Học & Ngân Sách Sai Số</div>
            <div class="card-mini-desc">
              Khảo sát định luật Snell chính xác, góc phản xạ toàn phần (TIR), độ nhạy <code>px/‰</code> và bảng phân tích sai số toàn phương RSS.
            </div>
          </div>
          <div class="card-mini">
            <div class="card-mini-title">⚖️ Tab 6: Đối Chứng Khúc Xạ Kế (Bland–Altman)</div>
            <div class="card-mini-desc">
              So sánh song song thiết bị dự án với khúc xạ kế quang cơ cầm tay bằng đồ thị tương quan <code>y = x</code> và đồ thị giới hạn đồng thuận Bland–Altman.
            </div>
          </div>
        </div>
        """)

    # -----------------------------------------------------------------------
    # BƯỚC 4: QUY CHUẨN TRUNG THỰC KHOA HỌC & BẮT ĐẦU
    # -----------------------------------------------------------------------
    else:
        bang(
            "vang",
            "<b>3 Nguyên tắc Trung thực Khoa học bắt buộc khi thuyết minh dự án KHKT:</b>",
            icon="🎓",
            la_html=True,
        )
        hien(buoc("A", "Phân biệt rõ Dữ liệu Mô phỏng và Dữ liệu Đo thật", "Khi chưa nạp file CSV đo dung dịch chuẩn thực tế ở Tab 4, hệ thống luôn gắn nhãn <b>CHƯA HIỆU CHUẨN – DỮ LIỆU MÔ PHỎNG</b> để đảm bảo tính minh bạch khoa học."))
        hien(buoc("B", "Độ mặn tương đương NaCl (NaCl-equivalent Salinity)", "Đường chuẩn được xây dựng từ dung dịch NaCl tinh khiết. Nước sông/ao hồ tự nhiên có thêm các ion khác (Mg²⁺, Ca²⁺, SO₄²⁻...) nên kết quả báo cáo là <b>độ mặn tương đương NaCl</b>."))
        hien(buoc("C", "Chỉ số độ đục tương đối [0.0 – 1.0]", "Độ đục được đánh giá qua độ mở rộng FWHM và suy giảm biên độ vạch laser do tán xạ Mie/Rayleigh. <b>Tuyệt đối không tự quy đổi ra NTU</b> khi chưa chuẩn hóa bằng dung dịch chuẩn Formazin."))

        bang(
            "xanh",
            "💡 <b>Mẹo nhỏ:</b> Sau khi đóng hộp thoại này, <b>Thanh Trợ Lý Hướng Dẫn Thời Gian Thực</b> ở đầu trang sẽ tiếp tục đồng hành và chỉ dẫn cho bạn từng bước thao tác trực tiếp!",
            icon="✨",
            la_html=True,
        )

    st.divider()
    c_f1, c_f2, c_f3 = st.columns([1, 1.1, 1.5])
    with c_f1:
        if buoc_ht > 1:
            if st.button("⬅️ Bước trước", width="stretch"):
                st.session_state["buoc_hd_modal"] = buoc_ht - 1
                st.rerun()
        else:
            if st.button("Đóng nhanh", width="stretch"):
                st.session_state["da_xem_huong_dan"] = True
                st.session_state["mo_huong_dan"] = False
                st.rerun()

    with c_f2:
        if buoc_ht < 4:
            if st.button("Bước tiếp theo ➡️", width="stretch"):
                st.session_state["buoc_hd_modal"] = buoc_ht + 1
                st.rerun()
        else:
            if st.button("Vào thẳng ứng dụng", width="stretch"):
                st.session_state["da_xem_huong_dan"] = True
                st.session_state["mo_huong_dan"] = False
                st.rerun()

    with c_f3:
        if st.button("🎯 Bắt đầu kèm Hướng dẫn Thời gian thực", type="primary", width="stretch"):
            st.session_state["da_xem_huong_dan"] = True
            st.session_state["mo_huong_dan"] = False
            st.session_state["bat_tro_ly_thoi_gian_thuc"] = True
            st.session_state["nguon_anh_radio"] = "Tạo ảnh mô phỏng thử nghiệm"
            st.session_state["yeu_cau_do_ngay"] = True
            st.rerun()
