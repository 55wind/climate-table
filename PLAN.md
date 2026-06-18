# 기후 식탁 (Climate Table) — 개발 계획 & /loop 작업 큐

> **/loop 운영 규칙 (토큰 최적화)**
> 1. 매 반복: `PROGRESS.md`를 먼저 읽어 현재 상태 파악(대화 맥락 의존 X).
> 2. 아래 작업 큐에서 `[ ]` 미완료 항목 중 **가장 위 1개만** 수행.
> 3. 해당 작업에 필요한 파일만 열고, 작은 단위로 편집.
> 4. 검증(서버 기동 + curl/headless 1~2개 핵심 체크). **오류 0% 확인.**
> 5. 통과 시 커밋(원자적). `PLAN.md` 항목을 `[x]`로, `PROGRESS.md`에 1~3줄 기록.
> 5b. **매 반복마다 PushNotification으로 모바일 알림 전송**(status: proactive). 형식: "[기후식탁] T## 완료: <한 줄 요약> (남은 N개)" 또는 실패 시 "[기후식탁] T## 실패: <원인>". 200자 이내 1줄.
> 6. 실패 시 원인만 기록하고 다음 반복에서 재시도(무한 재시도 금지: 같은 작업 3회 실패 시 SKIP 표시).
> 7. 큐가 모두 `[x]`면 "완료" 기록 + 최종 PushNotification "[기후식탁] 전체 작업 완료 🎉" 전송 후 루프 종료(추가 토큰 낭비 금지).

## 컨셉
한반도 폭염·가뭄·호우·한파 시나리오를 조작 → 백엔드 회귀모델이 농산물(배추·무·사과·쌀·시금치·양파) 가격을 예측. 최근 사회문제 **기후플레이션**을 학습하고 적응·해결방안을 탐색하는 인터랙티브 교육 웹앱.

## 아키텍처
- **백엔드**: Python 표준 라이브러리만 (`http.server`). REST JSON API + 정적 프론트 서빙. 회귀모델 순수 파이썬. 의존성 0 → `python backend/app.py`.
- **프론트엔드**: Vanilla JS + Canvas(차트 직접 렌더, CDN 의존 0 → 오프라인·0%오류).
- **데이터**: `backend/data/` 의 CSV/JSON. 실제 한국 기후·작황 사건(2024 폭염 배추, 금사과 등) 기반 모델링. 출처·근사 여부 README에 명시.

## API 설계
- `GET /api/health` → {status}
- `GET /api/items` → 작물 목록 + 메타
- `GET /api/series?item=배추` → 월별 시계열(날씨 피처 + 실제가격)
- `GET /api/model?item=배추` → 회귀계수 + R²(설명력)
- `POST /api/simulate` {item, heat_days, rain_mm, drought, cold_days, frost} → 예측가격 + 평년대비 % + 해설
- `GET /api/correlate?item=배추` → 피처별 상관계수
- `GET /api/quiz` → 학습 퀴즈 문항
- `GET /api/tutor?...` → 규칙기반 해설(옵션: LLM 연동 자리)

## 작업 큐 (위에서부터 1개씩)
- [x] T0 데이터 생성기 + 데이터셋 (`backend/data/gen_data.py` → `dataset.json`)
- [x] T1 백엔드 서버 스켈레톤 + /api/health + 정적 서빙 (`backend/app.py`)
- [x] T2 데이터 로딩 + /api/items + /api/series
- [x] T3 회귀모델(`backend/model.py`) + /api/model + /api/correlate
- [x] T4 /api/simulate (시나리오 → 예측 + 평년대비 + 규칙기반 해설)
- [x] T5 프론트 스켈레톤 + 작물 선택 + 헬스체크 연결
- [x] T6 시나리오 슬라이더 → /simulate 실시간 호출 + 결과 카드
- [x] T7 Canvas 차트: 과거 가격 시계열 + 예측선 + 사건 마커, 상관 막대
- [x] T8 /api/quiz 연결 + 학습 퀴즈 UI
- [x] T9 해결방안(적응전략) 패널 + 사회문제 서사 + 출처 표기
- [x] T10 반응형(모바일) + 로딩/에러(toast) 처리
- [x] T16 사과 봄냉해 연중 전파 완료(gen_data 2-pass). 사과 R² 0.62→0.81, frost70→ +19% 재현.
- [x] T11 통합 검증 스크립트(`backend/test_api.py`) 완료. 18/18 통과. 매 루프 `python backend/test_api.py`로 0에러 확인.
- [x] T14 회귀 신뢰도 등급(높음/보통/낮음)+사유를 model→API→프론트에 노출. 저R²(쌀) 교육적 설명 보강. 18/18 유지.
- [x] T15 프리셋 점검 중 '한파→사과 +51%' 오귀속 발견 → 비교기준을 '같은 시기 평년 기상'으로 변경(날씨효과 분리) + 릿지18로 다중공선성 억제. 한파→사과 +15%, 시금치 +9%(정상). R² 유지. UI 카피 정정. 18/18.
- [x] T12 개발계획서(docs/개발계획서.md) 작성 완료 — 100점 루브릭 매핑, 사회문제·아키텍처·일정·위험관리 포함.
- [x] T13 README 기후식탁용 전면 교체(실행법/아키텍처/원리/검증/데이터출처) + preview.png 재생성(2024 폭염 배추 +33%).
- [ ] T17 접근성(aria, 키보드), 작물별 단위표기(포기/개) 보강
- [ ] T18 최종 통합 검증 + 회귀 재확인 + PROGRESS에 '완료' 기록 후 루프 종료

## 검증 체크리스트(매 커밋 전 최소)
- 서버 기동 `python backend/app.py` 오류 없음
- `curl /api/health` 200, `/api/simulate` 정상 JSON
- 프론트 콘솔 에러 0 (headless)
