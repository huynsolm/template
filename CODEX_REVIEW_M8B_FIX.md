# Codex 요청: M8-B 검수 지적 수정분 재검수

> 이 문서를 Codex에 그대로 전달하세요. **코드 수정이 아니라 재검수 보고서 작성**을 요청합니다.

## 1. 요청
- 저장소·브랜치: `huynsolm/template`, `ccr-f9c07036-vgvm5j`
- 범위: `b4e55e4..HEAD`
- 기준: `M8_B_REVIEW.md`, `CODEX_TASK_M8B.md`, `AGENTS.md`, `CLAUDE_HANDOFF.md`의 "M8-B 현재 상태"
- 산출물: 저장소 루트의 `M8_B_REVIEW_2.md`(한국어) **한 파일만** 커밋·푸시. 코드·테스트·다른 문서는 수정하지 않는다.

## 2. 실행
```bash
git fetch origin && git checkout ccr-f9c07036-vgvm5j && git pull --ff-only
cd detail-page-auto
.venv/bin/python -m pytest -q tests/test_m8b_review.py tests/test_m8b.py
.venv/bin/python -m pytest -q
git status --porcelain=v1
```
지난 보고서의 재현 A~G를 그대로 다시 실행한다. 렌더 테스트와 수동 재현은 순서대로 실행한다.

## 3. 지적별 수정 (각각 해결 / 부분 / 미해결)
| # | 수정 | 회귀 테스트 (`tests/test_m8b_review.py`) |
|---|---|---|
| C-1 | `render()`가 작업 폴더(facts.json + manifest.json)를 읽을 때 `image_sources`를 기록 → ingest 렌더·미리보기·M1 모두 포함, ZIP으로 전달. 내보내기는 AI 이미지 작업인데 출처 기록이 없는 결과를 거부 | `test_ingest_render_and_export_carry_image_sources`, `test_export_refuses_a_render_without_image_sources` |
| C-2 | `render()`에서 AI 이미지가 있는 작업 폴더나 `staged` 이미지가 있는 문서는 `accept_review` 없이는 항상 DRAFT. 사진만 쓴 M1은 그대로 | `test_m1_render_of_an_ai_job_draft_stays_draft`, `..._staged_document_without_job_files_stays_draft`, `test_photo_only_m1_render_is_unchanged` |
| I-1 | 대표 사진 대체에서 AI 생성 이미지 제외, 실제 사진(또는 배경 변경 사진) 한 장 이상 필수 | `test_generated_picture_is_never_the_hero` |
| I-2 | 이름 정규화(`./`, `x/../`)로 입력 검증, 작업 생성 시 실제 경로·inode·내용 해시로 같은 파일 거부(복사 전) | `test_path_aliases_of_one_file_are_rejected`, `test_symlink_or_copy_names_resolving_to_one_file_are_rejected` |
| I-3 | 도구 이름 허용 문자 제한 + 도메인 형태·알려진 토큰 접두어·20자 이상 연속 영숫자 거부 | `test_generator_rejects_addresses_and_tokens`, `test_generator_accepts_tool_names` |
| I-4 | ⑤에 AI 이미지 목록과 확인 전/완료 표시 | `test_preview_screen_shows_ai_sources_and_pending_confirmation` |
| M-1 | 정책 확정: 승인 작업은 이미지가 같으면 이미지별 확인 유지(작업 안에서 이미지는 바뀌지 않음). 재미리보기에서 `AI_IMAGE_UNCONFIRMED`를 다시 만들지 않음. 새 미리보기는 항상 DRAFT | `test_confirmations_persist_on_an_unchanged_accepted_job` |

회귀 테스트 중 17개는 수정 전 코드(`b4e55e4`)에서 실패하고 수정 후 통과한다(나머지 7개는 사진 전용 M1·정상 도구 이름 등 변하지 않아야 하는 동작 확인).
확인 질문 2(전경 마스크 면적 비교)는 M8-B 범위에서 제외했다(배경 제거 모델이 선택 설치라 항상 쓸 수 없음).

## 4. 중점 확인
1. AI 이미지 작업에서 확인 없이 일반 파일명이 나오는 경로가 남아 있는가(일괄 작업, 테마 갤러리 썸네일 등 포함).
2. 사진만 쓴 작업의 테마 7종 HTML·픽셀·파일명이 여전히 같은가.
3. `sources_near`의 작업 폴더 판정(facts.json + manifest.json)이 오판하는 경우가 있는가.
4. 도구 이름 검사의 오탐(정상 이름 거부)이 실사용에 문제 되는가.

## 5. 보고서 형식 (`M8_B_REVIEW_2.md`)
```markdown
# M8-B 재검수 보고서
## 요약
- 판정: M8-C 진행 가능 / 조건부 / 재작업 필요
- 실행 결과
## 지적별 판정
| # | 판정 | 근거(실행/판독) |
## 새 발견 사항
| # | 심각도 | 파일:줄 | 내용 | 재현 방법 | 수정 방향 |
## 남은 확인 질문
```
