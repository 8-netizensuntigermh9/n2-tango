"""학습 카드·예문 렌더러 동작 검사 — 개발 전용 (.venv 의 playwright 필요).

사용법: .venv/Scripts/python tools/check_study.py     (먼저 python tools/build.py 로 dist/ 를 만든다)
dist/ 를 임시 로컬 서버로 띄워 Chromium 에서 검사하고, 하나라도 실패하면 종료코드 1.
  - 렌더러: rubyHtml 단위 검사, JS plain = Python plain (전체 단어), 발음·AI·상세에 중괄호 없음, highlight 잔재 없음
  - 학습 카드: 토글(무재렌더·visibility·aria-pressed·#sr), 새 카드 기본값(keepToggles 두 값), 되돌리기·자정,
    키보드, 뜻 잠깐 보여 주기(연타해도 answer 1회), 기출 칩, 표제어 글꼴, 진도 유지
"""
import functools
import http.server
import json
import re
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    print(("통과 " if ok else "실패 ") + name + (f" — {detail}" if detail and not ok else ""))


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    handler = functools.partial(Quiet, directory=str(DIST))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/"


# rubyHtml(raw, w, furi) 기대값 — 표제어 앞·뒤·문장 끝, 활용형, 가나 표제어, 덩어리 중간(경계 확장), 이스케이프, 중괄호 없음
RUBY_CASES = [
    ("範囲{はんい}は広{ひろ}い。", {"w": "範囲", "r": "はんい", "p": "n"}, True,
     "<mark><ruby>範囲<rt>はんい</rt></ruby></mark>は<ruby>広<rt>ひろ</rt></ruby>い。"),
    ("試験{しけん}の範囲{はんい}", {"w": "範囲", "r": "はんい", "p": "n"}, True,
     "<ruby>試験<rt>しけん</rt></ruby>の<mark><ruby>範囲<rt>はんい</rt></ruby></mark>"),
    ("もう済{す}みです。", {"w": "済む", "r": "すむ", "p": "v"}, True,
     "もう<mark><ruby>済<rt>す</rt></ruby></mark>みです。"),
    ("とてもおいしい。", {"w": "おいしい", "r": "おいしい", "p": "i"}, True,
     "とても<mark>おいしい</mark>。"),
    ("とてもおいしかった。", {"w": "おいしい", "r": "おいしい", "p": "i"}, True,
     "とても<mark>おいし</mark>かった。"),
    ("最大規模{さいだいきぼ}だ。", {"w": "規模", "r": "きぼ", "p": "n"}, True,
     "<mark><ruby>最大規模<rt>さいだいきぼ</rt></ruby></mark>だ。"),
    ("最大規模{さいだいきぼ}だ。", {"w": "規模", "r": "きぼ", "p": "n"}, False,
     "<mark>最大規模</mark>だ。"),
    ("<b>&\"'範囲{はんい}", {"w": "範囲", "r": "はんい", "p": "n"}, True,
     "&lt;b&gt;&amp;&quot;&#39;<mark><ruby>範囲<rt>はんい</rt></ruby></mark>"),
    ("範囲が広い。", {"w": "範囲", "r": "はんい", "p": "n"}, True, "<mark>範囲</mark>が広い。"),
    ("何もない。", {"w": "範囲", "r": "はんい", "p": "n"}, True, "何もない。"),
]


def main():
    from playwright.sync_api import sync_playwright
    rows, errors = validate.load()
    if errors:
        sys.exit("validate 오류 — 먼저 고친다")
    py_plain = [validate.plain(r["ex"]) for r in rows]
    src = (ROOT / "src/app.html").read_text(encoding="utf-8")
    check("highlight() 잔재 없음", "highlight(" not in src)
    check("rubyHtml 호출처 4곳(학습·퀴즈 해설·상세·AI 예문)", len(re.findall(r"\$\{rubyHtml\(", src)) == 4)
    check("revealed 상태 없음", not re.search(r"\brevealed\b", src))

    srv, url = serve()
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        page = br.new_page(viewport={"width": 402, "height": 680})
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.on("console", lambda m: m.type == "error" and errs.append(m.text))
        page.goto(url)
        page.evaluate("localStorage.clear()")
        page.reload()
        page.wait_for_selector(".card.study")
        ev = page.evaluate

        # ---- 렌더러 ----
        got = ev("cases => cases.map(([raw, w, furi]) => rubyHtml(raw, w, furi))", [[c[0], c[1], c[2]] for c in RUBY_CASES])
        bad = [(c[0], g, c[3]) for c, g in zip(RUBY_CASES, got) if g != c[3]]
        check(f"rubyHtml 단위 검사 {len(RUBY_CASES)}건", not bad, json.dumps(bad, ensure_ascii=False))
        js_plain = ev("WORDS.map(w => w.ex)")
        check(f"JS plain = Python plain ({len(py_plain)}행)", js_plain == py_plain,
              str(next(((a, b) for a, b in zip(js_plain, py_plain) if a != b), "길이 다름")))
        braces = ev("""() => {
          const out = [];
          for (const w of WORDS) {
            if (/[{}]/.test(w.ex)) out.push('ex:' + w.w);
            if (!aiPrompt(w, 'examples').includes('「' + w.ex + '」')) out.push('ai:' + w.w);
          }
          return out; }""")
        check("발음·AI 프롬프트·검색 문장에 중괄호 없음(전체)", not braces, str(braces[:5]))
        detail = ev("""() => {
          const out = [], said = [];
          speak = t => said.push(t);
          for (const w of WORDS.slice(0, 1310)) {
            openDetail(w.id);
            const t = [...document.querySelectorAll('#detail-body [data-act="speak"]')].map(b => b.dataset.t);
            if (t.some(x => /[{}]/.test(x)) || t[1] !== w.ex) out.push(w.w);
          }
          return out; }""")
        check("상세 시트 발음 data-t 에 중괄호 없음(전체)", not detail, str(detail[:5]))
        page.reload()
        page.wait_for_selector(".card.study")

        # ---- 토글: 무재렌더·visibility·aria-pressed·#sr ----
        ev("""() => { window.__n = 0; const o = renderStudy; renderStudy = (...a) => { __n++; return o(...a); };
                      window.__a = 0; const oa = answer; answer = (...a) => { __a++; return oa(...a); }; }""")
        state = """() => {
          const c = document.querySelector('.card.study'), vis = s => getComputedStyle(c.querySelector(s)).visibility;
          const rt = c.querySelector('rt');
          return { reading: vis('.reading'), rt: rt ? getComputedStyle(rt).visibility : 'none', meaning: vis('.meaning'), ko: vis('.ex .ko'),
                   kana: document.querySelector('[data-act=kana]').getAttribute('aria-pressed'),
                   mean: document.querySelector('[data-act=mean]').getAttribute('aria-pressed'),
                   word: c.querySelector('.word').getBoundingClientRect().top, ja: c.querySelector('.ex .ja').getBoundingClientRect().top,
                   sr: document.querySelector('#sr').textContent, n: __n, id: queue[0] }; }"""
        s0 = ev(state)
        check("새 카드 기본: 히라가나·의미 꺼짐(showReading=false)", s0["kana"] == "false" and s0["mean"] == "false"
              and s0["reading"] == "hidden" and s0["rt"] == "hidden" and s0["meaning"] == "hidden" and s0["ko"] == "hidden", str(s0))
        page.click("[data-act=kana]")
        s1 = ev(state)
        check("히라가나 ON: 읽기 줄·rt 보임, aria-pressed=true, 뜻은 그대로", s1["kana"] == "true" and s1["reading"] == "visible"
              and s1["rt"] == "visible" and s1["meaning"] == "hidden", str(s1))
        check("히라가나 ON: #sr 「읽기: …」", s1["sr"].startswith("읽기: "), s1["sr"])
        page.click("[data-act=mean]")
        s2 = ev(state)
        check("의미 ON: 뜻·번역 보임, aria-pressed=true", s2["mean"] == "true" and s2["meaning"] == "visible" and s2["ko"] == "visible", str(s2))
        check("의미 ON: #sr 「뜻: …」", s2["sr"].startswith("뜻: "), s2["sr"])
        page.click("[data-act=kana]")
        s3 = ev(state)
        check("히라가나 OFF: 읽기 줄·rt 숨김", s3["kana"] == "false" and s3["reading"] == "hidden" and s3["rt"] == "hidden", str(s3))
        check("토글 중 renderStudy 호출 0회", s3["n"] == 0, f"{s3['n']}회")
        check("토글해도 표제어·예문 위치 그대로(≤1px)", max(abs(x["word"] - s0["word"]) for x in (s1, s2, s3)) <= 1
              and max(abs(x["ja"] - s0["ja"]) for x in (s1, s2, s3)) <= 1)

        # ---- 새 카드 기본값: keepToggles OFF / ON, showReading ----
        page.click("[data-act=no]")   # 의미 ON 상태에서 다음 카드
        s4 = ev(state)
        check("다음 카드(keepToggles OFF): 토글 꺼짐", s4["id"] != s3["id"] and s4["kana"] == "false" and s4["mean"] == "false", str(s4))
        check("카드가 바뀌면 #sr 「새 카드: …」", s4["sr"].startswith("새 카드: "), s4["sr"])
        ev("S.keepToggles = true; S.showReading = true")
        page.click("[data-act=mean]")
        page.click("[data-act=no]")
        s5 = ev(state)
        check("다음 카드(keepToggles ON): 직전 토글 유지(의미 ON·히라가나 OFF)", s5["mean"] == "true" and s5["kana"] == "false", str(s5))
        ev("S.keepToggles = false")
        page.click("[data-act=no]")
        s6 = ev(state)
        check("다음 카드(showReading ON): 히라가나 켜짐·의미 꺼짐", s6["kana"] == "true" and s6["mean"] == "false", str(s6))
        ev("S.showReading = false")

        # ---- 되돌리기: 카드·토글 복원, 자정 뒤 되돌리기는 재구성 없이 ----
        page.click("[data-act=mean]")
        before = ev(state)
        page.click("[data-act=yes]")   # 의미 ON 이라 바로 넘어감
        page.click("[data-act=undo]")
        s7 = ev(state)
        check("되돌리기: 직전 카드와 토글 상태 복원", s7["id"] == before["id"] and s7["mean"] == "true" and s7["kana"] == before["kana"], str(s7))
        page.click("[data-act=no]")
        prev_id = ev("undo.queue[0]")
        ev("window.__realToday = today; today = () => addDays(__realToday(), 1)")
        page.click("[data-act=undo]")
        s8 = ev("({ id: queue[0], day: queueDay, real: __realToday() })")
        check("자정 뒤 되돌리기: 재구성 없이 직전 카드", s8["id"] == prev_id and s8["day"] == s8["real"], str(s8))
        page.click("[data-act=kana]")
        check("자정 뒤 토글만: 카드 그대로", ev("queue[0]") == prev_id)
        page.click("[data-act=no]")
        check("자정 뒤 답하면 새 날 목록", ev("queueDay") == ev("today()"))
        ev("today = __realToday")
        ev("queueDirty = true; renderStudy()")

        # ---- 키보드 ----
        def key(code, k=""):
            ev("([code, k]) => document.body.dispatchEvent(new KeyboardEvent('keydown', { code, key: k, bubbles: true }))", [code, k])
        ev("document.activeElement && document.activeElement.blur()")
        a0, id0 = ev("__a"), ev("queue[0]")
        key("KeyH", "h")
        k1 = ev(state)
        key("KeyM", "m")
        k2 = ev(state)
        key("Space", " ")
        k3 = ev(state)
        check("키보드 H 히라가나 · M/Space 의미", k1["kana"] == "true" and k2["mean"] == "true" and k3["mean"] == "false", f"{k1['kana']} {k2['mean']} {k3['mean']}")
        key("ArrowLeft", "ArrowLeft")
        check("키보드 ← 몰라요", ev("__a") == a0 + 1 and ev("queue[0]") != id0)
        key("KeyZ", "z")
        check("키보드 Z 되돌리기", ev("queue[0]") == id0)
        key("ArrowLeft", "ArrowLeft")
        key("Backspace", "Backspace")
        check("키보드 Backspace 되돌리기", ev("queue[0]") == id0)
        ev("S.flashOnKnow = false")
        key("ArrowRight", "ArrowRight")
        check("키보드 → 알아요", ev("__a") == a0 + 3 and ev("queue[0]") != id0)
        ev("S.flashOnKnow = true")

        # ---- 뜻 잠깐 보여 주기: 연타해도 answer 1회 ----
        a1, id1 = ev("__a"), ev("queue[0]")
        page.click("[data-act=yes]")
        f1 = ev(state)
        ev("document.querySelector('[data-act=yes]').click(); document.querySelector('[data-act=no]').click()")
        key("ArrowRight", "ArrowRight")
        key("ArrowLeft", "ArrowLeft")
        mid = ev("({ a: __a, id: queue[0] })")
        page.wait_for_timeout(750)
        after = ev("({ a: __a, id: queue[0] })")
        check("flashOnKnow: 의미 OFF 로 알아요 → 뜻 보임, 그동안 카드 그대로", f1["meaning"] == "visible" and mid["id"] == id1 and mid["a"] == a1, str(mid))
        check("flashOnKnow: 0.6초 뒤 다음 카드, 연타해도 answer 1회", after["a"] == a1 + 1 and after["id"] != id1, str(after))

        # ---- 기출 칩 ----
        chips = ev("""() => {
          const k = WORDS.find(w => w.kc), n = WORDS.find(w => !w.kc), out = {};
          for (const w of [k, n]) { queue.unshift(w.id); renderStudy(); out[w.kc ? 'k' : 'n'] = !!document.querySelector('.card .chip.kichul'); queue.shift(); }
          renderStudy(); return out; }""")
        check("기출 단어에만 「기출」 칩", chips == {"k": True, "n": False}, str(chips))
        n_kc = ev("WORDS.filter(w => w.kc).length")
        check("기출 표시 단어 수 = kichul.list", n_kc == len(validate.kichul_keys()), f"{n_kc}")

        # ---- 표제어 글꼴 ----
        page.wait_for_function("document.fonts.status === 'loaded'", timeout=15000)
        font = ev("""() => { const s = getComputedStyle(document.querySelector('.card .word'));
          return { family: s.fontFamily, weight: s.fontWeight, loaded: [...document.fonts].some(f => f.family.replace(/"/g, '') === 'IBM Plex Sans JP' && f.status === 'loaded') }; }""")
        check("표제어 글꼴 IBM Plex Sans JP 500", font["family"].startswith('"IBM Plex Sans JP"') and font["weight"] == "500", str(font))
        check("IBM Plex Sans JP 실제로 받음(네트워크)", font["loaded"], str(font))

        # ---- 진도 유지·기존 진도 형식 ----
        key_before = ev("Object.keys(P).length")
        page.reload()
        page.wait_for_selector(".card.study")
        check("새로고침 뒤 진도 유지", ev("Object.keys(P).length") == key_before and key_before > 0)
        old = {rows[i]["w"] + "|" + rows[i]["r"]: {"s": 5, "d": "2099-01-01", "w": 0, "f": "2026-01-01"} for i in range(30)}
        ev("p => localStorage.setItem('n2tango.progress', JSON.stringify(p))", old)
        page.reload()
        page.wait_for_selector(".view")
        master = ev("WORDS.filter(w => status(w) === 'master').length")
        stored = ev("JSON.parse(localStorage.getItem('n2tango.progress'))")
        check("기존 진도 JSON 그대로 읽힘(외운 30)", master == 30 and all(stored[k] == v for k, v in old.items()), f"{master}")

        check("콘솔 오류 0", not errs, str(errs[:3]))
        br.close()
    srv.shutdown()
    failed = [n for n, ok in results if not ok]
    print(f"\n검사 {len(results)}개 · 실패 {len(failed)}개")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
