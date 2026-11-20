/* ==========================================================================
   Hệ Thống Đo Độ Mặn Khúc Xạ Laser Vi Sai — Client Web 2.5D (Vanilla JS)
   ========================================================================== */
"use strict";

let INITIAL_HO_SO = "mac_dinh";
try {
  INITIAL_HO_SO = localStorage.getItem("salinity_ho_so") || "mac_dinh";
} catch (_) {}

const OFFLINE_QUEUE_KEY = "salinity_offline_queue";

const STATE = {
  hoSo: INITIAL_HO_SO,
  bootstrap: null,
  imgMode: "sim",          // "sim" | "upload" | "camera"
  uploadImageB64: null,
  cameraImageB64: null,
  lastMeasure: null,
  savedCurrentLog: false,
  cameraStream: null,
  calibMode: "sim",        // "sim" | "csv"
  calibCsvText: null,
  calibFileName: "",
  calibLast: null,
  opticsLast: null,
  baPairs: [],
  baLast: null,
  logLast: null,
  speciesLast: null,
  debounces: {},
  aborts: {},
  measureSeq: 0,
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

function esc(val) {
  return String(val ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function fmt(val, digits = 2, fallback = "--") {
  if (val === null || val === undefined || Number.isNaN(Number(val))) return fallback;
  return Number(val).toFixed(digits);
}

function toast(msg, ms = 2800) {
  const tray = $("#toast-tray");
  const el = document.createElement("div");
  el.className = "toast-25d";
  el.textContent = msg;
  tray.appendChild(el);
  setTimeout(() => el.remove(), ms);
}

function debounce(key, fn, delay = 90) {
  clearTimeout(STATE.debounces[key]);
  STATE.debounces[key] = setTimeout(fn, delay);
}

function isAbortError(err) {
  return Boolean(err && err.name === "AbortError");
}

function _nextAbortSignal(abortKey) {
  if (!abortKey) return undefined;
  if (STATE.aborts[abortKey]) {
    try { STATE.aborts[abortKey].abort(); } catch (_) {}
  }
  const ctrl = new AbortController();
  STATE.aborts[abortKey] = ctrl;
  return ctrl.signal;
}

async function apiGet(url, abortKey = null) {
  const signal = _nextAbortSignal(abortKey);
  const res = await fetch(url, {
    headers: { "X-Ho-So": encodeURIComponent(STATE.hoSo || "mac_dinh") },
    signal,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

async function apiPost(url, payload, abortKey = null) {
  const signal = _nextAbortSignal(abortKey);
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Ho-So": encodeURIComponent(STATE.hoSo || "mac_dinh"),
    },
    body: JSON.stringify(payload),
    signal,
  });
  const data = await res.json();
  if (!res.ok) {
    const err = new Error(data.error || `HTTP ${res.status}`);
    err.status = res.status;
    err.offline = Boolean(data.offline);
    throw err;
  }
  return data;
}

/* ==========================================================================
   Bộ Vẽ Đồ Thị Khoa Học HTML5 Canvas (Hỗ trợ Retina DPR & Tooltip)
   ========================================================================== */
function setupCanvas(canvas) {
  const wrap = canvas.parentElement;
  const width = Math.max(260, (wrap ? wrap.clientWidth - 12 : 420));
  const height = 280;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.round(width * dpr);
  canvas.height = Math.round(height * dpr);
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, width, height };
}

function formatTickVal(val, step) {
  if (Math.abs(val) < step * 1e-6) return "0";
  const dec = step > 0 ? Math.max(0, Math.min(4, Math.ceil(-Math.log10(step)))) : 2;
  return Number(val.toFixed(dec)).toString();
}

function niceTicks(minV, maxV, count = 5) {
  if (!(maxV > minV)) {
    minV -= 1;
    maxV += 1;
  }
  const span = maxV - minV;
  const roughStep = span / Math.max(count, 2);
  const pow10 = Math.pow(10, Math.floor(Math.log10(roughStep)));
  const frac = roughStep / pow10;
  let niceFrac = 1;
  if (frac > 5) niceFrac = 10;
  else if (frac > 2) niceFrac = 5;
  else if (frac > 1) niceFrac = 2;
  const step = niceFrac * pow10;
  const start = Math.floor(minV / step) * step;
  const ticks = [];
  for (let t = start; t <= maxV + step * 0.25; t += step) {
    if (t >= minV - step * 0.01 && t <= maxV + step * 0.01) ticks.push(t);
  }
  return { min: minV, max: maxV, step, ticks };
}

function drawXYChart(canvas, tooltipEl, opts) {
  if (!canvas || !canvas.offsetParent) return;
  const { ctx, width, height } = setupCanvas(canvas);
  const pad = { top: 28, right: 18, bottom: 42, left: 56 };
  const pw = width - pad.left - pad.right;
  const ph = height - pad.top - pad.bottom;

  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);

  const series = opts.series || [];
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  let hasData = false;
  for (const s of series) {
    const pts = s.points || [];
    for (let i = 0; i < pts.length; i++) {
      const pt = pts[i];
      if (Number.isFinite(pt.x) && Number.isFinite(pt.y)) {
        hasData = true;
        if (pt.x < minX) minX = pt.x;
        if (pt.x > maxX) maxX = pt.x;
        if (pt.y < minY) minY = pt.y;
        if (pt.y > maxY) maxY = pt.y;
      }
      if (Number.isFinite(pt.yLo)) {
        if (pt.yLo < minY) minY = pt.yLo;
        if (pt.yLo > maxY) maxY = pt.yLo;
      }
      if (Number.isFinite(pt.yHi)) {
        if (pt.yHi < minY) minY = pt.yHi;
        if (pt.yHi > maxY) maxY = pt.yHi;
      }
    }
  }
  if (!hasData) {
    ctx.fillStyle = "#64748b";
    ctx.font = "600 13px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(opts.emptyText || "Chưa có dữ liệu biểu đồ", width / 2, height / 2);
    return;
  }

  let xMin = opts.xMin !== undefined ? opts.xMin : minX;
  let xMax = opts.xMax !== undefined ? opts.xMax : maxX;
  let yMin = opts.yMin !== undefined ? opts.yMin : minY;
  let yMax = opts.yMax !== undefined ? opts.yMax : maxY;

  if (xMin === xMax) { xMin -= 1; xMax += 1; }
  if (yMin === yMax) { yMin -= 1; yMax += 1; }
  const yMargin = (yMax - yMin) * 0.08;
  if (opts.yMin === undefined) yMin -= yMargin;
  if (opts.yMax === undefined) yMax += yMargin;

  const toPxX = (x) => pad.left + ((x - xMin) / (xMax - xMin)) * pw;
  const toPxY = (y) => {
    const frac = (y - yMin) / (yMax - yMin);
    return opts.invertY ? pad.top + frac * ph : pad.top + (1 - frac) * ph;
  };

  // Lưới & trục
  const xt = niceTicks(xMin, xMax, 5);
  const yt = niceTicks(yMin, yMax, 5);
  ctx.strokeStyle = "#e2e8f0";
  ctx.lineWidth = 1;
  ctx.setLineDash([4, 3]);
  for (const xv of xt.ticks) {
    const px = toPxX(xv);
    ctx.beginPath();
    ctx.moveTo(px, pad.top);
    ctx.lineTo(px, pad.top + ph);
    ctx.stroke();
  }
  for (const yv of yt.ticks) {
    const py = toPxY(yv);
    ctx.beginPath();
    ctx.moveTo(pad.left, py);
    ctx.lineTo(pad.left + pw, py);
    ctx.stroke();
  }
  ctx.setLineDash([]);

  // Khung trục
  ctx.strokeStyle = "#94a3b8";
  ctx.lineWidth = 1.2;
  ctx.beginPath();
  ctx.moveTo(pad.left, pad.top);
  ctx.lineTo(pad.left, pad.top + ph);
  ctx.lineTo(pad.left + pw, pad.top + ph);
  ctx.stroke();

  // Nhãn tick trục
  ctx.fillStyle = "#475569";
  ctx.font = "600 10.5px sans-serif";
  ctx.textAlign = "center";
  for (const xv of xt.ticks) {
    const label = opts.xFormatter ? opts.xFormatter(xv) : formatTickVal(xv, xt.step);
    ctx.fillText(label, toPxX(xv), pad.top + ph + 15);
  }
  ctx.textAlign = "right";
  for (const yv of yt.ticks) {
    ctx.fillText(formatTickVal(yv, yt.step), pad.left - 6, toPxY(yv) + 3.5);
  }

  // Nhãn trục X & Y & Tiêu đề
  ctx.fillStyle = "#0b1d3a";
  ctx.font = "700 11.5px sans-serif";
  ctx.textAlign = "center";
  if (opts.title) ctx.fillText(opts.title, pad.left + pw / 2, 16);
  if (opts.xLabel) ctx.fillText(opts.xLabel, pad.left + pw / 2, height - 6);
  if (opts.yLabel) {
    ctx.save();
    ctx.translate(14, pad.top + ph / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText(opts.yLabel, 0, 0);
    ctx.restore();
  }

  // Dải fillBetween nếu có
  for (const s of series) {
    if (s.type === "band" && s.points.length >= 2) {
      ctx.save();
      ctx.fillStyle = s.fill || "rgba(229, 56, 59, 0.16)";
      ctx.beginPath();
      s.points.forEach((pt, idx) => {
        const px = toPxX(pt.x);
        const py = toPxY(pt.yHi);
        if (idx === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      });
      for (let i = s.points.length - 1; i >= 0; i--) {
        const pt = s.points[i];
        ctx.lineTo(toPxX(pt.x), toPxY(pt.yLo));
      }
      ctx.closePath();
      ctx.fill();
      ctx.restore();
    }
  }

  // Các đường tham chiếu dọc & ngang
  for (const vl of opts.vlines || []) {
    if (!Number.isFinite(vl.x)) continue;
    const px = toPxX(vl.x);
    if (px < pad.left || px > pad.left + pw) continue;
    ctx.save();
    ctx.strokeStyle = vl.color || "#0f766e";
    ctx.lineWidth = vl.width || 1.6;
    if (vl.dash) ctx.setLineDash(vl.dash);
    ctx.beginPath();
    ctx.moveTo(px, pad.top);
    ctx.lineTo(px, pad.top + ph);
    ctx.stroke();
    ctx.restore();
  }
  for (const hl of opts.hlines || []) {
    if (!Number.isFinite(hl.y)) continue;
    const py = toPxY(hl.y);
    if (py < pad.top || py > pad.top + ph) continue;
    ctx.save();
    ctx.strokeStyle = hl.color || "#f59e0b";
    ctx.lineWidth = hl.width || 1.4;
    if (hl.dash) ctx.setLineDash(hl.dash);
    ctx.beginPath();
    ctx.moveTo(pad.left, py);
    ctx.lineTo(pad.left + pw, py);
    ctx.stroke();
    ctx.restore();
  }

  // Vẽ series line & scatter
  const hoverTargets = [];
  for (const s of series) {
    if (s.type === "band") continue;
    const pts = (s.points || []).filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y));
    if (!pts.length) continue;

    if (s.type === "line" || s.type === "line-markers") {
      ctx.save();
      ctx.strokeStyle = s.color || "#e5383b";
      ctx.lineWidth = s.width || 2;
      if (s.dash) ctx.setLineDash(s.dash);
      ctx.beginPath();
      pts.forEach((p, idx) => {
        const px = toPxX(p.x);
        const py = toPxY(p.y);
        if (idx === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      });
      ctx.stroke();
      ctx.restore();
    }

    if (s.type === "scatter" || s.type === "line-markers") {
      ctx.save();
      ctx.fillStyle = s.color || "#1b4965";
      ctx.strokeStyle = s.color || "#1b4965";
      const r = s.radius || 3.2;
      for (const p of pts) {
        const px = toPxX(p.x);
        const py = toPxY(p.y);
        if (s.marker === "x") {
          ctx.lineWidth = 1.8;
          ctx.beginPath();
          ctx.moveTo(px - r, py - r);
          ctx.lineTo(px + r, py + r);
          ctx.moveTo(px + r, py - r);
          ctx.lineTo(px - r, py + r);
          ctx.stroke();
        } else {
          ctx.beginPath();
          ctx.arc(px, py, r, 0, Math.PI * 2);
          ctx.fill();
        }
        hoverTargets.push({ px, py, x: p.x, y: p.y, label: s.label || "" });
      }
      ctx.restore();
    } else {
      for (let i = 0; i < pts.length; i += Math.max(1, Math.floor(pts.length / 45))) {
        const p = pts[i];
        hoverTargets.push({ px: toPxX(p.x), py: toPxY(p.y), x: p.x, y: p.y, label: s.label || "" });
      }
    }
  }

  // Legend gọn ở góc trên phải
  const legendItems = series.filter((s) => s.label && s.type !== "band").slice(0, 6);
  if (legendItems.length) {
    ctx.font = "600 10px sans-serif";
    const ly = pad.top + 8;
    let lx = pad.left + 10;
    for (const item of legendItems) {
      const tw = ctx.measureText(item.label).width;
      if (lx + tw + 26 > width - 10) break;
      ctx.fillStyle = "rgba(255,255,255,0.88)";
      ctx.fillRect(lx - 3, ly - 9, tw + 22, 15);
      ctx.fillStyle = item.color || "#0b1d3a";
      ctx.fillRect(lx, ly - 4, 10, 4);
      ctx.fillStyle = "#1e293b";
      ctx.textAlign = "left";
      ctx.fillText(item.label, lx + 14, ly);
      lx += tw + 28;
    }
  }

  // Gắn tooltip tương tác (gom theo requestAnimationFrame để không gây giật khi rê chuột)
  if (tooltipEl) {
    let hoverRaf = 0;
    let lastEv = null;
    canvas.onmousemove = (ev) => {
      lastEv = ev;
      if (hoverRaf) return;
      hoverRaf = requestAnimationFrame(() => {
        hoverRaf = 0;
        if (!lastEv) return;
        const rect = canvas.getBoundingClientRect();
        const mx = lastEv.clientX - rect.left;
        const my = lastEv.clientY - rect.top;
        let best = null;
        let bestDist = 18 * 18;
        for (let i = 0; i < hoverTargets.length; i++) {
          const t = hoverTargets[i];
          const dx = t.px - mx;
          const dy = t.py - my;
          const d2 = dx * dx + dy * dy;
          if (d2 < bestDist) {
            bestDist = d2;
            best = t;
          }
        }
        if (best) {
          tooltipEl.style.display = "block";
          tooltipEl.style.left = `${Math.min(mx + 12, width - 150)}px`;
          tooltipEl.style.top = `${Math.max(my - 32, 6)}px`;
          tooltipEl.textContent = `${best.label ? best.label + ": " : ""}(${best.x.toFixed(2)}, ${best.y.toFixed(2)})`;
        } else {
          tooltipEl.style.display = "none";
        }
      });
    };
    canvas.onmouseleave = () => {
      lastEv = null;
      if (hoverRaf) {
        cancelAnimationFrame(hoverRaf);
        hoverRaf = 0;
      }
      tooltipEl.style.display = "none";
    };
  }
}

function drawHorizontalBarChart(canvas, tooltipEl, opts) {
  if (!canvas || !canvas.offsetParent) return;
  const { ctx, width, height } = setupCanvas(canvas);
  const bars = opts.bars || [];
  const pad = { top: 28, right: 64, bottom: 32, left: 162 };
  const pw = Math.max(80, width - pad.left - pad.right);
  const ph = height - pad.top - pad.bottom;

  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);

  if (!bars.length) return;
  const maxVal = Math.max(0.01, ...bars.map((b) => b.value)) * 1.15;

  ctx.fillStyle = "#0b1d3a";
  ctx.font = "700 11.5px sans-serif";
  ctx.textAlign = "center";
  ctx.fillText(opts.title || "", pad.left + pw / 2, 16);

  const rowH = ph / bars.length;
  bars.forEach((b, idx) => {
    const cy = pad.top + idx * rowH + rowH * 0.2;
    const bh = Math.max(14, rowH * 0.58);
    const bw = (b.value / maxVal) * pw;

    // 2.5D Shadow ledge dưới thanh
    ctx.fillStyle = "rgba(15, 23, 42, 0.14)";
    ctx.fillRect(pad.left, cy + 3, Math.max(2, bw), bh);

    ctx.fillStyle = b.color || "#14b8a6";
    ctx.fillRect(pad.left, cy, Math.max(2, bw), bh);

    ctx.fillStyle = "#334155";
    ctx.font = "600 10.5px sans-serif";
    ctx.textAlign = "right";
    ctx.fillText(b.label, pad.left - 8, cy + bh / 2 + 4);

    ctx.fillStyle = "#0b1d3a";
    ctx.font = "700 10.5px monospace";
    ctx.textAlign = "left";
    ctx.fillText(`${b.value.toFixed(4)} ‰`, pad.left + Math.max(4, bw) + 6, cy + bh / 2 + 4);
  });

  if (tooltipEl) tooltipEl.style.display = "none";
}

/* ==========================================================================
   Khởi Tạo & Đồng Bộ Giao Diện Chung
   ========================================================================== */
function populateProfileSelect(profiles) {
  const sel = $("#sb-profile-select");
  if (!sel) return;
  const list = Array.isArray(profiles) ? [...profiles] : ["mac_dinh"];
  if (!list.includes("mac_dinh")) list.unshift("mac_dinh");
  if (STATE.hoSo && !list.includes(STATE.hoSo)) list.push(STATE.hoSo);
  sel.innerHTML = list
    .map((p) => {
      const label = p === "mac_dinh" ? "🏠 Mặc định (chung)" : `🏡 ${p}`;
      return `<option value="${esc(p)}">${esc(label)}</option>`;
    })
    .join("");
  sel.value = STATE.hoSo || "mac_dinh";
}

function updateNetworkPill() {
  const pill = $("#net-status-pill");
  if (!pill) return;
  if (navigator.onLine) {
    pill.className = "pill-25d pill-green";
    pill.textContent = "🟢 Trực tuyến";
  } else {
    pill.className = "pill-25d pill-amber";
    pill.textContent = "🟠 Ngoại tuyến (Offline)";
  }
}

function getOfflineQueue() {
  try {
    const raw = localStorage.getItem(OFFLINE_QUEUE_KEY);
    const arr = raw ? JSON.parse(raw) : [];
    return Array.isArray(arr) ? arr : [];
  } catch (_) {
    return [];
  }
}

function saveOfflineQueue(arr) {
  try {
    localStorage.setItem(OFFLINE_QUEUE_KEY, JSON.stringify(arr));
  } catch (_) {}
  updateOfflineQueueBadge();
}

function updateOfflineQueueBadge() {
  const pill = $("#offline-queue-pill");
  const cnt = $("#offline-queue-count");
  if (!pill || !cnt) return;
  const n = getOfflineQueue().length;
  cnt.textContent = String(n);
  pill.style.display = n > 0 ? "inline-flex" : "none";
}

async function flushOfflineQueue(silent = false) {
  const q = getOfflineQueue();
  if (!q.length) return;
  if (!navigator.onLine) {
    if (!silent) toast("🟠 Chưa có kết nối mạng để đồng bộ.");
    return;
  }
  const remaining = [];
  let synced = 0;
  for (const item of q) {
    try {
      await apiPost("/api/logs/add", item);
      synced += 1;
    } catch (_) {
      remaining.push(item);
    }
  }
  saveOfflineQueue(remaining);
  if (synced > 0) {
    await loadLogs();
    toast(`✅ Đã đồng bộ ${synced} bản ghi ngoại tuyến lên máy chủ!`);
  } else if (!silent) {
    toast("⚠️ Máy chủ chưa phản hồi, bản ghi vẫn được giữ an toàn trên máy.");
  }
}

async function loadBootstrap() {
  try {
    const data = await apiGet(`/api/bootstrap?ho_so=${encodeURIComponent(STATE.hoSo || "mac_dinh")}`);
    STATE.bootstrap = data;
    populateProfileSelect(data.all_profiles);
    if (Array.isArray(data.all_locations)) refreshLocationSuggestions(data.all_locations);
    updateModelBadges(data.mo_hinh, data.quang_hoc, data.so_ban_ghi_nhat_ki);
    populateSpeciesDropdowns(data.danh_sach_loai);
    renderSpeciesFullTable(data.danh_sach_loai);
    $("#t5-a").value = data.quang_hoc.A_do;
    $("#val-t5-a").textContent = `${Number(data.quang_hoc.A_do).toFixed(1)}°`;
    $("#t5-d").value = data.quang_hoc.D_m;
    $("#val-t5-d").textContent = `${Number(data.quang_hoc.D_m).toFixed(1)} m`;
    $("#t5-pxmm").value = data.quang_hoc.pixel_mm;
  } catch (err) {
    toast(`Lỗi nạp cấu hình: ${err.message}`);
  }
}

function updateModelBadges(mh, qh, logCount) {
  const isSim = Boolean(mh.la_mo_phong);
  const isRealVerified = !isSim && Boolean(mh.da_xac_nhan_thuc_te);
  const badge = $("#badge-model-mode");
  const sbBox = $("#sb-calib-status");
  if (isSim) {
    badge.className = "pill-25d pill-amber";
    badge.textContent = "🧪 CHƯA HIỆU CHUẨN (MÔ PHỎNG)";
    sbBox.className = "sb-card-25d status-sim";
    $("#sb-calib-body").innerHTML =
      `<b>CHƯA HIỆU CHUẨN (MÔ PHỎNG)</b><br>Bậc ${mh.bac} | R² = ${fmt(mh.R2, 5)}<br>` +
      `Dải S: ${fmt(mh.S_min, 0)}–${fmt(mh.S_max, 0)} ‰ | T: ${fmt(mh.T_min, 1)}–${fmt(mh.T_max, 1)} °C`;
  } else if (isRealVerified) {
    badge.className = "pill-25d pill-green";
    badge.textContent = "✅ ĐÃ HIỆU CHUẨN (dữ liệu đo thật)";
    sbBox.className = "sb-card-25d status-real";
    $("#sb-calib-body").innerHTML =
      `<b>ĐÃ HIỆU CHUẨN (dữ liệu đo thật)</b><br>Bậc ${mh.bac} | R² = ${fmt(mh.R2, 5)} | ${mh.so_diem} mẫu<br>` +
      `Dải S: ${fmt(mh.S_min, 0)}–${fmt(mh.S_max, 0)} ‰`;
  } else {
    badge.className = "pill-25d pill-amber";
    badge.textContent = "⚠️ CHƯA XÁC NHẬN NGUỒN DỮ LIỆU";
    sbBox.className = "sb-card-25d status-sim";
    $("#sb-calib-body").innerHTML =
      `<b>CHƯA XÁC NHẬN NGUỒN DỮ LIỆU</b><br>Bậc ${mh.bac} | R² = ${fmt(mh.R2, 5)} | ${mh.so_diem} mẫu<br>` +
      `Thiếu nguon_du_lieu=THUC_TE • Dải S: ${fmt(mh.S_min, 0)}–${fmt(mh.S_max, 0)} ‰`;
  }
  if (qh) {
    $("#badge-prism").textContent = `📐 Lăng kính A = ${Number(qh.A_do).toFixed(1)}°`;
    $("#sb-optics-specs").innerHTML =
      `• Góc đỉnh A: <b>${Number(qh.A_do).toFixed(1)}°</b><br>` +
      `• Khoảng cách màn D: <b>${Number(qh.D_m).toFixed(1)} m</b><br>` +
      `• Bước sóng laser: <b>${qh.lambda_nm} nm (≤ 1 mW)</b><br>` +
      `• Độ nhạy lí thuyết: <b>~${fmt(qh.do_nhay_mac_dinh, 2)} px/‰</b>`;
  }
  if (logCount !== undefined) {
    $("#hero-log-count").textContent = String(logCount);
  }
}

function populateSpeciesDropdowns(list) {
  const html = list.map((s) => `<option value="${esc(s.ma_loai)}">${esc(s.ten_hien_thi)}</option>`).join("");
  const cur1 = $("#t1-species-select").value;
  const cur2 = $("#t2-species-select").value;
  $("#t1-species-select").innerHTML = html;
  $("#t2-species-select").innerHTML = html;
  if (cur1 && list.some((s) => s.ma_loai === cur1)) $("#t1-species-select").value = cur1;
  if (cur2 && list.some((s) => s.ma_loai === cur2)) $("#t2-species-select").value = cur2;

  const editSel = $("#t2-edit-preset");
  if (editSel) {
    const curEdit = editSel.value;
    editSel.innerHTML =
      `<option value="__new__">➕ Thêm loài / cây trồng mới</option>` + html;
    if (curEdit && (curEdit === "__new__" || list.some((s) => s.ma_loai === curEdit))) {
      editSel.value = curEdit;
    }
  }
}

function updateCoachBar() {
  const bar = $("#coach-bar");
  bar.style.display = $("#toggle-coach").checked ? "block" : "none";
  const measured = STATE.lastMeasure !== null;
  const saved = STATE.savedCurrentLog;
  const valid = measured && STATE.lastMeasure.chat_luong.hop_le;

  const s1 = $("#cs-1"), s2 = $("#cs-2"), s3 = $("#cs-3"), s4 = $("#cs-4");
  [s1, s2, s3, s4].forEach((el) => el.classList.remove("done", "active"));

  if (!measured) {
    s1.classList.add("done");
    s2.classList.add("active");
    $("#coach-icon").textContent = "📸";
    $("#coach-title").textContent = "Bước 2/4: Chọn nguồn ảnh & Tiến hành đo độ mặn";
    $("#coach-desc").textContent = "Kéo thanh trượt mô phỏng hoặc tải ảnh chụp thực tế rồi nhấn Tiến hành đo.";
  } else if (!saved) {
    s1.classList.add("done");
    s2.classList.add("done");
    s3.classList.add("active");
    if (valid && STATE.lastMeasure.mo_hinh_man) {
      const km = STATE.lastMeasure.mo_hinh_man;
      $("#coach-icon").textContent = "✅";
      $("#coach-title").textContent = `Bước 3/4: Đã đo xong — Độ mặn S = ${fmt(km.S_ppt, 2)} ± ${fmt(km.U_S_ppt, 2)} ‰`;
      $("#coach-desc").textContent = "Kiểm tra cảnh báo theo loài và nhấn 'Lưu kết quả vào Nhật kí SQLite'.";
    } else {
      $("#coach-icon").textContent = "⚠️";
      $("#coach-title").textContent = "Bước 3/4: Kiểm tra cảnh báo chất lượng ảnh chụp";
      $("#coach-desc").textContent = "Phát hiện ảnh bị bão hòa/mờ hoặc ngoài dải hiệu chuẩn. Điều chỉnh lại thông số trước khi lưu.";
    }
  } else {
    [s1, s2, s3, s4].forEach((el) => el.classList.add("done"));
    $("#coach-icon").textContent = "🎉";
    $("#coach-title").textContent = "Hoàn thành chu trình 4 bước — Bản ghi đã được lưu vào Nhật kí SQLite!";
    $("#coach-desc").textContent = "Bạn có thể tiếp tục đo mẫu mới hoặc mở Tab 3 để xem biểu đồ chuỗi thời gian và xuất CSV.";
  }
}

/* ==========================================================================
   TAB 1: ĐO ĐỘ MẶN & ĐỘ ĐỤC TỪ ẢNH
   ========================================================================== */
function getTab1Payload() {
  const dungRoi = $("#roi-manual-enable").checked;
  const payload = {
    mode: STATE.imgMode === "sim" ? "sim" : "upload",
    nhiet_do_do: Number($("#meas-temp").value || 25),
    phuong_phap: $("#meas-method").value,
    dung_roi_thu_cong: dungRoi,
    ma_loai: $("#t1-species-select").value,
  };
  if (STATE.imgMode === "sim") {
    payload.S_ppt = Number($("#sim-s").value);
    payload.T_C = Number($("#sim-t").value);
    payload.do_duc = Number($("#sim-duc").value);
    payload.drift_px = Number($("#sim-drift").value);
    payload.bo_tri = $("#sim-layout").value;
    payload.cho_phep_bao_hoa = $("#sim-saturate").checked;
  } else {
    payload.image_base64 = currentInputImage();
  }
  if (dungRoi) {
    const wGuess = (STATE.lastMeasure && STATE.lastMeasure.anh_width) || 400;
    const mid = Math.floor(wGuess / 2);
    payload.roi_tc = [Number($("#roi-tc-y0").value), Number($("#roi-tc-y1").value), 5, mid - 8];
    payload.roi_mau = [Number($("#roi-m-y0").value), Number($("#roi-m-y1").value), mid + 8, wGuess - 5];
  }
  return payload;
}

function currentInputImage() {
  if (STATE.imgMode === "camera") return STATE.cameraImageB64;
  if (STATE.imgMode === "upload") return STATE.uploadImageB64;
  return null;
}

const DEFAULT_IMG_CAPTION = "Vạch xanh: nước chuẩn (0 ‰) • Vạch cam: mẫu nước • Vàng: khoảng lệch Δy";

/** Hiển thị lỗi thân thiện khi ảnh tải lên / chụp không nhận diện được 2 vạch laser. */
function showMeasureError(message) {
  STATE.lastMeasure = null;
  STATE.savedCurrentLog = false;

  $("#kpi-s-val").textContent = "--";
  $("#kpi-s-u").textContent = "± -- ‰";
  $("#kpi-s-sub").textContent = "Chưa đo được";
  $("#kpi-duc-val").textContent = "--";
  $("#kpi-duc-level").textContent = "--";

  const raw = currentInputImage();
  const img = $("#t1-annotated-img");
  if (raw) {
    img.src = raw;
    img.classList.add("is-raw-error");
    $("#t1-img-caption").textContent = "⚠️ Ảnh gốc bạn vừa đưa vào — chưa nhận diện được 2 vạch laser.";
  }

  const vBox = $("#t1-species-verdict");
  vBox.className = "banner-25d danger";
  vBox.innerHTML = `<div class="banner-icon">📷</div><div>
    <b>Chưa đọc được ảnh.</b> ${esc(message)}
    <ul style="margin:6px 0 0; padding-left:18px;">
      <li>Che tối xung quanh, chỉ để lại 2 vạch laser sáng.</li>
      <li>Giữ máy thẳng, không rung, để cả 2 vạch nằm gọn trong khung.</li>
      <li>Không để vạch bị chói trắng (giảm độ sáng nếu cần).</li>
    </ul>
  </div>`;
  $("#t1-warnings-box").innerHTML = "";
  updateCoachBar();
}

async function runMeasure(opts) {
  const silent = Boolean(opts && opts.silent === true);
  if (STATE.imgMode !== "sim" && !currentInputImage()) {
    if (!silent) {
      toast(
        STATE.imgMode === "camera"
          ? "Hãy bật Camera và nhấn Chụp & Đo trước."
          : "Vui lòng chọn ảnh hoặc chụp ảnh bằng điện thoại trước khi đo."
      );
    }
    return;
  }
  const seq = ++STATE.measureSeq;
  const btn = $("#btn-run-measure");
  const oldLabel = btn.dataset.origLabel || btn.textContent;
  btn.dataset.origLabel = oldLabel;
  const showBusy = STATE.imgMode !== "sim";
  if (showBusy) {
    btn.disabled = true;
    btn.textContent = "⏳ Đang phân tích ảnh...";
  }
  try {
    const data = await apiPost("/api/measure", getTab1Payload(), "measure");
    if (seq !== STATE.measureSeq) return;
    STATE.lastMeasure = data;
    STATE.savedCurrentLog = false;
    $("#t1-annotated-img").classList.remove("is-raw-error");
    $("#t1-img-caption").textContent = DEFAULT_IMG_CAPTION;
    renderMeasureResults(data);
    updateCoachBar();
  } catch (err) {
    if (isAbortError(err) || seq !== STATE.measureSeq) return;
    if (STATE.imgMode !== "sim") {
      showMeasureError(err.message);
    } else {
      toast(`Lỗi đo ảnh: ${err.message}`);
    }
  } finally {
    if (showBusy && seq === STATE.measureSeq) {
      btn.disabled = false;
      btn.textContent = oldLabel;
    }
  }
}

function renderMeasureResults(d) {
  if (!d) return;
  const km = d.mo_hinh_man;
  const cq = d.chat_luong;
  const mp = d.chan_li_mp;

  if (km) {
    $("#kpi-s-val").textContent = fmt(km.S_ppt, 2);
    $("#kpi-s-u").textContent = `± ${fmt(km.U_S_ppt, 2)} ‰`;
    $("#kpi-s-sub").textContent = mp
      ? `Chân lí MP: ${fmt(mp.S_chan_li, 2)} ‰ (Lệch ${Number(km.S_ppt - mp.S_chan_li) >= 0 ? "+" : ""}${fmt(km.S_ppt - mp.S_chan_li, 3)} ‰)`
      : `Khoảng tin cậy 95% (k = ${km.k})`;
  } else {
    $("#kpi-s-val").textContent = "N/A";
    $("#kpi-s-u").textContent = d.error_man || "Ngoài dải / lỗi";
    $("#kpi-s-sub").textContent = "Không giải ngược được độ mặn";
  }

  $("#kpi-dy-val").textContent = fmt(d.delta_y_px, 2);
  $("#kpi-dy-err").textContent = `± ${fmt(d.sai_so_delta_y_px, 3)} px`;
  $("#kpi-dy-sub").textContent = mp
    ? `Snell lí thuyết: ${fmt(mp.delta_y_snell, 2)} px | Rung: ${mp.drift_px >= 0 ? "+" : ""}${fmt(mp.drift_px, 1)} px`
    : `R² Gauss: ${fmt(d.vach_mau.r2_trung_binh, 3)} (${d.vach_mau.so_cot_hop_le} cột)`;

  const duc = Number(d.chi_so_do_duc_tuong_doi || 0);
  const mucDuc = duc < 0.2 ? "Trong suốt" : duc < 0.55 ? "Hơi đục (lơ lửng)" : "Rất đục (tán xạ mạnh)";
  $("#kpi-duc-val").textContent = fmt(duc, 2);
  $("#kpi-duc-level").textContent = mucDuc;
  $("#kpi-duc-sub").textContent = `FWHM mẫu: ${fmt(cq.fwhm_mau, 2)} px (TC: ${fmt(cq.fwhm_tc, 2)} px)`;

  const qCard = $("#kpi-qual-card");
  qCard.className = `kpi-card-25d ${cq.hop_le ? "tone-emerald" : "tone-red"}`;
  $("#kpi-qual-val").textContent = cq.hop_le ? "ĐẠT CHUẨN" : "CẦN LƯU Ý";
  $("#kpi-qual-snr").textContent = `SNR = ${fmt(cq.snr, 1)}`;
  $("#kpi-qual-sub").textContent = `Bão hòa (≥250): ${fmt(cq.ti_le_bao_hoa * 100, 2)}% pixel`;

  // Đánh giá theo loài
  const dg = d.danh_gia_loai;
  const vBox = $("#t1-species-verdict");
  if (dg) {
    const cls = dg.trang_thai === "AN_TOAN" ? "ok" : dg.trang_thai === "CANH_BAO" ? "warn" : dg.trang_thai === "NGUY_HIEM" ? "danger" : "info";
    vBox.className = `banner-25d ${cls}`;
    vBox.innerHTML = `<div class="banner-icon">🔎</div><div><b>${esc(dg.tieu_de)}</b><br>${esc(dg.loi_khuyen)}</div>`;
  } else {
    vBox.className = "banner-25d warn";
    vBox.innerHTML = `<div class="banner-icon">⚠️</div><div>Chưa có ước lượng độ mặn hợp lệ để đối chiếu loài.</div>`;
  }

  // Cảnh báo chất lượng & mô hình
  const warnItems = [];
  for (const w of cq.canh_bao || []) warnItems.push({ cls: "warn", icon: "⚠️", text: w });
  if (km) {
    for (const w of km.canh_bao || []) warnItems.push({ cls: w.includes("NGOÀI") ? "danger" : "warn", icon: "🚨", text: w });
  }
  $("#t1-warnings-box").innerHTML = warnItems
    .map((w) => `<div class="banner-25d ${w.cls}"><div class="banner-icon">${w.icon}</div><div>${esc(w.text)}</div></div>`)
    .join("");

  // Ảnh đánh dấu
  if (d.anh_danh_dau_b64) {
    $("#t1-annotated-img").src = d.anh_danh_dau_b64;
  }

  // Bảng thông số 2 vạch
  const tc = d.vach_tham_chieu, vm = d.vach_mau;
  $("#t1-line-stats-body").innerHTML = `
    <tr><td>Tọa độ tâm tại x_ref (px)</td><td><b>${fmt(tc.y_tam, 3)} ± ${fmt(tc.sai_so_y, 3)}</b></td><td><b>${fmt(vm.y_tam, 3)} ± ${fmt(vm.sai_so_y, 3)}</b></td></tr>
    <tr><td>Độ rộng FWHM (px)</td><td>${fmt(tc.fwhm_trung_binh, 2)}</td><td>${fmt(vm.fwhm_trung_binh, 2)}</td></tr>
    <tr><td>Biên độ đỉnh TB (0–255)</td><td>${fmt(tc.cuong_do_dinh_tb, 1)}</td><td>${fmt(vm.cuong_do_dinh_tb, 1)}</td></tr>
    <tr><td>Hệ số xác định R² Gauss</td><td>${fmt(tc.r2_trung_binh, 4)}</td><td>${fmt(vm.r2_trung_binh, 4)}</td></tr>
    <tr><td>Số cột hợp lệ</td><td>${tc.so_cot_hop_le} / ${tc.so_cot_tong}</td><td>${vm.so_cot_hop_le} / ${vm.so_cot_tong}</td></tr>
  `;

  drawTab1Charts(d);
}

function drawTab1Charts(d) {
  if (!d) return;
  const prof = d.profile;
  if (prof) {
    const ptsTc = prof.y_coords.map((y, idx) => ({ x: y, y: prof.prof_tc[idx] }));
    const ptsM = prof.y_coords.map((y, idx) => ({ x: y, y: prof.prof_mau[idx] }));
    drawXYChart($("#canvas-gauss-profile"), $("#tip-gauss-profile"), {
      title: "Mặt cắt cường độ sáng I(y) tại tâm vạch",
      xLabel: "Tọa độ đứng y (pixel)",
      yLabel: "Cường độ I(y)",
      yMin: 0,
      yMax: 265,
      series: [
        { type: "line", color: "#10b981", width: 2, label: `Vạch TC (x=${prof.col_tc})`, points: ptsTc },
        { type: "line", color: "#e5383b", width: 2, label: `Vạch Mẫu (x=${prof.col_mau})`, points: ptsM },
      ],
      vlines: [
        { x: prof.y_tam_tc, color: "#047857", dash: [5, 3], width: 1.6 },
        { x: prof.y_tam_mau, color: "#991b1b", dash: [5, 3], width: 1.6 },
      ],
      hlines: [{ y: 250, color: "#f59e0b", dash: [3, 3], width: 1.2 }],
    });

    const w = prof.width || 400;
    const xLine = [0, w - 1];
    drawXYChart($("#canvas-line-fit"), $("#tip-line-fit"), {
      title: `Hồi quy đường thẳng tâm vạch (Δy = ${fmt(d.delta_y_px, 2)} px)`,
      xLabel: "Tọa độ ngang x (pixel)",
      yLabel: "Tọa độ tâm y (px)",
      invertY: true,
      xMin: 0,
      xMax: w,
      series: [
        { type: "scatter", color: "#34d399", radius: 2.3, label: "Tâm cột TC", points: (prof.x_tc || []).map((xv, i) => ({ x: xv, y: prof.y_tc[i] })) },
        { type: "scatter", color: "#f87171", radius: 2.3, label: "Tâm cột Mẫu", points: (prof.x_mau || []).map((xv, i) => ({ x: xv, y: prof.y_mau[i] })) },
        { type: "line", color: "#047857", width: 2, label: "Khớp TC", points: xLine.map((xv) => ({ x: xv, y: prof.do_doc_tc * xv + prof.he_so_b_tc })) },
        { type: "line", color: "#b91c1c", width: 2, label: "Khớp Mẫu", points: xLine.map((xv) => ({ x: xv, y: prof.do_doc_mau * xv + prof.he_so_b_mau })) },
      ],
      vlines: [{ x: prof.x_ref, color: "#f59e0b", dash: [5, 4], width: 1.8 }],
    });
  }

  const km = d.mo_hinh_man;
  if (km && km.thanh_phan_bat_dinh) {
    const mapLabel = {
      do_anh: "Định vị tâm vạch (σ_Δy)",
      lap_lai_duong_chuan: "Độ tản mát chuẩn (s_res)",
      he_so_duong_chuan: "Hệ số hồi quy (u_fit)",
      nhiet_do: "Nhiệt kế & bù nhiệt (σ_T)",
    };
    const colors = ["#14b8a6", "#1b4965", "#f59e0b", "#e5383b"];
    const bars = Object.entries(km.thanh_phan_bat_dinh).map(([k, v], i) => ({
      label: mapLabel[k] || k,
      value: Number(v || 0),
      color: colors[i % colors.length],
    }));
    drawHorizontalBarChart($("#canvas-gum-bar"), $("#tip-gum-bar"), {
      title: `Tổng hợp bất định chuẩn u_c = ${fmt(km.u_S_ppt, 3)} ‰ (k=${km.k} -> U=${fmt(km.U_S_ppt, 3)} ‰)`,
      bars,
    });
  }
}

async function saveMeasurementToLog() {
  if (!STATE.lastMeasure || !STATE.lastMeasure.mo_hinh_man) {
    toast("Chưa có kết quả độ mặn hợp lệ để lưu!");
    return;
  }
  const d = STATE.lastMeasure;
  const km = d.mo_hinh_man;
  const spName = $("#t1-species-select").selectedOptions[0]?.textContent || "Chưa chọn";
  const nguon = (d.la_anh_mo_phong || km.la_mo_phong)
    ? "MÔ PHỎNG"
    : (km.da_xac_nhan_thuc_te ? "ĐO THẬT" : "CHƯA XÁC NHẬN NGUỒN");
  const now = new Date();
  const pad2 = (n) => String(n).padStart(2, "0");
  const tsLocal = `${now.getFullYear()}-${pad2(now.getMonth() + 1)}-${pad2(now.getDate())} ${pad2(now.getHours())}:${pad2(now.getMinutes())}:${pad2(now.getSeconds())}`;
  const payload = {
    ho_so: STATE.hoSo || "mac_dinh",
    thoi_gian: tsLocal,
    vi_tri: $("#meas-location").value || "Ao nuôi tôm số 1",
    loai_nuoi: spName,
    delta_y_px: Number(d.delta_y_px.toFixed(3)),
    do_man_ppt: Number(km.S_ppt.toFixed(3)),
    bat_dinh_U_ppt: Number(km.U_S_ppt.toFixed(3)),
    nhiet_do_C: Number($("#meas-temp").value || 25),
    do_duc: Number(d.chi_so_do_duc_tuong_doi.toFixed(3)),
    chat_luong_hop_le: d.chat_luong.hop_le,
    nguon_du_lieu: nguon,
    ghi_chu: $("#meas-note").value || "",
  };

  if (!navigator.onLine) {
    const q = getOfflineQueue();
    q.push(payload);
    saveOfflineQueue(q);
    STATE.savedCurrentLog = true;
    updateCoachBar();
    toast("🟠 Đang mất mạng — đã lưu tạm vào máy (sẽ tự đồng bộ khi có mạng)!");
    return;
  }

  try {
    await apiPost("/api/logs/add", payload);
    STATE.savedCurrentLog = true;
    updateCoachBar();
    await loadLogs();
    toast("✅ Đã lưu kết quả vào Nhật kí SQLite!");
  } catch (err) {
    const isNetErr = err instanceof TypeError || err.offline || !navigator.onLine;
    if (isNetErr) {
      const q = getOfflineQueue();
      q.push(payload);
      saveOfflineQueue(q);
      STATE.savedCurrentLog = true;
      updateCoachBar();
      toast("🟠 Máy chủ tạm gián đoạn — đã lưu hàng đợi ngoại tuyến!");
    } else {
      toast(`Lỗi lưu nhật kí: ${err.message}`);
    }
  }
}

/* ==========================================================================
   TAB 2: CẢNH BÁO AN TOÀN THEO LOÀI (CÓ DỰ PHÒNG OFFLINE + CHỈNH NGƯỠNG)
   ========================================================================== */
function evalOneSpeciesLocal(sVal, info, uVal = 0) {
  const nguon = (info.nguon_tham_khao || "").trim();
  const tv = "Liên hệ cán bộ khuyến nông/khuyến ngư để được tư vấn.";
  const valStr = uVal > 0 ? `${sVal.toFixed(2)} ± ${uVal.toFixed(2)} ‰` : `${sVal.toFixed(2)} ‰`;
  const hasRange =
    (info.an_toan_min !== null && info.an_toan_max !== null) ||
    Boolean(info.canh_bao_thap) ||
    Boolean(info.canh_bao_cao) ||
    (info.nguy_hiem_duoi !== null && info.nguy_hiem_duoi !== undefined) ||
    (info.nguy_hiem_tren !== null && info.nguy_hiem_tren !== undefined);
  if (!info.co_du_lieu_nguon || !nguon || !hasRange) {
    return {
      ma_loai: info.ma_loai,
      ten_loai: info.ten_hien_thi,
      trang_thai: "CHUA_CO_NGUON",
      tieu_de: "CHƯA CÓ NGUỒN THAM KHẢO",
      loi_khuyen: `Đối tượng '${info.ten_hien_thi}' chưa có ngưỡng và nguồn trích dẫn trong config.yaml. Giá trị đo: ${valStr}. ${tv}`,
      nguon_tham_khao: "Chưa có nguồn tài liệu — yêu cầu người dùng điền vào config.yaml",
    };
  }
  const msg = (tt, khoang) =>
    `Trạng thái: ${tt}. Khoảng tham chiếu: ${khoang}. Giá trị đo: ${valStr}. Nguồn: ${nguon}. ${tv}`;
  if (info.nguy_hiem_duoi !== null && info.nguy_hiem_duoi !== undefined && sVal < info.nguy_hiem_duoi) {
    const k = `< ${info.nguy_hiem_duoi} ‰`;
    return {
      ma_loai: info.ma_loai, ten_loai: info.ten_hien_thi, trang_thai: "NGUY_HIEM",
      tieu_de: `NGUY HIỂM: Dưới ngưỡng tham chiếu (${k})`,
      loi_khuyen: msg("NGUY HIỂM (dưới ngưỡng)", k),
      nguon_tham_khao: nguon,
    };
  }
  if (info.nguy_hiem_tren !== null && info.nguy_hiem_tren !== undefined && sVal > info.nguy_hiem_tren) {
    const k = `> ${info.nguy_hiem_tren} ‰`;
    return {
      ma_loai: info.ma_loai, ten_loai: info.ten_hien_thi, trang_thai: "NGUY_HIEM",
      tieu_de: `NGUY HIỂM: Vượt ngưỡng tham chiếu (${k})`,
      loi_khuyen: msg("NGUY HIỂM (vượt ngưỡng)", k),
      nguon_tham_khao: nguon,
    };
  }
  if (Array.isArray(info.canh_bao_thap) && sVal >= info.canh_bao_thap[0] && sVal < info.canh_bao_thap[1]) {
    const k = `${info.canh_bao_thap[0]} – ${info.canh_bao_thap[1]} ‰`;
    return {
      ma_loai: info.ma_loai, ten_loai: info.ten_hien_thi, trang_thai: "CANH_BAO",
      tieu_de: `CẢNH BÁO THẤP (${k})`,
      loi_khuyen: msg("CẢNH BÁO THẤP", k),
      nguon_tham_khao: nguon,
    };
  }
  if (Array.isArray(info.canh_bao_cao) && sVal > info.canh_bao_cao[0] && sVal <= info.canh_bao_cao[1]) {
    const k = `${info.canh_bao_cao[0]} – ${info.canh_bao_cao[1]} ‰`;
    return {
      ma_loai: info.ma_loai, ten_loai: info.ten_hien_thi, trang_thai: "CANH_BAO",
      tieu_de: `CẢNH BÁO CAO (${k})`,
      loi_khuyen: msg("CẢNH BÁO CAO", k),
      nguon_tham_khao: nguon,
    };
  }
  const k = `${info.an_toan_min ?? 0} – ${info.an_toan_max ?? "?"} ‰`;
  return {
    ma_loai: info.ma_loai, ten_loai: info.ten_hien_thi, trang_thai: "AN_TOAN",
    tieu_de: `AN TOÀN: Nằm trong khoảng tham chiếu (${k})`,
    loi_khuyen: msg("AN TOÀN", k),
    nguon_tham_khao: nguon,
  };
}

function buildLocalSpeciesEval(sVal, maLoai) {
  const list = STATE.bootstrap?.danh_sach_loai || [];
  const info = list.find((s) => s.ma_loai === maLoai) || list[0];
  if (!info) return null;
  const ev = evalOneSpeciesLocal(sVal, info);
  let pho = null;
  if (info.co_du_lieu_nguon && info.an_toan_min !== null && info.an_toan_max !== null) {
    const sMax = info.s_max_scale || 40;
    const nhDuoi = info.nguy_hiem_duoi !== null && info.nguy_hiem_duoi !== undefined ? info.nguy_hiem_duoi : 0;
    const nhTren = info.nguy_hiem_tren !== null && info.nguy_hiem_tren !== undefined ? info.nguy_hiem_tren : info.an_toan_max;
    const clamped = Math.max(0, Math.min(sMax, sVal));
    pho = {
      s_max_scale: sMax,
      p_cur: (clamped / sMax) * 100,
      w1: (nhDuoi / sMax) * 100,
      w2: (Math.max(0, info.an_toan_min - nhDuoi) / sMax) * 100,
      w3: (Math.max(0, info.an_toan_max - info.an_toan_min) / sMax) * 100,
      w4: (Math.max(0, nhTren - info.an_toan_max) / sMax) * 100,
      w5: (Math.max(0, sMax - nhTren) / sMax) * 100,
    };
  }
  const ma_tran = list.map((item) => {
    const r = evalOneSpeciesLocal(sVal, item);
    return { ma_loai: item.ma_loai, ten_loai: item.ten_hien_thi, trang_thai: r.trang_thai, tieu_de: r.tieu_de, an_toan_str: item.an_toan_str };
  });
  return { S_ppt: sVal, chi_tiet: { ...ev, pho, info }, ma_tran };
}

function renderSpeciesTab2Data(data, sVal) {
  STATE.speciesLast = data;
  const ct = data.chi_tiet;
  const cls = ct.trang_thai === "AN_TOAN" ? "ok" : ct.trang_thai === "CANH_BAO" ? "warn" : ct.trang_thai === "NGUY_HIEM" ? "danger" : "info";
  $("#t2-verdict-box").className = `banner-25d ${cls}`;
  $("#t2-verdict-box").innerHTML = `<div class="banner-icon">🛡️</div><div><b>${esc(ct.tieu_de)}</b><br>${esc(ct.loi_khuyen)}</div>`;

  if (ct.pho) {
    const p = ct.pho, info = ct.info;
    $("#t2-spectrum-container").innerHTML = `
      <div class="bio-spectrum-25d">
        <div style="display:flex; justify-content:space-between; flex-wrap:wrap; gap:8px;">
          <div style="font-weight:800; color:#0b1d3a;">📏 Phổ thích nghi sinh học: <span style="color:#e5383b;">${esc(info.ten_hien_thi)}</span></div>
          <div style="font-size:0.8rem; color:#475569;">Dải tối ưu: <b>${esc(info.an_toan_str)}</b></div>
        </div>
        <div class="bio-pin-track">
          <div class="bio-pin" style="left:${p.p_cur.toFixed(1)}%;">Mẫu: ${fmt(sVal, 2)} ‰</div>
          <div class="bio-bar-segments">
            <div style="width:${p.w1.toFixed(2)}%; background:#ef4444;" title="Nguy hiểm dưới"></div>
            <div style="width:${p.w2.toFixed(2)}%; background:#f59e0b;" title="Cảnh báo thấp"></div>
            <div style="width:${p.w3.toFixed(2)}%; background:#10b981;" title="An toàn tối ưu"></div>
            <div style="width:${p.w4.toFixed(2)}%; background:#f59e0b;" title="Cảnh báo cao"></div>
            <div style="width:${p.w5.toFixed(2)}%; background:#ef4444;" title="Nguy hiểm trên"></div>
          </div>
        </div>
        <div class="bio-ticks">
          <span>0 ‰</span>
          <span>🟢 An toàn (${esc(info.an_toan_str)})</span>
          <span>🟡 Cảnh báo</span>
          <span>🔴 Nguy hiểm (&gt; ${info.nguy_hiem_tren !== null ? info.nguy_hiem_tren : p.s_max_scale} ‰)</span>
          <span>${p.s_max_scale} ‰</span>
        </div>
      </div>
    `;
  } else {
    $("#t2-spectrum-container").innerHTML = "";
  }

  $("#t2-citation-box").innerHTML = `📚 <b>Nguồn tài liệu trích dẫn:</b> ${esc(ct.nguon_tham_khao)}`;
  $("#t2-matrix-body").innerHTML = (data.ma_tran || []).map((r) => {
    const icon = r.trang_thai === "AN_TOAN" ? "🟢" : r.trang_thai === "CANH_BAO" ? "🟡" : r.trang_thai === "NGUY_HIEM" ? "🔴" : "⚪";
    return `<tr>
      <td><b>${esc(r.ten_loai)}</b></td>
      <td>${icon} ${esc(r.trang_thai)}</td>
      <td>${esc(r.tieu_de)}</td>
      <td>${esc(r.an_toan_str)}</td>
    </tr>`;
  }).join("");
}

async function evaluateSpeciesTab2() {
  const sVal = Number($("#t2-s-input").value || 0);
  const maLoai = $("#t2-species-select").value;
  $("#t2-s-chip").textContent = `${fmt(sVal, 1)} ‰`;
  try {
    if (!navigator.onLine) throw Object.assign(new Error("offline"), { offline: true });
    const data = await apiPost("/api/species-eval", { S_ppt: sVal, ma_loai: maLoai }, "species");
    renderSpeciesTab2Data(data, sVal);
  } catch (err) {
    if (isAbortError(err)) return;
    const localData = buildLocalSpeciesEval(sVal, maLoai);
    if (localData) {
      renderSpeciesTab2Data(localData, sVal);
    } else {
      toast(`Lỗi đánh giá loài: ${err.message}`);
    }
  }
}

function fillSpeciesEditForm(maLoai) {
  const setVal = (id, v) => {
    const el = $(id);
    if (el) el.value = v === null || v === undefined ? "" : String(v);
  };
  if (!maLoai || maLoai === "__new__") {
    ["#t2-sp-code", "#t2-sp-name", "#t2-sp-at-min", "#t2-sp-at-max", "#t2-sp-cbt-min", "#t2-sp-cbt-max", "#t2-sp-cbc-min", "#t2-sp-cbc-max", "#t2-sp-nh-duoi", "#t2-sp-nh-tren", "#t2-sp-source"]
      .forEach((id) => setVal(id, ""));
    return;
  }
  const info = (STATE.bootstrap?.danh_sach_loai || []).find((s) => s.ma_loai === maLoai);
  if (!info) return;
  setVal("#t2-sp-code", info.ma_loai);
  setVal("#t2-sp-name", info.ten_hien_thi);
  setVal("#t2-sp-at-min", info.an_toan_min);
  setVal("#t2-sp-at-max", info.an_toan_max);
  setVal("#t2-sp-cbt-min", info.canh_bao_thap ? info.canh_bao_thap[0] : "");
  setVal("#t2-sp-cbt-max", info.canh_bao_thap ? info.canh_bao_thap[1] : "");
  setVal("#t2-sp-cbc-min", info.canh_bao_cao ? info.canh_bao_cao[0] : "");
  setVal("#t2-sp-cbc-max", info.canh_bao_cao ? info.canh_bao_cao[1] : "");
  setVal("#t2-sp-nh-duoi", info.nguy_hiem_duoi);
  setVal("#t2-sp-nh-tren", info.nguy_hiem_tren);
  setVal("#t2-sp-source", info.nguon_tham_khao);
}

async function saveSpeciesConfig() {
  const numOrNull = (id) => {
    const raw = $(id)?.value?.trim();
    return raw === "" || raw === undefined ? null : Number(raw);
  };
  const payload = {
    ma_loai: $("#t2-sp-code").value.trim(),
    ten_hien_thi: $("#t2-sp-name").value.trim(),
    an_toan_min: numOrNull("#t2-sp-at-min"),
    an_toan_max: numOrNull("#t2-sp-at-max"),
    canh_bao_thap_min: numOrNull("#t2-sp-cbt-min"),
    canh_bao_thap_max: numOrNull("#t2-sp-cbt-max"),
    canh_bao_cao_min: numOrNull("#t2-sp-cbc-min"),
    canh_bao_cao_max: numOrNull("#t2-sp-cbc-max"),
    nguy_hiem_duoi: numOrNull("#t2-sp-nh-duoi"),
    nguy_hiem_tren: numOrNull("#t2-sp-nh-tren"),
    nguon_tham_khao: $("#t2-sp-source").value.trim(),
  };
  try {
    const res = await apiPost("/api/config/species", payload);
    if (STATE.bootstrap) {
      STATE.bootstrap.danh_sach_loai = res.danh_sach_loai;
    }
    populateSpeciesDropdowns(res.danh_sach_loai);
    renderSpeciesFullTable(res.danh_sach_loai);
    $("#t2-species-select").value = res.ma_loai;
    $("#t2-edit-preset").value = res.ma_loai;
    await evaluateSpeciesTab2();
    toast("✅ Đã lưu ngưỡng loài vào config.yaml!");
  } catch (err) {
    toast(`Lỗi lưu ngưỡng loài: ${err.message}`);
  }
}

async function saveOpticsConfig() {
  const payload = {
    goc_dinh_A_do: Number($("#t5-a").value),
    khoang_cach_man_D_m: Number($("#t5-d").value),
    kich_thuoc_pixel_mm: Number($("#t5-pxmm").value),
  };
  try {
    const res = await apiPost("/api/config/optics", payload);
    if (STATE.bootstrap) {
      STATE.bootstrap.quang_hoc = res.quang_hoc;
      updateModelBadges(STATE.bootstrap.mo_hinh, res.quang_hoc);
    }
    toast(`✅ Đã lưu A=${res.quang_hoc.A_do}°, D=${res.quang_hoc.D_m}m vào config.yaml!`);
  } catch (err) {
    toast(`Lỗi lưu cấu hình quang học: ${err.message}`);
  }
}

function renderSpeciesFullTable(list) {
  $("#t2-full-table-body").innerHTML = list.map((v) => `
    <tr>
      <td><b>${esc(v.ten_hien_thi)}</b></td>
      <td>${esc(v.an_toan_str)}</td>
      <td>${esc(v.cb_thap_str)}</td>
      <td>${esc(v.cb_cao_str)}</td>
      <td>${esc(v.nguy_hiem_str)}</td>
      <td>${esc(v.nguon_tham_khao || "Chưa có (Cần điền vào config.yaml)")}</td>
    </tr>
  `).join("");
}

/* ==========================================================================
   TAB 3: NHẬT KÍ QUAN TRẮC & XUẤT CSV
   ========================================================================== */
function fillSelectKeepValue(sel, allLabel, values) {
  const cur = sel.value || "ALL";
  sel.innerHTML =
    `<option value="ALL">${esc(allLabel)}</option>` +
    (values || []).map((s) => `<option value="${esc(s)}">${esc(s)}</option>`).join("");
  const stillExists = cur === "ALL" || (values || []).includes(cur);
  sel.value = stillExists ? cur : "ALL";
  return stillExists;
}

function refreshLocationSuggestions(locations) {
  const dl = $("#location-suggestions");
  if (!dl) return;
  dl.innerHTML = (locations || []).map((v) => `<option value="${esc(v)}"></option>`).join("");
}

function logsQueryString() {
  const hoSo = STATE.hoSo || "mac_dinh";
  const loai = $("#t3-filter-species").value || "ALL";
  const nguon = $("#t3-filter-source").value || "ALL";
  const viTri = $("#t3-filter-location").value || "ALL";
  return `?ho_so=${encodeURIComponent(hoSo)}&loai=${encodeURIComponent(loai)}&nguon=${encodeURIComponent(nguon)}&vi_tri=${encodeURIComponent(viTri)}`;
}

function salinityChip(r) {
  return `<b>${fmt(r.do_man_ppt, 2)}</b>`;
}

async function loadLogs(_retry = false) {
  const qs = logsQueryString();
  try {
    const data = await apiGet(`/api/logs${qs}`, "logs");

    // Cập nhật danh sách bộ lọc; nếu giá trị đang lọc không còn tồn tại (vd: vừa xóa dòng cuối) thì tự bỏ lọc
    const ok1 = fillSelectKeepValue($("#t3-filter-species"), "Tất cả đối tượng", data.all_species);
    const ok2 = fillSelectKeepValue($("#t3-filter-source"), "Tất cả nguồn", data.all_sources);
    const ok3 = fillSelectKeepValue($("#t3-filter-location"), "Tất cả ao / vị trí", data.all_locations);
    if (!(ok1 && ok2 && ok3) && !_retry) {
      return loadLogs(true);
    }

    STATE.logLast = data;
    $("#t3-btn-csv").href = `/api/logs/csv${qs}`;
    refreshLocationSuggestions(data.all_locations);

    const sm = data.summary || {};
    $("#t3-kpi-count").textContent = String(sm.tong_so || 0);
    $("#t3-kpi-mean").textContent = fmt(sm.s_tb, 2);
    $("#t3-kpi-max").textContent = fmt(sm.s_max, 2);
    $("#t3-kpi-duc").textContent = fmt(sm.duc_tb, 2);
    $("#hero-log-count").textContent = String(sm.tong_tat_ca ?? data.rows.length);

    // Dòng mô tả bộ lọc đang áp dụng
    const parts = [];
    const loc = $("#t3-filter-location").value;
    const sp = $("#t3-filter-species").value;
    const src = $("#t3-filter-source").value;
    if (loc !== "ALL") parts.push(`ao/vị trí “${loc}”`);
    if (sp !== "ALL") parts.push(`loài “${sp}”`);
    if (src !== "ALL") parts.push(`nguồn “${src}”`);
    $("#t3-filter-hint").textContent = parts.length
      ? `🔎 Đang lọc theo ${parts.join(", ")} — ${sm.tong_so || 0}/${sm.tong_tat_ca ?? 0} bản ghi. Nút Xuất CSV sẽ chỉ xuất các bản ghi đang hiển thị.`
      : `Đang hiển thị toàn bộ ${sm.tong_tat_ca ?? 0} bản ghi.`;
    $("#t3-btn-reset-filter").disabled = parts.length === 0;

    const rows = data.rows || [];
    if (!rows.length) {
      $("#t3-table-body").innerHTML = `<tr class="log-empty-row"><td colspan="12">
        📭 Chưa có bản ghi nào${parts.length ? " phù hợp với bộ lọc" : ""}. Hãy đo mẫu nước ở tab <b>Đo Nước</b> rồi bấm <b>Lưu kết quả</b>.
      </td></tr>`;
    } else {
      $("#t3-table-body").innerHTML = rows.map((r) => `
        <tr data-row-id="${esc(r.id)}">
          <td class="pro-only">${esc(r.id)}</td>
          <td>${esc(r.thoi_gian)}</td>
          <td>${esc(r.vi_tri)}</td>
          <td>${esc(r.loai_nuoi)}</td>
          <td class="pro-only">${fmt(r.delta_y_px, 2)}</td>
          <td>${salinityChip(r)}</td>
          <td class="pro-only">±${fmt(r.bat_dinh_U_ppt, 2)}</td>
          <td>${fmt(r.nhiet_do_C, 1)}</td>
          <td>${fmt(r.do_duc, 2)}</td>
          <td class="pro-only">${esc(r.nguon_du_lieu)}</td>
          <td>${esc(r.ghi_chu)}</td>
          <td style="text-align:center;">
            <button type="button" class="btn-row-delete" data-delete-id="${esc(r.id)}"
              data-desc="${esc(`${r.thoi_gian} • ${r.vi_tri} • ${fmt(r.do_man_ppt, 2)} ‰`)}"
              title="Xóa bản ghi này">🗑️</button>
          </td>
        </tr>
      `).join("");
    }

    drawLogsChart(data);
  } catch (err) {
    if (isAbortError(err)) return;
    toast(`Lỗi tải nhật kí: ${err.message}`);
  }
}

async function deleteLogRow(btn) {
  const id = Number(btn.dataset.deleteId);
  const desc = btn.dataset.desc || `#${id}`;
  if (!Number.isFinite(id)) return;
  if (!window.confirm(`Xóa bản ghi này khỏi Nhật kí?\n\n${desc}\n\nThao tác này không thể hoàn tác.`)) return;
  btn.disabled = true;
  try {
    await apiPost("/api/logs/delete", { id });
    const tr = btn.closest("tr");
    if (tr) tr.style.opacity = "0.35";
    await loadLogs();
    toast(`🗑️ Đã xóa bản ghi: ${desc}`);
  } catch (err) {
    btn.disabled = false;
    toast(`Lỗi xóa bản ghi: ${err.message}`);
  }
}

function drawLogsChart(data) {
  if (!data) return;
  const asc = [...(data.rows || [])].reverse();
  const labels = asc.map((r) => String(r.thoi_gian || "").slice(5, 16));
  drawXYChart($("#canvas-log-series"), $("#tip-log-series"), {
    title: "Chuỗi thời gian quan trắc độ mặn (Kèm dải ±U₉₅%)",
    xLabel: "Thứ tự điểm đo theo thời gian",
    yLabel: "Độ mặn S (‰)",
    xFormatter: (idx) => {
      const i = Math.round(idx);
      return labels[i] ? labels[i] : String(i);
    },
    series: [
      {
        type: "band",
        fill: "rgba(229, 56, 59, 0.17)",
        points: asc.map((r, i) => ({
          x: i,
          yLo: Number(r.do_man_ppt) - Number(r.bat_dinh_U_ppt || 0),
          yHi: Number(r.do_man_ppt) + Number(r.bat_dinh_U_ppt || 0),
        })),
      },
      {
        type: "line-markers",
        color: "#e5383b",
        width: 2.2,
        radius: 3.8,
        label: "Độ mặn S (‰)",
        points: asc.map((r, i) => ({ x: i, y: Number(r.do_man_ppt) })),
      },
    ],
    emptyText: "Chưa có dữ liệu nhật kí. Hãy đo ở Tab 1 hoặc bấm 'Nạp 10 mẫu MP'.",
  });
}

/* ==========================================================================
   TAB 4: HIỆU CHUẨN & BÙ NHIỆT ĐỘ
   ========================================================================== */
async function runCalibrate(activate = false) {
  const degVal = $("#t4-degree").value;
  const bacEp = degVal === "auto" ? null : Number(degVal);
  try {
    const data = await apiPost("/api/calibrate", {
      mode: STATE.calibMode,
      csv_text: STATE.calibCsvText,
      file_name: STATE.calibFileName,
      bac_ep: bacEp,
      activate,
    });
    STATE.calibLast = data;
    const mh = data.mo_hinh;
    $("#t4-kpi-r2").textContent = fmt(mh.R2, 5);
    $("#t4-kpi-pts").textContent = `Khớp trên ${mh.so_diem} điểm`;
    $("#t4-kpi-deg").textContent = `Bậc ${data.bac_chon}`;
    $("#t4-kpi-reason").textContent = data.ly_do_chon;
    $("#t4-kpi-rmsetest").textContent = data.RMSE_test_ppt !== null ? fmt(data.RMSE_test_ppt, 3) : "N/A";
    $("#t4-kpi-rmsepx").textContent = `RMSE ảnh: ${data.RMSE_test_px !== null ? fmt(data.RMSE_test_px, 3) : "N/A"} px`;
    $("#t4-kpi-sres").textContent = fmt(mh.s_res_px, 3);
    $("#t4-kpi-dof").textContent = `Bậc tự do ν = ${mh.bac_tu_do}`;

    $("#t4-equation-box").textContent = mh.phuong_trinh;
    if (mh.la_mo_phong) {
      $("#t4-model-warning").innerHTML = `<div class="banner-25d warn"><div class="banner-icon">⚠️</div><div>Đường chuẩn này dựng từ <b>DỮ LIỆU MÔ PHỎNG</b>, không phải số đo thực nghiệm.</div></div>`;
    } else if (mh.da_xac_nhan_thuc_te) {
      $("#t4-model-warning").innerHTML = `<div class="banner-25d ok"><div class="banner-icon">✅</div><div><b>ĐÃ HIỆU CHUẨN (dữ liệu đo thật)!</b></div></div>`;
    } else {
      $("#t4-model-warning").innerHTML = `<div class="banner-25d warn"><div class="banner-icon">⚠️</div><div><b>CHƯA XÁC NHẬN NGUỒN DỮ LIỆU:</b> File CSV thiếu cột <code>nguon_du_lieu=THUC_TE</code> nên KHÔNG được gắn nhãn đo thật.</div></div>`;
    }

    $("#t4-level-table-body").innerHTML = (data.sai_so_theo_muc || []).map((r) => `
      <tr>
        <td><b>${fmt(r.do_man_chuan_ppt, 1)}</b></td>
        <td>${r.so_diem}</td>
        <td>${fmt(r.delta_y_tb_px, 2)}</td>
        <td>${fmt(r.do_lech_chuan_px, 3)}</td>
        <td>${fmt(r.phan_du_tb_px, 3)}</td>
        <td>${fmt(r.S_uoc_luong_tb_ppt, 2)}</td>
        <td>${fmt(r.sai_so_S_tb_ppt, 3)}</td>
        <td>${fmt(r.sai_so_S_max_ppt, 3)}</td>
      </tr>
    `).join("");

    drawCalibrationCharts(data);

    if (activate) {
      if (STATE.bootstrap) {
        STATE.bootstrap.mo_hinh = mh;
        updateModelBadges(mh, STATE.bootstrap.quang_hoc);
      }
      toast(`✅ Đã lưu và kích hoạt đường chuẩn (${data.saved_file})!`);
      if (STATE.lastMeasure) runMeasure();
    }
  } catch (err) {
    toast(`Lỗi hiệu chuẩn: ${err.message}`);
  }
}

function drawCalibrationCharts(data) {
  if (!data || !data.plot_data) return;
  const pd = data.plot_data;
  const lineColors = ["#14b8a6", "#1b4965", "#f59e0b", "#8b5cf6", "#059669", "#64748b"];
  const curveSeries = (pd.curves || []).map((c, idx) => ({
    type: "line",
    color: lineColors[idx % lineColors.length],
    width: 1.9,
    label: `T=${c.T_C}°C`,
    points: c.S.map((sv, i) => ({ x: sv, y: c.delta_y[i] })),
  }));
  curveSeries.push({
    type: "scatter",
    color: "#2563eb",
    radius: 3.2,
    label: "Train",
    points: (pd.train || []).map((p) => ({ x: p.S, y: p.delta_y })),
  });
  curveSeries.push({
    type: "scatter",
    color: "#e5383b",
    marker: "x",
    radius: 4.5,
    label: "Test",
    points: (pd.test || []).map((p) => ({ x: p.S, y: p.delta_y })),
  });
  drawXYChart($("#canvas-calib-curve"), $("#tip-calib-curve"), {
    title: `Đường chuẩn bậc ${data.bac_chon} (R² = ${fmt(data.mo_hinh.R2, 5)})`,
    xLabel: "Độ mặn chuẩn S (‰)",
    yLabel: "Δy (pixel)",
    series: curveSeries,
  });

  const sRes = Number(data.s_res_train_px || data.mo_hinh.s_res_px || 0);
  drawXYChart($("#canvas-calib-res"), $("#tip-calib-res"), {
    title: `Phân bố phần dư (Nét đứt ±2·s_res = ±${fmt(2 * sRes, 3)} px)`,
    xLabel: "Độ mặn chuẩn S (‰)",
    yLabel: "Phần dư (pixel)",
    series: [
      { type: "scatter", color: "#1b4965", radius: 3.2, label: "Train", points: (pd.train || []).map((p) => ({ x: p.S, y: p.res })) },
      { type: "scatter", color: "#e5383b", marker: "x", radius: 4.5, label: "Test", points: (pd.test || []).map((p) => ({ x: p.S, y: p.res })) },
    ],
    hlines: [
      { y: 0, color: "#0f172a", width: 1.1 },
      { y: 2 * sRes, color: "#64748b", dash: [4, 4], width: 1.1 },
      { y: -2 * sRes, color: "#64748b", dash: [4, 4], width: 1.1 },
    ],
  });
}

/* ==========================================================================
   TAB 5: MÔ PHỎNG QUANG HỌC SNELL & NGÂN SÁCH SAI SỐ RSS
   ========================================================================== */
function renderOpticsSvg(d) {
  const yTc = 65.0;
  const dySvg = Math.max(0, Math.min(68, Number(d.delta_y_px || 0) * 0.42));
  const yMau = Math.min(168, yTc + dySvg);

  const exitRays = d.tir
    ? `<line x1="215" y1="95" x2="170" y2="155" stroke="#ef4444" stroke-width="2.6" stroke-dasharray="5,4"/>
       <text x="235" y="100" fill="#fca5a5" font-size="12" font-weight="700">🚨 PHẢN XẠ TOÀN PHẦN (n·sinA ≥ 1)</text>`
    : `<line x1="218" y1="82" x2="430" y2="${yTc.toFixed(1)}" stroke="#34d399" stroke-width="2.2" stroke-dasharray="4,3" opacity="0.88"/>
       <line x1="218" y1="108" x2="430" y2="${yMau.toFixed(1)}" stroke="#ff4d4f" stroke-width="2.5" opacity="0.92"/>`;

  $("#t5-svg-container").innerHTML = `
    <div style="background:linear-gradient(135deg,#071326 0%,#0b1d3a 100%); border-radius:16px; padding:12px 14px; border:1.5px solid rgba(148,163,184,0.28); box-shadow:0 5px 0 #040b16;">
      <svg viewBox="0 0 680 186" width="100%" height="186" xmlns="http://www.w3.org/2000/svg" style="display:block;">
        <defs>
          <filter id="laserGlow2" x="-20%" y="-50%" width="140%" height="200%">
            <feGaussianBlur stdDeviation="3" result="blur"/>
            <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
          </filter>
          <linearGradient id="prismGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="rgba(56,189,248,0.28)"/>
            <stop offset="100%" stop-color="rgba(14,165,233,0.08)"/>
          </linearGradient>
        </defs>
        <polygon points="14,76 24,68 82,68 72,76" fill="#475569" stroke="#94a3b8" stroke-width="1"/>
        <polygon points="72,76 82,68 82,104 72,112" fill="#0f172a" stroke="#64748b" stroke-width="1"/>
        <rect x="14" y="76" width="58" height="36" rx="6" fill="#1e293b" stroke="#94a3b8" stroke-width="1.5"/>
        <text x="43" y="92" fill="#f8fafc" font-size="9.5" font-weight="700" text-anchor="middle">LASER</text>
        <text x="43" y="104" fill="#fca5a5" font-size="8.5" text-anchor="middle">650 nm</text>

        <line x1="72" y1="86" x2="155" y2="86" stroke="#ff4d4f" stroke-width="2.4" filter="url(#laserGlow2)"/>
        <line x1="72" y1="102" x2="155" y2="102" stroke="#ff4d4f" stroke-width="2.4" filter="url(#laserGlow2)"/>

        <polygon points="155,36 167,28 260,86 248,94" fill="rgba(125,211,252,0.18)" stroke="#7dd3fc" stroke-width="1.2"/>
        <polygon points="155,152 248,94 260,86 167,144" fill="rgba(14,165,233,0.12)" stroke="#38bdf8" stroke-width="1"/>
        <polygon points="155,36 155,152 248,94" fill="url(#prismGrad)" stroke="#38bdf8" stroke-width="2"/>
        <line x1="155" y1="94" x2="248" y2="94" stroke="#cbd5e1" stroke-width="1.5" stroke-dasharray="3,3"/>
        <text x="196" y="21" fill="#7dd3fc" font-size="10.5" font-weight="700" text-anchor="middle">Lăng kính 2 ngăn (A = ${d.A_do.toFixed(1)}°)</text>
        <text x="178" y="75" fill="#a7f3d0" font-size="8.5" font-weight="600">Ngăn TC (0‰)</text>
        <text x="178" y="118" fill="#fecaca" font-size="8.5" font-weight="600">Ngăn Mẫu (${d.S_ppt.toFixed(1)}‰)</text>

        ${exitRays}

        <rect x="446" y="19" width="222" height="158" rx="12" fill="#020617" stroke="#334155" stroke-width="1"/>
        <rect x="442" y="14" width="222" height="158" rx="12" fill="#071122" stroke="#64748b" stroke-width="1.8"/>
        <text x="553" y="31" fill="#cbd5e1" font-size="10" font-weight="700" text-anchor="middle">MÀN HỨNG / ẢNH CAMERA</text>
        <line x1="553" y1="38" x2="553" y2="164" stroke="#334155" stroke-width="1" stroke-dasharray="3,3"/>

        <line x1="458" y1="${yTc.toFixed(1)}" x2="544" y2="${yTc.toFixed(1)}" stroke="#ff4d4f" stroke-width="3.2" stroke-linecap="round" filter="url(#laserGlow2)"/>
        <line x1="458" y1="${yTc.toFixed(1)}" x2="544" y2="${yTc.toFixed(1)}" stroke="#34d399" stroke-width="1.2" stroke-dasharray="2,2"/>
        <text x="460" y="${(yTc - 8).toFixed(1)}" fill="#6ee7b7" font-size="9.5" font-weight="700">Vạch TC (0‰)</text>

        <line x1="562" y1="${yMau.toFixed(1)}" x2="648" y2="${yMau.toFixed(1)}" stroke="#ff4d4f" stroke-width="3.4" stroke-linecap="round" filter="url(#laserGlow2)"/>
        <text x="562" y="${Math.min(164, yMau + 15).toFixed(1)}" fill="#fca5a5" font-size="9.5" font-weight="700">Vạch Mẫu (${d.S_ppt.toFixed(1)}‰)</text>

        <line x1="553" y1="${yTc.toFixed(1)}" x2="553" y2="${yMau.toFixed(1)}" stroke="#fde047" stroke-width="2.2"/>
        <circle cx="553" cy="${yTc.toFixed(1)}" r="3" fill="#34d399"/>
        <circle cx="553" cy="${yMau.toFixed(1)}" r="3" fill="#ff4d4f"/>
        <rect x="506" y="${((yTc + yMau) / 2 - 9).toFixed(1)}" width="94" height="18" rx="5" fill="rgba(15,23,42,0.9)" stroke="#fde047" stroke-width="1"/>
        <text x="553" y="${((yTc + yMau) / 2 + 3.5).toFixed(1)}" fill="#fde047" font-size="9.5" font-weight="800" text-anchor="middle">Δy = ${d.delta_y_px.toFixed(1)} px</text>
      </svg>
    </div>
  `;
}

async function runOpticsSim() {
  try {
    const data = await apiPost("/api/optics-sim", {
      A_deg: Number($("#t5-a").value),
      D_m: Number($("#t5-d").value),
      pixel_mm: Number($("#t5-pxmm").value || 0.05),
      S_ppt: Number($("#t5-s").value),
      T_C: Number($("#t5-t").value),
      sai_so_tim_tam_px: Number($("#t5-err-tam").value || 0.05),
      lech_nhiet_do_C: Number($("#t5-err-t").value || 0.5),
      sai_so_goc_A_do: Number($("#t5-err-a").value || 0.05),
      troi_laser_px: Number($("#t5-err-troi").value || 5.0),
      he_so_triet_chung: Number($("#t5-err-triet").value || 0.01),
    }, "optics");
    STATE.opticsLast = data;
    renderOpticsSvg(data);

    if (data.tir) {
      $("#t5-tir-alert").innerHTML = `<div class="banner-25d danger"><div class="banner-icon">🚨</div><div><b>PHẢN XẠ TOÀN PHẦN (TIR):</b> n·sin(A) = ${fmt(data.n_sin_A, 4)} ≥ 1. Tia laser bị phản xạ ngược bên trong, hãy giảm góc đỉnh A!</div></div>`;
      $("#t5-kpi-theta").textContent = "TIR";
      $("#t5-kpi-delta").textContent = "TIR";
      $("#t5-kpi-sens").textContent = "N/A";
    } else {
      $("#t5-tir-alert").innerHTML = "";
      $("#t5-kpi-theta").textContent = fmt(data.theta_ra, 2);
      $("#t5-kpi-n").textContent = `n_mẫu = ${fmt(data.n_mau, 5)}`;
      $("#t5-kpi-delta").textContent = fmt(data.delta_goc, 2);
      $("#t5-kpi-dy").textContent = `Δy = ${fmt(data.delta_y_px, 1)} px`;
      $("#t5-kpi-sens").textContent = fmt(data.sens_px, 2);
      $("#t5-kpi-sens-sub").textContent = `Tại A=${data.A_do}°, D=${data.D_m}m`;
    }

    if (data.ngan_sach) {
      const ns = data.ngan_sach;
      $("#t5-rss-body").innerHTML = `
        <tr><td>1. Thuật toán định vị tâm vạch dưới pixel (px)</td><td><b>${fmt(ns.tim_tam, 4)}</b></td></tr>
        <tr><td>2. Chênh lệch nhiệt độ giữa 2 ngăn (°C)</td><td><b>${fmt(ns.nhiet_do, 4)}</b></td></tr>
        <tr><td>3. Sai số gia công góc đỉnh A (độ)</td><td><b>${fmt(ns.goc_A, 4)}</b></td></tr>
        <tr><td>4. Trôi laser &amp; rung camera còn sót sau vi sai</td><td><b>${fmt(ns.troi_laser, 4)}</b></td></tr>
        <tr style="background:#eff6ff;"><td><b>∑ TỔNG HỢP TOÀN PHƯƠNG (RSS 1σ)</b></td><td><b>${fmt(ns.tong_RSS, 4)}</b></td></tr>
      `;
      $("#t5-rss-banner").className = "banner-25d ok";
      $("#t5-rss-banner").innerHTML = `<div class="banner-icon">🎯</div><div>Tổng bất định chuẩn thiết kế (1σ): <b>± ${fmt(ns.tong_RSS, 3)} ‰</b> — Mở rộng U₉₅% ≈ <b>± ${fmt(2 * ns.tong_RSS, 3)} ‰</b></div>`;
    } else {
      $("#t5-rss-body").innerHTML = "";
      $("#t5-rss-banner").className = "banner-25d danger";
      $("#t5-rss-banner").innerHTML = `<div class="banner-icon">🚨</div><div>Không tính được RSS do góc A vượt ngưỡng phản xạ toàn phần.</div>`;
    }

    drawOpticsCharts(data);
  } catch (err) {
    if (isAbortError(err)) return;
    toast(`Lỗi mô phỏng quang học: ${err.message}`);
  }
}

function drawOpticsCharts(data) {
  if (!data || !data.curves) return;
  const cv = data.curves;
  const sensPts = cv.angles
    .map((a, i) => ({ x: a, y: cv.sensitivities[i] }))
    .filter((p) => p.y !== null);

  drawXYChart($("#canvas-opt-sens"), $("#tip-opt-sens"), {
    title: "Độ nhạy tăng phi tuyến khi tiến gần giới hạn TIR",
    xLabel: "Góc đỉnh lăng kính A (độ)",
    yLabel: "Độ nhạy (px/‰)",
    series: [{ type: "line", color: "#e5383b", width: 2.3, label: "d(Δy)/dS (px/‰)", points: sensPts }],
    vlines: data.A_do <= 47 ? [{ x: data.A_do, color: "#1b4965", dash: [5, 4], width: 1.8 }] : [],
  });

  if (cv.response_tir) {
    drawXYChart($("#canvas-opt-resp"), $("#tip-opt-resp"), { series: [], emptyText: "Góc A vượt ngưỡng Phản xạ toàn phần (TIR)" });
  } else {
    drawXYChart($("#canvas-opt-resp"), $("#tip-opt-resp"), {
      title: `Đường đáp ứng Δy(S) tại A=${data.A_do}°, D=${data.D_m}m`,
      xLabel: "Độ mặn S (‰)",
      yLabel: "Δy lí thuyết (px)",
      series: [
        { type: "line", color: "#14b8a6", width: 2.2, label: "T = 20 °C", points: cv.s_grid.map((s, i) => ({ x: s, y: cv.dy_20[i] })) },
        { type: "line", color: "#f59e0b", width: 2.2, dash: [5, 4], label: "T = 30 °C", points: cv.s_grid.map((s, i) => ({ x: s, y: cv.dy_30[i] })) },
      ],
    });
  }
}

/* ==========================================================================
   TAB 6: ĐỐI CHỨNG KHÚC XẠ KẾ (BLAND–ALTMAN)
   ========================================================================== */
async function runBlandAltman(mode = "custom", csvText = null) {
  try {
    const payload = mode === "sample"
      ? { mode: "sample" }
      : mode === "csv"
        ? { mode: "csv", csv_text: csvText }
        : { mode: "custom", pairs: STATE.baPairs };

    const data = await apiPost("/api/bland-altman", payload);
    STATE.baLast = data;
    STATE.baPairs = (data.pairs || []).map((p) => ({ S_thiet_bi: p.S_thiet_bi, S_khuc_xa_ke: p.S_khuc_xa_ke }));
    renderBaPairsTable();

    $("#t6-kpi-bias").textContent = `${data.mean_diff >= 0 ? "+" : ""}${fmt(data.mean_diff, 3)}`;
    $("#t6-kpi-sd").textContent = fmt(data.std_diff, 3);
    $("#t6-kpi-n").textContent = `Trên ${data.n_pair} cặp phép đo`;
    $("#t6-kpi-loa").textContent = `[${data.loa_lower >= 0 ? "+" : ""}${fmt(data.loa_lower, 2)}, ${data.loa_upper >= 0 ? "+" : ""}${fmt(data.loa_upper, 2)}]`;
    $("#t6-kpi-r").textContent = fmt(data.r_corr, 5);
    $("#t6-kpi-r2").textContent = `R² = ${fmt(data.r2, 5)}`;

    $("#t6-conclusion-box").innerHTML =
      `<div class="banner-icon">🎯</div><div><b>Kết luận thống kê phục vụ thuyết minh KHKT:</b> Khoảng 95% sai khác giữa thiết bị của dự án và khúc xạ kế nằm trong dải <b>[${fmt(data.loa_lower, 2)} ‰, ${fmt(data.loa_upper, 2)} ‰]</b> với độ lệch trung bình Bias = <b>${data.mean_diff >= 0 ? "+" : ""}${fmt(data.mean_diff, 3)} ‰</b> (r = ${fmt(data.r_corr, 4)}).</div>`;

    drawBaCharts(data);
  } catch (err) {
    toast(`Lỗi Bland–Altman: ${err.message}`);
  }
}

function renderBaPairsTable() {
  $("#t6-pairs-body").innerHTML = STATE.baPairs.map((p, idx) => `
    <tr>
      <td>${idx + 1}</td>
      <td><input type="number" step="0.01" class="cell-num ba-cell" data-idx="${idx}" data-field="S_thiet_bi" value="${p.S_thiet_bi}" /></td>
      <td><input type="number" step="0.01" class="cell-num ba-cell" data-idx="${idx}" data-field="S_khuc_xa_ke" value="${p.S_khuc_xa_ke}" /></td>
      <td>${fmt(Number(p.S_thiet_bi) - Number(p.S_khuc_xa_ke), 2)}</td>
    </tr>
  `).join("");

  $$(".ba-cell").forEach((inp) => {
    inp.addEventListener("change", () => {
      const idx = Number(inp.dataset.idx);
      const field = inp.dataset.field;
      STATE.baPairs[idx][field] = Number(inp.value);
      debounce("ba_edit", () => runBlandAltman("custom"), 120);
    });
  });
}

function drawBaCharts(data) {
  if (!data || !data.pairs) return;
  const pts = data.pairs;
  const allVals = pts.flatMap((p) => [p.S_thiet_bi, p.S_khuc_xa_ke]);
  const lo = Math.min(...allVals) - 1;
  const hi = Math.max(...allVals) + 1;

  drawXYChart($("#canvas-ba-corr"), $("#tip-ba-corr"), {
    title: `Tương quan tuyến tính 2 phương pháp (R² = ${fmt(data.r2, 4)})`,
    xLabel: "S Khúc xạ kế đối chứng (‰)",
    yLabel: "S Thiết bị đo vi sai (‰)",
    series: [
      { type: "line", color: "#e5383b", dash: [5, 4], width: 1.8, label: "y = x lí tưởng", points: [{ x: lo, y: lo }, { x: hi, y: hi }] },
      { type: "scatter", color: "#1b4965", radius: 4, label: "Cặp đo", points: pts.map((p) => ({ x: p.S_khuc_xa_ke, y: p.S_thiet_bi })) },
    ],
  });

  drawXYChart($("#canvas-ba-diff"), $("#tip-ba-diff"), {
    title: "Đồ thị Bland–Altman (Giới hạn đồng thuận 95%)",
    xLabel: "Trung bình 2 máy (‰)",
    yLabel: "Hiệu (S_máy − S_kxk) (‰)",
    series: [
      { type: "scatter", color: "#e5383b", radius: 4, label: "Sai khác", points: pts.map((p) => ({ x: p.mean, y: p.diff })) },
    ],
    hlines: [
      { y: data.mean_diff, color: "#1b4965", width: 2 },
      { y: data.loa_upper, color: "#14b8a6", dash: [5, 4], width: 1.5 },
      { y: data.loa_lower, color: "#14b8a6", dash: [5, 4], width: 1.5 },
      { y: 0, color: "#94a3b8", dash: [2, 3], width: 1 },
    ],
  });
}

/* ==========================================================================
   Điều Khiển Chuyển Tab, Camera & Sự Kiện Giao Diện
   ========================================================================== */
function switchTab(tabId) {
  $$(".tab-btn-25d").forEach((b) => b.classList.toggle("active", b.dataset.tab === tabId));
  $$(".tab-pane").forEach((p) => p.classList.toggle("active", p.id === tabId));

  // Vẽ lại đồ thị Canvas khi tab được hiển thị (lúc này kích thước clientWidth > 0)
  requestAnimationFrame(() => {
    if (tabId === "tab-1" && STATE.lastMeasure) drawTab1Charts(STATE.lastMeasure);
    if (tabId === "tab-2") evaluateSpeciesTab2();
    if (tabId === "tab-3") loadLogs();
    if (tabId === "tab-4") {
      if (STATE.calibLast) drawCalibrationCharts(STATE.calibLast);
      else runCalibrate(false);
    }
    if (tabId === "tab-5") {
      if (STATE.opticsLast) drawOpticsCharts(STATE.opticsLast);
      else runOpticsSim();
    }
    if (tabId === "tab-6") {
      if (STATE.baLast) drawBaCharts(STATE.baLast);
      else runBlandAltman("sample");
    }
  });
}

function cameraSupported() {
  return Boolean(window.isSecureContext && navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
}

function setCameraUi(isOn) {
  $("#btn-cam-start").disabled = isOn || !cameraSupported();
  $("#btn-cam-snap").disabled = !isOn;
  $("#btn-cam-stop").disabled = !isOn;
  $("#camera-live-dot").style.display = isOn ? "block" : "none";
  $("#camera-placeholder").style.display = isOn ? "none" : "flex";
}

function stopCamera(showMsg = false) {
  if (STATE.cameraStream) {
    STATE.cameraStream.getTracks().forEach((t) => t.stop());
    STATE.cameraStream = null;
  }
  const video = $("#camera-video");
  if (video) video.srcObject = null;
  setCameraUi(false);
  if (showMsg) {
    $("#cam-status").textContent = "Camera đã tắt. Nhấn Bật Camera khi cần đo tiếp.";
  }
}

async function startCamera() {
  if (!cameraSupported()) {
    $("#cam-fallback").style.display = "flex";
    return;
  }
  $("#btn-cam-start").disabled = true;
  $("#cam-status").textContent = "Đang xin quyền truy cập camera...";
  try {
    STATE.cameraStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false,
    });
    // Người dùng có thể đã chuyển chế độ trong lúc chờ cấp quyền
    if (STATE.imgMode !== "camera") {
      stopCamera(false);
      return;
    }
    $("#camera-video").srcObject = STATE.cameraStream;
    setCameraUi(true);
    $("#cam-status").innerHTML = "✅ Camera đã bật — hướng vào màn hứng 2 vạch laser rồi nhấn <b>Chụp &amp; Đo</b>.";
  } catch (err) {
    STATE.cameraStream = null;
    setCameraUi(false);
    const name = err && err.name;
    let msg = `Không mở được Camera: ${err.message || err}`;
    if (name === "NotAllowedError" || name === "SecurityError") {
      msg = "Bạn đã từ chối quyền dùng camera. Hãy bấm biểu tượng 🔒 trên thanh địa chỉ → cho phép Camera rồi thử lại.";
    } else if (name === "NotFoundError" || name === "OverconstrainedError") {
      msg = "Không tìm thấy camera trên thiết bị này. Bạn có thể dùng mục 🖼️ Chọn ảnh thay thế.";
    } else if (name === "NotReadableError") {
      msg = "Camera đang được ứng dụng khác sử dụng. Hãy đóng ứng dụng đó rồi thử lại.";
    }
    $("#cam-status").textContent = msg;
  }
}

function snapCameraAndMeasure() {
  const video = $("#camera-video");
  if (!STATE.cameraStream || !video.videoWidth) {
    toast("Hãy bật Camera và chờ hình hiện lên trước khi chụp!");
    return;
  }
  const c = document.createElement("canvas");
  c.width = video.videoWidth;
  c.height = video.videoHeight;
  c.getContext("2d").drawImage(video, 0, 0);
  // JPEG chất lượng cao (0.94): giữ nguyên độ phân giải pixel nhưng giảm ~10-15x dung lượng tải lên trên di động
  STATE.cameraImageB64 = c.toDataURL("image/jpeg", 0.94);
  $("#cam-status").textContent = `📸 Đã chụp ảnh ${c.width}×${c.height} px — đang phân tích...`;
  runMeasure();
}

const MAX_UPLOAD_MB = 15;

function resetUploadPreview() {
  STATE.uploadImageB64 = null;
  $("#upload-img-name").textContent = "Chưa chọn ảnh";
  $("#upload-preview-box").style.display = "none";
  $("#upload-preview-img").removeAttribute("src");
}

function handleLaserFile(file, sourceLabel) {
  if (!file) return;
  if (!file.type || !file.type.startsWith("image/")) {
    toast("⚠️ File đã chọn không phải là ảnh. Hãy chọn ảnh JPG hoặc PNG.");
    return;
  }
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
    toast(`⚠️ Ảnh quá lớn (${(file.size / 1048576).toFixed(1)} MB). Giới hạn ${MAX_UPLOAD_MB} MB.`);
    return;
  }
  if (STATE.imgMode !== "upload") setImgMode("upload");
  const reader = new FileReader();
  reader.onload = () => {
    STATE.uploadImageB64 = reader.result;
    $("#upload-img-name").textContent = `${sourceLabel}: ${file.name} (${(file.size / 1024).toFixed(0)} KB)`;
    $("#upload-preview-img").src = reader.result;
    $("#upload-preview-box").style.display = "block";
    runMeasure();
  };
  reader.onerror = () => toast("Không đọc được file ảnh, vui lòng thử lại.");
  reader.readAsDataURL(file);
}

function setImgMode(mode) {
  STATE.imgMode = mode;
  $$(".seg-btn").forEach((b) => b.classList.toggle("active", b.dataset.imgMode === mode));
  $("#t1-mode-sim").style.display = mode === "sim" ? "block" : "none";
  $("#t1-mode-upload").style.display = mode === "upload" ? "block" : "none";
  $("#t1-mode-camera").style.display = mode === "camera" ? "block" : "none";
  if (mode !== "camera") {
    stopCamera(false);
  } else {
    const supported = cameraSupported();
    $("#cam-fallback").style.display = supported ? "none" : "flex";
    setCameraUi(Boolean(STATE.cameraStream));
  }
}

function bindEvents() {
  // Chuyển Tab
  $$(".tab-btn-25d").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });

  // Hồ sơ hộ nuôi / xưởng
  const switchProfile = async (newProfile) => {
    STATE.hoSo = (newProfile || "mac_dinh").trim() || "mac_dinh";
    try {
      localStorage.setItem("salinity_ho_so", STATE.hoSo);
    } catch (_) {}
    await loadBootstrap();
    await loadLogs();
    if (STATE.lastMeasure) runMeasure({ silent: true });
    const label = STATE.hoSo === "mac_dinh" ? "Mặc định (chung)" : STATE.hoSo;
    toast(`🏠 Đang dùng hồ sơ: ${label}`);
  };
  $("#sb-profile-select").addEventListener("change", (ev) => switchProfile(ev.target.value));
  $("#btn-add-profile").addEventListener("click", () => {
    const raw = window.prompt("Nhập tên Hộ nuôi / Ao lớn / Phân xưởng mới (vd: Hộ Ông Tư, Xưởng CB1):");
    if (raw === null) return;
    const clean = raw.trim();
    if (!clean) {
      toast("Tên hồ sơ không được để trống.");
      return;
    }
    STATE.hoSo = clean;
    populateProfileSelect([...(STATE.bootstrap?.all_profiles || ["mac_dinh"]), clean]);
    switchProfile(clean);
  });

  $("#offline-queue-pill").addEventListener("click", () => flushOfflineQueue(false));
  window.addEventListener("online", () => {
    updateNetworkPill();
    flushOfflineQueue(true);
  });
  window.addEventListener("offline", updateNetworkPill);

  // Chuyển chế độ Dễ dùng (nông dân/phổ thông) <-> Kỹ thuật (đầy đủ)
  const setUiMode = (mode, persist = true) => {
    const isSimple = mode !== "pro";
    document.body.classList.toggle("ui-simple", isSimple);
    $$(".ui-mode-btn").forEach((b) => {
      b.classList.toggle("active", (b.dataset.uiMode === "simple") === isSimple);
    });
    if (persist) {
      try {
        localStorage.setItem("salinity_ui_mode", isSimple ? "simple" : "pro");
      } catch (_) {}
    }
    if (isSimple) {
      const activeBtn = $(".tab-btn-25d.active");
      if (activeBtn && activeBtn.classList.contains("pro-only")) {
        switchTab("tab-1");
      }
      if ($("#toggle-coach").checked) {
        $("#toggle-coach").checked = false;
        updateCoachBar();
      }
    } else if (STATE.lastMeasure) {
      requestAnimationFrame(() => drawTab1Charts(STATE.lastMeasure));
    }
  };
  window._setUiMode = setUiMode;

  $$(".ui-mode-btn").forEach((b) =>
    b.addEventListener("click", () => setUiMode(b.dataset.uiMode))
  );
  let savedMode = "simple";
  try {
    savedMode = localStorage.getItem("salinity_ui_mode") || "simple";
  } catch (_) {}
  setUiMode(savedMode);

  const btnGoLogs = $("#btn-go-logs");
  if (btnGoLogs) {
    btnGoLogs.addEventListener("click", () => switchTab("tab-3"));
  }

  // Modal Hướng dẫn & Coach bar
  $("#btn-open-guide").addEventListener("click", () => $("#guide-modal-backdrop").classList.add("open"));
  $("#btn-close-guide").addEventListener("click", () => $("#guide-modal-backdrop").classList.remove("open"));
  $("#guide-modal-backdrop").addEventListener("click", (ev) => {
    if (ev.target.id === "guide-modal-backdrop") $("#guide-modal-backdrop").classList.remove("open");
  });
  $("#toggle-coach").addEventListener("change", updateCoachBar);
  const advDrawer = $("#t1-advanced-details");
  if (advDrawer) {
    advDrawer.addEventListener("toggle", () => {
      if (advDrawer.open && STATE.lastMeasure) {
        requestAnimationFrame(() => drawTab1Charts(STATE.lastMeasure));
      }
    });
  }

  const runQuickDemo = () => {
    $("#guide-modal-backdrop").classList.remove("open");
    setImgMode("sim");
    $("#sim-s").value = "16.5"; $("#val-sim-s").textContent = "16.5 ‰";
    $("#sim-t").value = "26.0"; $("#val-sim-t").textContent = "26.0 °C";
    $("#meas-temp").value = "26.0";
    $("#sim-duc").value = "0.15"; $("#val-sim-duc").textContent = "0.15";
    $("#sim-drift").value = "4"; $("#val-sim-drift").textContent = "+4.0 px";
    switchTab("tab-1");
    runMeasure();
    toast("⚡ Đã chạy mẫu thử 16.5 ‰!");
  };
  $("#btn-coach-quickstart").addEventListener("click", runQuickDemo);
  $("#btn-modal-quickstart").addEventListener("click", runQuickDemo);

  // Tab 1: Nguồn ảnh
  $$(".seg-btn").forEach((b) => b.addEventListener("click", () => setImgMode(b.dataset.imgMode)));

  $("#sim-s").addEventListener("input", () => {
    $("#val-sim-s").textContent = `${Number($("#sim-s").value).toFixed(1)} ‰`;
    if ($("#meas-live").checked) debounce("t1", runMeasure, 80);
  });
  $("#sim-t").addEventListener("input", () => {
    const v = Number($("#sim-t").value).toFixed(1);
    $("#val-sim-t").textContent = `${v} °C`;
    $("#meas-temp").value = v;
    if ($("#meas-live").checked) debounce("t1", runMeasure, 80);
  });
  $("#sim-duc").addEventListener("input", () => {
    $("#val-sim-duc").textContent = Number($("#sim-duc").value).toFixed(2);
    if ($("#meas-live").checked) debounce("t1", runMeasure, 80);
  });
  $("#sim-drift").addEventListener("input", () => {
    const d = Number($("#sim-drift").value);
    $("#val-sim-drift").textContent = `${d >= 0 ? "+" : ""}${d.toFixed(1)} px`;
    if ($("#meas-live").checked) debounce("t1", runMeasure, 80);
  });
  ["sim-saturate", "sim-layout", "meas-temp", "meas-method", "roi-manual-enable"].forEach((id) => {
    $(`#${id}`).addEventListener("change", () => {
      if ($("#meas-live").checked) runMeasure({ silent: true });
    });
  });
  $("#t1-species-select").addEventListener("change", () => {
    const km = STATE.lastMeasure && STATE.lastMeasure.mo_hinh_man;
    const list = STATE.bootstrap && STATE.bootstrap.danh_sach_loai;
    if (km && Array.isArray(list) && list.length) {
      const maLoai = $("#t1-species-select").value;
      const info = list.find((s) => s.ma_loai === maLoai);
      if (info) {
        const dg = evalOneSpeciesLocal(Number(km.S_ppt), info);
        STATE.lastMeasure.danh_gia_loai = dg;
        const cls = dg.trang_thai === "AN_TOAN" ? "ok" : dg.trang_thai === "CANH_BAO" ? "warn" : dg.trang_thai === "NGUY_HIEM" ? "danger" : "info";
        const vBox = $("#t1-species-verdict");
        vBox.className = `banner-25d ${cls}`;
        vBox.innerHTML = `<div class="banner-icon">🔎</div><div><b>${esc(dg.tieu_de)}</b><br>${esc(dg.loi_khuyen)}</div>`;
        return;
      }
    }
    if ($("#meas-live").checked) runMeasure({ silent: true });
  });

  $("#file-laser-img").addEventListener("change", (ev) => {
    handleLaserFile(ev.target.files?.[0], "Ảnh đã chọn");
    ev.target.value = "";
  });
  $("#file-laser-capture").addEventListener("change", (ev) => {
    handleLaserFile(ev.target.files?.[0], "Ảnh vừa chụp");
    ev.target.value = "";
  });
  $("#btn-upload-clear").addEventListener("click", () => {
    resetUploadPreview();
    toast("Đã bỏ ảnh. Hãy chọn hoặc chụp ảnh khác.");
  });
  $("#btn-upload-remeasure").addEventListener("click", () => runMeasure());

  // Kéo-thả ảnh vào ô chọn ảnh (máy tính)
  $$(".upload-choice").forEach((zone) => {
    zone.addEventListener("dragover", (ev) => {
      ev.preventDefault();
      zone.classList.add("drag-over");
    });
    zone.addEventListener("dragleave", () => zone.classList.remove("drag-over"));
    zone.addEventListener("drop", (ev) => {
      ev.preventDefault();
      zone.classList.remove("drag-over");
      handleLaserFile(ev.dataTransfer?.files?.[0], "Ảnh kéo thả");
    });
  });

  $("#btn-cam-start").addEventListener("click", startCamera);
  $("#btn-cam-snap").addEventListener("click", snapCameraAndMeasure);
  $("#btn-cam-stop").addEventListener("click", () => stopCamera(true));
  window.addEventListener("pagehide", () => stopCamera(false));
  document.addEventListener("visibilitychange", () => {
    if (document.hidden && STATE.cameraStream) {
      stopCamera(false);
      $("#cam-status").textContent = "Camera đã tự tắt khi bạn rời trang để tiết kiệm pin. Nhấn Bật Camera để dùng lại.";
    }
  });
  setCameraUi(false);

  $("#btn-run-measure").addEventListener("click", () => runMeasure());
  $("#btn-save-log").addEventListener("click", saveMeasurementToLog);

  // Tab 2
  $("#t2-eval-btn").addEventListener("click", evaluateSpeciesTab2);
  $("#t2-species-select").addEventListener("change", evaluateSpeciesTab2);
  $("#t2-s-input").addEventListener("input", () => debounce("t2", evaluateSpeciesTab2, 120));
  $("#t2-use-tab1").addEventListener("click", () => {
    if (STATE.lastMeasure?.mo_hinh_man) {
      $("#t2-s-input").value = fmt(STATE.lastMeasure.mo_hinh_man.S_ppt, 2);
      evaluateSpeciesTab2();
    } else {
      toast("Chưa có số đo hợp lệ từ Tab 1!");
    }
  });

  // Tab 2: chỉnh sửa ngưỡng loài
  $("#t2-edit-preset").addEventListener("change", (ev) => fillSpeciesEditForm(ev.target.value));
  $("#t2-btn-save-species").addEventListener("click", saveSpeciesConfig);

  // Tab 3
  $("#t3-filter-species").addEventListener("change", () => loadLogs());
  $("#t3-filter-source").addEventListener("change", () => loadLogs());
  $("#t3-filter-location").addEventListener("change", () => loadLogs());
  $("#t3-btn-reset-filter").addEventListener("click", () => {
    $("#t3-filter-species").value = "ALL";
    $("#t3-filter-source").value = "ALL";
    $("#t3-filter-location").value = "ALL";
    loadLogs();
  });
  $("#t3-table-body").addEventListener("click", (ev) => {
    const btn = ev.target.closest(".btn-row-delete");
    if (btn) deleteLogRow(btn);
  });
  $("#t3-btn-sample").addEventListener("click", async () => {
    await apiPost("/api/logs/sample", {});
    await loadLogs();
    toast("✅ Đã nạp 10 bản ghi mô phỏng vào Nhật kí!");
  });
  $("#t3-btn-clear").addEventListener("click", async () => {
    const total = STATE.logLast?.summary?.tong_tat_ca ?? 0;
    if (!total) {
      toast("Nhật kí đang trống, không có gì để xóa.");
      return;
    }
    if (!window.confirm(`⚠️ Xóa TOÀN BỘ ${total} bản ghi trong Nhật kí (mọi ao, mọi loài)?\n\nThao tác này không thể hoàn tác. Nên bấm "Xuất CSV" để sao lưu trước.`)) return;
    try {
      await apiPost("/api/logs/clear", {});
      await loadLogs();
      toast("🗑️ Đã xóa sạch Nhật kí đo!");
    } catch (err) {
      toast(`Lỗi xóa nhật kí: ${err.message}`);
    }
  });

  // Tab 4
  $("#file-calib-csv").addEventListener("change", (ev) => {
    const f = ev.target.files?.[0];
    if (!f) return;
    STATE.calibMode = "csv";
    STATE.calibFileName = f.name;
    $("#t4-csv-filename").textContent = `Đã chọn file: ${f.name}`;
    const reader = new FileReader();
    reader.onload = () => {
      STATE.calibCsvText = String(reader.result || "");
      $("#t4-source-banner").className = "banner-25d ok";
      $("#t4-source-banner").innerHTML = `<div class="banner-icon">📄</div><div>Đã nạp file <b>${esc(f.name)}</b>. Nhấn <b>Dựng đường chuẩn</b> để phân tích.</div>`;
      runCalibrate(false);
    };
    reader.readAsText(f, "utf-8");
  });
  $("#t4-btn-sim").addEventListener("click", () => {
    STATE.calibMode = "sim";
    STATE.calibCsvText = null;
    $("#t4-source-banner").className = "banner-25d warn";
    $("#t4-source-banner").innerHTML = `<div class="banner-icon">🧪</div><div>Đang dùng bộ dữ liệu mô phỏng Snell (72 điểm).</div>`;
    runCalibrate(false);
  });
  $("#t4-btn-fit").addEventListener("click", () => runCalibrate(false));
  $("#t4-btn-activate").addEventListener("click", () => runCalibrate(true));

  // Tab 5
  ["t5-a", "t5-d", "t5-s", "t5-t"].forEach((id) => {
    $(`#${id}`).addEventListener("input", () => {
      $("#val-t5-a").textContent = `${Number($("#t5-a").value).toFixed(1)}°`;
      $("#val-t5-d").textContent = `${Number($("#t5-d").value).toFixed(1)} m`;
      $("#val-t5-s").textContent = `${Number($("#t5-s").value).toFixed(1)} ‰`;
      $("#val-t5-t").textContent = `${Number($("#t5-t").value).toFixed(1)} °C`;
      debounce("t5", runOpticsSim, 75);
    });
  });
  ["t5-pxmm", "t5-err-tam", "t5-err-t", "t5-err-a", "t5-err-troi", "t5-err-triet"].forEach((id) => {
    $(`#${id}`).addEventListener("change", runOpticsSim);
  });
  $("#t5-btn-save-config").addEventListener("click", saveOpticsConfig);

  // Tab 6
  $("#t6-btn-sample").addEventListener("click", () => runBlandAltman("sample"));
  $("#t6-btn-add-row").addEventListener("click", () => {
    STATE.baPairs.push({ S_thiet_bi: 15.0, S_khuc_xa_ke: 15.0 });
    renderBaPairsTable();
    runBlandAltman("custom");
  });
  $("#file-ba-csv").addEventListener("change", (ev) => {
    const f = ev.target.files?.[0];
    if (!f) return;
    const reader = new FileReader();
    reader.onload = () => runBlandAltman("csv", String(reader.result || ""));
    reader.readAsText(f, "utf-8");
  });

  window.addEventListener("resize", () => {
    debounce("win_resize", () => {
      const activeTab = $(".tab-pane.active")?.id;
      if (activeTab === "tab-1" && STATE.lastMeasure) drawTab1Charts(STATE.lastMeasure);
      if (activeTab === "tab-3" && STATE.logLast) drawLogsChart(STATE.logLast);
      if (activeTab === "tab-4" && STATE.calibLast) drawCalibrationCharts(STATE.calibLast);
      if (activeTab === "tab-5" && STATE.opticsLast) drawOpticsCharts(STATE.opticsLast);
      if (activeTab === "tab-6" && STATE.baLast) drawBaCharts(STATE.baLast);
    }, 100);
  }, { passive: true });
}

function initLiveTour() {
  const ring = $("#live-tour-ring");
  const card = $("#live-tour-card");
  if (!ring || !card) return;

  const STEP_MS = 10000;
  const steps = [
    {
      tab: "tab-1",
      selector: "#net-status-pill",
      title: "1. Chế độ Ngoại tuyến (PWA & Đồng bộ Offline)",
      desc: "Huy hiệu này báo trạng thái Trực tuyến hoặc Ngoại tuyến. Ứng dụng có thể cài như app (PWA), lưu đệm giao diện để dùng ngay cả khi ra ao mất mạng; mọi phép đo chưa gửi sẽ xếp vào hàng đợi và tự đồng bộ khi có Internet.",
      hint: "👉 Mẹo: Khi mất mạng, biểu tượng hàng đợi màu vàng sẽ hiện cạnh đây để bạn theo dõi.",
    },
    {
      tab: "tab-1",
      selector: ".sb-profile-row",
      title: "2. Quản lý Đa hồ sơ hộ nuôi / xưởng",
      desc: "Mỗi hộ nuôi tôm, ruộng lúa hoặc phân xưởng công nghiệp có thể tạo một Hồ sơ riêng. Dữ liệu nhật kí SQLite và file đường chuẩn JSON được tách biệt hoàn toàn giữa các hồ sơ.",
      hint: "👉 Mẹo: Đổi hồ sơ trong danh sách hoặc bấm nút + để tạo hồ sơ mới.",
    },
    {
      tab: "tab-1",
      selector: "#sb-calib-status",
      title: "3. Trạng thái Đường chuẩn & Thông số Quang học",
      desc: "Thẻ thanh bên hiển thị máy đang dùng đường chuẩn Mô phỏng hay Thực nghiệm (kèm R², sai số dư s_res), cùng góc lăng kính A, khoảng cách màn D và độ nhạy quang học hiện tại.",
      hint: "👉 Mẹo: Bấm Tiếp theo hoặc xem các thông số thiết bị ngay bên thanh trái.",
    },
    {
      tab: "tab-1",
      selector: ".ui-mode-switch",
      title: "4. Chuyển chế độ Dễ dùng & Kỹ thuật",
      desc: "🌾 Dễ dùng ẩn bớt các bảng chuyên sâu để nông dân thao tác nhanh ngoài ao. 🔬 Kỹ thuật mở toàn bộ đồ thị Gauss, thông số sai số, hiệu chuẩn, mô phỏng quang học và đối chứng thiết bị.",
      hint: "👉 Mẹo: Nhấn thử nút Dễ dùng / Kỹ thuật hoặc đợi tự chuyển bước.",
    },
    {
      tab: "tab-1",
      selector: ".segmented-25d",
      title: "5. Chọn nguồn ảnh mẫu nước (3 cách)",
      desc: "Chọn 🧪 Thử mẫu để mô phỏng nhanh bằng thanh trượt; 📁 Tải ảnh để nạp ảnh vạch laser chụp sẵn (có khung xem trước); hoặc 📷 Camera để chụp trực tiếp bằng webcam/camera sau điện thoại.",
      hint: "👉 Mẹo: Chọn một nguồn ảnh hoặc kéo thanh độ mặn mô phỏng để chuyển bước ngay.",
    },
    {
      tab: "tab-1",
      selector: "#meas-location",
      title: "6. Nhập tên Ao nuôi / Vị trí lấy mẫu",
      desc: "Ghi tên ao hoặc vị trí đo (ví dụ: Ao nuôi tôm số 1, Kênh cấp) để phân loại nhật kí. Hệ thống tự động ghi nhớ và gợi ý lại các tên ao bạn từng đo.",
      hint: "👉 Mẹo: Nhập hoặc chọn tên ao của bạn rồi bấm Enter / nhấn ra ngoài.",
    },
    {
      tab: "tab-1",
      selector: "#meas-temp",
      title: "7. Nhập nhiệt độ mẫu nước (°C)",
      desc: "Nhập nhiệt độ nước thực tế từ nhiệt kế (mặc định 26.0 °C). Thuật toán tự động bù sai lệch chiết suất theo nhiệt độ để đảm bảo độ chính xác độ mặn.",
      hint: "👉 Mẹo: Chỉnh nhiệt độ mẫu nước thực tế hoặc bấm Tiếp theo.",
    },
    {
      tab: "tab-1",
      selector: "#btn-run-measure",
      title: "8. Chạy phép đo Độ mặn & Độ đục",
      desc: "Khi bấm Kiểm tra nước ngay, hệ thống tự định vị 2 vạch laser (tham chiếu 0‰ và mẫu nước), tính độ lệch đứng Δy dưới mức 1 pixel, suy ra độ mặn (‰) và chỉ số độ đục.",
      hint: "👉 Mẹo: Nhấn nút Kiểm tra nước ngay để xem hệ thống phân tích.",
    },
    {
      tab: "tab-1",
      mode: "pro",
      selector: ".kpi-row-4",
      title: "9. Đọc 4 chỉ số: Độ mặn, Δy, Độ đục & Chất lượng",
      desc: "4 thẻ kết quả hiển thị đầy đủ: Độ mặn (‰) kèm độ bất định mở rộng ± U, độ lệch vi sai Δy (px), mức Độ đục (FWHM) và Chất lượng ảnh + tỉ lệ tín hiệu/nhiễu SNR.",
      hint: "👉 Mẹo: Hệ thống tự cảnh báo nếu ảnh bị bão hòa lóa sáng hoặc quá mờ.",
    },
    {
      tab: "tab-1",
      mode: "pro",
      selector: ".t1-img-col .chassis-panel-25d",
      title: "10. Ảnh nhận diện 2 vạch & Mặt cắt Gauss I(y)",
      desc: "Ảnh đánh dấu trực quan vị trí vạch chuẩn (xanh) và vạch mẫu (cam). Ở chế độ Kỹ thuật, bên cạnh còn có đồ thị Mặt cắt cường độ Gauss I(y) giúp kiểm chứng độ mượt đỉnh tia laser.",
      hint: "👉 Mẹo: Có thể mở thêm ngăn 'Chi tiết kỹ thuật' bên dưới để xem bảng thống kê từng vạch.",
    },
    {
      tab: "tab-1",
      selector: "#t1-species-select",
      title: "11. Kiểm tra nhanh Ngưỡng an toàn cho Loài nuôi",
      desc: "Chọn tôm sú, tôm thẻ, cá tra, lúa, sầu riêng... Hệ thống đối chiếu ngay độ mặn vừa đo với ngưỡng sinh học (Xanh: An toàn, Vàng: Cảnh báo, Đỏ: Nguy hiểm) kèm khuyến cáo.",
      hint: "👉 Mẹo: Thử đổi loài nuôi trong danh sách để xem kết quả cảnh báo đổi màu.",
    },
    {
      tab: "tab-1",
      selector: "#btn-save-log",
      title: "12. Lưu kết quả vào Nhật kí (Hỗ trợ Offline)",
      desc: "Bấm Lưu kết quả để ghi phép đo vào cơ sở dữ liệu SQLite theo đúng hồ sơ và tên ao hiện tại. Nếu mất mạng, phép đo tự lưu vào hàng đợi Offline trên máy.",
      hint: "👉 Mẹo: Nhấn Lưu kết quả để ghi lại phép đo này vào Nhật kí.",
    },
    {
      tab: "tab-2",
      selector: "#t2-spectrum-container",
      title: "13. Tab 2: Dải phổ Ngưỡng sinh học & Ma trận loài",
      desc: "Tab Ngưỡng loài nuôi trực quan hóa dải độ mặn An toàn / Cảnh báo / Nguy hiểm cho từng loài, hiển thị trích dẫn nguồn khoa học và bảng ma trận so sánh toàn bộ loài cùng lúc.",
      hint: "👉 Mẹo: Bạn có thể chọn nhanh loài khác hoặc nhập giá trị độ mặn tùy ý để mô phỏng.",
    },
    {
      tab: "tab-2",
      selector: "#t2-edit-species-drawer",
      title: "14. Tab 2: Thêm / Sửa ngưỡng loài vào config.yaml",
      desc: "Mở ngăn kéo này để thêm loài thủy sản/cây trồng mới hoặc điều chỉnh lại các ngưỡng an toàn, cảnh báo, nguy hiểm và nguồn tham khảo. Dữ liệu được lưu thẳng vào file config.yaml.",
      hint: "👉 Mẹo: Bấm vào tiêu đề ngăn kéo để mở biểu mẫu chỉnh sửa trực tiếp.",
    },
    {
      tab: "tab-3",
      selector: "#t3-filter-location",
      title: "15. Tab 3: Nhật kí theo Ao, Xuất CSV & Xóa dòng",
      desc: "Tab Nhật kí đo cho phép lọc theo từng Ao/vị trí, theo Loài hoặc Nguồn đo; xuất file CSV đúng theo bộ lọc đang chọn; nạp 10 mẫu thử nghiệm hoặc xóa từng bản ghi sai.",
      hint: "👉 Mẹo: Thử đổi bộ lọc Ao hoặc bấm Xuất CSV để tải báo cáo.",
    },
    {
      tab: "tab-4",
      mode: "pro",
      selector: "#t4-btn-fit",
      title: "16. Tab 4: Hiệu chuẩn máy từ CSV Thực nghiệm 7 cột",
      desc: "Tab Hiệu chuẩn cho phép tải file CSV đo mẫu chuẩn NaCl (hoặc dùng 72 điểm mô phỏng Snell), tự chọn bậc đa thức tối ưu qua kiểm định chéo, xem R²/RMSE và Lưu & Áp dụng riêng cho hồ sơ hiện tại.",
      hint: "👉 Mẹo: Tải file CSV chuẩn hoặc bấm Nạp 72 điểm mô phỏng rồi bấm Dựng đường chuẩn.",
    },
    {
      tab: "tab-5",
      mode: "pro",
      selector: "#t5-btn-save-config",
      title: "17. Tab 5: Mô phỏng Quang học Snell & Lưu config.yaml",
      desc: "Tab Mô phỏng quang học tính góc lệch tia laser theo góc đỉnh lăng kính A, khoảng cách màn D, kích thước pixel, kiểm tra giới hạn phản xạ toàn phần (TIR) và lưu cấu hình máy vào config.yaml.",
      hint: "👉 Mẹo: Điều chỉnh thanh trượt A, D, pixel ở bên trái để xem độ nhạy (px/‰) thay đổi.",
    },
    {
      tab: "tab-6",
      mode: "pro",
      selector: "#t6-btn-sample",
      title: "18. Tab 6: Đối chứng Bland–Altman với Thiết bị chuẩn",
      desc: "Tab Đối chứng thiết bị giúp bạn nhập cặp số liệu đo song song giữa máy laser và khúc xạ kế thương mại chuẩn, tự động tính độ chệch Bias, giới hạn đồng thuận LoA (±1.96 SD) và hồi quy R².",
      hint: "👉 Hoàn tất! Bấm Hoàn tất ✓ để quay lại màn hình đo chính.",
    },
  ];

  const tour = {
    active: false,
    paused: false,
    idx: 0,
    timerId: null,
    stepStart: 0,
    remainMs: STEP_MS,
    advancePending: false,
    savedUiMode: "simple",
  };

  const positionElements = () => {
    if (!tour.active) return;
    const target = $(steps[tour.idx].selector);
    if (!target) return;
    const rect = target.getBoundingClientRect();
    const pad = 6;
    ring.style.top = `${Math.max(4, rect.top - pad)}px`;
    ring.style.left = `${Math.max(4, rect.left - pad)}px`;
    ring.style.width = `${rect.width + pad * 2}px`;
    ring.style.height = `${rect.height + pad * 2}px`;

    const cardRect = card.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    let top = rect.bottom + 14;
    let left = rect.left;

    if (top + cardRect.height > vh - 12) {
      top = Math.max(12, rect.top - cardRect.height - 14);
    }
    if (top < 12) top = 12;
    if (left + cardRect.width > vw - 12) {
      left = Math.max(12, vw - cardRect.width - 12);
    }
    if (left < 12) left = 12;

    card.style.top = `${top}px`;
    card.style.left = `${left}px`;
  };

  const updateTimerUI = (remainMs) => {
    const countdownEl = $("#tour-countdown");
    const fillEl = $("#tour-progress-fill");
    const pauseBtn = $("#btn-tour-pause");
    if (tour.paused) {
      countdownEl.textContent = `⏸️ Đang tạm dừng (${Math.ceil(remainMs / 1000)}s)`;
      countdownEl.classList.add("paused");
      if (pauseBtn) pauseBtn.textContent = "▶️ Tiếp";
    } else {
      const remainSec = Math.max(0, Math.ceil(remainMs / 1000));
      countdownEl.textContent = `⏳ Tự chuyển sau ${remainSec}s`;
      countdownEl.classList.remove("paused");
      if (pauseBtn) pauseBtn.textContent = "⏸️ Dừng";
    }
    fillEl.style.width = `${Math.max(0, Math.min(100, (remainMs / STEP_MS) * 100))}%`;
  };

  const stopTour = (markDone = true, showDoneToast = false) => {
    tour.active = false;
    tour.paused = false;
    tour.advancePending = false;
    if (tour.timerId) {
      clearInterval(tour.timerId);
      tour.timerId = null;
    }
    window.removeEventListener("scroll", positionElements, true);
    window.removeEventListener("resize", positionElements);
    ring.classList.remove("open");
    card.classList.remove("open");
    if (typeof window._setUiMode === "function") {
      window._setUiMode(tour.savedUiMode || "simple", false);
    }
    switchTab("tab-1");
    if (markDone) {
      try {
        localStorage.setItem("salinity_tour_done", "1");
      } catch (_) {}
    }
    if (showDoneToast) {
      toast("🎉 Đã hoàn thành toàn bộ 18 bước hướng dẫn tính năng! Chúc bạn sử dụng hiệu quả.");
    }
  };

  const startStepTimer = (durationMs = STEP_MS) => {
    if (tour.timerId) clearInterval(tour.timerId);
    tour.remainMs = durationMs;
    tour.stepStart = Date.now();
    updateTimerUI(tour.remainMs);

    tour.timerId = setInterval(() => {
      if (!tour.active || tour.paused) return;
      const elapsed = Date.now() - tour.stepStart;
      const remainMs = Math.max(0, tour.remainMs - elapsed);
      updateTimerUI(remainMs);
      if (remainMs <= 0) {
        goToStep(tour.idx + 1);
      }
    }, 200);
  };

  const goToStep = (idx) => {
    if (!tour.active) return;
    if (idx < 0) idx = 0;
    if (idx >= steps.length) {
      stopTour(true, true);
      return;
    }
    tour.idx = idx;
    tour.paused = false;
    tour.advancePending = false;

    const st = steps[idx];
    if (typeof window._setUiMode === "function") {
      if (st.mode === "pro") {
        window._setUiMode("pro", false);
      } else {
        window._setUiMode(tour.savedUiMode || "simple", false);
      }
    }
    switchTab(st.tab || "tab-1");

    $("#tour-step-badge").textContent = `Bước ${idx + 1}/${steps.length}`;
    $("#tour-step-title").textContent = st.title;
    $("#tour-step-desc").textContent = st.desc;
    const hintEl = $("#tour-action-hint");
    if (hintEl) hintEl.textContent = st.hint || "";

    const prevBtn = $("#btn-tour-prev");
    if (prevBtn) prevBtn.disabled = idx === 0;
    $("#btn-tour-next").textContent = idx === steps.length - 1 ? "Hoàn tất ✓" : "Tiếp theo →";

    const target = $(st.selector);
    if (target) {
      target.scrollIntoView({ behavior: "smooth", block: "center" });
    }
    ring.classList.add("open");
    card.classList.add("open");
    requestAnimationFrame(() => {
      positionElements();
      setTimeout(positionElements, 300);
    });

    startStepTimer(STEP_MS);
  };

  const completeCurrentStep = (expectedIdx) => {
    if (!tour.active || tour.idx !== expectedIdx || tour.advancePending) return;
    tour.advancePending = true;
    setTimeout(() => {
      if (tour.active && tour.idx === expectedIdx) {
        goToStep(expectedIdx + 1);
      }
    }, 350);
  };

  const startTour = () => {
    tour.savedUiMode = document.body.classList.contains("ui-simple") ? "simple" : "pro";
    tour.active = true;
    tour.paused = false;
    window.addEventListener("scroll", positionElements, { passive: true, capture: true });
    window.addEventListener("resize", positionElements, { passive: true });
    goToStep(0);
  };

  $("#btn-tour-skip").addEventListener("click", () => {
    stopTour(true, false);
    toast("⏭️ Đã bỏ qua hướng dẫn. Bạn có thể mở lại ở thanh bên bất cứ lúc nào.");
  });
  $("#btn-tour-next").addEventListener("click", () => goToStep(tour.idx + 1));

  const btnTourPrev = $("#btn-tour-prev");
  if (btnTourPrev) {
    btnTourPrev.addEventListener("click", () => {
      if (tour.idx > 0) goToStep(tour.idx - 1);
    });
  }

  const btnTourPause = $("#btn-tour-pause");
  if (btnTourPause) {
    btnTourPause.addEventListener("click", () => {
      if (!tour.active) return;
      if (!tour.paused) {
        const elapsed = Date.now() - tour.stepStart;
        tour.remainMs = Math.max(1000, tour.remainMs - elapsed);
        tour.paused = true;
        updateTimerUI(tour.remainMs);
      } else {
        tour.paused = false;
        startStepTimer(tour.remainMs);
      }
    });
  }

  const btnModalTour = $("#btn-modal-start-tour");
  if (btnModalTour) {
    btnModalTour.addEventListener("click", () => {
      $("#guide-modal-backdrop").classList.remove("open");
      startTour();
    });
  }

  // Theo dõi thao tác thực tế để tự động chuyển bước ngay khi làm xong
  $("#sb-profile-select")?.addEventListener("change", () => completeCurrentStep(1));
  $$(".ui-mode-btn").forEach((b) => b.addEventListener("click", () => {
    if (tour.active && tour.idx === 3) {
      tour.savedUiMode = b.dataset.uiMode === "pro" ? "pro" : "simple";
      completeCurrentStep(3);
    }
  }));
  $$(".seg-btn").forEach((b) => b.addEventListener("click", () => completeCurrentStep(4)));
  $("#file-laser-img").addEventListener("change", () => completeCurrentStep(4));
  $("#file-laser-capture").addEventListener("change", () => completeCurrentStep(4));
  $("#sim-s").addEventListener("change", () => completeCurrentStep(4));
  $("#sim-duc").addEventListener("change", () => completeCurrentStep(4));
  $("#meas-location")?.addEventListener("change", () => completeCurrentStep(5));
  $("#meas-temp")?.addEventListener("change", () => completeCurrentStep(6));
  $("#btn-run-measure").addEventListener("click", () => completeCurrentStep(7));
  $("#t1-species-select").addEventListener("change", () => completeCurrentStep(10));
  $("#btn-save-log").addEventListener("click", () => completeCurrentStep(11));
  $("#t2-species-select")?.addEventListener("change", () => completeCurrentStep(12));
  $("#t2-edit-species-drawer")?.addEventListener("toggle", () => completeCurrentStep(13));
  $("#t3-filter-location")?.addEventListener("change", () => completeCurrentStep(14));
  $("#t3-btn-csv")?.addEventListener("click", () => completeCurrentStep(14));
  $("#t4-btn-fit")?.addEventListener("click", () => completeCurrentStep(15));
  $("#t5-btn-save-config")?.addEventListener("click", () => completeCurrentStep(16));
  $("#t6-btn-sample")?.addEventListener("click", () => completeCurrentStep(17));

  window.addEventListener("keydown", (ev) => {
    if (!tour.active) return;
    if (ev.key === "Escape") {
      stopTour(true, false);
    } else if (ev.key === "ArrowRight") {
      goToStep(tour.idx + 1);
    } else if (ev.key === "ArrowLeft" && tour.idx > 0) {
      goToStep(tour.idx - 1);
    }
  });

  window._startLiveTour = startTour;
}

function initCustomSelects() {
  const selects = $$("select.select-25d, select.sb-select-25d");
  if (!selects.length) return;

  let openInstance = null;
  const instances = [];

  const closeAll = () => {
    if (!openInstance) return;
    openInstance.wrap.classList.remove("is-open");
    openInstance.menu.classList.remove("is-open");
    openInstance.trigger.setAttribute("aria-expanded", "false");
    openInstance = null;
  };

  const positionMenu = (inst) => {
    const rect = inst.trigger.getBoundingClientRect();
    const spaceBelow = window.innerHeight - rect.bottom - 12;
    const spaceAbove = rect.top - 12;
    const menuWidth = Math.max(rect.width, 180);
    inst.menu.style.width = `${menuWidth}px`;
    inst.menu.style.left = `${Math.max(8, Math.min(rect.left, window.innerWidth - menuWidth - 8))}px`;

    const estHeight = Math.min(inst.menu.scrollHeight || 220, 270);
    if (spaceBelow >= estHeight || spaceBelow >= spaceAbove) {
      inst.menu.style.top = `${rect.bottom + 6}px`;
      inst.menu.style.bottom = "auto";
      inst.menu.style.maxHeight = `${Math.max(120, Math.min(270, spaceBelow))}px`;
    } else {
      inst.menu.style.bottom = `${window.innerHeight - rect.top + 6}px`;
      inst.menu.style.top = "auto";
      inst.menu.style.maxHeight = `${Math.max(120, Math.min(270, spaceAbove))}px`;
    }
  };

  const renderMenu = (inst) => {
    const { select, menu } = inst;
    const options = select.options;
    const frag = document.createDocumentFragment();
    for (let i = 0; i < options.length; i++) {
      const opt = options[i];
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "cselect-option";
      btn.setAttribute("role", "option");
      btn.dataset.optIndex = String(i);
      const isSelected = opt.value === select.value;
      if (isSelected) btn.classList.add("is-selected");
      btn.setAttribute("aria-selected", isSelected ? "true" : "false");
      if (opt.disabled) btn.disabled = true;

      const textSpan = document.createElement("span");
      textSpan.textContent = opt.textContent;
      const checkSpan = document.createElement("span");
      checkSpan.className = "cselect-option-check";
      checkSpan.textContent = "✓";

      btn.appendChild(textSpan);
      btn.appendChild(checkSpan);
      frag.appendChild(btn);
    }
    menu.replaceChildren(frag);
    inst.dirty = false;
  };

  const syncSelect = (inst) => {
    const { select, labelEl } = inst;
    const selectedOpt = select.options[select.selectedIndex] || select.options[0];
    labelEl.textContent = selectedOpt ? selectedOpt.textContent : "";
    inst.dirty = true;
    if (openInstance === inst) {
      renderMenu(inst);
    }
  };

  // Dong bo tu dong khi code JS gan select.value = "..."
  const nativeDesc = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value");
  if (nativeDesc && !HTMLSelectElement.prototype.__cselectPatched) {
    Object.defineProperty(HTMLSelectElement.prototype, "value", {
      configurable: true,
      get() {
        return nativeDesc.get.call(this);
      },
      set(val) {
        nativeDesc.set.call(this, val);
        if (this.__cselectSync) this.__cselectSync();
      },
    });
    HTMLSelectElement.prototype.__cselectPatched = true;
  }

  selects.forEach((select) => {
    if (select.dataset.cselectInit === "1") return;
    select.dataset.cselectInit = "1";

    const isSidebar = select.classList.contains("sb-select-25d");
    const wrap = document.createElement("div");
    wrap.className = `cselect-25d${isSidebar ? " is-sidebar" : ""}`;
    select.parentNode.insertBefore(wrap, select);
    wrap.appendChild(select);
    select.classList.add("cselect-native");
    select.tabIndex = -1;

    const trigger = document.createElement("button");
    trigger.type = "button";
    trigger.className = "cselect-trigger";
    trigger.setAttribute("aria-haspopup", "listbox");
    trigger.setAttribute("aria-expanded", "false");
    if (select.title) trigger.title = select.title;

    const labelEl = document.createElement("span");
    labelEl.className = "cselect-label";

    const chevron = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    chevron.setAttribute("class", "cselect-chevron");
    chevron.setAttribute("viewBox", "0 0 20 20");
    chevron.setAttribute("fill", "none");
    chevron.innerHTML = '<path d="M5.5 7.75L10 12.25L14.5 7.75" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>';

    trigger.appendChild(labelEl);
    trigger.appendChild(chevron);
    wrap.appendChild(trigger);

    const menu = document.createElement("div");
    menu.className = `cselect-menu${isSidebar ? " is-sidebar" : ""}`;
    menu.setAttribute("role", "listbox");
    document.body.appendChild(menu);

    const inst = { select, wrap, trigger, labelEl, menu, dirty: true };
    select.__cselectSync = () => syncSelect(inst);
    instances.push(inst);

    menu.addEventListener("click", (ev) => {
      const btn = ev.target.closest(".cselect-option");
      if (!btn || btn.disabled) return;
      ev.stopPropagation();
      const opt = select.options[Number(btn.dataset.optIndex)];
      if (!opt || opt.disabled) return;
      const changed = select.value !== opt.value;
      select.value = opt.value;
      syncSelect(inst);
      closeAll();
      inst.trigger.focus();
      if (changed) {
        select.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });

    trigger.addEventListener("click", (ev) => {
      ev.stopPropagation();
      const willOpen = openInstance !== inst;
      closeAll();
      if (willOpen) {
        if (inst.dirty) renderMenu(inst);
        wrap.classList.add("is-open");
        menu.classList.add("is-open");
        trigger.setAttribute("aria-expanded", "true");
        positionMenu(inst);
        openInstance = inst;
        const activeBtn = menu.querySelector(".cselect-option.is-selected");
        if (activeBtn) activeBtn.scrollIntoView({ block: "nearest" });
      }
    });

    trigger.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape") {
        closeAll();
      } else if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
        ev.preventDefault();
        const opts = Array.from(select.options || []).filter((o) => !o.disabled);
        if (!opts.length) return;
        const curIdx = opts.findIndex((o) => o.value === select.value);
        const nextIdx =
          ev.key === "ArrowDown"
            ? (curIdx + 1) % opts.length
            : (curIdx - 1 + opts.length) % opts.length;
        select.value = opts[nextIdx].value;
        syncSelect(inst);
        select.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });

    select.addEventListener("change", () => syncSelect(inst));

    const obs = new MutationObserver(() => syncSelect(inst));
    obs.observe(select, { childList: true, subtree: true, characterData: true });

    syncSelect(inst);
  });

  document.addEventListener("click", (ev) => {
    if (!openInstance) return;
    if (!openInstance.wrap.contains(ev.target) && !openInstance.menu.contains(ev.target)) {
      closeAll();
    }
  });
  window.addEventListener("resize", () => {
    if (openInstance) positionMenu(openInstance);
  }, { passive: true });
  window.addEventListener("scroll", (ev) => {
    if (openInstance && ev.target !== openInstance.menu) {
      closeAll();
    }
  }, { passive: true, capture: true });
}

document.addEventListener("DOMContentLoaded", async () => {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }
  initCustomSelects();
  bindEvents();
  updateNetworkPill();
  updateOfflineQueueBadge();
  initLiveTour();
  await Promise.all([loadBootstrap(), runMeasure()]);
  flushOfflineQueue(true);
  let tourDone = false;
  try {
    tourDone = localStorage.getItem("salinity_tour_done") === "1";
  } catch (_) {}
  if (!tourDone && typeof window._startLiveTour === "function") {
    setTimeout(() => window._startLiveTour(), 450);
  }
});
