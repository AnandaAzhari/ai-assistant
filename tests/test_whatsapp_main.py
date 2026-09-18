import hashlib
import hmac
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

import whatsapp_main
from app.approval_gate import ApprovalGate
from app.lead import LeadAgent
from app.trust_layer import TrustLayer
from whatsapp_main import WhatsAppHTTPServer, WhatsAppWebhookHandler

APP_SECRET = "app-secret-rahasia"
VERIFY_TOKEN = "verify-token-rahasia"


def _sign(payload_bytes: bytes) -> str:
    return "sha256=" + hmac.new(APP_SECRET.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()


class FakeWhatsAppClient:
    def __init__(self):
        self.sent: list[tuple[str, str]] = []

    def send_text(self, to: str, text: str) -> None:
        self.sent.append((to, text))


class _FakeAdapter:
    """Meniru WhatsAppCustomerAdapter tanpa perlu WhatsAppHTTPClient/token asli."""

    def __init__(self, lead: LeadAgent, client: FakeWhatsAppClient):
        self.lead = lead
        self.client = client

    def process_webhook_event(self, payload: dict):
        from app.whatsapp import extract_inbound_messages
        replies = []
        for message in extract_inbound_messages(payload):
            reply = self.lead.handle_customer_message(message.sender_id, message.text, has_attachment=message.has_attachment)
            replies.append(reply)
            self.client.send_text(message.sender_id, reply.text)
        return replies


class WhatsAppMainServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        db = Path(self.temp.name) / "assistant.db"
        trust_layer = TrustLayer(db)
        approval_gate = ApprovalGate(db)
        lead = LeadAgent(trust_layer=trust_layer, approval_gate=approval_gate)
        self.client = FakeWhatsAppClient()
        self.adapter = _FakeAdapter(lead, self.client)

        self.server = WhatsAppHTTPServer(
            ("127.0.0.1", 0), WhatsAppWebhookHandler,
            adapter=self.adapter, verify_token=VERIFY_TOKEN, app_secret=APP_SECRET,
        )
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self._shutdown)

    def _shutdown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def _url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def _post(self, body: bytes, *, signature: str | None = None):
        headers = {"Content-Type": "application/json"}
        if signature is not None:
            headers["X-Hub-Signature-256"] = signature
        request = urllib.request.Request(self._url("/webhook"), data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8")

    def test_get_verification_challenge_succeeds_with_correct_token(self):
        url = self._url(f"/webhook?hub.mode=subscribe&hub.verify_token={VERIFY_TOKEN}&hub.challenge=abc123")
        with urllib.request.urlopen(url, timeout=5) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.read().decode("utf-8"), "abc123")

    def test_get_verification_fails_with_wrong_token(self):
        url = self._url("/webhook?hub.mode=subscribe&hub.verify_token=salah&hub.challenge=abc123")
        try:
            urllib.request.urlopen(url, timeout=5)
            self.fail("Seharusnya menolak dengan 403.")
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 403)

    def test_unknown_path_returns_404(self):
        try:
            urllib.request.urlopen(self._url("/lainnya"), timeout=5)
            self.fail("Seharusnya 404.")
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 404)

    def test_post_without_valid_signature_is_rejected_and_not_processed(self):
        body = json.dumps({"entry": [{"changes": [{"value": {"messages": [
            {"from": "628111", "id": "wamid.1", "type": "text", "text": {"body": "Halo kak"}},
        ]}}]}]}).encode("utf-8")
        status, _ = self._post(body, signature="sha256=" + "0" * 64)
        self.assertEqual(status, 403)
        self.assertEqual(self.client.sent, [])

    def test_post_missing_signature_header_is_rejected(self):
        body = json.dumps({"entry": []}).encode("utf-8")
        status, _ = self._post(body, signature=None)
        self.assertEqual(status, 403)

    def test_post_with_valid_signature_is_processed_and_replied(self):
        body = json.dumps({"entry": [{"changes": [{"value": {"messages": [
            {"from": "628222", "id": "wamid.2", "type": "text", "text": {"body": "Halo kak, mau tanya-tanya"}},
        ]}}]}]}).encode("utf-8")
        status, text = self._post(body, signature=_sign(body))
        self.assertEqual(status, 200)
        self.assertEqual(text, "EVENT_RECEIVED")
        self.assertEqual(len(self.client.sent), 1)
        self.assertEqual(self.client.sent[0][0], "628222")

    def test_post_with_valid_signature_but_malformed_json_is_rejected(self):
        body = b"bukan json"
        status, _ = self._post(body, signature=_sign(body))
        self.assertEqual(status, 400)

    def test_post_oversized_payload_is_rejected(self):
        body = json.dumps({"padding": "x" * (whatsapp_main.MAX_PAYLOAD_BYTES + 100)}).encode("utf-8")
        headers = {"Content-Type": "application/json", "X-Hub-Signature-256": _sign(body)}
        request = urllib.request.Request(self._url("/webhook"), data=body, headers=headers, method="POST")
        try:
            urllib.request.urlopen(request, timeout=5)
            self.fail("Seharusnya menolak payload terlalu besar.")
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 400)


class WhatsAppMainCliTests(unittest.TestCase):
    ENV_KEYS = (
        "WHATSAPP_API_TOKEN", "WHATSAPP_PHONE_NUMBER_ID",
        "WHATSAPP_WEBHOOK_VERIFY_TOKEN", "WHATSAPP_APP_SECRET",
        "DEEPSEEK_API_KEY", "DATABASE_PATH",
    )

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self._saved_cwd = Path.cwd()
        self._saved_env = {key: os.environ.get(key) for key in self.ENV_KEYS}
        self.addCleanup(self._restore_env)
        os.chdir(self.temp.name)
        self.addCleanup(lambda: os.chdir(self._saved_cwd))

    def _restore_env(self):
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_check_mode_fails_cleanly_when_config_missing(self):
        for key in self.ENV_KEYS:
            os.environ.pop(key, None)
        whatsapp_main.ROOT = Path(self.temp.name)
        exit_code = whatsapp_main.main(["--check"])
        self.assertEqual(exit_code, 2)

    def test_check_mode_succeeds_when_config_present(self):
        os.environ["WHATSAPP_API_TOKEN"] = "token-uji"
        os.environ["WHATSAPP_PHONE_NUMBER_ID"] = "123456789"
        os.environ["WHATSAPP_WEBHOOK_VERIFY_TOKEN"] = "verify-uji"
        os.environ["WHATSAPP_APP_SECRET"] = "secret-uji"
        os.environ["DATABASE_PATH"] = str(Path(self.temp.name) / "assistant.db")
        whatsapp_main.ROOT = Path(self.temp.name)
        exit_code = whatsapp_main.main(["--check"])
        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
