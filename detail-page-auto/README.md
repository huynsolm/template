# 상세페이지 자동화 — M1 + M2

Python 3.12에서 로컬 JSON과 PNG/JPEG를 받아 HTML과 폭 860px JPG를 만듭니다. M2는 구독 채팅의 붙여넣기 또는 공식 CLI로 문구 초안을 받습니다. 유료 API·배경 제거·UI·크롤링은 포함하지 않습니다.

## 설치

이 클라우드 작업은 이미 격리되어 있으므로 기존 체크아웃을 사용합니다. 별도 worktree가 필요하지 않습니다.

```bash
cd detail-page-auto
UV_CACHE_DIR=/tmp/template-uv uv venv .venv --python python3.12
UV_CACHE_DIR=/tmp/template-uv uv pip sync --python .venv/bin/python --require-hashes requirements.lock
```

uv가 없는 환경에서는 Python 3.12의 venv와 `pip install --require-hashes -r requirements.lock`를 사용할 수 있습니다.

브라우저 설치가 필요한 일반 환경:

```bash
.venv/bin/python -m playwright install chromium
# Linux에서 필요한 OS 라이브러리는 관리자 권한으로 playwright install-deps chromium
```

현재 클라우드에서는 cdn.playwright.dev 다운로드가 허용 목록에 없어 실패합니다. 사전 설치된 `/usr/bin/chromium`(검증 버전 156.0.8078.79)을 자동으로 사용하므로 추가 다운로드 없이 실행됩니다. 명시하려면 `M1_CHROMIUM_PATH=/usr/bin/chromium`을 설정하세요. 기본값은 `M1_CHROMIUM_PATH` → Playwright 기본 Chromium → `/opt/pw-browsers/chromium`(실행 파일 또는 하위 chrome-linux[64]/chrome) → PATH의 `chromium` 순서로 탐색합니다. 재현 시 Chromium 버전도 manifest와 비교하세요.

한글 폰트는 환경에 사전 설치된 Noto CJK 파일을 복사했으며 외부 다운로드는 하지 않았습니다. `assets/fonts/LICENSE.txt`에 SIL OFL 1.1과 저작권 원문을 동봉했습니다. 약 19MB의 폰트 원본을 수정 없이 포함합니다.

잠금 파일 갱신(의도적인 의존성 변경 시에만):

```bash
UV_CACHE_DIR=/tmp/template-uv uv pip compile requirements.in --generate-hashes --output-file requirements.lock
```

## 실행

```bash
.venv/bin/python samples/generate.py
.venv/bin/python cli.py --input samples/product.json --images samples --output outputs --max-height 1800 --png
.venv/bin/python -m pytest -q
```

`--max-height` 기본값은 4000이며 1~30000 범위입니다. 단일 섹션이 상한을 넘으면 섹션 ID와 함께 오류를 반환합니다. 전체 높이는 30000px 이하입니다. 정상 결과는 `outputs/job-<고유값>/`에 생성됩니다. 실패는 비정상 종료 코드와 `error:` 메시지를 반환하며 미완성 작업 폴더를 삭제합니다. 기존 결과를 덮어쓰지 않습니다.

결과 파일:

- `page.html`, `assets/`: 독립적으로 옮길 수 있는 HTML·CSS·이미지·폰트·라이선스
- `input.json`: 입력 문구와 출처를 보존하고 이미지 경로만 번들 내부 경로로 변환한 JSON 사본
- `page-001.jpg` 등: sRGB ICC 프로필, 품질 90, 실제 폭 860px
- `page-001.png` 등: `--png` 사용 시 무손실 분할 결과
- `manifest.json`: 파일 순서·크기·원본 좌표, 섹션 경계, 로딩 상태, 도구 버전, 실행 시간

입력 JSON은 `core/schema.py`의 엄격한 v1.0 스키마를 따릅니다. `samples/product.json`에 9종 섹션 예시가 있습니다. 선택 이미지 필드를 생략하면 이미지 영역도 없습니다. 후기 예시는 테스트 문구임을 명시한 fixture이며 실판매용 후기가 아닙니다. 실제 데이터의 출처와 사용 허가는 판매자가 확인해야 합니다.

## 오프라인·이동 검증

HTML의 이미지·CSS 경로와 CSS의 폰트 경로는 모두 번들 내부의 상대경로입니다. 출력 폴더 전체를 함께 옮겨야 합니다. 이 환경에서 `file://` 직접 열기는 관리 정책으로 차단되므로, 해당 방식의 실제 표시 성공을 검증했다고 주장하지 않습니다. 현재 클라우드의 관리형 Chromium은 file:// 탐색을 정책으로 차단하므로 재촬영 함수는 가상 루프백 URL의 요청을 파일 내용으로 직접 fulfill합니다. HTTP 서버·리스닝 포트·실제 네트워크 연결 없이 내보낸 폴더 아래 파일만 읽습니다. 외부 요청은 차단하고 오류로 반환합니다. 관리 정책은 변경하지 않습니다.

입력 사본으로 새 결과를 만들려면:

```bash
.venv/bin/python cli.py --input outputs/job-EXAMPLE/input.json --images outputs/job-EXAMPLE --output outputs
```

테스트는 실제 Chromium으로 한글·긴 문구·선택 이미지 생략·높이 제한·HTML 이스케이프·외부 요청 차단을 확인합니다. 이동한 HTML의 전체 재촬영과 PNG 조각을 픽셀 단위로 비교하고 JPG의 ICC·폭·높이·순서를 검사합니다. 검증은 샘플 디자인 기준이며 특정 판매 플랫폼 업로드 규격을 보장하지 않습니다.

## 저장소에 포함한 기대 결과와 이동 검증

`samples/expected/`는 9종 섹션 샘플 한 세트의 HTML·assets·입력 JSON·JPG·PNG·manifest입니다. 일반 `outputs/`는 Git에서 제외합니다. 기대 이미지는 기록된 Chromium 버전을 기준으로 하며 다른 브라우저·버전에서는 미세한 차이가 있을 수 있습니다.

```bash
.venv/bin/python tools/check_portability.py --report samples/expected/portability-report.json
```

이 명령은 샘플을 임시 폴더에 복사한 뒤 공백과 한글이 있는 다른 경로로 이동합니다. HTML 바이트가 바뀌지 않았는지, 이미지·CSS·폰트 상대경로 파일이 모두 존재하는지 확인하고, 외부 연결 없는 실제 Chromium 재촬영을 기대 PNG들과 픽셀 단위로 비교합니다. 이어 `file://`로 page.html을 직접 열기를 별도로 시도합니다. `direct_file_url.status`가 `blocked_by_browser_policy`라면 직접 열기 검증은 통과가 아니라 환경 정책에 의한 차단입니다. 이 결과와 재촬영 성공을 구분해 보고합니다.

렌더러의 가상 주소는 `http://127.0.0.1:18600/page.html`입니다. Playwright `page.route('**/*', ...)`가 요청을 가로채고, URL 경로를 현재 결과 폴더 아래 파일로 대응시켜 `route.fulfill(body=...)`로 바이트와 MIME 타입을 전달합니다. 이 포트에 서버를 띄우거나 접속하지 않습니다. CSS가 참조하는 `fonts/...`는 `assets/theme.css`를 기준으로, HTML의 `assets/...`는 page.html을 기준으로 브라우저가 해석합니다. 폴더 밖 경로·다른 호스트 요청은 중단하고, context도 offline으로 설정합니다. HTML을 data URL로 바꾸거나 이미지·폰트 경로를 절대경로로 주입하지 않습니다.

기대 결과의 중복 폰트 바이너리는 저장소에 포함하지 않습니다. `tools/check_portability.py`는 임시 복사본에 `assets/fonts/` 원본을 복사한 후 비교합니다. 배포용 결과는 M1 렌더러로 다시 생성하면 폰트를 포함합니다.

## M2: 채팅에 붙여넣어 문구 만들기 (기본 방식)

설치는 M1과 같으며 API 키나 추가 SDK가 필요하지 않습니다. 저장소 루트에서 `cd detail-page-auto` 후 아래 명령을 실행하세요.

① **상품 사실 작성**: `samples/facts.json`을 복사해 상품명·카테고리·표시 가격·색상과 `facts`를 작성합니다. 사실마다 고유 `id`, 설명 `text`(500자 이하), 종류 `kind`를 입력합니다. `claim`(효능·인증 등 주장)은 `evidence`가 필수입니다. `images`에는 이미지 디렉터리 기준 상대경로와 `role`을 적습니다. 사진은 최대 5장, 각 10MB·2,000만 픽셀 이하 PNG/JPEG입니다. 리뷰가 없으면 `reviews`를 생략하세요. 실제 후기는 출처와 사용 허가가 확인된 원문만 입력합니다. `notice`에는 판매자가 제공하는 배송·교환·반품 문구를 넣습니다.

② **프롬프트 만들기**:

```bash
.venv/bin/python cli.py prompt --facts samples/facts.json --images samples --output outputs
```

출력된 `outputs/job-고유값` 폴더의 `prompt.md`를 엽니다. 폴더 안의 사실·사진은 생성 당시 복사본입니다. 원본을 바꿔도 기존 작업은 바뀌지 않습니다. 붙여넣기 시도 상한은 기본 5회이며 `--max-attempts`로 바꿀 수 있습니다.

③ **구독 채팅 사용**: 사용자가 로그인한 Claude·ChatGPT·Gemini 중 하나의 채팅창에 `prompt.md` 전체를 붙여넣습니다. 사이트를 프로그램으로 자동 조작하지 않습니다. 생성된 문구가 사실과 일치하는지 확인하세요. 예시 JSON은 형식 참고용이며 그 내용을 상품 사실로 사용하면 안 됩니다.

④ **답변 저장**: 답변을 코드 블록 포함 또는 JSON만 복사해 UTF-8 텍스트 파일 `answer.txt`로 저장합니다. 답변에 JSON 객체가 여러 개 있으면 선택하지 않고 오류를 반환합니다. 테스트에는 실제 AI 대신 저장소의 고정 답변 `samples/answer.txt`를 쓸 수 있습니다.

⑤ **답변 검증·조립·렌더링** (`job-EXAMPLE`을 ②의 경로로 바꾸세요):

```bash
.venv/bin/python cli.py ingest --job outputs/job-EXAMPLE --answer answer.txt --source-label "Claude 채팅" --render
```

검증이 통과하면 같은 작업 폴더에 `copy.json`, `draft.json`, `review.json`이 생기고, `--render`를 쓰면 `rendered/job-고유값/`에 JPG가 생성됩니다. AI는 문구만 씁니다. 상품명·가격·이미지·실제 후기·배송 안내는 판매자 입력에서 복사하고, 스펙 표는 `kind: spec`인 사실의 id와 text를 그대로 사용합니다. AI의 문구를 프로그램이 자르거나 고치지 않습니다.

⑥ **오류 고치기**: 명령이 실패하면 오류의 필드 경로·원인을 읽고 작업 폴더의 `fix-prompt.md` 전체를 같은 채팅에 붙여넣습니다. 고친 답변 전체를 다시 `answer.txt`에 저장하고 ⑤를 반복하세요. 이전 답변과 오류는 `attempts/answer-1.txt`, `errors-1.json`처럼 보존됩니다. 성공한 작업에 다시 ingest하지 말고 아래 재생성을 사용하세요. 최종 M1 검증이나 렌더링 실패 시에는 성공 JSON을 남기지 않습니다.

⑦ **검수**: `review.json`을 열어 섹션 id·문구 경로·검수 사유·fact_ids를 확인합니다. 없는 사실 ID, 빈 근거 목록, claim/spec 근거 없는 숫자·퍼센트·인증·효능 표현을 표시합니다. 검수 항목은 문구를 삭제하거나 바꾸지 않습니다. 이 검사는 보조 수단이므로 모든 문구가 사실인지, 과장 광고나 개인정보 노출은 없는지 사람이 확인해야 합니다. 검수 목록이 비어 있어도 사실·법적 적합성을 보장하지 않습니다. 키워드 목록은 JSON 문자열 배열 파일을 `--review-terms terms.json`으로 전달해 바꿀 수 있습니다.

### 직접 고친 섹션 유지하며 재생성

`draft.json`에서 직접 문구를 고친 뒤 같은 폴더의 `edits.json`에 잠글 id를 적습니다.

```json
{"locked_sections": ["hero-1", "features-1"]}
```

```bash
.venv/bin/python cli.py prompt --from-job outputs/job-EXAMPLE --regenerate
```

새 폴더 경로가 출력됩니다. 기존 폴더는 수정하지 않습니다. 새 `prompt.md`는 잠긴 섹션을 참고로 포함하고 나머지 문구만 새로 쓰도록 요청합니다. 답변의 전체 CopyDraft 구조는 유지해야 하며 잠긴 섹션에 대응하는 AI 문구는 최종 조립에서 무시합니다. 새 폴더에서 ③~⑦을 진행하면 잠근 섹션은 이전 `draft.json`의 내용과 이미지 경로를 그대로 유지합니다. 잠금 설정도 다음 세대로 전달되며 해제하려면 `edits.json`에서 해당 id를 지우세요. 이미지를 수동 교체한다면 이전 작업 폴더 내부에 로컬 PNG/JPEG를 넣어 상대경로로 참조하세요.

### 선택: 구독 공식 CLI

```bash
.venv/bin/python cli.py generate --facts samples/facts.json --images samples --output outputs --provider codex --render
```

기본 전체 시도는 3회, 호출당 제한 시간은 300초입니다. 검증 실패 시 같은 CLI에 `fix-prompt.md`로 재요청합니다. `--max-attempts`, `--timeout`, `--providers-config`로 조정할 수 있습니다. 사용량 한도에 걸리면 붙여넣기로 전환하세요. 구독제 사용량 한도가 적용되며 개인 사용 범위와 각 서비스 약관을 확인해야 합니다. 이 환경에서는 Codex 설치·ChatGPT 로그인 상태와 도움말만 확인했고 실제 모델 생성은 실행하지 않았습니다. Claude/Gemini는 설치되지 않아 검증되지 않은 옵션을 넣지 않았고 사용자 설정이 필요합니다.

확인한 버전·정확한 옵션·설정 방법·안전 제한은 [CLI_PROVIDERS.md](docs/CLI_PROVIDERS.md)를 참고하세요. 외부 명령은 빈 임시 폴더에서 `shell=False` 인자 리스트와 표준 입력으로 실행합니다. API 인증 환경변수가 있으면 구독 전용 모드에서 실행을 거부합니다. 토큰과 CLI 설정 내용은 작업 파일·오류 로그에 기록하지 않습니다.

종료 코드: `0` 성공, `2` 입력/검증 오류, `3` CLI 미설치/미설정, `4` 시간 초과, `5` 사용량 한도, `6` 로그인/구독 인증 오류, `7` 그 밖의 공급자 오류입니다.

### M2 검증

```bash
.venv/bin/python -m pytest -q
```

M1과 M2 전체를 실행하며 실제 Chromium을 사용합니다. AI 답변은 고정 파일로, CLI는 임시 가짜 실행 파일로 검증하므로 실제 AI 서비스나 유료 API를 호출하지 않습니다. 의존성 추가는 없습니다. 프롬프트 버전 `copy_v1`과 생성 방식·출처 라벨·시도 수·시각은 작업 `manifest.json`에 남깁니다. 배포 후 프롬프트 내용을 바꾸면 `copy_v2.md` 등 새 버전을 만들어야 합니다.
