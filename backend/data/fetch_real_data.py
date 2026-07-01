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

# ---- KAMIS 품목/품종 코드 (productInfo 코드표로 확인). 도매=productclscode 02 ----
#  category: 100 식량작물 / 200 채소류 / 400 과일류
#  계절 품종(배추·무·사과)은 여러 kind를 우선순위로 이어붙여(stitch) 12개월을 채운다.
KAMIS_ITEMS = {
    "배추":   {"cat": "200", "item": "211", "kinds": ["06", "02", "01", "03"]},  # 월동·여름(고랭지)·봄·가을
    "무":     {"cat": "200", "item": "231", "kinds": ["06", "02", "01", "03"]},
    "사과":   {"cat": "400", "item": "411", "kinds": ["05", "06", "01", "07"]},  # 후지·아오리·홍로
    "쌀":     {"cat": "100", "item": "111", "kinds": ["01"]},                    # 20kg(일반계)
    "시금치": {"cat": "200", "item": "213", "kinds": ["00"]},
    "양파":   {"cat": "200", "item": "245", "kinds": ["00"]},
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


# ---------------- KAMIS 월별 도매가격 (monthlySalesList) ----------------
def _kamis_kind_month(cat, item, kind, year):
    """단일 품종의 해당 연도 도매 월가격 dict{month:price/kg}. 없으면 {}."""
    q = {
        "action": "monthlySalesList", "p_cert_key": KAMIS_KEY, "p_cert_id": KAMIS_ID,
        "p_returntype": "json", "p_yyyy": str(year), "p_period": "3",
        "p_itemcategorycode": cat, "p_itemcode": item, "p_kindcode": kind,
        "p_graderank": "2", "p_countycode": "1101", "p_convert_kg_yn": "Y",  # 도매·상품·전국·kg환산
    }
    out = {}
    try:
        d = json.loads(_get("https://www.kamis.or.kr/service/price/xml.do?" + urlencode(q)))
    except (URLError, HTTPError, ValueError):
        return out
    if str(d.get("error_code")) not in ("000", "0"):
        return out
    price = d.get("price")
    blocks = price if isinstance(price, list) else ([price] if isinstance(price, dict) else [])
    for blk in blocks:
        if not isinstance(blk, dict) or str(blk.get("productclscode")) != "02":  # 도매만
            continue
        its = blk.get("item", [])
        if isinstance(its, dict):
            its = [its]
        for row in its:
            if not isinstance(row, dict) or str(row.get("yyyy")) != str(year):
                continue
            for mo in range(1, 13):
                v = row.get(f"m{mo}")
                if v and str(v) not in ("-", ""):
                    try: out[mo] = float(str(v).replace(",", ""))
                    except (ValueError, TypeError): pass
    return out


def kamis_monthly(crop, year):
    """계절 품종을 우선순위로 stitch → 해당 연도 12개월 도매가격(원/kg) dict{month:price}."""
    c = KAMIS_ITEMS[crop]
    merged = {}
    for kind in c["kinds"]:
        mp = _kamis_kind_month(c["cat"], c["item"], kind, year)
        for mo, v in mp.items():
            merged.setdefault(mo, v)  # 우선순위(앞 품종)가 그 달을 차지
        time.sleep(0.05)
    return merged


def interpolate_gaps(series):
    """{(y,m):price} 의 빈 월을 양옆 실측값으로 선형 보간(앞뒤 없으면 최근값 캐리)."""
    keys = sorted(series.keys())
    if not keys:
        return series, 0
    # 전체 타임라인(첫~끝 월) 생성
    (sy, sm), (ey, em) = keys[0], keys[-1]
    timeline = []
    y, m = sy, sm
    while (y, m) <= (ey, em):
        timeline.append((y, m)); m += 1
        if m > 12: m = 1; y += 1
    filled, gaps = dict(series), 0
    for i, k in enumerate(timeline):
        if k in filled:
            continue
        gaps += 1
        prev = next((timeline[j] for j in range(i - 1, -1, -1) if timeline[j] in series), None)
        nxt = next((timeline[j] for j in range(i + 1, len(timeline)) if timeline[j] in series), None)
        if prev and nxt:
            span = timeline.index(nxt) - timeline.index(prev)
            step = (series[nxt] - series[prev]) / span
            filled[k] = round(series[prev] + step * (i - timeline.index(prev)))
        elif prev:
            filled[k] = series[prev]
        elif nxt:
            filled[k] = series[nxt]
    return filled, gaps


# ---------------- 기상청 ASOS 일자료 → 월별 피처 ----------------
def _kma_url(params):
    """기상청 serviceKey는 '일반 인증키(Encoding)'를 그대로 붙인다(이중 인코딩 방지)."""
    base = "http://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList"
    return f"{base}?serviceKey={KMA_KEY}&" + urlencode(params)


def kma_daily(station, start, end):
    """관측소 일자료 → {(y,m): {tas,rns,tmax,tmin,sun(일조시간)}}"""
    agg = {}
    for y, m in months(start, end):
        last = calendar.monthrange(y, m)[1]
        params = {
            "dataType": "JSON", "dataCd": "ASOS", "dateCd": "DAY",
            "startDt": f"{y}{m:02d}01", "endDt": f"{y}{m:02d}{last:02d}",
            "stnIds": str(station), "numOfRows": "50", "pageNo": "1",
        }
        try:
            d = json.loads(_get(_kma_url(params)))
            rows = d["response"]["body"]["items"]["item"]
            def f(x):
                try: return float(x)
                except (ValueError, TypeError): return None
            for r in rows:
                a = agg.setdefault((y, m), {"tas": [], "rns": [], "tmax": [], "tmin": [], "sun": []})
                if f(r.get("avgTa")) is not None: a["tas"].append(f(r["avgTa"]))
                if f(r.get("maxTa")) is not None: a["tmax"].append(f(r["maxTa"]))
                if f(r.get("minTa")) is not None: a["tmin"].append(f(r["minTa"]))
                if f(r.get("sumSsHr")) is not None: a["sun"].append(f(r["sumSsHr"]))  # 일조시간(시간)
                a["rns"].append(f(r.get("sumRn")) or 0.0)
            time.sleep(0.05)
        except (URLError, HTTPError, KeyError, ValueError) as e:
            print(f"  [KMA] stn{station} {y}-{m} 실패: {e}")
    return agg


def build_weather(start, end):
    """여러 관측소 평균 → 월별 피처(gen_data 스키마와 동일).
       sun_hr=실제 일조시간 합, frost=4월 서리(일최저≤1.5℃ 일수)를 연중 전파(금사과)."""
    per = [kma_daily(s, start, end) for s in KMA_STATIONS]
    n = max(1, len(KMA_STATIONS))

    # 개화기 냉해: 관측소별 '4월 일최저 ≤ 1.5℃ 일수' 평균 → 연도별 봄 서리 강도
    spring = {}
    for y, m in months(start, end):
        if m != 4:
            continue
        cnts = []
        for ag in per:
            tmins = ag.get((y, m), {}).get("tmin", [])
            if tmins:
                cnts.append(sum(1 for t in tmins if t <= 1.5))
        if cnts:
            spring[y] = round(sum(cnts) / len(cnts))

    rows = {}
    for y, m in months(start, end):
        tas, rns, tmax, tmin, suns = [], [], [], [], []
        for ag in per:
            a = ag.get((y, m))
            if not a: continue
            tas += a["tas"]; rns.append(sum(a["rns"])); tmax += a["tmax"]; tmin += a["tmin"]
            if a.get("sun"): suns.append(sum(a["sun"]))
        if not tas: continue
        temp = sum(tas) / len(tas)
        rain = sum(rns) / len(rns) if rns else 0
        sun_hr = round(sum(suns) / len(suns)) if suns else 170      # 관측소 평균 월 일조시간 합
        heat = sum(1 for t in tmax if t >= 33) // n
        cold = sum(1 for t in tmin if t <= -12) // n
        heavy = sum(1 for ag in per for x in ag.get((y, m), {}).get("rns", []) if x >= 80) // n
        clim = CLIMO_RAIN[m]
        drought = max(0, min(100, round((clim - rain) / clim * 60 + max(0, heat) * 1.2)))
        # 그 해 4월 서리는 5월~연말에, 이듬해 1~4월까지 지속 반영(사과 '금사과' 시차 효과)
        frost = spring.get(y, 0) if m >= 5 else spring.get(y - 1, 0)
        rows[(y, m)] = {
            "year": y, "month": m, "date": f"{y}-{m:02d}",
            "temp": round(temp, 1), "rain_mm": round(rain), "sun_hr": int(sun_hr),
            "heat_days": int(heat), "cold_days": int(cold), "heavy_rain_days": int(heavy),
            "drought_idx": int(drought), "frost": int(frost),
        }
    return rows


def derive_prices_from_weather(weather):
    """KAMIS 키가 없을 때: 실측 ASOS 기상 + gen_data 민감도 모델로 가격을 추정한다.
       (합성 가격을 그대로 쓰지 않고 '실측 기상'에서 다시 산출 → 기상→가격 인과 결합 유지)"""
    sys.path.insert(0, HERE)
    import gen_data  # 같은 폴더. import만으로 생성을 돌리지 않음(생성은 __main__ 보호).
    gen_data.random.seed(20260619)
    rows, prev = [], {k: None for k in gen_data.CROPS}
    for key in sorted(weather):
        w = dict(weather[key])
        pr = {}
        for crop in gen_data.CROPS:
            p = gen_data.price_for(crop, w, prev[crop])
            pr[crop] = p
            prev[crop] = p
        w["prices"] = pr
        rows.append(w)
    items = [{"name": k, "icon": v["icon"], "unit": v["unit"], "base": v["base"]}
             for k, v in gen_data.CROPS.items()]
    normals = {k: round(sum(r["prices"][k] for r in rows) / len(rows)) for k in gen_data.CROPS}
    return rows, items, normals


def main():
    args = sys.argv
    have_kamis = bool(KAMIS_KEY and KAMIS_ID)
    # 기상(ASOS) 키는 필수, KAMIS(가격) 키는 선택 — 없으면 실측 기상 기반 가격 추정으로 진행
    if not KMA_KEY:
        st = lambda v: ("설정됨(" + v[:6] + "…)") if v else "없음"
        print("=" * 64)
        print(" 기상청 ASOS 키(KMA_SERVICE_KEY)가 필요합니다(필수).")
        print(f"   KMA_SERVICE_KEY : {st(KMA_KEY)}")
        print(f"   KAMIS_CERT_KEY  : {st(KAMIS_KEY)}  /  KAMIS_CERT_ID : {st(KAMIS_ID)}  (가격용, 선택)")
        print(" → backend/data/.env.local 에 KMA_SERVICE_KEY 를 채운 뒤 다시 실행하세요.")
        print("   발급: 기상청 https://www.data.go.kr · KAMIS https://www.kamis.or.kr")
        print(" 키가 없어 dataset.json은 변경하지 않습니다(기존 데이터 유지).")
        print("=" * 64)
        sys.exit(2)

    start = args[args.index("--start") + 1] if "--start" in args else "2018-01"
    end = args[args.index("--end") + 1] if "--end" in args else "2025-12"
    years = sorted({y for y, _ in months(start, end)})

    # --check: 전체 96개월 수집 전에 키·코드가 맞는지 샘플 1회로 검증
    if "--check" in args:
        print("[check] 샘플 호출로 키·코드 검증 (dataset.json은 변경하지 않음)")
        y, m = 2024, 8
        last = calendar.monthrange(y, m)[1]
        kurl = _kma_url({"dataType": "JSON", "dataCd": "ASOS", "dateCd": "DAY",
                         "startDt": f"{y}{m:02d}01", "endDt": f"{y}{m:02d}{last:02d}",
                         "stnIds": "108", "numOfRows": "5", "pageNo": "1"})
        try:
            print("  [KMA] 응답 앞부분:", _get(kurl)[:320])
        except (URLError, HTTPError, ValueError) as e:
            print("  [KMA] 실패:", e)
        if have_kamis:
            print("  [KAMIS] 2024 도매 월 커버리지(품종 stitch 후):")
            for crop in KAMIS_ITEMS:
                mp = kamis_monthly(crop, 2024)
                ex = [mp[m] for m in sorted(mp)[:2]]
                print(f"    {crop}: {len(mp)}개월 {sorted(mp)}  예시={ex}")
        else:
            print("  [KAMIS] 키 없음 — 가격은 실측 기상 기반 추정으로 진행됩니다.")
        print("[check] 위 응답에 정상 데이터가 보이면 --check 없이 본 수집을 실행하세요.")
        sys.exit(0)

    steps = "3" if have_kamis else "2"
    print(f"[1/{steps}] 기상청 ASOS 실측 수집 {start}~{end} (관측소 {KMA_STATIONS}) ...")
    weather = build_weather(start, end)
    print(f"      → {len(weather)}개월 수집")
    if not weather:
        print(" ASOS 수집 결과가 비었습니다(키/관측소 확인). dataset.json 유지.")
        sys.exit(1)

    if have_kamis:
        print(f"[2/{steps}] KAMIS 월별 도매가 수집(계절 품종 stitch) ...")
        prices = {c: {} for c in KAMIS_ITEMS}
        for crop in KAMIS_ITEMS:
            for y in years:
                for mo, p in kamis_monthly(crop, y).items():
                    prices[crop][(y, mo)] = p
            raw_n = len(prices[crop])
            prices[crop], gaps = interpolate_gaps(prices[crop])
            print(f"      {crop}: 실측 {raw_n}개월 + 비수기 보간 {gaps}개월")
        print(f"[3/{steps}] dataset.json 작성 (기상·가격 모두 실측) ...")
        rows = []
        for key in sorted(weather):
            w = dict(weather[key])
            pr = {c: round(prices[c][key]) for c in KAMIS_ITEMS if prices[c].get(key)}
            if len(pr) < len(KAMIS_ITEMS):
                continue  # 일부 작물 가격 결측 월 제외
            w["prices"] = pr
            rows.append(w)
        if not rows:
            print(" 가격 수집이 비었습니다. KAMIS 코드/키를 --check로 확인하세요. dataset.json 유지.")
            sys.exit(1)
        items = [{"name": k, "icon": CROP_META[k][0], "unit": CROP_META[k][1],
                  "base": round(sum(r["prices"][k] for r in rows) / len(rows))} for k in KAMIS_ITEMS]
        normals = {k: round(sum(r["prices"][k] for r in rows) / len(rows)) for k in KAMIS_ITEMS}
        source = ("기상=기상청 기상자료개방포털 ASOS 일자료(종관관측) OpenAPI 실측 · "
                  "가격=KAMIS OpenAPI 실측 도매가(계절 품종 결합, 비수기 일부 월 선형보간)")
        price_real = True
    else:
        print(f"[2/{steps}] KAMIS 키 없음 → 실측 기상 기반 가격 추정(민감도 모델). dataset.json 작성 ...")
        print("      ※ KAMIS_CERT_KEY+CERT_ID 입력 후 재실행하면 실측 도매가로 자동 교체됩니다.")
        rows, items, normals = derive_prices_from_weather(weather)
        source = ("기상=기상청 기상자료개방포털 ASOS 일자료(종관관측) OpenAPI 실측 · "
                  "가격=실측 기상에 작물 민감도 모델 적용한 추정값(KAMIS 실가격 키 발급 후 교체 예정)")
        price_real = False

    out = {
        "meta": {"title": "기후 식탁 데이터셋(실데이터)", "source": source,
                 "period": f"{start} ~ {end} (월별)", "fetched": True, "price_real": price_real,
                 "features": ["temp", "rain_mm", "sun_hr", "heat_days", "cold_days",
                              "heavy_rain_days", "drought_idx", "frost"],
                 "note": "실측 ASOS 일자료를 월 피처로 집계(폭염≥33℃·한파≤-12℃·호우≥80mm·가뭄=평년강수대비·서리=4월 일최저≤1.5℃ 연중 전파)."},
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
    tag = "기상·가격 실측" if price_real else "기상 실측 + 가격 추정"
    print(f" 완료: {len(rows)}개월 → dataset.json ({tag})")


if __name__ == "__main__":
    main()
