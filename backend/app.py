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
    {"q": "2024년 여름 '배추 한 포기 2만원'의 직접적 원인은?",
     "o": ["역대급 폭염·가뭄", "갑작스러운 한파", "강수량 부족만"], "a": 0,
     "fb": "역대급 폭염과 가뭄으로 고랭지 배추 작황이 급감해 가격이 폭등했습니다."},
    {"q": "2024년 '금사과'(사과값 폭등)의 핵심 원인으로 가장 적절한 것은?",
     "o": ["겨울 폭설", "전년 봄 개화기 냉해", "여름 일조 과다"], "a": 1,
     "fb": "2023년 봄 개화기 저온·냉해로 착과가 줄어 이듬해 사과 생산·가격에 큰 영향을 줬습니다."},
    {"q": "다음 중 기상 변화에 가격이 가장 둔감한(설명력이 낮은) 품목은?",
     "o": ["배추", "쌀", "시금치"], "a": 1,
     "fb": "쌀은 정부 비축·수급관리 덕분에 기상 영향이 상대적으로 작습니다."},
    {"q": "'기후플레이션'이 뜻하는 것은?",
     "o": ["기후변화가 물가를 끌어올리는 현상", "기후가 좋아 물가가 내리는 현상", "계절 세일"], "a": 0,
     "fb": "기후(Climate)+인플레이션(Inflation). 이상기후가 작황을 악화시켜 먹거리 물가를 올리는 현상입니다."},
    {"q": "기후플레이션 대응 방안으로 적절하지 않은 것은?",
     "o": ["스마트팜·시설재배 확대", "내재해성 품종 보급", "기상예보 무시하고 관행대로 파종"], "a": 2,
     "fb": "기상예보·조기경보를 활용한 파종 시기 조정이 핵심 적응 전략입니다."},
]

# 평년(보통) 기상 — 시나리오의 '날씨 효과'를 분리하기 위한 같은-시기 비교 기준
BASELINE = {"heat_days": 6, "cold_days": 2, "heavy_rain_days": 2, "drought_idx": 20, "frost": 0}

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
            contribs = MODEL.contributions(crop, scen, month=month)
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
