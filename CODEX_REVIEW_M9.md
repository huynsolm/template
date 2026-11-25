# Codex 요청: M9(디자인 v2 · 입력 항목 분리) 검수

> 이 문서를 Codex에 그대로 전달하세요. **코드 수정이 아니라 검수 보고서 작성**을 요청합니다.

## 1. 요청
- 저장소·브랜치: `huynsolm/template`, `ccr-f9c07036-vgvm5j`
- 범위: `9931443..HEAD` (M9 구현 커밋. 이 문서도 같은 커밋에 있음)
- 기준: `CODEX_TASK_M9.md`(사용자 결정 2026-11-25), `AGENTS.md`(classic 규칙이 v1로 한정됨), `CLAUDE_HANDOFF.md`의 "M9 현재 상태"
- 산출물: `M9_REVIEW.md`(한국어) **한 파일만** 커밋·푸시. 코드·테스트·다른 문서는 수정하지 않는다.

## 2. 실행
```bash
git fetch origin && git checkout ccr-f9c07036-vgvm5j && git pull --ff-only
cd detail-page-auto
.venv/bin/python -m pytest -q tests/test_m9.py tests/test_m9_colors.py
.venv/bin/python -m pytest -q
git status --porcelain=v1
.venv/bin/python tools/make_screenshots.py --m9-only --images /tmp/m9-shots --output /tmp/m9-out
```
렌더 테스트와 수동 재현은 순서대로 실행한다.

## 3. 중점 검수 항목
1. **v1 보존**: 디자인 버전 키가 없는 기존 작업·기존 결과·classic v1 고정 비교가 그대로인가. v1 작업의 manifest·facts·draft·HTML이 바뀌지 않는가(새 필드가 비었을 때).
2. **버전 전환**: ⑤ 전환·`preview_job(design_version=)`·승인·재생성·일괄 작업·내보내기에서 버전이 일관되고, 버전이 다르면 승인·스냅샷이 재사용되지 않는가.
3. **v2 품질(7종)**: 글자 하한 22px(라벨 15px), 허용 글꼴, 가로 넘침, 좌우 여백, 대비(aa), 줄 수 측정 대상 선택자 대응(특히 hero `p:not(.price)`, stats `dt/dd`, cases `h3/h3+p`).
4. **문구 보존**: 숫자 띠 괄호 설명 분리, 공통 사양 분리(`split_spec_table`)에서 글자·셀이 빠지거나 바뀌지 않는가. PDF 글자 검사 통과(7종 × 샘플 2개).
5. **입력 항목**: 가격 공백 → 생략, 판매 상태 유지. 업종·용도·적용 사례가 비면 기존과 같은 결과. ① 편집기·facts.json 왕복.
6. **안전·기존 규칙**: AI 이미지 출처·연출 표시·이미지별 승인, `unsafe_allow_html` 미사용, 외부 요청 0, 테마 CSS 검증(외부 URL·주석 금지).
7. **테스트 품질**: 실제 Chromium·AppTest, 건너뛰기 없음. 기존 테스트 변경 2건(readiness 가격 권장, app 테마 변경 테스트의 v1 고정)의 타당성.

8. **색 방식**(추가 결정): 테마 기본(tone/duo)·단색 선택, 보조색 자동/직접, 그라데이션 적용 구간 제한(해결·첫 화면 띠·사진 뒤 배경), 글자 영역의 그라데이션 최저 대비(21곳 표본) ≥ 4.5와 조정·기록, 표·본문·구매 안내 단색, 사진 무변경, v1 무변경. `tests/test_m9_colors.py`.

## 4. 구현 측 결정 (동의/반대)
1. 라이브러리 기본은 v1, 앱·CLI(`prompt`/`generate`)·일괄 작업의 새 작업만 v2(기존 호출·테스트 호환).
2. v2는 classic 포함 7종 모두 aa 대비 정책과 M8-A 줄 수 규칙 적용.
3. v2 자동 정렬은 solution만(나머지는 디자인상 왼쪽 고정). M8-A의 "5종 자동 정렬"은 v1 새 테마에 해당.
4. 숫자 띠 값은 줄이지 않고(fit-stats 미사용) 줄바꿈 — 넘치면 M8-A 측정이 판매자 입력 초과로 알림.
5. 공통 사양 분리는 2행 이상에서 모든 행 값이 같은 열만, 모든 열이 같으면 분리하지 않음. 표 머리말 "세부 사양".
6. PDF 글자 추출을 막는 `tabular-nums`·`opacity`는 v2에서 쓰지 않음.

## 5. 보고서 형식 (`M9_REVIEW.md`)
```markdown
# M9 검수 보고서
## 요약
- 판정: 완료 / 조건부 / 재작업 필요
- 실행 결과
## 지시서 대조표
| 항목 | 판정 | 근거 |
## 발견 사항
| # | 심각도 | 파일:줄 | 내용 | 재현 방법 | 수정 방향 |
## 구현 측 결정에 대한 의견
## 확인 질문
```
