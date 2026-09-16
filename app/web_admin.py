"""Web Admin/PWA server minimum untuk AI Assistant.

Hanya memakai Python standard library agar fondasi tetap ringan.
Default bind ke localhost. Mode --lan wajib memakai WEB_ADMIN_KEY.
"""

from __future__ import annotations

import json
import mimetypes
import os
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from app.finance import FinanceService
from app.google_sheets_sync import GoogleSheetsSync
from app.lead import LeadAgent


WEB_ROOT = Path(__file__).resolve().parent.parent / "web_admin"
MAX_MESSAGE_BYTES = 32 * 1024


def system_status(sync_ready: bool = False) -> dict:
    return {
        "ok": True,
        "name": "Taqi AI Admin",
        "components": [
            {"name": "Lead Agent", "status": "aktif"},
            {"name": "Finance Agent", "status": "aktif"},
            {"name": "Google Sheets", "status": "siap" if sync_ready else "belum_dikonfigurasi"},
            {"name": "TaqiDesk", "status": "belum_terhubung"},
            {"name": "Telegram", "status": "opsional"},
        ],
    }


class WebAdminHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address, handler_class, *, lead: LeadAgent, admin_key: str = ""):
        super().__init__(server_address, handler_class)
        self.lead = lead
        self.admin_key = admin_key


class WebAdminHandler(BaseHTTPRequestHandler):
    server: WebAdminHTTPServer

    def log_message(self, fmt: str, *args) -> None:
        # Jangan log header/key atau isi pesan pengguna.
        print(f"[WebAdmin] {self.address_string()} - {fmt % args}", flush=True)

    def _security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; "
            "img-src 'self' data:; manifest-src 'self'; worker-src 'self'; frame-ancestors 'none'",
        )

    def _json(self, payload: dict, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(data)

    def _authorized(self) -> bool:
        expected = self.server.admin_key
        if not expected:
            return True
        supplied = self.headers.get("X-Admin-Key", "")
        return bool(supplied) and supplied == expected

    def _same_origin(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        try:
            parsed = urlparse(origin)
        except ValueError:
            return False
        return parsed.netloc == self.headers.get("Host", "")

    def _read_json(self) -> dict:
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            raise ValueError("Content-Type harus application/json.")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Content-Length tidak valid.") from exc
        if length <= 0 or length > MAX_MESSAGE_BYTES:
            raise ValueError("Ukuran pesan tidak valid.")
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("JSON tidak valid.") from exc
        if not isinstance(payload, dict):
            raise ValueError("Payload harus objek JSON.")
        return payload

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/status":
            if not self._authorized():
                return self._json({"ok": False, "error": "Akses ditolak."}, HTTPStatus.UNAUTHORIZED)
            sync_ready = bool(self.server.lead.sheets_sync and self.server.lead.sheets_sync.configured)
            return self._json(system_status(sync_ready))
        self._serve_static(path)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path != "/api/message":
            return self._json({"ok": False, "error": "Endpoint tidak ditemukan."}, HTTPStatus.NOT_FOUND)
        if not self._same_origin():
            return self._json({"ok": False, "error": "Origin ditolak."}, HTTPStatus.FORBIDDEN)
        if not self._authorized():
            return self._json({"ok": False, "error": "Akses ditolak."}, HTTPStatus.UNAUTHORIZED)
        try:
            payload = self._read_json()
            message = payload.get("message", "")
            if not isinstance(message, str) or len(message) > 8000:
                raise ValueError("Pesan harus berupa teks maksimal 8000 karakter.")
            reply = self.server.lead.handle_admin_message(message)
        except ValueError as exc:
            return self._json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
        return self._json({"ok": True, "reply": asdict(reply)})

    def _serve_static(self, request_path: str) -> None:
        if request_path in {"", "/"}:
            request_path = "/index.html"
        relative = request_path.lstrip("/")
        candidate = (WEB_ROOT / relative).resolve()
        root = WEB_ROOT.resolve()
        if root not in candidate.parents and candidate != root:
            return self.send_error(HTTPStatus.NOT_FOUND)
        if not candidate.is_file():
            return self.send_error(HTTPStatus.NOT_FOUND)
        data = candidate.read_bytes()
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(data)


def create_server(host: str, port: int, *, admin_key: str = "") -> WebAdminHTTPServer:
    if not WEB_ROOT.is_dir():
        raise RuntimeError(f"Folder Web Admin tidak ditemukan: {WEB_ROOT}")
    db_path = os.environ.get("DATABASE_PATH", "data/assistant.db").strip() or "data/assistant.db"
    finance = FinanceService(db_path)
    sheets_sync = GoogleSheetsSync.from_env(db_path)
    lead = LeadAgent(finance=finance, sheets_sync=sheets_sync)
    return WebAdminHTTPServer((host, port), WebAdminHandler, lead=lead, admin_key=admin_key)


def env_admin_key() -> str:
    return os.environ.get("WEB_ADMIN_KEY", "").strip()
