# Codex 요청: M9 검수 지적 수정분 재검수

> 이 문서를 Codex에 그대로 전달하세요. **코드 수정이 아니라 재검수 보고서 작성**을 요청합니다.

## 1. 요청
- 저장소·브랜치: `huynsolm/template`, `ccr-f9c07036-vgvm5j`
- 범위: `7f09996..HEAD`
- 기준: `M9_REVIEW.md`, `CODEX_TASK_M9.md`, `AGENTS.md`
- 산출물: `M9_REVIEW_2.md`(한국어) **한 파일만** 커밋·푸시. 코드·테스트·다른 문서는 수정하지 않는다.

## 2. 실행
```bash
git fetch origin && git checkout ccr-f9c07036-vgvm5j && git pull --ff-only
cd detail-page-auto
.venv/bin/python -m pytest -q tests/test_m9_review.py tests/test_m9.py tests/test_m9_colors.py
.venv/bin/python -m pytest -q
git status --porcelain=v1
```
지난 보고서의 재현 I-1~I-6을 다시 실행한다.

## 3. 지적별 수정 (각각 해결 / 부분 / 미해결)
| # | 수정 | 회귀 테스트 (`tests/test_m9_review.py`) |
|---|---|---|
| I-1 | impact·bold 제목 띠의 라벨·판매 상태까지 검사한 글자색(`--on-hero-band`) 사용 | `test_all_text_on_gradients_meets_contrast[테마 7 × 브랜드 3]` — 실제 DOM 글자색을 manifest 그라데이션 전체(21곳)와 대조 |
| I-2 | `regenerate_job`(초과 문구 재생성 포함)이 색 방식·보조색을 자식 작업에 넘김 | `test_regeneration_keeps_colour_settings`, `test_overflow_rewrite_keeps_colour_settings` |
| I-3 | `render.job_theme_styles`로 생성·수집·편집·승인 모두 버전별 대비 정책. v2 classic은 aa·legacy 경고 없음, v1 classic은 legacy 경고 유지 | `test_v2_classic_is_aa_at_every_step`, `test_v1_classic_still_warns_for_low_contrast` |
| I-4 | 숫자 띠 괄호 설명을 역할 `note`(1줄)로 해당 `items.N.value`에 측정, 섹션 합계 포함. 판매자 입력 안내 | `test_stats_note_lines_are_measured`, `test_short_stats_note_is_fine` |
| I-5 | 템플릿 전용 `split`은 사본에만 → `input.json`은 공개 스키마 그대로, M1 재입력 가능 | `test_v2_bundle_input_json_renders_again` |
| I-6 | `Targets.groups`가 있으면 groups를 이은 목록 = items (스키마 검증, 불일치 거부) | `test_targets_items_must_match_groups` |

새 테스트 중 8개는 수정 전(`7f09996`)에서 실패하고 수정 후 통과한다. 기존 테스트 변경: `test_m8a.py::test_rule_helpers`의 줄 한도 표에 `note: 1` 추가(새 역할).

## 4. 보고서 형식 (`M9_REVIEW_2.md`)
```markdown
# M9 재검수 보고서
## 요약
- 판정: 완료 / 조건부 / 재작업 필요
- 실행 결과
## 지적별 판정
| # | 판정 | 근거 |
## 새 발견 사항
| # | 심각도 | 파일:줄 | 내용 | 재현 방법 | 수정 방향 |
```
