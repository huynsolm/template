# Codex 요청: M8-C 검수 지적 수정분 재검수

> 이 문서를 Codex에 그대로 전달하세요. **코드 수정이 아니라 재검수 보고서 작성**을 요청합니다.

## 1. 요청
- 저장소·브랜치: `huynsolm/template`, `ccr-f9c07036-vgvm5j`
- 범위: `ac055d8..` 이 문서가 들어 있는 커밋 (M8-C 수정 커밋 하나. 그 뒤의 디자인 시안 커밋은 범위 밖)
- 기준: `M8_C_REVIEW.md`, `CODEX_TASK_M8C.md`, `AGENTS.md`, `CLAUDE_HANDOFF.md`의 "M8-C 현재 상태"
- 산출물: 저장소 루트의 `M8_C_REVIEW_2.md`(한국어) **한 파일만** 커밋·푸시. 코드·테스트·다른 문서는 수정하지 않는다.

## 2. 실행
```bash
git fetch origin && git checkout ccr-f9c07036-vgvm5j && git pull --ff-only
cd detail-page-auto
.venv/bin/python -m pytest -q tests/test_m8c_review.py tests/test_m8c.py
.venv/bin/python -m pytest -q
git status --porcelain=v1
```
지난 보고서의 재현 A~E를 그대로 다시 실행한다. 렌더 테스트와 수동 재현은 순서대로 실행한다.

## 3. 지적별 수정 (각각 해결 / 부분 / 미해결)
| # | 수정 | 회귀 테스트 (`tests/test_m8c_review.py`) |
|---|---|---|
| C-1 | 문구마다 **그려진 쪽과 높이**(문구 상자 ±4pt 안의 글자 기준선)에서만 찾고, 긴 문구부터 찾은 글자를 소모해 재사용하지 않음. 실패 위치는 실제로 빠진 문구 | `test_repeated_text_missing_at_print_time_fails[classic/modern]`, `test_text_contained_in_a_longer_text_is_matched_separately`, `test_unique_text_missing_at_print_time_fails`, `test_repeated_text_present_everywhere_passes` — 모두 실제 Chromium 인쇄 직전(`beforeprint`)에 누락 주입 |
| I-1 | `checkVisibility({checkVisibilityCSS:true})`로 조상 `display:none`·`visibility:hidden` 반영, 크기 없는 텍스트 제외 | `test_text_hidden_by_an_ancestor_is_not_required` |
| I-2 | 투명도가 있으면(알파 채널·투명 팔레트) 불투명 픽셀만 사용, RGBA는 사전곱으로 축소, 배경 추정 안 함 | `test_identical_looking_rgba_photos_give_identical_candidates`, `test_transparent_palette_png` |
| I-3 | `docs/canva-check.md`를 샘플 PDF에서 읽은 쪽 수·크기로 생성(modern 3, natural 3, classic 2쪽). 쪽 수·쪽 크기·글자 편집·글꼴 대체·정렬·사진 분리·캡처 경로 칸. README는 "확인 예정" 유지 | `test_canva_checklist_matches_the_sample_pdfs` |
| I-4 | 판매처 프로필 ZIP에도 PDF 포함. 기록된 PDF가 없으면 두 ZIP 모두 거부 | `test_both_zips_carry_the_recorded_pdf`, `test_zip_refuses_a_recorded_pdf_that_is_gone`, `test_profile_zip_without_pdf_has_no_pdf_record` |
| M-1 | 이체 선택자(U+FE00–FE0F, U+E0100–E01EF)만 무시하고 `text_check.ignored_presentation`에 개수 기록. ⭐ 등 실제 문자 누락은 그대로 실패 | `test_variation_selector_alone_does_not_fail_but_is_recorded`, `test_a_missing_emoji_still_fails` |

기존 `test_m8c.py`의 추출 함수 교체 테스트는 새 위치 추출 단계(`page_characters`)를 바꾸도록 옮겼다(검증 내용 동일).

## 4. 중점 확인
1. 위치 허용 범위(±4pt)와 문구 상자 기준이 줄바꿈·여러 줄 문구·표·숫자 띠·위첨자에서 오탐/미탐을 만드는가.
2. 텍스트 추출 순서가 화면 순서와 다른 테마(modern 등)에서도 위치 기반 대응이 맞는가.
3. ZWJ(U+200D) 등 이체 선택자 외의 서식 문자는 무시하지 않았다 — 이 정책이 타당한가.

## 5. 보고서 형식 (`M8_C_REVIEW_2.md`)
```markdown
# M8-C 재검수 보고서
## 요약
- 판정: 완료 / 조건부 / 재작업 필요
- 실행 결과
## 지적별 판정
| # | 판정 | 근거(실행/판독) |
## 새 발견 사항
| # | 심각도 | 파일:줄 | 내용 | 재현 방법 | 수정 방향 |
```
