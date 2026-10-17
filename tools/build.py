"""배포본 만들기: 데이터 검사 → src/app.html 에 단어 주입 → dist/ 에 앱 파일 모으기.

사용법: python tools/build.py
아이콘 PNG(src/icon-192.png, src/icon-512.png)는 src/icon.html 을 브라우저로 찍어 미리 만들어 둔다.
"""
import hashlib
import json
import shutil
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
DIST = ROOT / "dist"


def main():
    rows, errors = validate.load()
    if errors:
        for e in errors:
            print("오류:", e)
        sys.exit(f"데이터 오류 {len(errors)}건 — 빌드 중단")

    vocab = [[r["w"], r["r"], r["p"], r["m"], r["ex"], r["ko"]] for r in rows]
    # <script> 안에 넣으므로 "</script>" 가 생기지 않게 < 를 이스케이프한다
    vocab_json = json.dumps(vocab, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    app = (SRC / "app.html").read_text(encoding="utf-8")
    sw = (SRC / "sw.js").read_text(encoding="utf-8")
    h = hashlib.sha1((vocab_json + app + sw).encode("utf-8"))
    for name in ("manifest.webmanifest", "icon-192.png", "icon-512.png"):
        if (SRC / name).exists():
            h.update((SRC / name).read_bytes())
    digest = h.hexdigest()[:7]
    version = f"{date.today():%y%m%d}-{digest}"

    marker = "/*__VOCAB__*/[]"
    if app.count(marker) != 1:
        sys.exit("app.html 에 단어 자리표시(/*__VOCAB__*/[])가 정확히 1개 있어야 함")
    app = app.replace(marker, vocab_json).replace("__VERSION__", version)

    DIST.mkdir(exist_ok=True)
    (DIST / "index.html").write_text(app, encoding="utf-8")
    (DIST / "sw.js").write_text(sw.replace("__VERSION__", version), encoding="utf-8")
    shutil.copy(SRC / "manifest.webmanifest", DIST / "manifest.webmanifest")
    for name in ("icon-192.png", "icon-512.png"):
        if not (SRC / name).exists():
            sys.exit(f"{name} 없음 — src/icon.html 로 먼저 만든다")
        shutil.copy(SRC / name, DIST / name)
    (DIST / ".nojekyll").write_text("", encoding="utf-8")

    size = (DIST / "index.html").stat().st_size
    print(f"빌드 완료: 단어 {len(rows)}개 · 버전 {version} · index.html {size / 1024:.0f}KB")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
