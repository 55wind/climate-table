/* 기후 식탁 — 프론트엔드 (Vanilla JS + Canvas). 백엔드 REST API 연동. */
(() => {
"use strict";
const $ = id => document.getElementById(id);
const API = ""; // 동일 출처(백엔드가 정적 서빙)

const state = {
  item: "배추",
  scenario: { heat_days: 0, heavy_rain_days: 0, drought_idx: 20, cold_days: 0, frost: 0, month: 8 },
  items: [], normals: {}, events: [], series: [], normal: 0, r2: 0,
  dishes: [], meal: [],
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

// 남한 단순화 외곽선 [경도,위도] + 제주
const SK_OUTLINE = [
  [126.55, 37.75], [126.40, 37.0], [126.50, 36.6], [126.30, 36.0], [126.50, 35.6],
  [126.30, 35.0], [126.45, 34.6], [126.9, 34.4], [127.5, 34.5], [127.8, 34.75],
  [128.4, 34.85], [128.7, 35.0], [129.1, 35.1], [129.45, 35.6], [129.5, 36.05],
  [129.4, 36.6], [129.1, 37.2], [128.9, 37.75], [128.6, 38.25], [128.4, 38.55],
  [128.0, 38.35], [127.3, 38.30], [126.9, 38.10], [126.55, 37.95], [126.55, 37.75]
];
const SK_JEJU = { lon: 126.5, lat: 33.4, r: 0.42 };
const SK_DOMAIN = { lonMin: 125.7, lonMax: 130.0, latMin: 32.9, latMax: 38.9 };
// 작물별 주요 산지: {name, lon, lat, w(상대 민감도·비중)}
const CROP_REGIONS = {
  "배추": [{ n: "강원 고랭지", lon: 128.4, lat: 37.6, w: 1.3 }, { n: "전남 해남", lon: 126.6, lat: 34.6, w: 1.0 }, { n: "충북", lon: 127.6, lat: 36.8, w: 0.9 }, { n: "경북", lon: 128.7, lat: 36.4, w: 0.85 }],
  "무": [{ n: "강원", lon: 128.4, lat: 37.6, w: 1.2 }, { n: "제주", lon: 126.55, lat: 33.4, w: 1.1 }, { n: "전남", lon: 126.8, lat: 34.8, w: 1.0 }],
  "사과": [{ n: "경북 청송", lon: 129.0, lat: 36.4, w: 1.25 }, { n: "충북 충주", lon: 127.9, lat: 37.0, w: 1.0 }, { n: "경남 거창", lon: 127.9, lat: 35.7, w: 0.9 }, { n: "강원(신규)", lon: 128.4, lat: 37.7, w: 0.7 }],
  "쌀": [{ n: "전북", lon: 127.0, lat: 35.8, w: 1.0 }, { n: "충남", lon: 126.9, lat: 36.5, w: 1.0 }, { n: "전남", lon: 126.9, lat: 34.95, w: 1.0 }],
  "시금치": [{ n: "경남 남해", lon: 127.9, lat: 34.85, w: 1.1 }, { n: "전남 신안", lon: 126.4, lat: 34.8, w: 1.0 }, { n: "경북 포항", lon: 129.3, lat: 36.0, w: 1.0 }],
  "양파": [{ n: "전남 무안", lon: 126.5, lat: 34.95, w: 1.2 }, { n: "경남 창녕", lon: 128.5, lat: 35.5, w: 1.1 }, { n: "제주", lon: 126.55, lat: 33.4, w: 0.85 }],
};

const PRESETS = [
  { name: "2024 폭염·가뭄 (배추 대란)", s: { heat_days: 28, heavy_rain_days: 3, drought_idx: 75, cold_days: 0, frost: 0, month: 8 } },
  { name: "2020 역대 최장 장마", s: { heat_days: 4, heavy_rain_days: 9, drought_idx: 0, cold_days: 0, frost: 0, month: 7 } },
  { name: "2023 봄 개화기 냉해 (금사과)", s: { heat_days: 0, heavy_rain_days: 1, drought_idx: 10, cold_days: 0, frost: 70, month: 4 } },
  { name: "한겨울 한파", s: { heat_days: 0, heavy_rain_days: 0, drought_idx: 20, cold_days: 20, frost: 0, month: 1 } },
  { name: "평년 (기준)", s: { heat_days: 0, heavy_rain_days: 0, drought_idx: 20, cold_days: 0, frost: 0, month: 8 } },
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
    $("health").textContent = "● 연결됨 · " + h.crops.length + "작물 " + h.months + "개월";
    $("health").title = "데이터 출처: " + (h.source || "보정 데이터");
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
  setupTabs(); setupQuiz();
  await loadDishes(); buildTray(); buildMealPresets(); setupMealTable();
  renderMeal(null); updateWeatherBadge();
  // 온보딩 배너: 1회 노출(이전에 닫았으면 숨김)
  const ob = $("onboard");
  if (ob) {
    if (localStorage.getItem("ct_onboard_done")) ob.style.display = "none";
    $("onboardClose").onclick = () => { ob.style.display = "none"; try { localStorage.setItem("ct_onboard_done", "1"); } catch (e) {} };
  }
  window.addEventListener("resize", () => { drawChart(); drawMap(lastPct); });
}

/* ---------- 밥상 차리기 ---------- */
async function loadDishes() {
  try {
    const r = await api("/api/dishes");
    state.dishes = r.dishes || [];
  } catch (e) { state.dishes = []; }
}
function dishById(id) { return state.dishes.find(d => d.id === id); }

// 상차림 고정 자리 (식탁 위 %좌표). 뒷줄=반찬, 앞줄=밥·국, 가운데=메인.
const MEAL_SLOTS = {
  baechu_kimchi:   { x: 22, y: 30 },
  mu_saengchae:    { x: 41, y: 25 },
  sigeumchi_namul: { x: 59, y: 25 },
  yangpa_jangajji: { x: 78, y: 30 },
  jeyuk_bokkeum:   { x: 50, y: 50 },
  rice:            { x: 26, y: 74 },
  kimchi_jjigae:   { x: 50, y: 78 },
  doenjang_jjigae: { x: 74, y: 74 },
};
function slotFor(id) { return MEAL_SLOTS[id] || { x: 50, y: 50 }; }

function foodMedia(dish) {
  // 이미지 우선, 실패 시 이모지 폴백
  return `<img class="food-img" src="/assets/foods/${dish.img}" alt="${dish.name}"
    onerror="this.outerHTML='<span class=\\'food-emoji\\'>${dish.emoji}</span>'">`;
}

function buildTray() {
  const tray = $("mealTray"); if (!tray) return;
  tray.innerHTML = "";
  for (const d of state.dishes) {
    const card = document.createElement("div");
    card.className = "tray-card";
    card.dataset.id = d.id;
    card.innerHTML = `${foodMedia(d)}<div class="food-name">${d.name}</div>`;
    card.title = d.name + " (눌러서 올리기/빼기)";
    card.addEventListener("click", () => toggleDish(d.id));
    tray.appendChild(card);
  }
}

function buildMealPresets() {
  const box = $("mealPresets"); if (!box) return;
  box.innerHTML = "";
  PRESETS.forEach((p, i) => {
    const b = document.createElement("button"); b.type = "button"; b.textContent = p.name;
    b.onclick = () => {
      applyScenario(p.s);           // 기존 시뮬과 동일하게 시나리오 공유·갱신
      Array.from(box.children).forEach((x, j) => x.classList.toggle("active", j === i));
      refreshMeal();
    };
    box.appendChild(b);
  });
}

function setupMealTable() {
  const clear = $("mealClear");
  if (clear) clear.onclick = () => { state.meal = []; renderPlates(); simulateMeal(); };
}

// 클릭=토글. 이미 올라가 있으면 빼고, 없으면 고정 자리에 올린다(중복 불가).
function toggleDish(id) {
  if (!dishById(id)) return;
  const i = state.meal.indexOf(id);
  if (i >= 0) state.meal.splice(i, 1);
  else state.meal.push(id);
  renderPlates(); simulateMeal();
}
function renderPlates() {
  const wrap = $("mealPlates"); if (!wrap) return;
  wrap.innerHTML = "";
  for (const id of state.meal) {
    const d = dishById(id); if (!d) continue;
    const pos = slotFor(id);
    const el = document.createElement("div");
    el.className = "plate";
    el.style.left = pos.x + "%"; el.style.top = pos.y + "%";
    el.innerHTML = `${foodMedia(d)}<div class="plate-name">${d.name}</div>`;
    el.title = d.name + " (클릭 시 빼기)";
    el.onclick = () => toggleDish(id);
    wrap.appendChild(el);
  }
  // 트레이 선택 표시 동기화
  const tray = $("mealTray");
  if (tray) Array.from(tray.children).forEach(c =>
    c.classList.toggle("on", state.meal.indexOf(c.dataset.id) >= 0));
  const hint = $("mealHint"); if (hint) hint.style.display = state.meal.length ? "none" : "";
}

let mealTimer = null;
function simulateMeal() {
  clearTimeout(mealTimer);
  mealTimer = setTimeout(doSimulateMeal, 110);
}
async function doSimulateMeal() {
  const ids = state.meal.slice();
  let res;
  try {
    res = await api("/api/meal", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scenario: state.scenario, month: state.scenario.month, dishes: ids }),
    });
  } catch (e) { toast("밥상 계산 실패"); return; }
  renderMeal(res);
}

function updateWeatherBadge() {
  const b = $("mealWeatherBadge"); if (!b) return;
  const s = state.scenario;
  const on = [];
  if (s.heat_days >= 10) on.push("폭염");
  if (s.drought_idx >= 50) on.push("가뭄");
  if (s.heavy_rain_days >= 6) on.push("호우");
  if (s.cold_days >= 10) on.push("한파");
  if (s.frost >= 40) on.push("냉해");
  b.textContent = "현재 날씨 · " + (on.length ? on.join("·") : "평년 수준") + ` (${s.month}월)`;
}

// 받침 유무로 주격조사 이/가 선택
function gaParticle(w) {
  if (!w) return "가";
  const c = w.charCodeAt(w.length - 1);
  const hasBatchim = c >= 0xAC00 && c <= 0xD7A3 && ((c - 0xAC00) % 28) !== 0;
  return hasBatchim ? "이" : "가";
}
function renderMeal(res) {
  updateWeatherBadge();
  const box = $("mealResult"); if (!box) return;
  if (!res || !res.dishes || !res.dishes.length) {
    box.innerHTML = `<p class="meal-empty">식탁이 비었습니다. 위 음식을 눌러 올려 보세요.</p>`;
    return;
  }
  const cost = res.total.cost, eat = res.total.eatout;
  const sign = p => (p > 0 ? "+" : "") + p + "%";
  const top = res.ingredientTotals[0];
  const insight = top && cost.pct > 0
    ? `이 날씨에서 <b>${top.crop}</b>${gaParticle(top.crop)} 평년比 <b>+${top.pct}%</b>로 밥상값을 가장 많이 끌어올렸습니다.`
    : (cost.pct > 0 ? "기상 영향으로 밥상값이 소폭 올랐습니다." : "평년 날씨와 비슷한 수준입니다.");
  const dishRows = res.dishes.map(d =>
    `<div class="dish-row"><span class="dr-name">${d.name}<span class="dr-pct">${d.cost.pct > 0 ? "+" + d.cost.pct + "%" : ""}</span></span>
       <span class="dr-price">원가 ${d.cost.predicted.toLocaleString()} · 외식 ${d.eatout.predicted.toLocaleString()}원</span></div>`).join("");
  const maxDelta = Math.max(1, ...res.ingredientTotals.map(i => i.predicted - i.baseline));
  const ingBars = res.ingredientTotals.map(i => {
    const w = Math.max(3, (i.predicted - i.baseline) / maxDelta * 100);
    const up = i.unitPrice;
    return `<div class="ing-bar"><div class="ib-top">
        <span>${i.crop} <small style="color:#86868b">1${i.unit} ${up.predicted.toLocaleString()}원 (평년 ${up.baseline.toLocaleString()})</small></span>
        <b>${sign(i.pct)}</b></div>
        <div class="ib-track"><div class="ib-fill" style="width:${w}%"></div></div></div>`;
  }).join("");
  box.innerHTML = `
    <div class="meal-totals">
      <div class="meal-total">
        <div><span class="mt-label">재료 원가 (집에서 해먹을 때)</span>
          <div class="mt-num">${cost.predicted.toLocaleString()}<small>원</small></div></div>
        <div class="mt-pct ${cost.pct >= 0 ? "up" : "down"}">${sign(cost.pct)}</div>
      </div>
      <div class="meal-total sub">
        <div><span class="mt-label">사먹을 때 (외식)</span>
          <div class="mt-num">${eat.predicted.toLocaleString()}<small>원</small></div></div>
        <div class="mt-pct ${eat.pct >= 0 ? "up" : "down"}">${sign(eat.pct)}</div>
      </div>
    </div>
    <p class="meal-insight">${insight} 평년이라면 재료 원가 약 ${cost.baseline.toLocaleString()}원 · 외식 ${eat.baseline.toLocaleString()}원입니다.</p>
    <div class="meal-section-label">음식별 (원가 · 외식)</div>
    <div class="dish-list">${dishRows}</div>
    <div class="meal-section-label">원자재(기후 작물) 가격 영향 · 구매단위 기준</div>
    <div class="ing-bars">${ingBars || '<p class="meal-empty">기후 작물 재료가 없습니다.</p>'}</div>`;
}

function refreshMeal() {
  updateWeatherBadge();
  if (state.meal.length) simulateMeal();
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
    wrap.innerHTML = `<div class="lab"><span>${sl.label} <small style="color:#86868b">${sl.hint}</small></span><b id="v_${sl.key}"></b></div>
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
  const menu = $("presetMenu");
  menu.innerHTML = "";
  for (const p of PRESETS) {
    const b = document.createElement("button"); b.type = "button"; b.textContent = p.name;
    b.onclick = () => applyScenario(p.s);
    menu.appendChild(b);
  }
  const reset = $("resetBtn");
  if (reset) reset.onclick = () => applyScenario(PRESETS[PRESETS.length - 1].s); // 평년(기준)
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
let simTimer = null, lastPred = null, lastPct = 0;
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
  lastPct = res.explain.pct;
  renderResult(res);
  drawChart();
  drawMap(lastPct);
  refreshMeal();
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
  $("r2box").innerHTML = `기상 설명력 <b>R² = ${res.r2}</b> · 신뢰도 <b>${rel.label}</b><br><span style="color:#86868b">${rel.reason}</span>`;
  const ul = $("adapt"); ul.innerHTML = "";
  for (const a of res.adapt) { const li = document.createElement("li"); li.textContent = a; ul.appendChild(li); }
  // 상태 가시성: 결과 갱신을 잠깐 강조
  const card = $("resultCard");
  card.classList.remove("flash"); void card.offsetWidth; card.classList.add("flash");
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
  ctx.font = "10px Inter, Pretendard"; ctx.textBaseline = "middle";
  for (let k = 0; k <= 4; k++) {
    const v = lo + (hi - lo) * k / 4, y = Y(v);
    ctx.strokeStyle = "rgba(0,0,0,0.06)"; ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(w - pad.r, y); ctx.stroke();
    ctx.fillStyle = "#86868b"; ctx.textAlign = "right"; ctx.fillText(Math.round(v).toLocaleString(), pad.l - 6, y);
  }
  // x 연도
  ctx.textAlign = "center";
  data.forEach((d, i) => {
    if (d.month === 1) {
      const x = X(i);
      ctx.fillStyle = "#86868b"; ctx.fillText(d.date.slice(0, 4), x, h - 8);
      ctx.strokeStyle = "rgba(0,0,0,0.04)"; ctx.beginPath(); ctx.moveTo(x, pad.t); ctx.lineTo(x, h - pad.b); ctx.stroke();
    }
  });
  // 기상 사건 표시
  ctx.textAlign = "center";
  for (const ev of state.events) {
    const idx = data.findIndex(d => d.date === ev.date);
    if (idx < 0) continue;
    const x = X(idx);
    ctx.strokeStyle = "rgba(0,0,0,0.12)"; ctx.setLineDash([3, 3]);
    ctx.beginPath(); ctx.moveTo(x, pad.t); ctx.lineTo(x, h - pad.b); ctx.stroke(); ctx.setLineDash([]);
    ctx.fillStyle = "#86868b"; ctx.font = "9px Inter, Pretendard";
    ctx.save(); ctx.translate(x, pad.t + 2); ctx.fillText("▼", 0, 0); ctx.restore();
  }
  // 평년선
  ctx.strokeStyle = "rgba(0,0,0,0.22)"; ctx.setLineDash([5, 4]);
  ctx.beginPath(); ctx.moveTo(pad.l, Y(state.normal)); ctx.lineTo(w - pad.r, Y(state.normal)); ctx.stroke(); ctx.setLineDash([]);
  // 가격선
  ctx.strokeStyle = "#1d1d1f"; ctx.lineWidth = 1.8; ctx.beginPath();
  data.forEach((d, i) => { const x = X(i), y = Y(d.price); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
  ctx.stroke();
  // 현재 예측선
  if (lastPred != null) {
    ctx.strokeStyle = "#0066cc"; ctx.lineWidth = 1.6; ctx.setLineDash([6, 3]);
    ctx.beginPath(); ctx.moveTo(pad.l, Y(lastPred)); ctx.lineTo(w - pad.r, Y(lastPred)); ctx.stroke(); ctx.setLineDash([]);
    ctx.fillStyle = "#0066cc"; ctx.textAlign = "left"; ctx.font = "700 10px Inter, Pretendard";
    ctx.fillText("예측 " + lastPred.toLocaleString() + "원", pad.l + 4, Y(lastPred) - 6);
  }
}

/* ---------- 지역별 영향 지도 (Canvas, 세팅값 반응) ---------- */
function drawMap(pct) {
  const cv = $("mapCanvas"); if (!cv) return;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const w = cv.clientWidth, h = 320;
  cv.width = w * dpr; cv.height = h * dpr;
  const ctx = cv.getContext("2d"); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  const D = SK_DOMAIN, pad = 12;
  const lonSpan = (D.lonMax - D.lonMin) * Math.cos(36 * Math.PI / 180), latSpan = D.latMax - D.latMin;
  const sc = Math.min((w - pad * 2) / lonSpan, (h - pad * 2) / latSpan);
  const cxp = w / 2, cyp = h / 2, midLon = (D.lonMin + D.lonMax) / 2, midLat = (D.latMin + D.latMax) / 2, cosM = Math.cos(36 * Math.PI / 180);
  const P = (lon, lat) => [cxp + (lon - midLon) * cosM * sc, cyp - (lat - midLat) * sc];
  // 외곽선
  ctx.beginPath();
  SK_OUTLINE.forEach((p, i) => { const [x, y] = P(p[0], p[1]); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
  ctx.closePath();
  ctx.fillStyle = "#eceae3"; ctx.fill();
  ctx.strokeStyle = "#cfcabd"; ctx.lineWidth = 1; ctx.stroke();
  // 제주
  const [jx, jy] = P(SK_JEJU.lon, SK_JEJU.lat);
  ctx.beginPath(); ctx.ellipse(jx, jy, SK_JEJU.r * cosM * sc, SK_JEJU.r * sc * 0.7, 0, 0, 7);
  ctx.fillStyle = "#eceae3"; ctx.fill(); ctx.stroke();
  // 산지 점 계산
  const regions = CROP_REGIONS[state.item] || [];
  const pts = regions.map(r => {
    const [x, y] = P(r.lon, r.lat);
    const impact = Math.max(0, pct) * r.w;
    const rad = 7 + r.w * 4 + Math.min(9, Math.max(0, pct) / 80 * 9);
    return { r, x0: x, y0: y, x, y, rad, impact };
  });
  // 겹침 분리(반발 + 원위치 스프링)
  for (let it = 0; it < 90; it++) {
    for (let i = 0; i < pts.length; i++) for (let j = i + 1; j < pts.length; j++) {
      const a = pts[i], b = pts[j];
      const dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy) || 0.01, min = a.rad + b.rad + 16;
      if (d < min) { const push = (min - d) / 2, ux = dx / d, uy = dy / d; a.x -= ux * push; a.y -= uy * push; b.x += ux * push; b.y += uy * push; }
    }
    for (const p of pts) {
      p.x += (p.x0 - p.x) * 0.03; p.y += (p.y0 - p.y) * 0.03;
      p.x = Math.max(p.rad + 20, Math.min(w - p.rad - 20, p.x));
      p.y = Math.max(p.rad + 16, Math.min(h - p.rad - 24, p.y));
    }
  }
  // 그리기 (연결선 → 원 → 라벨)
  ctx.textAlign = "center";
  for (const p of pts) {
    if (Math.hypot(p.x - p.x0, p.y - p.y0) > 3) {
      ctx.strokeStyle = "rgba(0,0,0,0.18)"; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(p.x0, p.y0); ctx.lineTo(p.x, p.y); ctx.stroke();
      ctx.fillStyle = "rgba(0,0,0,0.4)"; ctx.beginPath(); ctx.arc(p.x0, p.y0, 2, 0, 7); ctx.fill();
    }
  }
  for (const p of pts) {
    const alpha = Math.min(0.82, 0.1 + p.impact / 80 * 0.72);
    ctx.beginPath(); ctx.arc(p.x, p.y, p.rad, 0, 7);
    ctx.fillStyle = pct >= 0 ? `rgba(0,102,204,${alpha})` : "rgba(134,134,139,0.22)"; ctx.fill();
    ctx.lineWidth = 1.2; ctx.strokeStyle = pct >= 0 ? "rgba(0,102,204,0.9)" : "rgba(134,134,139,0.7)"; ctx.stroke();
    ctx.fillStyle = "#1d1d1f"; ctx.font = "600 11px Inter, Pretendard"; ctx.fillText(p.r.n, p.x, p.y - p.rad - 5);
    ctx.fillStyle = pct >= 0 ? "#0066cc" : "#86868b"; ctx.font = "700 11px Inter, Pretendard"; ctx.fillText((pct > 0 ? "+" : "") + Math.round(p.impact) + "%", p.x, p.y + 4);
  }
  // 범례
  ctx.textAlign = "left"; ctx.fillStyle = "#86868b"; ctx.font = "11px Inter, Pretendard";
  ctx.fillText(state.item + " 주요 산지 · 가격 상승 압력", pad + 2, h - 8);
}

/* ---------- 탭 전환 ---------- */
let goSim = null;
function setupTabs() {
  const views = { sim: $("viewSim"), meal: $("viewMeal"), quiz: $("viewQuiz") };
  const tabs = { sim: $("tabSim"), meal: $("tabMeal"), quiz: $("tabQuiz") };
  const show = which => {
    for (const k of Object.keys(views)) {
      if (views[k]) views[k].hidden = k !== which;
      if (tabs[k]) {
        tabs[k].classList.toggle("active", k === which);
        tabs[k].setAttribute("aria-selected", String(k === which));
      }
    }
    window.scrollTo(0, 0);
  };
  tabs.sim.onclick = () => show("sim");
  tabs.meal.onclick = () => { show("meal"); refreshMeal(); };
  tabs.quiz.onclick = () => { show("quiz"); ensureQuiz(); };
  goSim = () => show("sim");
}

/* ---------- 학습 퀴즈 (탭·진행률·영역별 채점·예측 챌린지) ---------- */
const CHALLENGE = {
  type: "challenge", cat: "예측", item: "배추",
  scenario: { heat_days: 28, drought_idx: 78, heavy_rain_days: 3, cold_days: 0, frost: 0, month: 9 },
  q: "예측 챌린지 — 2024년 여름 폭염 시나리오(폭염 28일·가뭄 78)에서 배추 도매가는 같은 시기 평년 대비 얼마나 오를까요?",
  o: ["거의 변화 없음 (±5%)", "+10~20% 안팎", "+40% 이상"], a: 2,
  fb: "폭염·가뭄이 고랭지 배추 작황을 무너뜨려 큰 폭으로 오릅니다."
};
let allQuiz = [], QUIZ = [], qi = 0, qscore = 0, qansd = false, catStats = {}, selectedCat = "전체", quizLoaded = false;

function setupQuiz() {
  $("qBegin").onclick = startQuiz;
  $("qNext").onclick = nextQuiz;
}
async function ensureQuiz() {
  if (quizLoaded) return true;
  try { allQuiz = (await api("/api/quiz")).quiz; } catch (e) { toast("퀴즈를 불러오지 못했습니다"); return false; }
  quizLoaded = true; buildCatChips(); return true;
}
function buildCatChips() {
  const cats = ["전체"].concat(Array.from(new Set(allQuiz.map(q => q.cat))));
  const box = $("qCatSel"); box.innerHTML = "";
  cats.forEach(c => {
    const b = document.createElement("button"); b.type = "button";
    b.className = "qchip" + (c === selectedCat ? " active" : ""); b.textContent = c;
    b.onclick = () => { selectedCat = c; Array.from(box.children).forEach(x => x.classList.toggle("active", x.textContent === c)); };
    box.appendChild(b);
  });
}
function shuffle(a) { for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; }
async function startQuiz() {
  if (!(await ensureQuiz())) return;
  const pool = selectedCat === "전체" ? allQuiz.slice() : allQuiz.filter(q => q.cat === selectedCat);
  QUIZ = shuffle(pool).concat([CHALLENGE]);
  qi = 0; qscore = 0; catStats = {};
  $("qStart").hidden = true; $("qResult").hidden = true; $("qStage").hidden = false;
  renderQ();
}
function backToStart() { $("qStage").hidden = true; $("qResult").hidden = true; $("qStart").hidden = false; }
function renderQ() {
  qansd = false;
  const item = QUIZ[qi], n = QUIZ.length;
  $("qBar").style.width = (qi / n * 100) + "%";
  $("qCount").textContent = `${qi + 1} / ${n}`;
  $("qScore").textContent = `정답 ${qscore}개`;
  $("qCat").textContent = item.cat || "개념";
  $("qQ").textContent = item.q;
  $("qFb").textContent = ""; $("qFb").className = "qfb";
  $("qNext").style.visibility = "hidden";
  $("qNext").textContent = qi < n - 1 ? "다음 문항" : "결과 보기";
  const box = $("qOpts"); box.innerHTML = "";
  item.o.forEach((opt, i) => {
    const b = document.createElement("button"); b.type = "button"; b.textContent = opt;
    b.onclick = () => answer(item, i, b, box);
    box.appendChild(b);
  });
  if (item.type === "challenge") fetchChallenge(item);
}
async function fetchChallenge(item) {
  try {
    item._real = await api("/api/simulate", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.assign({ item: item.item }, item.scenario)) });
  } catch (e) { /* 기본 해설 사용 */ }
}
function answer(item, i, btn, box) {
  if (qansd) return; qansd = true;
  const ok = i === item.a, cat = item.cat || "개념";
  catStats[cat] = catStats[cat] || { c: 0, t: 0 }; catStats[cat].t++;
  if (ok) { btn.classList.add("correct"); qscore++; catStats[cat].c++; }
  else { btn.classList.add("wrong"); box.children[item.a].classList.add("correct"); }
  let fb = (ok ? "정답입니다. " : "아쉬워요. ") + item.fb;
  if (item.type === "challenge" && item._real) fb += ` 모델 예측: 평년 대비 +${item._real.explain.pct}% (${item._real.predicted.toLocaleString()}원/kg).`;
  $("qFb").textContent = fb; $("qFb").className = "qfb " + (ok ? "ok" : "no");
  $("qScore").textContent = `정답 ${qscore}개`;
  $("qBar").style.width = ((qi + 1) / QUIZ.length * 100) + "%";
  $("qNext").style.visibility = "visible";
}
function nextQuiz() { if (qi < QUIZ.length - 1) { qi++; renderQ(); } else showResult(); }
function showResult() {
  $("qStage").hidden = true;
  const n = QUIZ.length, pct = Math.round(qscore / n * 100);
  let grade, msg;
  if (pct >= 90) { grade = "기후 식탁 마스터"; msg = "완벽에 가깝습니다. 기후플레이션을 정확히 이해했어요."; }
  else if (pct >= 70) { grade = "우수"; msg = "잘하셨어요. 약한 영역만 복습하면 완벽합니다."; }
  else if (pct >= 50) { grade = "보통"; msg = "기본기는 갖췄어요. 시뮬레이터로 사례를 더 체험해 보세요."; }
  else { grade = "복습 필요"; msg = "시뮬레이터에서 폭염·냉해 시나리오를 직접 돌려보며 원리를 익혀 보세요."; }
  const cats = Object.keys(catStats).map(k =>
    `<div class="qres-cat"><span>${k}</span><b>${catStats[k].c}/${catStats[k].t}</b></div>`).join("");
  $("qResult").innerHTML =
    `<span class="qkicker">결과</span>
     <div class="qres-score"><span class="qres-num">${qscore}<small>/${n}</small></span><span class="qres-grade">${grade}</span></div>
     <div class="qres-bar"><div style="width:${pct}%"></div></div>
     <p class="qres-msg">${msg}</p>
     <div class="qres-cats">${cats}</div>
     <div class="qres-actions"><button id="qRetry" class="primary" type="button">다시 풀기</button><button id="qGoSim" class="ghost" type="button">시뮬레이터에서 확인</button></div>`;
  $("qResult").hidden = false;
  $("qRetry").innerHTML = "다른 분야 풀기"; $("qRetry").onclick = backToStart;
  $("qGoSim").onclick = () => goSim && goSim();
}

init();
})();
