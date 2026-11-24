# M8-B 재검수 보고서

## 요약

- 판정: **재작업 필요**. 새 발견 사항은 Critical 1건, Important 1건, Minor 1건이다. 이전 A~G의 직접 재현은 수정됐지만, 출처가 없는 독립 `staged` 초안의 내보내기와 유지된 이미지 확인의 미리보기 전달에 빈틈이 남았다.
- 대상: `huynsolm/template`, `ccr-f9c07036-vgvm5j`, `b4e55e4..5cf1467`. 검수일: 2026-11-24(KST).
- 코드·테스트·기존 문서는 수정하지 않았다. 이 보고서 한 파일만 커밋한다.

### 직접 실행한 결과

환경은 Linux, Python 3.12.14, 저장소 `.venv`, Chromium 156.0.8078.79이다. 실제 AI·외부 이미지 서비스·배경 제거 모델을 호출하지 않았다. 재현 이미지는 `tests/test_m8b.py`의 Pillow 가상 이미지와 저장소 가상 샘플이다. 렌더링 테스트·수동 재현·전체 테스트는 서로 겹치지 않게 순차 실행했다.

| 실행 | 결과 |
| --- | --- |
| `git fetch origin` 및 `git pull --ff-only` | `5cf1467`으로 갱신, 시작 시 작업 트리 깨끗함 |
| `.venv/bin/python -m pytest -q tests/test_m8b_review.py tests/test_m8b.py` | **47 passed, 0 failed, 0 skipped**, 78.20초, 종료 0 |
| 이전 보고서 재현 A~G 재실행 | 아래 지적별 표 참조 |
| 같은 파일 복사본·하드 링크, 도구 이름, 독립 초안 내보내기, 승인 후 테마 변경 AppTest | 아래 새 발견 사항과 중점 확인 참조 |
| 7테마 사진 전용 재렌더링 및 이전 결과 비교 | draft·HTML·CSS 바이트, 파일명·검수 플래그 동일. PNG **20장 모두 크기·RGB 픽셀 동일** |
| `.venv/bin/python -m pytest -q` | **517 passed, 0 failed, 0 skipped**, 1077.27초, 종료 0 |
| 테스트 후 `git status --porcelain=v1` | 출력 없음(보고서 추가 전) |

사진 비교는 `samples/facts-rich.json`과 `answer-rich.txt`를 `5cf1467`에서 다시 렌더링하고, 직전 검수에서 보존한 `1e156f6` 결과와 대조했다. 테마는 classic/minimal/bold/modern/natural/impact/industrial이다. 모든 사용자 입력에 대한 동일성 증명이라는 뜻은 아니다.

추가 스크립트·원본 출력·비교 자료는 `/tmp/m8b-recheck/`에만 두었다. 이번에는 요청서에 없는 캡처 갱신을 하지 않았다. 구현 측의 “수정 전 17개 실패” 주장은 과거 버전으로 회귀 테스트를 다시 실행해 검증하지 않았으며, 위 통과 수는 현재 버전을 직접 실행한 결과다.

## 지적별 판정

| # | 판정 | 근거(실행/판독) |
| --- | --- | --- |
| C-1 | **부분 해결** | **실행 A:** AI 이미지 2개가 있는 작업을 `ingest_job(..., render_output=True)`로 렌더링하면 출처 7개가 기록되고 export ZIP에도 동일하게 담긴다. 출처 필드를 지운 정상 작업 결과의 export 거부 테스트도 통과한다. 다만 작업 밖 `staged` 초안은 출처 없이 export가 가능하다(R2-C-1). |
| C-2 | **해결(검증 경로)** | **실행 B:** 같은 작업 초안의 공개 M1 명령이 `needs_review=true`, `page-001.DRAFT.jpg` 등으로 출력하고 출처 7개를 기록한다. 작업 정보 없는 staged 문서도 DRAFT 강제 테스트 통과. 기본 승인 UI·accept의 확인 강제 테스트도 유지된다. |
| I-1 | **해결** | **실행 C:** 생성 lifestyle 1장만 입력하면 대표 사진 필요 오류. 생성 이미지가 앞이고 뒤에 실제 detail 사진이 있는 회귀 테스트는 실제 사진을 hero로 선택한다. `assemble`의 대체 후보에서도 생성 출처를 제외한다(판독). |
| I-2 | **해결(검증 표본)** | **실행 D:** `./rich-hero.png` 별칭 거부. `sub/../`·하드 링크 회귀 테스트 통과. 별도 실제 복사본과 하드 링크도 직접 만들어 거부를 확인했다. 검사가 작업 복사 전에 수행된다(판독). 기존 경로 검사도 심볼릭 링크를 금지한다. |
| I-3 | **해결, UX 보완 권고** | **실행 E:** `tools.example.com`, 합성 토큰 형태가 저장 전에 거부된다. 정상 이름 6개와 주소/토큰 회귀 테스트 통과. 다만 정상 명칭의 가운데점 오탐이 있다(R2-M-1). 실제 인증 정보는 사용하지 않았다. |
| I-4 | **부분 해결** | **실행 F:** 미승인 작업의 ⑤에 `AI 생성`, `AI 배경 변경`, `확인 전`, ⑥ 안내가 표시된다. 그러나 확인 유지 정책이 적용된 승인 작업에서 새 미리보기를 만들면 기존 확인이 전달되지 않아 “확인 전”으로 표시된다(R2-I-1). |
| M-1 | **해결(새 정책 기준)** | **실행 G:** 같은 테마로 승인 작업 재미리보기 시 root `review_accepted=true`, 기존 승인 결과 우선 재개, 새 미리보기는 DRAFT다. 작업 review의 `AI_IMAGE_UNCONFIRMED`는 0개. 문서의 “이미지가 같으면 확인 유지”와 맞는다. 다만 그 상태를 새 렌더에 전달하는 문제는 R2-I-1로 분리했다. |

## 새 발견 사항

줄 번호는 `5cf1467`의 `detail-page-auto/` 기준이다. 3건 모두 **직접 실행**으로 재현했으며, 원인과 수정 방향은 코드 판독으로 대조했다.

| # | 심각도 | 파일:줄 | 내용 | 재현 방법·실제/기대 결과 | 수정 방향 |
| --- | --- | --- | --- | --- | --- |
| R2-C-1 | **Critical** | `core/image_checks.py:151`, `core/render.py:221`, `core/export.py:265` | 작업 정보 없는 `staged` 초안은 AI 이미지임을 알면서도 출처 없는 결과·ZIP을 내보낸다. C-1의 방어가 정상 작업 폴더 배치에만 의존한다. | 재현 1. 실제: DRAFT는 맞지만 render·ZIP 모두 `image_sources` 없음, export는 warning으로 파일 생성, ZIP 생성 성공. 기대: 알려진 AI 이미지의 출처를 확보하거나, 확보할 수 없으면 내보내기를 거부. | 독립 staged 입력에서도 출처 미확인 상태를 결과에 명시하고 내보내기 전 출처 완전성을 검사. 부모 디렉터리에 facts가 있는 경우만 검사하지 않기. 사진 전용 독립 M1 호환은 유지. |
| R2-I-1 | **Important** | `core/render.py:221`, `core/editor.py:240`, `app/main.py:639` | 승인 작업에 유지된 `image_checks`가 새 미리보기 manifest로 전달되지 않아 ⑤가 확인 상태를 잘못 안내한다. | 재현 2. 실제: 같은 이미지의 작업 확인 2개, 작업 review의 미확인 0개인데 새 렌더의 `image_checks`는 없음. UI는 2장 모두 “확인 전” 경고. 기대: 페이지 전체 DRAFT 여부와 별도로 이미지별 확인 완료를 정확히 표시·기록. | 새 렌더에도 유효한 이미지 확인을 전달하고, UI에서 해당 이미지별 체크를 대조. 새 페이지의 승인 상태와 이미지 확인 상태를 구분. |
| R2-M-1 | **Minor** | `core/facts.py:31` | 정상 도구 이름 `DALL·E 3`가 가운데점 때문에 거부된다. | 재현 3. 실제: `generator='DALL·E 3'`는 검증 오류, `'DALL-E 3'`는 통과. 기대: 정상 이름은 사용하거나, 허용 표기 대안을 명확히 안내. | 안전한 명칭 문장부호 허용 범위를 보완하거나 입력 안내에 `DALL-E 3` 같은 대체 표기 제공. 도메인·토큰 금지를 완화할 필요는 없다. |

### 공통 준비

`detail-page-auto`에서 `.venv/bin/python`으로 실행한다.

```python
import sys, json, io, zipfile, shutil, subprocess, tempfile, os
from pathlib import Path
sys.path.insert(0, str(Path('tests').resolve()))
from test_m8b import virtual_images, facts_with, BASE, AI_SCENE, AI_EDITED, ANSWER
from core.workflow import create_job, ingest_job, accept_job, read_json
from core.editor import preview_job
from core.export import export_bundle, build_export_zip

root = Path(tempfile.mkdtemp(prefix='m8b-recheck-', dir='/tmp'))
photos = virtual_images(root / 'photos')
job = create_job(facts_with(BASE + [AI_SCENE, AI_EDITED]), photos,
                 root / 'jobs', theme='modern')
ingest_job(job, ANSWER, render_output=True)
```

### 재현 1 — 작업 정보 없는 연출 초안의 export

이번 회귀 테스트의 `test_m1_render_of_a_staged_document_without_job_files_stays_draft`와 같은 입력 형태다. 초안의 `staged`를 지우거나 숨기지 않는다.

```python
loose = root / 'loose'
shutil.copytree(job / 'images', loose / 'images')
r = subprocess.run([
    sys.executable, 'cli.py', '--input', str(job / 'draft.json'),
    '--images', str(loose), '--output', str(root / 'loose-m1'),
    '--png', '--theme', 'modern',
], capture_output=True, text=True)
assert r.returncode == 0, r.stderr
bundle = Path(r.stdout.strip().splitlines()[-1])
m = read_json(bundle / 'manifest.json')
e = export_bundle(bundle, 'generic', output_dir=root / 'loose-export')
_, data = build_export_zip(Path(e['folder']))
with zipfile.ZipFile(io.BytesIO(data)) as z:
    zipped = json.loads(z.read('manifest.json'))
print(m['needs_review'], e['status'])
print('image_sources' in m, 'image_sources' in zipped)
print((bundle / 'page.html').read_text().count('연출 이미지입니다'))
```

실제 출력: `True warning`, `False False`, `1`. 출력 이미지는 DRAFT이므로 C-2의 일반 파일명 우회가 다시 생긴 것은 아니다. 문제는 이미 연출 문구까지 붙여 AI 사용을 아는 결과를 출처 없이 내보낸다는 점이다. 정상 job 안에서 출처 필드를 삭제하는 회귀 테스트와 달리, export의 `bundle.parent.parent/facts.json` 조건이 성립하지 않는다. 기대는 출처 확보 안내와 내보내기 차단이며, 정보를 알 수 없는데 도구 이름을 추측해 채우라는 의미는 아니다.

### 재현 2 — 확인 유지 후 새 미리보기의 잘못된 안내

```python
accepted = accept_job(job, image_confirmations={
    'image-5': ['no_product'],
    'image-6': ['shape', 'color', 'composition'],
})
from streamlit.testing.v1 import AppTest
from test_app import stage
os.environ['DETAIL_PAGE_OUTPUTS'] = str(job.parent)
app = AppTest.from_file('app/main.py', default_timeout=120).run()
app.selectbox(key='resume_job').set_value(str(accepted))
app.button(key='resume').click().run()
stage(app, 4)  # ⑤ 미리보기
app.selectbox(key='theme_choice').set_value('minimal').run()
preview = Path(app.session_state['bundle'])
print(len(read_json(accepted / 'manifest.json')['image_checks']))
print(read_json(preview / 'manifest.json').get('image_checks'))
print(sum(r.get('code') == 'AI_IMAGE_UNCONFIRMED'
          for r in read_json(accepted / 'review.json')))
print([w.value for w in app.warning])
```

실제: AppTest 예외 없음, 확인 개수 `2`, 렌더 확인 `None`, 미확인 개수 `0`. 경고에는 일반 DRAFT 안내와 함께 다음이 나온다.

> AI로 만든 이미지 2장 · 확인 전: 사진 6 AI 생성(Gemini), 사진 7 AI 배경 변경(ChatGPT). ⑥ 승인에서 원본과 나란히 보고 이미지마다 확인해야 합니다.

이미지는 바꾸지 않고 테마만 바꿨다. 새 페이지를 DRAFT로 만들고 페이지 승인을 다시 받는 것은 맞지만, 현재 정책상 유지된 이미지 확인을 “확인 전”이라고 안내하는 것은 다르다. 같은 테마의 `preview_job(accepted)`도 이미지 확인을 새 렌더에 담지 않는다. 새 `image_checks` 유무를 단순 truthiness로 판단하는 UI에 이 누락이 전달된다.

### 재현 3 — 정상 이름 오탐

```python
facts_with(BASE + [dict(AI_EDITED, generator='DALL·E 3')])  # ValueError
facts_with(BASE + [dict(AI_EDITED, generator='DALL-E 3')])  # 성공
```

실제 오류는 주소·계정 정보 불가 안내다. 주소나 토큰을 입력하지 않은 사용자에게는 원인이 드러나지 않는다. 대체 표기로 계속 작업할 수 있으므로 Minor로 분류했다.

## 중점 확인 결과

1. **확인 없는 일반 파일명 경로:** 집중 테스트와 직접 M1 재현에서 정상 job·독립 staged 모두 DRAFT다. `ingest --accept-review` 거부와 개별 accept 확인 테스트도 통과했다. 일괄 export는 상품별 승인 상태를 요구한다(정적 판독). 갤러리 썸네일은 `thumbnail=True`로 바이트를 반환하는 내부 캐시이며 승인 산출물/일반 JPG를 만들지 않는다(정적 판독). 이번 검증에서 추가 일반 파일명 우회는 재현되지 않았다. 출처 없는 DRAFT export는 R2-C-1로 별도 분류한다.
2. **사진 전용 7테마 호환:** 실제 재렌더 및 RGB 비교 통과. 사진 전용 M1 회귀 테스트도 통과했다. 정상 job의 render manifest에 `image_sources`가 새로 들어가는 메타데이터 변경과 기존 HTML/픽셀/파일명 보존은 구분했다.
3. **`sources_near` 작업 판정:** samples의 facts만으로 job으로 보지 않는 M1 테스트가 통과했다. facts만 있고 manifest 없는 디렉터리도 직접 호출 시 출처 목록을 읽지 않았다. 다만 비작업 디렉터리의 staged 여부는 유지해 DRAFT로 만드는 것은 맞다. 그때 출처를 알 수 없다는 사실을 export 경로가 처리하지 않는 문제가 R2-C-1이다. facts+manifest라는 이름만으로 모든 가능한 비작업 폴더의 오판을 막는다고 증명한 것은 아니다.
4. **도구 이름 오탐:** `ChatGPT`, `Gemini 2.5`, `가상 AI 도구`, `Adobe Firefly`, `Stable Diffusion` 통과를 직접 확인했다. 도메인·합성 토큰은 거부한다. `DALL·E 3` 오탐은 R2-M-1. 20자 이상의 연속 영숫자 제한 때문에 긴 붙임 이름은 거부될 수 있다(정적 판독); 공백을 포함한 정상 명칭 안내가 유용하다.

## 남은 확인 질문

- **이미지가 같으면 확인 유지:** 정책 방향에 동의한다. 페이지 승인과 이미지 비교 확인은 구분할 수 있다. 다만 그 정책을 새 렌더·⑤에도 일관되게 적용해야 한다(R2-I-1). 기존 지시서 4절의 “이미지나 문구가 바뀌면 확인 무효”와 새 설명의 관계도 문서에서 명확히 해 두는 것이 좋다.
- **전경 마스크 면적 비교 제외:** 수동 확인을 유지하고 비율 지표의 한계를 안내한다면 범위 축소는 합리적이다. 이번 재검수는 요청서에 명시된 축소 범위를 기준으로 했고, 모델 미실행 자체를 결함으로 세지 않았다. 원 지시서 3절에는 모델이 있을 때의 면적 비교 요구가 남아 있으므로 확정 범위와 문서 표현을 맞추는 것이 좋다.

두 정책 의견과 별개로 R2-C-1·R2-I-1 수정 후 재검수가 필요하다. 전체 테스트 통과 여부는 위 실행 결과이며, 이번 추가 재현을 자동 테스트가 모두 덮는다는 뜻은 아니다.
