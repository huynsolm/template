# Codex 작업 지시서 — M6: 디자인 시스템 (테마 4종 + 폰트 + 새 섹션)

기준: 브랜치 `ccr-f9c07036-vgvm5j`, M1~M5 완료 상태(전체 384 테스트 통과, 커밋 `9221d36` 이후). 이 지시서와 충돌하면 이 지시서가 우선한다.

## 배경
실제 사용해 보니 결과물 디자인 품질이 낮았다. 원인은 (1) 폰트가 Regular 한 굵기뿐이라 제목이 가짜 볼드로 뭉개지고, (2) 모든 섹션이 "제목+문단+사진 1장"이라 문서처럼 보이며, (3) 기존 테마(classic/minimal/bold)가 같은 구조에 색만 바꾼 것이기 때문이다.

## 사용자 결정 (2026-11-21)
- **테마를 통째로 고르고 브랜드 색만 바꾼다.** 섹션별 레이아웃을 사용자가 고르는 기능은 만들지 않는다(테마가 정한다).
- **첫 새 테마 4종**: `modern`(프리미엄 모던), `natural`(감성 내추럴), `impact`(임팩트), `industrial`(B2B·설비).
- **폰트 추가 허용**: 저장소에 넣어 둔 OFL 폰트만 쓴다(아래 참고). 렌더링 중 외부에서 폰트를 받지 않는다.

## 이미 준비된 것 (이 커밋에 포함)
- `detail-page-auto/assets/font-library/` — Pretendard(가변 굵기), 고운바탕(400·700), 검은고딕(Black Han Sans). 폰트별 `fonts.css`, woff2, `LICENSE.txt`, `README.md`.
- `design/references/` — 목표 디자인 4종의 HTML·CSS와 렌더링 PNG(`modern`, `natural`, `impact`, `industrial`). **이 시안의 구성·위계·여백·폰트 조합을 테마로 구현한다.** 픽셀 단위로 같을 필요는 없다. 시안 속 상품·문구·회색 "사진 자리"는 예시일 뿐이다.

## 범위 밖
- 섹션별 레이아웃 선택 UI, 사용자 정의 CSS 입력
- AI 연출 이미지 생성, 유료 API, 외부 폰트 CDN, 배포·다중 사용자
- 일괄 작업(M5-C) 시트에 새 입력 시트 추가 (테마 id 목록 갱신만 한다)
- 기존 테마 `classic`·`minimal`·`bold`의 디자인 변경 (그대로 유지, 기존 테스트 유지)

---

## 1. 폰트 레지스트리 — `core/fonts.py`
- [ ] `assets/font-library/<id>/fonts.css`를 읽는 레지스트리: 폰트 id → CSS 파일, 글꼴 이름(family), 라이선스 경로.
- [ ] 검증: `fonts.css`의 `url()`은 같은 폴더의 `.woff2`만 허용(`http`, `//`, `..`, 절대 경로 거부), 참조한 파일이 모두 존재, 폴더에 `LICENSE.txt` 존재.
- [ ] 렌더링할 때 **선택한 테마가 쓰는 폰트 폴더만** 결과 번들 `assets/fonts/<id>/`로 복사한다(폰트 라이브러리 전체를 복사하지 않는다). 기존 테마는 지금처럼 Noto Sans CJK를 그대로 쓴다.
- [ ] manifest에 사용한 폰트 id·글꼴 이름을 기록하고, 렌더링 후 `document.fonts`에서 해당 글꼴이 실제로 `loaded`인지 검사한다(기존 `font_loaded` 검사 확장). 로드 실패는 렌더링 오류.

## 2. 내용 모델 확장 (판매자 입력, AI가 만들지 않음)
새 섹션을 채우는 데 필요한 값은 **판매자가 입력**한다. 모두 선택 필드이며, 없으면 그 섹션을 생략한다. 기존 `facts.json`·작업은 그대로 열려야 한다.
- [ ] `ProductFacts`
  - `highlights: list[{value, label, fact_id}]` 최대 4개 — 숫자 띠(예: `AC 220V` / `사용 전압`). `fact_id`는 기존 사실을 가리켜야 한다(근거 연결).
  - `targets: list[str]` 최대 12개 — 적용 장소·추천 대상(예: 주택, 오피스텔).
  - `structure: list[{name, desc}]` 최대 8개 — 구조·구성 설명(단면도 옆 목록).
  - `spec_table: {columns: list[str], rows: list[list[str]], notes: list[str]}` 선택 — 여러 열의 사양표(열 2~8개, 행 1~30개, 각 행 길이 = 열 수). 없으면 기존처럼 `kind == "spec"` 사실로 2열 표를 만든다.
- [ ] `ImageRef.role`에 `detail`(디테일), `lifestyle`(사용 장면), `diagram`(구조도) 추가. 사진 최대 장수 5 → **10장**(장당 10MB·픽셀 상한은 유지).
- [ ] 이 값들은 조립(`assemble`)에서 판매자 원본 그대로 복사한다. 검수 화면(④)에서 수정하지 않고 ①에서 수정한다(기존 규칙과 동일).
- [ ] ① 상품 정보 화면에 위 입력 칸 추가(행 추가·삭제). 오류는 해당 칸 옆에 한국어로 표시.

## 3. 섹션 확장 — `core/schema.py`, `templates/`
- [ ] Document에 섹션 타입 추가: `stats`(숫자 띠), `targets`(적용 장소), `structure`(구조 설명 + diagram 이미지), `gallery`(사진 여러 장), `image`(전체 폭 사진 1장). `spec`은 `spec_table`(다열) 형식도 받도록 확장.
- [ ] `schema_version`은 `"1.1"`을 추가로 허용하고 `"1.0"` 문서는 그대로 검증·렌더링한다.
- [ ] 조립 순서(제안): hero → stats → pain → solution → image(lifestyle) → features(POINT) → structure → targets → gallery → how_to → review → spec → faq → notice. 해당 입력이 없으면 그 섹션은 생략.
- [ ] features 각 항목에는 `role == "feature"`·`detail` 사진을 순서대로 붙인다. 사진이 없는 항목은 사진 없이 그린다(회색 "사진 자리"를 결과물에 넣지 않는다).
- [ ] AI 출력 스키마(CopyDraft)와 프롬프트는 바꾸지 않는다. 단, features 최대 개수가 6 미만이면 6으로 늘리고 프롬프트에 "POINT 카드로 쓰이니 제목은 짧고 구체적으로" 한 줄을 추가한 새 프롬프트 버전으로 만든다(기존 버전 파일은 유지).

## 4. 테마 시스템 확장 — `core/themes.py`, `themes/`
- [ ] `theme.toml`에 추가:
  - `fonts = {heading = "<폰트 id>", body = "<폰트 id>", display = "<폰트 id, 선택>"}` (레지스트리에 있는 id만 허용)
  - `[variants]` 섹션별 레이아웃 이름(예: `hero = "overlay"|"arch"|"poster"|"split"`, `pain = "cards"|"lines"|"checklist"`, `features = "numbered"|"cards"|"grid"`, `stats = "band"|"tiles"`, `spec = "dark"|"card"|"plain"`)
  - `contrast_policy = "aa"` (새 테마 4종 모두 aa)
- [ ] 섹션 템플릿을 `templates/sections/<type>/<variant>.html`로 나누고 **HTML 구조는 변형(variant) 단위로 공유**한다. 테마는 어떤 변형을 쓸지와 CSS·토큰만 정한다. 같은 HTML을 테마마다 복제하지 않는다.
- [ ] 기존 테마는 기존 단일 템플릿 경로로 렌더링해 **결과가 지금과 같아야 한다**(M5-A classic 픽셀 동일 테스트 유지).
- [ ] 브랜드 색에서 역할별 색(배경·면·글자·강조·브랜드 위 글자)을 계산하는 기존 M5-A 로직을 재사용한다. 장식·브랜드 배경은 입력 색 유지, 글자색만 AA 보정(기존 aa 정책 그대로).
- [ ] 테마 CSS 검증은 기존 규칙 유지: 외부 URL·`@import`·이스케이프·주석 금지, `url()` 금지(폰트는 레지스트리가 붙인다).
- [ ] 새 테마 4종 구현:

| id | 참고 시안 | 폰트 | 대표 변형 |
|---|---|---|---|
| `modern` | `design/references/modern.html` | Pretendard (제목 800~900 / 본문 400) | hero overlay(어두운 그라디언트), stats band, pain cards, features numbered(큰 숫자 01·02), spec dark |
| `natural` | `natural.html` | 제목 고운바탕 700 + 본문 Pretendard | hero arch, pain lines, 인용형 solution, features 가운데 정렬, spec card |
| `impact` | `impact.html` | 제목 검은고딕 + 본문 Pretendard | hero poster(배지·도장), pain checklist(어두운 배경), stats tiles, features cards(굵은 테두리·그림자) |
| `industrial` | `industrial.html` | Pretendard | hero overlay(밝은 그라디언트 위 글자), stats band, pain cards 2열, features cards(마지막 강조 카드), structure(구조도+목록), targets 칩, spec dark 다열 표 |

- [ ] 공통 타이포그래피: 한국어 `word-break: keep-all`, 제목 굵기 대비(제목 ≥ 700, 본문 400), 섹션 상하 여백 ≥ 90px, 가로 넘침 없음.

## 5. 화면 (M4 앱)
- [ ] ⑤ 미리보기에 **디자인 갤러리**: 테마 7종(새 4종 + 기존 3종) 썸네일을 한 번에 비교. 썸네일은 현재 문구·사진·브랜드 색으로 렌더링한 페이지 상단(약 1,800px)을 축소한 이미지. 처음 열 때 한 번 만들고 (문구 해시·테마·브랜드 색) 기준으로 캐시. 만드는 동안 진행 표시.
- [ ] 썸네일을 눌러 테마 선택 → 기존처럼 새 렌더링 스냅샷(이전 스냅샷 보존).
- [ ] ⑤에 **브랜드 색 선택기**: 바꾸면 새 스냅샷을 만들고 manifest에 `brand_color`(실제 사용 값)를 기록. 판매자 원본 `facts.json`은 바꾸지 않고 작업 단위 설정으로 저장한다. 승인 후 테마·브랜드 색이 바뀌면 승인 무효(기존 `bundle_matches` 확장).
- [ ] 새 작업의 기본 테마는 `modern`. 기존 작업은 저장된 테마(없으면 classic)를 유지.
- [ ] CLI: `--theme`에 새 id 허용, `--brand-color #RRGGBB` 옵션 추가(`ingest`, `accept`, `generate`, M1 `--input`).

## 6. 샘플 — `samples/`
- [ ] `samples/facts-rich.json`: 가상 상품(실제 브랜드·실제 업체 자료 사용 금지) 1개. highlights 4, targets, structure, spec_table, 사진 역할 여러 개를 모두 채운다. 사진은 Pillow로 생성(기존 `samples/generate.py` 확장). 대응하는 고정 답변 `samples/answer-rich.txt`.
- [ ] README용 캡처는 `tools/make_screenshots.py`에서만 생성(테마 7종 × 샘플). 테스트는 `docs/`를 수정하지 않는다.

## 7. 테스트
- [ ] 폰트 레지스트리: 정상 / 외부 URL·`..`·없는 파일·LICENSE 없음 거부. 선택한 테마의 폰트만 번들에 복사.
- [ ] 새 테마 4종 × `facts-rich` → 실제 Chromium 렌더링: 폭 860, 가로 넘침 없음, 사용 폰트가 `document.fonts`에서 loaded, 섹션 경계 분할 정상.
- [ ] 새 테마 4종 × 밝은·어두운·중간 브랜드 색: 실제 DOM 대비(본문 4.5:1, 큰 제목 3:1), 장식·브랜드 배경은 입력 색 유지.
- [ ] 기존 `samples/facts.json`(새 필드 없음)·schema 1.0 문서가 새 테마에서도 렌더링되고, 입력 없는 섹션은 생략.
- [ ] 기존 테마 3종 결과 불변(기존 테스트 그대로 통과).
- [ ] 입력 검증: highlights 5개 이상·없는 fact_id, spec_table 행 길이 불일치·열 9개, 사진 11장 → 위치가 맞는 오류.
- [ ] AppTest: 갤러리 표시 → 테마 선택 → 새 스냅샷, 브랜드 색 변경 → 새 스냅샷 + 승인 무효, 다시 열어도 선택 유지.
- [ ] 건너뛰기 금지, 테스트 후 `git status` 깨끗.

## 8. 문서
- [ ] README "화면으로 사용하기"에 테마 갤러리·브랜드 색·새 입력 칸 사용법, 테마 7종 캡처.
- [ ] `assets/font-library/README.md`에 "렌더러와 연결됨" 갱신.
- [ ] `CLAUDE_HANDOFF.md`에 M6 절 추가(공용 함수, 폴더 구조, 결정 사항, 테스트 수).

---

## 완료 보고 형식
1. 실행 명령과 전체 테스트 통과/실패/건너뜀 수, 테스트 후 `git status`
2. 테마 7종 × `facts-rich` 렌더링 결과 이미지 경로(상단 캡처), 그리고 `design/references`와 비교해 의도적으로 다르게 한 부분
3. 폰트 번들 크기(테마별 결과 폴더 크기)와 렌더링 시간
4. 미해결 항목, 지시서와 다르게 구현한 부분과 이유
5. 커밋 해시와 푸시 여부 (브랜치 `ccr-f9c07036-vgvm5j`). 작업 전 `git fetch`로 원격 변경을 먼저 확인할 것
