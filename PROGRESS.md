# PROGRESS — 기후 식탁

> /loop가 매 반복 시작 시 읽는 상태 파일. 최신이 위로.
> [야간운영] 자율 루프 활성 — 약 25분 간격으로 PLAN 큐 1작업씩 처리하며 이 파일과 git 로그에 진행상황 기록. 큐 소진 시 자동 종료.

## 현재 상태
- 단계: 마무리. T16, T11, T14, T15, T12, T13 완료.
- 서버 기동: `python backend/app.py` → http://localhost:8000 정상 / 검증 18/18
- 문서: docs/개발계획서.md + README(기후식탁) + docs/preview.png 완료
- 다음 작업: **T17 (접근성 aria/키보드, 작물별 단위 표기 보강)**

## 운영 메모(토큰 최적화)
- 서버는 백그라운드 1개만. 코드 변경 후 재기동 필요(모델/데이터는 startup 로드).
- 한글 POST 검증은 UTF-8 파일+`--data-binary @file` (Git Bash가 cp949로 깨뜨림).
- headless 검증은 핵심 1~2개만. 매번 전체 스샷 금지.

## 로그
- T0~T10 완료: backend(stdlib http.server, 순수파이썬 릿지회귀) + frontend(Vanilla JS, Canvas 차트). 기후플레이션 시뮬레이터 풀스택 동작.
- (init) 피벗: 날씨 샌드박스 → 기후 식탁(기후플레이션). 사회문제(밥상물가)+해결방안 연계.
