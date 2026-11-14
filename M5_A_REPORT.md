# M5-A 대비 정책 수정 완료 보고

이 보고서는 8cac895의 초기 완료 보고와 이전 "classic도 보정" 설계를 대체하는 사용자 확정 기준에 대한 결과다. M5-B는 이 수정에 포함하지 않는다.

## 1. 구현 여부와 커밋

완료. 수정 커밋 해시와 푸시 결과는 최종 응답에 기록한다. 설계·계획·AGENTS·작업 지시서·인계서·README에도 동일한 확정 기준을 반영한다.

- classic: `contrast_policy = "legacy"`. 브랜드 색을 자동 변경하지 않는다. M5 이전 원본 HTML·DOM·CSS를 출력하고 모든 색의 렌더링을 유지한다.
- classic 저대비: `BRAND_COLOR_LOW_CONTRAST` 경고를 manifest의 `contrast_reviews`와 `review.json`에 기록한다. `contrast_adjustments`는 비어 있다.
- minimal/bold: `contrast_policy = "aa"`. 본문·제목 등 글자색만 보정한다. 장식용 `--brand-original`, 글자용 `--brand-text`를 분리해 blockquote 테두리와 bold 브랜드 배경을 원래 색으로 유지한다.
- 작업·렌더링·ZIP manifest는 `contrast_policy`, 실제 색 `resolved_colors`, 보정 이력 `contrast_adjustments`, 대비 경고 `contrast_reviews`를 공통 기록한다. 승인 결과에도 기록한다.
- 이전 정책 스냅샷은 보존한다. 정책이 없거나 달라진 결과는 현재 미리보기·ZIP에 재사용하지 않는다. 새 정책으로 미리보기를 만들면 이전 승인 포인터를 해제한다.

## 2. 명령과 테스트

- 실패 재현: classic 원본 HTML/픽셀·정책 전파 12개 실패, 이전 정책 스냅샷 재사용 2개 실패를 확인한 뒤 구현했다.
- 대상 검증: `.venv/bin/python -m pytest tests/test_themes.py tests/test_app.py::test_theme_change_preserves_snapshot_and_uses_selected_theme -q` → 63 passed.
- 독립 리뷰의 실패 ingest/테마 변경 메타데이터 불일치: 회귀 2 failed → 수정 후 2 passed.
- 이전 승인 정책 포인터: 회귀 1 failed → 수정 후 1 passed.
- 최종 전체 검증: `.venv/bin/python -m pytest -q` → 278 passed, 0 failed, 0 skipped (634.18s).
- 실제 DOM 검사에서 본문은 글자 크기와 관계없이 4.5:1, 큰 제목은 3:1을 검사한다. minimal/bold 각각 #FFFF00 / #000000 / #777777 / #c7b195를 검사한다. 같은 DOM에서 blockquote 테두리와 bold 홀수 섹션 배경이 입력 색과 같은지 확인한다.
- classic #305b46 / #234567 / #c7b195 / #FFFF00의 HTML·CSS를 b2cdcad 원본 fixture와 비교하고, 동일 Chromium에서 전체 픽셀을 비교한다. 저대비 두 색은 색 미변경과 경고 발생도 검사한다. 기존 M1 기대 결과 비교를 유지한다.
- `git diff --check` 통과. 최종 pytest 전후 Git 대상 파일 SHA-256와 `git status --porcelain=v1`가 동일함을 확인했다. 커밋 후 status는 최종 응답에 보고한다.
- 최종 검증은 소스 변경 없이 처음부터 끝까지 실행했다. 추가 승인 포인터 회귀 수정 전 중간 실행은 최종 통과 근거로 사용하지 않는다.

## 3. 결과 예시와 캡처

| 테마 | 입력 색 | 글자 강조색 | 정책 | 경고 |
|---|---|---|---|---|
| classic | #c7b195 | #c7b195 (유지) | legacy | BRAND_COLOR_LOW_CONTRAST |
| classic | #FFFF00 | #FFFF00 (유지) | legacy | BRAND_COLOR_LOW_CONTRAST |
| minimal | #c7b195 / #FFFF00 | #000000 | aa | 없음 |
| bold | #c7b195 / #FFFF00 | #000000 | aa | 없음 |

AA 모드에서도 장식·브랜드 배경은 입력 색 그대로다. 성공한 보정은 검수 항목이 아니며 기존 "브랜드 색 대비 보정됨" 안내만 표시한다. classic에는 그 안내를 표시하지 않는다.

캡처 도구 재실행: `.venv/bin/python tools/make_screenshots.py --themes-only`.

- `detail-page-auto/docs/images/theme-classic.png`
- `detail-page-auto/docs/images/theme-minimal.png`
- `detail-page-auto/docs/images/theme-bold.png`

기존 샘플 #305b46의 세 테마 캡처 픽셀은 바뀌지 않는다. 저대비 classic의 원본 비교는 실제 Chromium 회귀 테스트가 검증한다.

## 4. 미해결 항목·차이

기능상 미해결 항목이나 확정 기준과 다른 구현은 없다. 독립 리뷰에서 발견한 실패 답변의 테마/정책 불일치를 수정했으며, 추가로 옛 승인 포인터의 정책 전환도 검증했다. 외부 서비스·네트워크·실제 AI CLI·배경 제거 모델은 테스트에서 호출하지 않는다.

## 5. 푸시

대상: `ccr-f9c07036-vgvm5j`. 최종 응답에 커밋 해시·원격 일치·푸시 결과를 기록한다.
