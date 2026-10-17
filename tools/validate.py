"""N2 단어 데이터(data/*.txt, | 구분) 검사기.

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


def stem(word, pos):
    """예문에서 찾을 표제어 조각. 활용하는 품사는 어미를 뗀다."""
    if pos == "v":
        return word[:-1]
    if pos == "i":
        return word[:-1]
    return word


def load():
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
            w, r, p, m, ex, ko = (c.strip() for c in cols)
            if not all((w, r, p, m, ex, ko)):
                errors.append(f"{where} 빈 칸: {w}")
            if p not in POS:
                errors.append(f"{where} 품사 코드 '{p}': {w}")
            if p == "kata":
                if not KATA.match(r):
                    errors.append(f"{where} 가타카나어 읽기가 가타카나가 아님 '{r}': {w}")
            elif not HIRA.match(r):
                errors.append(f"{where} 읽기가 히라가나가 아님 '{r}': {w}")
            if stem(w, p) not in ex and stem(r, p) not in ex:
                errors.append(f"{where} 예문에 표제어 없음 '{w}': {ex}")
            if not HANGUL.search(m) or not HANGUL.search(ko):
                errors.append(f"{where} 한국어 뜻/번역 누락: {w}")
            if len(m) > 40:
                errors.append(f"{where} 뜻이 너무 김({len(m)}자): {w}")
            if not END.search(ex):
                errors.append(f"{where} 예문 끝 문장부호 없음: {ex}")
            rows.append({"w": w, "r": r, "p": p, "m": m, "ex": ex, "ko": ko, "_at": where})
    seen = {}
    for row in rows:
        key = (row["w"], row["r"])
        if key in seen:
            errors.append(f"{row['_at']} 중복 단어 '{row['w']}' (처음: {seen[key]})")
        else:
            seen[key] = row["_at"]
    return rows, errors


def main():
    rows, errors = load()
    counts = {}
    for row in rows:
        counts[row["p"]] = counts.get(row["p"], 0) + 1
    print(f"단어 {len(rows)}개 · " + " ".join(f"{k}={v}" for k, v in sorted(counts.items())))
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
