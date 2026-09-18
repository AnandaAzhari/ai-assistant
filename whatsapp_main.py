"""WhatsApp webhook — Fase 4 lanjutan (`docs/roadmap_customer_channel_v1.md`).

Entry point HTTP publik untuk WhatsApp Business Platform Cloud API (Meta), memakai
pola `http.server` stdlib yang sama seperti `app/web_admin.py`. `app/whatsapp.py`
SENGAJA tidak menjalankan server sendiri (lihat docstring-nya) — script inilah yang
menjadi endpoint publik sungguhan, dijalankan terpisah dari `main.py` (desktop) dan
`telegram_main.py` (admin), konsisten dengan pemisahan channel admin/pelanggan yang
permanen di `docs/core_architecture.md` (Telegram/Web Admin/Desktop = admin saja;
WhatsApp/Web App pelanggan = pelanggan saja).

Jalankan dengan: py -3 whatsapp_main.py [--host HOST] [--port PORT] [--check]

Uji coba dari komputer sendiri dulu (sebelum pindah ke VPS): jalankan script ini
(default bind ke 127.0.0.1), lalu tunnel lewat ngrok (atau sejenisnya) ke port yang
sama, dan daftarkan URL publik ngrok itu sebagai Callback URL webhook di Meta App
Dashboard. Untuk produksi: jalankan di server yang selalu menyala, umumnya di
belakang reverse proxy HTTPS.

Setiap pesan tetap WAJIB melalui Trust Layer -> Approval Gate -> (AI intent, fallback
kata kunci) lewat `LeadAgent.handle_customer_message()` — script ini hanya menjembatani
HTTP publik ke `WhatsAppCustomerAdapter` yang sudah menegakkan urutan itu.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from app.approval_gate import ApprovalGate
from app.customer_intent import CustomerIntentClassifier
from app.document_agent import DocumentAgent
from app.document_engine import DocumentEngine
from app.document_preferences import DocumentPreferenceStore
from app.document_session import DocumentSessionStore
from app.env import load_env
from app.lead import LeadAgent
from app.providers.deepseek import DeepSeekProvider
from app.source_registry import SourceRegistry
from app.trust_layer import TrustLayer
from app.whatsapp import (
    WhatsAppCustomerAdapter,
    WhatsAppError,
    WhatsAppHTTPClient,
    verify_webhook_challenge,
    verify_webhook_signature,
)

ROOT = Path(__file__).resolve().parent
# Payload webhook WhatsApp normalnya jauh lebih kecil dari ini; batas ini hanya
# menahan permintaan yang jelas tidak wajar sebelum dibaca penuh ke memori.
MAX_PAYLOAD_BYTES = 256 * 1024


def _customer_scope_id(sender_id: str) -> str:
    """`source_scope` unik per nomor pelanggan, supaya sesi/brief satu pelanggan
    tidak pernah tercampur dengan pelanggan lain (lihat "Isolasi Antar Pelanggan"
    di `policies/security_policy.md`)."""
    safe = re.sub(r"[^A-Za-z0-9_-]", "", sender_id or "")[:64] or "unknown"
    return f"DOCSRC-WHATSAPP-{safe}"


def create_customer_adapter() -> WhatsAppCustomerAdapter:
    """Rakit jalur pelanggan (Trust Layer -> Approval Gate -> AI intent -> Document
    Agent, lihat `app/lead.py`) dan sambungkan ke WhatsApp. Setiap pesan tetap WAJIB
    melalui `LeadAgent.handle_customer_message()` — tidak pernah langsung ke agent lain.

    `document_factory` membuat satu `DocumentAgent` tersendiri per nomor WhatsApp
    (dipanggil `LeadAgent` hanya saat pelanggan itu benar-benar butuh, lihat
    `_customer_document_agent`), memakai pedoman penomoran/format yang sama seperti
    admin (`skills/document_academic/`) — tidak ada pedoman terpisah yang perlu dibuat
    khusus untuk WhatsApp.
    """
    db_path = os.environ.get("DATABASE_PATH", "data/assistant.db").strip() or "data/assistant.db"
    provider = DeepSeekProvider.from_env()

    def document_factory(sender_id: str) -> DocumentAgent:
        return DocumentAgent(
            provider,
            engine=DocumentEngine.from_env(),
            registry=SourceRegistry(db_path),
            preference_store=DocumentPreferenceStore(db_path),
            source_scope=_customer_scope_id(sender_id),
            session_store=DocumentSessionStore(db_path),
        )

    lead = LeadAgent(
        trust_layer=TrustLayer(db_path),
        approval_gate=ApprovalGate(db_path),
        intent_classifier=CustomerIntentClassifier(provider),
        document_factory=document_factory,
    )
    client = WhatsAppHTTPClient(
        os.environ.get("WHATSAPP_API_TOKEN", ""),
        os.environ.get("WHATSAPP_PHONE_NUMBER_ID", ""),
    )
    return WhatsAppCustomerAdapter(client, lead)


class WhatsAppHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address, handler_class, *, adapter: WhatsAppCustomerAdapter,
                 verify_token: str, app_secret: str):
        super().__init__(server_address, handler_class)
        self.adapter = adapter
        self.verify_token = verify_token
        self.app_secret = app_secret


class WhatsAppWebhookHandler(BaseHTTPRequestHandler):
    server: WhatsAppHTTPServer

    def log_message(self, fmt: str, *args) -> None:
        # Jangan log header (signature/token) atau isi pesan pelanggan.
        print(f"[WhatsApp] {self.address_string()} - {fmt % args}", flush=True)

    def _plain(self, status: int, text: str) -> None:
        data = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/webhook":
            return self._plain(HTTPStatus.NOT_FOUND, "Not found")
        query = parse_qs(parsed.query)
        challenge = verify_webhook_challenge(
            mode=(query.get("hub.mode") or [""])[0],
            token=(query.get("hub.verify_token") or [""])[0],
            challenge=(query.get("hub.challenge") or [""])[0],
            expected_verify_token=self.server.verify_token,
        )
        if challenge is None:
            return self._plain(HTTPStatus.FORBIDDEN, "Verifikasi webhook gagal.")
        return self._plain(HTTPStatus.OK, challenge)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/webhook":
            return self._plain(HTTPStatus.NOT_FOUND, "Not found")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self._plain(HTTPStatus.BAD_REQUEST, "Content-Length tidak valid.")
        if length <= 0 or length > MAX_PAYLOAD_BYTES:
            return self._plain(HTTPStatus.BAD_REQUEST, "Ukuran payload tidak valid.")
        raw = self.rfile.read(length)
        signature = self.headers.get("X-Hub-Signature-256", "")
        if not verify_webhook_signature(raw, signature, self.server.app_secret):
            # Payload tanpa tanda tangan valid ditolak sebelum diproses sama sekali
            # (lihat docstring app/whatsapp.py — "Zero trust untuk input pelanggan").
            return self._plain(HTTPStatus.FORBIDDEN, "Tanda tangan tidak valid.")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._plain(HTTPStatus.BAD_REQUEST, "JSON tidak valid.")
        if not isinstance(payload, dict):
            return self._plain(HTTPStatus.BAD_REQUEST, "Payload harus objek JSON.")
        try:
            self.server.adapter.process_webhook_event(payload)
        except WhatsAppError as exc:
            print(f"[WhatsApp] Pemrosesan event gagal: {exc}", flush=True)
        # Selalu balas 200 setelah tanda tangan tervalidasi, supaya Meta tidak
        # mengulang kirim event yang sama karena dianggap gagal terkirim.
        return self._plain(HTTPStatus.OK, "EVENT_RECEIVED")


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} belum diisi di .env")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Taqi AI — WhatsApp Customer Adapter (webhook publik)")
    parser.add_argument("--host", default=os.environ.get("WHATSAPP_WEBHOOK_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("WHATSAPP_WEBHOOK_PORT", "8443") or 8443))
    parser.add_argument("--check", action="store_true", help="Periksa konfigurasi tanpa menjalankan server")
    args = parser.parse_args(argv)

    os.chdir(ROOT)
    load_env(ROOT / ".env")

    try:
        _require_env("WHATSAPP_API_TOKEN")
        _require_env("WHATSAPP_PHONE_NUMBER_ID")
        verify_token = _require_env("WHATSAPP_WEBHOOK_VERIFY_TOKEN")
        app_secret = _require_env("WHATSAPP_APP_SECRET")
        adapter = create_customer_adapter()
    except ValueError as exc:
        print("Konfigurasi belum lengkap: " + str(exc))
        print(
            "Isi WHATSAPP_API_TOKEN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_WEBHOOK_VERIFY_TOKEN, "
            "dan WHATSAPP_APP_SECRET di .env lokal."
        )
        return 2

    classifier = adapter.lead.intent_classifier
    ai_note = "siap (DeepSeek)" if classifier is not None and classifier.configured else "belum dikonfigurasi, memakai fallback kata kunci"
    document_note = "aktif (Document Agent tersambung)" if adapter.lead.document_factory is not None else "belum tersambung"

    if args.check:
        print("Konfigurasi WhatsApp Customer Adapter lengkap.")
        print("Trust Layer + Approval Gate: aktif.")
        print("AI intent classifier: " + ai_note + ".")
        print("Pembuatan dokumen (makalah/KTI/skripsi): " + document_note + ".")
        print(f"Server akan mendengarkan di {args.host}:{args.port}, endpoint /webhook.")
        return 0

    server = WhatsAppHTTPServer(
        (args.host, args.port), WhatsAppWebhookHandler,
        adapter=adapter, verify_token=verify_token, app_secret=app_secret,
    )
    print(f"WhatsApp Customer Adapter aktif di {args.host}:{args.port}/webhook.")
    print("AI intent classifier: " + ai_note + ".")
    print("Pembuatan dokumen (makalah/KTI/skripsi): " + document_note + ".")
    print("Biarkan terminal ini terbuka. Ctrl+C untuk berhenti.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDihentikan.")
    finally:
        server.server_close()
    print("WhatsApp Customer Adapter ditutup.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
