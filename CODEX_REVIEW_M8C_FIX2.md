# Codex 요청: M8-C 재검수 2 지적 수정분 확인

> 이 문서를 Codex에 그대로 전달하세요. **코드 수정이 아니라 확인 보고서 작성**을 요청합니다.

## 1. 요청
- 저장소·브랜치: `huynsolm/template`, `ccr-f9c07036-vgvm5j`
- 범위: `49c2083..` 이 문서가 들어 있는 커밋 (M8-C 수정 커밋 하나. 디자인 작업 커밋은 범위 밖)
- 기준: `M8_C_REVIEW_2.md`, `CODEX_TASK_M8C.md`, `AGENTS.md`
- 산출물: 저장소 루트의 `M8_C_REVIEW_3.md`(한국어) **한 파일만** 커밋·푸시. 코드·테스트·다른 문서는 수정하지 않는다.

## 2. 실행
```bash
git fetch origin && git checkout ccr-f9c07036-vgvm5j && git pull --ff-only
cd detail-page-auto
.venv/bin/python -m pytest -q tests/test_m8c_review.py tests/test_m8c.py
.venv/bin/python -m pytest -q
git status --porcelain=v1
```
지난 보고서의 재현 1·2를 다시 실행한다.

## 3. 지적별 수정 (각각 해결 / 미해결)
| # | 수정 | 회귀 테스트 (`tests/test_m8c_review.py`) |
|---|---|---|
| R-C-1 | 글자의 표시 여부를 둘로 나눠 판단: `display:contents`는 건너뛰고 가장 가까운 상자 있는 조상의 `checkVisibility()`(조상 `display:none`·`content-visibility` 반영), 글자 자체는 부모의 계산된 `visibility`(상속, 자식이 다시 `visible`로 바꾼 경우 포함) | `test_visible_text_inside_display_contents_is_checked`(인쇄 직전 누락 주입 → 실패), `test_display_contents_text_present_passes_and_hidden_cases_still_skip` |
| R-I-1 | 알파 채널이 실제로 무언가를 가릴 때(최소 알파 < 255)만 전경 마스크. 모두 불투명하면 RGB와 같은 가장자리 배경 제외. 색 알고리즘 버전 `colors-3` | `test_opaque_rgba_photo_gives_the_same_candidates_as_rgb` |

새 테스트 3개 중 2개는 수정 전(`49c2083`)에서 실패하고 수정 후 통과한다. 기존 숨김·투명 PNG·투명 팔레트 회귀 테스트는 그대로 통과한다.

## 4. 보고서 형식 (`M8_C_REVIEW_3.md`)
```markdown
# M8-C 재검수 3 보고서
## 요약
- 판정: 완료 / 조건부 / 재작업 필요
- 실행 결과
## 지적별 판정
| # | 판정 | 근거(실행/판독) |
## 새 발견 사항
| # | 심각도 | 파일:줄 | 내용 | 재현 방법 | 수정 방향 |
```
