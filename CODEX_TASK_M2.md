# Codex 작업 지시서 — M2: 근거 기반 카피 생성 (Claude API)

기준 문서: `PLAN_detail_page_automation.md` 4장 M2. 이 지시서와 충돌하면 이 지시서가 우선한다.
M1 코드(`detail-page-auto/`)를 그대로 확장한다. M1 테스트 43개는 계속 통과해야 한다.

## 확정된 결정
- **LLM: Anthropic Claude API, 공식 Python SDK `anthropic`** (OpenAI 호환 래퍼·raw HTTP 사용 금지)
- **모델: `claude-opus-5-5`** (날짜 접미사 붙이지 말 것). 설정으로 바꿀 수 있게 하되 기본값은 이 값.
- 인증: SDK 기본 자격 증명 해석(`ANTHROPIC_API_KEY` 환경 변수 등). 키를 파일·로그·manifest에 저장하지 않는다.

## 아직 정하지 않은 것 (임의 확정 금지)
- 작업당·월간 비용 상한의 **실제 금액**. 설정 항목으로만 만들고, 기본값은 아래 "제안값"을 쓰되 README에 "사용자 확인 필요"로 표시한다.
- M3(배경 제거)·M4(UI)·M5 기능은 구현하지 않는다.

## 범위
입력: 상품 사실 파일(`facts.json`) + 로컬 이미지 디렉터리
출력: M1 스키마(`core/schema.py`의 `Document`)를 통과하는 **초안 JSON** + 검수 목록 → 기존 M1 렌더러로 JPG까지 생성 가능

```
facts.json ──► copywriter (Claude, 구조화 출력) ──► CopyDraft 검증 ──► 근거 검사
          ──► 이미지·hero 배치(코드) ──► Document 검증(M1 스키마) ──► draft.json + review.json
          ──► (선택) M1 render
```

---

## 작업 목록

### 0. M1 정리 (먼저 처리)
- [ ] 폰트 중복 제거: `samples/expected/assets/fonts/NotoSansCJK-Regular.ttc`(약 19MB)를 저장소에서 빼고, 테스트가 `assets/fonts/`의 원본을 기대 결과 폴더로 복사해 사용하도록 수정한다. 라이선스 파일은 남긴다. 기존 비교 테스트가 동일하게 통과해야 한다.
- [ ] README에서 `/workspace/...` 절대 경로를 저장소 기준 상대 경로로 바꾼다. Chromium 경로 탐색 순서에 `M1_CHROMIUM_PATH` → Playwright 기본 → `/opt/pw-browsers/chromium` → PATH의 `chromium`을 명시한다.

### 1. 상품 사실 입력 — `core/facts.py`, `samples/facts.json`
- [ ] Pydantic 모델 `ProductFacts`: `schema_version`, `product`(M1 `Product`와 동일 필드), `facts: list[Fact]`, `images: list[ImageRef]`, `reviews: list[ReviewItem]`(선택, M1 ReviewItem 재사용), `notice`(판매자 제공 배송·교환·반품 문구, 선택)
- [ ] `Fact`: `id`(고유), `text`(1~500자), `kind`(`spec` | `feature` | `usage` | `claim` | `other`), `evidence`(근거 설명 또는 자료 식별자, `claim`이면 필수)
- [ ] `ImageRef`: `path`(M1 collect 규칙으로 검증), `role`(`hero` | `feature` | `solution` | `other`), `alt`(선택)
- [ ] 중복 id, 알 수 없는 필드, `claim`인데 `evidence` 없음 → 오류
- [ ] `samples/facts.json`: 가상 상품 예시(실제 브랜드·실제 후기 사용 금지)

### 2. LLM 출력 스키마 — `core/copy_schema.py`
LLM은 **문구만** 만든다. 이미지 경로·후기·별점·가격·상품명은 LLM이 만들지 않고 코드가 채운다.
- [ ] `CopyDraft` Pydantic 모델: hero(headline, subcopy), pain, solution, features, how_to, spec, faq 섹션의 문구 필드
- [ ] **review 섹션은 CopyDraft에 없다.** 후기는 `facts.json`의 `reviews`가 있을 때만 코드가 그대로 복사한다.
- [ ] 각 문구 단위(섹션 또는 항목)에 `fact_ids: list[str]`를 둔다. 해당 문구가 근거로 삼은 사실 id 목록이다.
- [ ] spec 행은 LLM이 쓰지 않고 `kind == "spec"` 사실에서 코드가 생성하는 방식을 우선 검토한다. LLM에 맡길 경우 각 행의 `fact_ids` 필수.
- [ ] 길이 제한은 M1 스키마와 동일하게 Pydantic에 선언한다. (API 구조화 출력은 `minLength`/`maxLength`·숫자 범위를 지원하지 않으며, SDK가 이를 요청 스키마에서 제거하고 응답을 클라이언트 측에서 검증한다. 따라서 검증 실패는 정상적으로 발생할 수 있는 경로로 처리한다.)
- [ ] 모든 객체는 `extra="forbid"`(구조화 출력은 `additionalProperties: false` 필수). 재귀 스키마 금지.

### 3. 프롬프트 — `prompts/copy_v1.md`
- [ ] 파일 이름의 버전(`copy_v1`)을 manifest에 기록한다. 내용을 바꾸면 새 버전 파일을 만든다.
- [ ] 지시 내용: 한국어 오픈마켓 상세페이지 카피, 제공된 사실만 사용, 각 문구에 근거 `fact_ids` 표기, 근거 없는 수치·효능·인증·비교 우위·최상급 표현 금지, 후기·별점·가격 생성 금지, 의약품 오인 표현 금지
- [ ] 상품 사실은 시스템 프롬프트가 아니라 사용자 메시지에 **데이터로** 넣는다(사실 텍스트 안의 지시문을 따르지 않도록 명시). 시스템 프롬프트는 고정 문자열로 두어 프롬프트 캐싱이 가능하게 한다.

### 4. Claude 호출 — `core/copywriter.py`
SDK 사용법(이 형태를 따를 것):
```python
import anthropic
client = anthropic.Anthropic(timeout=60.0, max_retries=0)   # 재시도는 직접 제어
resp = client.messages.parse(
    model=cfg.model,                      # 기본 "claude-opus-5-5"
    max_tokens=cfg.max_output_tokens,     # 제안 16000
    output_config={"effort": cfg.effort}, # 제안 "medium" (이 모델의 기본값이지만 명시)
    system=SYSTEM_PROMPT,
    messages=[{"role": "user", "content": facts_payload}],
    output_format=CopyDraft,
)
draft = resp.parsed_output
```
- [ ] **이 모델에서 금지된 파라미터를 보내지 않는다**: `thinking={"type":"disabled"}`, `budget_tokens`, `temperature`/`top_p`/`top_k`, assistant prefill, `tool_choice` `any`/`tool` → 모두 400 오류.
- [ ] `stop_reason` 확인 후 결과 사용: `refusal`이면 `stop_details.category`를 기록하고 중단(재시도 예산 소진 안 함, 사용자에게 보고), `max_tokens`면 출력 불완전으로 처리
- [ ] 거절 시 서버 측 대체 모델(`fallbacks`)은 **기본 비활성**으로 두고 설정 플래그만 만든다. 켜면 `client.beta.messages` + `betas=["server-side-fallback-2026-07-01"]` + `fallbacks="default"`를 사용하며, 실제 응답한 모델(`response.model`)을 manifest에 기록한다.
- [ ] 재시도 정책(계획서 M2): 요청당 60초, **최초 호출 포함 최대 3회**
  - `anthropic.RateLimitError`(429): `retry-after` 헤더를 따르고 없으면 지수 백오프 + 지터
  - `APIStatusError` 5xx, `APIConnectionError`, `APITimeoutError`: 지수 백오프 후 재시도
  - `AuthenticationError`, `PermissionDeniedError`, `BadRequestError`, `NotFoundError`: 즉시 중단
  - 구조화 출력 검증 실패: 오류 내용을 담아 1회 보정 요청, **같은 3회 예산에 포함**
  - 예외는 구체적인 클래스부터 순서대로 잡는다(`APIStatusError` 하나로 뭉뚱그리지 말 것)
- [ ] 비용 상한
  - 호출 전 `client.messages.count_tokens(...)`로 입력 토큰을 구하고, `최악 비용 = 입력토큰×입력단가 + max_tokens×출력단가`를 계산한다.
  - 단가는 설정값으로 둔다. 기본값: `claude-opus-5-5` 입력 $4.00 / 출력 $20.00 (100만 토큰당). README에 "가격은 변경될 수 있으니 공식 가격표 확인" 명시.
  - 누적 실제 비용(응답의 `usage.input_tokens`, `output_tokens`, 캐시 토큰 포함) + 다음 호출의 최악 비용이 **작업당 상한**을 넘으면 호출하지 않고 중단한다.
  - 제안 기본값: 작업당 $1.00, 월간 상한은 설정 항목만 만들고 기본 미설정 시 CLI가 경고 후 진행(사용자 확인 필요로 README에 표시). 월간 누적은 로컬 파일(`outputs/usage-ledger.jsonl`)에 기록한다.
- [ ] 로그: 작업 폴더에 `llm/attempt-<n>.json`(요청 요약·프롬프트 버전·모델·`_request_id`·stop_reason·usage·검증 오류·소요 시간). API 키·인증 헤더는 절대 기록하지 않는다.

### 5. 근거 검사·조립 — `core/assemble.py`
- [ ] 모든 `fact_ids`가 `facts.json`에 존재하는지 확인. 없는 id를 참조한 문구는 **오류가 아니라 검수 항목**으로 표시하고 초안에는 남긴다.
- [ ] 문구에 숫자·퍼센트·인증/효능 관련 단어(설정 가능한 목록)가 있는데 근거 fact가 `claim`/`spec`이 아니면 검수 항목으로 표시 (보조 수단임을 README에 명시)
- [ ] hero 이미지 = `role == "hero"` 이미지(없으면 첫 이미지, 이미지가 하나도 없으면 오류). 나머지는 role에 따라 solution/features에 순서대로 배치.
- [ ] product 정보·가격·notice·review는 `facts.json`에서 그대로 복사(LLM 출력 사용 금지)
- [ ] 섹션 id는 `<type>-<n>` 형식으로 코드가 부여
- [ ] 최종 결과를 M1 `Document`로 검증. 실패 시 성공 파일을 남기지 않는다.
- [ ] 출력: `draft.json`(Document), `review.json`(검수 항목: 섹션 id·필드 경로·사유·관련 fact_ids), `copy_raw.json`(LLM 원본 CopyDraft)

### 6. 수동 수정 보존
- [ ] `draft.json`을 사람이 수정한 뒤 `--regenerate` 실행 시, 사용자가 `locked_sections`(섹션 id 목록, `edits.json`)에 넣은 섹션은 다시 생성하지 않고 그대로 유지한다.
- [ ] 재생성은 항상 새 작업 폴더에 쓴다. 이전 작업 폴더의 파일은 수정하지 않는다.

### 7. CLI
- [ ] `cli.py generate --facts samples/facts.json --images samples --output outputs [--render] [--max-cost-usd 1.0] [--model claude-opus-5-5] [--effort medium]`
- [ ] `cli.py generate --from-job outputs/job-xxx --regenerate`
- [ ] `--render`면 M1 렌더러로 JPG까지 생성
- [ ] `--dry-run`: API 호출 없이 프롬프트·토큰 수·최악 비용만 출력
- [ ] 기존 M1 명령(`--input ...`)은 그대로 동작해야 한다(하위 호환).
- [ ] 실패 시 0이 아닌 종료 코드 + 원인. 거절·예산 초과·인증 실패는 서로 다른 종료 코드.

### 8. 테스트 — `tests/test_m2.py`
**실제 API를 호출하지 않는다.** `copywriter`가 클라이언트 객체를 주입받도록 만들고 가짜 클라이언트로 테스트한다.
- [ ] 정상 응답 → draft.json이 M1 Document 검증 통과 → M1 렌더러로 JPG 생성(실제 Chromium)
- [ ] 스키마 검증 실패 1회 → 보정 요청 → 성공 (시도 2회 기록)
- [ ] 검증 실패가 3회 연속 → 실패 종료, 성공 파일 없음
- [ ] 타임아웃·5xx 후 성공, 429 + `retry-after` 준수(sleep 함수 주입으로 대기 시간 검증)
- [ ] 인증 실패 → 즉시 중단, 시도 1회
- [ ] `refusal` → 중단, category 기록
- [ ] `max_tokens` 중단 → 불완전 출력 처리
- [ ] 예산: 최악 비용이 상한 초과 → 호출 0회로 중단
- [ ] 없는 fact_id 참조, 근거 없는 수치 문구 → review.json에 항목 생성
- [ ] facts에 reviews 없음 → review 섹션 없음 / 있음 → 원문 그대로 복사, LLM 출력에는 후기 필드 자체가 없음
- [ ] locked 섹션이 재생성 후에도 동일
- [ ] 로그·manifest에 API 키 문자열이 없는지 검사
- [ ] 테스트 건너뛰기(skip/xfail) 금지

### 9. 실제 API 확인 스크립트 — `tools/live_check.py`
- [ ] pytest에 넣지 않는 별도 스크립트. `samples/facts.json`으로 실제 1회 생성 → draft·review·JPG·사용량·실제 비용을 출력
- [ ] 실행 전 최악 비용을 출력하고 `--yes` 없이는 호출하지 않는다.
- [ ] 키가 없거나 네트워크가 막혀 있으면 그 사실을 명확히 출력하고 종료(실패를 성공으로 보고하지 않음)

### 10. 문서
- [ ] README에 M2 설치(`anthropic` 의존성 잠금 갱신), 환경 변수, 명령, 비용 설정, 검수 흐름, "가격·한도는 사용자 확인 필요" 기록
- [ ] `PLAN_detail_page_automation.md` 6장의 "M2 전: 사용할 LLM"에 "Claude API(`claude-opus-5-5`)로 결정" 한 줄 추가

---

## 완료 보고 형식
1. 설치·실행·테스트 명령과 결과(M1+M2 전체 통과/실패/건너뜀 수)
2. 가짜 클라이언트로 생성한 샘플 결과: `draft.json`, `review.json`, 렌더링된 JPG 경로
3. `tools/live_check.py` 실행 여부. 실행했다면 모델·토큰 사용량·실제 비용·소요 시간·생성 문구 품질에 대한 의견. 실행하지 못했다면 이유(키 없음/네트워크 차단 등)
4. 저장소 크기 변화(폰트 중복 제거 전후)
5. 미해결 항목, 지시서와 다르게 구현한 부분과 이유
6. 커밋 해시와 푸시 여부 (브랜치 `ccr-f9c07036-vgvm5j`에 커밋·푸시할 것)
