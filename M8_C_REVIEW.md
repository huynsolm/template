# M8-C 검수 보고서

## 요약

- 판정: **재작업 필요**. Critical **1건**, Important **4건**, Minor **1건**.
- 대상: `huynsolm/template`, `ccr-f9c07036-vgvm5j`, `577aabc..e71623d`. 검수일: **2026-11-25(KST)**.
- 핵심은 글자 보존 검사가 같은 문구의 다른 출현을 재사용해 실제 누락을 통과시키는 점이다. 이는 인쇄 단계의 누락을 의도적으로 주입한 검증 시험이며, 기본 UI가 자연적으로 그 누락을 일으켰다는 주장은 아니다.
- 코드·테스트·기존 문서는 수정하지 않았다. 이 보고서 한 파일만 추가한다.

### 직접 실행한 결과

환경: Linux, Python 3.12.14, 저장소 `.venv`, Chromium 156.0.8078.79, `pypdf==6.21.4`. 가상 샘플과 Pillow 생성 이미지만 사용했다. 실제 AI·캔바·외부 이미지 서비스·배경 제거 모델은 호출하지 않았다. 집중 테스트, 추가 Chromium 재현, 변경 전후 렌더링, 전체 테스트, 요청된 캡처는 순차 실행했다.

| 명령·검증 | 결과 |
| --- | --- |
| `git fetch origin`, `git pull --ff-only` | `e71623d` 확인, 시작 시 작업 트리 깨끗함 |
| `uv pip sync --python .venv/bin/python --require-hashes requirements.lock` | 기본 캐시 `/home/agent/.cache/uv`가 읽기 전용이어서 실패. `UV_CACHE_DIR=/tmp/m8c-review/uv-cache`로 같은 명령 재실행 성공. pypdf 1개 설치 |
| `.venv/bin/python -m pytest -q tests/test_m8c.py` | **17 passed, 0 failed, 0 skipped**, 91.07초, 종료 0 |
| `.venv/bin/python -m pytest -q` | **542 passed, 0 failed, 0 skipped**, 1233.45초, 종료 0 |
| `git status --porcelain=v1` | 출력 없음(보고서 추가 전) |
| `.venv/bin/python tools/make_screenshots.py --m8c-only --images /tmp/m8c-shots --samples /tmp/m8c-samples --output /tmp/m8c-out` | 종료 0. 캡처 2장·샘플 PDF 3개 생성 및 캡처 직접 열람. `pdftoppm`의 Type3 glyph bounding-box 경고는 아래 의견에 기록 |
| `577aabc`와 `e71623d`의 7테마 재렌더링 비교 | 초안·HTML·CSS 바이트, 파일명·검수 플래그 동일. **PNG 20장·JPG 20장 모두 크기·RGB 픽셀 동일** |
| 긴 문서, 투명 PNG, 누락 고장 주입, 숨김 요소, 특수 문자, 오프라인 경계 | 아래 발견 사항·중점 결과 참조 |

JPG의 파일 바이트 동일성을 주장하지 않는다. ICC 프로필 생성 시각 바이트가 달랐고, 디코딩한 픽셀은 같았다. 해당 프로필 생성 코드는 변경 전에도 존재한다. 추가 스크립트·PDF·로그·비교 자료는 `/tmp/m8c-review/`에만 두었다. 긴 문서 시험의 최초 실행은 재현 스크립트가 `notice`에 허용되지 않은 title을 넣어 중단됐고, 가상 입력을 바로잡아 다시 실행했다. 이는 제품 코드 실패로 세지 않았다.

## 지시서 대조표

| 항목 | 판정 | 근거 |
| --- | --- | --- |
| 1. 브랜드 색 후보 | 부분 | RGB 가상 상품 색·배경 제외·무채색 제외·결정성·생성 이미지 제외·SHA/버전 기록 테스트 통과. 투명 PNG의 숨은 RGB가 전경 후보를 없애는 I-2가 있다. |
| 2. 색 후보 화면 | 충족(검증 범위) | ①·⑤ AppTest에서 고르기 전 색 유지, 클릭 후 적용을 실제 확인했다. 후보 대비와 테마별 경고/보정을 제공한다. |
| 3. PDF | 부분 | 7테마 기본 샘플과 긴 문서 쪽 수·크기, DRAFT 이름, 출처 검사, 기본 ZIP 포함 테스트 통과. 판매처 ZIP의 PDF 누락 I-4와 글자 검사 미탐 C-1과 오탐 I-1, 문자 표현 제한 M-1이 있다. |
| 4. 캔바 확인 절차 | 부분 | 사람 확인용 표와 가상 PDF가 있고 README는 확인 예정으로 구분한다. 체크리스트 쪽 수가 실제 샘플과 다르다(I-3). 캔바 편집 가능 여부 자체는 미확인이다. |
| 5. 테스트 | 부분 | 실제 Chromium·AppTest와 전체 실행은 위 결과. 기존 7테마 픽셀도 보존됐다. 다만 단일 문구 추출을 바꾸는 누락 테스트가 C-1을 잡지 못하고, 투명·숨김·VS16 사례가 빠져 있다. |
| 6. 문서·의존성 | 부분 | README·인계서·검수 요청서와 pypdf 해시 잠금이 있다. 다른 기존 패키지 버전 변경은 없다. 샘플 쪽 수 안내는 I-3에 따라 정정 필요. |

## 발견 사항

위치는 `e71623d`의 `detail-page-auto/` 기준이다. 모두 **직접 실행으로 재현**했으며 원인은 정적 판독으로 대조했다.

| # | 심각도 | 파일:줄 | 내용 | 재현 입력·실제/기대 결과 | 수정 방향 |
| --- | --- | --- | --- | --- | --- |
| C-1 | **Critical** | `core/pdf.py:110` | 전역 PDF 문자열에 포함되는지만 검사해, 같은 문구가 한 곳에서 빠져도 다른 곳의 문구로 검사에 통과한다. | 재현 A. 원본 hero와 pain 제목에 같은 문구 2개, 인쇄 직전 hero 1개 누락. 실제 PDF에는 1개인데 `missing=0`으로 저장. 기대: hero 누락 실패·위치 표시·신규 PDF 미저장. | 실제 출현 횟수와 위치를 고려해 텍스트를 대응시키고 같은 PDF 텍스트를 여러 원본 출현에 재사용하지 않기. 반복·포함 문구와 실제 인쇄 단계 누락 회귀 시험 추가. |
| I-1 | **Important** | `core/pdf.py:41` | 텍스트의 직접 부모만 검사하므로 숨김 조상 안의 보이지 않는 글을 필수 문구로 수집한다. | 재현 B. `display:none` div 안 p의 숨은 문구를 넣으면 PDF 내보내기가 “글자 보존 실패”로 중단된다. 기대: 화면에 보이지 않는 문구는 검사 대상 제외. | 조상에 의한 표시 상태와 실제 렌더링 여부를 반영해 텍스트 노드 수집. |
| I-2 | **Important** | `core/colors.py:48` | 완전 투명 영역의 RGB를 배경 색 집계에 넣어, 실제 전경 색까지 배경으로 제거한다. | 재현 C. 보이는 결과가 같은 RGBA PNG 두 개에서 하나는 `[]`, 다른 하나는 녹색 `#149646` 후보. 기대: 투명 픽셀의 보이지 않는 RGB가 결과에 영향 없음. | 알파/전경 마스크가 있으면 먼저 실제 전경을 선정하고 투명 RGB를 배경 추정에 쓰지 않기. RGBA·투명 팔레트 PNG 회귀 시험 추가. |
| I-3 | **Important** | `docs/canva-check.md:21` | 캔바 체크리스트가 샘플을 모두 7쪽으로 가정한다. | 커밋된 PDF를 직접 읽으면 modern 3쪽, natural 3쪽, classic 2쪽이다. 기대: 실제 원본 쪽 수·크기를 기준으로 업로드 결과 비교. | 테마별 원본 쪽 수와 쪽별 크기 안내를 샘플에서 생성하거나 실제 값으로 기재. 계정 정보 없이 캡처 경로도 적을 칸 제공. |
| I-4 | **Important** | `core/export.py:366` | 판매처 프로필 ZIP에 PDF가 빠지는데 ZIP manifest는 PDF가 있다고 기록한다. | 재현 E. 원본 `page.pdf`는 존재하고 ZIP manifest의 `pdf.file`도 `page.pdf`지만 ZIP에는 PDF가 0개다. 기대: 만든 PDF를 ZIP에도 포함하고 기록과 실제 파일이 일치. | 기본 ZIP뿐 아니라 `build_export_zip`에서도 원본 PDF를 안전하게 포함하고 두 ZIP 경로를 모두 회귀 검사. |
| M-1 | **Minor** | `core/pdf.py:48`, `core/pdf.py:111` | 표시용 변형 선택자 U+FE0F가 추출에서 빠지면 다른 문구가 모두 있어도 내보내기가 실패한다. | 재현 D. 제목 `제품 · 확인 ※ 주의 ⭐️ 😀 USB-C AC-220V`에서 추출에는 `⭐`·나머지 문구가 있으나 VS16만 없어 hero 누락 오류. 기대: 보존 정책에 맞게 표시 코드와 실제 문구 누락을 구분하거나 지원 제한 안내. | VS16 등 표시 코드 처리 정책을 정하고 제한된 정규화/진단 적용. 실제 문자 누락을 무조건 제거하는 방식은 피하기. |

### 재현 A — 중복 문구의 실제 누락 통과

`detail-page-auto`에서 `.venv/bin/python`으로 실행했다. 추출 함수를 바꿔 끼우지 않았다. Chromium의 인쇄 직전 이벤트로 한 문구의 출력만 없애 검증기를 시험했다.

```python
import re, tempfile
from pathlib import Path
from pypdf import PdfReader
from core.schema import Document
from core.render import render
from core.pdf import make_pdf
from core.workflow import read_json

doc = Document.model_validate({
    'schema_version': '1.0',
    'product': {'name': '가상 시험', 'category': '가상',
                'price': '표시 없음', 'brand_color': '#305b46'},
    'sections': [
        {'id': 'hero', 'type': 'hero', 'headline': '공통 검증 문구',
         'image': 'rich-hero.png'},
        {'id': 'pain', 'type': 'pain', 'title': '공통 검증 문구',
         'items': ['누락 확인용 본문']},
    ],
})
out = Path(tempfile.mkdtemp(dir='/tmp'))
bundle = render(doc, Path('samples'), out, png=True, theme='classic')
html = bundle / 'page.html'
original = html.read_text()
html.write_text(original.replace('</body>', '''<script>
window.addEventListener('beforeprint', () => {
  document.querySelector('h1').style.visibility = 'hidden';
});</script></body>'''))
pdf = make_pdf(bundle)
text = ''.join(p.extract_text() or '' for p in PdfReader(pdf).pages)
print(original.count('공통 검증 문구'))
print(re.sub(r'\s+', '', text).count('공통검증문구'))
print(read_json(bundle / 'manifest.json')['pdf']['text_check'])
```

실제: 원본 출현 `2`, PDF 출현 `1`, 검사 결과 `{'runs': 5, 'missing': 0}`. PDF가 1쪽으로 저장되고 쪽 수도 일치하므로 쪽 수 검사로도 잡히지 않는다. 대조 시험으로 hero만 `유일한 검증 머리말`로 바꾸고 같은 누락을 주입하면 hero 위치를 표시하며 올바르게 실패하고 PDF·임시 파일을 남기지 않았다. 즉 누락 감지 자체가 없는 것이 아니라 반복/포함 문구를 구분하지 못한다.

### 재현 B — 숨김 조상 오탐

A의 **고장 주입 전 원본**과 같은 유효 문서를 별도 렌더링했다. 첫 section 안에 아래 요소만 추가하고 `make_pdf`를 호출했다.

```html
<div style="display:none"><p>숨은검수전용문구</p></div>
```

실제: `PDF에서 글자 1곳이 빠졌습니다(글자 보존 실패). 위치: hero: 숨은검수전용문구`. PDF·tmp 파일은 없었다. p의 계산된 display는 block이지만 조상 때문에 화면과 PDF 어디에도 보이지 않는 문구다. 정상 UI가 이 마크업을 자동 생성한다는 주장이 아니라, 요청서의 숨김 요소 및 “보이는 텍스트” 기준을 직접 시험한 결과다.

### 재현 C — 투명 RGB의 영향

```python
from PIL import Image, ImageDraw
from core.colors import suggest_colors

for name, clear_rgb in [('green', (20,150,70,0)), ('black', (0,0,0,0))]:
    image = Image.new('RGBA', (240,240), clear_rgb)
    ImageDraw.Draw(image).rectangle((50,50,190,190), fill=(20,150,70,255))
    image.save(out / (name + '.png'))
    print(name, suggest_colors([out / (name + '.png')]))
```

실제 green은 `[]`, black은 첫 후보 `#149646`, share `1.0`, 흰 배경 대비 `3.83`이다. 두 파일을 같은 흰 배경에 알파 합성한 픽셀이 완전히 같음도 확인했다. ① 화면이 호출하는 실제 색 추출 함수의 지원 입력이며 외부 모델을 사용하지 않았다.

### 재현 D — VS16

유효한 modern 문서의 hero headline을 `제품 · 확인 ※ 주의 ⭐️ 😀 USB-C AC-220V`로 바꾸면 `make_pdf`가 hero 누락 오류로 실패했다. 진단을 위해 같은 오프라인 로더·페이지 나누기로 원시 PDF를 별도 `/tmp`에 출력해 추출 문자를 대조했다. 없는 문자는 **U+FE0F 하나**였고 `·`, `※`, `⭐`, `😀`, 영문 하이픈은 추출됐다. 진단용 원시 PDF를 검증 완료 산출물로 배포하지 않았다. 의미 있는 문자까지 버리도록 검사를 약화할 것을 권하는 것은 아니다.

### 재현 E — 판매처 ZIP의 PDF 누락

고장 주입이 없는 정상 문서에서 PDF를 만든 뒤, ⑦의 판매처 내보내기와 같은 함수를 실행했다.

```python
import io, json, zipfile
from core.export import export_bundle, build_export_zip
normal = doc.model_copy(deep=True)
normal.sections[0].headline = '일반 검증 문구'
fresh = render(normal, Path('samples'), out / 'zip', png=True,
               theme='modern', max_height=2500)
pdf = make_pdf(fresh)
result = export_bundle(fresh, 'generic', output_dir=out / 'exports')
_, data = build_export_zip(Path(result['folder']))
with zipfile.ZipFile(io.BytesIO(data)) as z:
    meta = json.loads(z.read('manifest.json'))
    print(pdf.is_file(), meta['pdf']['file'], meta['pdf']['file'] in z.namelist())
```

실제: `True page.pdf False`. ZIP의 `.pdf` 파일은 0개였다. generic 프로필은 규격 미확인 등에 따른 warning으로 정상 파일을 생성했고 출처 차단 오류는 없었다. 기본 `core.editor.build_zip`에 PDF를 추가한 것과 달리, 프로필 ZIP은 HTML/draft/review/assets만 수집해 PDF를 빠뜨린다. 이 두 경로를 같은 “ZIP 포함”으로 간주하면 안 된다.

## 중점 검수 항목 결과 (요청서 3장 1~10)

1. **지시서 — 문제 있음.** 1~6절 대조표와 발견 사항 참조. 캔바 편집은 사용자 확인 예정으로 구분한다.
2. **색 — 부분 문제 있음.** 기본 배경색/무채색 제외, 결정성, 생성 이미지 제외, 원본 불변은 집중 테스트에서 확인했다. 투명 PNG는 I-2. 상품과 배경 색이 비슷하거나 작은 단색 사진에서는 후보가 없을 수 있는 휴리스틱이다(판독). 대표 사진을 먼저 정렬하지만 집계 자체에는 별도 우선 가중치가 없다(판독). 선택 전 색 유지와 선택 후 적용은 AppTest 통과.
3. **쪽 나누기 — 확인 표본에서 문제 없음.** 7테마 기본 PDF 쪽 수·645pt 근사 너비·높이 테스트 통과. 별도 긴 문서(hero + 긴 notice 9개)는 `max_height=2000/6000/18000`에서 성공했고 쪽 수는 각각 **4/4, 2/2, 1/1**로 JPG/PDF가 일치했다. +2px은 이 표본에서 빈 쪽 방지에 작동했지만 모든 문서에 대한 증명은 아니다.
4. **글자 보존 — 문제 있음.** C-1, I-1, M-1. Pillow 가상 AI 이미지 작업을 별도로 만들어 PDF의 “연출 이미지입니다” 추출, `page.DRAFT.pdf`, 출처 7개 유지를 직접 확인했다. `Usb-C product`에 CSS uppercase를 적용한 경우도 PDF의 `USB-C PRODUCT`를 정상 검사했다. 고유 문구 누락 대조 시험에서는 실패·위치 보고·임시 파일 제거가 정상 동작했다.
5. **안전 — 확인 범위 내 문제 없음.** 정상 집중 테스트에서 PDF의 외부 요청 기록은 비어 있다. 추가로 예약 `.invalid` 이미지 URL과 `..%2Foutside.png` 참조를 가진 가상 번들을 넣었을 때 오프라인 로더에서 차단되어 PDF가 남지 않았다. 실제 외부 서버에 접속하지 않았다. AI 출처 검사와 DRAFT 이름은 집중 테스트 통과.
6. **기존 결과 — 문제 없음(표본 범위).** 양 커밋에서 같은 facts/답변으로 7테마를 직접 재렌더링했다. HTML·CSS·초안·파일명과 PNG/JPG 20장씩의 RGB 픽셀이 동일하다. ICC 시각에 의한 파일 바이트 차이는 픽셀 회귀로 세지 않았다.
7. **의존성 — 문제 없음.** 기존 버전 목록을 실제 비교한 결과 pypdf 6.21.4만 추가, 기존 버전 변경 없음. SHA-256 2개가 잠금 파일에 있고 `--require-hashes` 동기화 성공. 캐시 경로만 환경 제약에 맞춰 변경했다.
8. **화면·ZIP — 부분 문제 있음.** ①·⑤ 후보 선택과 ⑦ PDF 생성·다운로드, DRAFT PDF의 기본 ZIP 포함은 실제 AppTest/집중 테스트 통과. 판매처 프로필 ZIP은 I-4와 같이 PDF가 누락된다. UI의 PDF 글자 보존 보장은 C-1 수정과 함께 다뤄야 한다.
9. **테스트 품질 — 보완 필요.** 실제 Chromium·AppTest이며 건너뛰기나 비활성화로 통과시킨 정황은 없다. 다만 추출 함수를 바꾸는 단일 고유 문구 시험만으로 검증기 강도를 보장하지 못한다. C-1의 반복 문구+실제 인쇄 단계 누락, 숨김 조상, RGBA 동등 표시를 회귀로 고정할 필요가 있다.
10. **캔바 절차 — 부분 문제 있음.** 글자 상자·한글 수정·폰트 대체·정렬·개별 사진·배경·날짜와 개인정보 제외는 다룬다. 원본 쪽 수는 I-3에 따라 수정해야 한다. Type3의 캔바 편집성과 폰트 대체 결과는 실제 업로드 미확인이다.

## 구현 측 결정에 대한 의견 (요청서 4장 1~5)

1. **동의.** 사용자가 요청할 때 후보를 계산하는 방식은 타당하다. UI는 manifest 후보를 재사용한다. 다만 `job_color_suggestions` 함수 자체는 기록 비교 전에 매번 양자화를 수행하므로 “함수가 결과 캐시로 계산을 생략한다”는 뜻으로 이해하면 안 된다(판독).
2. **동의.** PDF를 요청 시 생성하면 일반 미리보기 비용을 줄일 수 있다. DRAFT·출처 검사를 같은 경로에 적용하는 것도 맞다.
3. **조건부 동의.** +2px 차이를 명시하고 문서별 실제 크기를 기록하는 것은 허용 가능한 선택이다. 7테마·긴 문서의 이번 표본에서 쪽 수는 일치했다. 다만 PDF 치수가 JPG와 완전히 같다는 안내나 샘플이 모두 같은 높이라는 안내는 피해야 한다.
4. **방향은 동의, 현 검사는 반대.** 실제 보이는 문구를 기준으로 하면 렌더링되지 않은 상품 필드의 오탐을 줄인다. 그러나 조상 숨김을 반영해야 하고, PDF 안의 아무 출현 하나를 모든 동일 문구에 재사용해서는 안 된다(C-1/I-1).
5. **조건부 동의.** Type3 사실을 숨기지 않고 확인 예정으로 기록한 것은 맞다. 캡처의 `pdftoppm` 실행도 종료 0이었으나 `Bad bounding box in Type 3 glyph` 경고가 발생했다. 첫 쪽 육안 확인을 모든 PDF 도구에서의 호환성 보장으로 해석하면 안 된다. 글자 추출·선택 가능성과 캔바에서의 수정 가능성은 별개다. 샘플과 체크리스트를 맞춘 후 사용자가 결과를 제공하기 전까지 캔바 편집 가능을 완료로 표시하면 안 된다.

## 확인 질문

- VS16 같은 표시용 선택자는 엄격한 문자 동일성 대상인지, 실제 표시 문구 기준으로 정규화할지 확정할 필요가 있다(M-1).
- “대표 사진 우선”이 단순 입력 정렬인지 후보 순위에 가중치를 주는 것인지 명확히 하면 좋다. 현재 합산에서는 순서가 대표 사진의 가중치로 작동하지 않는다.
- 캔바 편집 결과는 사용자 확인이 남아 있다. I-3을 고친 원본 기준으로 테마별 글자 상자·폰트 대체·정렬과 캡처 경로를 기록해 달라.

C-1과 I-1~I-4는 정책 답변과 별개로 수정·재검수가 필요하다. 서버 반영이나 캔바 업로드는 이번 검수에서 수행하지 않았다.
