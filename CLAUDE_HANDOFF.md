# Claude 개발 인계서

## 시작할 때

- 저장소: `huynsolm/template`
- 작업 브랜치: `ccr-f9c07036-vgvm5j`
- 구현 기준 커밋: `9221d36` (M1~M4·M3는 `91d8054`, M5-A~D는 그 이후 커밋)
- 앱 폴더: `detail-page-auto/`
- 먼저 `AGENTS.md`, 이 문서, `detail-page-auto/README.md`를 읽는다.
- 배경은 `PLAN_detail_page_automation.md`, 상세 요구사항은 `CODEX_TASK_M1.md`, `CODEX_TASK_M2.md`, `CODEX_TASK_M4.md`, `CODEX_TASK_M3.md`, `CODEX_TASK_M5.md`에 있다. 작업별 보고·검수는 `M5_A_REPORT.md`, `M5_B_REPORT.md`, `M5_C_REPORT.md`, `M5_C_REVIEW.md`에 있다.

**M1~M4·M3와 M5-A(테마)·M5-B(플랫폼 프로필)·M5-C(일괄 생성)·M5-D(참고 자료)는 모두 구현됐다(2026-11-16 기준).** 완료된 마일스톤을 처음부터 다시 구현하지 않는다. M6 범위와 승인된 디자인 방향은 `CODEX_TASK_M6.md`를 따른다. 다중 사용자·배포와 URL 자동 수집은 사용자 결정으로 제외됐다.

여러 작업자가 같은 브랜치에 동시에 커밋해 충돌·중복 작업이 생긴 적이 있다. 작업 전 반드시 `git fetch` 후 원격 상태를 확인하고, 이미 반영된 수정을 다시 하지 않는다.

## M7 입력 도우미

- 구현 순서는 자료 가져오기 → 사진 자르기 → 입력 완성도 → 승인 전 표현 확인이다. 가상 자료 `samples/extract-answer.txt`와 Pillow 브로슈어만 사용한다.
- `core/extract.py`의 `FactsDraft`, `extraction_prompt`, `ingest_facts`, `apply_import`, `promote_claim`, `validate_form_draft`를 UI와 CLI가 공유한다. 가져오기 오류는 수정 프롬프트를 반환하고, 적용 전 미리보기를 거친다. 가격 후보는 확인 전 가격에 넣지 않는다. 빈 칸 병합은 기존 사실·숫자 띠를 보존하고 관계없는 사실 ID에 근거를 붙이지 않는다.
- `ProductFacts`의 선택 메타데이터는 `pending_claims`, `uncertain`, `price_candidate`, `spec_from_import`, `spec_verified`다. `ImageRef.document_confirmed`는 문서형 경고 해제 기록이다. 옛 작업은 기본값으로 열린다.
- `Processing.crop`는 left/top/right/bottom 비율 0~0.45다. 처리 순서는 방향 → crop → sRGB → resize → 선택 배경 제거다. 자를 때만 남는 영역 200px 최소 크기를 적용한다. 이미지 파이프라인 캐시 버전은 4다.
- `core/readiness.py:check_readiness(facts, images, settings)`는 원시 입력 dict와 ProductFacts를 받고, images는 원본 사진 폴더다. 필수는 생성 불가, 권장·참고는 안내다. UI는 입력 위 점검 패널을, CLI prompt는 같은 검사와 비정상 종료를 사용한다.
- `core/claims.py:claim_items`는 최종 문구와 연결 사실·근거를 표현별 ID로 묶는다. UI는 기존 5개 확인과 표현별 확인을 모두 요구한다. `accept_job(..., claim_confirmations=...)`는 같은 문서로 검사하며 승인 작업·렌더링 manifest의 `claim_checks`에 기록한다. CLI의 명시적 accept와 ingest/generate `--accept-review`도 같은 기록을 남긴다.
- 입력 UI 보조는 `app/input_tools.py`, 가상 시나리오는 `tools/m7_scenario.py`다. README 캡처는 `tools/make_screenshots.py --m7-only`로만 생성한다.

- M7 최종 검증은 `detail-page-auto/.venv/bin/python -m pytest -q`로 436 passed, 0 failed, 0 skipped였다. Linux·Chromium 156, 2026-11-22 기준이며 실행 중 추적 파일 변경이 없었다. 가상 시나리오는 사실 9개·숫자 띠 4개·사양표 4행·보관 주장 1개를 가져와 실제 렌더링했다. 프롬프트 전문은 `detail-page-auto/docs/extract-prompt.md`, 캡처는 `detail-page-auto/docs/images/m7-{before,after,detail,input}.png`다.

## M6 디자인 시스템

- 새 단일 작업은 `modern`이 기본이다. `natural`, `impact`, `industrial`과 기존 `classic`, `minimal`, `bold`를 선택할 수 있다. 테마 기록이 없는 작업은 `classic`으로 연다. 기존 M1의 기본 스타일과 일괄 시트의 빈 테마 기본값도 `classic`이다.
- `core/themes.py`의 `load_theme`과 `theme_styles`가 레이아웃·글꼴·AA 토큰을 관리한다. 공용 변형은 `templates/sections/<type>/<variant>.html`에 있고 테마의 선택과 스타일은 `themes/<id>/`에 있다. 기존 문서의 기존 테마는 기존 CSS와 HTML 경로를 쓴다.
- `core/fonts.py:load_font`는 OFL 라이선스와 로컬 WOFF2 참조를 검증한다. `core/render.py:render`는 선택한 패키지를 `assets/fonts/<id>/`에 묶고 Chromium에서 해당 글꼴이 로드됐는지 확인한다. 번들 manifest에는 `fonts`, `font_loaded`, `brand_color`가 들어간다.
- `core/assemble.py:seller_sections`는 판매자 값으로 숫자 띠, 추천 대상, 구조, 사진, 사양을 구성하며 `core/editor.py`도 같은 함수로 값 변경을 검증한다. 새 섹션이 포함된 Document는 1.1이며 기존 1.0도 지원한다. AI 답변과 프롬프트 계약은 기존 버전을 사용한다.
- `core/editor.py:preview_job`은 테마와 작업 색을 새 스냅샷에 적용한다. `gallery_thumbnail`은 `job/gallery/`에 문구·사진·테마·색 기준 상단 이미지를 캐시한다. `bundle_matches`는 문구·테마·색·대비 정책을 확인한다. 브랜드 색 변경은 `facts.json`과 이전 렌더링을 보존한다.
- 상세 샘플은 `detail-page-auto/samples/facts-rich.json`과 `answer-rich.txt`다. `tools/make_screenshots.py --themes-only`로 README 상단 캡처 7장을 갱신한다.

- 검증 환경은 Linux·Chromium 156이다. 전체 실행은 411개 통과, 2개 실패였다. 새 기본 테마의 영향을 받은 기존 classic 정책 픽스처를 명시한 뒤 `tests/test_export.py`, `tests/test_m6.py`, 일괄 사진 상한 테스트를 다시 실행해 79개가 통과했다. 최종 검증 집계는 기존 384개와 M6 30개, 총 414개 통과·0개 실패·0개 건너뜀이다.

## M5-A 현재 상태

M5-A 초기 구현은 `8cac895`에 있다. 이후 사용자 확정 기준으로 classic은 `legacy`, minimal/bold는 `aa`로 구분했다. classic은 색을 보정하지 않고 원본 HTML·DOM·CSS·픽셀을 유지하며 저대비는 `BRAND_COLOR_LOW_CONTRAST`로 기록한다. AA 보정은 글자색만 바꾸며 장식·브랜드 배경은 원래 색이다. 이전 "classic도 보정" 기준을 다시 적용하지 않는다.

- `core/themes.py`: `theme_styles`, `contrast_metadata`, `load_theme`; 정책·적용 색·보정/경고를 공용 계산한다.
- 테마 파일: `themes/{classic,minimal,bold}/theme.toml`, `theme.css`; 섹션 HTML은 공유한다.
- manifest 공용 필드: `theme`, `contrast_policy`, `resolved_colors`, `contrast_adjustments`, `contrast_reviews`.
- `core/editor.py`의 `bundle_matches`는 문구·테마·현재 정책을 확인한다. 이전 정책/정책 없는 스냅샷은 보존하지만 새 미리보기/다운로드에 재사용하지 않는다.
- 회귀 기준: `tests/fixtures/classic-original.html`, `classic-original.css`는 b2cdcad 이전 디자인 원본이며 #c7b195/#FFFF00도 전체 픽셀 비교한다. `tests/test_themes.py`는 실제 DOM 대비·장식 색·정책/ZIP/승인 전파도 검사한다.
- 수정 최종 테스트 수와 커밋·푸시 결과는 `M5_A_REPORT.md`와 최종 완료 보고를 확인한다. 다음 작업은 M5-B이며 이 수정 커밋에는 포함하지 않는다.

## M5-B 현재 상태

원격 선행 구현은 `251f0c0`이며 이후 검증·보완은 `M5_B_REPORT.md`를 따른다. `core/export.py`의 Profile/load_profile/list_profiles/save_user_profile/export_bundle/build_export_zip/current_bundle을 UI·CLI에서 공유한다. 프로필은 `profiles/<id>.toml`, 사용자 입력은 Git 제외 `profiles/user/`에 저장한다.

coupang은 값·출처·확인 날짜가 빈 `unverified` 템플릿이다. smartstore는 공식 도움말에서 확인한 권장 폭 848px와 출처·확인 날짜만 들어 있고 나머지는 비어 있어 `unverified`다. 남은 값은 사용자가 공식 도움말에서 확인해야 한다. 공식 도움말을 직접 확인하지 않고 값을 채우지 않는다. 미확인 결과는 경고와 `.UNVERIFIED` ZIP 이름을 유지한다.

내보내기는 섹션 경계 우선이며 섹션 내부는 RGB 모든 채널의 픽셀이 균일한 빈 행에서만 자른다. 회색조나 오차 허용으로 흐린 글자 행을 빈 행으로 처리하지 않는다. ZIP 최상위 pages/width/height/sections는 실제 내보낸 이미지 기준이며, 변환 전 렌더링 manifest는 source_render에 보존한다. HTML/assets는 원본 렌더링 자료다. 승인본도 현재 문구·테마·대비 정책과 일치해야 내보낸다. 프로필 값을 덮어쓰면 UI의 옛 검사 결과와 ZIP 캐시를 무효화한다.

## M5-C 현재 상태

구현 `83bf877`, 검수 `M5_C_REVIEW.md`(Important 5건), 수정 `3df24b3`·`d84a84b`(회귀 테스트 `4a9d0d9`). `core/batch.py`의 `read_sheets`, `import_batch`, `write_template`, `batch_status`, `list_batches`, `export_prompts`, `ingest_answers`, `ingest_uploaded_answers`, `generate_batch`, `export_batch`를 UI(사이드바 **작업 방식 → 일괄 작업**)와 CLI(`cli.py batch template|import|prompts|ingest|generate|status|export`)가 공유한다.

- 입력: XLSX(`products`·`facts`·`images` 필수, `reviews`·`references` 선택) 또는 같은 이름의 UTF-8 CSV. 저장값만 읽고 매크로 파일은 거부한다. 압축 해제 전 항목 수·풀린 크기·압축률을 검사한다.
- 템플릿의 `reviews`·`references` 시트에는 예시 행을 넣지 않는다(지어낸 후기·자리표시 경쟁사 문구가 페이지·프롬프트에 들어가지 않도록).
- 폴더: `outputs/batch-<id>/products/<product_id>/job-*` + `batch.json`. 상태는 작업 폴더에서 다시 계산한다.
- 승인 상태는 일괄 작업 폴더를 옮겨도 유지되고, 승인 후 원본 문구·테마가 바뀌면 검수 필요로 돌아가 내보내기에서 빠진다.
- 화면 답변 수집은 이번에 올린 파일만 처리한다(`ingest_uploaded_answers`).
- 일괄 승인 기능은 없다. 상품마다 ⑥ 체크리스트로 승인한다. 구독 CLI는 순차 실행하며 공급자 오류가 나면 즉시 멈춘다.
- 의존성: openpyxl 3.1.5, et-xmlfile 2.0.0(MIT).

## M5-D 현재 상태

구현 `50947d8`(테스트 `ac33043`, 인코딩 수정 `366bd9a`, 테스트 픽스처 수정 `9221d36`). URL 자동 수집은 없고 사용자가 붙여넣은 텍스트만 쓴다.

- `core/facts.py`: `ProductFacts.references`(id·label·kind·text 최대 5,000자·source_note), `reference_names`(경쟁사·브랜드 이름). 필드가 없는 기존 facts.json도 그대로 동작한다.
- `prompts/copy_v2.md`: 참고 자료가 있을 때만 `<references>` 블록과 지시(그대로 쓰지 말 것, 참고 자료 수치·효능은 우리 사실이 아님, 경쟁사 이름·비교 광고 금지)를 넣는다. 참고 자료가 없으면 `copy_v1`과 같은 동작이다.
- `core/similarity.py`: `similarity_matches`, `reference_reviews`(검수 사유 "참고 자료와 표현 유사"·"참고 자료의 경쟁사·브랜드 이름 포함", `detail`에 구간 위치), `personal_data_warnings`(이메일·전화번호·주문번호 형태, 자동 삭제 없음).
- 참고 자료 id는 `fact_ids`로 인정되지 않는다(기존 "존재하지 않는 fact_ids" 검수 항목).
- 화면: ① "참고 자료 (선택)" 입력과 저장 전 개인정보 경고, ④ 유사 구간 표시. `source_note`의 URL에는 접속하지 않는다.
- `samples/answer.txt`는 코드 블록이 있는 채팅 답변 형식이다. 테스트에서 읽을 때 `core.ingest.extract_json`을 쓴다.

## 제품과 현재 흐름

단일 사용자가 자신의 컴퓨터에서 상품 정보·사진으로 폭 860px의 상세페이지 이미지를 만드는 도구다.

1. Streamlit 화면에서 상품 사실·사진·실제 후기·안내 문구 입력
2. 프롬프트 복사 → 사용자가 Claude/ChatGPT/Gemini 채팅에 붙여넣기
3. 답변 붙여넣기 → 엄격한 JSON 검증·근거 검사·상품 정보 조립
4. 문구·근거 사실 선택·목록 항목 수정, 잠금, 재검수
5. DRAFT 미리보기 → 확인 체크리스트 5개 → 승인
6. 같은 작업 버전 ID의 JPG·HTML·assets·JSON을 ZIP으로 다운로드

선택 기능으로 로그인된 공식 CLI를 호출할 수 있다. 기본은 붙여넣기다. 사진은 원본을 보존하고 EXIF 방향·sRGB·크기를 정리하며 선택적으로 로컬 배경 제거를 한다.

## 반드시 유지할 규칙

- 유료 AI API·API SDK·외부 이미지 처리 서비스 사용 금지.
- 채팅 웹사이트를 자동 조작하지 않는다. 자동 테스트도 실제 AI 서비스·CLI·배경 제거 모델을 호출하지 않는다.
- 앱은 `127.0.0.1`에만 바인딩한다. 단일 사용자·로컬용이다.
- 검증·근거 편집·이미지 처리·렌더링·승인·ZIP 로직은 `core/`에 두고 UI는 공용 함수를 호출한다.
- 사용자 문구·답변을 `unsafe_allow_html=True`로 출력하지 않는다. 템플릿 자동 이스케이프를 유지한다.
- AI가 후기·별점·가격을 만들지 않는다. 생성 문구를 자동으로 잘라 검증을 통과시키지 않는다.
- 원본 사진, 원본 `copy.json`, 승인 시 원본 작업 폴더를 보존한다.
- 비밀 값·CLI 인증 설정·모델 파일을 커밋하거나 로그·manifest에 남기지 않는다.
- 외부 프로세스는 `shell=False` 인자 목록으로 실행한다.
- 테스트 이미지와 화면 예시는 로컬에서 생성한다. 외부 이미지·폰트 다운로드 금지.
- 테스트를 skip/xfail 처리하거나 검증을 약화해 통과시키지 않는다. 실제 Chromium 테스트를 유지한다.
- pytest는 추적 파일을 수정하지 않는다. `outputs/`, 모델, 가상환경은 Git에서 제외한다.
- 요청 범위 밖의 배포·다중 사용자·크롤링·추가 테마·AI 연출 이미지 생성을 임의로 추가하지 않는다.

## 핵심 파일과 수정 위치

| 대상 | 파일 | 책임 |
|---|---|---|
| 화면 | `app/main.py` | 단계별 입력·편집·미리보기·승인·다운로드 |
| 명령 | `cli.py` | 기존 M1 렌더링과 prompt/ingest/generate/accept/images |
| 사실 입력 | `core/facts.py` | ProductFacts, Fact, ImageRef 및 처리 설정 |
| 출력 검증 | `core/schema.py` | M1 Document와 섹션 9종 |
| AI 문구 검증 | `core/copy_schema.py` | CopyDraft, 각 문구의 fact_ids |
| 프롬프트·추출 | `core/prompting.py`, `core/ingest.py` | 버전 프롬프트·수정 요청·JSON 단일 객체 추출 |
| 조립 | `core/assemble.py` | 판매자 원본과 AI 문구 조립 |
| 작업 흐름 | `core/workflow.py` | 작업 생성·수집·재생성·승인·사진 처리 연결 |
| 편집·재검수 | `core/editor.py` | 근거 선택·항목 편집·수정 이력·스냅샷·ZIP |
| 입력 사진 | `core/collect.py`, `core/uploads.py` | 경로·실제 형식·파일 크기·픽셀 수 검증·안전한 업로드 이름 |
| 사진 처리 | `core/images.py` | 방향·ICC·알파·메타데이터 제거·리사이즈·배치·검증 캐시 |
| 선택 배경 제거 | `core/background.py` | 지연 로드·u2netp·체크섬·CPU 실행 |
| 렌더링 | `core/render.py`, `templates/` | 로컬 Chromium·860px·섹션 경계 분할·파일명·manifest |
| 구독 CLI | `core/providers.py`, `providers.toml` | 설치 버전에서 확인한 옵션·표준 입력·오류 분류 |
| 문서 캡처 | `tools/make_screenshots.py` | 명시적으로 실행할 때만 README 캡처 갱신 |
| 실제 모델 확인 | `tools/bg_check.py` | pytest 밖에서 수동 실행 |

위 경로는 `detail-page-auto/` 기준이다. 수정하기 전에 해당 함수의 현재 시그니처와 호출부를 함께 읽는다.

## 공용 API와 주의점

- `create_job`: 원본을 새 작업에 복사하고 사진을 처리한 후 facts·prompt·manifest를 생성한다.
- `ingest_job`: 시도별 답변·오류를 보존한다. 검증 실패 시 fix-prompt를 만들고 성공 파일을 남기지 않는다.
- `generate_job(..., existing_job=job)`: 재생성 중인 작업의 잠금·근거를 유지한다. UI에서 새 작업을 다시 만들어 잠금을 잃지 않도록 한다.
- `evidence_units`: 문구별 `section_id`, `path`, `key`, `fact_ids`를 반환한다. UI 선택지에는 실제 사실 ID만 넣는다.
- `save_draft(..., evidence=...)`: 판매자 전용 필드를 보호하고 M1 검증·재검수·이력을 저장한다. copy.json은 보존한다.
- `change_copy_items`: pain/features/how_to/faq 추가·삭제와 인덱스 변경에 따른 근거 재매핑을 함께 처리한다. UI에서 이 규칙을 다시 구현하지 않는다.
- `reassess_draft`: 현재 문구와 수정한 근거·사용자 지정 검수 용어·사진 검수 항목으로 재검수한다.
- `preview_job` / `build_zip`: 불변 렌더링 스냅샷을 사용한다. 화면 ID와 ZIP manifest의 job_id가 같아야 한다.
- `accept_job`: 현재 수동 수정본을 검증·재검수해 새 작업으로 승인한다. AI나 답변 재입력이 필요 없다.

검수 항목이 있으면 일반 ingest 렌더링은 `page-001.DRAFT.jpg`를 쓴다. 명시적 승인 후 일반 파일명을 쓴다. `needs_review`는 검수 항목 유무이며 `review_accepted`와 별개다. 승인한다고 검수 이력을 지우지 않는다. 승인 전 UI 미리보기·ZIP은 검수 항목이 없어도 DRAFT다.

## 데이터와 보존

- `facts.json`: 판매자 정보·사실·원본 사진 경로·processing·derived_path
- `copy.json`: 검증을 통과한 원본 AI 문구
- `draft.json`: 현재 편집 가능한 Document
- `edited-evidence.json`: 사용자 근거 선택
- `locked-evidence.json`, `locked.json`, `edits.json`: 잠금과 재생성용 근거
- `history.json`: 문구·근거·잠금 수정 이력
- `review.json`, `manifest.json`: 검수·상태·처리 이력
- `attempts/`: 시도별 답변·오류
- `images/`: 원본 사본, `images/derived/<해시>/`: 파생본
- `rendered/`: 버전별 렌더링 스냅샷

렌더링은 `ImageRef.effective_path`를 사용한다. 사진 처리 재실행은 원본 `path`에서 시작하며 이미 만든 파생본에 반복 처리하지 않는다. 캐시는 원본·설정·브랜드 색·도구/파이프라인 버전에 묶인다. 처리 알고리즘을 바꾸면 캐시 버전도 검토한다.

## 설치와 실행

저장소 루트에서:

```bash
cd detail-page-auto
UV_CACHE_DIR=/tmp/template-uv uv venv .venv --python python3.12
UV_CACHE_DIR=/tmp/template-uv uv pip sync --python .venv/bin/python --require-hashes requirements.lock
./run_app.sh
```

Windows는 README의 가상환경 설치 방법과 `run_app.bat`를 사용한다. 브라우저 주소는 `http://127.0.0.1:8501`이다. 다른 머신에는 필요한 경우 `.venv/bin/python -m playwright install chromium`으로 브라우저를 설치한다.

Chromium 탐색 순서는 `M1_CHROMIUM_PATH` → Playwright 기본 → `/opt/pw-browsers/chromium` → PATH의 chromium이다. 현재 클라우드의 Chromium은 file:// 직접 탐색이 정책으로 차단된다. 렌더러는 가상 루프백 요청을 Playwright로 가로채 로컬 파일 바이트를 전달하며 실제 서버나 외부 연결을 만들지 않는다.

배경 제거를 앱에서 활성화하려면 선택 잠금 파일을 설치한다.

```bash
UV_CACHE_DIR=/tmp/template-uv uv pip sync --python .venv/bin/python --require-hashes requirements-bg.lock
```

기본 설치만으로 기존 기능과 사진 기본 처리는 동작한다. rembg 2.0.87은 MIT, u2netp/U-2-Net은 공식 프로젝트 Apache-2.0 기준이다. 모델은 4,574,861바이트이며 checksum을 검증한다. 모델 이름을 생략하면 다른 모델이 선택될 수 있으므로 명시적 u2netp 선택을 유지한다. 설치·캐시 위치·다운로드 출처는 README를 따른다.

## 검증

```bash
.venv/bin/python -m pytest -q
git status --porcelain=v1
```

커밋 `9221d36`에서 **384 passed, 0 failed, 0 skipped**(Linux, Chromium 153, 약 15분)와 테스트 후 빈 git status 출력을 확인했다. 이는 인계 시점의 기록이며 새 변경 후에는 다시 실행해 실제 결과를 보고한다. 전체 실행이 길므로 작업 중에는 관련 테스트 파일만 먼저 돌리고 마지막에 전체를 돌린다.

- 문구·워크플로: test_m2.py, test_providers.py, test_editor.py
- 이미지: test_images.py, test_background.py, test_image_workflow.py, test_uploads.py
- UI: test_app.py의 AppTest와 test_browser.py의 실제 로컬 Streamlit/Chromium
- M1: test_m1.py의 실제 렌더링·분할·이동 검증
- M5: test_themes.py, test_export.py, test_export_regressions.py, test_batch.py, test_references.py

확인하지 못한 것: Windows에서의 `run_app.bat` 실행과 전체 테스트(`.github/workflows/m5c-windows.yml` 실행 결과 미확인), 실제 구독 CLI 연동, 실제 상품 사진·실제 채팅 AI 답변으로 만든 결과물의 품질.

테스트는 고정 답변·가짜 CLI·가짜 제거기를 사용한다. 실제 모델 수동 확인만 별도로 실행한다.

```bash
.venv/bin/python tools/bg_check.py --model-dir outputs/models --output outputs/bg-check --download-model
```

README용 화면이 바뀌었을 때는 pytest와 별개로 `tools/make_screenshots.py`를 명시적으로 실행하고 변경된 이미지를 검토한다.

## 다음 코딩 요청을 받을 때

1. 사용자가 지정한 다음 목표와 관련 파일만 확인한다. 다음 목표가 없다면 기능을 임의로 정하지 않는다.
2. 기존 코드를 활용해 변경하고 관련 회귀 테스트를 추가한다.
3. 전체 테스트와 추적 파일 변경 여부를 확인한다. 원본·비밀·모델·가상환경·outputs는 커밋하지 않는다.
4. 커밋·푸시 범위는 해당 요청과 저장소 지침을 따른다. 현재 대상 브랜치는 위와 같다.
5. 바뀐 동작, 실행한 명령과 통과/실패/건너뜀 수, 미해결 항목, 커밋·푸시 결과를 보고한다.

### Claude에게 붙여넣을 시작 요청

```text
huynsolm/template 저장소의 ccr-f9c07036-vgvm5j 브랜치에서 이어서 개발해줘.
AGENTS.md, CLAUDE_HANDOFF.md, 관련 CODEX_TASK 문서와 README를 먼저 읽어줘.
M1~M4와 M5-A~D는 모두 완료됐으니(기준 커밋 9221d36) 처음부터 다시 구현하지 마.
작업 전에 git fetch로 원격에 이미 반영된 변경이 있는지 확인해줘.
기존 공용 core와 테스트를 유지하면서 아래 작업만 구현해줘.

다음 작업: [여기에 원하는 기능 또는 수정할 문제를 적기]

검증 후 변경 내용, 실행 명령, 테스트 통과/실패/건너뜀 수와 미해결 사항을 보고해줘.
```
