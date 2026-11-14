# Claude 개발 인계서

## 시작할 때

- 저장소: `huynsolm/template`
- 작업 브랜치: `ccr-f9c07036-vgvm5j`
- 구현 기준 커밋: `91d8054347ede352b7609017e3fac61a8e2aa429`
- 앱 폴더: `detail-page-auto/`
- 먼저 `AGENTS.md`, 이 문서, `detail-page-auto/README.md`를 읽는다.
- 배경은 `PLAN_detail_page_automation.md`, 상세 요구사항은 `CODEX_TASK_M1.md`, `CODEX_TASK_M2.md`, `CODEX_TASK_M4.md`, `CODEX_TASK_M3.md`에 있다.

**M1·M2·M4·M3 및 M4 마무리 수정은 이미 구현됐다.** 완료된 마일스톤을 처음부터 다시 구현하지 않는다. 사용자가 다음 작업으로 **M5를 지정했다**: `CODEX_TASK_M5.md`(M5-A 테마 → M5-B 플랫폼 프로필 → M5-C 일괄 생성 → M5-D 참고 자료)와 `AGENTS.md`를 따른다. 다중 사용자·배포와 URL 자동 수집은 M5에서도 제외됐다.

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

마지막 구현 커밋에서 **210 passed, 0 failed, 0 skipped**와 테스트 후 빈 git status 출력을 확인했다. 이는 인계 시점의 기록이며 새 변경 후에는 다시 실행해 실제 결과를 보고한다.

- 문구·워크플로: test_m2.py, test_providers.py, test_editor.py
- 이미지: test_images.py, test_background.py, test_image_workflow.py, test_uploads.py
- UI: test_app.py의 AppTest와 test_browser.py의 실제 로컬 Streamlit/Chromium
- M1: test_m1.py의 실제 렌더링·분할·이동 검증

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
M1·M2·M3·M4는 91d8054에서 완료됐으니 처음부터 다시 구현하지 마.
기존 공용 core와 테스트를 유지하면서 아래 작업만 구현해줘.

다음 작업: [여기에 원하는 기능 또는 수정할 문제를 적기]

검증 후 변경 내용, 실행 명령, 테스트 통과/실패/건너뜀 수와 미해결 사항을 보고해줘.
```
