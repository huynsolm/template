# AGENTS.md

## 현재 작업
`CODEX_TASK_M2.md`의 M2를 구현한다. M1(`CODEX_TASK_M1.md`)은 완료됐으며 그 테스트는 계속 통과해야 한다. 전체 배경은 `PLAN_detail_page_automation.md`를 참고한다.

## 규칙
- LLM은 Anthropic Claude API(공식 Python SDK `anthropic`, 모델 `claude-opus-5-5`)만 사용한다.
- M3 이후 기능(배경 제거, UI, 크롤링, 다중 사용자)은 구현하지 않는다.
- 비용 상한의 실제 금액·플랫폼 규격을 임의로 확정하지 않는다. 설정 항목과 제안 기본값만 둔다.
- AI가 후기·별점·가격을 만들지 않는다.
- API 키를 파일·로그·manifest·커밋에 남기지 않는다.
- 자동 테스트는 실제 API를 호출하지 않는다(가짜 클라이언트 사용). 실제 호출은 `tools/live_check.py`로만 한다.
- 외부 이미지·폰트를 다운로드해 저장소에 넣지 않는다.
- 테스트를 건너뛰거나 비활성화해서 통과시키지 않는다. 실제 Chromium 렌더링 테스트를 포함한다.
- 작업이 끝나면 브랜치 `ccr-f9c07036-vgvm5j`에 커밋·푸시하고 `CODEX_TASK_M2.md`의 "완료 보고 형식"대로 보고한다.
