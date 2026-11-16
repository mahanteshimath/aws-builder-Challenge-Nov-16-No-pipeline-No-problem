"""GET /, /assets/{file} and a branded 404. The static site ships inside the package under web/."""
import base64
import gzip
import hashlib
from pathlib import Path

WEB = Path(__file__).parent / "web"
TYPES = {".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml",
         ".woff2": "font/woff2", ".txt": "text/plain; charset=utf-8", ".html": "text/html; charset=utf-8"}
TEXTUAL = {".css", ".js", ".svg", ".txt", ".html"}
PAGES = {"index.html", "404.html"}
SECURITY = {
    "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; font-src 'self'; "
                               "img-src 'self' data:; connect-src 'self'; frame-src 'self'; frame-ancestors 'self'; "
                               "base-uri 'none'; form-action 'none'",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Vary": "Accept-Encoding",
}

_files = {p.name: p.read_bytes() for p in WEB.iterdir() if p.is_file()}
VERSION = hashlib.sha256(b"".join(_files[k] for k in sorted(_files))).hexdigest()[:10]


def _entry(name, data):
    ext = Path(name).suffix
    if name in PAGES:
        data = data.replace(b"__V__", VERSION.encode())
    return {"type": TYPES[ext], "raw": data, "gz": gzip.compress(data, 9, mtime=0) if ext in TEXTUAL else None}


_assets = {n: _entry(n, d) for n, d in _files.items()}


def _respond(code, entry, accept, cache):
    headers = {"Content-Type": entry["type"], "Cache-Control": cache, **SECURITY}
    if entry["gz"] is not None and "gzip" in accept:
        headers["Content-Encoding"] = "gzip"
        body, b64 = base64.b64encode(entry["gz"]).decode(), True
    elif entry["gz"] is None:
        body, b64 = base64.b64encode(entry["raw"]).decode(), True
    else:
        body, b64 = entry["raw"].decode(), False
    return {"statusCode": code, "body": body, "isBase64Encoded": b64, "headers": headers}


def handler(event, ctx):
    accept = (event.get("headers") or {}).get("accept-encoding", "")
    path = event.get("rawPath", "/")
    if path == "/":
        return _respond(200, _assets["index.html"], accept, "no-cache")
    name = path[len("/assets/"):] if path.startswith("/assets/") else "favicon.svg" if path == "/favicon.ico" else ""
    if name and name not in PAGES and name in _assets:
        return _respond(200, _assets[name], accept, "public, max-age=31536000, immutable")
    return _respond(404, _assets["404.html"], accept, "no-store")
