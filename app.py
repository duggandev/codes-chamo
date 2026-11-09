import os
import re
from html import escape
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from dotenv import load_dotenv
from flask import Flask, Response, abort, request, send_from_directory


PROJECT_ROOT = Path(__file__).resolve().parent
STATIC_ROOT = PROJECT_ROOT / "static"

load_dotenv(PROJECT_ROOT / ".env")

TARGET_URL = (os.getenv("web") or os.getenv("WEB") or "").strip().rstrip("/")
if not TARGET_URL:
    raise RuntimeError("Falta la variable 'web' en el archivo .env")

target_parts = urlsplit(TARGET_URL)
if target_parts.scheme not in {"http", "https"} or not target_parts.netloc:
    raise RuntimeError("La variable 'web' debe contener una URL http:// o https:// valida")

TARGET_ORIGIN = urlunsplit((target_parts.scheme, target_parts.netloc, "", "", ""))
TARGET_ROOT_PATH = target_parts.path.rstrip("/")
VERIFY_SSL = os.getenv("VERIFY_SSL", "true").lower() not in {"0", "false", "no"}
BUSINESS_NAME = (os.getenv("NombreNegocio") or "CodeFlix").strip() or "CodeFlix"

app = Flask(__name__)
session = requests.Session()

HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}

# Estas cabeceras pertenecen a la web original y suelen impedir que el contenido
# funcione al servirse desde otro origen.
RESPONSE_HEADERS_TO_DROP = HOP_BY_HOP_HEADERS | {
    "content-length",
    "content-encoding",
    "content-security-policy",
    "content-security-policy-report-only",
    "cross-origin-embedder-policy",
    "cross-origin-opener-policy",
    "cross-origin-resource-policy",
    "report-to",
    "nel",
    "strict-transport-security",
    "x-frame-options",
}


def upstream_url(path: str) -> str:
    """Mapea una ruta local a la misma ruta del servidor configurado."""
    if not path:
        url = TARGET_URL + "/"
    else:
        # Las rutas del navegador empiezan en la raiz del host remoto. Si la URL
        # configurada incluye un prefijo, se conserva tambien en rutas relativas.
        prefix = TARGET_ROOT_PATH if TARGET_ROOT_PATH and request.path.startswith(TARGET_ROOT_PATH + "/") else ""
        url = f"{TARGET_ORIGIN}{prefix}/{path.lstrip('/')}"
    if request.query_string:
        url += "?" + request.query_string.decode("latin-1")
    return url


def localize_url(value: str) -> str:
    """Convierte URLs del mismo servidor en rutas que pasan por este proxy."""
    if not value:
        return value
    absolute = urljoin(TARGET_URL + "/", value)
    parts = urlsplit(absolute)
    if parts.scheme in {"http", "https"} and parts.netloc == target_parts.netloc:
        return urlunsplit(("", "", parts.path or "/", parts.query, parts.fragment))
    return value


def rewrite_body(body: bytes, content_type: str) -> bytes:
    textual = any(
        kind in content_type.lower()
        for kind in ("text/html", "text/css", "javascript", "application/json", "application/xml", "image/svg+xml")
    )
    if not textual:
        return body

    charset_match = re.search(r"charset=([\w.-]+)", content_type, flags=re.I)
    charset = charset_match.group(1) if charset_match else "utf-8"
    try:
        text = body.decode(charset)
    except (LookupError, UnicodeDecodeError):
        text = body.decode("utf-8", errors="replace")
        charset = "utf-8"

    # Cubre URLs absolutas escritas en HTML, CSS, JavaScript y JSON. Las rutas
    # relativas y las que empiezan por / ya son capturadas por Flask.
    origins = {
        TARGET_ORIGIN,
        TARGET_ORIGIN.replace("https://", "http://", 1),
        TARGET_ORIGIN.replace("http://", "https://", 1),
        TARGET_ORIGIN.replace("/", r"\/"),
    }
    for origin in sorted(origins, key=len, reverse=True):
        text = text.replace(origin, "")

    # El nombre visible de la plataforma se administra desde .env y se aplica
    # tanto al HTML como a scripts, estilos y respuestas JSON textuales.
    text = text.replace("CodeFlix", BUSINESS_NAME)

    # Una etiqueta <base> remota haria que el navegador se saltara el proxy.
    text = re.sub(r"<base\b[^>]*>", "", text, flags=re.I)

    if "text/html" in content_type.lower():
        # El titulo de la pestaña siempre usa el nombre configurado del negocio.
        business_title = escape(BUSINESS_NAME, quote=False)
        if re.search(r"<title\b", text, flags=re.I):
            text = re.sub(
                r"<title\b[^>]*>.*?</title\s*>",
                f"<title>{business_title}</title>",
                text,
                count=1,
                flags=re.I | re.S,
            )
        else:
            text = re.sub(
                r"<head\b[^>]*>",
                lambda match: match.group(0) + f"\n<title>{business_title}</title>",
                text,
                count=1,
                flags=re.I,
            )

        # Usa siempre el favicon local, aunque el sitio remoto declare otro.
        text = re.sub(
            r'<link\b(?=[^>]*\brel=["\'][^"\']*(?:icon|shortcut icon)[^"\']*["\'])[^>]*>',
            "",
            text,
            flags=re.I,
        )
        local_head = (
            '<meta name="theme-color" content="#0b0b0d">\n'
            '<meta name="mobile-web-app-capable" content="yes">\n'
            '<meta name="apple-mobile-web-app-capable" content="yes">\n'
            '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">\n'
            '<link rel="icon" href="/favicon.ico" type="image/x-icon">\n'
            '<link rel="stylesheet" href="/mobile-theme.css">\n'
            '<script src="/mobile-app.js" defer></script>'
        )
        text = re.sub(r"</head\s*>", local_head + "\n</head>", text, count=1, flags=re.I)

        # Personalizacion de la pantalla de acceso de CodeFlix: el formulario
        # conserva internamente el rol reseller, pero no muestra el selector.
        text = re.sub(
            r'<div\b[^>]*\bclass=["\'][^"\']*\brole-selector\b[^"\']*["\'][^>]*>.*?</div>',
            "",
            text,
            flags=re.I | re.S,
        )
        text = re.sub(
            r"\b(let|var)\s+selectedRole\s*=\s*([\"\']).*?\2\s*;",
            r"\1 selectedRole = 'reseller';",
            text,
            count=1,
            flags=re.I,
        )
    return text.encode(charset, errors="replace")


def request_headers() -> dict[str, str]:
    headers = {}
    for name, value in request.headers.items():
        lower = name.lower()
        if lower in HOP_BY_HOP_HEADERS or lower in {"host", "content-length", "accept-encoding"}:
            continue
        if lower == "origin":
            value = TARGET_ORIGIN
        elif lower == "referer":
            value = urljoin(TARGET_URL + "/", request.path.lstrip("/"))
        headers[name] = value
    headers["Accept-Encoding"] = "identity"
    return headers


@app.get("/favicon.ico")
def favicon():
    return send_from_directory(
        STATIC_ROOT,
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon",
        max_age=86400,
    )


@app.get("/mobile-theme.css")
def mobile_theme():
    return send_from_directory(
        STATIC_ROOT / "css",
        "mobile-theme.css",
        mimetype="text/css",
        max_age=3600,
    )


@app.get("/mobile-app.js")
def mobile_app_script():
    return send_from_directory(
        STATIC_ROOT / "js",
        "mobile-app.js",
        mimetype="application/javascript",
        max_age=3600,
    )


def copy_response_headers(upstream: requests.Response, response: Response) -> None:
    for name, value in upstream.headers.items():
        if name.lower() not in RESPONSE_HEADERS_TO_DROP and name.lower() not in {"set-cookie", "location"}:
            response.headers[name] = value

    if "Location" in upstream.headers:
        response.headers["Location"] = localize_url(upstream.headers["Location"])

    # requests combina algunas cabeceras en el diccionario normal; urllib3
    # permite conservar cada Set-Cookie por separado.
    raw_headers = getattr(upstream.raw, "headers", None)
    cookies = raw_headers.getlist("Set-Cookie") if raw_headers and hasattr(raw_headers, "getlist") else []
    for cookie in cookies:
        cookie = re.sub(r";\s*Domain=[^;]+", "", cookie, flags=re.I)
        if request.scheme != "https":
            cookie = re.sub(r";\s*Secure\b", "", cookie, flags=re.I)
        response.headers.add("Set-Cookie", cookie)


@app.route("/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
@app.route("/<path:path>", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
def proxy(path: str) -> Response:
    try:
        upstream = session.request(
            method=request.method,
            url=upstream_url(path),
            headers=request_headers(),
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            timeout=(10, 60),
            verify=VERIFY_SSL,
            stream=True,
        )
    except requests.RequestException as exc:
        app.logger.warning("No se pudo contactar al servidor remoto: %s", exc.__class__.__name__)
        abort(502, description="No se pudo contactar al servidor remoto")

    body = upstream.raw.read(decode_content=True)
    content_type = upstream.headers.get("Content-Type", "application/octet-stream")
    body = rewrite_body(body, content_type)
    response = Response(body, status=upstream.status_code, content_type=content_type)
    copy_response_headers(upstream, response)
    return response


if __name__ == "__main__":
    app.run(
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("DEBUG", "false").lower() in {"1", "true", "yes"},
    )
