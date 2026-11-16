"""GET /: serves the single-page board (workers, supervisor and read-only viewers)."""
from pathlib import Path

_HTML = (Path(__file__).parent / "ui.html").read_text(encoding="utf-8")


def handler(event, ctx):
    return {"statusCode": 200, "body": _HTML, "headers": {
        "Content-Type": "text/html; charset=utf-8",
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
        "Content-Security-Policy": "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
                                   "connect-src 'self'; frame-ancestors 'none'",
    }}
