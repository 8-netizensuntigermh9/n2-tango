"""학습 카드 「한 화면」 측정 — 개발 전용 (.venv 의 playwright + chromium·webkit 필요).

사용법: .venv/Scripts/python tools/check_layout.py [--report .omc/research/layout_check.md]
        (먼저 python tools/build.py 로 dist/ 를 만든다)
엔진 Chromium·WebKit × 뷰포트 402×680·360×640·375×812 × 라이트·다크 × 글꼴(정상 / Google Fonts 차단) = 24조합.
조합마다 「최악 카드」(루비 예문 높이·번역·뜻 상위 5, 표제어 길이 상위 3 + コミュニケーション)를 두 토글 ON 으로 띄워
  - 문서 스크롤 0 (scrollHeight ≤ innerHeight, scrollWidth ≤ innerWidth)
  - 카드 안 스크롤 0 (세로·가로), 진도 줄 넘침 0
  - 토글 2·답 2·탭바가 뷰포트 안
  - 토글 4상태에서 표제어·예문 top 차이 ≤ 1px
  - 콘솔 오류 0
을 검사한다. 하나라도 실패하면 종료코드 1.
"""
import argparse
import functools
import http.server
import sys
import threading
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
VIEWPORTS = [(402, 680), (360, 640), (375, 812)]
EXTRA_WORD = "コミュニケーション"


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(DIST)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/"


# 진도: 1000단어를 외움·오늘 복습으로 심어 진도 줄 숫자를 가장 길게 만든다
SEED = """() => {
  const p = {}, t = today();
  WORDS.slice(0, 1000).forEach(w => { p[w.k] = { s: 5, d: t, w: 0, f: t }; });
  localStorage.setItem('n2tango.progress', JSON.stringify(p));
  localStorage.setItem('n2tango.settings', JSON.stringify({ newPerDay: 50, keepToggles: true, flashOnKnow: false, tab: 'study' }));
}"""

# 한 카드를 두 토글 ON 으로 띄운다(앱에 테스트 코드를 넣지 않고 queue 를 바꿔 renderStudy)
SHOW = """id => { queue[0] = id; view = { kana: true, mean: true }; renderStudy(); }"""

# 최악 카드 고르기: 모든 단어를 두 토글 ON 으로 그려 높이를 잰다
PICK = """extra => {
  const m = WORDS.map(w => {
    queue[0] = w.id; view = { kana: true, mean: true }; renderStudy();
    const c = document.querySelector('.card.study');
    return { id: w.id, w: w.w, ja: [c.querySelector('.ex .ja').offsetHeight, w.ex.length], ko: [c.querySelector('.ex .ko').offsetHeight, w.ko.length],
             mean: [c.querySelector('.meaning').offsetHeight, w.m.length], wl: [w.w.length, 0] };
  });
  // 높이가 같으면 글자 수가 긴 쪽이 더 나쁜 카드
  const top = (k, n) => m.slice().sort((a, b) => b[k][0] - a[k][0] || b[k][1] - a[k][1] || a.id - b.id).slice(0, n);
  const pick = new Map();
  for (const [k, n, why] of [['ja', 5, '루비 예문 높이'], ['ko', 5, '번역 높이'], ['mean', 5, '뜻 높이'], ['wl', 3, '표제어 길이']])
    for (const x of top(k, n)) {
      if (!pick.has(x.id)) pick.set(x.id, { id: x.id, w: x.w, why: [] });
      pick.get(x.id).why.push(why);
    }
  const ex = WORDS.find(w => w.w === extra);
  if (ex && !pick.has(ex.id)) pick.set(ex.id, { id: ex.id, w: ex.w, why: ['지정'] });
  return [...pick.values()];
}"""

MEASURE = """ids => {
  const out = [];
  const spare = c => {   // 카드 안 남는 높이: 늘어나는 .face 를 잠시 멈추고 내용 끝과 카드 안쪽 끝의 차이
    const f = c.querySelector('.face'), ex = c.querySelector('.ex');
    f.style.flexGrow = '0';
    const v = c.clientHeight - parseFloat(getComputedStyle(c).paddingBottom) - (ex.offsetTop + ex.offsetHeight);
    f.style.flexGrow = '';
    return Math.round(v);
  };
  const inView = el => { if (!el) return false; const r = el.getBoundingClientRect(); return r.top >= 0 && r.left >= 0 && r.bottom <= innerHeight + 0.5 && r.right <= innerWidth + 0.5; };
  for (const id of ids) {
    queue[0] = id; view = { kana: true, mean: true }; renderStudy();
    const se = document.scrollingElement, c = document.querySelector('.card.study'), st = document.querySelector('.stats');
    const pos = [];
    for (const [k, mn] of [[false, false], [true, false], [false, true], [true, true]]) {
      setView('kana', k); setView('mean', mn);
      pos.push([c.querySelector('.word').getBoundingClientRect().top, c.querySelector('.ex .ja').getBoundingClientRect().top]);
    }
    const shift = Math.max(...pos.map(p => Math.max(Math.abs(p[0] - pos[0][0]), Math.abs(p[1] - pos[0][1]))));
    const buttons = [...document.querySelectorAll('#view-study .tg, #view-study .btn.ans')];
    out.push({
      id, w: WORDS[id].w,
      docY: se.scrollHeight - innerHeight, docX: se.scrollWidth - innerWidth,
      cardY: c.scrollHeight - c.clientHeight, cardX: c.scrollWidth - c.clientWidth,
      statsX: st.scrollWidth - st.clientWidth, view: document.querySelector('#view-study').scrollHeight - document.querySelector('#view-study').clientHeight,
      buttons: buttons.length === 4 && buttons.every(inView), tabs: inView(document.querySelector('.tabs')),
      shift, spare: spare(c),
    });
  }
  return out;
}"""


def ignorable(text, block):
    """측정 조건이 만든 콘솔 오류: 일부러 막은 글꼴 요청, WebKit 이 모르는 뷰포트 키(interactive-widget, 안드로이드용)."""
    return (block and "ERR_FAILED" in text) or 'Viewport argument key "interactive-widget"' in text


def run_combo(pw, engine, vp, scheme, block, url, ids):
    br = getattr(pw, engine).launch()
    ctx = br.new_context(viewport={"width": vp[0], "height": vp[1]}, color_scheme=scheme, device_scale_factor=2)
    if block:
        ctx.route(lambda u: "fonts.googleapis.com" in u or "fonts.gstatic.com" in u, lambda r: r.abort())
    page = ctx.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.on("console", lambda m: m.type == "error" and not ignorable(m.text, block) and errs.append(m.text))
    page.goto(url)
    page.evaluate(SEED)
    page.reload()
    page.wait_for_selector(".card.study")
    page.click("[data-act=no]")          # 되돌리기 아이콘까지 보이게
    if not block:
        page.wait_for_function("document.fonts.status === 'loaded'", timeout=20000)
        fonts = page.evaluate("[...document.fonts].filter(f => f.status === 'loaded').map(f => f.family.replace(/\"/g, ''))")
    else:
        fonts = []
    res = page.evaluate(MEASURE, ids)
    br.close()
    return res, errs, sorted(set(fonts))


def main():
    from playwright.sync_api import sync_playwright
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default=str(ROOT / ".omc/research/layout_check.md"))
    args = ap.parse_args()
    srv, url = serve()
    rows, fails = [], []
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        page = br.new_page(viewport={"width": 360, "height": 640})
        page.goto(url)
        page.evaluate(SEED)
        page.reload()
        page.wait_for_selector(".card.study")
        page.wait_for_function("document.fonts.status === 'loaded'", timeout=20000)
        worst = page.evaluate(PICK, EXTRA_WORD)
        br.close()
        ids = [x["id"] for x in worst]
        print(f"최악 카드 {len(ids)}장: " + ", ".join(f"{x['w']}({'/'.join(x['why'])})" for x in worst))
        for engine in ("chromium", "webkit"):
            for vp in VIEWPORTS:
                for scheme in ("light", "dark"):
                    for block in (False, True):
                        res, errs, fonts = run_combo(pw, engine, vp, scheme, block, url, ids)
                        bad = [r for r in res if r["docY"] > 0 or r["docX"] > 0 or r["cardY"] > 0 or r["cardX"] > 0 or r["statsX"] > 0
                               or r["view"] > 0 or not r["buttons"] or not r["tabs"] or r["shift"] > 1]
                        name = f"{engine} {vp[0]}×{vp[1]} {scheme} {'글꼴 차단' if block else '글꼴 정상'}"
                        spare = min(r["spare"] for r in res)
                        ok = not bad and not errs
                        rows.append((name, ok, spare, max(r["shift"] for r in res), len(errs), bad, fonts))
                        print(("통과 " if ok else "실패 ") + f"{name} · 카드 여유 최소 {spare}px" + (f" · 문제 {[(b['w'], {k: v for k, v in b.items() if k not in ('id', 'w')}) for b in bad[:2]]}" if bad else "") + (f" · 콘솔 {errs[:2]}" if errs else ""))
                        if not ok:
                            fails.append(name)
    srv.shutdown()
    write_report(Path(args.report), worst, rows)
    print(f"\n조합 {len(rows)}개 · 실패 {len(fails)}개 · 보고서 {args.report}")
    sys.exit(1 if fails else 0)


def write_report(path, worst, rows):
    lines = ["# 학습 카드 한 화면 측정", "", f"측정 {datetime.now():%Y-%m-%d %H:%M} · `tools/check_layout.py`", "",
             "## 최악 카드 (Chromium 360×640, 두 토글 ON 으로 전체 1310장을 그려 고름)", ""]
    lines += [f"- {x['w']} — {', '.join(x['why'])}" for x in worst]
    small = min(r[2] for r in rows if "360×640" in r[0])
    lines += ["", "## B-layout(작은 화면 4칸 한 줄) 판단", "",
              f"- 360×640 에서 카드 안 남는 높이 최소 {small}px → " + ("**B-layout 적용 안 함**. 두 줄 배치(토글 2 + 답 2)로 모든 조합이 들어가므로 전환 기준값(max-height)을 두지 않는다." if small >= 0 and all(r[1] for r in rows) else "**B-layout 필요** — 넘친 높이를 보고 기준값을 정한다."),
              "- 측정 중 고친 것: 진도 줄 되돌리기 아이콘의 음수 여백(-8px)이 가로 넘침을 만들어 제거, 긴 표제어(コミュニケーション 등)는 글자 수(--len)에 맞춰 글자 크기를 줄임."]
    lines += ["", "## 조합별 결과", "", "| 조합 | 결과 | 카드 안 남는 높이(최소) | 토글 이동(최대) | 콘솔 오류 | 받은 글꼴 |", "|---|---|---|---|---|---|"]
    for name, ok, spare, shift, nerr, bad, fonts in rows:
        lines.append(f"| {name} | {'통과' if ok else '실패'} | {spare}px | {shift:.1f}px | {nerr} | {', '.join(fonts) or '—'} |")
    lines += ["", "「카드 안 남는 높이」 = 카드 높이 − 카드 내용 높이(늘어나는 단어 칸을 멈추고 잼). 0 이상이면 카드 안 스크롤 없이 들어간다.",
              "진도 줄은 1000단어 외움·1020장 남음으로 숫자를 가장 길게 만들고 되돌리기 아이콘까지 띄운 상태다.",
              "콘솔 오류에서 뺀 것: 글꼴 차단 조합의 막힌 요청(ERR_FAILED), WebKit 의 `interactive-widget` 뷰포트 키 경고(안드로이드 키보드용 키라 iOS 는 무시).", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
