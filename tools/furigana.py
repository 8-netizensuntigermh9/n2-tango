"""예문 후리가나(루비) 1차안 만들기 — 개발 전용 (.venv 의 sudachipy·pykakasi 필요).

표기: その件{けん}はもう済{す}みです — {} 앞의 연속 한자 덩어리에 읽기를 붙인다.

사용법: .venv/Scripts/python tools/furigana.py [--out .omc/research/furigana_draft.tsv] [--report .omc/research/furigana_review.md]
  1) SudachiPy(core, Mode C) 형태소마다 읽기를 받아, 송리가나를 떼고 한자 덩어리별 읽기로 자른다.
     Mode A 로 쪼갠 읽기를 이어 붙인 것이 Mode C 읽기와 같으면 더 잘게(덩어리 경계가 표제어와 맞게) 쓴다.
  2) 표제어 구간은 data 2열 읽기를 우선한다(사전보다 데이터가 정본).
  3) pykakasi 로 다시 읽어 덩어리 읽기가 다르면 「불일치」로 표시한다(검토 우선순위용).
  4) 고친 읽기는 GLOBAL(모든 문장)과 tools/furigana_fix.txt 로 덮어쓴다.
     furigana_fix.txt 한 줄 = 단어|읽기 <탭> 바꿀 부분 <탭> 새 부분  (또는 단어|읽기 <탭> 루비 문장 전체)
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate  # noqa: E402
from validate import KANJI, KANJI_RUN, hira, plain  # noqa: E402  루비 규칙은 validate.py 한 곳에

ROOT = Path(__file__).resolve().parent.parent
FIX = Path(__file__).resolve().parent / "furigana_fix.txt"

NUM = re.compile(r"[0-9０-９一二三四五六七八九十百千万何数幾]")
# 숙자훈·다르게 읽는 낱말 — 들어 있으면 우선 검토
JUKU = ["今日", "明日", "昨日", "一昨日", "明後日", "今朝", "今年", "今夜", "一人", "二人", "大人", "一日", "二日", "上手", "下手",
        "時計", "眼鏡", "部屋", "果物", "景色", "素人", "玄人", "為替", "土産", "真面目", "笑顔", "雪崩", "風邪", "相撲", "竹刀",
        "二十歳", "目上", "人気", "方", "何", "大家", "生物", "市場", "最中", "日本", "分別", "寒気", "見物", "気質", "一人前",
        "仲人", "迷子", "息子", "博士", "姉さん", "兄さん", "下手", "心地", "田舎", "八百屋", "行方", "日中", "後", "間", "上", "下",
        "中", "前", "辺", "所", "者", "人", "身", "家", "工場", "変化", "一時", "一体", "一度", "一番", "一生", "一緒", "一層"]


def parts(surface):
    """표기를 [(조각, 한자인가)] 로 나눈다."""
    out, i = [], 0
    for m in KANJI_RUN.finditer(surface):
        if m.start() > i:
            out.append((surface[i:m.start()], False))
        out.append((m.group(), True))
        i = m.end()
    if i < len(surface):
        out.append((surface[i:], False))
    return out


def align(surface, reading):
    """표기와 읽기(히라가나)를 맞춰 [(조각, 읽기 또는 None)] 를 돌려준다.
    가나 조각을 고정점으로 삼는다. 맞출 수 없으면 None, 여러 방법이 가능하면 ambiguous=True."""
    ps = parts(surface)
    if not any(k for _, k in ps):
        return [(surface, None)], False
    if len(ps) == 1:
        return [(surface, reading)], False
    pat = "".join("(.+?)" if k else re.escape(hira(s)) for s, k in ps)
    greedy = pat.replace("(.+?)", "(.+)")
    a, b = re.fullmatch(pat, reading), re.fullmatch(greedy, reading)
    if not a:
        return None, True
    out, g = [], iter(a.groups())
    for s, k in ps:
        out.append((s, next(g) if k else None))
    return out, a.groups() != b.groups()


class Gen:
    def __init__(self):
        from sudachipy import dictionary, tokenizer
        import pykakasi
        self.tok = dictionary.Dictionary(dict="core").create()
        self.C, self.A = tokenizer.Tokenizer.SplitMode.C, tokenizer.Tokenizer.SplitMode.A
        self.kks = pykakasi.kakasi()

    def segs(self, sentence):
        """문장 → [(조각, 읽기|None)] (한자 덩어리마다 읽기), 표시 목록."""
        out, flags = [], set()
        for m in self.tok.tokenize(sentence, self.C):
            surf = m.surface()
            if not KANJI_RUN.search(surf):
                out.append((surf, None))
                continue
            subs = m.split(self.A)
            units = [(x.surface(), hira(x.reading_form())) for x in subs]
            if len(units) < 2 or "".join(r for _, r in units) != hira(m.reading_form()):
                units = [(surf, hira(m.reading_form()))]
            for s, r in units:
                al, amb = align(s, r)
                if al is None:   # 읽기를 표기에 맞출 수 없음 → 덩어리마다 통째로 두고 검토
                    flags.add("정렬 모호")
                    al = [(p, r if k else None) for p, k in parts(s)]
                elif amb:
                    flags.add("정렬 모호")
                out.extend(al)
        return out, flags

    def kakasi_runs(self, sentence):
        """pykakasi 기준 한자 덩어리 (시작 위치, 끝 위치) → 읽기."""
        runs, pos = {}, 0
        for it in self.kks.convert(sentence):
            orig, rd = it["orig"], it["hira"]
            al, _ = align(orig, rd)
            p = pos
            for s, r in al or [(orig, None)]:
                if r is not None and KANJI_RUN.fullmatch(s):
                    runs[(p, p + len(s))] = r
                p += len(s)
            pos += len(orig)
        return runs


def to_raw(segs):
    return "".join(f"{s}{{{r}}}" if r is not None else s for s, r in segs)


def seg_runs(segs):
    runs, p = {}, 0
    for s, r in segs:
        if r is not None:
            runs[(p, p + len(s))] = r
        p += len(s)
    return runs


def head_span(row):
    """예문(plain) 안 표제어 구간과 그 구간의 기대 읽기. 표제어가 글자 그대로 없으면 None."""
    w, r, p, ex = row["w"], row["r"], row["p"], row["plain"]
    i = ex.find(w)
    if i < 0 or not KANJI_RUN.search(w):
        return None
    return i, i + len(w), w, r


def force_head(segs, row):
    """표제어 구간을 data 2열 읽기로 맞춘다. (새 조각들, 바꿨는가, 맞출 수 있었는가)"""
    hs = head_span(row)
    if not hs:
        return segs, False, True
    a, b, w, r = hs
    al, _ = align(w, r)
    if al is None:
        return segs, False, False
    kan = [(s, rd) for s, rd in al if rd is not None]
    pre = post = None
    lo, hi, p = a, b, 0
    for s, rd in segs:
        x, y = p, p + len(s)
        p = y
        if rd is None or y <= a or x >= b:
            continue
        lo, hi = min(lo, x), max(hi, y)
        if x < a and y > b:
            return segs, False, False          # 표제어가 덩어리 한가운데
        if x < a:                              # 앞에서 걸침: 덩어리 뒷부분이 표제어 첫 한자 덩어리
            h = kan[0]
            if row["plain"][a:y] != h[0] or not rd.endswith(h[1]) or rd == h[1]:
                return segs, False, False
            pre = (row["plain"][x:a], rd[: -len(h[1])])
        if y > b:                              # 뒤에서 걸침
            h = kan[-1]
            if row["plain"][x:b] != h[0] or not rd.startswith(h[1]) or rd == h[1]:
                return segs, False, False
            post = (row["plain"][b:y], rd[len(h[1]):])
    mid = ([pre] if pre else []) + list(al) + ([post] if post else [])
    out, p, done = [], 0, False
    for s, rd in segs:
        x, y = p, p + len(s)
        p = y
        if y <= lo or x >= hi:
            out.append((s, rd))
        elif x < lo or y > hi:                 # 가나 조각이 구간 경계를 넘음 → 바깥 부분만 남긴다
            if x < lo:
                out.append((s[: lo - x], None))
            if not done:
                out.extend(mid)
                done = True
            if y > hi:
                out.append((s[hi - x:], None))
        elif not done:
            out.extend(mid)
            done = True
    merged = []
    for s, rd in out:
        if rd is None and merged and merged[-1][1] is None:
            merged[-1] = (merged[-1][0] + s, None)
        else:
            merged.append((s, rd))
    return merged, to_raw(merged) != to_raw(segs), True


def load_rows():
    rows, errors = validate.load()
    if errors:
        sys.exit(f"validate 오류 {len(errors)}건 — 먼저 고친다")
    for r in rows:
        r["plain"] = plain(r["ex"])
    return rows


def load_fix():
    fix = {}
    if FIX.exists():
        for line in FIX.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.startswith("#"):
                k, *v = line.split("\t")
                fix.setdefault(k, []).append(v)
    return fix


def apply_fix(raw, fixes):
    """수정 한 줄: 값 하나면 문장 전체, 둘이면 (바꿀 부분 → 새 부분) 첫 번째 것 치환."""
    for f in fixes:
        if len(f) == 1:
            raw = f[0]
        elif f[0] in raw:
            raw = raw.replace(f[0], f[1], 1)
        else:
            sys.exit(f"furigana_fix.txt: '{f[0]}' 가 {raw} 에 없음")
    return raw


def spans(runs):
    """붙어 있는 덩어리를 합쳐 최대 한자 구간 → 이어 붙인 읽기 (분석기마다 덩어리 경계가 달라도 비교되게)."""
    out, cur = {}, None
    for (x, y) in sorted(runs):
        if cur and cur[1] == x:
            cur = (cur[0], y, cur[2] + runs[(x, y)])
        else:
            if cur:
                out[cur[:2]] = cur[2]
            cur = (x, y, runs[(x, y)])
    if cur:
        out[cur[:2]] = cur[2]
    return out


def key(row):
    return f"{row['w']}|{row['r']}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / ".omc/research/furigana_draft.tsv"))
    ap.add_argument("--report", default=str(ROOT / ".omc/research/furigana_review.md"))
    args = ap.parse_args()
    rows, gen, fix = load_rows(), Gen(), load_fix()
    results = []
    for row in rows:
        segs, flags = gen.segs(row["plain"])
        sud = to_raw(segs)
        segs, forced, ok = force_head(segs, row)
        if forced or not ok:
            flags.add("표제어 구간")
        kr, sr = spans(gen.kakasi_runs(row["plain"])), spans(seg_runs(segs))
        diffs = [(row["plain"][x:y], sr[(x, y)], kr.get((x, y), "?")) for (x, y) in sorted(sr) if kr.get((x, y)) != sr[(x, y)]]
        if diffs:
            flags.add("불일치")
        if any(NUM.search(row["plain"][x:y]) for x, y in sr) or re.search(rf"[0-9０-９][{KANJI}]", row["plain"]):
            flags.add("숫자·조수사")
        solo = {row["plain"][x:y] for x, y in sr}   # 한 글자 항목은 그 글자 하나로 된 구간일 때만
        if any((j in row["plain"]) if len(j) > 1 else (j in solo) for j in JUKU):
            flags.add("숙자훈")
        raw = first = to_raw(segs)
        for a, b in GLOBAL:
            raw = raw.replace(a, b)
        fixed = fix.get(key(row))
        if fixed is not None:
            raw = apply_fix(raw, fixed)
            if plain(raw) != row["plain"]:
                sys.exit(f"furigana_fix.txt 의 {key(row)} 를 벗기면 예문과 다름: {raw}")
        results.append({**row, "raw": raw, "sudachi": sud, "flags": flags, "diffs": diffs, "fixed": raw != first})

    bad = [r for r in results if plain(r["raw"]) != r["plain"]]
    Path(args.out).write_text("".join(f"{key(r)}\t{r['raw']}\n" for r in results), encoding="utf-8")
    write_report(results, Path(args.report))
    print(f"문장 {len(results)}개 · 벗긴 문장 불일치 {len(bad)}개 · 수정 반영 {sum(r['fixed'] for r in results)}개")
    for f in ORDER:
        print(f"  {f}: {sum(f in r['flags'] for r in results)}")
    print("저장:", args.out, args.report)
    if bad:
        sys.exit(1)


# 사전 읽기가 학습용으로 어색한 것 — 모든 문장에 적용 (검토 결과)
GLOBAL = [("私{わたくし}", "私{わたし}"), ("言{ゆ}", "言{い}"), ("日本{にっぽん}", "日本{にほん}"), ("明日{あす}", "明日{あした}"),
          ("一{いち}週間{しゅうかん}", "一{いっ}週間{しゅうかん}"), ("一{いち}か月{げつ}", "一{いっ}か月{げつ}"),
          ("三百{さんひゃく}", "三百{さんびゃく}"), ("三千{さんせん}", "三千{さんぜん}"), ("九{きゅう}時{じ}", "九{く}時{じ}"),
          ("九{きゅう}月{がつ}", "九{く}月{がつ}"), ("四{よん}年{ねん}", "四{よ}年{ねん}"),
          ("一{いち}日{にち}中{ちゅう}", "一日中{いちにちじゅう}"), ("一{いち}年{ねん}中{ちゅう}", "一年中{いちねんじゅう}"),
          ("一{いち}日{にち}", "一日{いちにち}"), ("一{いち}番{ばん}", "一番{いちばん}")]

ORDER = ["정렬 모호", "불일치", "숫자·조수사", "숙자훈", "표제어 구간"]


def write_report(results, path):
    def group(r):
        for i, f in enumerate(ORDER):
            if f in r["flags"]:
                return i
        return len(ORDER)
    names = ORDER + ["나머지"]
    lines = ["# 예문 후리가나 전수 검토", "",
             f"문장 {len(results)}개. 우선순위 ① 정렬 모호 ② 분석기 불일치(Sudachi↔pykakasi) ③ 숫자·조수사 ④ 숙자훈 목록 ⑤ 표제어 구간 ⑥ 나머지.",
             "한 문장은 가장 높은 우선순위 한 곳에만 나온다. 「검토」 칸: 확정 = 1차안 그대로, 수정 = 일괄 규칙(GLOBAL) 또는 tools/furigana_fix.txt 로 고침.",
             "검토 방법(2026-10-21): ①~⑤ 는 문장마다 문맥을 읽고 판단, ⑥ 은 전체 낱자 루비 읽기 목록(글자별 읽기 종류)을 훑어 이상한 읽기를 문맥 확인.",
             "일괄 규칙: " + ", ".join(f"{a}→{b}" for a, b in GLOBAL), ""]
    for gi, name in enumerate(names):
        rs = [r for r in results if group(r) == gi]
        lines += [f"## {'①②③④⑤⑥'[gi]} {name} — {len(rs)}개", "", "| 단어 | 루비 | 표시 | 검토 |", "|---|---|---|---|"]
        for r in rs:
            note = "; ".join(f"{s}: {a}↔{b}" for s, a, b in r["diffs"])
            flags = ", ".join(f for f in ORDER if f in r["flags"]) + (f" ({note})" if note else "")
            review = "수정" if r["fixed"] else "확정"
            lines.append(f"| {r['w']} | {r['raw'].replace('|', '｜')} | {flags} | {review} |")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
