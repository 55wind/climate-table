/* 기후 식탁 — 프론트엔드 (Vanilla JS + Canvas). 백엔드 REST API 연동. */
(() => {
"use strict";
const $ = id => document.getElementById(id);
const API = ""; // 동일 출처(백엔드가 정적 서빙)

const state = {
  item: "배추",
  scenario: { heat_days: 6, heavy_rain_days: 2, drought_idx: 20, cold_days: 0, frost: 0, month: 8 },
  items: [], normals: {}, events: [], series: [], normal: 0, r2: 0,
};

const SLIDERS = [
  { key: "heat_days", label: "폭염일수", unit: "일", min: 0, max: 31, hint: "33℃ 이상 일수" },
  { key: "heavy_rain_days", label: "호우일수", unit: "일", min: 0, max: 12, hint: "집중호우 일수" },
  { key: "drought_idx", label: "가뭄지수", unit: "", min: 0, max: 100, hint: "0=충분 100=극심" },
  { key: "cold_days", label: "한파일수", unit: "일", min: 0, max: 28, hint: "겨울 한파" },
  { key: "frost", label: "개화기 냉해", unit: "", min: 0, max: 100, hint: "봄 저온·서리(사과)" },
  { key: "month", label: "기준 월", unit: "월", min: 1, max: 12, hint: "계절 효과" },
];

// 가계 체감 단위(소매 환산용 대략 중량)
const UNIT_PACK = {
  "배추": { label: "한 포기", kg: 2.5 }, "무": { label: "1개", kg: 1.0 },
  "사과": { label: "1개", kg: 0.3 }, "쌀": { label: "20kg 한 포대", kg: 20 },
  "시금치": { label: "1단", kg: 0.4 }, "양파": { label: "1망(1.5kg)", kg: 1.5 },
};

const PRESETS = [
  { name: "🌡️ 2024 폭염·가뭄 (배추 대란)", s: { heat_days: 28, heavy_rain_days: 3, drought_idx: 75, cold_days: 0, frost: 0, month: 8 } },
  { name: "🌧️ 2020 역대 최장 장마", s: { heat_days: 4, heavy_rain_days: 9, drought_idx: 0, cold_days: 0, frost: 0, month: 7 } },
  { name: "🍎 2023 봄 개화기 냉해 (금사과)", s: { heat_days: 0, heavy_rain_days: 1, drought_idx: 10, cold_days: 0, frost: 70, month: 4 } },
  { name: "❄️ 한겨울 한파", s: { heat_days: 0, heavy_rain_days: 0, drought_idx: 20, cold_days: 20, frost: 0, month: 1 } },
  { name: "🌤️ 평년 (기준)", s: { heat_days: 6, heavy_rain_days: 2, drought_idx: 20, cold_days: 0, frost: 0, month: 8 } },
];

function toast(msg) { const t = $("toast"); t.textContent = msg; t.hidden = false; setTimeout(() => t.hidden = true, 3000); }

async function api(path, opts) {
  const r = await fetch(API + path, opts);
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json();
}

/* ---------- 초기화 ---------- */
async function init() {
  try {
    const h = await api("/api/health");
    $("health").textContent = "● 백엔드 연결됨 (" + h.crops.length + "작물 · " + h.months + "개월)";
    $("health").className = "health ok";
  } catch (e) {
    $("health").textContent = "● 백엔드 미연결 (python backend/app.py 실행 필요)";
    $("health").className = "health bad";
    toast("백엔드에 연결할 수 없습니다. 서버를 실행하세요.");
    return;
  }
  const items = await api("/api/items");
  state.items = items.items; state.normals = items.normals; state.events = items.events;
  buildCrops(); buildSliders(); buildPresets();
  await selectCrop(state.item);
  bindQuiz();
  window.addEventListener("resize", () => drawChart());
}

function buildCrops() {
  const g = $("cropGrid"); g.innerHTML = "";
  for (const it of state.items) {
    const b = document.createElement("button");
    b.innerHTML = `<span class="ico" aria-hidden="true">${it.icon}</span>${it.name}`;
    b.setAttribute("aria-label", it.name + " 선택");
    b.classList.toggle("active", it.name === state.item);
    b.onclick = () => selectCrop(it.name);
    g.appendChild(b);
  }
}
function buildSliders() {
  const c = $("sliders"); c.innerHTML = "";
  for (const sl of SLIDERS) {
    const wrap = document.createElement("div"); wrap.className = "slider";
    wrap.innerHTML = `<div class="lab"><span>${sl.label} <small style="color:#6b7888">${sl.hint}</small></span><b id="v_${sl.key}"></b></div>
      <input type="range" id="s_${sl.key}" min="${sl.min}" max="${sl.max}" step="1" aria-label="${sl.label} (${sl.hint})">`;
    c.appendChild(wrap);
    const input = wrap.querySelector("input");
    input.value = state.scenario[sl.key];
    $("v_" + sl.key).textContent = state.scenario[sl.key] + sl.unit;
    input.oninput = () => {
      state.scenario[sl.key] = +input.value;
      $("v_" + sl.key).textContent = input.value + sl.unit;
      simulate();
    };
  }
}
function buildPresets() {
  const btn = $("presetBtn"), menu = $("presetMenu");
  menu.innerHTML = "";
  for (const p of PRESETS) {
    const b = document.createElement("button"); b.textContent = p.name;
    b.onclick = () => { applyScenario(p.s); menu.hidden = true; };
    menu.appendChild(b);
  }
  btn.onclick = () => menu.hidden = !menu.hidden;
}
function applyScenario(s) {
  state.scenario = Object.assign({}, s);
  for (const sl of SLIDERS) {
    $("s_" + sl.key).value = state.scenario[sl.key];
    $("v_" + sl.key).textContent = state.scenario[sl.key] + sl.unit;
  }
  simulate();
}

/* ---------- 작물 선택 ---------- */
async function selectCrop(name) {
  state.item = name;
  document.querySelectorAll("#cropGrid button").forEach((b, i) =>
    b.classList.toggle("active", state.items[i].name === name));
  const s = await api("/api/series?item=" + encodeURIComponent(name));
  state.series = s.series; state.normal = s.normal; state.r2 = s.r2;
  const corr = await api("/api/correlate?item=" + encodeURIComponent(name));
  renderCorr(corr.correlations);
  await simulate();
}

/* ---------- 시뮬레이션 (디바운스) ---------- */
let simTimer = null, lastPred = null;
function simulate() {
  clearTimeout(simTimer);
  simTimer = setTimeout(doSimulate, 110);
}
async function doSimulate() {
  let res;
  try {
    res = await api("/api/simulate", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.assign({ item: state.item }, state.scenario)),
    });
  } catch (e) { toast("예측 요청 실패"); return; }
  lastPred = res.predicted;
  renderResult(res);
  drawChart();
}

function renderResult(res) {
  const ref = res.baseline != null ? res.baseline : res.normal;
  $("predPrice").textContent = res.predicted.toLocaleString();
  $("predVal").textContent = res.predicted.toLocaleString() + "원";
  $("normalVal").textContent = ref.toLocaleString() + "원";
  const pct = res.explain.pct;
  const badge = $("pctBadge");
  badge.textContent = (pct > 0 ? "+" : "") + pct + "%";
  badge.className = "pct-badge " + (pct >= 0 ? "up" : "down");
  const maxv = Math.max(res.predicted, ref) * 1.05;
  $("barNormal").style.width = (ref / maxv * 100) + "%";
  const pk = UNIT_PACK[state.item];
  $("packPrice").textContent = pk ? `${pk.label} ≈ ${Math.round(res.predicted * pk.kg).toLocaleString()}원` : "";
  $("barPred").style.width = (res.predicted / maxv * 100) + "%";
  $("headline").textContent = res.explain.headline;
  $("drivers").textContent = res.explain.drivers;
  $("note").textContent = res.explain.note;
  const rel = res.reliability || { label: "-", reason: "" };
  $("r2box").innerHTML = `기상 설명력 <b>R² = ${res.r2}</b> · 신뢰도 <b>${rel.label}</b><br><span style="color:#6b7888">${rel.reason}</span>`;
  const ul = $("adapt"); ul.innerHTML = "";
  for (const a of res.adapt) { const li = document.createElement("li"); li.textContent = a; ul.appendChild(li); }
}

function renderCorr(corrs) {
  const c = $("corr"); c.innerHTML = "";
  for (const cr of corrs) {
    const row = document.createElement("div"); row.className = "corr-row";
    const w = Math.abs(cr.r) * 50;
    const side = cr.r >= 0 ? `<i class="pos" style="width:${w}%"></i>` : `<i class="neg" style="width:${w}%"></i>`;
    row.innerHTML = `<div class="ct"><span>${cr.label}</span><span>${cr.r > 0 ? "+" : ""}${cr.r}</span></div>
      <div class="corr-bar"><div class="corr-mid"></div>${side}</div>`;
    c.appendChild(row);
  }
  $("corrNote").textContent = "양(+)의 상관: 값이 클수록 가격↑ (빨강) · 음(−): 가격↓ (파랑)";
}

/* ---------- Canvas 차트 ---------- */
function drawChart() {
  const cv = $("chart"); if (!state.series.length) return;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const w = cv.clientWidth, h = 240;
  cv.width = w * dpr; cv.height = h * dpr;
  const ctx = cv.getContext("2d"); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  const pad = { l: 46, r: 12, t: 12, b: 22 };
  const data = state.series;
  const prices = data.map(d => d.price);
  let lo = Math.min(...prices, state.normal), hi = Math.max(...prices, lastPred || 0);
  lo = Math.floor(lo * 0.9 / 100) * 100; hi = Math.ceil(hi * 1.05 / 100) * 100;
  const X = i => pad.l + i / (data.length - 1) * (w - pad.l - pad.r);
  const Y = v => pad.t + (1 - (v - lo) / (hi - lo)) * (h - pad.t - pad.b);

  // y 그리드
  ctx.font = "10px Pretendard"; ctx.textBaseline = "middle";
  for (let k = 0; k <= 4; k++) {
    const v = lo + (hi - lo) * k / 4, y = Y(v);
    ctx.strokeStyle = "rgba(255,255,255,0.06)"; ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(w - pad.r, y); ctx.stroke();
    ctx.fillStyle = "#6b7888"; ctx.textAlign = "right"; ctx.fillText(Math.round(v).toLocaleString(), pad.l - 6, y);
  }
  // x 연도
  ctx.textAlign = "center";
  data.forEach((d, i) => {
    if (d.month === 1) {
      const x = X(i);
      ctx.fillStyle = "#6b7888"; ctx.fillText(d.date.slice(0, 4), x, h - 8);
      ctx.strokeStyle = "rgba(255,255,255,0.04)"; ctx.beginPath(); ctx.moveTo(x, pad.t); ctx.lineTo(x, h - pad.b); ctx.stroke();
    }
  });
  // 기상 사건 표시
  ctx.textAlign = "center";
  for (const ev of state.events) {
    const idx = data.findIndex(d => d.date === ev.date);
    if (idx < 0) continue;
    const x = X(idx);
    ctx.strokeStyle = "rgba(255,183,77,0.5)"; ctx.setLineDash([3, 3]);
    ctx.beginPath(); ctx.moveTo(x, pad.t); ctx.lineTo(x, h - pad.b); ctx.stroke(); ctx.setLineDash([]);
    ctx.fillStyle = "#ffb74d"; ctx.font = "9px Pretendard";
    ctx.save(); ctx.translate(x, pad.t + 2); ctx.fillText("▼", 0, 0); ctx.restore();
  }
  // 평년선
  ctx.strokeStyle = "rgba(154,167,182,0.5)"; ctx.setLineDash([5, 4]);
  ctx.beginPath(); ctx.moveTo(pad.l, Y(state.normal)); ctx.lineTo(w - pad.r, Y(state.normal)); ctx.stroke(); ctx.setLineDash([]);
  // 가격선
  ctx.strokeStyle = "#4fa9ff"; ctx.lineWidth = 1.8; ctx.beginPath();
  data.forEach((d, i) => { const x = X(i), y = Y(d.price); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
  ctx.stroke();
  // 현재 예측선
  if (lastPred != null) {
    ctx.strokeStyle = "#ff6b5b"; ctx.lineWidth = 1.4; ctx.setLineDash([6, 3]);
    ctx.beginPath(); ctx.moveTo(pad.l, Y(lastPred)); ctx.lineTo(w - pad.r, Y(lastPred)); ctx.stroke(); ctx.setLineDash([]);
    ctx.fillStyle = "#ff6b5b"; ctx.textAlign = "left"; ctx.font = "10px Pretendard";
    ctx.fillText("예측 " + lastPred.toLocaleString() + "원", pad.l + 4, Y(lastPred) - 6);
  }
}

/* ---------- 퀴즈 ---------- */
let QUIZ = [], qi = 0, qscore = 0, qansd = false;
async function bindQuiz() {
  $("quizBtn").onclick = async () => {
    if (!QUIZ.length) { try { QUIZ = (await api("/api/quiz")).quiz; } catch (e) { toast("퀴즈 로드 실패"); return; } }
    qi = 0; qscore = 0; $("quizModal").hidden = false; renderQuiz();
  };
  $("quizClose").onclick = () => $("quizModal").hidden = true;
  $("quizNext").onclick = () => {
    if (qi < QUIZ.length - 1) { qi++; renderQuiz(); }
    else {
      $("quizQ").textContent = `🎉 완료! ${QUIZ.length}문제 중 ${qscore}개 정답`;
      $("quizOpts").innerHTML = ""; $("quizFb").textContent = qscore === QUIZ.length ? "완벽합니다! 기후플레이션을 정확히 이해했어요." : "시나리오를 더 조작하며 원리를 체험해 보세요.";
      $("quizNext").style.visibility = "hidden";
    }
  };
}
function renderQuiz() {
  qansd = false; const item = QUIZ[qi];
  $("quizQ").textContent = `Q${qi + 1}. ${item.q}`;
  $("quizFb").textContent = ""; $("quizScore").textContent = `점수 ${qscore} / ${QUIZ.length}`;
  $("quizNext").style.visibility = "hidden"; $("quizNext").textContent = qi < QUIZ.length - 1 ? "다음" : "결과 보기";
  const box = $("quizOpts"); box.innerHTML = "";
  item.o.forEach((opt, i) => {
    const b = document.createElement("button"); b.textContent = opt;
    b.onclick = () => {
      if (qansd) return; qansd = true;
      const ok = i === item.a;
      if (ok) { b.classList.add("correct"); qscore++; } else { b.classList.add("wrong"); box.children[item.a].classList.add("correct"); }
      $("quizFb").textContent = (ok ? "✅ 정답! " : "❌ ") + item.fb;
      $("quizScore").textContent = `점수 ${qscore} / ${QUIZ.length}`;
      $("quizNext").style.visibility = "visible";
    };
    box.appendChild(b);
  });
}

init();
})();
