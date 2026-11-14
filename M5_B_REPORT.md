# M5-B 완료 보고 (플랫폼별 내보내기 프로필)

## 1. 구현 여부

**완료.** 기준 커밋 `d080b14`(M5-A 확정본) 위의 단일 커밋. 커밋 해시는 최종 보고에 기록한다.

| 항목 | 위치 |
|---|---|
| 프로필 파일 | `profiles/generic.toml`, `profiles/smartstore.toml`, `profiles/coupang.toml`. 사용자 프로필 `profiles/user/*.toml`(Git 제외, `DETAIL_PAGE_USER_PROFILES`로 위치 변경 가능) |
| 검증·내보내기 | `core/export.py`: `Profile`(알 수 없는 항목·음수·날짜 형식·https 아닌 출처·verified인데 값/출처 누락 거부), `load_profile`, `list_profiles`, `save_user_profile`, `export_bundle`, `build_export_zip`, `current_bundle` |
| 화면 | ⑦ 다운로드 "올릴 곳 규격 검사·내보내기": 프로필 선택 → 검사 결과(통과/경고/오류) → 프로필별 ZIP, "새 프로필 만들기" |
| CLI | `cli.py export --job JOB --profile ID [--format jpg|png] [--output DIR]` |

내보내기 동작:
- 렌더링 스냅샷(PNG 우선)을 이어 붙인 뒤 프로필 폭이 다르면 비율을 유지해 리사이즈한다.
- 분할은 섹션 경계를 우선하고, 한 섹션이 최대 높이보다 길면 **픽셀이 균일한 빈 행에서만** 자른다(텍스트 행을 자르지 않음). 빈 행이 없으면 `SPLIT_IMPOSSIBLE` 오류.
- 용량 초과 시 JPEG 품질을 5씩 프로필 최솟값(기본 80)까지만 낮춰 재시도한다. 그래도 초과(`FILE_TOO_LARGE`), 장수 초과(`TOO_MANY_IMAGES`), 형식 불일치(`FORMAT_NOT_ALLOWED`)면 오류이며 파일을 쓰지 않는다.
- `unverified` 또는 값이 빈 프로필은 결과를 만들되 `PROFILE_UNVERIFIED`·`PROFILE_VALUE_MISSING` "규격 미확인" 경고를 화면·manifest에 남기고 ZIP 이름에 `.UNVERIFIED`를 붙인다. 어떤 경우에도 "업로드 가능"이라고 표시하지 않는다.
- 렌더링 스냅샷은 수정하지 않는다. 내보내기는 `<작업>/exports/export-…/`에 새로 만든다(`rendered/` 밖).
- ZIP: 내보낸 이미지, `page.html`·`assets`·`draft.json`·`review.json`, 그리고 렌더링 manifest에 `export`(프로필 id·값·출처·확인 날짜·유효값·형식·검사 결과·파일별 크기/품질)를 더한 `manifest.json`.

## 2. 실행과 검증

```bash
cd detail-page-auto
.venv/bin/python -m pytest -q
git status --porcelain=v1
```

- 기준(`d080b14`): 278 passed, 0 failed, 0 skipped.
- 변경 후 전체: **317 passed, 0 failed, 0 skipped** (약 14분). 테스트 후 `git status`에는 이번 변경 파일만 있음(테스트가 만든 파일 없음).
- 새 테스트: `tests/test_export.py`(38개), `tests/test_app.py`의 ⑦ 프로필 내보내기 AppTest 1개.
  - 폭·분할 높이가 다른 가짜 프로필 2개로 장수·크기 확인, 섹션 경계 우선 + 섹션 내부 분할 지점이 모두 빈 행인지 확인
  - 빈 행이 없는 섹션(노이즈 이미지) → 분할 불가 오류, 파일 미작성
  - 용량 초과 → 품질 하향 재시도 성공 / 최솟값 80에서도 초과 → 오류
  - 장수 초과·형식 불일치 → 오류, PNG 허용 프로필은 PNG 출력
  - 기본 3개 프로필 `unverified` → 결과 생성 + 경고 + `.UNVERIFIED` ZIP, 플랫폼 틀에 지어낸 값 없음, generic은 기존 기본값
  - 잘못된 프로필 파일(날짜 형식·없는 날짜·음수·0·알 수 없는 항목·status·verified 누락·형식·출처 스킴·품질 역전·TOML 오류) → 오류
  - 사용자 프로필 저장·목록·기본 id 보호·Git 제외(`git check-ignore`), 환경변수 폴더
  - manifest에 프로필 값·출처·날짜·검사 결과, 스냅샷 불변, 기본 내보내기 폴더가 `rendered/` 밖, CLI export(정상·없는 프로필·미리보기 없음)

## 3. 결과 예시

- 프로필별 검사 결과 예시 (샘플 렌더링):
  - `generic`: 경고 — `PROFILE_UNVERIFIED`("규격 미확인: … 공식 문서로 확인되지 않았습니다"), `PROFILE_VALUE_MISSING`(max_file_bytes, max_images 검사 안 함) → `job-…-generic.UNVERIFIED.zip`
  - `smartstore`/`coupang`: 경고 — 위 항목 + 폭·높이·형식·품질도 비어 기본값 사용 → `.UNVERIFIED.zip`
  - 가짜 verified 프로필(최대 1장): 오류 — `TOO_MANY_IMAGES`("장수 초과: N장이 필요하지만 프로필 최대는 1장입니다"), ZIP 없음
- **smartstore·coupang 공식 출처: 사용자 확인 필요.** 작업 환경에서 네이버 판매자센터 도움말(`help.sell.smartstore.naver.com`)은 가져오기가 거부되었고, 쿠팡 판매자 도움말(`helpseller.coupang.com`)은 세션 네트워크 허용 목록 밖이라 열 수 없었다. 웹 검색 결과는 블로그·외주 업체 글뿐이어서 근거로 쓰지 않았다. 두 프로필은 값·`source_url`·`checked_date`를 비운 `unverified` 틀로 두었다. 공식 문서에서 확인한 뒤 값·출처·날짜를 채우고 `status = "verified"`로 바꾸면 된다.

## 4. 미해결·지시서와 다른 점

- smartstore·coupang 규격 값: 위 3장대로 사용자 확인 필요.
- 지시서에 없는 필드 `min_jpeg_quality`(기본 80)를 추가했다. 지시서의 "프로필의 최솟값(기본 80)"을 담기 위해서다.
- 형식 불일치는 "요청한 출력 형식(`--format`)이 프로필의 `formats`에 없음"으로 정의했다. 출력은 JPG 또는 PNG만 만든다.
- 섹션 내부 분할은 렌더링 이미지에서 픽셀이 균일한 행(회색조 차이 12 이하)을 찾는 방식이다. 사진 안의 균일한 행에서 잘릴 수는 있으나 글자 행은 자르지 않는다.
- 테스트 작성 중 기존 동작에서 알게 된 점(수정하지 않음): "최근 작업" 목록은 상품명·생성 시각(분 단위)·상태로 표시되므로, 같은 분에 만든 원본 작업과 승인 작업의 이름이 같게 보일 수 있다.
- `CLAUDE_HANDOFF.md`는 지시서대로 M5 전체가 끝난 뒤 갱신한다. M5-C·D는 포함하지 않는다.

## 5. 푸시

브랜치 `ccr-f9c07036-vgvm5j`, `d080b14` 다음 커밋으로 푸시(강제 푸시 없음).
