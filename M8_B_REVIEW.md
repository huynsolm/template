# M8-B 검수 보고서

## 요약

- 판정: **재작업 필요**. Critical 2건, Important 4건, Minor 1건. 기본 승인 화면과 `accept_job`의 확인 강제는 동작하지만, 다른 렌더링 경로의 출처 누락과 확인 없는 일반 파일명 출력이 재현됐다.
- 검수 대상: `huynsolm/template`, `ccr-f9c07036-vgvm5j`, `1e156f6..b67ce7e`. 기준은 `CODEX_TASK_M8B.md`와 `CODEX_REVIEW_M8B.md`이다.
- 검수일: 2026-11-24(KST). 코드·테스트·기존 문서는 수정하지 않았다. 이 보고서만 저장소에 추가한다.

### 직접 실행한 결과

환경: Linux, Python 3.12.14, 저장소 `.venv`, Chromium 156.0.8078.79. 실제 AI·외부 이미지 서비스·배경 제거 모델은 호출하지 않았다. 추가 재현 이미지는 `tests/test_m8b.py`의 Pillow 가상 이미지와 저장소의 가상 샘플뿐이다. 렌더링 작업은 모두 순차 실행했다.

| 실행 | 결과 |
| --- | --- |
| `git fetch origin`, 대상 브랜치 최신 상태 확인 | `b67ce7e` 확인, 시작 시 작업 트리 깨끗함 |
| `.venv/bin/python -m pytest -q tests/test_m8b.py` | 23 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest -q` | 493 passed, 0 failed, 0 skipped (1006.65초, 종료 0) |
| `.venv/bin/python tools/make_screenshots.py --m8b-only --images /tmp/m8b-shots --output /tmp/m8b-out` | 종료 0. `/tmp/m8b-shots/m8b-approval.png`, `m8b-staged.png` 생성·직접 열람; 원본/결과 나란히 보기와 연출 안내 확인 |
| 테스트·캡처 후 `git status --porcelain=v1` | 출력 없음(보고서 추가 전) |
| `1e156f6`과 `b67ce7e`에서 같은 사진 전용 facts/답변으로 7개 테마 렌더링 | draft·HTML·CSS 바이트 동일, 파일명·검수 플래그 동일, PNG 20장 모두 크기·RGB 픽셀 동일 |
| AI 이미지의 본문·갤러리 안내를 7개 테마에서 Chromium DOM 측정 | 각각 22px, 왼쪽 56~64px, 오른쪽 최대 804px, 860px 페이지 가로 넘침 없음 |
| 승인·출처·경로 별칭·도구 이름·대표 이미지·작업 재개 추가 재현 | 아래 C-1~M-1 참조 |

추가 재현 스크립트·로그는 `/tmp/m8b-review/`에만 만들었다. 보고서의 재현 방법은 저장소 테스트 도우미로 다시 실행할 수 있으며, 이 임시 경로가 있어야만 재현되는 방식은 아니다.

## 지시서 대조표

| 항목 | 판정 | 근거 |
| --- | --- | --- |
| 1. 출처 모델·검증·기존 데이터 호환 | 부분 | 필수 값·직접 자기 참조·AI 원본 참조·명시적 역할 제한은 검사한다. `None → photo` 호환은 확인했다. 경로 별칭, 도구 이름 검증 우회, 조립 시 대표 이미지 승격은 I-1~I-3. |
| 2. 복사·붙여넣기 프롬프트 | 충족 | 배경 4종, 상품 보존·상품 미묘사 지시, 직접 첨부 안내, 데이터 블록 이스케이프와 가격·후기·claim 제외를 테스트·정적 판독으로 확인했다. |
| 3. 업로드·처리·기록·보조 지표 | 부분 | 원본 해시 불변, `based_on`의 작업 내부 경로 변환, 정규화·출처 기록은 기본 경로에서 확인했다. 비율·해상도는 제공하지만 모델 설치 시의 전경 면적 비교는 구현되지 않았다. |
| 4. 이미지별 검수·승인·무효화 | 부분 | UI·`accept_job`·CLI accept의 개별 확인 강제와 ingest 일괄 승인 거부는 확인했다. M1 일반 출력 경로는 C-2, 재미리보기 정책 설명 불일치는 M-1. |
| 5. 렌더링·내보내기 | 부분 | 일반적인 사용 장면·갤러리의 안내와 7개 테마 사진 전용 결과 불변은 직접 확인했다. ingest 렌더·ZIP 출처 누락 C-1, 대표 이미지 안내 누락 I-1. |
| 6. 화면 | 부분 | ① 출처 저장·프롬프트 및 ⑥ 나란히 보기·개별 체크는 AppTest로 확인했다. ④ 기존 경고는 있으나 ⑤ 출처 배지·AI 미확인 안내는 없다(I-4). |
| 7. 테스트 | 부분 | 집중·전체 테스트 결과는 위 표. 실제 Chromium·AppTest를 사용한다. 다만 이번 우회와 전체 7개 테마의 이전 결과 대조를 저장소의 M8-B 테스트가 모두 고정하지는 않는다. |
| 8. 문서·가상 샘플 | 부분 | README·인계서·검수 요청서 및 Pillow 캡처가 있다. 승인 작업 재미리보기의 설명은 실제 동작과 다르다(M-1). |

## 발견 사항

위치는 모두 `detail-page-auto/` 기준이며, 줄 번호는 `b67ce7e` 기준이다. 아래 모든 발견 사항은 **직접 실행으로 재현**했고, 원인은 코드 판독으로 대조했다. 단순 추정만으로 등록한 결함은 없다.

| # | 심각도 | 파일:줄 | 내용 | 재현 방법·실제/기대 결과 | 수정 방향 |
| --- | --- | --- | --- | --- | --- |
| C-1 | Critical | `core/workflow.py:150`, `core/export.py:349` | `ingest --render`의 렌더링 manifest와 해당 결과의 ZIP에서 이미지 출처가 사라진다. | 아래 재현 A. 작업에 AI 이미지 2개가 기록되어도 렌더·ZIP의 `image_sources`가 없다. 기대: DRAFT를 포함한 모든 결과에서 출처 유지. | preview/accept뿐 아니라 ingest 렌더에도 동일 출처 메타데이터를 연결하고, export에서 누락 상태를 그대로 유통하지 않도록 검사. |
| C-2 | Critical | `cli.py:18`, `cli.py:29`, `core/render.py:119`, `core/render.py:192` | 공개 M1 명령은 AI 이미지가 든 실제 작업 초안을 확인 없이 일반 파일명으로 출력한다. | 아래 재현 B. 종료 0, `needs_review=false`, `page-001.jpg` 등 일반 이름. `review_accepted=false`이므로 승인 기록을 만든다는 뜻은 아니며, **확인 없는 일반 출력** 문제다. 기대: AI 이미지임이 확인되는 작업은 이미지별 확인 전 DRAFT/차단. | M1에도 AI 초안의 출처·검수 상태를 전달하거나, 해당 입력은 검수 가능한 작업 경로로 안내. 사진 전용 M1 호환은 유지. |
| I-1 | Important | `core/assemble.py:65` | 생성 이미지를 lifestyle로만 등록해도 hero가 없으면 첫 사진 대체 규칙으로 대표 상품 사진에 재사용된다. hero에는 연출 안내도 없다. | 아래 재현 C. 생성 lifestyle 1장만으로 생성 성공, hero와 image가 같은 파일, 안내는 image 쪽 1개뿐. 기대: 생성 이미지는 분위기 영역에서만 사용하며 hero 대체에서 제외/입력 오류. | 대표 이미지 선택에서도 출처 제약 적용. 생성 이미지가 첫 번째이고 뒤에 실제 사진이 있는 경우도 검사. |
| I-2 | Important | `core/facts.py:129`, `core/workflow.py:76` | 같은 물리 파일의 `name`/`./name` 별칭으로 실제 사진·AI 이미지 동시 사용 및 자기 참조 금지를 우회한다. | 아래 재현 D. 실제 사진 `rich-hero.png`, edited `./rich-hero.png`, based_on `rich-hero.png`가 성공하며 두 작업 파일로 복사된다. 기대: 같은 파일이므로 거부. | 입력 이미지 루트를 기준으로 검증한 실제 경로의 동일성을 확인한 뒤 출처 관계 검증·복사. 원래 문자열 비교만으로 판정하지 않기. |
| I-3 | Important | `core/facts.py:30`, `core/facts.py:61`, `core/image_checks.py:42` | 생성 도구 이름의 URL·토큰 거부가 일부 구분자 검사에 그친다. 주소와 인식 가능한 토큰 형태가 facts·manifest에 저장된다. | 아래 재현 E. 예약 도메인 `tools.example.com`과 합성 토큰 형태가 모두 저장된다. 기대: 도구 이름만 허용하며 주소·토큰은 저장 전 거부. | 스킴 없는 주소와 알려진 인증 정보 형태를 저장 전에 검사. 필드 길이 제한만으로 토큰 금지를 대신하지 않기. |
| I-4 | Important | `app/main.py:625` | ⑤ 미리보기에는 이미지별 AI 출처 표시나 AI 이미지 확인 필요 안내가 없다. | 아래 재현 F. AI 2개가 미확인인 작업의 ⑤에서 일반 DRAFT 안내와 근거·수치·광고 검수 안내만 나온다. 기대: AI 배경 변경/AI 생성과 미확인 상태를 확인 가능. | `image_sources`와 이미지 검수 상태로 ⑤에 출처·미확인 안내 표시. ④ 경고 대체만으로 ⑤ 요구가 충족되지는 않는다. |
| M-1 | Minor | `core/editor.py:241`, `core/editor.py:267`; `CODEX_REVIEW_M8B.md` 4장 4번 | “승인 작업을 다시 미리보기하면 다시 확인이 필요하다”는 설명과 실제 작업 재개가 다르다. | 아래 재현 G. 같은 테마로 재미리보기하면 새 결과는 DRAFT지만 작업의 `review_accepted=true`와 이전 승인 결과 선택은 유지된다. 기대: 문서와 동작이 같은 정책. | 변경 없는 재미리보기에서 기존 승인을 유지하는 정책이라면 설명 정정. 무조건 재확인 정책이라면 명시적으로 승인 무효화. 이미지·문구 변경 없이 재현했으므로 이것 자체를 승인 우회로 세지 않음. |

### 재현 공통 준비

저장소의 `detail-page-auto`에서 `.venv/bin/python`으로 실행한다. 아래 도우미는 커밋된 가상 샘플과 Pillow 이미지만 사용한다.

```python
import sys, json, io, zipfile, subprocess, tempfile
from pathlib import Path
sys.path.insert(0, str(Path('tests').resolve()))
from test_m8b import virtual_images, facts_with, BASE, AI_EDITED, AI_SCENE, ANSWER
from core.workflow import create_job, ingest_job, accept_job, read_json
from core.editor import preview_job, resume_bundle
from core.export import export_bundle, build_export_zip

root = Path(tempfile.mkdtemp(prefix='m8b-review-', dir='/tmp'))
photos = virtual_images(root / 'photos')
job = create_job(facts_with(BASE + [AI_SCENE, AI_EDITED]), photos,
                 root / 'jobs', theme='modern')
ingest_job(job, ANSWER, render_output=True)
bundle = next((job / 'rendered').iterdir())
```

#### A — ingest 렌더·ZIP 출처 누락

```python
rendered = read_json(bundle / 'manifest.json')
exported = export_bundle(bundle, 'generic', output_dir=root / 'exports')
_, data = build_export_zip(Path(exported['folder']))
with zipfile.ZipFile(io.BytesIO(data)) as z:
    zipped = json.loads(z.read('manifest.json'))
    print('facts.json' in z.namelist())
print('image_sources' in rendered, 'image_sources' in zipped)
```

실제: `False`, `False False`. 작업 facts와 `image_processing`에는 생성/배경 변경 출처가 있고 `review.json`에는 `AI_IMAGE_UNCONFIRMED` 2개가 있지만, 배포 결과의 출처 목록은 없다. DRAFT라는 이유로 출처를 비워도 된다는 예외는 없다. 미승인 단계의 확인 결과가 비어 있는 것은 문제로 세지 않았다.

비교 대조: 같은 작업에 `preview_job(job)`를 사용하면 `image_sources`가 있다. 모든 체크를 지정해 `accept_job`한 결과는 작업·승인 렌더·ZIP의 `image_sources`와 `image_checks`가 일치한다. 즉 출처가 전혀 구현되지 않은 것이 아니라 렌더 경로별 연결 차이다.

#### B — M1 일반 파일명 출력

```python
result = subprocess.run([
    sys.executable, 'cli.py', '--input', str(job / 'draft.json'),
    '--images', str(job), '--output', str(root / 'm1'),
    '--png', '--theme', 'modern',
], capture_output=True, text=True)
print(result.returncode)
m1 = Path(result.stdout.strip().splitlines()[-1])
m = read_json(m1 / 'manifest.json')
print(m['needs_review'], m['review_accepted'], [p['file'] for p in m['pages']])
```

실제: 종료 `0`, `False False`, `['page-001.jpg', 'page-002.jpg', 'page-003.jpg']`. 이미지 확인 인수는 전혀 주지 않았다. 입력은 A에서 정상 생성된 초안이며 `staged=true`인 이미지도 포함한다. HTML에는 연출 문구가 1개 나오지만 출처 목록은 없고 DRAFT 파일명이 아니다. 기대는 해당 AI 이미지의 확인 전 일반 출력 금지다. 반면 `accept_job(job)`만 실행하면 “사진 6, 사진 7”의 확인 누락을 올바르게 거부한다.

#### C — 생성 lifestyle의 hero 승격

```python
only = create_job(facts_with([AI_SCENE]), photos, root / 'only', theme='modern')
ingest_job(only, ANSWER)
d = read_json(only / 'draft.json')
hero = next(s for s in d['sections'] if s['type'] == 'hero')
scene = next(s for s in d['sections'] if s['type'] == 'image')
print(hero['image'] == scene['image'], hero.get('staged'), scene.get('staged'))
p = preview_job(only)
print((p / 'page.html').read_text().count('연출 이미지입니다'))
```

실제: `True None True`, 안내 개수 `1`. 같은 생성 이미지가 대표 사진과 사용 장면 두 곳에 나오지만 대표 쪽에는 안내가 없다. 기대: 사용 장면에만 쓰고, 허용된 대표 사진이 없으면 입력을 보완하도록 안내한다.

#### D — 경로 별칭

```python
alias = dict(AI_EDITED, path='./rich-hero.png', based_on='rich-hero.png')
print((photos / alias['path']).resolve() == (photos / alias['based_on']).resolve())
a = create_job(facts_with(BASE + [alias]), photos, root / 'alias')
f = read_json(a / 'facts.json')
print(f['images'][0]['path'], f['images'][-1]['path'], f['images'][-1]['based_on'])
```

실제: `True`, `images/image-000.png images/image-005.png images/image-000.png`. 오류 없이 작업이 생성된다. 같은 입력 파일을 두 번 복사한 뒤에는 원래 같았다는 관계가 사라진다. 기대는 복사 전에 거부다.

#### E — 도구 이름

```python
for name in ('tools.example.com', 'AIza' + 'A' * 35):
    f = facts_with(BASE + [dict(AI_EDITED, generator=name)])
    a = create_job(f, photos, root / 'generator')
    print(read_json(a / 'facts.json')['images'][-1]['generator'] == name,
          read_json(a / 'manifest.json')['image_processing'][-1]['generator'] == name)
```

실제: 두 입력 모두 `True True`. 두 번째는 **실제 키가 아닌 합성 문자열**(39자)이다. 외부 요청을 하지 않았다. 기대: 모두 저장 전 오류. `https://...`와 `me@...` 거부 테스트가 이 두 경우를 덮지는 않는다.

#### F — ⑤ 미리보기 표시

A의 작업을 `preview_job(job)`한 뒤 AppTest에서 `DETAIL_PAGE_OUTPUTS=job.parent`로 저장 작업을 재개하고 ⑤ 미리보기로 이동했다(`test_app.stage(app, 4)`). 예외는 없었다. 경고는 “DRAFT · 승인 전 미리보기입니다. 검수 항목과 문구를 확인하세요.”였고, 표시된 warning/error/info/caption/markdown 전체에 `AI 배경 변경`, `AI 생성`, `AI_IMAGE_UNCONFIRMED`가 없었다. `display_bundle` 코드도 이미지 출처 목록을 읽지 않는다. 기대는 ⑤에서 AI 출처와 미확인 상태가 보이는 것이다.

#### G — 승인 작업 재미리보기·재개

```python
accepted = accept_job(job, image_confirmations={
    'image-5': ['no_product'],
    'image-6': ['shape', 'color', 'composition'],
})
old = resume_bundle(accepted)
new = preview_job(accepted)
print(read_json(accepted / 'manifest.json')['review_accepted'])
print(resume_bundle(accepted) == old)
print(read_json(new / 'manifest.json')['review_accepted'])
```

실제: `True`, `True`, `False`. 작업의 새 `review.json`에는 미확인 항목이 다시 2개 생기지만 작업 재개는 기존 승인 결과를 고른다. 이 재현에서는 이미지·문구·테마를 바꾸지 않았다. 기대는 확정한 재미리보기 정책과 설명의 일치다.

## 중점 검수 항목 결과 (요청서 3장 1~10)

1. **지시서 대조 — 문제 있음.** 위 1~8절 대조표와 C-1~I-4 참조.
2. **승인 우회 — 문제 있음.** C-2가 실제 일반 출력 경로다. 기본 UI는 체크 누락 시 비활성이고 `accept_job`·CLI accept는 누락을 거부한다(직접 실행). `ingest --accept-review`는 AI 이미지가 하나라도 있으면 거부한다(집중 테스트). 일괄 작업은 개별 승인 상태를 요구하며 새 확인을 대체하는 일괄 체크는 없다(정적 판독). batch 템플릿에는 AI 출처 입력 칸 자체가 없으므로 이번 검수에서 “AI 일괄 입력 지원까지 검증”했다고 보지는 않는다. 재생성/저장 시의 승인 초기화는 공통 코드·기존 회귀 테스트로 확인했다. 원본 facts나 파일을 수동 변조한 경우까지 이번 검증 범위로 확장하지 않았다.
3. **출처 기록 — 문제 있음.** C-1. 기본 승인 경로는 7개 이미지의 출처·2개 AI 확인 결과가 승인 작업/렌더/ZIP에 동일하고 `based_on`도 작업 내부 경로다(직접 실행). 원본 SHA-256 불변은 집중 테스트에서 확인했다. 사진 전용 기존 기록을 변경하지 않는 설계 자체는 결함으로 세지 않았다.
4. **입력 검증 — 문제 있음.** 직접 지정한 `ai_generated + hero/diagram` 및 누락된 원본·도구·AI 원본 참조는 거부한다(집중 테스트). 조립 이후 역할 우회, 별칭, 도구 문자열은 I-1~I-3.
5. **프롬프트 안전 — 문제 없음(확인 범위 내).** 테스트와 코드 판독상 상품 보존·상품 미묘사·직접 첨부 안내가 있고, `data_block`을 사용한다. `feature/usage/spec`만 문맥에 넣고 후기·가격 필드·claim을 넣지 않는다. AI가 프롬프트를 실제로 준수하는지는 실행하지 않았으며 보장하지 않는다.
6. **기존 결과 불변 — 문제 없음(실행 표본 범위).** `samples/facts-rich.json`과 `answer-rich.txt`를 양 커밋의 동일 환경에서 렌더링했다. classic/minimal/bold/modern/natural/impact/industrial 모두 초안·HTML·CSS 바이트와 PNG 20장 RGB 픽셀 동일. `staged`/안내가 추가되지 않았다. 기존 classic 고정 비교 테스트도 유지된다. 모든 가능한 사용자 입력에 대한 동일성 증명이라는 뜻은 아니다.
7. **연출 안내 — 부분 문제 있음.** 일반 image/gallery 2개는 7테마 모두 DOM 수치 기준 통과, edited와 photo에는 안내가 없다(직접 실행). I-1의 hero 승격 시 안내 누락은 별도 결함이다.
8. **화면 — 부분 문제 있음.** ① AppTest는 출처 선택 분기를 실제 실행하고 작업 저장을 확인한다. 프롬프트는 `st.code`이며 입력을 `unsafe_allow_html`로 출력하지 않는다(코드 판독). ⑥ edited 원본/결과와 개별 3개 체크의 승인 제어는 AppTest로 확인했다. ⑤는 I-4.
9. **보조 지표 — 기본 방식 문제 없음, 범위는 부분.** 가상 이미지를 세로 절반으로 줄이면 종횡비 차이가 100%가 되어 경고한다(집중 테스트). 경고는 자동 불승인 판정이 아니며 수동 확인을 대체하지 않는다. 같은 비율로 상품만 바꾸면 탐지하지 못하고, 배경 크롭만 바꿔도 경고할 수 있다. 모델 설치 시 면적 비교는 미구현이며 실제 모델을 실행하지 않았다.
10. **테스트 품질 — 실질 검증은 있으나 누락 있음.** 실제 Chromium·AppTest, 무체크/부분 체크 거부, 승인 ZIP 기록 단언이 있다. 비활성화·무조건 참 단언으로 통과시킨 테스트는 발견하지 않았다. 다만 `test_photo_only_jobs_render_exactly_as_before`는 이름과 달리 이전 HTML·픽셀을 직접 비교하지 않고 `staged` 부재 등을 검사한다. 생성 이미지 DOM 테스트는 classic/modern만 매개변수화되어 있고, 나머지는 이번 외부 재현으로 보완했다. C-1~I-4를 회귀 테스트에 추가할 필요가 있다.

## 구현 측 결정에 대한 의견 (요청서 4장 1~6)

1. **동의.** 내부 `source=None`, 외부 의미 `origin='photo'`는 기존 JSON·프롬프트를 보존하는 합리적인 호환 선택이다. 사진 전용 7테마 실제 비교도 통과했다. 다만 사용자 입력/문서에는 생략이 실제 사진이라는 규칙을 일관되게 설명해야 한다.
2. **조건부 동의.** 모델을 새로 설치·실행하지 않고 비율·해상도를 보조로 쓰는 것은 현재 수동 검수 흐름에 맞는다. 그러나 지시서의 “모델이 있을 때 전경 면적 비교”는 충족하지 않았으므로 완료로 쓰면 안 된다. 이번 검수에서는 실제 배경 제거 모델을 호출하지 않았다. 해당 조건부 요구를 후속으로 남길지 사용자 확정이 필요하다.
3. **동의.** 안내를 템플릿 인라인 22px로 넣어 기존 CSS를 보존하는 방식은 타당하다. 7테마의 크기·여백·가로 넘침과 기존 결과 불변을 직접 확인했다. 단, I-1의 부적절한 배치까지 해결되는 것은 아니다.
4. **기록 분리는 동의, 재미리보기 설명은 정정 필요.** 승인 review에서 미확인 항목을 지우고 최초 검수 기록을 manifest에 남기는 것은 이력과 현재 상태를 구분한다. “다시 미리보기하면 다시 확인”은 실제와 다르므로 M-1에 따라 정책을 일치시켜야 한다. 변경이 없는데 이전 승인 유지 자체를 무조건 결함으로 보지는 않는다.
5. **현 상태에는 반대.** ④의 기존 사진 경고는 AI 미확인 안내의 일부 대안이지만, ⑤에 출처 정보가 없어 ④·⑤ 요구를 대신하지 못한다(I-4). 별도 배지 모양은 선택할 수 있어도 두 단계에서의 확인 가능성은 확보해야 한다.
6. **동의.** `--confirm-image image-N=checks`를 이미지별로 요구하는 방식은 한 번의 명령 실행을 모든 이미지 확인으로 간주하지 않는다. 실제 CLI의 누락 거부·완전 체크 성공을 확인했다. 다른 렌더 경로 C-2도 함께 정리해야 한다.

## 확인 질문

- 변경 없는 승인 작업을 다시 미리보기했을 때 기존 승인을 유지할지, 항상 재확인할지 정책 설명을 확정해 달라(M-1). 현재 지시서의 “이미지·문구 변경 시 무효화”에는 전자가 모순되지 않는다.
- 모델 설치 시 전경 면적 비교는 M8-B의 미완료 조건부 항목으로 남길지, 이번 범위에서 제외할지 확정해 달라. 현재 구현에는 없다.

위 정책 질문의 답변과 별개로 C-1·C-2 및 I-1~I-4는 수정 후 재검수가 필요하다. 실제 AI 이미지의 상품 일치 여부는 사람이 확인해야 하며, 가상 이미지 테스트 통과가 이를 자동 보장하지 않는다.
