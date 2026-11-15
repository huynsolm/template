# M5-C 완료 보고 (시트로 여러 상품 일괄 생성)

## 1. 구현 여부

**완료.** 기준 커밋 `e4b94c9`(M5-B 보완) 위의 단일 커밋. 커밋 해시는 최종 보고에 기록한다.

| 항목 | 위치 |
|---|---|
| 읽기·검증·가져오기 | `core/batch.py`: `read_sheets`, `import_batch`, `write_template` |
| 상태·프롬프트·답변·CLI·내보내기 | `core/batch.py`: `batch_status`, `export_prompts`, `ingest_answers`, `generate_batch`, `export_batch`, `list_batches` |
| CLI | `cli.py batch template|import|prompts|ingest|generate|status|export` |
| 화면 | 사이드바 **작업 방식 → 일괄 작업**: 템플릿 다운로드, 가져오기, 이전 일괄 작업 열기, 상태 배지 표, 상품별 열기(①~⑦), 프롬프트 ZIP, 답변 파일 수집, 구독 CLI 순차 생성(설정 시), 승인 상품 ZIP |
| 의존성 | `openpyxl 3.1.5`(MIT), `et-xmlfile 2.0.0`(MIT)를 `requirements.in`·해시 고정 `requirements.lock`에 추가. 다른 패키지 버전·해시는 바뀌지 않음(주석만 갱신) |

동작 요약:
- **입력**: XLSX(`products`·`facts`·`images` 필수, `reviews` 선택) 또는 같은 구조의 CSV 파일 묶음(UTF-8, BOM 허용; 다른 인코딩은 명확한 오류). XLSX는 `data_only`로 **저장된 값만** 읽고 수식을 계산하지 않는다. `.xlsm` 등 매크로 파일은 확장자와 내용(`vbaProject.bin`·macroEnabled) 모두로 거부한다. 상품 수 상한 50개, 파일 크기 상한 5MB(인자로 변경 가능).
- **템플릿**: 시트별 열 이름, 열 이름 셀 메모(설명), 예시 1행(`example-1`), 드롭다운(테마·프로필·종류·역할·배경 제거 여부·허가 확인), `안내` 시트. **후기 시트에는 예시 행을 넣지 않았다**(예시를 그대로 두면 지어낸 후기가 페이지에 실릴 수 있어서). 후기 예시는 안내 시트에 글로만 적었다.
- **검증**: 상품마다 기존 `ProductFacts`로 검증하고, 사진은 지정한 사진 루트 아래 상품 폴더에서 기존 `validate_images`로 검사한다. 오류가 있는 상품만 제외하고 나머지는 진행한다. 오류는 `시트·행(엑셀 행 번호)·열·원인`이며, 흔한 검증 문구는 한국어로 바꿔 보여 준다. 없는 product_id를 가리키는 행, 중복 product_id, 잘못된 product_id 형식은 일괄 작업 전체 오류로 따로 보고한다.
- **폴더**: `outputs/batch-<id>/products/<product_id>/job-*`(기존 작업 폴더 그대로) + `batch.json`(상품별 상태·작업 경로·승인 작업 경로·테마·프로필·오류·마지막 메시지). 상태는 작업 폴더에서 다시 계산한다(입력 오류/프롬프트 대기/답변 오류/검수 필요/승인됨).
- **붙여넣기**: `prompts/<product_id>.md` + 전체 ZIP. 답변 오류 상품은 수정 요청 프롬프트(`fix-prompt.md`)를 넣는다. `answers/<product_id>.txt`를 폴더째 읽어 상품별 `ingest_job`을 실행한다. 정확한 이름의 파일만 읽고(링크 제외), 상품이 없는 파일은 보고만 한다. 프롬프트 하나에 여러 상품을 섞지 않는다.
- **구독 CLI**: 상품별 순차 실행. 공급자 오류(사용량 한도·로그인·시간 초과)가 나면 즉시 멈추고 재시도하지 않으며, 남은 상품은 프롬프트 대기로 둔다(시도 횟수도 쓰지 않음).
- **승인·내보내기**: 일괄 승인 기능은 없다. 상품마다 기존 ⑥ 체크리스트로 승인한다(`accept_job`). 승인된 상품만, 각 상품의 프로필로 M5-B 내보내기를 해서 상품별 폴더로 묶는다. 승인본이 현재 문구·테마·정책과 맞지 않으면 그 상품은 오류로 보고하고 넣지 않는다(M5-B `current_bundle` 재사용).

## 2. 실행과 검증

```bash
cd detail-page-auto
UV_CACHE_DIR=... uv pip compile requirements.in --constraint requirements.lock --generate-hashes --python-version 3.12 --output-file requirements.lock
UV_CACHE_DIR=... uv pip sync --python .venv/bin/python --require-hashes requirements.lock
.venv/bin/python -m pytest -q
git status --porcelain=v1
```

- 기준(`e4b94c9`): 334 passed.
- 변경 후 전체: **367 passed, 0 failed, 0 skipped** (약 13분). 테스트 후 `git status`에는 이번 변경 파일만 있음.
- 새 테스트: `tests/test_batch.py` 32개, `tests/test_app.py`의 일괄 작업 AppTest 1개.
  - 템플릿 생성(시트·열·설명·예시·드롭다운) → 예시 행 가져오기 / 템플릿을 채운 XLSX로 3개 상품 → 상품별 작업(테마·프로필 반영)
  - 빈 상품명·근거 없는 주장·허가 없는 후기·없는 사진 → 해당 상품만 제외, `시트·행·열` 정확
  - 사진 루트 밖 폴더·`..`·절대 경로·하위 경로·역슬래시·제어 문자 파일명 거부, 없는/중복/잘못된 product_id, 알 수 없는 테마·프로필
  - CSV(BOM) 동일 결과 / cp949 → 오류, 수식 셀은 저장값 사용, `.xlsm`과 내용상 매크로 파일 거부, 상품 수·파일 크기 상한, 시트·열 누락
  - 답변 폴더 일괄 수집: 정상·형식 오류·파일 없음·모르는 파일이 섞인 경우 상품별 상태, 답변 오류 상품의 수정 프롬프트, 재수집
  - 가짜 공급자/가짜 CLI: 2번째 상품에서 사용량 한도 → 즉시 중단(호출 2회), 3번째 이후 대기, 시도 횟수 0
  - 일괄 승인 함수 없음, 승인 전 내보내기 오류, 승인된 상품만 상품별 프로필·테마로 내보내기(smartstore는 폭 848px)
  - 다른 위치로 옮겨 다시 열어도 상태 유지, CLI 전체 흐름
  - AppTest: 새 세션에서 이전 일괄 작업 열기 → 상태 배지 표, 입력 오류 표시, 프롬프트 ZIP, 승인 상품만 ZIP, 상품 열기 → ① ~ ⑦ 화면(일반 모드)으로 이동

## 3. 결과 예시 — 3개 상품(+입력 오류 1개) 일괄 처리 상태표

실제 실행(가져오기 → p1·p2 답변 수집 → p1만 ⑥ 승인 → 내보내기):

| product_id | 테마 | 프로필 | 상태 | 메시지 |
|---|---|---|---|---|
| p1 | classic | generic | 🟢 승인됨 | |
| p2 | minimal | generic | 🟠 답변 오류 | hero: Field required; pain: Field required; … |
| p3 | bold | smartstore | 🟡 프롬프트 대기 | p3.txt 답변 파일이 없습니다 |
| p4 | classic | generic | 🔴 입력 오류 | products 5행 상품명: 한 글자 이상 입력해 주세요 |

승인 상품 ZIP `batch-…-approved.zip`: `p1/`만 포함, `p2`·`p3`·`p4`는 "승인되지 않음"으로 건너뜀(`batch-export.json`에 기록).

## 4. 미해결·지시서와 다른 점

- **후기 시트 예시 행 없음**: 지시서는 "예시 1행"이지만, 후기는 예시를 그대로 두면 지어낸 후기가 페이지에 들어갈 수 있어 안내 시트에 글로만 적었다(products·facts·images는 예시 행 있음).
- **구독 CLI 중단 범위**: 지시서는 "사용량 한도 오류"에서 중단이다. 로그인·시간 초과 등 다른 공급자 오류도 다음 상품에서 반복될 가능성이 높아 같은 방식으로 즉시 중단하고 남은 상품을 대기로 둔다.
- **화면 가져오기**: AppTest는 파일 업로드 조작을 지원하지 않아, 화면의 업로드·가져오기 버튼 자체는 자동 테스트하지 않았다. 같은 core 함수(`import_batch`)는 위 테스트로 검증했다. 업로드 파일은 `outputs/.batch-uploads/` 아래 고정된 이름으로만 저장한다.
- **사진 루트 폴더**: 로컬 단일 사용자 도구이므로 화면에서 사진 루트 폴더 경로를 직접 입력받는다(사진을 업로드받지 않음).
- **작업 방식 선택 위치**: 사이드바 맨 위에 선택 상자로 두었다(기존 화면의 "진행 단계" 라디오 동작을 바꾸지 않으려고).
- `CLAUDE_HANDOFF.md`는 지시서대로 M5 전체(A~D)가 끝난 뒤 갱신한다. M5-D(참고 자료, 일괄 시트의 `references`)는 포함하지 않는다.

## 5. 푸시

브랜치 `ccr-f9c07036-vgvm5j`, `e4b94c9` 다음 커밋으로 푸시(강제 푸시 없음).
