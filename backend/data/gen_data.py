# -*- coding: utf-8 -*-
"""
기후 식탁 — 데이터 생성기 (표준 라이브러리만 사용)
월별(2018.01~2025.12) 한반도 대표 기상 피처 + 농산물 도매가격(원/kg)을 생성한다.

데이터 근거(현실 정합):
 - 2018-07/08  역대급 폭염 (관측사상 최고기온)         → 폭염일수 급증, 잎채소·과수 피해
 - 2020-06~08  역대 최장 장마(중부 54일)              → 강수량 급증, 일조 급감, 작황 악화
 - 2022-08     수도권 집중호우(시간당 100mm+)         → 호우일수 급증
 - 2023-04     사과 개화기 저온·서리 + 여름 잦은 비    → 2024 '금사과'(사과값 폭등)
 - 2024-여름   역대급 폭염·고온                        → 배추·무 등 엽채류 가격 폭등(김장물가)
가격 수준은 KAMIS(농산물유통정보)·통계청 보도값을 참고한 근사 모델이며,
정밀 시세가 아닌 '기상→가격' 인과를 학습시키기 위한 교육용 데이터셋이다.
"""
import json, math, os, random

random.seed(20260619)

YEARS = list(range(2018, 2026))
MONTHS = list(range(1, 13))

# 작물 정의: 기준가(원/kg), 기상 민감도(피처별 계수), 계절(월별 가중)
# 민감도 단위는 가격(원/kg) 변화량. 양수=가격 상승요인.
CROPS = {
    "배추": {  # 1포기≈2.5kg, 여름 고온·가뭄·호우에 매우 민감
        "base": 900, "unit": "원/kg",
        "sens": {"heat": 22, "drought": 6.5, "heavy_rain": 28, "cold": 4, "frost": 0, "sun": -1.2},
        "season": {7: 250, 8: 400, 9: 350, 10: 300, 11: 250},  # 김장철 수요·고랭지
        "icon": "🥬",
    },
    "무": {
        "base": 700, "unit": "원/kg",
        "sens": {"heat": 16, "drought": 5.0, "heavy_rain": 20, "cold": 5, "frost": 0, "sun": -0.9},
        "season": {8: 200, 9: 260, 10: 240, 11: 220},
        "icon": "🌰",
    },
    "사과": {  # 연 1회 수확. 봄 개화기 냉해가 그 해 작황·연중 가격을 좌우
        "base": 2600, "unit": "원/kg",
        "sens": {"heat": 9, "drought": 3.0, "heavy_rain": 16, "cold": 2, "frost": 120, "sun": -2.0},
        "season": {1: 300, 2: 350, 3: 300, 8: -150, 9: -250, 10: -300},  # 햇사과 출하기 하락
        "icon": "🍎",
    },
    "쌀": {  # 정부 관리로 비교적 안정. 태풍·호우·일조 영향
        "base": 2700, "unit": "원/kg",
        "sens": {"heat": 3, "drought": 1.5, "heavy_rain": 9, "cold": 1, "frost": 0, "sun": -1.0},
        "season": {},
        "icon": "🌾",
    },
    "시금치": {  # 한파·고온 모두 취약(엽채류)
        "base": 3200, "unit": "원/kg",
        "sens": {"heat": 28, "drought": 5.0, "heavy_rain": 22, "cold": 24, "frost": 6, "sun": -1.5},
        "season": {12: 300, 1: 350, 2: 300},
        "icon": "🥬",
    },
    "양파": {  # 봄 수확·저장. 봄 기상·저장조건
        "base": 1100, "unit": "원/kg",
        "sens": {"heat": 10, "drought": 6.0, "heavy_rain": 12, "cold": 3, "frost": 10, "sun": -0.8},
        "season": {3: 180, 4: 150, 5: -100, 6: -120},
        "icon": "🧅",
    },
}

# 월별 평년 기후값(대표)
CLIMO_TEMP = {1: -1, 2: 2, 3: 7, 4: 13, 5: 18, 6: 22, 7: 26, 8: 27, 9: 22, 10: 15, 11: 8, 12: 1}
CLIMO_RAIN = {1: 30, 2: 35, 3: 55, 4: 75, 5: 100, 6: 150, 7: 290, 8: 280, 9: 150, 10: 60, 11: 50, 12: 30}
CLIMO_SUN = {1: 170, 2: 175, 3: 200, 4: 210, 5: 220, 6: 170, 7: 130, 8: 160, 9: 180, 10: 200, 11: 165, 12: 160}

# 연·월 기상 이상(실제 사건 반영): (year, month) -> dict of anomalies
EVENTS = {
    (2018, 7): {"heat": 16, "temp": 2.5, "sun": 30},
    (2018, 8): {"heat": 14, "temp": 2.8, "drought": 25},
    (2020, 6): {"rain": 120, "sun": -50},
    (2020, 7): {"rain": 250, "heavy_rain": 6, "sun": -70, "temp": -1.5},
    (2020, 8): {"rain": 230, "heavy_rain": 7, "sun": -60},
    (2022, 8): {"rain": 200, "heavy_rain": 8, "temp": 0.5},
    (2023, 4): {"frost": 70, "temp": -2.5},      # 사과 개화기 냉해
    (2023, 7): {"rain": 180, "heavy_rain": 6},
    (2024, 7): {"heat": 12, "temp": 2.2, "drought": 18},
    (2024, 8): {"heat": 18, "temp": 3.0, "drought": 30, "sun": 25},  # 역대급 폭염
    (2024, 9): {"heat": 8, "temp": 2.5},
}


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def gen_month(year, month):
    ev = EVENTS.get((year, month), {})
    temp = CLIMO_TEMP[month] + random.gauss(0, 1.0) + ev.get("temp", 0)
    rain = max(0, CLIMO_RAIN[month] + random.gauss(0, 25) + ev.get("rain", 0))
    sun = max(40, CLIMO_SUN[month] + random.gauss(0, 15) + ev.get("sun", 0))
    # 폭염일수: 여름철 고온일 때
    heat = 0
    if month in (6, 7, 8, 9):
        heat = clamp(round((temp - 24) * 2.2 + ev.get("heat", 0) + random.gauss(0, 1)), 0, 31)
    # 한파일수: 겨울철 저온
    cold = 0
    if month in (12, 1, 2):
        cold = clamp(round((-2 - temp) * 1.8 + random.gauss(0, 1)), 0, 28)
    # 호우일수
    heavy = clamp(round(rain / 90 - 1 + ev.get("heavy_rain", 0) + random.gauss(0, 0.5)), 0, 12)
    # 가뭄지수(강수 부족 + 고온)
    drought = clamp(round((CLIMO_RAIN[month] - rain) / CLIMO_RAIN[month] * 60 + ev.get("drought", 0) + max(0, heat) * 1.2), 0, 100)
    # 개화기 냉해(주로 4월)
    frost = ev.get("frost", 0) if month == 4 else (random.choice([0, 0, 0, 5]) if month == 4 else 0)
    return {
        "year": year, "month": month, "date": f"{year}-{month:02d}",
        "temp": round(temp, 1), "rain_mm": round(rain), "sun_hr": round(sun),
        "heat_days": int(heat), "cold_days": int(cold), "heavy_rain_days": int(heavy),
        "drought_idx": int(drought), "frost": int(frost),
    }


def price_for(crop, w, prev):
    c = CROPS[crop]
    s = c["sens"]
    base = c["base"] + c["season"].get(w["month"], 0)
    delta = (s["heat"] * w["heat_days"] + s["drought"] * (w["drought_idx"] / 10.0)
             + s["heavy_rain"] * w["heavy_rain_days"] + s["cold"] * w["cold_days"]
             + s["frost"] * (w["frost"] / 10.0) + s["sun"] * ((w["sun_hr"] - 170) / 10.0))
    # 사과: 봄 냉해는 그 해 가을~다음해까지 누적 영향(연 1회 수확)
    target = base + delta
    # AR(1) 평활 + 노이즈
    p = 0.55 * target + 0.45 * (prev if prev else target) + random.gauss(0, base * 0.03)
    return max(round(p / 10) * 10, 200)


def main():
    # pass1: 월별 기상 생성
    weather = [gen_month(y, m) for y in YEARS for m in MONTHS]
    # 연도별 봄 냉해(4월) 강도
    spring = {}
    for w in weather:
        if w["month"] == 4:
            spring[w["year"]] = max(spring.get(w["year"], 0), w["frost"])
    for y in YEARS:
        spring.setdefault(y, 0)
    # 냉해를 그 해 전체로 전파(연1회 수확 작물의 연중 가격 신호) — 5~12월은 당해, 1~4월은 전년 봄
    for w in weather:
        y, m = w["year"], w["month"]
        w["frost"] = int(spring.get(y, 0) if m >= 5 else spring.get(y - 1, 0))
    # pass2: 가격 산출
    rows = []
    prev = {k: None for k in CROPS}
    for w in weather:
        prices = {}
        for crop in CROPS:
            pr = price_for(crop, w, prev[crop])
            prices[crop] = pr
            prev[crop] = pr
        w["prices"] = prices
        rows.append(w)

    items = [{"name": k, "icon": v["icon"], "unit": v["unit"], "base": v["base"]} for k, v in CROPS.items()]
    # 평년 가격(작물별 전체 평균)
    normals = {}
    for crop in CROPS:
        vals = [r["prices"][crop] for r in rows]
        normals[crop] = round(sum(vals) / len(vals))

    out = {
        "meta": {
            "title": "기후 식탁 데이터셋",
            "period": "2018-01 ~ 2025-12 (월별)",
            "note": "KAMIS·통계청·기상청 보도값 기반 교육용 근사 모델. 기상→가격 인과 학습용.",
            "features": ["temp", "rain_mm", "sun_hr", "heat_days", "cold_days", "heavy_rain_days", "drought_idx", "frost"],
        },
        "events": [
            {"date": "2018-08", "label": "역대급 폭염", "desc": "관측사상 최고기온, 엽채류·과수 피해"},
            {"date": "2020-07", "label": "역대 최장 장마", "desc": "중부 54일 장마, 일조 급감"},
            {"date": "2022-08", "label": "수도권 집중호우", "desc": "시간당 100mm+ 폭우"},
            {"date": "2023-04", "label": "사과 개화기 냉해", "desc": "저온·서리 → 2024 금사과 원인"},
            {"date": "2024-08", "label": "역대급 폭염", "desc": "배추·무 등 김장물가 폭등"},
        ],
        "items": items,
        "normals": normals,
        "rows": rows,
    }
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "dataset.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"generated {len(rows)} months, {len(CROPS)} crops -> dataset.json")
    print("normals:", normals)


if __name__ == "__main__":
    main()
