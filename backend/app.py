# -*- coding: utf-8 -*-
"""
기후 식탁 (Climate Table) — 백엔드 서버
Python 표준 라이브러리만 사용. 의존성 0.
실행:  python backend/app.py   →  http://localhost:8000

REST API (JSON) + 정적 프론트엔드(frontend/) 서빙.
"""
import json, os, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model import ClimateModel, FEATURES  # noqa: E402
import dishes  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONT = os.path.join(ROOT, "frontend")
PORT = int(os.environ.get("PORT", "8000"))

MODEL = ClimateModel()

# 작물별 적응·해결 전략(교육 콘텐츠)
ADAPT = {
    "배추": ["고랭지 재배지 분산·차광시설로 폭염 대응", "스마트팜·시설재배로 기상 변동 흡수", "비축물량 방출 등 수급 안정 정책"],
    "무": ["배수 개선으로 호우 피해 저감", "파종 시기 조정으로 폭염 회피", "저장기술로 출하 시기 분산"],
    "사과": ["개화기 냉해 방지(미세살수·방상팬)", "고온 적응 품종·재배지 북상 대응", "수입·대체 과일로 가격 충격 완화"],
    "쌀": ["내재해성 품종 보급", "정부 비축·수급 관리 유지", "물 관리로 가뭄·태풍 대비"],
    "시금치": ["한파·폭염 모두 대비한 시설재배", "재배지 다변화", "근거리 유통으로 신선도·가격 안정"],
    "양파": ["저장시설 현대화로 연중 공급", "봄 기상 모니터링·조기경보", "주산지 분산으로 위험 분산"],
}

CLIMATE_NOTE = {
    "배추": "여름 폭염·가뭄에 가장 민감한 대표 작물. 2024년 폭염 때 '배추 한 포기 2만원'이 현실이 됐습니다.",
    "사과": "봄 개화기 냉해가 그 해 사과 생산을 좌우합니다. 2023년 냉해가 2024년 '금사과'를 만들었습니다.",
    "쌀": "정부 비축·수급관리로 기상 영향이 상대적으로 작습니다(낮은 설명력). 식량안보의 핵심.",
    "무": "배추와 함께 김장물가를 좌우합니다.",
    "시금치": "한파와 폭염 양쪽에 취약한 엽채류입니다.",
    "양파": "봄 수확·저장 작물로 봄 기상과 저장조건이 중요합니다.",
}

QUIZ = [
    # ── 개념 ──
    {"cat": "개념", "q": "'기후플레이션'이 뜻하는 것은?",
     "o": ["기후변화가 물가를 끌어올리는 현상", "기후가 좋아 물가가 내리는 현상", "계절 세일"], "a": 0,
     "fb": "기후(Climate)+인플레이션(Inflation). 이상기후가 작황을 악화시켜 먹거리 물가를 올리는 현상입니다."},
    {"cat": "개념", "q": "기후가 농산물 가격에 영향을 주는 경로로 가장 알맞은 것은?",
     "o": ["기상 → 작황(공급) → 가격", "기상 → 환율 → 가격", "기상과 가격은 무관"], "a": 0,
     "fb": "이상기후가 작황(공급)을 줄이면 공급 부족으로 가격이 오릅니다. 기상→작황→가격의 사슬입니다."},
    {"cat": "개념", "q": "국제 공동연구(PIK·ECB, 2024)는 기온 상승이 식품물가를 연 최대 몇 %p 올린다고 봤나?",
     "o": ["약 +0.1%p", "약 +3.2%p", "변화 없음"], "a": 1,
     "fb": "포츠담기후영향연구소·ECB는 2035년까지 연간 식품물가 상승률을 최대 +3.2%p 끌어올린다고 전망했습니다."},
    {"cat": "개념", "q": "폭염·가뭄이 채소 가격을 올리는 직접적인 이유는?",
     "o": ["생육 부진·수확량 감소로 공급이 줄어서", "택배비가 올라서", "소비자 입맛이 변해서"], "a": 0,
     "fb": "고온·물 부족은 작물 생육을 방해해 수확량을 줄이고, 공급 감소가 가격 상승으로 이어집니다."},
    # ── 사례 ──
    {"cat": "사례", "q": "2024년 여름 '배추 한 포기 2만원'의 직접적 원인은?",
     "o": ["역대급 폭염·가뭄", "갑작스러운 한파", "강수량 부족만"], "a": 0,
     "fb": "역대급 폭염과 가뭄으로 고랭지 배추 작황이 급감해 가격이 폭등했습니다(가락시장 도매 평년의 약 2배)."},
    {"cat": "사례", "q": "2024년 '금사과'(사과값 폭등)의 핵심 원인으로 가장 적절한 것은?",
     "o": ["겨울 폭설", "전년 봄 개화기 냉해", "여름 일조 과다"], "a": 1,
     "fb": "2023년 봄 개화기 저온·냉해로 착과가 줄어 이듬해 사과 도매가가 평년보다 120% 넘게 올랐습니다."},
    {"cat": "사례", "q": "2023년 8월 폭염 때 한 달 새 가격이 100% 넘게 뛴 품목 조합은?",
     "o": ["배추·무", "쌀·콩", "감자·고구마"], "a": 0,
     "fb": "2023년 8월 폭염으로 배추 +118%, 무 +128% 급등했습니다(엽채·뿌리채소가 고온에 취약)."},
    {"cat": "사례", "q": "2020년 농산물 가격에 큰 영향을 준 기상 사건은?",
     "o": ["역대 최장 장마(중부 약 54일)", "역대 최강 한파", "이른 봄 폭염"], "a": 0,
     "fb": "2020년 중부 약 54일의 역대 최장 장마로 일조가 급감해 채소 작황이 크게 나빠졌습니다."},
    {"cat": "사례", "q": "2024년 이상기후로 전 세계 가격이 사상 최고로 치솟은 기호식품은?",
     "o": ["코코아·커피", "설탕·소금", "생수"], "a": 0,
     "fb": "서아프리카 가뭄·병해 등으로 2024년 코코아·커피 국제가격이 사상 최고치를 기록했습니다(기후플레이션은 전 지구적)."},
    # ── 대응 ──
    {"cat": "대응", "q": "기후플레이션 '대응 방안'으로 적절하지 않은 것은?",
     "o": ["스마트팜·시설재배 확대", "내재해성 품종 보급", "기상예보 무시하고 관행대로 파종"], "a": 2,
     "fb": "기상예보·조기경보를 활용한 파종 시기 조정이 핵심 적응 전략입니다."},
    {"cat": "대응", "q": "정부가 배추·무 가격 급등에 쓰는 단기 수급안정 수단으로 알맞은 것은?",
     "o": ["비축물량 방출·할인 지원", "재배 전면 금지", "수입 전면 중단"], "a": 0,
     "fb": "비축물량 방출, 할인 지원, (필요 시) 수입 확대 등으로 단기 수급을 안정시킵니다."},
    {"cat": "대응", "q": "기후 변동에 강한 농업 기술로 보기 어려운 것은?",
     "o": ["스마트팜·시설재배", "내재해성(고온·내병) 품종", "노지에서 기상 무대비 재배"], "a": 2,
     "fb": "통제된 환경의 스마트팜과 내재해성 품종이 기상 충격을 줄입니다."},
    {"cat": "대응", "q": "소비자가 기후플레이션에 현명하게 대응하는 방법은?",
     "o": ["제철·대체 품목을 함께 활용", "한 품목만 사재기", "가격 정보 무시"], "a": 0,
     "fb": "값이 급등한 품목 대신 제철·대체 품목을 활용하면 부담을 줄일 수 있습니다."},
    # ── 데이터(문해력) ──
    {"cat": "데이터", "q": "모델의 '설명력(R²)'이 낮다는 것은 무슨 뜻인가?",
     "o": ["가격이 기상 외 요인에 많이 좌우됨", "기상이 가격을 100% 결정함", "데이터가 틀렸다는 뜻"], "a": 0,
     "fb": "R²이 낮으면 그 품목 가격은 정책·수급 등 비기상 요인의 영향이 크다는 의미입니다(예: 쌀)."},
    {"cat": "데이터", "q": "두 변수의 '상관관계가 높다'면 항상 '인과관계'일까?",
     "o": ["아니다 — 상관은 인과를 보장하지 않는다", "그렇다 — 늘 인과다", "상관과 인과는 같은 말"], "a": 0,
     "fb": "상관≠인과. 해석할 때는 메커니즘과 다른 요인을 함께 고려해야 합니다."},
    {"cat": "데이터", "q": "이 도구가 변동률을 비교하는 기준으로 옳은 것은?",
     "o": ["같은 시기 평년(정상) 기상 대비", "10년 전 가격 대비", "이웃나라 가격 대비"], "a": 0,
     "fb": "계절 효과를 빼고 '같은 시기 평년 기상 대비'로 비교해 순수 날씨 효과만 보여줍니다."},
    # ── 정책 ──
    {"cat": "정책", "q": "쌀 가격이 기상 변화에 상대적으로 둔감한 주된 이유는?",
     "o": ["정부 비축·수급관리", "쌀은 날씨와 무관해서", "수요가 없어서"], "a": 0,
     "fb": "쌀은 정부 비축과 수급관리로 가격이 안정적입니다 — 식량안보 정책의 효과입니다."},
    {"cat": "정책", "q": "식량안보를 가늠하는 핵심 지표로 알맞은 것은?",
     "o": ["식량자급률", "관광객 수", "휴대폰 보급률"], "a": 0,
     "fb": "식량자급률은 국내 소비를 자국 생산으로 얼마나 충당하는지를 보여주는 핵심 지표입니다."},
]

# 평년(보통) 기상 — '극단기상 없음' 기준. 날씨 효과·요인을 깔끔히 분리.
BASELINE = {"heat_days": 0, "cold_days": 0, "heavy_rain_days": 0, "drought_idx": 20, "frost": 0}

CONTENT = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
           ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8",
           ".png": "image/png", ".svg": "image/svg+xml", ".ico": "image/x-icon"}


def explain(crop, pred, ref, contribs):
    pct = round((pred - ref) / ref * 100)
    top = [c for c in contribs if abs(c["contrib"]) >= 20][:3]
    drivers = ", ".join(f"{c['label']}({'+' if c['contrib']>0 else ''}{c['contrib']}원)" for c in top)
    if pct >= 25:
        head = f"이 날씨면 같은 시기 평년보다 {pct}% 비싸집니다. 식탁 물가에 큰 부담입니다."
    elif pct >= 8:
        head = f"이 날씨면 같은 시기 평년보다 {pct}% 오릅니다."
    elif pct <= -8:
        head = f"이 날씨면 같은 시기 평년보다 {abs(pct)}% 저렴해집니다(풍작 경향)."
    else:
        head = "같은 시기 평년 날씨와 비슷한 수준입니다."
    body = f"주요 요인: {drivers}." if drivers else "기상 요인 영향이 크지 않습니다."
    return {"pct": pct, "headline": head, "drivers": body, "note": CLIMATE_NOTE.get(crop, "")}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass  # 조용히

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _err(self, msg, code=400):
        self._json({"error": msg}, code)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        u = urlparse(self.path)
        p = u.path
        q = parse_qs(u.query)
        try:
            if p == "/api/health":
                return self._json({"status": "ok", "crops": MODEL.items,
                                   "months": len(MODEL.rows),
                                   "source": MODEL.data.get("meta", {}).get("source", "보정 데이터(calibrated)")})
            if p == "/api/items":
                return self._json({"items": MODEL.data["items"], "normals": MODEL.normals,
                                   "events": MODEL.data["events"], "features": FEATURES})
            if p == "/api/series":
                crop = (q.get("item", [""])[0])
                if crop not in MODEL.items:
                    return self._err("unknown item")
                return self._json({"item": crop, "normal": MODEL.normals[crop],
                                   "r2": round(MODEL.r2[crop], 3), "series": MODEL.series(crop)})
            if p == "/api/model":
                crop = q.get("item", [""])[0]
                if crop not in MODEL.items:
                    return self._err("unknown item")
                return self._json({"item": crop, "r2": round(MODEL.r2[crop], 3),
                                   "reliability": MODEL.reliability(crop),
                                   "coefs": MODEL.coefs[crop]})
            if p == "/api/correlate":
                crop = q.get("item", [""])[0]
                if crop not in MODEL.items:
                    return self._err("unknown item")
                return self._json({"item": crop, "correlations": MODEL.correlations(crop)})
            if p == "/api/quiz":
                return self._json({"quiz": QUIZ})
            if p == "/api/dishes":
                return self._json({"dishes": dishes.all_dishes()})
            # 정적 파일
            return self._static(p)
        except Exception as e:  # noqa
            return self._err(f"server error: {e}", 500)

    def do_POST(self):
        u = urlparse(self.path)
        if u.path != "/api/simulate":
            return self._err("not found", 404)
        try:
            n = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(n) or b"{}")
            crop = body.get("item")
            if crop not in MODEL.items:
                return self._err("unknown item")
            month = int(body.get("month", 8))
            scen = {k: float(body.get(k, 0)) for k in FEATURES if k != "sun_dev"}
            if "sun_hr" in body:
                scen["sun_hr"] = float(body["sun_hr"])
            pred = MODEL.predict(crop, scen, month=month)
            normal = MODEL.normals[crop]
            # 같은 시기 평년 기상 기준 → 날씨 효과만 분리
            ref = MODEL.predict(crop, dict(BASELINE), month=month)
            # 기여도는 '평년 기상 대비 차이'로 계산 → 헤드라인(평년比 %)과 일치
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

    def _static(self, p):
        if p == "/" or p == "":
            p = "/index.html"
        safe = os.path.normpath(p).lstrip("\\/")
        fpath = os.path.join(FRONT, safe)
        if not os.path.abspath(fpath).startswith(os.path.abspath(FRONT)) or not os.path.isfile(fpath):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404")
            return
        ext = os.path.splitext(fpath)[1].lower()
        with open(fpath, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", CONTENT.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"기후 식탁 서버 → http://localhost:{PORT}  (crops={len(MODEL.items)}, months={len(MODEL.rows)})")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
