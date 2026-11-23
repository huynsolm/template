# Codex 요청: M8-A 최종 확인 (재검수 2 후속)

> 이 문서를 Codex에 그대로 전달하세요. **코드 수정이 아니라 확인 보고서 작성**을 요청합니다.

## 1. 요청
- 저장소·브랜치: `huynsolm/template`, `ccr-f9c07036-vgvm5j`
- 범위: `fd58f47..HEAD`
- 기준: `M8_A_REVIEW_2.md`, `CODEX_TASK_M8A.md`의 **"사용자 결정 (2026-11-24)"** 절(이번에 추가, 본문보다 우선), `AGENTS.md`
- 산출물: 저장소 루트의 `M8_A_REVIEW_3.md`(한국어) **한 파일만** 커밋·푸시. 코드·테스트·다른 문서는 수정하지 않는다.

## 2. 실행
```bash
git fetch origin && git checkout ccr-f9c07036-vgvm5j && git pull --ff-only
cd detail-page-auto
.venv/bin/python -m pytest -q tests/test_m8a_review.py tests/test_m8a.py
.venv/bin/python -m pytest -q
git status --porcelain=v1
```
R2-1 재현(이전 규칙으로 승인된 modern 작업 → 새 미리보기 → 앱 재개 → ⑦ 다운로드)을 다시 실행한다.

## 3. 확인 항목 (각각 해결 / 미해결)
| 항목 | 변경 | 테스트 |
|---|---|---|
| #8 natural 제목 굵기 | 사용자 결정으로 규칙 확정: 제목 800 이상, 제목 글꼴의 최대 굵기가 더 낮으면 그 값(natural 고운바탕 700, impact 검은고딕 400). `themes.required_heading_weight`로 테마 로딩 시 검사. DOM 검사도 modern·industrial ≥ 800, natural = 700, impact = 400으로 강화 | `test_m8a.py::test_dom_type_scale_spacing_and_fonts`, `test_heading_weight_must_reach_800_or_the_faces_heaviest_weight` |
| R2-1 재개 시 최신 미리보기 | `editor.resume_bundle`: 승인 결과 → 미리보기 순으로 현재 문구·테마·측정 규칙에 맞는 것을 고른다(화면 재개가 사용). `preview_job`은 더 이상 맞지 않는 이전 승인(`rendered_job`)을 해제하고 `review_accepted=false`로 둔다 | `test_stale_old_approval_falls_back_to_the_current_preview` |
| 확인 질문 2·3 | 사용자 결정: 자동 정렬은 5종만, 4.1 data 속성은 `MEASURE_SPEC` 선택자 측정으로 대체(지시서에 기록). 코드 변경 없음 | — |

## 4. 보고서 형식 (`M8_A_REVIEW_3.md`)
```markdown
# M8-A 최종 확인 보고서
## 요약
- 판정: M8-B 진행 가능 / 조건부 / 재작업 필요
- 실행 결과: (환경, 명령, passed/failed/skipped, git status)
## 항목별 판정
| 항목 | 판정 | 근거(실행/판독) |
## 새 발견 사항
| # | 심각도 | 파일:줄 | 내용 | 재현 방법 | 수정 방향 |
```
