# M8-A 검수 보고서

## 요약

- 판정은 **조건부**다. 아래 Important 항목을 수정하고 회귀 검증한 뒤 M8-B로 진행하는 것을 권한다.
- 검수 범위는 `cdbf277..8a26a75`이며, 검수 대상 구현 커밋은 `8a26a759b2df5f02b81105dd8780b2e8b6067724`다. 저장소는 `huynsolm/template`, 브랜치는 `ccr-f9c07036-vgvm5j`다.
- 직접 확인한 발견 사항은 **Critical 0건, Important 8건, Minor 1건**이다. 기존 테마 3종의 결과 변경이나 문구 자동 삭제는 재현되지 않았다.
- 실행 환경은 Linux, Python 3.12, Chromium 156이며 검수 날짜는 2026-11-24 KST다. 가상 샘플과 임시 작업만 사용했다.
- 아래에서 **실행**은 pytest·Chromium·AppTest 또는 임시 작업으로 확인한 결과, **판독**은 코드·문서·Git diff를 읽은 판단을 뜻한다. 파일과 줄 번호는 검수 대상 커밋의 `detail-page-auto/` 기준이다.

### 직접 실행한 결과

| 명령·검사 | 결과 |
|---|---|
| `git fetch`, `git merge --ff-only origin/ccr-f9c07036-vgvm5j` | 원격 구현을 가져와 `8a26a75`에서 검수 |
| `.venv/bin/python -m pytest -q tests/test_m8a.py` | **21 passed, 0 failed, 0 skipped**, 150.10초, 종료 코드 0 |
| `.venv/bin/python -m pytest -q` | **457 passed, 0 failed, 0 skipped**, 1613.16초(26분 53초), 종료 코드 0 |
| 전체 테스트 직후 `git status --porcelain=v1` | 출력 없음. 보고서 작성 전 작업 트리 깨끗함 |
| `.venv/bin/python tools/make_screenshots.py --m8a-only --images /tmp/m8a-shots --output /tmp/m8a-out` | 종료 코드 0. modern·natural·impact·industrial의 상단 860×1800 PNG 4장 생성. 경로는 `/tmp/m8a-shots/m8a-long-{theme}.png` |
| 구현 전 `cdbf277`과 현재 코드로 `samples/product.json`을 각각 렌더링 | classic·minimal·bold 모두 HTML, CSS, 전체 페이지 픽셀, 검수 상태, JPG 파일명 일치. 현재 manifest에는 각각 측정 항목 15개 기록 |
| 별도 Chromium·AppTest 재현 | 아래 발견 사항 1~9와 정상 굵은 글씨·인라인 측정, 승인 후 검수 기록 보존, 부모 작업 불변 확인 |

예상한 구현 측 전용 테스트 수 21개와 실제 결과가 일치했다. 전체 실행 결과는 위 표의 직접 실행 수치로 판단했다. 재현용 스크립트·작업·출력은 `/workspace/work/m8a-review/`, `/tmp/m8a-review-probes/`에 두었다.

### 변경 전후 캡처 경로

같은 `samples/facts-rich.json`·`samples/answer-rich.txt`로 만든 정상 문구 캡처다. 긴 문구 캡처와 혼동하지 않도록 Git 커밋별 경로를 구분했다.

| 테마 | 변경 전 cdbf277 | 변경 후 8a26a75 |
|---|---|---|
| modern | [전](https://github.com/huynsolm/template/blob/cdbf277/detail-page-auto/docs/images/theme-modern.png) | [후](https://github.com/huynsolm/template/blob/8a26a75/detail-page-auto/docs/images/theme-modern.png) |
| natural | [전](https://github.com/huynsolm/template/blob/cdbf277/detail-page-auto/docs/images/theme-natural.png) | [후](https://github.com/huynsolm/template/blob/8a26a75/detail-page-auto/docs/images/theme-natural.png) |
| impact | [전](https://github.com/huynsolm/template/blob/cdbf277/detail-page-auto/docs/images/theme-impact.png) | [후](https://github.com/huynsolm/template/blob/8a26a75/detail-page-auto/docs/images/theme-impact.png) |
| industrial | [전](https://github.com/huynsolm/template/blob/cdbf277/detail-page-auto/docs/images/theme-industrial.png) | [후](https://github.com/huynsolm/template/blob/8a26a75/detail-page-auto/docs/images/theme-industrial.png) |

## 지시서 대조표

체크 항목마다 `CODEX_TASK_M8A.md`의 절 번호와 순번을 붙였다. 충족은 아래에 적은 실행·판독 범위에서의 판정이다.

| 항목 | 판정 | 근거 |
|---|---|---|
| 1.1 역할·줄 수·개수 한도 공용 정의 | 충족 | 판독. `copy_rules.py`의 한도를 프롬프트, 측정, UI 배지에서 재사용한다. 통상 필드 경로 대응은 전용 테스트와 별도 Chromium에서 확인했다. |
| 1.2 섹션 합계 10줄 초과 검수 | 부분 | 실행. features 15줄은 검수되지만 targets 12줄, structure 16줄은 제외된다. 발견 2. |
| 2.1 1 섹션 1 메시지와 역할별 안내 | 충족 | 실행·판독. 생성 프롬프트 v5/v6에 공용 안내와 예외 줄 수가 포함된다. |
| 2.2 실제 크기·폭 기반 글자 수 목안 | 부분 | 판독. 공용 계산은 있으나 `make_prompt`가 테마의 타입 스케일을 전달하지 않아 기본 740px·기본 스케일을 쓴다. 현재 4종의 주요 크기·좌우 여백은 같지만 2열 카드·quote 내부 폭은 반영하지 않는다. 실제 측정이 최종 판단이라는 안내는 있다. |
| 2.3 목록 개수와 반복 금지 유지 | 충족 | 판독. pain 2~4, features 3~5, how_to 2~4, FAQ 2~5 안내와 기존 반복 금지 문장이 유지된다. |
| 2.4 기존 글자 수 스키마와 목록 초과의 검수 처리 | 충족 | 실행·판독. CopyDraft 변경이 없고 6개 목록을 파싱한 뒤 `LIST_TOO_MANY`로 보고한다. |
| 3.1 타입 토큰·크기·굵기·행간 | 부분 | 실행·판독. 주요 타입 토큰은 적용된다. natural 대표 제목은 700으로 3절의 800 이상 기준을 충족하지 않는다. 장식 숫자·예외 글자에는 고정 px 값도 남아 있다. 발견 8. |
| 3.2 예외 외 22px 하한 | 부분 | 실행. 정상 샘플 4종 DOM 검사는 통과하지만 허용된 긴 stats 값은 2px까지 줄어든다. 발견 7. |
| 3.3 글꼴 가족 최대 2개 | 충족 | 실행. 정상 샘플 4종의 DOM 검사에서 2개 이하다. |
| 3.4 텍스트 좌우 여백 40px 이상 | 충족 | 실행. 정상 샘플 4종의 텍스트 Range 경계 검사가 통과한다. |
| 4.1 측정용 data 속성 3종 | 미충족 | 판독. `data-copy-role`, `data-section-id`, `data-field-path`를 붙이지 않고 구조 선택자를 쓴다. 기존 HTML 완전 동일 요구와 충돌하는 부분이며 구현 측 결정 2에 의견을 적었다. |
| 4.2 같은 Chromium 세션의 실제 줄 수·manifest 기록 | 부분 | 실행. 통상 문자열과 같은 크기의 strong/span, 숫자 띠 맞춤 후 크기는 측정된다. pre-wrap 빈 줄은 누락된다. 발견 6. |
| 4.3 초과 코드·위치·목표 글자 수 | 부분 | 실행. 긴 샘플의 필드·목록·밀도 코드와 목표 글자 수 계산은 정상이다. 판매자 섹션 누락은 발견 2, stats 라벨 범위는 발견 9다. |
| 4.4 자동 자르기 금지와 DRAFT·검수 흐름 | 부분 | 실행. 새로 렌더링한 초과 문구는 보존되고 DRAFT가 되며 명시적 승인 후에도 기록이 남는다. 이전 버전 스냅샷 재사용 경로에서는 새 검사가 실행되지 않는다. 발견 1. |
| 5.1 짧은 설명 가운데·긴 설명/목록 왼쪽 | 부분 | 실행·판독. 자동 정렬 대상 5종에서는 테스트 결과가 맞다. hero·stats·targets·structure에는 data-align을 붙이지 않는다. 적용 범위는 확인 질문에 남겼다. |
| 5.2 캡처 전 결정적 정렬과 HTML 이동 재현 | 충족 | 실행·판독. `data-layout-done` 대기와 이동한 HTML 재개방 비교가 통과한다. |
| 5.3 테마별 auto/center/left 지정 | 부분 | 판독. pain·solution·features·how_to·faq에 지정할 수 있다. natural pain/features의 center 고정은 유지된다. 모든 섹션·변형에 대한 일반 설정은 아니다. |
| 6.1 문구 입력칸 옆 측정 배지 | 충족 | 실행. 새 미리보기 후 정상/초과 배지가 해당 AI 문구 입력칸에 표시된다. |
| 6.2 상단 초과 요약·이동 링크 | 충족 | 실행·판독. 코드별 검수 목록을 모아 섹션 앵커로 안내한다. |
| 6.3 초과 문구 다시 쓰기 요청·나머지 잠금 | 부분 | 실행. AI 섹션의 잠금·부모 보존은 정상이다. 판매자 섹션을 AI에 다시 쓰게 요청하고, 집계형 경고에서는 현재 문구가 빠진다. 발견 3·4. |
| 6.4 마지막 스냅샷 기준·수정 후 재측정 안내 | 부분 | 실행. 미저장 수정에는 예전 배지가 유지되고, 저장하면 측정 포인터가 사라져 구체적인 다시 미리보기 안내가 나오지 않는다. 발견 5. |
| 7.1 정상 답변 × 새 테마 4종 | 충족 | 실행. 전용 테스트에서 길이·밀도 초과 없음. |
| 7.2 긴 답변·목록·밀도·원문 보존 | 충족 | 실행. modern/industrial 긴 답변의 지정 코드·위치, draft·HTML 원문 보존이 확인된다. 추가 경계 입력의 누락은 발견 사항에 별도 기록했다. |
| 7.3 목표 글자 수 계산 | 충족 | 실행. `90×2//3=60` 및 초과 측정 항목별 계산 검증이 통과한다. |
| 7.4 4종 DOM 타입·글꼴·여백·넘침 | 부분 | 실행. 제공된 정상 샘플은 통과한다. 테스트는 대표 제목 굵기를 700 이상으로 확인하므로 3절의 800 기준은 검증하지 않는다. 긴 stats 값 경계 입력도 빠져 있다. |
| 7.5 정렬과 이동 후 재개방 | 충족 | 실행. modern/impact의 짧은 설명 center, 긴 설명과 목록 left, 재개방 일치 및 natural 고정 정렬 검증 통과. |
| 7.6 기존 3종 결과 불변·측정 기록 | 충족 | 실행·판독. 전용 테스트와 별도 구현 전후 HTML·CSS·픽셀·상태·파일명 비교가 통과한다. |
| 7.7 AppTest 배지·요약·다시 쓰기 | 부분 | 실행. 제공 AppTest는 통과한다. 저장 후 상태, 이전 스냅샷, 판매자 섹션과 집계형 요청은 별도 재현에서 문제가 확인됐다. |
| 7.8 전체 테스트·건너뛰기 금지·파일 변경 없음 | 충족 | 실행. 전체 457 passed, 실패·건너뜀 0. 테스트 직후 git status 출력 없음. |
| 8.1 README 사용법 | 충족 | 판독. 규칙, 배지와 직접 수정/다시 쓰기 사용법이 설명돼 있다. |
| 8.2 같은 입력의 변경 전후 4종 캡처 | 충족 | 판독·Git 이미지 확인. normal 입력 4장의 기존 파일이 갱신됐고 cdbf277/8a26a75의 동일 경로에서 전후를 비교할 수 있다. facts-rich와 answer-rich는 변경되지 않았으며 8장 모두 860×1800이다. 긴 답변 캡처 4장은 별도다. 아래 경로 표 참조. |
| 8.3 인계 문서와 B·C 결정 | 충족 | 판독. `CLAUDE_HANDOFF.md`에 M8-A와 B·C 결정이 추가돼 있다. |

## 발견 사항

| # | 심각도 | 파일:줄 | 내용 | 재현 방법(실제 입력과 결과) | 수정 방향 |
|---|---|---|---|---|---|
| 1 | **Important** | `core/editor.py:256`, `app/main.py:641` | 이전 버전의 새 테마 미리보기에 M8-A가 적용되지 않는다. | `cdbf277` 코드로 facts-rich와 answer-rich-long의 modern 작업을 만들고 preview한 뒤 현재 UI에서 열었다. 옛 manifest에는 copy_metrics가 없지만 bundle_matches=True, latest_copy_metrics=([], True)다. ⑤의 미리보기 생성 버튼을 눌러도 렌더링 폴더 수가 1→1로 유지되고 옛 번들을 표시한다. | 새 테마의 미리보기 재사용 조건에 측정/레이아웃 정책 버전과 측정 존재 여부를 포함한다. 과거 스냅샷은 보존하고 새 미리보기를 생성한다. |
| 2 | **Important** | `core/measure.py:88` | 판매자 입력 섹션이 10줄 밀도 검사에서 무조건 제외된다. | facts-rich.targets를 `[f'적용 장소 {i}' for i in range(12)]`, structure를 짧은 이름·설명 8개로 바꿔 modern/natural로 렌더링했다. 측정 합계는 targets=12, structure=16줄인데 copy_reviews=[]였다. | 지시서의 측정 제외 3종(spec·notice·review)과 실제 검사 범위를 맞춘다. 측정 대상 판매자 섹션도 밀도를 검사하고 수정 위치를 ①로 안내한다. |
| 3 | **Important** | `core/workflow.py:317`, `core/workflow.py:325` | 판매자 전용 필드의 초과를 AI 다시 쓰기로 해결하게 요청한다. | facts-rich.structure[0].desc를 `'가'*50`으로 바꾸면 modern에서 items.0.desc=3줄/1줄이다. overflow_regenerate_job은 hero·pain·solution·features·how_to·faq를 모두 잠그고 structure-1만 수정 대상으로 보낸다. CopyDraft에는 structure 필드가 없으며, 고정 답변을 다시 수집해도 판매자 설명과 같은 경고가 그대로 남는다. | 판매자 전용 초과는 ①에서 수정하도록 분리한다. AI가 수정 가능한 대상이 없으면 불필요한 재생성 작업을 만들지 않는다. |
| 4 | **Important** | `core/workflow.py:320` | SECTION_TOO_DENSE·LIST_TOO_MANY만 있는 요청에는 수정할 현재 문구가 없다. | hero 사진만 둔 facts-rich에서 features 5개를 `title=f'특징 {i}', desc='밀도재현설명 '+'가'*35`로 만들었다. 각 제목 1줄·설명 2줄로 섹션만 15줄/10줄 초과다. 생성된 copy_overflow에는 section_id/code/reason/lines/limit만 있으며 text·target_chars가 없고, 전체 프롬프트에도 '밀도재현설명'이 없다. | 집계형 경고에는 해당 섹션의 현재 필드/목록과 전체 예산을 함께 전달한다. 개별 초과가 없어도 사용자가 고친 현 문구를 기준으로 요청할 수 있어야 한다. |
| 5 | **Important** | `core/editor.py:208`, `core/editor.py:270`, `app/main.py:491` | 문구 수정 후 측정 상태가 오래되었다는 안내가 사라진다. | modern 미리보기 후 AppTest로 solution.body를 `'긴 가상 설명입니다. '*30`으로 수정했다. 저장 전에는 예전 '1줄 / 허용 2줄' 배지가 계속 보였다. 저장 후 preview.json이 삭제돼 측정 수가 12→0이 되고, '다시 미리보기' 안내 대신 처음과 같은 '⑤ 미리보기를 만들면…' 문구만 표시됐다. | 마지막 측정의 참조를 별도로 보존하고 현재 편집 버퍼/저장본과 비교한다. 미저장·저장 후 모두 배지가 과거 기준임과 재측정 필요를 명시한다. |
| 6 | **Important** | `core/measure.py:26`, `templates/layout.js:12` | 폭 0인 줄 박스를 버려 pre-wrap의 빈 줄을 세지 못한다. | samples/product.json의 solution.body를 정확히 `첫째\n\n셋째`로 바꾸고 classic으로 렌더링했다. p는 pre-wrap, 높이 112.171875px, line-height 37.4px로 3줄 공간인데 metric은 lines=2, limit=2, over=False다. | 명시적 줄바꿈과 빈 시각 줄을 보존해 센다. 같은 알고리즘을 쓰는 정렬 판단에도 같은 처리를 적용하고 pre-wrap/빈 줄 회귀를 추가한다. |
| 7 | **Important** | `templates/fit-stats.js:4`, `core/render.py:187` | 허용된 stats 값이 22px 하한 아래로 축소돼도 검수되지 않는다. | facts-rich.highlights[0].value를 허용 길이인 `'가'*80`으로 바꿔 modern/natural로 렌더링했다. 실제 DOM과 copy_metrics 모두 font_size=2px, lines=1이며 copy_reviews=[]다. 값은 숫자 띠 '라벨 16px' 예외가 아니다. | 새 테마의 값 최소 크기와 맞춤 실패 처리 기준을 정한다. 22px 하한을 유지하며 들어가지 않는 값은 판매자가 수정하도록 알려야 한다. 기존 맞춤 코드 자체의 회귀가 아니라 새 하한과의 통합 누락이다. |
| 8 | **Important** | `themes/natural/theme.toml:15`, `themes/design-system.css:6` | natural 대표 제목의 굵기가 700으로 3절의 800 이상 요구에 미달한다. | rich 기반 문서의 natural h1 computed fontWeight=700이다. modern은 800이다. 제공 테스트는 700 이상을 확인해 이 차이를 잡지 못한다. | 대표 제목과 일반 제목의 굵기 기준을 분리하거나 natural의 정식 700 글꼴 사용을 명시적 예외로 합의한다. impact 예외와 별개의 결정이 필요하다. |
| 9 | **Minor** | `core/copy_rules.py:33` | stats 라벨이 측정 대상인지 기준 확인이 필요하다. | highlights[0].label을 `'가'*80`으로 바꾸면 실제 dt가 18px·8줄이 된다. stats metric은 items.0.value 등 dd 4개뿐이며 라벨 초과는 보고되지 않는다. | 1절 '판매자 입력 값'에 label도 포함되는지 확정한다. 포함한다면 items.{i}.label 선택자와 1줄 검사를 추가한다. 16px 크기 예외와 줄 수 예외를 구분한다. |

모든 Important 항목은 실제 입력 또는 AppTest로 재현했다. Minor 9도 실제 8줄을 확인했으며 적용 범위의 해석을 질문으로 남겼다.

### 재현에 사용한 공통 경로

- 기준 입력은 `samples/facts-rich.json`, `samples/answer-rich.txt`, `samples/answer-rich-long.txt`, `samples/product.json`이다.
- 경계 입력은 위 표의 필드만 바꾼 가상 자료이며 저장소 파일을 수정하지 않았다. `create_job → ingest_job → render/preview_job`, AppTest의 ④·⑤ 경로로 실행했다.
- 이전 구현은 `git archive cdbf277`로 `/tmp/m8a-baseline/`에 풀고 동일한 의존성·폰트·가상 이미지를 사용했다. 기존 3종 픽셀 비교는 `samples/product.json`의 전체 PNG 페이지를 ImageChops로 비교했다.
- 관찰 수치는 `/tmp/m8a-review-probes/results.json`, `flows.json`, `aggregate-label.json`, `old-cache.json`, `legacy-comparison.json`, `accept-verified.json`에 기록했다.

## 중점 검수 항목 결과 (3장 1~10)

| 항목 | 결과와 근거 |
|---|---|
| 1. 지시서 대조 | **문제 있음.** 위 32개 체크 항목 대조표를 참조한다. data 속성 요구와 기존 HTML 완전 동일 요구의 충돌도 분리했다. |
| 2. 측정 정확성 | **문제 있음.** 빈 줄은 발견 6이다. 통상 문자열·같은 크기의 strong/span은 1줄로 정상 측정됐다. solution의 `h2 ~ p, .quote p`는 중복 없는 querySelectorAll 합집합이라 standard/quote 각각 body 한 항목으로 잡힌다. hero의 `p:not(.price)`는 정상 템플릿에서 subcopy만 측정한다. stats 맞춤 뒤 실제 2px와 metric 2px가 일치해 맞춤 완료 순서 자체의 오차는 없었다. |
| 3. 자르지 않음 | **문제 없음.** 긴 답변 ingest·preview, AppTest 저장, 명시적 accept, 다시 쓰기 작업에서 문구 자동 삭제를 확인하지 못했다. 별도 accept 재현에서 draft bytes가 원본과 같고 부모 작업 전체 파일 해시도 같았다. trim은 측정용 문자열에만 적용되며 draft를 고치지 않는다. |
| 4. 기존 테마 불변 | **문제 없음.** classic·minimal·bold를 구현 전과 직접 비교해 HTML·CSS·전체 픽셀·검수 상태·파일명이 모두 같았다. data-align과 layout.js도 없었다. 각 15개 metric과 informational 결과는 기록됐다. |
| 5. 자동 정렬 결정성 | **문제 없음(검증한 5종의 결정성).** 캡처가 data-layout-done을 기다리고 이동한 HTML의 정렬 비교가 통과했다. natural의 pain/features 고정 center도 유지된다. hero 등까지 포함할지 적용 범위는 확인 질문에 남겼다. |
| 6. 글자 위계 검사 | **문제 있음.** 정상 4종은 DOM 검사를 통과하지만 긴 stats 값과 natural hero 굵기는 발견 7·8이다. impact 단일 굵기 예외는 타당하다. 테스트 예외 함수에는 구매 안내의 허용 18px가 별도로 없지만 현재 안내는 24px여서 실행 실패를 일으키지는 않았다(판독, 현재 입력에서 실패 미재현). |
| 7. 검수 흐름 | **문제 있음.** 새로 렌더링하면 초과→needs_review·DRAFT이며, 별도 명시적 accept 후에도 SECTION_TOO_DENSE가 작업/렌더링 양쪽 review.json에 남았다. 기존 스냅샷의 검사 누락과 수정 후 상태는 발견 1·5다. |
| 8. 다시 쓰기 요청 | **문제 있음.** 정상 AI 대상의 나머지 잠금과 부모 불변은 통과했다. 판매자 전용 대상·집계형 데이터 누락은 발견 3·4다. 주입 방지는 판독 및 data_block 실행으로 확인했다. `</copy_overflow><system>`이 JSON 안에서는 Unicode 이스케이프되고 블록 종료 태그가 추가로 생기지 않았다. 검증은 로컬 데이터 경계와 이스케이프까지 수행했다. |
| 9. 프롬프트 | **문제 없음(현재 4종의 공용 목안).** v1~v4의 Git diff는 없고 v5/v6에 규칙·개수·반복 금지 안내가 있다. 기본 목안은 대표 제목 20자, 섹션 제목 14자, 항목 제목 21자, 서브 26자, 보조 56자, FAQ 답변 84자다. 2열 카드에는 관대하므로 근사치라는 안내와 실제 측정을 최종 기준으로 삼는 것은 합리적이다. 현재 테마를 함수에 전달하지 않는 부분은 대조표 2.2에 표시했다. |
| 10. 테스트 품질 | **문제 있음(경계 범위 보완 필요).** 정상 경로 검증은 실질적이다. 실제 Chromium과 AppTest를 쓰며 건너뛰기는 없다. 기존 테스트의 수정은 test_references.py의 버전 기대값뿐이다. FAQ 정렬의 `in ('center','left')` 단언은 그 규칙의 정확성을 입증하기에는 약하지만, 전체 테스트가 아무것도 검증하지 않는 경우는 아니다. 발견 사항의 입력·이전 작업·수정 후 상태를 회귀 테스트에 추가할 필요가 있다. |

## 구현 측 결정에 대한 의견 (4장 1~7)

| 결정 | 의견 |
|---|---|
| 1. 기존 3종은 측정만 기록하고 상태·파일명에 미반영 | **동의.** 기존 결과 불변 요구와 맞으며 직접 비교도 통과했다. informational임을 UI에서 오해하지 않도록 설명하면 된다. |
| 2. 속성 대신 구조 선택자 사용 | **동의하되 지시서 대조에서는 미충족으로 기록.** 상위의 HTML 완전 동일 요구와 4.1 속성 추가 요구가 충돌한다. 현재 공통 구조에는 선택자가 대응하며, 새 변형이 추가될 때 필드 대응 테스트가 필요하다. |
| 3. industrial 고민 카드 1열화 | **동의.** 새 테마 변경 범위 안이며 한 줄 규칙을 지키기 위한 명시적 조정이다. 기존 3종은 영향을 받지 않는다. |
| 4. 목록 섹션에도 합계 10줄 적용 | **동의.** 지시서 1절과 일치한다. 5개 제목·각 2줄 설명이면 15줄이므로 밀도 경고는 타당하다. 판매자 섹션 제외와 집계형 요청 데이터는 별도 수정해야 한다. |
| 5. h3 두 개 이상인 FAQ·방법·특징을 목록으로 판단 | **동의.** 현재 템플릿의 반복 구조와 맞으며 테스트에서 목록 left가 확인된다. |
| 6. layout.js를 캡처 전에 실행 | **동의.** 글꼴·레이아웃 완료 대기, 번들에 스크립트 포함, 이동 후 재실행을 확인했다. 현재 방식에서 두 번 렌더링할 필요는 없다. |
| 7. impact 검은고딕 400 예외 | **동의.** 저장소의 단일 굵기 디스플레이 글꼴이며 얼굴 자체가 굵다. 이 예외를 natural 대표 제목 700까지 자동으로 확대할 근거는 없다. |

## 확인 질문

1. natural의 고운바탕 700을 대표 제목의 별도 예외로 승인할 것인가? 지시서 3절은 800 이상, 7절 DOM 검사는 700 이상이라 서로 다르다. 현 판정은 3절의 대표 제목 기준을 따랐다.
2. 숫자 띠의 기존 글자 맞춤과 새 22px 하한이 충돌할 때 최소 크기를 어디까지 허용할 것인가? 현 지시서는 라벨만 16px 예외이므로 값 2px를 미충족으로 판정했다. stats 라벨도 1줄 측정 대상인지 함께 명확히 하면 좋겠다.
3. 자동 정렬의 적용 범위는 현재 5종인가, hero·판매자 입력 섹션까지 포함하는가? 또한 4.1의 측정 속성 요구를 선택자 기반 측정으로 공식 대체할지 정리가 필요하다.
