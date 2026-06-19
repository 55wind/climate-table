# -*- coding: utf-8 -*-
"""
기후 식탁 — 실데이터 수집기 (KAMIS 가격 + 기상청 ASOS 날씨 → dataset.json)
표준 라이브러리만 사용. 인증키는 환경변수로 주입한다.

[필요 인증키 — 무료 발급]
  1) KAMIS OpenAPI  : https://www.kamis.or.kr/customer/reference/openapi_list.do  (이용신청 → cert_key, cert_id)
  2) 기상청 ASOS    : https://www.data.go.kr  '기상청_지상(종관, ASOS) 일자료 조회서비스' 활용신청 → serviceKey

[실행]
  set KAMIS_CERT_KEY=...   &  set KAMIS_CERT_ID=...   &  set KMA_SERVICE_KEY=...   (Windows: $env:로)
  python backend/data/fetch_real_data.py --start 2018-01 --end 2025-12
  → backend/data/dataset.json 을 실데이터로 덮어씀 (백엔드 재기동 시 자동 반영)

키가 없으면 아무것도 덮어쓰지 않고, 발급 안내를 출력한 뒤 종료한다(기존 보정 데이터 유지).

[주의] KAMIS 품목/종/등급 코드와 ASOS 관측소 코드는 아래 표에 best-effort로 채워두었다.
       최초 1회 --check 로 코드 응답을 확인하고 필요 시 보정할 것.
"""
import json, os, sys, time, calendar
from urllib.request import urlopen
from urllib.parse import urlencode
from urllib.error import URLError, HTTPError

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "dataset.json")

# .env.local(깃 제외)에서 키 로드 → 환경변수보다 우선순위 낮게(환경변수 있으면 그것 사용)
def _load_env_local():
    path = os.path.join(HERE, ".env.local")
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

_load_env_local()
KAMIS_KEY = os.environ.get("KAMIS_CERT_KEY", "")
KAMIS_ID = os.environ.get("KAMIS_CERT_ID", "")
KMA_KEY = os.environ.get("KMA_SERVICE_KEY", "")

# ---- KAMIS 품목 코드 (도매·상품 기준). 최초 1회 코드표로 확인 권장 ----
#  category: 100 식량작물 / 200 채소류 / 400 과일류
KAMIS_ITEMS = {
    "배추":   {"cat": "200", "item": "211", "kind": "06"},  # 가을배추
    "무":     {"cat": "200", "item": "231", "kind": "06"},
    "사과":   {"cat": "400", "item": "411", "kind": "05"},  # 후지
    "쌀":     {"cat": "100", "item": "111", "kind": "01"},  # 일반계
    "시금치": {"cat": "200", "item": "264", "kind": "00"},
    "양파":   {"cat": "200", "item": "245", "kind": "00"},
}
CROP_META = {
    "배추": ("🥬", "원/kg"), "무": ("🌰", "원/kg"), "사과": ("🍎", "원/kg"),
    "쌀": ("🌾", "원/kg"), "시금치": ("🥬", "원/kg"), "양파": ("🧅", "원/kg"),
}
# 전국 대표 ASOS 관측소(서울108·대전133·광주156·대구143·전주146·춘천101) → 평균
KMA_STATIONS = [108, 133, 156, 143, 146, 101]

# 평년 강수(가뭄지수 산출 기준, mm)
CLIMO_RAIN = {1: 30, 2: 35, 3: 55, 4: 75, 5: 100, 6: 150, 7: 290, 8: 280, 9: 150, 10: 60, 11: 50, 12: 30}


def _get(url):
    with urlopen(url, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def months(start, end):
    sy, sm = map(int, start.split("-")); ey, em = map(int, end.split("-"))
    y, m = sy, sm
    while (y, m) <= (ey, em):
        yield y, m
        m += 1
        if m > 12: m = 1; y += 1


# ---------------- KAMIS 월별 도매가격 ----------------
def kamis_monthly(crop, year):
    """해당 연도 12개월 도매가격(원/kg) dict{month:price}"""
    c = KAMIS_ITEMS[crop]
    q = {
        "action": "monthlyPriceByCategoryList", "p_cert_key": KAMIS_KEY, "p_cert_id": KAMIS_ID,
        "p_returntype": "json", "p_yyyy": str(year), "p_period": "2",  # 2=월별
        "p_itemcategorycode": c["cat"], "p_itemcode": c["item"], "p_kindcode": c["kind"],
        "p_productrankcode": "04", "p_productclscode": "02",  # 02=도매, 04=상품
        "p_convert_kg_yn": "Y", "p_countrycode": "1101",
    }
    url = "https://www.kamis.or.kr/service/price/xml.do?" + urlencode(q)
    out = {}
    try:
        data = json.loads(_get(url))
        items = (data.get("data", {}) or {}).get("item", []) if isinstance(data.get("data"), dict) else data.get("data", [])
        for it in items or []:
            # 월 필드는 m1..m12 또는 'yyyymm' 형태 — 응답 구조에 맞춰 파싱
            for k, v in it.items():
                if k.startswith("m") and k[1:].isdigit():
                    try: out[int(k[1:])] = float(str(v).replace(",", ""))
                    except (ValueError, TypeError): pass
    except (URLError, HTTPError, ValueError) as e:
        print(f"  [KAMIS] {crop} {year} 실패: {e}")
    return out


# ---------------- 기상청 ASOS 일자료 → 월별 피처 ----------------
def kma_daily(station, start, end):
    """관측소 일자료 → {(y,m): {tas:[],rns:[],tmax:[],tmin:[]}}"""
    agg = {}
    for y, m in months(start, end):
        last = calendar.monthrange(y, m)[1]
        q = {
            "serviceKey": KMA_KEY, "dataType": "JSON", "dataCd": "ASOS", "dateCd": "DAY",
            "startDt": f"{y}{m:02d}01", "endDt": f"{y}{m:02d}{last:02d}",
            "stnIds": str(station), "numOfRows": "40", "pageNo": "1",
        }
        url = "http://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList?" + urlencode(q, safe="%")
        try:
            d = json.loads(_get(url))
            rows = d["response"]["body"]["items"]["item"]
            for r in rows:
                key = (y, m)
                a = agg.setdefault(key, {"tas": [], "rns": [], "tmax": [], "tmin": []})
                def f(x):
                    try: return float(x)
                    except (ValueError, TypeError): return None
                if f(r.get("avgTa")) is not None: a["tas"].append(f(r["avgTa"]))
                if f(r.get("maxTa")) is not None: a["tmax"].append(f(r["maxTa"]))
                if f(r.get("minTa")) is not None: a["tmin"].append(f(r["minTa"]))
                a["rns"].append(f(r.get("sumRn")) or 0.0)
            time.sleep(0.05)
        except (URLError, HTTPError, KeyError, ValueError) as e:
            print(f"  [KMA] stn{station} {y}-{m} 실패: {e}")
    return agg


def build_weather(start, end):
    """여러 관측소 평균 → 월별 피처(gen_data 스키마와 동일)"""
    per = [kma_daily(s, start, end) for s in KMA_STATIONS]
    rows = {}
    for y, m in months(start, end):
        tas, rns, tmax, tmin = [], [], [], []
        for ag in per:
            a = ag.get((y, m))
            if not a: continue
            tas += a["tas"]; rns.append(sum(a["rns"])); tmax += a["tmax"]; tmin += a["tmin"]
        if not tas: continue
        temp = sum(tas) / len(tas)
        rain = sum(rns) / len(rns) if rns else 0
        heat = sum(1 for t in tmax if t >= 33) // max(1, len(KMA_STATIONS))
        cold = sum(1 for t in tmin if t <= -12) // max(1, len(KMA_STATIONS))
        heavy = sum(1 for ag in per for d in [ag.get((y, m), {}).get("rns", [])] for x in d if x >= 80) // max(1, len(KMA_STATIONS))
        clim = CLIMO_RAIN[m]
        drought = max(0, min(100, round((clim - rain) / clim * 60 + max(0, heat) * 1.2)))
        rows[(y, m)] = {
            "year": y, "month": m, "date": f"{y}-{m:02d}",
            "temp": round(temp, 1), "rain_mm": round(rain), "sun_hr": 170,
            "heat_days": int(heat), "cold_days": int(cold), "heavy_rain_days": int(heavy),
            "drought_idx": int(drought), "frost": 0,
        }
    return rows


def main():
    if not (KAMIS_KEY and KAMIS_ID and KMA_KEY):
        st = lambda v: ("설정됨(" + v[:6] + "…)") if v else "없음"
        print("=" * 64)
        print(" 실데이터 수집 키 상태:")
        print(f"   KAMIS_CERT_KEY  : {st(KAMIS_KEY)}")
        print(f"   KAMIS_CERT_ID   : {st(KAMIS_ID)}   (KAMIS는 key와 id 둘 다 필요)")
        print(f"   KMA_SERVICE_KEY : {st(KMA_KEY)}   (기상청 날씨용)")
        missing = [n for n, v in [("KAMIS_CERT_ID", KAMIS_ID), ("KMA_SERVICE_KEY", KMA_KEY), ("KAMIS_CERT_KEY", KAMIS_KEY)] if not v]
        print(" 부족: " + ", ".join(missing))
        print(" → backend/data/.env.local 에 채우거나 환경변수로 설정 후 다시 실행하세요.")
        print("   발급: KAMIS https://www.kamis.or.kr · 기상청 https://www.data.go.kr")
        print(" 키가 부족해 dataset.json은 변경하지 않습니다(기존 보정 데이터 유지).")
        print("=" * 64)
        sys.exit(2)

    args = sys.argv
    start = args[args.index("--start") + 1] if "--start" in args else "2018-01"
    end = args[args.index("--end") + 1] if "--end" in args else "2025-12"
    years = sorted({y for y, _ in months(start, end)})

    print(f"[1/3] 기상청 ASOS 수집 {start}~{end} (관측소 {KMA_STATIONS}) ...")
    weather = build_weather(start, end)
    print(f"      → {len(weather)}개월 수집")

    print("[2/3] KAMIS 월별 도매가 수집 ...")
    prices = {c: {} for c in KAMIS_ITEMS}
    for crop in KAMIS_ITEMS:
        for y in years:
            mp = kamis_monthly(crop, y)
            for mo, p in mp.items():
                prices[crop][(y, mo)] = p
            time.sleep(0.1)
        print(f"      {crop}: {len(prices[crop])}개월")

    print("[3/3] dataset.json 작성 ...")
    rows = []
    for key in sorted(weather):
        w = dict(weather[key])
        pr = {}
        for crop in KAMIS_ITEMS:
            v = prices[crop].get(key)
            if v: pr[crop] = round(v)
        if len(pr) < len(KAMIS_ITEMS):
            continue  # 가격 결측 월 제외
        w["prices"] = pr
        rows.append(w)
    if not rows:
        print(" 수집 결과가 비었습니다. 코드/키를 확인하세요(--check). dataset.json 유지.")
        sys.exit(1)

    items = [{"name": k, "icon": CROP_META[k][0], "unit": CROP_META[k][1],
              "base": round(sum(r["prices"][k] for r in rows) / len(rows))} for k in KAMIS_ITEMS]
    normals = {k: round(sum(r["prices"][k] for r in rows) / len(rows)) for k in KAMIS_ITEMS}
    out = {
        "meta": {"title": "기후 식탁 데이터셋(실데이터)", "source": "KAMIS + 기상청 ASOS OpenAPI",
                 "period": f"{start} ~ {end} (월별)", "fetched": True},
        "events": [
            {"date": "2018-08", "label": "역대급 폭염", "desc": "관측사상 최고기온"},
            {"date": "2020-07", "label": "역대 최장 장마", "desc": "중부 54일"},
            {"date": "2022-08", "label": "수도권 집중호우", "desc": "시간당 100mm+"},
            {"date": "2023-04", "label": "사과 개화기 냉해", "desc": "2024 금사과 원인"},
            {"date": "2024-08", "label": "역대급 폭염", "desc": "김장물가 폭등"},
        ],
        "items": items, "normals": normals, "rows": rows,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f" 완료: {len(rows)}개월 실데이터 → dataset.json (source=KAMIS+ASOS)")


if __name__ == "__main__":
    main()
