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

# 하이브리드: 표시(차트·평년·밥상)는 실측 KAMIS 그대로, 시뮬레이터 인과는 도메인 부호 보존.
# 작물별 기상 민감도(원/kg, 양수=악천후→가격 상승). gen_data 모델과 동일한 물리 우선값.
_SENS = {
    "배추":   {"heat": 82, "drought": 26.0, "heavy_rain": 70, "cold": 34, "frost": 0,   "sun": -2.6},
    "무":     {"heat": 62, "drought": 22.0, "heavy_rain": 48, "cold": 22, "frost": 0,   "sun": -1.8},
    "사과":   {"heat": 18, "drought": 12.0, "heavy_rain": 34, "cold": 2,  "frost": 470, "sun": -3.2},
    "쌀":     {"heat": 3,  "drought": 4.0,  "heavy_rain": 9,  "cold": 1,  "frost": 0,   "sun": -1.0},
    "시금치": {"heat": 28, "drought": 12.0, "heavy_rain": 22, "cold": 24, "frost": 6,   "sun": -1.5},
    "양파":   {"heat": 10, "drought": 14.0, "heavy_rain": 12, "cold": 6,  "frost": 10,  "sun": -0.8},
}


def _prior_coef(crop):
    """설계행렬 순서 [1, FEATURES.., sin, cos] 의 계수 사전(prior). 악천후 피처는 모두 양(+)."""
    s = _SENS.get(crop, {})
    feat = {
        "heat_days": s.get("heat", 0), "cold_days": s.get("cold", 0),
        "heavy_rain_days": s.get("heavy_rain", 0), "drought_idx": s.get("drought", 0) / 10.0,
        "frost": s.get("frost", 0) / 10.0, "sun_dev": -s.get("sun", 0),
    }
    return [0.0] + [float(feat[k]) for k in FEATURES] + [0.0, 0.0]


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


def _solve(A, b, ridge=1.0, prior=None):
    """정규방정식 (AᵀA + λI) x = Aᵀb + λ·prior 를 가우스 소거로 푼다.
       prior가 있으면 ||Ax-b||² + λ·||x-prior||² 를 최소화(도메인 우선값으로 수축)."""
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
    for p in range(1, n):  # 절편 제외 릿지(+prior 수축)
        AtA[p][p] += ridge
        if prior is not None:
            Atb[p] += ridge * prior[p]
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
        n = len(A)
        for crop in self.items:
            y = [r["prices"][crop] for r in self.rows]
            ybar = sum(y) / n
            ss_tot = sum((v - ybar) ** 2 for v in y) or 1.0

            # (1) 신뢰도용: 제약 없는 실측 회귀의 R² = '기상이 실제 가격을 설명하는 비율'(정직)
            emp = _solve(A, y, ridge=18.0)
            ss_res = sum((y[i] - sum(c * x for c, x in zip(emp, A[i]))) ** 2 for i in range(n))
            self.r2[crop] = max(0.0, 1 - ss_res / ss_tot)

            # (2) 시뮬레이터용 인과 계수: 실측으로 학습 + 도메인 우선값 수축 + 악천후 부호 바닥 고정
            prior = _prior_coef(crop)
            coef = _solve(A, y, ridge=42.0, prior=prior)
            for i in range(len(FEATURES)):
                floor = max(0.0, 0.5 * prior[i + 1])
                if coef[i + 1] < floor:
                    coef[i + 1] = floor
            # (3) 레벨 보정: 평균 기상에서 예측 평균 = 실측 평균이 되도록 절편 재중심(평년比% 정합)
            mean_pred = sum(sum(c * x for c, x in zip(coef, A[i])) for i in range(n)) / n
            coef[0] += ybar - mean_pred
            self.coefs[crop] = coef

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
        """기상 민감도(모델): 각 피처가 이 작물 가격에 주는 표준화 영향(부호=인과, 정규화 -1~1).
           시뮬레이터·기여요인과 동일한 인과 모델에서 산출 → 화면 전체 정합."""
        coef = self.coefs[crop]
        n = len(self.rows)
        out = []
        for i, k in enumerate(FEATURES):
            xs = [_feat_row(r)[k] for r in self.rows]
            xb = sum(xs) / n
            sd = math.sqrt(sum((x - xb) ** 2 for x in xs) / n)
            out.append({"feature": k, "label": FEATURE_LABELS[k], "eff": coef[i + 1] * sd})
        mx = max((abs(o["eff"]) for o in out), default=1.0) or 1.0
        for o in out:
            o["r"] = round(o["eff"] / mx, 3)
            del o["eff"]
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
