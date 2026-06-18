# -*- coding: utf-8 -*-
"""
기후 식탁 — 회귀 모델 (표준 라이브러리만)
월별 데이터로 작물별 '기상 → 가격' 선형회귀(릿지 정규화)를 학습하고,
시나리오 예측·상관분석·설명력(R²)을 제공한다.
"""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(HERE, "data", "dataset.json")

# 회귀 피처 순서(시나리오 입력과 일치해야 함)
FEATURES = ["heat_days", "cold_days", "heavy_rain_days", "drought_idx", "frost", "sun_dev"]
FEATURE_LABELS = {
    "heat_days": "폭염일수", "cold_days": "한파일수", "heavy_rain_days": "호우일수",
    "drought_idx": "가뭄지수", "frost": "개화기냉해", "sun_dev": "일조부족",
}


def _feat_row(r):
    """원시 행 → 피처 dict"""
    return {
        "heat_days": r["heat_days"],
        "cold_days": r["cold_days"],
        "heavy_rain_days": r["heavy_rain_days"],
        "drought_idx": r["drought_idx"],
        "frost": r["frost"],
        "sun_dev": (170 - r["sun_hr"]) / 10.0,  # 일조 부족(양수=흐림)
    }


def _design(r):
    """설계행렬 한 행: [1, features..., sin(month), cos(month)]"""
    f = _feat_row(r)
    m = r["month"]
    row = [1.0] + [float(f[k]) for k in FEATURES]
    row.append(math.sin(2 * math.pi * m / 12))
    row.append(math.cos(2 * math.pi * m / 12))
    return row


def _solve(A, b, ridge=1.0):
    """정규방정식 (AᵀA + λI) x = Aᵀb 를 가우스 소거로 푼다."""
    n = len(A[0])
    # AtA, Atb
    AtA = [[0.0] * n for _ in range(n)]
    Atb = [0.0] * n
    for i in range(len(A)):
        ai = A[i]
        bi = b[i]
        for p in range(n):
            Atb[p] += ai[p] * bi
            aip = ai[p]
            row = AtA[p]
            for q in range(n):
                row[q] += aip * ai[q]
    for p in range(1, n):  # 절편 제외 릿지
        AtA[p][p] += ridge
    # 가우스 소거
    M = [AtA[i][:] + [Atb[i]] for i in range(n)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[piv][col]) < 1e-12:
            continue
        M[col], M[piv] = M[piv], M[col]
        pv = M[col][col]
        for j in range(col, n + 1):
            M[col][j] /= pv
        for r in range(n):
            if r != col and abs(M[r][col]) > 1e-12:
                fac = M[r][col]
                for j in range(col, n + 1):
                    M[r][j] -= fac * M[col][j]
    return [M[i][n] for i in range(n)]


class ClimateModel:
    def __init__(self):
        with open(DATA_PATH, encoding="utf-8") as f:
            self.data = json.load(f)
        self.rows = self.data["rows"]
        self.items = [it["name"] for it in self.data["items"]]
        self.normals = self.data["normals"]
        self.coefs = {}   # crop -> coef vector
        self.r2 = {}      # crop -> R²
        self._fit_all()

    def _fit_all(self):
        A = [_design(r) for r in self.rows]
        for crop in self.items:
            y = [r["prices"][crop] for r in self.rows]
            coef = _solve(A, y, ridge=18.0)
            self.coefs[crop] = coef
            # R²
            ybar = sum(y) / len(y)
            ss_tot = sum((v - ybar) ** 2 for v in y) or 1.0
            ss_res = 0.0
            for i in range(len(A)):
                pred = sum(c * x for c, x in zip(coef, A[i]))
                ss_res += (y[i] - pred) ** 2
            self.r2[crop] = max(0.0, 1 - ss_res / ss_tot)

    def predict(self, crop, scenario, month=8):
        """scenario: dict with FEATURES 키(sun_dev 또는 sun_hr 허용)"""
        coef = self.coefs[crop]
        sc = dict(scenario)
        if "sun_dev" not in sc and "sun_hr" in sc:
            sc["sun_dev"] = (170 - sc["sun_hr"]) / 10.0
        row = [1.0] + [float(sc.get(k, 0)) for k in FEATURES]
        row.append(math.sin(2 * math.pi * month / 12))
        row.append(math.cos(2 * math.pi * month / 12))
        pred = sum(c * x for c, x in zip(coef, row))
        return max(round(pred / 10) * 10, 200)

    def contributions(self, crop, scenario, month=8):
        """각 피처가 가격에 더한 기여액(원/kg) — 설명용"""
        coef = self.coefs[crop]
        sc = dict(scenario)
        if "sun_dev" not in sc and "sun_hr" in sc:
            sc["sun_dev"] = (170 - sc["sun_hr"]) / 10.0
        out = []
        for i, k in enumerate(FEATURES):
            out.append({"feature": k, "label": FEATURE_LABELS[k],
                        "contrib": round(coef[i + 1] * float(sc.get(k, 0)))})
        out.sort(key=lambda d: abs(d["contrib"]), reverse=True)
        return out

    def correlations(self, crop):
        """피처별 가격과의 피어슨 상관"""
        ys = [r["prices"][crop] for r in self.rows]
        n = len(ys)
        ybar = sum(ys) / n
        out = []
        for k in FEATURES:
            xs = [_feat_row(r)[k] for r in self.rows]
            xbar = sum(xs) / n
            num = sum((xs[i] - xbar) * (ys[i] - ybar) for i in range(n))
            dx = math.sqrt(sum((x - xbar) ** 2 for x in xs))
            dy = math.sqrt(sum((y - ybar) ** 2 for y in ys))
            r = num / (dx * dy) if dx > 0 and dy > 0 else 0.0
            out.append({"feature": k, "label": FEATURE_LABELS[k], "r": round(r, 3)})
        out.sort(key=lambda d: abs(d["r"]), reverse=True)
        return out

    def reliability(self, crop):
        """모델 설명력(R²)을 교육용 신뢰도 등급으로 변환"""
        r = self.r2.get(crop, 0)
        if r >= 0.7:
            return {"level": "high", "label": "높음", "r2": round(r, 2),
                    "reason": "가격 변동의 대부분을 기상으로 설명할 수 있습니다."}
        if r >= 0.4:
            return {"level": "mid", "label": "보통", "r2": round(r, 2),
                    "reason": "기상 영향이 뚜렷하지만 수급·유통 등 다른 요인도 함께 작용합니다."}
        return {"level": "low", "label": "낮음", "r2": round(r, 2),
                "reason": "정부 비축·수급관리 등 비(非)기상 요인이 가격을 크게 좌우합니다."}

    def series(self, crop):
        return [{"date": r["date"], "price": r["prices"][crop],
                 "heat_days": r["heat_days"], "heavy_rain_days": r["heavy_rain_days"],
                 "drought_idx": r["drought_idx"], "cold_days": r["cold_days"]}
                for r in self.rows]


if __name__ == "__main__":
    m = ClimateModel()
    for crop in m.items:
        print(crop, "R2=", round(m.r2[crop], 3), "normal=", m.normals[crop])
    print("예시 배추 폭염30·가뭄80 예측:",
          m.predict("배추", {"heat_days": 30, "drought_idx": 80, "heavy_rain_days": 4}, month=8))
