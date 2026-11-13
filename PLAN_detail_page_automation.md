# 상세페이지 자동화 — Codex용 계획 브리프

> 이 문서를 Codex에게 그대로 전달하고 "이 브리프를 바탕으로 구현 계획(작업 단위·파일 구조·마일스톤)을 세워줘"라고 요청하세요.
> 참고 영상: https://www.instagram.com/reel/DfjwQCXSngE/ (영상 내용은 직접 확인하지 못했음. 아래 `0. 참고 영상 요약`을 직접 채워 넣으면 Codex의 계획이 더 정확해집니다.)

---

## 0. 참고 영상 요약 (사용자가 채울 부분)
- 영상에서 사용한 도구: (예: ChatGPT / Claude / Gemini / Midjourney / Figma / Make·n8n / 구글시트 …)
- 입력값: (예: 상품명 + 상품 사진 몇 장 + 쿠팡/스마트스토어 URL)
- 출력물: (예: 860px 세로형 JPG 상세페이지 한 장 / 섹션별 이미지 여러 장)
- 꼭 따라 하고 싶은 부분:

## 1. 목표
상품 정보와 사진을 넣으면 **오픈마켓(스마트스토어·쿠팡 등)에 바로 올릴 수 있는 상세페이지 이미지**를 자동으로 만든다.

- 입력: 상품명, 카테고리, 가격, 핵심 특징(텍스트 또는 경쟁사 URL), 상품 사진 1~N장
- 출력: 가로 860px 세로형 상세페이지 (JPG/PNG, 길면 여러 장으로 분할), 편집 가능한 HTML 원본
- 성공 기준: 상품 1개 기준 5분 이내 생성, 사람이 문구만 살짝 고치면 바로 업로드 가능한 품질

## 2. 전체 파이프라인
```
[입력 폼/시트] → [1. 정보 수집·정리] → [2. 카피 생성(LLM)] → [3. 섹션 구성(JSON)]
 → [4. 이미지 처리(누끼·보정·AI 연출컷)] → [5. HTML 템플릿 렌더링] → [6. 스크린샷 → JPG 분할] → [7. 검수·다운로드]
```

| 단계 | 내용 | 추천 기술 |
|---|---|---|
| 1. 정보 수집 | 입력값 정리, 경쟁사 URL이 있으면 리뷰·특징 크롤링 | Python, Playwright |
| 2. 카피 생성 | 후킹 문구, 고객 고민(Pain point), 해결/특장점, 사용법, FAQ, 스펙 | LLM API (Claude/OpenAI), 프롬프트 템플릿 |
| 3. 섹션 구성 | LLM 결과를 **정해진 JSON 스키마**로 받기 (섹션 타입 + 문구 + 이미지 슬롯) | JSON Schema / Pydantic 검증 |
| 4. 이미지 처리 | 배경 제거(누끼), 리사이즈, 필요하면 AI 연출 이미지 생성 | rembg, Pillow, 이미지 생성 API(선택) |
| 5. 렌더링 | 섹션 JSON → HTML/CSS 템플릿(섹션별 컴포넌트) | Jinja2 또는 React, 한글 폰트(Pretendard 등) |
| 6. 출력 | 860px 폭 풀페이지 스크린샷 → 일정 높이로 분할 저장 | Playwright, Pillow |
| 7. 검수 | 미리보기 화면에서 문구 수정 후 다시 렌더링 | 간단한 웹 UI (Streamlit 또는 Next.js) |

## 3. 섹션 JSON 스키마 (초안)
```json
{
  "product": { "name": "", "category": "", "price": "", "brand_color": "#000000" },
  "sections": [
    { "type": "hero",      "headline": "", "subcopy": "", "image": "hero.png" },
    { "type": "pain",      "title": "", "items": ["", "", ""] },
    { "type": "solution",  "title": "", "body": "", "image": "" },
    { "type": "features",  "items": [{ "title": "", "desc": "", "image": "" }] },
    { "type": "how_to",    "steps": [{ "title": "", "desc": "" }] },
    { "type": "review",    "items": [{ "text": "", "rating": 5 }] },
    { "type": "spec",      "rows": [["항목", "값"]] },
    { "type": "faq",       "items": [{ "q": "", "a": "" }] },
    { "type": "notice",    "body": "배송/교환/반품 안내" }
  ]
}
```
섹션 타입마다 HTML 템플릿 1개 → 순서만 바꿔도 다른 상세페이지가 나오도록 설계.

## 4. 마일스톤 (Codex가 세부 작업으로 쪼갤 단위)
1. **M1 — 렌더링 엔진(MVP)**: 손으로 쓴 샘플 JSON → HTML → 860px JPG 출력. (LLM 없이 먼저 결과물 모양을 고정)
2. **M2 — 카피 자동 생성**: 상품 정보 입력 → LLM → 스키마에 맞는 JSON. 검증 실패 시 재시도.
3. **M3 — 이미지 처리**: 누끼·리사이즈·슬롯 자동 배치. (AI 이미지 생성은 선택 기능)
4. **M4 — 입력/미리보기 UI**: 폼 입력 → 미리보기 → 문구 수정 → 다운로드(ZIP).
5. **M5 — 확장**: 템플릿 테마 여러 개, 구글시트 일괄 생성(여러 상품), 경쟁사 URL 분석, 플랫폼별 규격(스마트스토어/쿠팡).

## 5. 권장 폴더 구조
```
detail-page-auto/
  app/            # UI (Streamlit 또는 Next.js)
  core/
    collect.py    # 입력·크롤링
    copywriter.py # LLM 프롬프트 + JSON 생성
    schema.py     # Pydantic 스키마
    images.py     # 누끼·리사이즈
    render.py     # HTML 렌더 + 스크린샷 + 분할
  templates/      # 섹션별 HTML/CSS, 테마
  prompts/        # 카피 프롬프트 (톤·카테고리별)
  samples/        # 샘플 입력·출력
  tests/
```

## 6. 결정이 필요한 사항 (Codex에게 같이 물어볼 것)
- 사용할 LLM / 이미지 생성 API와 월 예산
- 혼자 쓰는 로컬 도구인지, 웹 서비스(여러 사용자)인지
- 주 판매 플랫폼과 카테고리 (식품·화장품은 표시광고 규정 문구 검토 필요)
- 노코드(n8n/Make + Figma) 방식 vs 코드(Python) 방식 — 이 문서는 코드 방식 기준

## 7. 주의사항
- 화장품·건강식품 등은 과장·의약품 오인 표현 금지 → 금지어 필터 단계 추가
- 경쟁사 이미지·문구는 그대로 쓰지 말고 참고만 (저작권)
- 폰트는 상업적 이용 가능한 무료 폰트 사용 (Pretendard, 나눔 계열 등)

---

### Codex에게 보낼 요청문 예시
```
첨부한 PLAN_detail_page_automation.md를 읽고,
1) 6번 결정사항 중 기본값을 제안하고,
2) M1~M4를 각각 1~2시간 단위 작업으로 쪼갠 구현 계획(파일별 변경 내용, 테스트 방법 포함)을 작성해줘.
먼저 M1(샘플 JSON → 860px JPG)부터 동작하는 걸 목표로 해.
```
