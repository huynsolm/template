# 폰트 라이브러리 (M6 테마용)

모두 SIL Open Font License 1.1(OFL) 폰트이며 상업적 이용이 가능하다(폰트 단독 판매만 금지). 각 폴더에 라이선스 원문(`LICENSE.txt`)이 있다.

| 폴더 | 글꼴 | 출처 패키지 | 용도 |
|---|---|---|---|
| `pretendard/` | Pretendard Variable (굵기 45~920) | npm `pretendard@1.3.9` | 기본 본문·제목 |
| `gowun-batang/` | 고운바탕 400·700 | npm `@fontsource/gowun-batang@5.3.0` | 명조 제목(감성 내추럴) |
| `black-han-sans/` | 검은고딕(Black Han Sans) 400 | npm `@fontsource/black-han-sans@5.3.0` | 굵은 디스플레이 제목(임팩트) |

- 각 폴더의 `fonts.css`가 `@font-face`를 정의한다. 고운바탕·검은고딕은 유니코드 범위별로 나뉜 woff2 파일을 쓴다(필요한 글자 파일만 로드).
- 렌더링은 오프라인이므로 외부 CDN을 쓰지 않는다. 새 폰트도 OFL 등 상업 이용 가능한 라이선스만, 라이선스 원문과 함께 이 폴더에 추가한다.
- 2026-11-21 저장소에 추가했다. 아직 렌더러·테마와 연결하지 않았다(CODEX_TASK_M6.md 참고).
