# PROGRESS — 기후 식탁

> /loop가 매 반복 시작 시 읽는 상태 파일. 최신이 위로.

## ✅ 완료 (루프 종료)
- **작업 큐 전체 완료(T0~T18).** 자율 개선 루프 정상 종료.
- 최종 검증: 데이터 재생성 OK / `python backend/test_api.py` **18/18** / 프론트 콘솔에러 **0** / git 커밋 10개.
- 실행: `python backend/app.py` → http://localhost:8000
- 검증: `python backend/test_api.py`

## 산출물 요약
- 백엔드: `backend/app.py`(REST API, 표준라이브러리만) + `backend/model.py`(릿지 회귀) + `backend/test_api.py`(통합검증) + `backend/data/`(gen_data.py, dataset.json)
- 프론트: `frontend/`(index.html, style.css, app.js — Vanilla JS + Canvas)
- 문서: `docs/개발계획서.md`(100점 루브릭 매핑), `docs/preview.png`, `README.md`
- 모델 R²: 배추0.86 무0.83 사과0.79 쌀0.12(낮음=정부수급) 시금치0.43 양파0.42
- 재현: 배추 폭염가뭄 +33%, 사과 냉해(금사과) +21%

## 밤새 진행 로그 (자율 루프)
- T18 최종 통합 검증 → 큐 전체 완료, 루프 종료
- T17 접근성(aria)+가계 단위 환산("배추 한 포기 ≈ N원")
- T13 README 기후식탁용 전면 교체 + preview.png 재생성
- T12 개발계획서(docs/개발계획서.md) 100점 루브릭 매핑 작성
- T15 날씨 효과 분리(같은 시기 평년 기상 기준)+릿지18로 한파 오귀속 수정
- T14 회귀 신뢰도 등급화(높음/보통/낮음)+저R² 작물 설명
- T11 통합 검증 스크립트(test_api.py) 18/18
- T16 사과 봄냉해 연중 전파('금사과' 재현)
- T0~T10 베이스라인: 풀스택(기후플레이션 시뮬레이터) 구축
