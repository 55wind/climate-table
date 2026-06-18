# -*- coding: utf-8 -*-
"""
기후 식탁 — 통합 검증 스크립트 (표준 라이브러리만)
서버를 임시 포트에 스레드로 띄우고 전 엔드포인트·경계값을 자동 점검한다.
실행:  python backend/test_api.py   (종료코드 0=통과, 1=실패)
"""
import json, os, sys, threading, time
from http.server import ThreadingHTTPServer
from urllib.request import urlopen, Request
from urllib.error import HTTPError

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app  # noqa: E402

PORT = 8765
BASE = f"http://127.0.0.1:{PORT}"
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("  PASS " if cond else "  FAIL ") + name + (f" — {detail}" if detail and not cond else ""))


def get(path):
    try:
        with urlopen(BASE + path, timeout=5) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def post(path, obj):
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    req = Request(BASE + path, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def run_checks():
    # health
    s, d = get("/api/health")
    check("health 200", s == 200)
    check("health crops=6", len(d.get("crops", [])) == 6)
    check("health months=96", d.get("months") == 96)

    # items
    s, d = get("/api/items")
    check("items 200", s == 200)
    check("items 6종+normals+events", len(d["items"]) == 6 and len(d["normals"]) == 6 and len(d["events"]) >= 3)

    # series
    s, d = get("/api/series?item=%EB%B0%B0%EC%B6%94")  # 배추
    check("series 배추 200", s == 200)
    check("series 96포인트", len(d["series"]) == 96)
    check("series r2 범위", 0 <= d["r2"] <= 1)

    # correlate
    s, d = get("/api/correlate?item=%EC%82%AC%EA%B3%BC")  # 사과
    check("correlate 사과", s == 200 and len(d["correlations"]) == 6)

    # quiz
    s, d = get("/api/quiz")
    check("quiz >=5문항", s == 200 and len(d["quiz"]) >= 5)

    # simulate — 배추 폭염 시나리오 → 평년 대비 상승
    s, d = post("/api/simulate", {"item": "배추", "heat_days": 30, "drought_idx": 80, "heavy_rain_days": 4, "month": 8})
    check("simulate 배추 200", s == 200)
    check("simulate predicted>0", d.get("predicted", 0) > 0)
    check("simulate 폭염→상승", d["explain"]["pct"] > 10, f"pct={d['explain']['pct']}")
    check("simulate adapt 존재", len(d.get("adapt", [])) >= 1)

    # simulate — 사과 냉해 → 상승
    s, d = post("/api/simulate", {"item": "사과", "frost": 70, "month": 11})
    check("simulate 사과 냉해→상승", d["explain"]["pct"] > 8, f"pct={d['explain']['pct']}")

    # 경계값/에러 처리
    s, d = post("/api/simulate", {"item": "없는작물"})
    check("simulate 잘못된 작물 400", s == 400 and "error" in d)
    s, d = get("/api/series?item=xxx")
    check("series 잘못된 작물 400", s == 400)
    # 빈 시나리오(0) — 평년 근처, 에러 없어야
    s, d = post("/api/simulate", {"item": "쌀"})
    check("simulate 빈 시나리오 정상", s == 200 and d["predicted"] > 0)


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), app.Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    time.sleep(0.4)
    print("통합 검증 시작 →", BASE)
    try:
        run_checks()
    finally:
        srv.shutdown()
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\n결과: {passed}/{total} 통과")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
