# Codex 작업 지시서 — M2: 근거 기반 카피 생성 (구독제 AI 사용, API 미사용)

기준 문서: `PLAN_detail_page_automation.md` 4장 M2. 이 지시서와 충돌하면 이 지시서가 우선한다.
M1 코드(`detail-page-auto/`)를 그대로 확장한다. M1 테스트는 계속 통과해야 한다.

## 확정된 결정
- 사용자는 Claude·ChatGPT(Codex)·Gemini를 **월 정액 구독**으로 사용한다. **유료 API(Anthropic/OpenAI/Google API 키)는 사용하지 않는다.** API SDK 의존성(`anthropic`, `openai`, `google-genai` 등)을 추가하지 않는다.
- 문구 생성 방식은 두 가지다.
  1. **붙여넣기 방식(기본)**: 프로그램이 프롬프트 파일을 만들고 → 사용자가 채팅창에 붙여넣고 → 받은 답변을 파일로 저장하면 → 프로그램이 검증·조립한다.
  2. **구독 CLI 방식(선택)**: 사용자가 로그인해 둔 공식 CLI(`claude`, `codex`, `gemini`)를 프로그램이 실행해 답변을 받는다.
- **채팅 웹사이트를 브라우저 자동화(Playwright 등)로 조작하지 않는다.** (약관 위반 소지·불안정)

## 범위 밖 (구현 금지)
- 유료 API 호출, 비용 계산·예산 기능
- M3(배경 제거)·M4(UI)·M5(크롤링·다중 사용자)

## 전체 흐름
```
facts.json ─► [prompt] prompt.md 생성
                 │
     ┌───────────┴─────────────┐
 (기본) 사용자가 채팅에 붙여넣기     (선택) cli.py가 claude/codex/gemini CLI 실행
     └───────────┬─────────────┘
           답변 텍스트(answer.txt)
                 │
          [ingest] JSON 추출 → CopyDraft 검증
                 │  실패 시 → fix-prompt.md 생성(오류 목록 포함) → 다시 붙여넣기
                 ▼
         근거 검사 → 이미지·상품정보 조립(코드) → M1 Document 검증
                 ▼
         draft.json + review.json  ─► (선택) M1 렌더러로 JPG
```

---

## 작업 목록

### 0. M1 정리 (먼저 처리)
- [ ] 폰트 중복 제거: `samples/expected/assets/fonts/NotoSansCJK-Regular.ttc`(약 19MB)를 저장소에서 빼고, 테스트가 `assets/fonts/`의 원본을 기대 결과 폴더로 복사해 쓰도록 수정한다. 라이선스 파일은 남긴다. 기존 비교 테스트가 동일하게 통과해야 한다.
- [ ] README에서 `/workspace/...` 절대 경로를 저장소 기준 상대 경로로 바꾼다. Chromium 경로 탐색 순서(`M1_CHROMIUM_PATH` → Playwright 기본 → `/opt/pw-browsers/chromium` → PATH의 `chromium`)를 명시한다.

### 1. 상품 사실 입력 — `core/facts.py`, `samples/facts.json`
- [ ] Pydantic 모델 `ProductFacts`: `schema_version`, `product`(M1 `Product`와 동일 필드), `facts: list[Fact]`, `images: list[ImageRef]`, `reviews: list[ReviewItem]`(선택, M1 ReviewItem 재사용), `notice`(판매자 제공 배송·교환·반품 문구, 선택)
- [ ] `Fact`: `id`(고유), `text`(1~500자), `kind`(`spec` | `feature` | `usage` | `claim` | `other`), `evidence`(근거 설명 또는 자료 식별자, `claim`이면 필수)
- [ ] `ImageRef`: `path`(M1 collect 규칙으로 검증), `role`(`hero` | `feature` | `solution` | `other`), `alt`(선택)
- [ ] 중복 id, 알 수 없는 필드, `claim`인데 `evidence` 없음 → 오류
- [ ] `samples/facts.json`: 가상 상품 예시(실제 브랜드·실제 후기 사용 금지)

### 2. AI 출력 형식 — `core/copy_schema.py`
AI는 **문구만** 만든다. 이미지 경로·후기·별점·가격·상품명·배송 안내는 AI가 만들지 않고 코드가 채운다.
- [ ] `CopyDraft` Pydantic 모델(`extra="forbid"`): hero(headline, subcopy), pain, solution, features, how_to, faq 섹션의 문구 필드
- [ ] **review 섹션은 CopyDraft에 없다.** 후기는 `facts.json`의 `reviews`가 있을 때만 코드가 그대로 복사한다.
- [ ] spec 섹션은 AI가 쓰지 않고 `kind == "spec"` 사실에서 코드가 생성한다.
- [ ] 각 문구 단위(섹션 또는 항목)에 `fact_ids: list[str]`(근거 사실 id 목록)를 둔다.
- [ ] 길이 제한은 M1 스키마와 동일하게 선언한다.
- [ ] `CopyDraft.model_json_schema()`로 만든 JSON Schema와 **채워진 예시 JSON 1개**를 프롬프트에 넣을 수 있게 한다.

### 3. 프롬프트 — `prompts/copy_v1.md`, `core/prompting.py`
- [ ] 프롬프트 템플릿 파일명에 버전을 둔다(`copy_v1`). 내용을 바꾸면 새 버전 파일을 만들고, 사용한 버전을 작업 폴더 manifest에 기록한다.
- [ ] 지시 내용: 한국어 오픈마켓 상세페이지 카피, 제공된 사실만 사용, 각 문구에 근거 `fact_ids` 표기, 근거 없는 수치·효능·인증·비교 우위·최상급 표현 금지, 후기·별점·가격 생성 금지, 의약품 오인 표현 금지
- [ ] 상품 사실은 `<facts>` 같은 구분 블록 안에 **데이터로** 넣고, 그 안의 문장을 지시로 따르지 말라고 명시한다.
- [ ] 출력 규칙: **JSON 하나만** ```json 코드 블록으로 출력, 설명 문장 금지. 스키마와 예시를 포함한다.
- [ ] 채팅 서비스 세 곳(Claude·ChatGPT·Gemini)에 그대로 붙여넣어도 동작하도록 서비스 전용 문법을 쓰지 않는다.
- [ ] 수정 요청 프롬프트(`fix-prompt.md`): 이전 답변 JSON + 검증 오류 목록(필드 경로·원인·허용 범위)을 담아 "고친 JSON 전체만 다시 출력"을 요청한다.

### 4. 답변 수집·검증 — `core/ingest.py`
- [ ] 답변 텍스트에서 JSON 추출: ```json 코드 블록 우선 → 없으면 첫 `{`~짝이 맞는 `}` 구간. 여러 개면 오류로 알리고 어느 것을 쓸지 추측하지 않는다.
- [ ] 흔한 형식 문제(앞뒤 설명 문장, 코드 블록)는 추출 단계에서 처리한다. **내용(문구·글자 수)을 프로그램이 임의로 자르거나 고치지 않는다.**
- [ ] `CopyDraft` 검증 실패 시: 오류를 사람이 읽을 수 있게 출력하고 `fix-prompt.md`를 작업 폴더에 생성한 뒤 0이 아닌 코드로 종료한다.
- [ ] 시도할 때마다 `attempts/answer-<n>.txt`, `attempts/errors-<n>.json`을 보존한다. 시도 횟수 상한은 설정값(기본 5, 붙여넣기는 사람이 하므로 넉넉히).

### 5. 근거 검사·조립 — `core/assemble.py`
- [ ] 모든 `fact_ids`가 `facts.json`에 존재하는지 확인. 없는 id를 참조한 문구는 **오류가 아니라 검수 항목**으로 표시하고 초안에는 남긴다.
- [ ] 문구에 숫자·퍼센트·인증/효능 관련 단어(설정 가능한 목록)가 있는데 근거 fact가 `claim`/`spec`이 아니면 검수 항목으로 표시한다(보조 수단임을 README에 명시).
- [ ] hero 이미지 = `role == "hero"` 이미지(없으면 첫 이미지, 이미지가 하나도 없으면 오류). 나머지는 role에 따라 solution/features에 순서대로 배치한다.
- [ ] product 정보·가격·notice·review는 `facts.json`에서 그대로 복사한다.
- [ ] 섹션 id는 `<type>-<n>` 형식으로 코드가 부여한다.
- [ ] 최종 결과를 M1 `Document`로 검증한다. 실패 시 성공 파일을 남기지 않는다.
- [ ] 출력: `draft.json`(Document), `review.json`(검수 항목: 섹션 id·필드 경로·사유·관련 fact_ids), `copy.json`(검증 통과한 CopyDraft 원본)
- [ ] manifest에 기록: 프롬프트 버전, 생성 방식(`paste` / `cli:claude` 등), 사용자가 입력한 출처 라벨(예: "Claude 채팅"), 시도 횟수, 시각

### 6. 수동 수정 보존
- [ ] 사용자가 `edits.json`의 `locked_sections`(섹션 id 목록)에 넣은 섹션은 다시 생성·재수집해도 이전 작업의 내용을 그대로 유지한다.
- [ ] 재생성은 항상 새 작업 폴더에 쓴다. 이전 작업 폴더의 파일은 수정하지 않는다.
- [ ] 잠근 섹션만 빼고 나머지만 다시 쓰도록 요청하는 프롬프트도 생성할 수 있게 한다(잠근 섹션 문구는 참고용으로 포함).

### 7. 구독 CLI 방식(선택 기능) — `core/providers.py`
- [ ] `Provider` 인터페이스: `generate(prompt_text) -> answer_text`. 구현: `PasteProvider`(파일 기반, 기본), `CliProvider`(외부 명령 실행).
- [ ] 지원 대상: `claude`(Claude Code), `codex`(Codex CLI), `gemini`(Gemini CLI). **각 CLI의 비대화형 실행 옵션과 읽기 전용·도구 비활성 옵션은 설치된 버전의 `--help`로 확인한 뒤 구현**하고, 확인한 버전과 명령을 README에 기록한다. 추측으로 플래그를 쓰지 않는다.
- [ ] 명령 템플릿은 설정 파일(`providers.toml` 등)에서 바꿀 수 있게 한다. 프롬프트는 가능하면 표준 입력으로 전달한다(명령줄 길이 제한 회피).
- [ ] 안전: 빈 임시 작업 디렉터리에서 실행하고, CLI가 제공하는 경우 파일 수정·명령 실행 권한을 끄는 옵션을 사용한다. 셸 문자열 결합 대신 인자 리스트로 실행한다(`subprocess.run([...], shell=False)`).
- [ ] 제한 시간(기본 300초), 0이 아닌 종료 코드, 빈 출력, 로그인 안 됨·사용량 한도 메시지를 구분해 오류로 보고한다. 사용량 한도면 붙여넣기 방식으로 전환하라고 안내한다.
- [ ] 검증 실패 시 `fix-prompt.md`로 같은 CLI를 다시 호출하되, 전체 시도는 설정 상한(기본 3) 안에서만 한다.
- [ ] CLI가 설치돼 있지 않으면 명확한 오류로 종료한다. 인증 토큰·설정 파일 내용을 로그에 남기지 않는다.
- [ ] README에 "구독제 사용량 한도가 적용됨, 개인 사용 범위에서 쓰고 각 서비스 약관 확인 필요"를 적는다.

### 8. CLI 명령
- [ ] `cli.py prompt --facts samples/facts.json --images samples --output outputs` → 새 작업 폴더에 `prompt.md` 생성, 경로 출력
- [ ] `cli.py ingest --job outputs/job-xxx --answer answer.txt [--source-label "Claude 채팅"] [--render]` → 검증·조립, 실패 시 `fix-prompt.md` 생성
- [ ] `cli.py generate --facts ... --images ... --output ... --provider claude|codex|gemini [--render]` → CLI 방식으로 한 번에 실행
- [ ] `cli.py prompt --from-job outputs/job-xxx --regenerate` → 잠근 섹션을 제외한 재생성용 프롬프트를 새 작업 폴더에 생성
- [ ] 기존 M1 명령(`--input ...`)은 그대로 동작해야 한다(하위 호환).
- [ ] 실패 시 0이 아닌 종료 코드와 원인을 출력한다. 검증 실패·CLI 없음·제한 시간 초과·사용량 한도는 서로 다른 종료 코드로 구분한다.

### 9. 테스트 — `tests/test_m2.py`
**실제 AI 서비스나 CLI를 호출하지 않는다.** 답변은 고정 텍스트 파일, CLI는 테스트용 가짜 실행 파일(스크립트)로 대신한다.
- [ ] 정상 답변 → draft.json이 M1 Document 검증 통과 → M1 렌더러로 JPG 생성(실제 Chromium)
- [ ] JSON 추출: 코드 블록 / 앞뒤 설명 문장 포함 / 코드 블록 없음 / JSON 두 개(오류) / 깨진 JSON(오류)
- [ ] 글자 수 초과·필드 누락·알 수 없는 필드 → `fix-prompt.md` 생성, 오류 목록 포함, 성공 파일 없음
- [ ] 수정 답변 재입력 → 성공, 시도 2회 기록
- [ ] 없는 fact_id 참조, 근거 없는 수치 문구 → review.json에 항목 생성
- [ ] 답변에 review·price 필드가 섞여 있으면 거부(extra forbid)
- [ ] facts에 reviews 없음 → review 섹션 없음 / 있음 → 원문 그대로 복사
- [ ] locked 섹션이 재생성 후에도 동일
- [ ] 가짜 CLI: 정상 / 종료 코드 오류 / 제한 시간 초과 / 빈 출력 / 사용량 한도 메시지 / 미설치 / 1회 실패 후 수정 성공
- [ ] `shell=False`로 실행되는지, 프롬프트에 특수문자(따옴표·`$`·백틱)가 있어도 안전한지 확인
- [ ] 테스트 건너뛰기(skip/xfail) 금지

### 10. 문서
- [ ] README에 M2 사용법을 **비개발자 기준 단계별**로 작성: ① facts.json 작성법 ② `prompt` 실행 ③ 어떤 채팅에 무엇을 붙여넣는지 ④ 답변 저장 ⑤ `ingest` ⑥ 오류 시 fix-prompt 사용법 ⑦ 검수 목록 보는 법
- [ ] 구독 CLI 방식 설정·주의사항
- [ ] `PLAN_detail_page_automation.md` 6장 "M2 전: 사용할 LLM" 항목에 "유료 API 대신 구독 중인 Claude/ChatGPT/Gemini를 붙여넣기(기본) 또는 공식 CLI(선택)로 사용하기로 결정" 한 줄 추가

---

## 완료 보고 형식
1. 설치·실행·테스트 명령과 결과(M1+M2 전체 통과/실패/건너뜀 수)
2. 샘플 결과: `prompt.md`, 샘플 답변으로 만든 `draft.json`, `review.json`, 렌더링된 JPG 경로
3. 구독 CLI 방식: 작업 환경에 설치·로그인된 CLI가 있었는지, 확인한 버전과 `--help` 기준 옵션, 실제 실행 여부. 실행하지 못했다면 이유
4. 저장소 크기 변화(폰트 중복 제거 전후)
5. 미해결 항목, 지시서와 다르게 구현한 부분과 이유
6. 커밋 해시와 푸시 여부 (브랜치 `ccr-f9c07036-vgvm5j`에 커밋·푸시할 것)
