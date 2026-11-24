# M8-A 최종 확인 보고서

## 요약

- 판정: **M8-B 진행 가능**.
- 대상: `huynsolm/template`, `ccr-f9c07036-vgvm5j`, `fd58f47..00470320e5a00dd62d292463f83c715af73dbeef`. 원격 fetch·fast-forward 후 확인했다.
- 기준: `CODEX_REVIEW_M8A_FIX2.md`, `M8_A_REVIEW_2.md`, `CODEX_TASK_M8A.md`의 사용자 결정(2026-11-24), `AGENTS.md`, `CLAUDE_HANDOFF.md`, README.
- 검수일: 2026-11-24 (한국 시간).
- 환경: Linux x86_64, Python 3.12.14, 저장소 `.venv`, 실제 Chromium 156.0.8078.79. 가상 상품 샘플만 사용했다. 실제 AI·구독 CLI·외부 이미지 서비스는 호출하지 않았다.
- 이전 미해결 #8과 R2-1 및 확인 질문 2·3을 아래와 같이 확인했다. 이번 확인에서 확정한 새 Critical·Important·Minor는 없다.

| 실행 명령 / 확인 | 결과 |
|---|---|
| `.venv/bin/python -m pytest -q tests/test_m8a_review.py tests/test_m8a.py` | **34 passed / 0 failed / 0 skipped**, 138.33초, 종료 코드 0 |
| `UV_CACHE_DIR=/tmp/template-uv uv pip sync --python .venv/bin/python --require-hashes requirements.lock` | 기존 가상환경에서 빠진 openpyxl 3.1.5·et-xmlfile 2.0.0만 설치. 소스·잠금 파일 변경 없음 |
| `.venv/bin/python -m pytest -q` | **470 passed / 0 failed / 0 skipped**, 954.22초(15분 54초), 종료 코드 0** |
| 테스트 후 `git status --porcelain=v1` | **전체 테스트 종료 직후 빈 출력. 보고서 작성 전 추적 파일 변경 없음** |

최초 전체 실행은 openpyxl이 없는 기존 가상환경 때문에 test_batch.py·test_references.py 수집 오류 2건으로 중단됐다(1.08초). 제품 테스트 실패로 집계하지 않고 환경 문제로 구분했다. 잠금 파일대로 동기화한 뒤 전체를 재실행했다. 렌더 포트 충돌을 피하려고 집중 테스트·수동 재현·전체 테스트는 순서대로 실행했다.

## 항목별 판정

| 항목 | 판정 | 근거(실행/판독) |
|---|---|---|
| #8 natural 제목 굵기 | 해결 | **실행:** Chromium에서 h1/h2는 modern 800/800, industrial 800/800, natural 700/700, impact 400/400이었다. natural은 Gowun Batang, impact는 Black Han Sans로 확인했고 상단 캡처도 직접 열어 보았다. **실행:** 테마 로더의 기준값은 800·800·700·400이며 임시 사본에서 각각 700·700·600·300으로 낮추면 모두 ValueError로 거부됐다. **판독:** 저장소 내 고운바탕의 font-face는 400·700, 검은고딕은 400이며 사용자 결정의 예외와 맞는다. |
| R2-1 재개 시 최신 미리보기 | 해결 | **실행:** M8-A 이전 코드로 실제 승인한 modern 작업에, 수정 전 코드로 현재 측정 버전 미리보기만 만들어 부모의 옛 승인 상태가 남는 입력을 재현했다. 현재 앱은 유효한 preview를 선택하고 ⑦에서 DRAFT ZIP 다운로드를 제공했다. 구 승인 작업을 현재 ⑤에서 새로 미리보기한 경우에는 부모 review_accepted=false·rendered_job 제거를 확인했고, 앱을 새로 열어도 그 preview와 DRAFT ZIP을 선택했다. 재승인 ZIP은 review_accepted=true였다. 아래 재현 절차 참조. |
| 확인 질문 2: 자동 정렬 범위 | 해결 | **판독:** 사용자 결정 절과 인계서가 pain·solution·features·how_to·faq 5종만 적용한다고 명시한다. 이번 커밋에서 해당 범위를 바꾸는 코드는 없다. 이전 구현 차이가 명시적으로 승인된 기준이 됐다. |
| 확인 질문 3: 측정 속성 대신 구조 선택자 | 해결 | **판독:** 사용자 결정 절이 data-copy-role/data-section-id/data-field-path 추가를 MEASURE_SPEC 구조 선택자 측정으로 대체한다고 명시한다. 기존 HTML 보존 목적과 새 변형의 선택자-필드 대응 테스트 요구도 기록돼 있다. |

### R2-1 수동 재현 근거 — 실제 코드·AppTest·Chromium

`facts-rich.json`과 `answer-rich.txt`로 다음 순서를 실행했다. manifest의 버전 키를 지워 구 버전을 흉내 낸 입력이 아니라, 저장소의 구 버전 코드로 승인 결과를 실제 생성했다.

1. `cdbf277` 코드에서 modern 작업을 만들고 승인했다. 부모 review_accepted=true이며 승인 렌더에는 copy_measure_version이 없다. 검증용으로 작업 폴더를 두 벌 복사했다.
2. **재개 대체 경로(A):** `31d1f98` 코드에서 첫 복사본을 미리보기했다. 부모는 옛 승인·rendered_job을 유지하고 preview는 m8a-2인, 지난 R2-1과 같은 상태가 만들어졌다.
3. 현재 `0047032`의 실제 Streamlit AppTest로 A를 재개했다. resume_bundle은 구 승인 대신 preview를 선택했고 latest_copy_metrics의 fresh=true였다. ⑦에 ZIP 다운로드 버튼이 있고 실제 ZIP 바이트의 manifest는 m8a-2·review_accepted=false였다. 빈 bundle로 인해 다시 렌더하라고만 안내하던 현상은 재현되지 않았다.
4. **새 미리보기 경로(B):** 새 preview가 없는 두 번째 구 승인 복사본을 현재 앱에서 열어 ⑤ 미리보기를 실행했다. review_accepted=false와 rendered_job 삭제를 확인했다. 새 AppTest 인스턴스로 다시 재개해도 현재 preview를 선택하며 ⑦ DRAFT ZIP을 받을 수 있었다.
5. B의 가상 상품 승인 체크리스트를 확인하고 ⑥ 승인을 실행했다. 새 승인 작업·ZIP이 생성됐고 측정 버전 m8a-2·review_accepted=true였다. 유효한 승인 작업에 별도 DRAFT 미리보기를 추가해도 resume_bundle은 유효한 승인 결과를 우선 선택했다.
6. A/B의 이전 승인 렌더 폴더는 모두 남았으며, 재현 전후 파일 경로·내용을 합친 SHA-256이 같았다.

위 모든 조작은 `/tmp/m8a3-review/`의 가상 작업에서 수행했다. 실제 사용자 작업이나 원본 상품 자료를 수정하지 않았다. 원문 검수의 특정 임시 작업 디렉터리를 사용한 것은 아니며, 같은 가상 샘플을 구 버전 정식 생성·승인 경로로 재생성한 검사다.

### 코드·문서 대조

- `core/editor.py`의 resume_bundle은 승인 후보·preview 후보 순서로 bundle_matches를 통과하는 스냅샷을 고른다. `app/main.py`의 open_job이 이 공용 함수를 사용한다.
- preview_job은 새 결과와 포인터를 쓴 뒤 현재 규칙과 맞지 않는 rendered_job을 제거하고 승인을 해제한다. 유효한 현재 승인은 유지하는 대조도 직접 실행했다.
- required_heading_weight와 load_theme의 하한 검사, 네 테마별 실제 DOM 기대값이 새 사용자 기준과 일치한다. 부적합 하한 검사는 저장소 파일을 고치지 않고 `/tmp`의 테마 사본으로 실행했다.
- 이번 변경에는 기존 테마 CSS·템플릿·측정/정렬 알고리즘 변경이 없다. 이번 확인은 위 남은 항목과 전체 회귀 테스트 범위이며, 전차 검수의 모든 개별 입력을 다시 재현한 것으로 확대 해석하지 않는다.

## 새 발견 사항

| # | 심각도 | 파일:줄 | 내용 | 재현 방법 | 수정 방향 |
|---|---|---|---|---|---|
| — | — | — | 이번 범위에서 확정한 새 지적 없음 | — | — |

코드·테스트·다른 문서는 수정하지 않았다. 재현 스크립트·가상 작업·로그·캡처는 `/tmp/m8a3-review/`에만 두고, 이 보고서 한 파일만 커밋한다.
