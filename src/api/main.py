"""FastAPI and Standard Library HTTP Application for Since AI.

Target: Google Cloud Run in europe-north1 (Hamina, Finland) and Local Development.
"""

import json
import logging
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict

from src.api.routes_chat import (
    handle_chat_message,
    handle_consent_update,
    handle_create_session,
    handle_health_check,
)
from src.api.routes_analysis import (
    handle_analyze_request,
    handle_classify_sms,
)

logger = logging.getLogger(__name__)

# Attempt to define FastAPI app if installed
app = None
try:
    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, JSONResponse

    app = FastAPI(
        title="Since AI — DNA Digital Security Assistant API",
        version="1.0.0",
        description="Grounded, deterministic cybersecurity assistant running in europe-north1 (Finland).",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/v1/health")
    async def health_check():
        return handle_health_check()

    @app.post("/api/v1/sessions")
    async def create_session(request: Request):
        payload = await request.json()
        return handle_create_session(payload)

    @app.post("/api/v1/chat")
    async def chat(request: Request):
        payload = await request.json()
        return handle_chat_message(payload)

    @app.post("/api/v1/analyze")
    async def analyze(request: Request):
        payload = await request.json()
        return handle_analyze_request(payload)

    @app.post("/api/classify")
    @app.post("/api/v1/classify")
    async def classify(request: Request):
        payload = await request.json()
        return handle_classify_sms(payload)

    @app.post("/api/v1/consent")
    async def consent(request: Request):
        payload = await request.json()
        return handle_consent_update(payload)

    index_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "../../frontend/.output/public/index.html"))
    demo_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "../../demo.html"))

    @app.get("/")
    @app.get("/index.html")
    @app.get("/demo")
    @app.get("/demo.html")
    async def serve_phone_simulator():
        if os.path.exists(index_path):
            return FileResponse(index_path)
        if os.path.exists(demo_path):
            return FileResponse(demo_path)
        return JSONResponse({"error": "phone_simulator_not_found"}, status_code=404)

    # Mount static frontend assets from .output/public
    public_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "../../frontend/.output/public"))
    if os.path.exists(public_dir):
        from fastapi.staticfiles import StaticFiles
        assets_dir = os.path.join(public_dir, "assets")
        if os.path.exists(assets_dir):
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
        audio_dir = os.path.join(public_dir, "audio")
        if os.path.exists(audio_dir):
            app.mount("/audio", StaticFiles(directory=audio_dir), name="audio")

    import urllib.request
    import urllib.error

    @app.api_route("/{full_path:path}", methods=["GET", "POST", "HEAD", "OPTIONS"])
    async def proxy_ssr_frontend(request: Request, full_path: str):
        if not full_path or full_path in ("index.html", "demo", "demo.html"):
            if os.path.exists(index_path):
                return FileResponse(index_path)
            if os.path.exists(demo_path):
                return FileResponse(demo_path)

        if full_path and os.path.exists(public_dir):
            static_file = os.path.join(public_dir, full_path)
            if os.path.isfile(static_file):
                return FileResponse(static_file)

        target_url = f"http://127.0.0.1:3000/{full_path}"
        if request.url.query:
            target_url += f"?{request.url.query}"
        req_body = await request.body()
        req_headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in ("host", "content-length", "connection")
        }
        py_req = urllib.request.Request(
            target_url,
            data=req_body if req_body else None,
            headers=req_headers,
            method=request.method,
        )
        try:
            with urllib.request.urlopen(py_req, timeout=10) as resp:
                content = resp.read()
                resp_headers = {
                    k: v for k, v in resp.headers.items()
                    if k.lower() not in ("transfer-encoding", "content-encoding", "connection")
                }
                from fastapi import Response
                return Response(
                    content=content,
                    status_code=resp.status,
                    headers=resp_headers,
                )
        except urllib.error.HTTPError as e:
            content = e.read()
            from fastapi import Response
            return Response(content=content, status_code=e.code)
        except Exception:
            # Always serve phone simulator on GET requests, never the old fallback
            if request.method == "GET":
                if os.path.exists(index_path):
                    return FileResponse(index_path)
                if os.path.exists(demo_path):
                    return FileResponse(demo_path)
            return JSONResponse({"error": "frontend_unavailable"}, status_code=502)

except ImportError:
    app = None


class SinceAIHttpHandler(SimpleHTTPRequestHandler):
    """Standard library HTTP request handler providing both REST API and static files."""

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/v1/health":
            self._send_json(200, handle_health_check())
        elif self.path in ("/", "/index.html", "/demo", "/demo.html"):
            candidates = [
                os.path.normpath(os.path.join(os.path.dirname(__file__), "../../frontend/.output/public/index.html")),
                os.path.normpath(os.path.join(os.path.dirname(__file__), "../../frontend/index.html")),
                os.path.normpath(os.path.join(os.path.dirname(__file__), "../../demo.html")),
            ]
            for p in candidates:
                if os.path.exists(p):
                    self._send_file(p, "text/html; charset=utf-8")
                    return
            self.send_error(404, "Phone Simulator Not Found")
        else:
            # Check public output directory first, then frontend directory
            public_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "../../frontend/.output/public"))
            rel_path = self.path.lstrip("/")
            file_path = os.path.join(public_dir, rel_path)
            if not (os.path.exists(file_path) and os.path.isfile(file_path)):
                frontend_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "../../frontend"))
                file_path = os.path.join(frontend_dir, rel_path)
            if os.path.exists(file_path) and os.path.isfile(file_path):
                content_type = "text/plain"
                if file_path.endswith(".js"):
                    content_type = "application/javascript"
                elif file_path.endswith(".css"):
                    content_type = "text/css"
                elif file_path.endswith(".html"):
                    content_type = "text/html; charset=utf-8"
                self._send_file(file_path, content_type)
            else:
                self.send_error(404, "Not Found")

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        payload = json.loads(body.decode("utf-8")) if body else {}

        if self.path == "/api/v1/chat":
            result = handle_chat_message(payload)
            self._send_json(200, result)
        elif self.path == "/api/v1/analyze":
            result = handle_analyze_request(payload)
            self._send_json(200, result)
        elif self.path in ("/api/classify", "/api/v1/classify"):
            result = handle_classify_sms(payload)
            self._send_json(200, result)
        elif self.path == "/api/v1/sessions":
            result = handle_create_session(payload)
            self._send_json(200, result)
        elif self.path == "/api/v1/consent":
            result = handle_consent_update(payload)
            self._send_json(200, result)
        else:
            self.send_error(404, "Endpoint Not Found")

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _send_json(self, status_code: int, data: Dict[str, Any]):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _send_file(self, path: str, content_type: str):
        with open(path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(data)


def run_standalone_server(port: int = 8080):
    server = ThreadingHTTPServer(("0.0.0.0", port), SinceAIHttpHandler)
    print(f"Since AI Server running at http://localhost:{port} (Region: europe-north1 / Finland)")
    server.serve_forever()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    if app:
        import uvicorn
        uvicorn.run("src.api.main:app", host="0.0.0.0", port=port, reload=False)
    else:
        run_standalone_server(port=port)
