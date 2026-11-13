# 상세페이지 자동화 — M1

Python 3.12에서 로컬 JSON과 PNG/JPEG를 받아 HTML과 폭 860px JPG를 만듭니다. LLM·배경 제거·UI·크롤링은 포함하지 않습니다.

## 설치

이 클라우드 작업은 이미 격리되어 있으므로 기존 체크아웃을 사용합니다. 별도 worktree가 필요하지 않습니다.

```bash
cd /workspace/template/detail-page-auto
UV_CACHE_DIR=/tmp/template-uv uv venv .venv --python python3.12
UV_CACHE_DIR=/tmp/template-uv uv pip sync --python .venv/bin/python --require-hashes requirements.lock
```

uv가 없는 환경에서는 Python 3.12의 venv와 `pip install --require-hashes -r requirements.lock`를 사용할 수 있습니다.

브라우저 설치가 필요한 일반 환경:

```bash
.venv/bin/python -m playwright install chromium
# Linux에서 필요한 OS 라이브러리는 관리자 권한으로 playwright install-deps chromium
```

현재 클라우드에서는 cdn.playwright.dev 다운로드가 허용 목록에 없어 실패합니다. 사전 설치된 `/usr/bin/chromium`(검증 버전 156.0.8078.79)을 자동으로 사용하므로 추가 다운로드 없이 실행됩니다. 명시하려면 `M1_CHROMIUM_PATH=/usr/bin/chromium`을 설정하세요. 기본값은 Playwright의 설치된 Chromium을 우선 사용하고 없으면 PATH의 chromium을 사용합니다. 재현 시 Chromium 버전도 manifest와 비교하세요.

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
