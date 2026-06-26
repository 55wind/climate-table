# 밥상 차리기 시뮬레이션 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 음식을 드래그&드롭으로 식탁에 올리면 재료(원자재)별 날씨 기반 물가상승률과 밥상 총액을 계산해 보여주는 새 탭을 추가한다.

**Architecture:** 백엔드(Python 표준 라이브러리)에 음식 레시피 데이터 모듈과 `/api/dishes`·`/api/meal` 엔드포인트를 추가하고, 가격은 기존 `ClimateModel`을 6종 작물에 재사용해 계산한다. 프론트엔드(Vanilla JS IIFE)에 세 번째 탭 "밥상 차리기"를 추가하고 기존 `state.scenario`(날씨)를 공유해 같은 기후에서 밥상값을 계산한다.

**Tech Stack:** Python `http.server`(의존성 0), Vanilla JS + HTML5 Drag and Drop + Canvas 없음(이미지/DOM), 3D 일러스트 PNG 에셋(로컬 번들).

## Global Constraints

- 외부 런타임 의존성 0 — 표준 라이브러리만, CDN 신규 추가 금지(에셋은 로컬 번들). (verbatim: "외부 패키지·설치가 전혀 필요 없습니다")
- 기존 시뮬레이션·퀴즈 탭 동작은 변경 금지(비파괴적 추가).
- 재료비 환산 관례: **예측 도매가(원/kg) × 분량(kg)**, 소매 마진 미적용(기존 앱과 통일).
- 기후 작물은 6종만: 배추·무·사과·쌀·시금치·양파.
- 평년 기준 = `BASELINE`(app.py): `{"heat_days":0,"cold_days":0,"heavy_rain_days":0,"drought_idx":20,"frost":0}`.
- 들여쓰기: Python 4-space, JS/CSS/HTML 2-space(기존 파일 관례).
- 모든 백엔드 검증은 `python backend/test_api.py`로 수행(별도 테스트 러너 없음). 프론트는 수동 브라우저 검증.

## File Structure

- Create: `backend/dishes.py` — 음식 카탈로그(레시피·정가) 순수 데이터 + 조회 함수.
- Modify: `backend/app.py` — `/api/dishes`(GET), `/api/meal`(POST) 추가, `do_POST` 디스패치 분리.
- Modify: `backend/test_api.py` — dishes/meal 검증 케이스 추가.
- Create: `frontend/assets/foods/<id>.png` (8개), `frontend/assets/table.png` — 3D 투명 PNG.
- Create: `frontend/assets/CREDITS.md` — 에셋 출처·라이선스.
- Modify: `frontend/index.html` — 탭 버튼 + `#viewMeal` 뷰 마크업.
- Modify: `frontend/style.css` — 밥상 탭 스타일.
- Modify: `frontend/app.js` — 음식 로드·트레이·드래그/드롭·결과 렌더·날씨 공유.

---

## Task 1: 음식 카탈로그 데이터 + `GET /api/dishes`

**Files:**
- Create: `backend/dishes.py`
- Modify: `backend/app.py` (import + GET 라우트, do_GET 내부 ~line 159 부근)
- Test: `backend/test_api.py` (run_checks 내 추가)

**Interfaces:**
- Produces: `dishes.DISHES` (list), `dishes.by_id(did) -> dict|None`, `dishes.CROPS` (set).
- Produces: HTTP `GET /api/dishes` → `{"dishes": [ {id,name,img,emoji,ingredients:[...]} ]}`.

- [ ] **Step 1: Write `backend/dishes.py`**

```python
# -*- coding: utf-8 -*-
"""밥상 차리기 — 음식 카탈로그(레시피·정가). 순수 데이터, 모델 의존 없음.

기후 재료(kind="crop")는 6종 작물 중 하나로 분량(amount_kg)을 가지며
가격은 ClimateModel로 날씨에 따라 계산된다.
고정 재료(kind="fixed")는 정가(won)로 날씨와 무관하다.
분량·정가는 교육용 1인분 근사값이며 이 파일 한 곳에서 조정한다.
"""

CROPS = {"배추", "무", "사과", "쌀", "시금치", "양파"}

DISHES = [
    {"id": "rice", "name": "공기밥", "img": "rice.png", "emoji": "🍚",
     "ingredients": [
         {"name": "쌀", "kind": "crop", "crop": "쌀", "amount_kg": 0.10},
     ]},
    {"id": "kimchi_jjigae", "name": "김치찌개", "img": "kimchi_jjigae.png", "emoji": "🥘",
     "ingredients": [
         {"name": "배추", "kind": "crop", "crop": "배추", "amount_kg": 0.12},
         {"name": "양파", "kind": "crop", "crop": "양파", "amount_kg": 0.05},
         {"name": "무", "kind": "crop", "crop": "무", "amount_kg": 0.03},
         {"name": "돼지고기", "kind": "fixed", "won": 2500},
         {"name": "두부", "kind": "fixed", "won": 900},
         {"name": "양념", "kind": "fixed", "won": 400},
     ]},
    {"id": "doenjang_jjigae", "name": "된장찌개", "img": "doenjang_jjigae.png", "emoji": "🍲",
     "ingredients": [
         {"name": "양파", "kind": "crop", "crop": "양파", "amount_kg": 0.05},
         {"name": "무", "kind": "crop", "crop": "무", "amount_kg": 0.05},
         {"name": "시금치", "kind": "crop", "crop": "시금치", "amount_kg": 0.02},
         {"name": "두부", "kind": "fixed", "won": 900},
         {"name": "된장양념", "kind": "fixed", "won": 500},
     ]},
    {"id": "baechu_kimchi", "name": "배추김치", "img": "baechu_kimchi.png", "emoji": "🥬",
     "ingredients": [
         {"name": "배추", "kind": "crop", "crop": "배추", "amount_kg": 0.18},
         {"name": "무", "kind": "crop", "crop": "무", "amount_kg": 0.04},
         {"name": "양파", "kind": "crop", "crop": "양파", "amount_kg": 0.03},
         {"name": "사과", "kind": "crop", "crop": "사과", "amount_kg": 0.02},
         {"name": "고춧가루·젓갈", "kind": "fixed", "won": 800},
     ]},
    {"id": "mu_saengchae", "name": "무생채", "img": "mu_saengchae.png", "emoji": "🥗",
     "ingredients": [
         {"name": "무", "kind": "crop", "crop": "무", "amount_kg": 0.12},
         {"name": "양파", "kind": "crop", "crop": "양파", "amount_kg": 0.02},
         {"name": "사과", "kind": "crop", "crop": "사과", "amount_kg": 0.02},
         {"name": "양념", "kind": "fixed", "won": 300},
     ]},
    {"id": "sigeumchi_namul", "name": "시금치나물", "img": "sigeumchi_namul.png", "emoji": "🌿",
     "ingredients": [
         {"name": "시금치", "kind": "crop", "crop": "시금치", "amount_kg": 0.08},
         {"name": "양파", "kind": "crop", "crop": "양파", "amount_kg": 0.01},
         {"name": "참기름·양념", "kind": "fixed", "won": 300},
     ]},
    {"id": "yangpa_jangajji", "name": "양파장아찌", "img": "yangpa_jangajji.png", "emoji": "🧅",
     "ingredients": [
         {"name": "양파", "kind": "crop", "crop": "양파", "amount_kg": 0.10},
         {"name": "간장·식초", "kind": "fixed", "won": 400},
     ]},
    {"id": "jeyuk_bokkeum", "name": "제육볶음", "img": "jeyuk_bokkeum.png", "emoji": "🍖",
     "ingredients": [
         {"name": "양파", "kind": "crop", "crop": "양파", "amount_kg": 0.06},
         {"name": "돼지고기", "kind": "fixed", "won": 3000},
         {"name": "고추장양념", "kind": "fixed", "won": 600},
     ]},
]


def all_dishes():
    return DISHES


def by_id(did):
    for d in DISHES:
        if d["id"] == did:
            return d
    return None
```

- [ ] **Step 2: Add import + GET route in `backend/app.py`**

Add to the import block near line 14 (after `from model import ...`):

```python
import dishes  # noqa: E402
```

Add a new GET branch inside `do_GET`, right after the `/api/quiz` branch (currently line 180-181), before `# 정적 파일`:

```python
            if p == "/api/dishes":
                return self._json({"dishes": dishes.all_dishes()})
```

- [ ] **Step 3: Add failing test in `backend/test_api.py`**

Add inside `run_checks()` after the quiz check (after line 67):

```python
    # dishes
    s, d = get("/api/dishes")
    check("dishes 200", s == 200)
    ds = d.get("dishes", [])
    check("dishes >=8종", len(ds) >= 8)
    import dishes as _D
    ok_struct = all(
        x.get("id") and x.get("name") and isinstance(x.get("ingredients"), list)
        and all(
            (ing["kind"] == "crop" and ing["crop"] in _D.CROPS and ing.get("amount_kg", 0) > 0)
            or (ing["kind"] == "fixed" and ing.get("won", 0) > 0)
            for ing in x["ingredients"])
        for x in ds)
    check("dishes 재료구조 유효", ok_struct)
```

- [ ] **Step 4: Run test to verify dishes checks**

Run: `python backend/test_api.py`
Expected: 새 `dishes 200`, `dishes >=8종`, `dishes 재료구조 유효` 모두 PASS, 기존 체크도 전부 PASS (총합 통과).

- [ ] **Step 5: Commit**

```bash
git add backend/dishes.py backend/app.py backend/test_api.py
git commit -m "feat: 음식 카탈로그 데이터 + GET /api/dishes"
```

---

## Task 2: 밥상 가격 계산 + `POST /api/meal`

**Files:**
- Modify: `backend/app.py` (모듈 함수 `_pct`, `compute_meal` 추가 + `do_POST` 디스패치 분리, 현재 line 187-218)
- Test: `backend/test_api.py`

**Interfaces:**
- Consumes: `MODEL.predict(crop, scenario, month)`, `BASELINE`, `dishes.by_id`, `FEATURES`.
- Produces: 모듈 함수 `compute_meal(scenario: dict, month: int, dish_ids: list) -> dict` with shape:
  `{"total":{"predicted","baseline","pct"}, "dishes":[{"id","name","predicted","baseline","pct","ingredients":[{"name","kind","predicted","baseline","pct"}]}], "ingredientTotals":[{"crop","predicted","baseline","pct","usedIn":[name...]}]}`
- Produces: HTTP `POST /api/meal` `{scenario:{...}, month:int, dishes:[id...]}` → 위 구조.

- [ ] **Step 1: Add `_pct` and `compute_meal` to `backend/app.py`**

Add these module-level functions right after the `explain(...)` function (after line 124):

```python
def _pct(pred, base):
    return round((pred - base) / base * 100) if base else 0


def compute_meal(scenario, month, dish_ids):
    """음식 id 목록 → 음식별·재료별·총액(예측 vs 평년 기상)."""
    crop_cache = {}

    def crop_price(crop):
        if crop not in crop_cache:
            p = MODEL.predict(crop, scenario, month=month)
            b = MODEL.predict(crop, dict(BASELINE), month=month)
            crop_cache[crop] = (p, b)
        return crop_cache[crop]

    out_dishes, agg = [], {}
    total_p = total_b = 0
    for did in dish_ids:
        d = dishes.by_id(did)
        if not d:
            continue  # 알 수 없는 음식은 건너뛴다
        dp = db = 0
        ings = []
        for ing in d["ingredients"]:
            if ing["kind"] == "crop":
                pp, bb = crop_price(ing["crop"])
                amt = float(ing.get("amount_kg", 0))
                ip, ib = round(pp * amt), round(bb * amt)
                a = agg.setdefault(ing["crop"], {"predicted": 0, "baseline": 0, "usedIn": []})
                a["predicted"] += ip
                a["baseline"] += ib
                if d["name"] not in a["usedIn"]:
                    a["usedIn"].append(d["name"])
            else:
                ip = ib = int(ing.get("won", 0))
            dp += ip
            db += ib
            ings.append({"name": ing["name"], "kind": ing["kind"],
                         "predicted": ip, "baseline": ib, "pct": _pct(ip, ib)})
        out_dishes.append({"id": d["id"], "name": d["name"],
                           "predicted": dp, "baseline": db, "pct": _pct(dp, db),
                           "ingredients": ings})
        total_p += dp
        total_b += db

    ing_totals = [{"crop": c, "predicted": v["predicted"], "baseline": v["baseline"],
                   "pct": _pct(v["predicted"], v["baseline"]), "usedIn": v["usedIn"]}
                  for c, v in agg.items()]
    ing_totals.sort(key=lambda x: x["predicted"] - x["baseline"], reverse=True)
    return {"total": {"predicted": total_p, "baseline": total_b, "pct": _pct(total_p, total_b)},
            "dishes": out_dishes, "ingredientTotals": ing_totals}
```

- [ ] **Step 2: Refactor `do_POST` to dispatch `/api/simulate` and `/api/meal`**

Replace the current `do_POST` (line 187-218) with a dispatcher that keeps simulate intact and adds meal:

```python
    def do_POST(self):
        u = urlparse(self.path)
        try:
            n = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:  # noqa
            return self._err(f"bad request: {e}", 400)
        if u.path == "/api/simulate":
            return self._simulate(body)
        if u.path == "/api/meal":
            return self._meal(body)
        return self._err("not found", 404)

    def _simulate(self, body):
        try:
            crop = body.get("item")
            if crop not in MODEL.items:
                return self._err("unknown item")
            month = int(body.get("month", 8))
            scen = {k: float(body.get(k, 0)) for k in FEATURES if k != "sun_dev"}
            if "sun_hr" in body:
                scen["sun_hr"] = float(body["sun_hr"])
            pred = MODEL.predict(crop, scen, month=month)
            normal = MODEL.normals[crop]
            ref = MODEL.predict(crop, dict(BASELINE), month=month)
            delta = {k: float(scen.get(k, 0)) - float(BASELINE.get(k, 0)) for k in FEATURES if k != "sun_dev"}
            contribs = MODEL.contributions(crop, delta, month=month)
            return self._json({
                "item": crop, "predicted": pred, "normal": normal,
                "baseline": ref,
                "r2": round(MODEL.r2[crop], 3),
                "reliability": MODEL.reliability(crop),
                "contributions": contribs,
                "explain": explain(crop, pred, ref, contribs),
                "adapt": ADAPT.get(crop, []),
            })
        except Exception as e:  # noqa
            return self._err(f"bad request: {e}", 400)

    def _meal(self, body):
        try:
            sc_in = body.get("scenario", {}) or {}
            month = int(body.get("month", sc_in.get("month", 8)))
            scen = {k: float(sc_in.get(k, 0)) for k in FEATURES if k != "sun_dev"}
            if "sun_hr" in sc_in:
                scen["sun_hr"] = float(sc_in["sun_hr"])
            dish_ids = body.get("dishes", []) or []
            return self._json(compute_meal(scen, month, dish_ids))
        except Exception as e:  # noqa
            return self._err(f"bad request: {e}", 400)
```

Note: this preserves the exact `/api/simulate` response (verify against current behavior — only moved into `_simulate`).

- [ ] **Step 3: Add failing tests in `backend/test_api.py`**

Add inside `run_checks()` after the dishes checks:

```python
    # meal — 폭염 시나리오에서 밥상 총액 상승
    hot = {"heat_days": 30, "drought_idx": 80, "heavy_rain_days": 4}
    s, d = post("/api/meal", {"scenario": hot, "month": 8,
                              "dishes": ["rice", "kimchi_jjigae", "baechu_kimchi"]})
    check("meal 200", s == 200)
    check("meal total>0", d["total"]["predicted"] > 0)
    check("meal 폭염→총액 상승", d["total"]["predicted"] >= d["total"]["baseline"]
          and d["total"]["pct"] > 0, f"pct={d['total']['pct']}")
    check("meal 음식 3개", len(d["dishes"]) == 3)
    check("meal 원자재 집계 존재", len(d["ingredientTotals"]) >= 1)
    # meal — 빈 밥상
    s, d = post("/api/meal", {"scenario": hot, "month": 8, "dishes": []})
    check("meal 빈 밥상 0원", s == 200 and d["total"]["predicted"] == 0 and d["total"]["pct"] == 0)
    # meal — 알 수 없는 음식은 스킵
    s, d = post("/api/meal", {"scenario": hot, "month": 8, "dishes": ["rice", "없는음식"]})
    check("meal 미지음식 스킵", s == 200 and len(d["dishes"]) == 1)
    # meal — 평년 시나리오 → pct≈0
    base = {"heat_days": 0, "cold_days": 0, "heavy_rain_days": 0, "drought_idx": 20, "frost": 0}
    s, d = post("/api/meal", {"scenario": base, "month": 8, "dishes": ["kimchi_jjigae"]})
    check("meal 평년 pct≈0", abs(d["total"]["pct"]) <= 1, f"pct={d['total']['pct']}")
```

- [ ] **Step 4: Run tests**

Run: `python backend/test_api.py`
Expected: 모든 meal 체크 PASS + 기존(simulate 포함) 전부 PASS. `meal 평년 pct≈0`이 통과해야 함(평년 시나리오는 BASELINE과 동일).

- [ ] **Step 5: Commit**

```bash
git add backend/app.py backend/test_api.py
git commit -m "feat: POST /api/meal — 밥상 가격·재료비 계산"
```

---

## Task 3: 3D 음식·식탁 에셋 번들 + CREDITS

**Files:**
- Create: `frontend/assets/foods/{rice,kimchi_jjigae,doenjang_jjigae,baechu_kimchi,mu_saengchae,sigeumchi_namul,yangpa_jangajji,jeyuk_bokkeum}.png`
- Create: `frontend/assets/table.png`
- Create: `frontend/assets/CREDITS.md`

**Interfaces:**
- Produces: 정적 경로 `/assets/foods/<id>.png`, `/assets/table.png` (app.py `_static`가 이미 `.png` 서빙).
- Note: 프론트는 이미지 로드 실패 시 이모지로 폴백하므로 이 태스크가 없어도 앱은 동작한다(비차단). 단 최종 품질을 위해 완료한다.

- [ ] **Step 1: 무료 3D 일러스트 에셋 수집**

투명배경·무료 라이선스 3D(클레이) 음식 일러스트를 확보한다. 권장 출처: Flaticon 3D / Icons8 3D / 기타 CC 라이선스 세트. 한식 매핑이 어려운 음식은 가장 가까운 일반 음식 일러스트로 대체(예: 김치찌개=스튜, 제육볶음=볶음요리). 식탁은 위에서 본 둥근 나무 식탁 투명 PNG.

파일을 위 경로에 정확한 파일명으로 저장한다(`dishes.py`의 `img` 값과 일치).

- [ ] **Step 2: CREDITS.md 작성**

```markdown
# 에셋 출처 및 라이선스

| 파일 | 출처(URL) | 저작자 | 라이선스 |
|---|---|---|---|
| foods/rice.png | <URL> | <author> | <license> |
| ... | ... | ... | ... |
| table.png | <URL> | <author> | <license> |

모든 에셋은 투명배경 무료 라이선스이며, 라이선스가 요구하는 출처 표기를 본 문서로 갈음한다.
```

각 파일의 실제 출처·라이선스를 채운다(빈칸 금지).

- [ ] **Step 3: 서빙 확인**

Run: `python backend/app.py` (백그라운드) 후
`curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/assets/table.png`
Expected: `200`. 음식 PNG 하나도 동일하게 200 확인.

- [ ] **Step 4: Commit**

```bash
git add frontend/assets
git commit -m "assets: 3D 음식·식탁 일러스트 + CREDITS"
```

---

## Task 4: HTML 탭 + 밥상 뷰 마크업 + CSS

**Files:**
- Modify: `frontend/index.html` (nav line 33-36, `#viewMeal` 섹션은 `#viewQuiz` 앞에 삽입 = line 115 직전)
- Modify: `frontend/style.css` (파일 끝 `@media` 앞에 밥상 스타일 추가)

**Interfaces:**
- Produces: DOM ids — `tabMeal`, `viewMeal`, `mealWeatherBadge`, `mealPresets`, `mealTray`, `mealTable`, `mealPlates`, `mealHint`, `mealClear`, `mealResult`. (Task 5의 JS가 이 id들을 사용)

- [ ] **Step 1: 탭 버튼 추가**

`frontend/index.html`의 `<nav class="tabs" ...>`(line 33-36)를 다음으로 교체:

```html
<nav class="tabs" role="tablist" aria-label="화면 전환">
  <button id="tabSim" class="tab active" role="tab" aria-selected="true" type="button">시뮬레이션</button>
  <button id="tabMeal" class="tab" role="tab" aria-selected="false" type="button">밥상 차리기</button>
  <button id="tabQuiz" class="tab" role="tab" aria-selected="false" type="button">학습 퀴즈</button>
</nav>
```

- [ ] **Step 2: 밥상 뷰 마크업 삽입**

`<section id="viewQuiz" ...>`(line 115) 바로 앞에 삽입:

```html
<section id="viewMeal" class="mealpage" hidden>
  <div class="mealwrap">
    <div class="meal-head">
      <div>
        <h2 class="meal-title">오늘의 밥상, 이 날씨엔 얼마일까?</h2>
        <p class="meal-sub">음식을 식탁에 올리면 재료(원자재)별 물가상승률과 총액을 계산합니다. 날씨는 시뮬레이션 탭과 공유됩니다.</p>
      </div>
      <span id="mealWeatherBadge" class="mw-badge">현재 날씨 —</span>
    </div>
    <div id="mealPresets" class="meal-presets"></div>

    <div id="mealTray" class="meal-tray" aria-label="음식 트레이"></div>

    <div id="mealTable" class="meal-table">
      <div id="mealPlates" class="meal-plates"></div>
      <p class="meal-hint" id="mealHint">음식을 식탁 위로 끌어다 놓아 보세요 (모바일은 탭)</p>
    </div>
    <div class="meal-tablebar">
      <button id="mealClear" class="mini" type="button">식탁 비우기</button>
    </div>

    <div class="card meal-result" id="mealResult" aria-live="polite"></div>
  </div>
</section>
```

- [ ] **Step 3: CSS 추가**

`frontend/style.css`의 `@media (max-width:833px){`(현재 파일 끝부분) **앞에** 추가:

```css
/* ---------- 밥상 차리기 ---------- */
.mealwrap{max-width:1080px;margin:0 auto;padding:32px 28px 0}
.meal-head{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;margin-bottom:18px}
.meal-title{font-size:28px;font-weight:600;letter-spacing:-.5px;line-height:1.2}
.meal-sub{font-size:15px;color:var(--muted);margin-top:8px;letter-spacing:-.3px;line-height:1.5;max-width:560px}
.mw-badge{flex:0 0 auto;background:var(--canvas);border:1px solid var(--hairline);border-radius:9999px;padding:8px 14px;font-size:13px;font-weight:500;color:var(--ink);white-space:nowrap}
.meal-presets{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:18px}
.meal-presets button{background:var(--canvas);border:1px solid var(--hairline);border-radius:9999px;padding:9px 16px;font-size:13px;letter-spacing:-.2px;color:var(--ink);min-height:38px;transition:transform .12s,border-color .12s}
.meal-presets button:active{transform:scale(.95)}
.meal-presets button:hover{border-color:var(--ink)}
.meal-presets button.active{box-shadow:inset 0 0 0 2px var(--primary-focus);border-color:transparent;font-weight:600}

.meal-tray{display:flex;gap:10px;overflow-x:auto;padding:12px;background:var(--canvas);border:1px solid var(--hairline);border-radius:18px;margin-bottom:16px}
.tray-card{flex:0 0 auto;width:92px;text-align:center;border:1px solid var(--hairline);border-radius:14px;padding:10px 6px;background:var(--canvas);cursor:grab;transition:transform .12s,border-color .12s;user-select:none}
.tray-card:hover{border-color:var(--ink)}
.tray-card:active{cursor:grabbing;transform:scale(.96)}
.tray-card .food-img{width:54px;height:54px;object-fit:contain;display:block;margin:0 auto 6px;pointer-events:none}
.tray-card .food-emoji{font-size:42px;line-height:54px;display:block;margin-bottom:6px}
.tray-card .food-name{font-size:12px;letter-spacing:-.2px;color:var(--ink)}

.meal-table{position:relative;min-height:340px;border-radius:24px;
  background:radial-gradient(ellipse 70% 60% at 50% 50%,#e8d4b0,#d8bd92);
  border:3px solid #c4a574;overflow:hidden;transition:box-shadow .15s}
.meal-table.drag-over{box-shadow:inset 0 0 0 3px var(--primary)}
.meal-table.has-bg{background:#f0ead9}
.meal-table .table-img{position:absolute;inset:0;width:100%;height:100%;object-fit:contain;pointer-events:none}
.meal-plates{position:absolute;inset:0}
.plate{position:absolute;transform:translate(-50%,-50%);text-align:center;cursor:pointer;transition:transform .12s}
.plate:hover{transform:translate(-50%,-50%) scale(1.06)}
.plate:active{transform:translate(-50%,-50%) scale(.94)}
.plate .food-img{width:74px;height:74px;object-fit:contain;display:block;filter:drop-shadow(0 4px 8px rgba(0,0,0,.18))}
.plate .food-emoji{font-size:58px;display:block;filter:drop-shadow(0 4px 8px rgba(0,0,0,.18))}
.plate .plate-name{font-size:11px;font-weight:600;color:#5a4a30;margin-top:2px}
.meal-hint{position:absolute;left:0;right:0;top:50%;transform:translateY(-50%);text-align:center;color:#9b8a6a;font-size:15px;letter-spacing:-.3px;pointer-events:none}
.meal-tablebar{display:flex;justify-content:flex-end;margin:10px 0 18px}

.meal-result{padding:24px}
.meal-empty{color:var(--muted-48);font-size:15px;text-align:center;padding:8px 0}
.meal-total{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;padding-bottom:18px;border-bottom:1px solid var(--divider)}
.meal-total .mt-label{font-size:14px;color:var(--muted-48)}
.meal-total .mt-num{font-size:44px;font-weight:600;letter-spacing:-1px;line-height:1;margin-top:4px}
.meal-total .mt-num small{font-size:17px;color:var(--muted-48);margin-left:4px}
.meal-total .mt-pct{font-size:26px;font-weight:600;letter-spacing:-.4px;white-space:nowrap}
.meal-total .mt-pct.up{color:var(--ink)} .meal-total .mt-pct.down{color:var(--primary)}
.meal-insight{font-size:15px;color:var(--muted);margin:16px 0;letter-spacing:-.3px;line-height:1.5}
.meal-insight b{color:var(--ink)}
.meal-section-label{font-size:13px;font-weight:600;color:var(--muted-48);letter-spacing:-.2px;margin:18px 0 10px}
.dish-list{display:flex;flex-direction:column;gap:8px}
.dish-row{display:flex;justify-content:space-between;align-items:center;font-size:14px;padding:8px 0;border-bottom:1px solid var(--divider)}
.dish-row:last-child{border:none}
.dish-row .dr-name{color:var(--ink)}
.dish-row .dr-price{color:var(--muted);font-variant-numeric:tabular-nums}
.dish-row .dr-pct{font-size:12px;color:var(--primary);margin-left:8px}
.ing-bars{display:flex;flex-direction:column;gap:10px}
.ing-bar{font-size:13px;letter-spacing:-.2px}
.ing-bar .ib-top{display:flex;justify-content:space-between;margin-bottom:4px;color:var(--muted)}
.ing-bar .ib-top b{color:var(--ink)}
.ing-bar .ib-track{height:8px;background:var(--parchment);border-radius:9999px;overflow:hidden}
.ing-bar .ib-fill{height:100%;background:var(--primary);border-radius:9999px;transition:width .4s}
```

- [ ] **Step 4: 시각 확인**

Run: `python backend/app.py` (실행 중이면 생략) → 브라우저로 `http://localhost:8000` 접속, 상단에 **밥상 차리기** 탭이 보이는지 확인. (탭 전환 JS는 Task 5에서 연결되므로 아직 클릭 동작은 미완 — 마크업/스타일만 확인)

- [ ] **Step 5: Commit**

```bash
git add frontend/index.html frontend/style.css
git commit -m "feat: 밥상 차리기 탭·뷰 마크업 + 스타일"
```

---

## Task 5: 프론트엔드 로직 — 트레이·드래그/드롭·결과 렌더

**Files:**
- Modify: `frontend/app.js` (state 확장, init 확장, setupTabs 확장, 신규 밥상 함수들 추가; IIFE 내부)

**Interfaces:**
- Consumes: `GET /api/dishes`, `POST /api/meal`, 기존 `state.scenario`, `PRESETS`, `api()`, `toast()`, `$()`.
- Consumes (DOM): Task 4의 id들.
- Produces: 함수 `loadDishes()`, `buildTray()`, `setupMealTable()`, `buildMealPresets()`, `addPlate(id,x,y)`, `removePlate(uid)`, `simulateMeal()`, `renderMeal(res)`, `refreshMeal()`, `updateWeatherBadge()`.

- [ ] **Step 1: state에 밥상 필드 추가**

`const state = {...}` (line 7-11)에 `meal` 배열과 dishes 캐시 추가. `r2: 0,` 뒤에 추가:

```javascript
  dishes: [], meal: [], mealUid: 0,
```

- [ ] **Step 2: 음식 로드 + 트레이 빌드 + 프리셋 함수 추가**

`init()` 함수 뒤(line 90 이후, `function buildCrops()` 앞)에 추가:

```javascript
/* ---------- 밥상 차리기 ---------- */
async function loadDishes() {
  try {
    const r = await api("/api/dishes");
    state.dishes = r.dishes || [];
  } catch (e) { state.dishes = []; }
}
function dishById(id) { return state.dishes.find(d => d.id === id); }

function foodMedia(dish, cls) {
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
    card.draggable = true;
    card.dataset.id = d.id;
    card.innerHTML = `${foodMedia(d)}<div class="food-name">${d.name}</div>`;
    card.addEventListener("dragstart", e => e.dataTransfer.setData("text/plain", d.id));
    card.addEventListener("click", () => addPlate(d.id)); // 모바일/탭 폴백
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
```

- [ ] **Step 3: 식탁 드롭/배치/제거 + 시뮬·렌더 함수 추가**

위 코드 바로 뒤에 추가:

```javascript
function setupMealTable() {
  const table = $("mealTable"); if (!table) return;
  table.addEventListener("dragover", e => { e.preventDefault(); table.classList.add("drag-over"); });
  table.addEventListener("dragleave", () => table.classList.remove("drag-over"));
  table.addEventListener("drop", e => {
    e.preventDefault(); table.classList.remove("drag-over");
    const id = e.dataTransfer.getData("text/plain"); if (!id) return;
    const rect = table.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 100;
    const y = ((e.clientY - rect.top) / rect.height) * 100;
    addPlate(id, x, y);
  });
  const clear = $("mealClear");
  if (clear) clear.onclick = () => { state.meal = []; renderPlates(); simulateMeal(); };
}

function addPlate(id, x, y) {
  const d = dishById(id); if (!d) return;
  // 좌표 미지정(탭 추가) 시 가운데 부근에 분산 배치
  if (x == null) { x = 30 + (state.meal.length * 17) % 45; y = 38 + (state.meal.length * 13) % 30; }
  x = Math.max(10, Math.min(90, x)); y = Math.max(14, Math.min(86, y));
  state.meal.push({ uid: ++state.mealUid, id, x, y });
  renderPlates(); simulateMeal();
}
function removePlate(uid) {
  state.meal = state.meal.filter(p => p.uid !== uid);
  renderPlates(); simulateMeal();
}
function renderPlates() {
  const wrap = $("mealPlates"); if (!wrap) return;
  wrap.innerHTML = "";
  for (const p of state.meal) {
    const d = dishById(p.id); if (!d) continue;
    const el = document.createElement("div");
    el.className = "plate";
    el.style.left = p.x + "%"; el.style.top = p.y + "%";
    el.innerHTML = `${foodMedia(d)}<div class="plate-name">${d.name}</div>`;
    el.title = d.name + " (클릭 시 제거)";
    el.onclick = () => removePlate(p.uid);
    wrap.appendChild(el);
  }
  const hint = $("mealHint"); if (hint) hint.style.display = state.meal.length ? "none" : "";
}

let mealTimer = null;
function simulateMeal() {
  clearTimeout(mealTimer);
  mealTimer = setTimeout(doSimulateMeal, 110);
}
async function doSimulateMeal() {
  const ids = state.meal.map(p => p.id);
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

function renderMeal(res) {
  updateWeatherBadge();
  const box = $("mealResult"); if (!box) return;
  if (!res || !res.dishes || !res.dishes.length) {
    box.innerHTML = `<p class="meal-empty">식탁이 비었습니다. 위 음식을 끌어다 올려 보세요.</p>`;
    return;
  }
  const t = res.total;
  const pctTxt = (t.pct > 0 ? "+" : "") + t.pct + "%";
  const top = res.ingredientTotals[0];
  const insight = top && t.pct > 0
    ? `이 날씨에서 <b>${top.crop}</b>이(가) 평년比 <b>+${top.pct}%</b>로 밥상값을 가장 많이 끌어올렸습니다.`
    : (t.pct > 0 ? "기상 영향으로 밥상값이 소폭 올랐습니다." : "평년 날씨와 비슷한 수준입니다.");
  const dishRows = res.dishes.map(d =>
    `<div class="dish-row"><span class="dr-name">${d.name}<span class="dr-pct">${d.pct > 0 ? "+" + d.pct + "%" : ""}</span></span>
       <span class="dr-price">${d.predicted.toLocaleString()}원</span></div>`).join("");
  const maxDelta = Math.max(1, ...res.ingredientTotals.map(i => i.predicted - i.baseline));
  const ingBars = res.ingredientTotals.map(i => {
    const delta = i.predicted - i.baseline;
    const w = Math.max(3, delta / maxDelta * 100);
    return `<div class="ing-bar"><div class="ib-top"><span>${i.crop} <small style="color:#86868b">${i.usedIn.join("·")}</small></span>
        <b>${i.pct > 0 ? "+" : ""}${i.pct}% · ${i.predicted.toLocaleString()}원</b></div>
        <div class="ib-track"><div class="ib-fill" style="width:${w}%"></div></div></div>`;
  }).join("");
  box.innerHTML = `
    <div class="meal-total">
      <div><span class="mt-label">밥상 총액</span>
        <div class="mt-num">${t.predicted.toLocaleString()}<small>원</small></div></div>
      <div class="mt-pct ${t.pct >= 0 ? "up" : "down"}">${pctTxt}</div>
    </div>
    <p class="meal-insight">${insight} 평년 밥상은 약 ${t.baseline.toLocaleString()}원입니다.</p>
    <div class="meal-section-label">음식별</div>
    <div class="dish-list">${dishRows}</div>
    <div class="meal-section-label">원자재(기후 작물) 가격 영향</div>
    <div class="ing-bars">${ingBars || '<p class="meal-empty">기후 작물 재료가 없습니다.</p>'}</div>`;
}

function refreshMeal() {
  updateWeatherBadge();
  if (state.meal.length) simulateMeal();
}
```

- [ ] **Step 4: init()에서 밥상 초기화 + 시나리오 변경 시 갱신 연결**

(4a) `init()` 안에서 `setupTabs(); setupQuiz();`(line 82) 줄을 다음으로 교체:

```javascript
  setupTabs(); setupQuiz();
  await loadDishes(); buildTray(); buildMealPresets(); setupMealTable();
  renderMeal(null); updateWeatherBadge();
```

(4b) 기존 `doSimulate()`(작물 시뮬)가 시나리오를 바꾸므로, 밥상도 같이 갱신되도록 `doSimulate` 끝에 한 줄 추가. `drawMap(lastPct);`(line 170) 바로 뒤에 추가:

```javascript
  refreshMeal();
```

- [ ] **Step 5: 탭 전환에 밥상 추가 (setupTabs 교체)**

`setupTabs()`(line 339-351)를 3탭 지원으로 교체:

```javascript
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
```

- [ ] **Step 6: 수동 검증 (브라우저)**

Run: `python backend/app.py` 실행 후 `http://localhost:8000` 접속.
검증 항목:
1. **밥상 차리기** 탭 클릭 → 트레이에 음식 8종(이미지 또는 이모지) 표시.
2. 트레이 음식을 식탁으로 **드래그&드롭** → 식탁에 접시가 놓이고 결과 패널에 총액·음식별·원자재 막대 표시.
3. 음식 카드 **클릭(탭)** → 식탁에 추가됨(폴백 동작).
4. 식탁 위 접시 **클릭** → 제거되고 총액 갱신.
5. **식탁 비우기** → 빈 상태 안내.
6. 밥상 프리셋(예: 2024 폭염) 클릭 → 총액·% 상승, 날씨 배지 갱신.
7. **시뮬레이션 탭**으로 가서 슬라이더 조절 → 다시 밥상 탭 오면 같은 날씨로 총액 반영(공유 확인).
8. 기존 시뮬레이션·퀴즈 탭 정상 동작(회귀 없음).

(gstack 사용자는 `/browse`로 스크린샷·상호작용 검증 가능.)

- [ ] **Step 7: Commit**

```bash
git add frontend/app.js
git commit -m "feat: 밥상 차리기 로직 — 드래그/드롭·날씨 공유·결과 렌더"
```

---

## Task 6: 통합 검증 & 마무리

**Files:**
- Modify: (필요 시) 위 파일들 버그 수정

- [ ] **Step 1: 백엔드 전체 테스트**

Run: `python backend/test_api.py`
Expected: 기존 18 + dishes 3 + meal 6 = 모든 체크 PASS, 종료코드 0.

- [ ] **Step 2: 프론트 회귀 + 신규 수동 QA**

Task 5 Step 6의 8개 항목을 다시 1회 통과 확인. 데스크톱 + 모바일 폭(개발자도구 833px 이하)에서 트레이 가로 스크롤·식탁 레이아웃 정상 확인.

- [ ] **Step 3: README 갱신(선택)**

`README.md`의 기능 표/사용법에 "밥상 차리기" 한 줄 추가(있다면).

- [ ] **Step 4: 최종 커밋**

```bash
git add -A
git commit -m "docs: README에 밥상 차리기 기능 반영"
```

---

## Self-Review (작성자 점검 결과)

**Spec coverage:**
- (2) 탭 추가·날씨 공유 → Task 4(탭), Task 5(공유 refreshMeal/badge). ✓
- (3) 음식↔재료 모델 → Task 1(dishes.py), Task 2(compute_meal). ✓
- (4) 백엔드 API → Task 1(GET), Task 2(POST). ✓
- (5) 드래그&드롭 + 탭 폴백 + 제거 → Task 5 Step 3. ✓
- (6) 결과 패널(총액·음식별·원자재 분해) → Task 5 renderMeal. ✓
- (7) 3D 에셋·이모지 폴백 → Task 3 + foodMedia onerror. ✓
- (8) 엣지(빈 밥상·미지 id·평년≈0) → Task 2 테스트. ✓
- (9) test_api 확장 → Task 1·2. ✓

**Placeholder scan:** CREDITS.md의 `<URL>`/`<author>`는 Task 3에서 실제 값으로 채우라고 명시(빈칸 금지). 그 외 placeholder 없음.

**Type consistency:** `compute_meal` 반환 키(`total`/`dishes`/`ingredientTotals`, 각 항목의 `predicted`/`baseline`/`pct`/`usedIn`)가 Task 5 `renderMeal` 소비와 일치. DOM id가 Task 4 마크업과 Task 5 사용처에서 일치(`mealTray`,`mealTable`,`mealPlates`,`mealResult`,`mealClear`,`mealWeatherBadge`,`mealPresets`,`mealHint`). 함수명 일관(`addPlate`/`removePlate`/`renderPlates`/`simulateMeal`/`refreshMeal`).
