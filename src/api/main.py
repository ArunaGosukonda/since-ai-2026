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

    @app.post("/api/v1/consent")
    async def consent(request: Request):
        payload = await request.json()
        return handle_consent_update(payload)

    @app.get("/demo")
    @app.get("/demo.html")
    async def serve_demo():
        demo_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "../../demo.html"))
        if os.path.exists(demo_path):
            return FileResponse(demo_path)
        return JSONResponse({"error": "demo not found"}, status_code=404)

    # Mount static frontend assets (serves index.html on root /)
    frontend_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "../../frontend"))
    if os.path.exists(frontend_dir):
        from fastapi.staticfiles import StaticFiles
        app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

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
        elif self.path == "/" or self.path == "/index.html":
            frontend_index = os.path.normpath(os.path.join(os.path.dirname(__file__), "../../frontend/index.html"))
            if os.path.exists(frontend_index):
                self._send_file(frontend_index, "text/html; charset=utf-8")
            else:
                demo_html = os.path.normpath(os.path.join(os.path.dirname(__file__), "../../demo.html"))
                self._send_file(demo_html, "text/html; charset=utf-8")
        else:
            # Check frontend directory
            frontend_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "../../frontend"))
            rel_path = self.path.lstrip("/")
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
