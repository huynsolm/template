# M5-B 완료 보고 — 플랫폼 내보내기 프로필

## 1. 구현 여부와 커밋

완료. 작업 시작 시 원격에 선행 구현 `251f0c0`이 이미 있어 fast-forward로 받았다. 중복 구현하지 않고 M5-B 요구사항을 대조한 뒤 발견한 결함을 회귀 테스트로 재현·수정했다. 선행 구현의 기반은 M5-A 확정본 `d080b14`이다. 이번 보완 커밋 해시는 최종 응답에 기록한다.

- `profiles/{generic,smartstore,coupang}.toml`, 사용자 프로필 `profiles/user/*.toml`(Git 제외, `DETAIL_PAGE_USER_PROFILES`로 경로 설정 가능).
- `core/export.py`: 엄격한 Profile 검증, 프로필 저장·목록, 비율 유지 리사이즈, 섹션 경계 우선 분할, 용량·장수·형식 검사, 품질 하향, ZIP.
- ⑦ 다운로드: 프로필 선택 → 검사 결과 → 프로필별 ZIP, 사용자 프로필 생성.
- CLI: `cli.py export --job JOB --profile ID [--format jpg|png] [--output DIR]`.
- 미확인 프로필은 결과를 만들되 화면·manifest 경고와 ZIP `.UNVERIFIED`를 유지한다.

검증 중 보완한 사항:

1. ZIP 최상위 manifest의 `pages`, `width`, `height`, `max_height`, `sections`를 실제 변환·분할 파일과 맞췄다. 원본 렌더링 metadata는 `source_render`로 보존한다. HTML/assets는 원본 렌더링 자료다.
2. 회색조 변환·오차 12 이내 판정은 흐린 글자나 같은 휘도의 다른 RGB 글자를 자를 수 있었다. RGB 모든 채널이 정확히 균일한 빈 행에서만 섹션 내부를 분할하도록 수정했다. 빈 행이 없으면 오류다.
3. CLI 내보내기에서 승인본도 현재 문구·테마·대비 정책에 맞는지 확인한다. 오래된 승인본을 우회 선택하지 않는다.
4. 같은 ID의 사용자 프로필을 덮어쓰면 기존 검사 결과와 다운로드 캐시를 지우고 재검사를 요구한다.

## 2. 실행 명령과 전체 테스트

```bash
git fetch origin ccr-f9c07036-vgvm5j
git merge --ff-only origin/ccr-f9c07036-vgvm5j
cd detail-page-auto
.venv/bin/python -m pytest tests/test_export_regressions.py tests/test_app.py::test_overwriting_export_profile_invalidates_visible_zip -q
.venv/bin/python -m pytest tests/test_export.py -q
.venv/bin/python -m pytest -q
git diff --check
git status --porcelain=v1
```

- 보완 회귀: 8 failed로 결함을 확인한 뒤 수정 → **8 passed**.
- 기존 내보내기: **38 passed**.
- 최종 전체 테스트: **325 passed, 0 failed, 0 skipped (683.97s)**. M5-A 및 실제 Chromium 테스트를 포함한다.
- 최종 pytest 전후 Git 대상 파일 SHA-256와 status가 동일함을 확인했다. 커밋 후 깨끗한 status와 원격 해시 일치는 최종 응답에 보고한다.
- 선행 작성자의 317 passed 기록은 `251f0c0`에 있다. 이번 최종 결과는 소스 변경 없이 별도로 끝까지 실행한 결과이며, 수정 전에 시작한 중간 실행은 최종 근거로 사용하지 않는다.

## 3. 프로필별 결과 예시와 공식 출처

로컬 샘플 상품으로 실제 프롬프트 작업·답변 수집·미리보기를 만든 뒤 내보냈다.

| 프로필 | 결과 | 실제 출력 | ZIP 표시 |
|---|---|---|---|
| generic | 경고: PROFILE_UNVERIFIED, 용량·장수 값 없음 | 860×2590, JPG 1장 | generic.DRAFT.UNVERIFIED.zip |
| smartstore | 경고: PROFILE_UNVERIFIED, 폭 외 규격 값 비어 기본값 사용/미검사 (6장 보완 후 폭 848px 적용) | 보완 전 860×2590, JPG 1장 | smartstore.DRAFT.UNVERIFIED.zip |
| coupang | 경고: PROFILE_UNVERIFIED, 규격 값 비어 기본값 사용/미검사 | 860×2590, JPG 1장 | coupang.DRAFT.UNVERIFIED.zip |

위 표는 6장 보완 전 결과다. coupang의 출력 크기는 판매처 규격이 아니라 도구 기본값이다. smartstore는 6장 보완으로 폭만 공식 권장값 848px을 쓰고 나머지는 도구 기본값이다. 결과물 예시는 `detail-page-auto/outputs/m5-b-check/`에 있으며 outputs는 커밋하지 않는다.

| 판매처 | 공식 규격 출처 URL | 규격 확인 날짜 | 결론 |
|---|---|---|---|
| smartstore | https://help.sell.smartstore.naver.com/faq/content.help?faqId=3923 (검토자 확인, 6장) | 2026-11-15 | 권장 폭 848px만 반영, 나머지 **사용자 확인 필요**, `unverified` 유지 |
| coupang | 미확인, 필드 비움 | 비움 | **사용자 확인 필요** |

2026-11-15(KST) 공식 사이트를 직접 열려고 시도했으나 이 환경의 연결 터널에서 모두 403으로 차단됐다. 따라서 문서의 규격을 직접 확인하지 못했고 어떤 값도 채우지 않았다. 블로그·커뮤니티를 근거로 쓰지 않았다.

- 스마트스토어 공식 도움말 접속 시도: https://help.sell.smartstore.naver.com/
- 쿠팡 판매자 도움말 접속 시도: https://helpseller.coupang.com/
- 쿠팡 판매자 사이트 접속 시도: https://wing.coupang.com/ , https://marketplace.coupang.com/

이 주소들은 접속 시도 기록이며 규격을 확인한 출처 URL로 프로필에 기록한 것이 아니다.

오류 예시는 가짜 프로필 테스트로 확인했다: 최솟값에서도 용량 초과 → FILE_TOO_LARGE, 장수 초과 → TOO_MANY_IMAGES, 형식 불일치 → FORMAT_NOT_ALLOWED, 빈 행 없음 → SPLIT_IMPOSSIBLE. 오류 시 결과 파일과 ZIP을 만들지 않는다.

## 4. 미해결·지시서와 다른 점

- smartstore·coupang 규격은 사용자 확인 필요다. 지시서의 미확인 처리 방식대로 빈 unverified 템플릿을 유지했다.
- 선행 구현의 `min_jpeg_quality`(기본 80) 필드는 지시서의 "프로필의 최솟값"을 담는 설정으로 유지했다.
- 긴 섹션은 균일한 RGB 빈 행에서만 나눈다. 안전한 분할 위치를 못 찾으면 글자를 자르는 대신 오류다. 사진 안의 균일한 배경 행도 분할 위치가 될 수 있다.
- 확인된 기능 결함은 모두 수정했고 독립 리뷰와 회귀 검증을 수행했다. M5-C·D는 포함하지 않는다.

## 5. 푸시

브랜치 `ccr-f9c07036-vgvm5j`. `251f0c0` 위에 보완 커밋을 별도로 만들고 푸시한다. 결과와 해시는 최종 응답에 기록한다.

## 6. 검토 후 추가 보완 (Claude, 2026-11-15)

검토 지시(Important 1건·스마트스토어 근거)를 Claude 세션에서도 동시에 처리했다. `current_bundle()` 수정은 위 1장 3번과 같은 변경이라 중복 반영하지 않았고, 아래만 더했다.

- **스마트스토어 부분 반영**: 검토자가 공식 도움말(`https://help.sell.smartstore.naver.com/faq/content.help?faqId=3923`)에서 2026-11-15에 확인한 **상세설명 권장 폭 848px**만 `width`로 넣고 `source_url`·`checked_date = "2026-11-15"`를 기록했다. 장당 20MB(바이트 환산 기준 미확인)와 "4,000px 초과 시 3,000px 노출·나머지 펼쳐보기"는 `notes`에만 적었다. 허용 형식·최대 장수·이미지별 최대 높이·용량 제한값은 비워 두고 `status = "unverified"`를 유지한다. Claude 작업 환경에서는 해당 도움말에 접속할 수 없어 직접 재확인하지 못했다. 쿠팡은 공식 근거가 없어 빈 `unverified` 틀 그대로다.
- **추가 회귀 테스트** (`tests/test_export.py`): 승인 뒤 문구 변경·테마 변경·예전 classic-AA 정책 스냅샷 각각에 대해 `current_bundle()`과 **CLI export**가 내보내지 않고 오류로 끝나는지(ZIP 미생성), 오래된 승인본 대신 일치하는 미리보기를 쓰는지, 현재와 일치하는 승인본은 그대로 쓰는지. 스마트스토어 프로필이 확인된 폭·출처·날짜만 갖는지.
- README의 기본 프로필 설명을 스마트스토어·쿠팡으로 나눠 갱신했다.
- `00a85fb` 위로 옮긴 뒤 전체 테스트: **334 passed, 0 failed, 0 skipped** (약 14분). 그 전 실행에서 `test_browser.py`가 ① 사진 처리 미리보기 대기 시간 초과로 한 번 실패했으나(수정 전 기준선 `b2cdcad`에서도 같은 지점 실패 1회), 단독 재실행 5번 중 4번과 이번 전체 실행에서 통과했다. 건너뛰거나 완화하지 않았다.
