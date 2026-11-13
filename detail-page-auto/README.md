# 상세페이지 자동화 — M1 + M2 + M3 + M4

Python 3.12에서 로컬 JSON과 PNG/JPEG를 받아 HTML과 폭 860px JPG를 만듭니다. M2는 구독 채팅의 붙여넣기 또는 공식 CLI로 문구 초안을 받습니다. M3는 원본을 보존하며 방향·색 공간·크기를 정리하고 선택적으로 로컬 배경 제거를 지원합니다. M4는 단일 사용자용 로컬 Streamlit 화면을 제공합니다. 유료 API·외부 이미지 서비스·크롤링·배포 기능은 포함하지 않습니다.

## 화면으로 사용하기

명령어 대신 브라우저에서 상품 입력 → 프롬프트 복사 → 답변 붙여넣기 → 검수·수정 → 미리보기 → 승인 → ZIP 다운로드를 진행할 수 있습니다. 먼저 Python 3.12와 Chromium을 준비하세요.

1. 저장소의 `detail-page-auto` 폴더에서 가상환경과 고정 의존성을 설치합니다.

   ```bash
   python3.12 -m venv .venv
   .venv/bin/python -m pip install --require-hashes -r requirements.lock
   .venv/bin/python -m playwright install chromium
   ```

   Windows에서는 `py -3.12 -m venv .venv` 후 `.venv\Scripts\python.exe -m pip install --require-hashes -r requirements.lock`와 `.venv\Scripts\python.exe -m playwright install chromium`을 사용하세요. 현재 클라우드에서는 사전 설치된 Chromium을 자동 탐색하므로 브라우저 다운로드 없이 실행됩니다. OS 라이브러리 설치와 탐색 순서는 아래 CLI 설치 절을 참고하세요.

2. macOS/Linux는 `./run_app.sh`, Windows는 `run_app.bat`를 실행합니다. 가상환경이 없으면 설치 안내를 표시하고 종료합니다. 직접 실행하려면 다음 명령을 사용하세요.

   ```bash
   .venv/bin/python -m streamlit run app/main.py --server.address 127.0.0.1
   ```

3. 같은 컴퓨터의 브라우저에서 `http://127.0.0.1:8501`을 엽니다. 주소는 `127.0.0.1`에만 바인딩되며 사용 통계 수집은 꺼져 있습니다. 업로드 상한은 한 장당 10MB입니다. 외부 공개·다중 사용자용 서버가 아닙니다.
4. 처음에는 **샘플 데이터 넣기**로 가상 상품을 체험할 수 있습니다. 실제 사용 시 상품명·가격·사실·사진을 바꾸고, 주장은 근거를 입력하세요. 사진은 실제 PNG/JPEG 형식으로 즉시 검증하고 안전한 파일명으로 저장합니다. 사진마다 배경 제거 여부를 선택하고 **사진 처리 미리보기**를 눌러 처리 전/후와 체크무늬 마스크를 비교하세요. 체크를 해제하면 기본 방향·색 공간·크기 정리본을 사용합니다. 배경 제거는 선택 의존성을 설치했을 때만 활성화됩니다. 실제 후기만 출처·허가와 함께 입력하세요. 사실 행의 위로/아래로/삭제/추가 버튼으로 순서를 조정할 수 있고, facts.json 불러오기·내보내기도 지원합니다. JSON을 불러오면 사진은 별도로 올려 주세요.
5. **저장하고 프롬프트 만들기**를 누르고 코드 상자의 복사 버튼으로 전체 프롬프트를 복사해 Claude·ChatGPT·Gemini 채팅에 붙여넣습니다. 화면이 채팅 사이트를 자동 조작하지 않습니다. 답변 전체를 ③에 붙여넣어 검증하세요. 오류가 있으면 화면의 수정 프롬프트를 같은 채팅에 보내 다시 받은 답변을 입력합니다.
6. ④에서 경고와 근거를 확인하고 문구를 고친 뒤 **수정 저장·재검수**를 누릅니다. 글자 수를 임의로 자르지 않으며 M1 상한을 넘으면 저장 오류를 표시합니다. 상품명·가격·후기·스펙·안내는 ①에서 수정해 새 작업을 시작하세요. 각 문구의 근거는 기존 사실 목록의 다중 선택에서 수정할 수 있고, 고객 고민·특징·사용법·FAQ 항목은 추가·삭제할 수 있습니다. 근거를 수정하거나 부적절한 항목을 지운 뒤 재검수하면 해소된 경고가 없어집니다. 잠근 섹션은 재생성에서도 문구와 수정한 근거를 유지합니다. 수정 이력은 `history.json`에 기록하고 원본 `copy.json`은 보존합니다.
7. ⑤에서 미리보기를 생성합니다. 승인 전에는 항상 DRAFT 파일명과 표시가 붙습니다. 같은 저장 버전의 미리보기 버튼을 다시 눌러도 렌더링을 중복 실행하지 않습니다. ⑥의 다섯 확인 항목을 모두 체크해야 승인할 수 있습니다. 승인은 현재 저장 문구를 다시 검증·재검수하고 원본을 바꾸지 않은 새 작업으로 일반 JPG 파일명을 생성합니다.
8. ⑦에서 보이는 이미지와 **작업 버전 ID**를 확인하고 ZIP을 받습니다. ZIP의 manifest에도 같은 ID가 들어 있으며 해당 이미지·HTML·assets·draft.json·review.json만 묶습니다. 승인 전 DRAFT ZIP도 받을 수 있습니다. 저장 문구를 수정하면 이전 미리보기 포인터를 무효화하며, 예전 ZIP을 새로운 문구와 섞지 않습니다.
9. 화면을 닫았다 다시 열면 사이드바 **최근 작업 → 기존 작업 이어하기**를 선택하세요. 상품명·생성 시각(KST)·상태로 작업을 찾을 수 있습니다. 작업은 `outputs/job-*`에 유지되며 입력 사진 작업 폴더도 outputs 안에만 생성합니다. 필요하면 `DETAIL_PAGE_OUTPUTS` 환경변수로 로컬 저장 위치를 바꿀 수 있습니다.

설정된 구독 CLI가 있을 때만 선택 버튼이 나타납니다. CLI도 검증된 명령을 빈 임시 폴더에서 실행하며, 사용량·로그인·시간 초과 오류는 붙여넣기 방식으로 이어갈 수 있도록 안내합니다. 테스트는 실제 AI 서비스를 호출하지 않습니다.

샘플 화면(실제 Chromium으로 생성):

| 상품 입력 | 프롬프트 |
|---|---|
| ![상품 정보와 사진 입력](docs/images/01-input.png) | ![프롬프트 복사 화면](docs/images/02-prompt.png) |

| 검수·문구 수정 | 미리보기 | 승인 후 다운로드 |
|---|---|---|
| ![검수 화면](docs/images/03-review.png) | ![DRAFT 미리보기](docs/images/04-preview.png) | ![승인 결과 다운로드](docs/images/05-download.png) |

## CLI로 사용하기

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

테스트는 실제 Chromium으로 한글·긴 문구·선택 이미지 생략·높이 제한·HTML 이스케이프·외부 요청 차단을 확인합니다. 같은 실행에서 이동 전후 HTML 재촬영 결과를 픽셀 단위로 비교하고, 커밋 PNG와는 크기·분할 위치만 비교하며 JPG의 ICC·폭·높이·순서를 검사합니다. 검증은 샘플 디자인 기준이며 특정 판매 플랫폼 업로드 규격을 보장하지 않습니다.

## 저장소에 포함한 기대 결과와 이동 검증

`samples/expected/`는 9종 섹션 샘플 한 세트의 HTML·assets·입력 JSON·JPG·PNG·manifest입니다. 일반 `outputs/`는 Git에서 제외합니다. 기대 이미지는 기록된 Chromium 버전을 기준으로 하며 다른 브라우저·버전에서는 미세한 차이가 있을 수 있습니다.

```bash
.venv/bin/python tools/check_portability.py --report samples/expected/portability-report.json
```

이 명령은 샘플을 임시 폴더에 복사한 뒤 공백과 한글이 있는 다른 경로로 이동합니다. HTML 바이트가 바뀌지 않았는지, 이미지·CSS·폰트 상대경로 파일이 모두 존재하는지 확인하고, 외부 연결 없이 같은 Chromium 버전으로 이동 전과 이동 후를 실제 재촬영해 픽셀 단위로 비교합니다. 커밋된 PNG의 픽셀 색상은 비교하지 않으며 크기·섹션 경계·분할 위치만 확인합니다. 따라서 Chromium 버전별 안티앨리어싱 차이를 파일 이동 오류로 오인하지 않습니다. 이어 `file://`로 page.html을 직접 열기를 별도로 시도합니다. `direct_file_url.status`가 `blocked_by_browser_policy`라면 직접 열기 검증은 통과가 아니라 환경 정책에 의한 차단입니다. 이 결과와 재촬영 성공을 구분해 보고합니다.

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

### 검수 항목이 있는 렌더링과 명시적 승인

`ingest --render` 또는 `generate --render`에서 `review.json`이 비어 있지 않으면 콘솔 표준 오류에 큰 `WARNING: 검수 필요` 경고와 항목 수·검수 파일 경로가 표시됩니다. 기본 이미지 이름은 `page-001.DRAFT.jpg`, `page-001.DRAFT.png`입니다. 작업 manifest와 렌더링 manifest 모두 `needs_review: true`, `review_accepted: false`를 기록하고 파일 목록도 실제 DRAFT 이름을 가리킵니다.

내용을 사람이 확인하고 일반 파일명으로 출력하려면 새 작업의 ingest/generate 실행에 `--accept-review`를 명시하세요.

```bash
.venv/bin/python cli.py ingest --job outputs/job-EXAMPLE --answer answer.txt --render --accept-review
```

승인 시 `page-001.jpg`/`.png`를 사용하고 `review_accepted: true`를 기록합니다. 검수 항목이 남아 있다는 사실을 보존하기 위해 `needs_review`는 계속 `true`이며 `review.json`과 경고도 유지됩니다. 이미 완료된 작업은 덮어쓰지 않습니다. 초안을 먼저 생성했다면 아래 `accept` 명령으로 답변 재입력 없이 승인할 수 있습니다. 검수 항목이 없으면 승인 옵션 없이도 일반 파일명을 쓰며 `needs_review`는 `false`입니다.

### 완성한 초안 승인: AI 호출·답변 재입력 없이 렌더링

```bash
.venv/bin/python cli.py accept --job outputs/job-EXAMPLE
```

원본 작업의 현재 `draft.json`을 읽고 M1 스키마와 참조 이미지의 경로·파일 형식·용량·해상도를 검증합니다. 직접 수정한 문구와 이미지도 그대로 사용하며 원본 작업의 파일은 수정하지 않습니다. 잘못된 JSON·문구 길이·누락 이미지·심볼릭 링크는 오류로 반환합니다.

명령은 원본과 같은 상위 디렉터리에 새로운 `job-고유값`을 만들고 경로를 출력합니다. 새 폴더의 `draft.json`, `review.json`, 참조 이미지 사본과 `rendered/job-고유값/page-001.jpg`(PNG도 포함)를 확인하세요. 일반 파일명을 사용하고 `manifest.json`에는 `method: "accept"`, `attempts: 0`, `review_accepted: true`, `source_job`(원본 작업의 절대경로), 승인 시각, `rendered_job` 경로를 기록합니다. 렌더링 manifest에도 승인 여부와 원본 작업 경로가 남습니다. 검수 목록이 없더라도 명시적 승인 사실은 true로 기록합니다.

현재 문구의 근거 ID와 수치·용어를 다시 검사해 새 작업의 `review.json`과 `needs_review`를 갱신합니다. 이는 보조 검사이므로 사람이 사실과 광고 표현을 최종 확인한 뒤 실행하세요. 프롬프트·이전 답변·실제 AI·CLI 로그인이 필요하지 않으며, 검증·렌더링에 실패하면 미완성 승인 작업 폴더를 제거합니다. 재검수에는 `facts.json`, 원본 `copy.json`, `manifest.json`이 필요하며 이전 승인 작업의 경우 `source_job` 참조를 통해 원본 스냅샷을 찾을 수 있습니다. 승인 결과는 최종 출력 사본이며 문구 재생성은 원본 작업을 기준으로 진행하세요.

## 사진 처리와 선택 배경 제거

기본 설치만으로 EXIF 방향 보정, sRGB 변환, 긴 변 최대 1720px 축소가 동작합니다. 작은 사진은 확대하지 않고 너비 860px 미만이면 선명도 검수 항목을 추가합니다. 원본은 `images/image-000.*` 등으로 그대로 보존하며, 위치(GPS)·촬영 정보 등 개인정보성 메타데이터는 파생 파일에서 제거합니다. 투명 PNG의 알파 채널은 유지합니다. CMYK·그레이스케일·팔레트와 ICC 프로필도 처리합니다.

`facts.json` 이미지 항목의 예시(기존 processing 없는 파일도 기본값으로 동작):

```json
{
  "path": "product-hires.png",
  "role": "hero",
  "processing": {
    "auto_orient": true,
    "resize": true,
    "max_edge": 1720,
    "remove_background": false,
    "background": "brand",
    "padding": 0.08
  }
}
```

`background`는 `brand`(브랜드 색상 12% + 흰색 88%) 또는 `white`를 선택합니다. 배경 제거한 상품을 중앙에 여백과 함께 배치하고 별도 그림자는 추가하지 않습니다. `derived_path`는 프로그램이 생성하는 경로이며 입력 시 직접 작성할 필요가 없습니다. 파생본은 `images/derived/<내용·설정 해시>/<해시>-normalized|foreground|mask-preview|placed.png`로 분리합니다. 설정별 하위 폴더는 과거 결과를 덮어쓰지 않고 캐시를 검증하기 위한 구조입니다.

원본 SHA-256, 설정, 적용 단계, 도구 버전, 파생본 체크섬, 검수 항목을 작업 manifest의 `image_processing`, `image_reviews`에 기록합니다. 동일 원본·설정·브랜드 색상·도구 버전이면 `outputs/.image-cache`에서 재사용합니다. 손상된 캐시는 재검증하며 배경 제거 실패 결과는 성공 캐시로 저장하지 않습니다. 기존 작업의 결과는 바꾸지 않고 새 작업에서 처리합니다.

사진 처리만 CLI에서 확인하려면:

```bash
.venv/bin/python cli.py images --facts samples/facts.json --images samples --output outputs
```

AI 호출 없이 원본·파생본·manifest가 있는 새 작업을 만듭니다. `prompt`와 `generate`도 같은 처리 설정을 사용합니다. 기본 정리는 성공했으나 요청한 배경 제거가 실패하면 기본 처리본을 보존하고 경고를 기록합니다. `images` 명령은 이 경우 0이 아닌 종료 코드로 알립니다. 배경 제거 실패나 전경 면적 5% 미만/98% 초과는 검수 항목으로 남기며 최종 판단은 사람이 합니다.

### 배경 제거 선택 설치 (CPU)

유료 API·외부 이미지 처리 서비스는 사용하지 않습니다. 기본 환경에는 rembg를 넣지 않으며, 원하는 경우 기본 패키지를 포함한 별도 해시 잠금 파일을 설치합니다.

```bash
UV_CACHE_DIR=/tmp/template-uv uv pip sync --python .venv/bin/python --require-hashes requirements-bg.lock
# pip 사용 시
.venv/bin/python -m pip install --require-hashes -r requirements-bg.lock
```

도구는 **rembg 2.0.87 (MIT)**, 모델은 **u2netp / U-2-Net (공식 프로젝트 Apache-2.0)**를 명시적으로 선택합니다. rembg의 다른 기본 모델을 자동 선택하지 않습니다.

- rembg 라이선스: https://github.com/danielgatis/rembg/blob/main/LICENSE.txt
- U-2-Net 라이선스: https://github.com/xuebinqin/U-2-Net/blob/master/LICENSE
- 모델 다운로드: https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx
- 최초 모델 다운로드 크기: **4,574,861바이트(약 4.57MB)**. Python 선택 의존성 다운로드 용량은 별도입니다.
- 공식 모델 MD5: `8e83ca70e441ab06c318d82300c84806`. 새 다운로드와 기존 파일 모두 검증하며 `MODEL_CHECKSUM_DISABLED`는 허용하지 않습니다.
- 모델 루트 기본값: 현재 실행 폴더의 `outputs/models`. rembg 2.0.87의 실제 파일 위치는 `<루트>/models/u2netp/u2netp.onnx`입니다. 예: `outputs/models/models/u2netp/u2netp.onnx`.
- 위치 변경: `DETAIL_PAGE_MODEL_DIR` 환경변수 또는 확인 스크립트의 `--model-dir`.
- 모델 파일은 `.gitignore`로 제외합니다. 모델이 없으면 배경 제거 요청 시 공식 위치에서 처음 다운로드합니다. 오프라인·손상·설치 실패는 경고로 알리고 기본 처리본은 유지합니다. CPU 스레드는 2개로 제한하고 ONNX Runtime 사용 통계는 끕니다.

⑥ 승인 체크리스트에서 **상품 사진의 형태·색상이 실제와 다르게 바뀌지 않았는지 확인**해야 합니다. 투명 마스크가 잘못된 상품의 모서리를 지우거나 색상을 변형하지 않았는지 전/후를 비교하고, 마음에 들지 않으면 배경 제거 체크를 해제하세요.

### 실제 모델 수동 확인과 문서 캡처

자동 테스트는 실제 모델을 실행하거나 다운로드하지 않습니다. 별도 확인 스크립트만 직접 생성한 도형 사진으로 실제 모델을 1회 실행합니다.

```bash
.venv/bin/python tools/bg_check.py --model-dir outputs/models --output outputs/bg-check --download-model
# 이미 모델이 있으면 다운로드 허용 옵션 없이 실행
.venv/bin/python tools/bg_check.py --model-dir outputs/models --output outputs/bg-check
.venv/bin/python tools/make_image_samples.py --output outputs/m3-samples
```

기본 의존성만 설치했거나 모델이 없고 다운로드를 허용하지 않았다면 명확한 FAILED 메시지와 비정상 종료 코드를 반환합니다. 성공 시 실제 처리 시간, 프로세스 최대 RSS(MiB, Linux 기준), 원본·처리본·마스크 경로를 출력합니다. 모델 품질을 자동 보장하지 않습니다.

pytest의 브라우저 캡처·ZIP·서버 로그는 `tmp_path`에만 저장합니다. README용 5장 캡처를 의도적으로 갱신할 때만 다음 도구를 실행하세요.

```bash
.venv/bin/python tools/make_screenshots.py
```

이 도구는 `docs/images/`를 갱신하며 결과 ZIP은 `outputs/m4-browser/approved.zip`에 둡니다. `samples/product.png`는 이전 원본을 그대로 유지하고, M3 예시용 `samples/product-hires.png`는 Pillow로 별도 생성한 이미지입니다(`tools/make_image_samples.py --fixture`로 명시적 재생성). 테스트에서는 이 파일들을 읽기만 합니다.
