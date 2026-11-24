# Codex 요청: M8-C(색 후보 · PDF 내보내기) 검수

> 이 문서를 Codex에 그대로 전달하세요. **코드 수정이 아니라 검수 보고서 작성**을 요청합니다. 구현은 Claude가 했고, 수정이 필요하면 보고서를 본 뒤 Claude가 합니다.

## 1. 요청
- 저장소·브랜치: `huynsolm/template`, `ccr-f9c07036-vgvm5j`
- 범위: `577aabc..HEAD` (M8-C 구현 커밋. 이 문서도 같은 커밋에 있음)
- 기준: `CODEX_TASK_M8C.md`(사용자 결정 2026-11-24 포함), `AGENTS.md`, `CLAUDE_HANDOFF.md`의 "M8-C 현재 상태"
- 산출물: 저장소 루트의 `M8_C_REVIEW.md`(한국어) **한 파일만** 커밋·푸시. 코드·테스트·다른 문서는 수정하지 않는다.

## 2. 실행
```bash
git fetch origin && git checkout ccr-f9c07036-vgvm5j && git pull --ff-only
cd detail-page-auto
uv pip sync --python .venv/bin/python --require-hashes requirements.lock   # pypdf 추가
.venv/bin/python -m pytest -q tests/test_m8c.py
.venv/bin/python -m pytest -q
git status --porcelain=v1
.venv/bin/python tools/make_screenshots.py --m8c-only --images /tmp/m8c-shots --samples /tmp/m8c-samples --output /tmp/m8c-out
```
렌더 테스트와 수동 재현은 순서대로 실행한다.

## 3. 중점 검수 항목 (각각 문제 없음 / 문제 있음(근거))
1. **지시서 대조**: `CODEX_TASK_M8C.md` 1~6절을 충족·부분·미충족 표로.
2. **색 후보**: 배경 제외·무채색 제외·결정성·AI 생성 이미지 제외가 맞는가. 투명 PNG, 배경 제거된 사진, 상품과 배경 색이 비슷한 사진, 아주 작은 사진에서의 동작. 고르기 전에 색이 바뀌는 경로가 없는가.
3. **PDF 쪽 나누기**: 테마 7종·긴 문서·`max_height` 변경 시 PDF 쪽 수와 크기가 JPG와 맞는가. 빈 쪽·쪽 넘침이 생기는 입력이 있는가(+2px 여유의 타당성).
4. **글자 보존 검사**: 숨김 요소·`text-transform`·연출 이미지 문구·특수 문자(·, ※, 이모지)·영문 하이픈에서 오탐/미탐이 있는가. 빠지면 파일을 남기지 않는가.
5. **안전**: PDF 생성 중 외부 요청 0, 번들 밖 파일 접근 불가, `export_block`(AI 이미지 출처) 동일 적용, DRAFT 표시.
6. **기존 결과 불변**: `capture`의 `open_offline` 분리 후 테마 7종 JPG·PNG·HTML·픽셀이 그대로인가.
7. **의존성**: `pypdf` 추가가 해시 잠금으로 되어 있고 다른 패키지 버전이 바뀌지 않았는가.
8. **화면**: ①·⑤ 색 후보, ⑦ PDF 만들기·다운로드, ZIP 포함.
9. **테스트 품질**: 실제 Chromium, 건너뛰기·약화된 단언 없음. 글자 누락 테스트가 추출 함수를 바꿔 끼우는 방식인데 충분한가.
10. **캔바 확인 절차**: `docs/canva-check.md`와 가상 샘플 PDF가 사용자가 따라 하기에 충분한가.

## 4. 구현 측 결정 (동의/반대 판정 요청)
1. 색 후보는 작업 생성 때가 아니라 요청할 때 계산해 manifest에 기록(모든 작업 생성이 느려지지 않도록).
2. PDF는 렌더링 때 자동으로 만들지 않고 ⑦·CLI에서 요청할 때 만든다(미리보기마다 PDF를 만들면 느림).
3. 쪽 높이에 2px 여유(반올림 때문에 내용이 다음 쪽으로 넘치는 것 방지) — PDF 쪽 높이는 JPG보다 2px(1.5pt) 크다.
4. 글자 검사는 문서 필드가 아니라 실제 페이지의 보이는 텍스트 노드 전체를 기준으로 한다(렌더링되지 않는 필드 오탐 방지).
5. Pretendard 가변 글꼴이 Type3로 들어가는 것은 그대로 두고 manifest·README에 기록(캔바 확인 결과로 판단).

## 5. 보고서 형식 (`M8_C_REVIEW.md`)
```markdown
# M8-C 검수 보고서
## 요약
- 판정: 완료 / 조건부 / 재작업 필요
- 실행 결과: (환경, 명령, passed/failed/skipped, git status)
## 지시서 대조표
| 항목 | 판정 | 근거 |
## 발견 사항
| # | 심각도 | 파일:줄 | 내용 | 재현 방법(실제 입력과 결과) | 수정 방향 |
## 중점 검수 항목 결과 (3장 1~10)
## 구현 측 결정에 대한 의견 (4장 1~5)
## 확인 질문
```
- 심각도: **Critical**(글자 누락 PDF 통과, 확인 없이 승인/일반 파일명, 기존 결과 변경, 외부 요청) / **Important**(지시서 미충족, 잘못된 기록·표시) / **Minor**. 재현하지 못한 지적은 Minor "미재현".
