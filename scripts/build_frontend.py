"""Builds the Mini App page from frontend/app.html.

    python -m scripts.build_frontend

Outputs:
  static/index.html   served by FastAPI at "/" (loads the Telegram SDK)
  dist/preview.html   standalone browser preview with images embedded (runs in demo mode)
"""
import base64
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "frontend" / "app.html"

HEAD = """<!doctype html>
<html lang="ka">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, user-scalable=no">
<script src="https://telegram.org/js/telegram-web-app.js"></script>
"""


def main() -> None:
    src = SRC.read_text(encoding="utf-8")
    head, body = src.split("<!--BODY-->", 1)

    (ROOT / "static" / "index.html").write_text(f"{HEAD}{head}</head>\n<body>{body}</body>\n</html>\n", encoding="utf-8")

    def inline(m: re.Match) -> str:
        path = ROOT / m.group(1)
        return "data:image/webp;base64," + base64.b64encode(path.read_bytes()).decode()

    preview = re.sub(r"(static/img/[\w/.-]+\.webp)", inline, src).replace("<!--BODY-->", "")
    (ROOT / "dist").mkdir(exist_ok=True)
    (ROOT / "dist" / "preview.html").write_text(preview, encoding="utf-8")
    print("built static/index.html and dist/preview.html")


if __name__ == "__main__":
    main()
