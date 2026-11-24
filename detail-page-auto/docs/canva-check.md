# 캔바(Canva) 편집 가능 여부 확인 (M8-C)

캔바는 외부 서비스라 자동 테스트로 확인할 수 없습니다. 아래 **가상 샘플 PDF**를 직접 올려 보고 결과를 기록합니다. 실제 상품 자료는 쓰지 않습니다.

## 샘플 파일
| 파일 | 테마 | 글꼴 |
|---|---|---|
| `docs/samples/canva-sample-modern.pdf` | modern | Pretendard(가변 글꼴 — PDF 안에서는 Type3 글꼴로 들어감) |
| `docs/samples/canva-sample-natural.pdf` | natural | 고운바탕(제목) + Pretendard(본문) |
| `docs/samples/canva-sample-classic.pdf` | classic | Noto Sans CJK |

다시 만들기: `.venv/bin/python tools/make_screenshots.py --m8c-only`

## 확인 순서
1. 캔바 → 업로드 → PDF 파일 올리기 → 열기("PDF 편집"으로 가져오기)
2. 아래 항목을 테마별로 확인

## 확인 항목과 결과 기록
| 항목 | modern | natural | classic |
|---|---|---|---|
| 1. 쪽 수가 7쪽이고 쪽 크기가 같게 열린다 | | | |
| 2. 제목·본문을 눌렀을 때 **글자 상자**로 선택된다(이미지가 아님) | | | |
| 3. 글자를 고쳐 쓸 수 있다(한글 입력) | | | |
| 4. 글꼴이 유지된다 / 다른 글꼴로 바뀐다(바뀐 글꼴 이름) | | | |
| 5. 줄바꿈·정렬이 원래와 같다 | | | |
| 6. 사진이 따로 선택·이동된다 | | | |
| 7. 배경색·띠가 따로 선택되거나 하나로 합쳐진다 | | | |

- 확인 날짜:
- 기타 관찰:

결과는 계정 정보 없이 위 표만 채워 알려 주세요. README의 "캔바에서 수정할 때 알아 둘 점"을 이 결과로 갱신합니다.
