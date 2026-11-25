# Codex 요청: M9 재검수 2 지적(R-I-1) 수정 확인

> 이 문서를 Codex에 그대로 전달하세요. **코드 수정이 아니라 확인 보고서 작성**을 요청합니다.

## 1. 요청
- 저장소·브랜치: `huynsolm/template`, `ccr-f9c07036-vgvm5j`
- 범위: `0d96635..HEAD`
- 기준: `M9_REVIEW_2.md`, `CODEX_TASK_M9.md`, `AGENTS.md`
- 산출물: `M9_REVIEW_3.md`(한국어) **한 파일만** 커밋·푸시. 코드·테스트·다른 문서는 수정하지 않는다.

## 2. 실행
```bash
git fetch origin && git checkout ccr-f9c07036-vgvm5j && git pull --ff-only
cd detail-page-auto
.venv/bin/python -m pytest -q tests/test_m9_review.py tests/test_batch.py
.venv/bin/python -m pytest -q
git status --porcelain=v1
```
지난 보고서의 재현(이전 코드 `7f09996`으로 만든 승인 결과를 현재 코드로 재개·다운로드·일괄 조회)을 다시 실행한다.

## 3. 수정
| # | 수정 | 회귀 테스트 |
|---|---|---|
| R-I-1 | v2 결과 manifest에 `render_revision`(`V2_RENDER_REVISION='v2-r2'`)을 기록하고, `render.snapshot_is_current`로 판정한다. `bundle_matches`(재개·⑤·⑦ 다운로드·내보내기)와 일괄 승인 조회(`batch._approval_is_current`, 승인 번들 자체의 manifest 확인)가 같은 판정을 쓴다. 옛 결과는 지우지 않고, 새 미리보기를 만들면 옛 승인이 해제되어 다시 우선되지 않는다. v1(디자인 버전 없음)은 영향 없음 | `tests/test_m9_review.py::test_older_v2_renders_are_not_reused_by_app_download_or_batch`, `test_v1_renders_are_unaffected_by_the_v2_revision` |

`test_older_v2_renders_are_not_reused_by_app_download_or_batch`는 수정 전(`0d96635`)에서 실패하고 수정 후 통과한다. 이 테스트는 옛 결과를 "render_revision 없음"으로 흉내 낸 고정 입력을 쓴다. 실제 이전 코드로 만든 결과는 위 재현으로 확인해 달라.
`MEASURE_VERSION`은 올리지 않았다(v1 새 테마의 측정 방식은 바뀌지 않아 v1 미리보기를 불필요하게 무효화하지 않기 위해). v2 측정 변경은 `render_revision`이 대신 구별한다.

## 4. 보고서 형식 (`M9_REVIEW_3.md`)
```markdown
# M9 재검수 3 보고서
## 요약
- 판정: 완료 / 조건부 / 재작업 필요
- 실행 결과
## 지적별 판정
| # | 판정 | 근거 |
## 새 발견 사항
| # | 심각도 | 파일:줄 | 내용 | 재현 방법 | 수정 방향 |
```
