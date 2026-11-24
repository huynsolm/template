# Codex 요청: M8-B 재검수 2 지적 수정분 확인

> 이 문서를 Codex에 그대로 전달하세요. **코드 수정이 아니라 확인 보고서 작성**을 요청합니다.

## 1. 요청
- 저장소·브랜치: `huynsolm/template`, `ccr-f9c07036-vgvm5j`
- 범위: `54dbd09..HEAD`
- 기준: `M8_B_REVIEW_2.md`, `CODEX_TASK_M8B.md`의 **"검수 후 확정한 정책"** 절(이번에 추가), `AGENTS.md`
- 산출물: 저장소 루트의 `M8_B_REVIEW_3.md`(한국어) **한 파일만** 커밋·푸시. 코드·테스트·다른 문서는 수정하지 않는다.

## 2. 실행
```bash
git fetch origin && git checkout ccr-f9c07036-vgvm5j && git pull --ff-only
cd detail-page-auto
.venv/bin/python -m pytest -q tests/test_m8b_review.py tests/test_m8b.py
.venv/bin/python -m pytest -q
git status --porcelain=v1
```
지난 보고서의 재현 1~3을 다시 실행한다.

## 3. 지적별 수정 (각각 해결 / 미해결)
| # | 수정 | 회귀 테스트 (`tests/test_m8b_review.py`) |
|---|---|---|
| R2-C-1 | render manifest에 `ai_images`·`image_sources_known` 기록. `image_checks.export_block`이 AI 이미지가 알려진 결과(플래그, 연출 표시 `staged-note`, 작업 facts)에 출처가 없으면 내보내기 거부(파일 생성 전). ⑤에도 오류 표시 | `test_staged_draft_without_job_files_cannot_be_exported_without_sources`, `test_legacy_staged_render_without_flags_is_not_exported` |
| R2-I-1 | 작업 manifest의 `image_checks` 중 같은 번호·파일·출처인 것만 새 렌더에 전달. ⑤는 이미지별로 확인 완료/확인 전을 나눠 표시(페이지 승인은 별도 표시) | `test_kept_confirmations_reach_new_previews_and_the_screen`, `test_partial_confirmation_is_shown_per_image`, `test_checks_for_a_different_image_are_not_carried` |
| R2-M-1 | 도구 이름에 `·` 허용, 오류 문구에 허용 문자와 예시 안내 | `test_generator_accepts_names_with_a_middle_dot` |

새 회귀 테스트 8개 중 5개는 수정 전(`54dbd09`)에서 실패하고 수정 후 통과한다(나머지 3개는 다른 이미지 확인 미전달·정상 이름 통과처럼 유지돼야 하는 동작).
확인 질문 2건(확인 유지와 4절의 관계, 전경 면적 비교 제외)은 지시서의 "검수 후 확정한 정책" 절에 문서화했다. 다시 승인할 때는 ⑥에서 이미지별 확인을 다시 체크한다(페이지 승인과 이미지 확인은 별개).

## 4. 보고서 형식 (`M8_B_REVIEW_3.md`)
```markdown
# M8-B 재검수 3 보고서
## 요약
- 판정: M8-C 진행 가능 / 조건부 / 재작업 필요
- 실행 결과
## 지적별 판정
| # | 판정 | 근거(실행/판독) |
## 새 발견 사항
| # | 심각도 | 파일:줄 | 내용 | 재현 방법 | 수정 방향 |
```
