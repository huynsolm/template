# M8-C 재검수 보고서

## 요약

- 판정: **재작업 필요**. 새 발견 사항은 **Critical 1건, Important 1건, Minor 0건**이다.
- 대상: `huynsolm/template`, `ccr-f9c07036-vgvm5j`, `ac055d8..ae8674f`. 검수일: 2026-11-25(KST).
- 이전 A~E의 직접 재현은 수정됐다. 다만 새 가시성 필터가 `display:contents`의 보이는 문구를 검사 대상에서 제외하며, 색 추출은 실제로 불투명한 RGBA 사진의 배경을 제외하지 않는다.
- 이번 보고서는 **A(M8-C 수정분)**에 한정한다. 디자인 시안·실제 상품 자료는 검수·커밋 대상이 아니다. 코드·테스트·다른 문서는 수정하지 않고 이 보고서만 추가한다.

### 실행 결과

환경: Linux, Python 3.12.14, 저장소 `.venv`, Chromium 156.0.8078.79, pypdf 6.21.4. 가상 샘플·Pillow 생성 이미지만 사용했다. 실제 AI·캔바·배경 제거 모델·외부 이미지 서비스는 호출하지 않았다. 집중 테스트 → 이전 재현 → 추가 Chromium 재현 → 전체 테스트를 겹치지 않게 순차 실행했다.

| 실행 | 결과 |
| --- | --- |
| `git fetch origin`, `git pull --ff-only` | `ae8674f` 확인, 시작 시 작업 트리 깨끗함 |
| `.venv/bin/python -m pytest -q tests/test_m8c_review.py tests/test_m8c.py` | **31 passed, 0 failed, 0 skipped**, 139.00초, 종료 0 |
| 지난 보고서 재현 A~E 재실행 | 아래 지적별 판정 참조 |
| 추가 RGBA·display:contents·위첨자·긴 문서 검사 | 아래 새 발견 사항·중점 확인 참조 |
| `.venv/bin/python -m pytest -q` | **556 passed, 0 failed, 0 skipped**, 1248.91초, 종료 0 |
| 테스트 후 `git status --porcelain=v1` | 출력 없음(보고서 추가 전) |

원본 실행 결과와 스크립트는 `/tmp/m8c-recheck/`에만 있다. 구현 측이 보고한 수정 전 실패 수를 과거 커밋에서 별도로 다시 실행하지는 않았다. 현재 버전의 통과 수와 아래 재현은 직접 확인했다. 이번 범위에서는 이전의 7테마 JPG/PNG 픽셀 비교나 문서 캡처 갱신을 별도로 반복하지 않았다. 렌더러·테마 CSS·템플릿이 이번 커밋에서 바뀌지 않았음은 diff로 확인했다.

## 지적별 판정

| # | 판정 | 근거(실행/판독) |
| --- | --- | --- |
| C-1 | **부분 해결** | **실행 A:** 같은 문구를 hero와 pain 제목에 두고 인쇄 직전 hero만 숨긴 기존 재현은 이제 hero 위치를 표시하며 실패한다. 고유 문구·포함 문구·누락 없는 반복 문구 회귀도 통과한다. 그러나 검사 대상 수집 단계가 다른 보이는 문구를 놓쳐 실제 누락을 통과시키는 새 경로가 있다(R-C-1). |
| I-1 | **해결(기존 재현)** | **실행 B:** 조상 `display:none` 안의 문구를 넣어도 정상 PDF가 생성된다. `visibility:hidden`을 포함한 집중 테스트도 통과했다. `display:contents`의 과도한 제외는 별도 R-C-1로 분리한다. |
| I-2 | **부분 해결** | **실행 C:** 투명 영역의 숨은 RGB만 다른 두 RGBA PNG가 같은 `#149646` 후보를 낸다. 투명 팔레트 회귀도 통과했다. 다만 알파가 모두 255인 RGBA 사진에는 배경 제외가 적용되지 않는 R-I-1이 남았다. |
| I-3 | **해결** | **실행:** 커밋된 샘플을 읽는 테스트에서 modern 3쪽·natural 3쪽·classic 2쪽과 실제 크기 표가 일치한다. 쪽 수·크기·편집·폰트 대체·정렬·캡처 경로 칸이 있고 README는 확인 예정이다. **판독:** 샘플 재생성 도구가 표도 생성한다. 실제 캔바 편집은 아직 미확인이다. |
| I-4 | **해결** | **실행 E:** 정상 PDF를 만든 뒤 프로필 ZIP을 생성하면 기록된 `page.pdf`가 실제 ZIP에 포함된다. 집중 테스트에서 기본/프로필 두 ZIP의 PDF 바이트 일치, 기록 파일이 사라지면 거부, PDF 기록이 없는 경우도 확인했다. |
| M-1 | **해결(명시된 정책 기준)** | **실행 D:** 이전 `제품 · 확인 ※ 주의 ⭐️ 😀 USB-C AC-220V` 입력으로 정상 PDF가 생성된다. 회귀 테스트는 U+FE0F 무시 개수 기록과 실제 ⭐ 누락 시 실패를 확인한다. **판독:** 정규화는 이체 선택자로 제한되고 ZWJ는 제거하지 않는다. |

## 새 발견 사항

줄 번호는 `ae8674f`의 `detail-page-auto/` 기준이다. 두 항목 모두 **직접 실행**으로 재현했다.

| # | 심각도 | 파일:줄 | 내용 | 재현 방법·실제/기대 결과 | 수정 방향 |
| --- | --- | --- | --- | --- | --- |
| R-C-1 | **Critical** | `core/pdf.py:44` | `display:contents` 부모는 자체 상자가 없어 `checkVisibility()`가 false지만 그 안의 텍스트는 보인다. 이 텍스트를 검사 대상에서 빼므로 실제 인쇄 단계 누락이 통과한다. | 재현 1. 화면에 보이고 스냅샷 경계도 같은 고유 제목이 runs에는 없다. 인쇄 직전 제목을 숨기면 PDF에서 사라져도 `missing=0`으로 파일 생성. 기대: 제목도 대상으로 수집해 누락 실패·위치 보고·신규 PDF 미저장. | 요소 자체의 상자 유무와 텍스트의 실제 가시성을 구분. 텍스트 Range와 조상 표시 상태를 함께 고려하고, 기존 숨김 회귀를 유지하며 display:contents 제어 시험 추가. |
| R-I-1 | **Important** | `core/colors.py:43`, `core/colors.py:46` | RGBA/LA 모드라는 이유만으로 전경 마스크가 있다고 간주한다. 실제로 전부 불투명한 사진에도 배경 추정을 생략해 배경색을 주요 상품색으로 제안한다. | 재현 2. 파란 배경·노란 상품의 같은 사진에서 RGB는 노랑 1개, 알파가 모두 255인 RGBA는 파랑이 75.3%로 1순위. 기대: 알파가 배경을 구분하지 않는 불투명 사진은 RGB와 같은 배경 제외. | 채널 존재뿐 아니라 알파가 실제 전경/배경을 구분하는지 확인. 불투명 알파의 경우 기존 가장자리 배경 추정을 적용하고 true transparency·투명 팔레트 회귀는 유지. |

### 재현 1 — 보이는 display:contents 문구가 검사에서 제외됨

`detail-page-auto`에서 `.venv/bin/python`으로 실행한다. 아래는 가상 문서의 인쇄 누락을 시험하기 위한 고장 주입이다. 정상 앱 UI가 이 누락을 자동 발생시킨다는 주장은 아니다. 추출 함수를 바꿔 끼우지 않았다.

```python
import tempfile
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
        {'id': 'hero', 'type': 'hero', 'headline': '고유한 가시 문구',
         'image': 'rich-hero.png'},
        {'id': 'pain', 'type': 'pain', 'title': '다른 위치 제목',
         'items': ['누락 확인용 본문']},
    ],
})
out = Path(tempfile.mkdtemp(dir='/tmp'))
bundle = render(doc, Path('samples'), out, theme='modern', png=True)
html = bundle / 'page.html'
html.write_text(html.read_text().replace('</body>', '''<script>
const h = document.querySelector('h1'), s = document.createElement('span');
s.style.display = 'contents';
s.textContent = h.textContent;
h.replaceChildren(s);
window.addEventListener('beforeprint', () => { h.style.visibility = 'hidden'; });
</script></body>'''))
pdf = make_pdf(bundle)
text = ''.join(p.extract_text() or '' for p in PdfReader(pdf).pages)
print('고유한가시문구' in ''.join(text.split()))
print(read_json(bundle / 'manifest.json')['pdf']['text_check'])
```

실제: 제목 존재 `False`, 검사 결과 `runs=5`, `missing=0`, `matching='position-occurrence'`로 정상 저장된다. 고유 제목이 다른 문구와 같거나 포함되는 경우가 아니므로 기존 중복 소비 보완만으로는 막히지 않는다.

인쇄 전 별도 Chromium에서 `TEXT_JS`를 평가해 다음을 직접 확인했다.

- h1의 표시 문구는 `고유한 가시 문구`, h1은 visible이다. 화면 캡처도 직접 열어 제목을 확인했다.
- span의 `checkVisibility({checkVisibilityCSS:true})`는 false지만 텍스트 Range의 client rect는 1개다.
- 제목은 수집된 runs에 없다.
- 본문 높이 1363px과 두 섹션의 top/bottom이 기존 스냅샷과 같다. 따라서 스냅샷 생성 뒤 레이아웃을 바꿔 생긴 쪽 수 오류와는 다른 사례다.

### 재현 2 — 불투명 RGBA의 배경색이 후보가 됨

```python
from PIL import Image, ImageDraw
from core.colors import suggest_colors

rgb = Image.new('RGB', (240,240), '#1f5fbf')
ImageDraw.Draw(rgb).rectangle((70,50,170,190), fill='#e8a317')
rgb.save(out / 'rgb.png')
rgb.convert('RGBA').save(out / 'rgba.png')  # 모든 알파 255, 표시 픽셀은 같음
print(suggest_colors([out / 'rgb.png']))
print(suggest_colors([out / 'rgba.png']))
```

실제 RGB는 노랑 `#e8a317`만 share `1.0`으로 제안한다. RGBA는 파란 **배경색** `#1f5fbf`를 share `0.753`으로 1순위, 노랑을 `0.247`로 2순위에 둔다. 투명 PNG를 지원하려고 배경 추정을 생략한 분기가 불투명한 RGBA 사진에도 적용된 결과다. 실제 색 후보 함수에 들어갈 수 있는 일반 사진 입력이며, 색이 자동 적용됐다는 뜻은 아니다.

## 중점 확인 결과

1. **위치 허용 범위·줄바꿈·표·숫자 띠·위첨자:** 7테마 기본 가상 문서 PDF 검사는 집중 테스트에서 통과했다. 기존 긴 문서(hero + 긴 notice 9개)도 `max_height=2000/6000/18000`에서 각각 JPG/PDF **4/4, 2/2, 1/1쪽**으로 정상 생성됐다. 실제 입력 가능한 `m²` 제목과 흐름 높이를 유지한 CSS sup 재현도 통과했다. 처음의 기본 sup 삽입 시험은 스냅샷 생성 뒤 행 높이를 바꿔 쪽 수가 달라졌으므로 유효한 기존 스냅샷 시험으로 보지 않았다. 이 표본 통과가 모든 위치·서식 조합의 증명은 아니며, 새 Critical은 허용 범위가 아니라 수집 대상 자체의 누락이다.
2. **화면 순서와 다른 modern 추출:** 기존 A의 반복/포함 문구 누락과 실제 누락 위치 진단은 회귀 테스트·직접 재현에서 개선됐다. PDF 문자 위치와 출현 소비로 대응하는 방향은 타당하다. 그러나 위치 대응 이전에 보이는 문구를 빠짐없이 수집해야 한다(R-C-1).
3. **이체 선택자·ZWJ:** 명시한 이체 선택자만 무시하고 개수를 기록하며 실제 별표 누락은 실패시키는 것은 이전 Minor의 구체적인 해결이다. ZWJ를 임의로 제거하지 않는 정책에 동의한다. 복합 이모지의 의미를 보존할 수 없을 때 조용히 통과시키기보다 제한을 알려 주는 편이 타당하다. 이번에 모든 ZWJ 조합이나 모든 이체 선택자의 시각적 동일성을 검증한 것은 아니다.
4. **테스트 변경:** 기존 추출 교체 시험은 `page_characters`의 문자와 높이를 함께 제거하도록 옮겨 검사 대상 단계에 맞췄다. 검증을 삭제한 것이 아니며 실제 beforeprint 누락 회귀도 추가됐다. 다만 display:contents의 보이는 고유 문구와 RGB/불투명 RGBA의 동등성은 현재 회귀에 없다.
5. **범위·사람 확인:** 실제 상품 자료·디자인 scratchpad를 저장소에 넣지 않았다. 캔바 편집 결과는 여전히 사용자 확인 예정이며, 서버 반영이나 디자인 구현은 이번 검수에서 수행하지 않았다.

R-C-1·R-I-1을 수정하고 재검수할 필요가 있다. 전체 테스트의 통과 여부와 추가 재현에서 발견한 결함은 구분해야 한다.
