"""N2 단어 데이터(data/*.txt, | 구분) 검사기.

예문(5열)은 루비 표기: その件{けん}はもう済{す}みです — {} 앞의 연속 한자 덩어리에 히라가나 읽기를 붙인다.

사용법: python tools/validate.py            → data/*.txt 전체 검사, 오류가 있으면 종료코드 1
       python tools/validate.py --json OUT  → 검사 통과 시 단어 배열을 JSON으로 저장
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
POS = {"n", "vs", "v", "i", "na", "adv", "kata", "etc"}
HIRA = re.compile(r"^[ぁ-ゖー]+$")
KATA = re.compile(r"^[ァ-ヺー・]+$")
HANGUL = re.compile(r"[가-힣]")
END = re.compile(r"[。？！」]$")
KANJI = "\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff々〆ヶ"
KANJI_RUN = re.compile(f"[{KANJI}]+")
RUBY = re.compile(rf"([{KANJI}]+)\{{([^{{}}]*)\}}")


def plain(raw):
    """루비 표기를 벗긴 문장 (app.html 의 plain() 과 같은 규칙)."""
    return RUBY.sub(r"\1", raw)


def hira(s):
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def ruby_errors(raw):
    """(b) 루비 없는 한자 (c) {} 안 히라가나만·빈 {} 금지·중괄호 짝/위치."""
    errs = []
    for base, rt in RUBY.findall(raw):
        if not rt:
            errs.append(f"빈 {{}}: {base}")
        elif not HIRA.match(rt):
            errs.append(f"{{}} 안이 히라가나가 아님: {base}{{{rt}}}")
    rest = RUBY.sub("", raw)
    if "{" in rest or "}" in rest:
        errs.append("중괄호 짝·위치가 맞지 않음")
    bare = KANJI_RUN.findall(rest)
    if bare:
        errs.append("루비 없는 한자: " + " ".join(bare))
    return errs


def spans(raw):
    """plain 기준 루비 덩어리 [(시작, 끝, 읽기)] 와 글자별 읽기 문자열 함수."""
    out, pos, i = [], 0, 0
    for m in RUBY.finditer(raw):
        pos += m.start() - i
        out.append((pos, pos + len(m.group(1)), m.group(2)))
        pos += len(m.group(1))
        i = m.end()
    return out


def reading_of(raw, a, b):
    """plain[a:b] 구간의 읽기. 루비 덩어리가 구간 경계에 걸치면 None."""
    text, rs, out, p = plain(raw), spans(raw), "", a
    for x, y, rt in rs:
        if y <= a or x >= b:
            continue
        if x < a or y > b:
            return None
        out += text[p:x] + rt
        p = y
    return hira(out + text[p:b])


def head_check(w, r, p, raw):
    """(d) 표제어 구간이 루비 덩어리 경계와 맞고 읽기가 2열과 같은가. (오류, 경고)"""
    if p == "kata" or not KANJI_RUN.search(w):
        return None, None
    text = plain(raw)
    i = text.find(w)
    if i >= 0:
        got = reading_of(raw, i, i + len(w))
        if got is None:
            return f"표제어 구간이 루비 덩어리와 어긋남 '{w}'", None
        if got != hira(r) and not re.search(r"[0-9０-９]", w):   # 숫자에는 루비를 달 수 없다
            return f"표제어 읽기 '{got}' ≠ 2열 '{r}'", None
        return None, None
    st, sr = stem(w, p), stem(r, p)
    i = text.find(st) if st != w and KANJI_RUN.search(st) else -1
    if i < 0:
        return None, None
    got = reading_of(raw, i, i + len(st))
    if got != hira(sr):
        return None, f"활용형 어간 읽기 '{got}' ≠ '{sr}' ('{w}')"
    return None, None


def stem(word, pos):
    """예문에서 찾을 표제어 조각. 활용하는 품사는 어미를 뗀다."""
    if pos == "v":
        return word[:-1]
    if pos == "i":
        return word[:-1]
    return word


def mixed_ok(word, reading):
    """クリーム状(クリームじょう)처럼 표제어에 가타카나가 섞이면, 그 가타카나 덩어리는 읽기에 그대로 둔다."""
    kata = re.findall(r"[ァ-ヺー]+", word)
    if not kata or not re.fullmatch(r"[ぁ-ゖァ-ヺー]+", reading):
        return False
    rest = reading
    for k in kata:
        if k not in rest:
            return False
        rest = rest.replace(k, "", 1)
    return bool(HIRA.match(rest)) if rest else True


def kichul_keys():
    """data/kichul.list 의 기출 단어 키(단어|읽기) 집합."""
    path = DATA / "kichul.list"
    if not path.exists():
        return set()
    return {l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")}


def load(warnings=None):
    rows, errors = [], []
    for path in sorted(DATA.glob("*.txt")):
        for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip() or line.startswith("#"):
                continue
            where = f"{path.name}:{no}"
            cols = line.split("|")
            if len(cols) != 6:
                errors.append(f"{where} 칸 수 {len(cols)} (6이어야 함): {line[:40]}")
                continue
            w, r, p, m, exr, ko = (c.strip() for c in cols)
            ex = plain(exr)
            if not all((w, r, p, m, ex, ko)):
                errors.append(f"{where} 빈 칸: {w}")
            if p not in POS:
                errors.append(f"{where} 품사 코드 '{p}': {w}")
            if p == "kata":
                if not KATA.match(r):
                    errors.append(f"{where} 가타카나어 읽기가 가타카나가 아님 '{r}': {w}")
            elif not HIRA.match(r) and not mixed_ok(w, r):
                errors.append(f"{where} 읽기가 히라가나가 아님 '{r}': {w}")
            if stem(w, p) not in ex and stem(r, p) not in ex:
                errors.append(f"{where} 예문에 표제어 없음 '{w}': {ex}")
            if not HANGUL.search(m) or not HANGUL.search(ko):
                errors.append(f"{where} 한국어 뜻/번역 누락: {w}")
            if len(m) > 40:
                errors.append(f"{where} 뜻이 너무 김({len(m)}자): {w}")
            if not END.search(ex):
                errors.append(f"{where} 예문 끝 문장부호 없음: {ex}")
            errors.extend(f"{where} 예문 루비 {e}: {w}" for e in ruby_errors(exr))
            err, warn = head_check(w, r, p, exr)
            if err:
                errors.append(f"{where} {err}: {exr}")
            if warn and warnings is not None:
                warnings.append(f"{where} {warn}: {exr}")
            rows.append({"w": w, "r": r, "p": p, "m": m, "ex": exr, "ko": ko, "_at": where})
    seen = {}
    for row in rows:
        key = (row["w"], row["r"])
        if key in seen:
            errors.append(f"{row['_at']} 중복 단어 '{row['w']}' (처음: {seen[key]})")
        else:
            seen[key] = row["_at"]
    for k in sorted(kichul_keys() - set(f"{w}|{r}" for w, r in seen)):
        errors.append(f"kichul.list 의 '{k}' 가 단어 데이터에 없음")
    return rows, errors


def main():
    warnings = []
    rows, errors = load(warnings)
    counts = {}
    for row in rows:
        counts[row["p"]] = counts.get(row["p"], 0) + 1
    print(f"단어 {len(rows)}개 · " + " ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    for e in warnings:
        print("경고:", e)
    for e in errors:
        print("오류:", e)
    if errors:
        print(f"오류 {len(errors)}건")
        sys.exit(1)
    print("검사 통과")
    if "--json" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--json") + 1])
        data = [{k: v for k, v in row.items() if k != "_at"} for row in rows]
        out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print("저장:", out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
