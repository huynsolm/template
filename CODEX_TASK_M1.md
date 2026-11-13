# Codex 작업 지시서 — M1: 샘플 JSON → HTML → 860px JPG

기준 문서: `PLAN_detail_page_automation.md` (이 지시서와 충돌하면 이 지시서가 우선)

## 범위
- **M1만 구현한다.** M2~M5(LLM, 배경 제거, UI, 크롤링)는 구현하지 않는다.
- AI 서비스·예산·플랫폼 규격을 임의로 확정하지 않는다.
- 외부 API·로그인·배포 없이 로컬에서 동작해야 한다.
- 코드는 저장소 루트 아래 `detail-page-auto/`에 둔다.

## 기술 스택 (계획서 기본안)
Python 3.12, Pydantic v2, Jinja2, Playwright(Chromium), Pillow, pytest. 의존성은 잠금 파일로 고정한다.

## 작업 목록

### 1. 프로젝트 준비
- [ ] `detail-page-auto/` 구조 생성 (계획서 5장 폴더 구조 중 M1에 필요한 부분: `core/`, `cli.py`, `templates/`, `assets/fonts/`, `samples/`, `tests/`, `README.md`)
- [ ] 의존성 정의 + 잠금 파일, Chromium 설치 방법을 README에 기록

### 2. 스키마 검증 — `core/schema.py`
- [ ] `schema_version`(지원: `"1.0"`), `product`, 섹션 9종(hero, pain, solution, features, how_to, review, spec, faq, notice)을 `type` 구분 Pydantic 모델로 정의
- [ ] 알 수 없는 타입·필드(`extra="forbid"`), 중복 `id`, 미지원 버전 → 오류
- [ ] `product.name/category/price` 비어 있지 않은 문자열, `brand_color`는 `#RRGGBB`
- [ ] 길이 제한: 섹션 1~20개, headline/title 1~80자, subcopy/desc 1~300자, body 1~2,000자, 목록 1~10개, FAQ q ≤200·a ≤1,000자, 리뷰 text ≤1,000자
- [ ] `hero` 정확히 1개, headline·image 필수
- [ ] `spec.rows`는 비어 있지 않은 문자열 2개 쌍, `rating`은 정수 1~5
- [ ] review 항목은 `source`와 `permission_confirmed: true`가 없으면 거부
- [ ] 이미지 필드: 생략은 허용(이미지 영역 생략), 빈 문자열은 오류
- [ ] 오류 메시지에 필드 경로와 원인 표시. 조용한 자동 보정 금지

### 3. 입력 검증 — `core/collect.py`
- [ ] 이미지는 지정 입력 디렉터리 하위의 PNG/JPEG만 허용, 경로 이탈·심볼릭 링크 차단
- [ ] 최대 5장, 장당 10MB·2,000만 픽셀 이하
- [ ] 필수 이미지 누락·손상 시 렌더링 전에 오류

### 4. 템플릿 — `templates/`, `assets/fonts/`
- [ ] 섹션 9종 Jinja2 템플릿 + 기본 테마 CSS 1개, 폭 860px 기준
- [ ] 상업적 이용 가능한 한글 폰트(예: Pretendard, SIL OFL)를 로컬에 포함하고 라이선스 파일 동봉
- [ ] Jinja2 autoescape 활성화, 사용자 문구의 HTML/스크립트 실행 금지

### 5. 렌더링·출력 — `core/render.py`
- [ ] Playwright Chromium, viewport 폭 860, device scale factor 1
- [ ] 촬영 중 외부 네트워크 요청 차단 (로컬 파일만 허용)
- [ ] `document.fonts.ready` + 모든 이미지 decode 완료 후 촬영, 타임아웃 시 명확한 오류
- [ ] 전체 높이 30,000px 초과 시 오류
- [ ] 섹션 경계 좌표를 DOM에서 읽어 분할. 최대 높이 기본 4,000px(설정 가능)
- [ ] **단일 섹션이 최대 높이보다 크면 오류를 반환한다** (M1 결정 사항. 임의 위치 분할 금지)
- [ ] JPG: sRGB, 품질 90, 파일명 `page-001.jpg`… PNG는 옵션
- [ ] 결과 폴더: `page.html`, 로컬 assets, 입력 JSON 사본, JPG들, `manifest.json`(파일 순서·각 크기·도구 버전·실행 시간)
- [ ] 실행마다 새 작업 폴더 생성, 기존 결과 덮어쓰기 금지

### 6. CLI·샘플
- [ ] `cli.py`: 입력 JSON, 이미지 디렉터리, 출력 디렉터리, 분할 높이, PNG 옵션 인자. 실패 시 0이 아닌 종료 코드 + 원인 메시지
- [ ] `samples/`: 필수 값이 모두 채워진 유효 샘플 JSON + 샘플 이미지. **샘플 이미지는 Pillow 등으로 직접 생성**한다(외부 이미지 다운로드 금지, 저작권 문제 방지)

### 7. 테스트 — `tests/`
- [ ] 스키마: 경계값, 알 수 없는 타입/필드, 중복 id, hero 0개/2개, 허가 없는 후기, 잘못된 색상
- [ ] 입력: 경로 이탈, 심볼릭 링크, 용량·픽셀 초과, 손상 이미지, 필수 이미지 누락
- [ ] 실제 Chromium 렌더링: 정상 입력, 긴 한글 문구, 선택 이미지 생략, 큰 섹션(오류), 30,000px 초과(오류)
- [ ] 출력: JPG를 다시 열어 폭 860px·순서·높이 합계 확인, 분할 전후 픽셀 영역 누락·중복 없음(JPG 손실 차이 허용)
- [ ] 결과 폴더를 다른 경로로 옮겨 네트워크 없이 `page.html` 재촬영 가능

## 완료 보고 형식
1. 실행한 설치·실행·테스트 명령과 결과(통과/실패 수)
2. 생성된 샘플 결과 폴더 경로와 manifest 내용
3. 한글 깨짐·가로 넘침·문구 잘림 육안 검수 결과(샘플 JPG 첨부)
4. 미해결 항목과 계획서와 다르게 구현한 부분(있다면 이유)
