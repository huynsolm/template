# M5-A 완료 보고

## 1. 구현 여부

완료. classic/minimal/bold, 공유 섹션 HTML, 로컬 테마 검증, WCAG 전경 보정, 작업·렌더링·ZIP manifest 기록, UI 테마 변경·승인·재개, CLI --theme를 연결했다. 승인한 설계 문서와 구현 계획을 함께 커밋한다. 커밋 해시는 최종 응답에 기록한다.

## 2. 실행과 검증

- 설치: `UV_CACHE_DIR=/tmp/template-uv uv venv .venv --python python3.12`, `UV_CACHE_DIR=/tmp/template-uv uv pip sync --python .venv/bin/python --require-hashes requirements.lock`.
- 기준 커밋 b2cdcad를 별도 임시 폴더에 풀어 실행: 210 passed, 0 failed, 0 skipped.
- 테마·AppTest 대상 검증: 57 passed. 추가 리뷰 회귀 2 passed, 외부 테마 변경 시 승인 초기화 1 passed, 실제 DOM 대비 9 passed.
- 최종 전체 검증: `.venv/bin/python -m pytest -q` — 264 passed, 0 failed, 0 skipped (477.35s).
- 실제 Chromium을 사용해 폭 860px·가로 넘침 없음·한글 폰트·세 테마·밝은/어두운/중간색의 실제 글자 대비를 검사했다.
- `#305b46`, `#234567` classic은 별도 보존한 기존 CSS로 같은 Chromium에서 렌더해 전체 픽셀 동일성을 확인했다. 기존 M1 기대 결과·이동 검증 테스트도 유지했다.
- `git diff --check` 통과. 최종 pytest 전후 Git 대상 파일의 SHA-256와 status가 동일함을 확인했다. 커밋 후 `git status --porcelain=v1` 결과는 최종 응답에 기록한다.
- 테스트 도중 소스 변경이 섞인 초기 실행과 추가 회귀 수정 전의 중간 실행은 최종 통과 근거로 사용하지 않았다. 최종 실행은 소스 변경 없이 처음부터 끝까지 수행했다.

## 3. 결과 예시

캡처 생성 명령: `.venv/bin/python tools/make_screenshots.py --themes-only`.

- `detail-page-auto/docs/images/theme-classic.png`
- `detail-page-auto/docs/images/theme-minimal.png`
- `detail-page-auto/docs/images/theme-bold.png`

성공한 보정은 검수 항목이 아니며 미리보기에 `브랜드 색 대비 보정됨`을 표시한다. 예를 들어 classic의 `#FFFF00` 강조색은 검정으로 보정되며 `contrast_adjustments`에 `token`, `original`, `adjusted`, `backgrounds`, `minimum`, `original_contrast_ratio`, `contrast_ratio`를 기록한다. 원본 상품 브랜드 색·배경·문구는 바꾸지 않는다. 작업/렌더링/ZIP manifest가 이 정보를 보존한다.

UI 테마 변경은 새 스냅샷을 만든다. 이전 스냅샷 파일은 바꾸지 않는다. CLI에서 같은 작업의 테마를 바꾼 경우에도 오래된 테마 다운로드를 거부하고, 열려 있는 승인 화면의 체크를 초기화한다.

## 4. 미해결·차이·리뷰

- 기능상 미해결 항목 없음. M5-B~D는 이 커밋에 포함하지 않는다.
- 사용자 승인에 따라 대비 부족 classic 색만 글자·강조색이 이전과 달라질 수 있다. 기준을 이미 만족하는 색은 유지한다.
- 본문·강조색은 보수적으로 4.5:1을 적용하고 실제 DOM 검사는 큰 글자 3:1 / 일반 글자 4.5:1로 확인한다.
- README 지침대로 현재 격리 체크아웃을 사용했고 별도 worktree는 만들지 않았다.
- 독립 리뷰의 오래된 테마 ZIP 문제, 추가 검토의 대비 검수 플래그 불일치·외부 테마 변경 시 승인 체크 문제는 실패 회귀 테스트를 먼저 확인한 뒤 수정했다.
- 리뷰의 경미한 추가 커버리지 제안(`regenerate_job(accepted)`·`generate_job(existing_job=..., theme=None)` 전용 테스트)은 보류했다. 해당 전달 경로를 정적으로 확인했으며 일반 재생성·테마 상속·승인 결과 테마는 기존/추가 테스트에서 확인한다.

## 5. 푸시

대상 브랜치: `ccr-f9c07036-vgvm5j`. 푸시 결과와 원격 해시 일치는 최종 응답에서 보고한다.
