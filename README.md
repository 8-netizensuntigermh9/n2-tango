# N2 단어장

JLPT N2 핵심 단어 1,310개를 예문과 함께 외우는 휴대폰용 단어장 웹앱입니다.

**앱 열기:** https://8-netizensuntigermh9.github.io/n2-tango/
Chrome에서 메뉴(⋮) → 「홈 화면에 추가」를 누르면 앱처럼 설치됩니다.

- **학습**: 카드에 단어와 예문이 늘 보입니다. 「히라가나」 버튼은 단어 읽기와 예문 후리가나를, 「의미」 버튼은 뜻과 번역을 따로 켜고 끕니다. 「몰라요 / 알아요」를 고르면 모르는 단어는 자주, 아는 단어는 점점 드물게 다시 나옵니다. 기출 단어에는 「기출」 표시가 붙습니다.
- **퀴즈**: 4지선다 10문제 (뜻 고르기 · 단어 고르기 · 읽기 고르기)
- **단어장**: 한자 · 읽기 · 한국어 뜻으로 검색. 🔊로 발음 듣기
- **Gemini AI**: 설정에 무료 API 키를 넣으면 예문 추가 · 뉘앙스 설명 · 질문하기. 키가 없으면 질문을 복사해 Gemini 앱으로 넘겨 줍니다.

키보드가 있으면 ← 몰라요 · → 알아요 · H 히라가나 · M/Space 의미 · Z 되돌리기로 넘길 수 있습니다.

진도와 API 키는 각자의 브라우저에만 저장되며, 어디에도 올라가지 않습니다.

> **「기출」 표시 출처:** 『일단합격 JLPT 완벽대비 N2』의 파이널 단어 체크북에 실린 단어 목록을 기준으로 했습니다. 단어의 뜻·예문·번역은 책에서 옮기지 않고 따로 썼습니다.

> **API 키 팁:** 이 앱 전용 키를 새로 만들고, Google AI Studio(또는 Cloud 콘솔)의 키 설정에서 사용처를 `https://8-netizensuntigermh9.github.io/*`(HTTP 리퍼러)로 제한해 두세요.
> 같은 github.io 주소를 쓰는 다른 페이지는 브라우저 저장소를 함께 쓰기 때문에, 제한해 두면 키가 새어 나가도 다른 곳에서 쓸 수 없습니다.

## 고치고 다시 만들기

```
python tools/validate.py   # 단어 데이터 검사
python tools/build.py      # dist/ 생성
```

- 단어는 `data/*.txt` 에 `단어|읽기|품사|뜻|예문|번역` 형식으로 한 줄씩 씁니다.
- 예문은 한자 덩어리마다 읽기를 붙인 루비 표기로 씁니다: `彼{かれ}の話{はな}し方{かた}はとても良{よ}い印象{いんしょう}を与{あた}えた。`
  `{}` 앞의 이어진 한자 전체에 히라가나 읽기를 붙이고, 한자는 하나도 빠짐없이 읽기가 있어야 합니다. `validate.py` 가 확인합니다.
- 기출 단어는 `data/kichul.list` 에 `단어|읽기` 로 한 줄씩 적습니다.
- 앱 본체는 `src/app.html`, 설계는 `DESIGN.md` 를 보세요.

### 개발 도구 (선택)

후리가나 1차안 생성과 화면 검사는 따로 설치한 파이썬 환경에서 돌립니다. 앱 빌드에는 필요 없습니다.

```
python -m venv .venv
.venv/Scripts/pip install -r tools/requirements-dev.txt
.venv/Scripts/python -m playwright install chromium webkit
```

- `tools/furigana.py` — 예문 루비 1차안 생성(SudachiPy + pykakasi 대조). 고칠 읽기는 `tools/furigana_fix.txt` 에 적습니다.
- `tools/check_study.py` — 학습 카드 동작 검사(토글·되돌리기·키보드·기출 칩 등).
- `tools/check_layout.py` — 여러 화면 크기에서 학습 카드가 스크롤 없이 한 화면에 들어가는지 검사.

두 검사는 `python tools/build.py` 로 `dist/` 를 만든 뒤 실행합니다.
