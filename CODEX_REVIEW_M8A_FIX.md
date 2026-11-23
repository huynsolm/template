# Codex 요청: M8-A 검수 지적 수정분 재검수

> 이 문서를 Codex에 그대로 전달하세요. **코드 수정이 아니라 재검수 보고서 작성**을 요청합니다. 수정은 Claude가 했고, 추가 수정이 필요하면 보고서를 본 뒤 Claude가 합니다.

## 1. 요청
- 저장소·브랜치: `huynsolm/template`, `ccr-f9c07036-vgvm5j`
- 범위: `b8a24d4..HEAD` (지적 수정 커밋. 이 문서도 같은 커밋에 있음)
- 기준 문서: `M8_A_REVIEW.md`(지난 검수), `CODEX_TASK_M8A.md`, `AGENTS.md`, `CLAUDE_HANDOFF.md`의 "M8 결정과 M8-A 현재 상태"
- 산출물: 저장소 루트의 `M8_A_REVIEW_2.md`(한국어) **한 파일만** 커밋·푸시. 코드·테스트·다른 문서는 수정하지 않는다.
- 실제로 실행한 것과 코드만 읽고 판단한 것을 구분해 적는다.

## 2. 실행
```bash
git fetch origin && git checkout ccr-f9c07036-vgvm5j && git pull --ff-only
cd detail-page-auto
.venv/bin/python -m pytest -q tests/test_m8a_review.py tests/test_m8a.py
.venv/bin/python -m pytest -q
git status --porcelain=v1
```
지난 검수에서 쓴 재현 입력(`/tmp/m8a-review-probes/` 등)을 그대로 다시 실행해 결과가 바뀌었는지 확인한다.

## 3. 지적별 수정 내용 (각각 해결 / 부분 / 미해결 판정 요청)
| # | 수정 | 회귀 테스트 (`tests/test_m8a_review.py`) |
|---|---|---|
| 1 | 측정 버전 `MEASURE_VERSION`을 manifest `copy_measure_version`에 기록. 새 테마는 `bundle_matches`에서 버전이 다르거나 없으면 재사용하지 않는다. 이전 폴더는 지우지 않는다. | `test_preview_from_an_older_measurement_version_is_not_reused` |
| 2 | 판매자 섹션(stats·targets·structure)을 섹션 합계에 포함. 검수 항목 `detail.source='seller'`, 사유에 "① 상품 정보에서 고치고 새 작업" 안내. | `test_seller_section_density_is_checked_and_points_to_product_info` |
| 3 | `overflow_regenerate_job`은 AI 문구 섹션(hero·pain·solution·features·how_to·faq)만 요청. 남는 것이 없으면 작업을 만들지 않고 오류 안내. 화면 버튼도 AI 초과가 없으면 비활성 + 안내 문구. | `test_seller_only_overflow_does_not_create_a_rewrite_job` |
| 4 | `SECTION_TOO_DENSE`·`LIST_TOO_MANY` 요청에 `current`(섹션의 현재 문구, id·이미지·변형 제외)와 `fields`(칸별 측정 줄 수·문구)를 넣음. 미리보기가 없으면 수집 시 렌더링한 최신 결과의 측정을 사용. | `test_density_rewrite_request_carries_the_current_copy` |
| 5 | `preview_job`이 `measured.json`에 마지막 측정 스냅샷을 기록하고 `save_draft`는 이를 지우지 않음(`editor.latest_measurement`). ④는 미저장 편집·저장 후 모두 "지난 미리보기 기준 N줄 … 다시 미리보기 필요"로 표시(측정 당시 문구와 현재 입력 비교). | `test_saved_edit_keeps_the_last_measurement_as_stale`, `test_review_screen_marks_badges_stale_before_and_after_save` |
| 6 | 줄 박스 그룹화에서 폭 0 상자를 버리지 않음(높이 0만 제외). `layout.js`도 동일. | `test_prewrap_empty_lines_are_counted`(classic, `첫째\n\n셋째` → 3줄), `test_prewrap_empty_lines_drive_alignment` |
| 7 | `fit-stats.js`가 CSS 변수 `--fit-min`보다 작게 줄이지 않음(새 테마 `design-system.css`에서 22). 그래도 넘치면 줄바꿈 허용 → 측정에서 1줄 초과로 검수(판매자 입력 안내). 기존 테마는 변수가 없어 이전과 같은 동작. | `test_stats_value_keeps_the_22px_minimum_and_is_reported[modern/natural]` |
| 8 | **미수정 — 사용자 결정 대기**(natural 대표 제목 700 예외 여부). | — |
| 9 | 숫자 띠 라벨 `items.{i}.label`을 1줄 측정 대상에 추가(크기 16px 예외와 줄 수 규칙은 별개). | `test_stats_label_is_measured` |

회귀 테스트 11개는 수정 전 코드(`b8a24d4`)에서 모두 실패하고 수정 후 통과함을 구현 측에서 확인했다.

## 4. 중점 확인
1. 기존 테마 3종의 HTML·CSS·픽셀·검수 상태·파일명이 여전히 같은가(`fit-stats.js` 변경 포함).
2. 측정 버전 도입으로 승인된 이전 새 테마 작업의 내보내기가 막히는 경우 안내가 충분한가(다시 미리보기·승인 필요).
3. 폭 0 상자를 세면서 생기는 과대 계산(인라인 요소 경계, 끝 줄바꿈 등)이 없는가.
4. 숫자 띠 값이 줄바꿈될 때 레이아웃이 깨지거나 860px 밖으로 넘치지 않는가.
5. `<copy_overflow>`의 `current`·`fields`가 데이터 블록으로 이스케이프되는가.

## 5. 보고서 형식 (`M8_A_REVIEW_2.md`)
```markdown
# M8-A 재검수 보고서
## 요약
- 판정: M8-B 진행 가능 / 조건부 / 재작업 필요
- 실행 결과: (환경, 명령, passed/failed/skipped, git status)
## 지적별 판정
| # | 판정 | 근거(실행/판독) |
## 새 발견 사항
| # | 심각도 | 파일:줄 | 내용 | 재현 방법 | 수정 방향 |
## 남은 확인 질문
```
