# 에셋 출처 및 라이선스

밥상 차리기 탭의 음식 아이콘은 **Microsoft Fluent Emoji**의 3D 변형을 사용합니다.

- 출처: https://github.com/microsoft/fluentui-emoji
- 저작자: Microsoft Corporation
- 라이선스: **MIT License** (자유로운 사용·수정·재배포 허용, 본 문서로 출처 표기를 갈음)
- 모두 투명배경 256×256 PNG, 통일된 3D 클레이 스타일.

| 파일 | 음식 | 원본 Fluent Emoji |
|---|---|---|
| foods/rice.png | 공기밥 | Cooked rice (🍚) |
| foods/kimchi_jjigae.png | 김치찌개 | Pot of food (🍲) |
| foods/doenjang_jjigae.png | 된장찌개 | Shallow pan of food (🥘) |
| foods/baechu_kimchi.png | 배추김치 | Leafy green (🥬) |
| foods/mu_saengchae.png | 무생채 | Green salad (🥗) |
| foods/sigeumchi_namul.png | 시금치나물 | Herb (🌿) |
| foods/yangpa_jangajji.png | 양파장아찌 | Onion (🧅) |
| foods/jeyuk_bokkeum.png | 제육볶음 | Meat on bone (🍖) |

한식 요리에 1:1로 대응하는 3D 에셋이 없어, 가장 가까운 일반 음식 아이콘으로 매핑했습니다.
이미지 로드 실패 시 프론트엔드(app.js `foodMedia`)가 동일 의미의 이모지로 자동 폴백합니다.

식탁(배경)은 별도 이미지 없이 CSS 그라데이션으로 렌더링합니다.
