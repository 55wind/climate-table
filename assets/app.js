/* =====================================================================
 * 날씨 샌드박스 (Weather Sandbox Korea) — 시뮬레이션 엔진 + UI
 * 순수 클라이언트(JS/Canvas). 백엔드·빌드·외부API 없음.
 * 물리: 기압장 → 기압경도력 + 전향력(지균풍) + 마찰 → 바람장 → 입자 이류
 * ===================================================================== */
(() => {
"use strict";

/* ---------------- 캔버스/투영 ---------------- */
const stage = document.getElementById("stage");
const view = document.getElementById("map");        // 보이는 캔버스
const vctx = view.getContext("2d");
const base = document.createElement("canvas");        // 정적 장면(배경/지도/등압선/기온/강수)
const bctx = base.getContext("2d");
const part = document.createElement("canvas");        // 입자 트레일
const pctx = part.getContext("2d");

let W = 0, H = 0, dpr = 1;
const midLon = (DOMAIN.lonMin + DOMAIN.lonMax) / 2;
const midLat = (DOMAIN.latMin + DOMAIN.latMax) / 2;
const cosMid = Math.cos(midLat * Math.PI / 180);
let scale = 1, cx = 0, cy = 0;

function project(lon, lat) {
  return [cx + (lon - midLon) * cosMid * scale, cy - (lat - midLat) * scale];
}
function unproject(x, y) {
  return [(x - cx) / (cosMid * scale) + midLon, midLat - (y - cy) / scale];
}

function resize() {
  W = stage.clientWidth; H = stage.clientHeight;
  dpr = Math.min(window.devicePixelRatio || 1, 2);
  for (const c of [view, base, part]) { c.width = W * dpr; c.height = H * dpr; }
  view.style.width = base.style.width = part.style.width = W + "px";
  view.style.height = base.style.height = part.style.height = H + "px";
  for (const ctx of [vctx, bctx, pctx]) { ctx.setTransform(dpr, 0, 0, dpr, 0, 0); }
  // 도메인을 화면에 맞춤(여백 포함)
  const lonSpan = (DOMAIN.lonMax - DOMAIN.lonMin) * cosMid;
  const latSpan = (DOMAIN.latMax - DOMAIN.latMin);
  scale = Math.min(W / lonSpan, H / latSpan) * 0.98;
  cx = W / 2; cy = H / 2;
  seedParticles();
  computeFields();
  drawBase();
}

/* ---------------- 상태 ---------------- */
let systems = [];   // {type,lon,lat,strength,radius,temp,label}
let warmF = 0;      // 0..1 온난화 강도
let playing = true;
let armed = null;   // 'H' | 'L' 배치 대기
let selected = null;
let currentScene = "자유 탐색 모드";
const layers = { wind: true, iso: true, temp: false, rain: true };

/* ---------------- 기압/기온 장 ---------------- */
const P0 = 1013;
// 온난화 시 북태평양고기압 강화 계수
function boosted(s) {
  let str = s.strength, rad = s.radius, tmp = s.temp;
  if (s.label && s.label.indexOf("북태평양") >= 0) {
    str *= (1 + warmF * 0.55); rad *= (1 + warmF * 0.30); tmp += warmF * 3;
  }
  return { str, rad, tmp };
}
function pressureAt(lon, lat) {
  let p = P0;
  for (const s of systems) {
    const b = boosted(s);
    const dx = (lon - s.lon) * cosMid, dy = (lat - s.lat);
    const d2 = dx * dx + dy * dy;
    p += b.str * Math.exp(-d2 / (2 * b.rad * b.rad));
  }
  return p;
}
function baseTemp(lat) { return 30 - (lat - 32) * 1.7 + warmF * 5; }
function tempAt(lon, lat) {
  let t = baseTemp(lat);
  for (const s of systems) {
    const b = boosted(s);
    const dx = (lon - s.lon) * cosMid, dy = (lat - s.lat);
    const d2 = dx * dx + dy * dy;
    t += b.tmp * Math.exp(-d2 / (2 * b.rad * b.rad));
  }
  return t;
}
// 지균풍 + 마찰 → (동, 북) 성분
const FRIC = 22 * Math.PI / 180; // 마찰 유입각
const cosA = Math.cos(FRIC), sinA = Math.sin(FRIC);
function windAt(lon, lat) {
  const dl = 0.06;
  const Px = (pressureAt(lon + dl, lat) - pressureAt(lon - dl, lat)) / (2 * dl);
  const Py = (pressureAt(lon, lat + dl) - pressureAt(lon, lat - dl)) / (2 * dl);
  const f = Math.max(0.45, Math.sin(lat * Math.PI / 180)); // 전향력(위도 의존)
  // 지균풍: 경도벡터를 +90°(반시계) 회전 → 북반구 저기압=반시계
  const gE = -Py / f, gN = Px / f;
  // 마찰 회전(-α): 저기압 유입/고기압 발산
  let wE = gE * cosA + gN * sinA;
  let wN = -gE * sinA + gN * cosA;
  // 풍속 상한(현실 최대치 ~65 m/s) — 입자 점프·비현실 수치 방지
  const cap = 65 / WIND_MS, mag = Math.hypot(wE, wN);
  if (mag > cap) { const k = cap / mag; wE *= k; wN *= k; }
  return [wE, wN];
}

/* ---------------- 격자장(등압선/기온/강수/지표) ---------------- */
let grid = null;
const GSTEP = 13; // px 간격
function computeFields() {
  const nx = Math.ceil(W / GSTEP) + 1, ny = Math.ceil(H / GSTEP) + 1;
  const P = new Float32Array(nx * ny), T = new Float32Array(nx * ny);
  const conv = new Float32Array(nx * ny);
  let maxWind = 0, maxConv = 0;
  for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
    const x = i * GSTEP, y = j * GSTEP;
    const [lon, lat] = unproject(x, y);
    const idx = j * nx + i;
    P[idx] = pressureAt(lon, lat);
    T[idx] = tempAt(lon, lat);
    const [wE, wN] = windAt(lon, lat);
    const sp = Math.hypot(wE, wN) * WIND_MS;
    if (sp > maxWind) maxWind = sp;
    // 수렴(발산의 음수)
    const e = 0.06;
    const [aE] = windAt(lon + e, lat), [, bN] = windAt(lon, lat + e);
    const [cE] = windAt(lon - e, lat), [, dN] = windAt(lon, lat - e);
    const div = (aE - cE) / (2 * e) + (bN - dN) / (2 * e);
    const c = Math.max(0, -div) * Math.max(0, (T[idx] - 6) / 24); // 수렴 × 수증기(기온)
    conv[idx] = c;
    if (c > maxConv) maxConv = c;
  }
  grid = { nx, ny, P, T, conv, maxWind, maxConv };
  updateIndices();
}

/* 마칭스퀘어 등압선 */
function drawIsobars(ctx) {
  if (!grid) return;
  const { nx, ny, P } = grid;
  let lo = Infinity, hi = -Infinity;
  for (let k = 0; k < P.length; k++) { if (P[k] < lo) lo = P[k]; if (P[k] > hi) hi = P[k]; }
  const step = 4; // hPa
  const start = Math.ceil(lo / step) * step;
  ctx.lineWidth = 1;
  ctx.font = "10px Pretendard";
  for (let lev = start; lev <= hi; lev += step) {
    const main = (lev % 20 === 0);
    ctx.strokeStyle = main ? "rgba(170,200,235,0.55)" : "rgba(120,150,185,0.32)";
    ctx.beginPath();
    for (let j = 0; j < ny - 1; j++) for (let i = 0; i < nx - 1; i++) {
      const x0 = i * GSTEP, y0 = j * GSTEP, x1 = x0 + GSTEP, y1 = y0 + GSTEP;
      const a = P[j * nx + i], b = P[j * nx + i + 1];
      const c = P[(j + 1) * nx + i + 1], d = P[(j + 1) * nx + i];
      let cs = (a > lev ? 1 : 0) | (b > lev ? 2 : 0) | (c > lev ? 4 : 0) | (d > lev ? 8 : 0);
      if (cs === 0 || cs === 15) continue;
      const T = (p, q, va, vb, xa, ya, xb, yb) => {
        const t = (lev - va) / (vb - va);
        return [xa + (xb - xa) * t, ya + (yb - ya) * t];
      };
      const top = () => T(0, 0, a, b, x0, y0, x1, y0);
      const right = () => T(0, 0, b, c, x1, y0, x1, y1);
      const bot = () => T(0, 0, d, c, x0, y1, x1, y1);
      const left = () => T(0, 0, a, d, x0, y0, x0, y1);
      const seg = (p, q) => { ctx.moveTo(p[0], p[1]); ctx.lineTo(q[0], q[1]); };
      switch (cs) {
        case 1: case 14: seg(left(), top()); break;
        case 2: case 13: seg(top(), right()); break;
        case 3: case 12: seg(left(), right()); break;
        case 4: case 11: seg(right(), bot()); break;
        case 6: case 9: seg(top(), bot()); break;
        case 7: case 8: seg(left(), bot()); break;
        case 5: seg(left(), top()); seg(right(), bot()); break;
        case 10: seg(top(), right()); seg(left(), bot()); break;
      }
    }
    ctx.stroke();
  }
}

function tempColor(t) {
  // -10 → 38 ℃ 를 파랑→빨강
  const stops = [
    [-12, 30, 60, 140], [0, 40, 120, 200], [10, 60, 180, 170],
    [20, 120, 200, 90], [27, 240, 200, 70], [33, 245, 120, 50], [40, 220, 40, 40]
  ];
  let c = stops[0];
  for (let i = 0; i < stops.length - 1; i++) {
    if (t >= stops[i][0] && t <= stops[i + 1][0]) {
      const a = stops[i], b = stops[i + 1], f = (t - a[0]) / (b[0] - a[0]);
      return [a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f, a[3] + (b[3] - a[3]) * f];
    }
  }
  if (t < stops[0][0]) c = stops[0]; else c = stops[stops.length - 1];
  return [c[1], c[2], c[3]];
}

/* ---------------- 정적 장면 그리기 ---------------- */
function lonlatPath(ctx, ring) {
  ctx.beginPath();
  ring.forEach((p, i) => { const [x, y] = project(p[0], p[1]); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
}
function drawBase() {
  bctx.clearRect(0, 0, W, H);
  // 바다 배경
  const g = bctx.createLinearGradient(0, 0, 0, H);
  g.addColorStop(0, "#0c2138"); g.addColorStop(1, "#06101f");
  bctx.fillStyle = g; bctx.fillRect(0, 0, W, H);

  // 기온 레이어
  if (layers.temp && grid) {
    const { nx, ny, T } = grid;
    for (let j = 0; j < ny - 1; j++) for (let i = 0; i < nx - 1; i++) {
      const [r, gg, b] = tempColor(T[j * nx + i]);
      bctx.fillStyle = `rgba(${r|0},${gg|0},${b|0},0.45)`;
      bctx.fillRect(i * GSTEP, j * GSTEP, GSTEP + 1, GSTEP + 1);
    }
  }

  // 등압선
  if (layers.iso) drawIsobars(bctx);

  // 육지
  bctx.save();
  lonlatPath(bctx, PENINSULA);
  bctx.fillStyle = "rgba(28,52,40,0.55)";
  bctx.fill();
  bctx.lineWidth = 1.4; bctx.strokeStyle = "rgba(150,210,180,0.7)"; bctx.stroke();
  lonlatPath(bctx, JEJU); bctx.fill(); bctx.stroke();
  bctx.restore();

  // 강수/전선 레이어 (육지 위에도 보이도록 육지 다음에 그림)
  if (layers.rain && grid && grid.maxConv > 0) {
    const { nx, ny, conv, maxConv } = grid;
    for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
      const c = conv[j * nx + i] / maxConv;
      if (c < 0.22) continue;
      const x = i * GSTEP, y = j * GSTEP;
      const rad = GSTEP * 1.9;
      const rg = bctx.createRadialGradient(x, y, 0, x, y, rad);
      const a = Math.min(0.62, (c - 0.18) * 1.0);
      rg.addColorStop(0, `rgba(90,170,255,${a})`);
      rg.addColorStop(0.6, `rgba(60,130,245,${a * 0.6})`);
      rg.addColorStop(1, "rgba(70,150,255,0)");
      bctx.fillStyle = rg; bctx.beginPath(); bctx.arc(x, y, rad, 0, 7); bctx.fill();
    }
  }

  // 위경도 그리드(옅게)
  bctx.strokeStyle = "rgba(120,150,185,0.10)"; bctx.lineWidth = 1;
  for (let lo = 124; lo <= 132; lo += 2) {
    const [x] = project(lo, midLat); bctx.beginPath(); bctx.moveTo(x, 0); bctx.lineTo(x, H); bctx.stroke();
  }
  for (let la = 34; la <= 42; la += 2) {
    const [, y] = project(midLon, la); bctx.beginPath(); bctx.moveTo(0, y); bctx.lineTo(W, y); bctx.stroke();
  }

  // 도시
  bctx.fillStyle = "rgba(235,242,255,0.9)"; bctx.font = "11px Pretendard";
  for (const c of CITIES) {
    const [x, y] = project(c.lon, c.lat);
    bctx.beginPath(); bctx.arc(x, y, 2.2, 0, 7); bctx.fill();
    bctx.fillText(c.name, x + 5, y + 3);
  }

  // 기압계 시스템 마커
  for (const s of systems) drawSystem(bctx, s);
}
function drawSystem(ctx, s) {
  const [x, y] = project(s.lon, s.lat);
  const isH = s.strength > 0;
  const col = s.type === "TY" ? "#d65bff" : (isH ? "#ff7a59" : "#5b8def");
  ctx.save();
  // 영향 반경
  const rpx = s.radius * scale;
  ctx.strokeStyle = col + ""; ctx.globalAlpha = 0.25; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.arc(x, y, rpx, 0, 7); ctx.stroke();
  ctx.globalAlpha = 1;
  // 중심
  ctx.beginPath(); ctx.arc(x, y, 15, 0, 7);
  ctx.fillStyle = col; ctx.fill();
  if (s === selected) { ctx.lineWidth = 2.5; ctx.strokeStyle = "#fff"; ctx.stroke(); }
  ctx.fillStyle = "#fff"; ctx.font = "700 14px Pretendard"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.fillText(s.type === "TY" ? "🌀" : (isH ? "고" : "저"), x, y + 1);
  ctx.textAlign = "left"; ctx.textBaseline = "alphabetic";
  if (s.label) {
    ctx.font = "10px Pretendard"; ctx.fillStyle = "rgba(255,255,255,0.85)";
    const tw = ctx.measureText(s.label).width;
    ctx.fillStyle = "rgba(8,18,33,0.7)"; ctx.fillRect(x - tw / 2 - 4, y + 18, tw + 8, 15);
    ctx.fillStyle = "rgba(255,255,255,0.9)"; ctx.textAlign = "center";
    ctx.fillText(s.label, x, y + 29); ctx.textAlign = "left";
  }
  ctx.restore();
}

/* ---------------- 입자(바람) ---------------- */
const WIND_MS = 12;     // 바람 벡터 → m/s 환산(표시/속도 튜닝)
const PX_SPEED = 1.05;  // 입자 픽셀 이동 스케일
let particles = [];
function seedParticles() {
  const n = Math.min(3200, Math.floor(W * H / 360));
  particles = new Array(n);
  for (let i = 0; i < n; i++) particles[i] = newParticle();
}
function newParticle() {
  return { x: Math.random() * W, y: Math.random() * H, age: Math.random() * 90 | 0, life: 60 + Math.random() * 80 | 0 };
}
function stepParticles() {
  // 트레일 페이드
  pctx.globalCompositeOperation = "destination-out";
  pctx.fillStyle = "rgba(0,0,0,0.10)";
  pctx.fillRect(0, 0, W, H);
  pctx.globalCompositeOperation = "source-over";
  pctx.lineWidth = 1.15;
  for (const p of particles) {
    if (p.age++ > p.life || p.x < -5 || p.x > W + 5 || p.y < -5 || p.y > H + 5) {
      Object.assign(p, newParticle()); continue;
    }
    const [lon, lat] = unproject(p.x, p.y);
    const [wE, wN] = windAt(lon, lat);
    const sp = Math.hypot(wE, wN);
    const vx = wE * PX_SPEED, vy = -wN * PX_SPEED; // 화면 y 반전
    const nx = p.x + vx, ny = p.y + vy;
    const ms = sp * WIND_MS;
    // 속도별 색
    let col;
    if (ms < 6) col = "rgba(150,200,255,0.55)";
    else if (ms < 14) col = "rgba(120,230,200,0.65)";
    else if (ms < 24) col = "rgba(245,225,120,0.75)";
    else col = "rgba(255,130,90,0.85)";
    pctx.strokeStyle = col;
    pctx.beginPath(); pctx.moveTo(p.x, p.y); pctx.lineTo(nx, ny); pctx.stroke();
    p.x = nx; p.y = ny;
  }
}

/* ---------------- 메인 루프 ---------------- */
function frame() {
  if (playing && layers.wind) stepParticles();
  vctx.clearRect(0, 0, W, H);
  vctx.drawImage(base, 0, 0, W, H);
  if (layers.wind) vctx.drawImage(part, 0, 0, W, H);
  requestAnimationFrame(frame);
}

/* ---------------- 지표/패널 업데이트 ---------------- */
const $ = id => document.getElementById(id);
function updateIndices() {
  if (!grid) return;
  const maxWind = Math.round(grid.maxWind);
  // 폭염위험: 남부 대표지점 최고기온
  let tmax = -99;
  for (const c of [CITIES[0], CITIES[1], CITIES[2], CITIES[4]]) tmax = Math.max(tmax, tempAt(c.lon, c.lat));
  const heat = Math.max(0, Math.min(100, Math.round((tmax - 24) / (40 - 24) * 100)));
  const rain = Math.max(0, Math.min(100, Math.round(grid.maxConv / 0.9 * 100)));
  $("idxHeat").textContent = heat;
  $("idxWind").textContent = maxWind;
  $("idxRain").textContent = rain;
  $("idxHeat").style.color = heat > 66 ? "#ff7a59" : heat > 33 ? "#ffc24d" : "#34d399";
}

/* ---------------- 학습 카드 ---------------- */
let cardTimer = null, cardIdx = 0;
function setLearn(title, body) { $("learnTitle").textContent = title; $("learnBody").textContent = body; }
function cycleCards() {
  clearInterval(cardTimer);
  cardTimer = setInterval(() => {
    if (currentScene !== "자유 탐색 모드") return;
    const c = CONCEPT_CARDS[cardIdx % CONCEPT_CARDS.length]; cardIdx++;
    setLearn(c.t, c.d);
  }, 9000);
}

/* ---------------- 프리셋 ---------------- */
function loadPreset(key) {
  const p = PRESETS[key];
  systems = p.systems.map(s => Object.assign({}, s));
  currentScene = p.title;
  $("sceneTitle").textContent = p.title;
  selected = null; updateSelPanel();
  setLearn(p.title, p.concept);
  document.querySelectorAll(".preset-grid button").forEach(b => b.classList.toggle("active", b.dataset.key === key));
  $("climateNote").textContent = p.climateNote;
  computeFields(); drawBase();
  $("readout").innerHTML = `<b>${p.title}</b> · ${p.desc}`;
}

/* ---------------- 상호작용 ---------------- */
function evtPos(e) {
  const r = view.getBoundingClientRect();
  const t = e.touches ? e.touches[0] : e;
  return [t.clientX - r.left, t.clientY - r.top];
}
function hitSystem(x, y) {
  for (let i = systems.length - 1; i >= 0; i--) {
    const [sx, sy] = project(systems[i].lon, systems[i].lat);
    if (Math.hypot(x - sx, y - sy) < 18) return systems[i];
  }
  return null;
}
let dragging = null, dragOff = [0, 0];
function pointerDown(e) {
  const [x, y] = evtPos(e);
  if (armed) {
    const [lon, lat] = unproject(x, y);
    const s = armed === "H"
      ? { type: "H", lon, lat, strength: 18, radius: 6, temp: 3, label: "" }
      : { type: "L", lon, lat, strength: -16, radius: 5, temp: 0, label: "" };
    systems.push(s); selected = s;
    setArmed(null); selectSystem(s);
    computeFields(); drawBase();
    setLearn(armed === "H" ? "고기압" : "저기압", s.strength > 0
      ? "고기압: 바람이 시계방향으로 불어 나가고(발산) 하강기류로 날씨가 맑습니다."
      : "저기압: 바람이 반시계방향으로 모여들어(수렴) 상승기류로 구름·비가 생깁니다.");
    return;
  }
  const s = hitSystem(x, y);
  if (s) { dragging = s; const [sx, sy] = project(s.lon, s.lat); dragOff = [x - sx, y - sy]; selectSystem(s); e.preventDefault && e.preventDefault(); }
  else { selectSystem(null); }
}
function pointerMove(e) {
  const [x, y] = evtPos(e);
  if (dragging) {
    const [lon, lat] = unproject(x - dragOff[0], y - dragOff[1]);
    dragging.lon = lon; dragging.lat = lat;
    computeFields(); drawBase();
    e.preventDefault && e.preventDefault();
  } else {
    const [lon, lat] = unproject(x, y);
    const [wE, wN] = windAt(lon, lat);
    const ms = Math.hypot(wE, wN) * WIND_MS;
    const dir = (Math.atan2(-wE, -wN) * 180 / Math.PI + 360) % 360; // 바람이 불어오는 방향
    const dirs = ["북", "북동", "동", "남동", "남", "남서", "서", "북서"];
    const dn = dirs[Math.round(dir / 45) % 8];
    $("readout").innerHTML = `${lat.toFixed(1)}°N ${lon.toFixed(1)}°E · 바람 <b>${dn}풍 ${ms.toFixed(0)}m/s</b> · 기압 <b>${pressureAt(lon,lat).toFixed(0)}hPa</b> · 기온 <b>${tempAt(lon,lat).toFixed(0)}℃</b>`;
  }
}
function pointerUp() { dragging = null; }

function setArmed(t) {
  armed = t;
  document.querySelectorAll(".tool-btn").forEach(b => b.classList.toggle("armed", b.dataset.add === t));
  $("placeHint").textContent = t ? "지도를 클릭해 " + (t === "H" ? "고기압" : "저기압") + "을 놓으세요." : "버튼을 누르고 지도를 클릭하세요. 시스템을 드래그하면 이동합니다.";
}
function selectSystem(s) { selected = s; updateSelPanel(); drawBase(); }
function updateSelPanel() {
  const panel = $("selPanel");
  if (!selected) { panel.hidden = true; return; }
  panel.hidden = false;
  $("strSlider").value = Math.abs(selected.strength);
  $("radSlider").value = selected.radius;
  $("tmpSlider").value = selected.temp;
  $("strVal").textContent = Math.abs(selected.strength) + " hPa";
  $("radVal").textContent = selected.radius + "°";
  $("tmpVal").textContent = (selected.temp > 0 ? "+" : "") + selected.temp + "℃";
}

/* ---------------- 이벤트 바인딩 ---------------- */
function bind() {
  // 프리셋 버튼
  const grid = $("presetGrid");
  for (const key of Object.keys(PRESETS)) {
    const b = document.createElement("button");
    b.dataset.key = key; b.textContent = PRESETS[key].title;
    b.onclick = () => loadPreset(key);
    grid.appendChild(b);
  }
  document.querySelectorAll(".tool-btn").forEach(b => b.onclick = () => setArmed(armed === b.dataset.add ? null : b.dataset.add));

  // 선택 슬라이더
  $("strSlider").oninput = e => { if (!selected) return; const v = +e.target.value; selected.strength = selected.strength < 0 ? -v : v; $("strVal").textContent = v + " hPa"; computeFields(); drawBase(); };
  $("radSlider").oninput = e => { if (!selected) return; selected.radius = +e.target.value; $("radVal").textContent = selected.radius + "°"; computeFields(); drawBase(); };
  $("tmpSlider").oninput = e => { if (!selected) return; selected.temp = +e.target.value; $("tmpVal").textContent = (selected.temp > 0 ? "+" : "") + selected.temp + "℃"; computeFields(); drawBase(); };
  $("delBtn").onclick = () => { if (!selected) return; systems = systems.filter(s => s !== selected); selectSystem(null); computeFields(); drawBase(); };

  // 레이어
  const lay = (id, key) => $(id).onchange = e => { layers[key] = e.target.checked; if (!layers.wind) pctx.clearRect(0, 0, W, H); drawBase(); };
  lay("layWind", "wind"); lay("layIso", "iso"); lay("layTemp", "temp"); lay("layRain", "rain");

  // 온난화
  $("warmSlider").oninput = e => {
    warmF = +e.target.value / 40;
    $("warmVal").textContent = "+" + (warmF * 5).toFixed(1) + " ℃";
    computeFields(); drawBase();
    if (warmF > 0) setLearn("지구온난화 실험", currentScene !== "자유 탐색 모드" && PRESETS[activeKey()] ? PRESETS[activeKey()].climateNote : "기온이 오르고 북태평양고기압이 강해집니다. 폭염위험·강수강도 지표 변화를 보세요.");
  };

  // 기타
  $("resetBtn").onclick = () => { systems = []; selected = null; warmF = 0; $("warmSlider").value = 0; $("warmVal").textContent = "+0.0 ℃"; currentScene = "자유 탐색 모드"; $("sceneTitle").textContent = currentScene; document.querySelectorAll(".preset-grid button").forEach(b => b.classList.remove("active")); updateSelPanel(); setLearn("자유 탐색 모드", "고기압·저기압을 직접 놓고 드래그하며 바람이 어떻게 부는지 실험해 보세요."); computeFields(); drawBase(); };
  $("playBtn").onclick = e => { playing = !playing; e.target.textContent = playing ? "⏸" : "▶"; };
  $("panelToggle").onclick = () => $("panel").classList.toggle("open");
  $("quizBtn").onclick = openQuiz;
  $("quizClose").onclick = () => $("quizModal").hidden = true;
  // 온보딩 힌트: 닫기 버튼 또는 첫 조작 시 사라짐
  const closeOnboard = () => { const o = $("onboard"); if (o) o.style.display = "none"; };
  $("onboardClose").onclick = closeOnboard;
  view.addEventListener("mousedown", closeOnboard, { once: true });
  view.addEventListener("touchstart", closeOnboard, { once: true });
  setTimeout(closeOnboard, 11000);

  // 포인터(마우스 + 터치)
  view.addEventListener("mousedown", pointerDown);
  window.addEventListener("mousemove", pointerMove);
  window.addEventListener("mouseup", pointerUp);
  view.addEventListener("touchstart", pointerDown, { passive: false });
  view.addEventListener("touchmove", e => { pointerMove(e); }, { passive: false });
  view.addEventListener("touchend", pointerUp);
  window.addEventListener("resize", resize);
}
function activeKey() { const b = document.querySelector(".preset-grid button.active"); return b ? b.dataset.key : null; }

/* ---------------- 퀴즈 ---------------- */
const QUIZ = [
  { q: "북반구에서 저기압 주위의 바람은 어느 방향으로 불까요?", o: ["시계방향으로 불어 나간다", "반시계방향으로 불어 들어온다", "항상 북쪽으로만 분다"], a: 1, fb: "저기압은 반시계방향으로 수렴(불어 들어옴)하여 상승기류·구름·비를 만듭니다." },
  { q: "등압선의 간격이 좁을수록(촘촘할수록) 바람은?", o: ["약해진다", "변화 없다", "강해진다"], a: 2, fb: "등압선이 촘촘하면 기압경도력이 커져 바람이 강합니다. 시스템을 가까이 붙여 확인해 보세요." },
  { q: "한여름 한반도에 무더위를 가져오는 기압계는?", o: ["시베리아고기압", "북태평양고기압", "오호츠크해기단"], a: 1, fb: "고온다습한 북태평양고기압이 확장하면 폭염·열대야가 나타납니다." },
  { q: "장마전선(정체전선)은 어떻게 만들어질까요?", o: ["찬 기단과 더운 기단이 만나 힘겨루기할 때", "고기압 하나만 있을 때", "바람이 전혀 없을 때"], a: 0, fb: "성질이 다른 두 기단(북태평양·오호츠크해)이 만나 경계에서 비구름이 집중됩니다." },
  { q: "지구온난화로 해수면 온도가 오르면 태풍은?", o: ["반드시 약해진다", "강한 태풍 비율이 늘 수 있다", "사라진다"], a: 1, fb: "따뜻한 바다는 태풍의 에너지원이라 급강화·강한 태풍 비율이 늘어날 수 있습니다." }
];
let qi = 0, qscore = 0, qansd = false;
function openQuiz() { qi = 0; qscore = 0; $("quizModal").hidden = false; renderQuiz(); }
function renderQuiz() {
  qansd = false;
  const item = QUIZ[qi];
  $("quizQ").textContent = `Q${qi + 1}. ${item.q}`;
  $("quizFb").textContent = "";
  $("quizScore").textContent = `점수 ${qscore} / ${QUIZ.length}`;
  $("quizNext").style.visibility = "hidden";
  const box = $("quizOpts"); box.innerHTML = "";
  item.o.forEach((opt, i) => {
    const b = document.createElement("button"); b.textContent = opt;
    b.onclick = () => {
      if (qansd) return; qansd = true;
      const correct = i === item.a;
      if (correct) { b.classList.add("correct"); qscore++; }
      else { b.classList.add("wrong"); box.children[item.a].classList.add("correct"); }
      $("quizFb").textContent = (correct ? "✅ 정답! " : "❌ ") + item.fb;
      $("quizScore").textContent = `점수 ${qscore} / ${QUIZ.length}`;
      $("quizNext").style.visibility = "visible";
      $("quizNext").textContent = qi < QUIZ.length - 1 ? "다음" : "결과 보기";
    };
    box.appendChild(b);
  });
}
$("quizNext").onclick = () => {
  if (qi < QUIZ.length - 1) { qi++; renderQuiz(); }
  else {
    $("quizQ").textContent = `🎉 완료! ${QUIZ.length}문제 중 ${qscore}개 정답`;
    $("quizOpts").innerHTML = "";
    $("quizFb").textContent = qscore === QUIZ.length ? "완벽합니다! 기상 원리를 정확히 이해했어요." : "지도를 더 조작하며 원리를 체험해 보세요.";
    $("quizNext").style.visibility = "hidden";
  }
};

/* ---------------- 시작 ---------------- */
function init() {
  bind();
  resize();
  loadPreset("summer");   // 첫 화면: 한여름
  cycleCards();
  requestAnimationFrame(frame);
}
init();
})();
