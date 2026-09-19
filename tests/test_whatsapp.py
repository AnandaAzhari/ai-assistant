import hashlib
import hmac
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import Mock, patch

from app.approval_gate import ApprovalGate
from app.attachment_guard import AttachmentGuard
from app.document_agent import DocumentResult
from app.lead import LeadAgent
from app.trust_layer import TrustLayer
from app.whatsapp import (
    ATTACHMENT_HOLD_TEXT,
    WHATSAPP_TEXT_LIMIT,
    WhatsAppCustomerAdapter,
    WhatsAppError,
    WhatsAppHTTPClient,
    extract_inbound_messages,
    verify_webhook_challenge,
    verify_webhook_signature,
)


def _document_message_payload(sender: str, *, filename: str, media_id: str = "media-doc-1", message_id: str = "wamid.doc") -> dict:
    return {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": sender, "id": message_id, "type": "document",
                        "document": {"id": media_id, "filename": filename, "mime_type": "application/octet-stream"},
                    }],
                },
            }],
        }],
    }


def _text_message_payload(sender: str, body: str, *, message_id: str = "wamid.1") -> dict:
    return {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": sender, "id": message_id, "type": "text",
                        "text": {"body": body},
                    }],
                },
            }],
        }],
    }


class WebhookVerificationTests(unittest.TestCase):
    def test_challenge_echoed_when_mode_and_token_match(self):
        result = verify_webhook_challenge(
            mode="subscribe", token="rahasia123", challenge="abc123", expected_verify_token="rahasia123",
        )
        self.assertEqual(result, "abc123")

    def test_challenge_rejected_on_wrong_token(self):
        result = verify_webhook_challenge(
            mode="subscribe", token="tebakan", challenge="abc123", expected_verify_token="rahasia123",
        )
        self.assertIsNone(result)

    def test_challenge_rejected_on_wrong_mode(self):
        result = verify_webhook_challenge(
            mode="unsubscribe", token="rahasia123", challenge="abc123", expected_verify_token="rahasia123",
        )
        self.assertIsNone(result)

    def test_signature_accepted_when_valid(self):
        secret = "app-secret-rahasia"
        payload = json.dumps({"hello": "world"}).encode("utf-8")
        signature = "sha256=" + hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
        self.assertTrue(verify_webhook_signature(payload, signature, secret))

    def test_signature_rejected_when_payload_tampered(self):
        secret = "app-secret-rahasia"
        payload = json.dumps({"hello": "world"}).encode("utf-8")
        signature = "sha256=" + hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
        tampered = json.dumps({"hello": "world!!"}).encode("utf-8")
        self.assertFalse(verify_webhook_signature(tampered, signature, secret))

    def test_signature_rejected_when_missing_or_malformed(self):
        self.assertFalse(verify_webhook_signature(b"{}", "", "secret"))
        self.assertFalse(verify_webhook_signature(b"{}", "not-sha256=abcd", "secret"))


class ExtractInboundMessagesTests(unittest.TestCase):
    def test_text_message_is_extracted(self):
        payload = _text_message_payload("628123456789", "Halo, mau tanya harga")
        messages = extract_inbound_messages(payload)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].sender_id, "628123456789")
        self.assertEqual(messages[0].text, "Halo, mau tanya harga")
        self.assertFalse(messages[0].has_attachment)

    def test_image_message_is_flagged_as_attachment(self):
        payload = {
            "entry": [{"changes": [{"value": {"messages": [{
                "from": "628999", "id": "wamid.2", "type": "image",
                "image": {"caption": "ini buktinya", "id": "media123"},
            }]}}]}],
        }
        messages = extract_inbound_messages(payload)
        self.assertEqual(len(messages), 1)
        self.assertTrue(messages[0].has_attachment)
        self.assertEqual(messages[0].text, "ini buktinya")
        self.assertEqual(messages[0].media_id, "media123")
        self.assertEqual(messages[0].media_type, "image")

    def test_document_message_captures_media_metadata(self):
        payload = _document_message_payload("628999", filename="tugas.pdf")
        messages = extract_inbound_messages(payload)
        self.assertEqual(messages[0].media_id, "media-doc-1")
        self.assertEqual(messages[0].media_filename, "tugas.pdf")
        self.assertEqual(messages[0].media_mime_type, "application/octet-stream")

    def test_status_callback_without_messages_is_ignored(self):
        payload = {"entry": [{"changes": [{"value": {"statuses": [{"status": "delivered"}]}}]}]}
        self.assertEqual(extract_inbound_messages(payload), [])

    def test_malformed_payload_returns_empty_list(self):
        self.assertEqual(extract_inbound_messages({}), [])
        self.assertEqual(extract_inbound_messages({"entry": "bukan-list"}), [])
        self.assertEqual(extract_inbound_messages(None), [])


class WhatsAppHTTPClientTests(unittest.TestCase):
    def test_empty_token_is_rejected(self):
        with self.assertRaises(ValueError):
            WhatsAppHTTPClient("", "123456")

    def test_token_with_whitespace_is_rejected(self):
        with self.assertRaises(ValueError):
            WhatsAppHTTPClient("token dengan spasi", "123456")

    def test_non_numeric_phone_number_id_is_rejected(self):
        with self.assertRaises(ValueError):
            WhatsAppHTTPClient("valid-token", "bukan-angka")


class FakeWhatsAppClient:
    def __init__(self, *, media_content: bytes = b"%PDF-1.4 isi dummy", media_mime_type: str = "application/pdf",
                 download_error: Exception | None = None):
        self.sent: list[tuple[str, str]] = []
        self.uploaded: list[str] = []
        self.documents_sent: list[tuple[str, str, str]] = []
        self.downloaded_media_ids: list[str] = []
        self._media_content = media_content
        self._media_mime_type = media_mime_type
        self._download_error = download_error

    def send_text(self, to: str, text: str) -> None:
        self.sent.append((to, text))

    def upload_media(self, file_path: str, *, mime_type: str) -> str:
        self.uploaded.append(file_path)
        return "fake-media-id"

    def send_document(self, to: str, media_id: str, *, filename: str) -> None:
        self.documents_sent.append((to, media_id, filename))

    def download_media(self, media_id: str) -> tuple[bytes, str]:
        self.downloaded_media_ids.append(media_id)
        if self._download_error is not None:
            raise self._download_error
        return self._media_content, self._media_mime_type


class FakeCustomerDocumentAgent:
    """Meniru antarmuka DocumentAgent yang dipakai LeadAgent/WhatsAppCustomerAdapter,
    tanpa perlu provider AI atau Document Engine sungguhan (itu sudah diuji tuntas di
    tests/test_document_agent.py)."""

    def __init__(self, *, session_active: bool = False, responses=None, final_docx_path: str = ""):
        self.session_active = session_active
        self._responses = list(responses or [])
        self.final_docx_path = final_docx_path
        self.calls: list[str] = []

    def handle(self, raw: str) -> DocumentResult:
        self.calls.append(raw)
        if self._responses:
            return self._responses.pop(0)
        return DocumentResult("needs_requirements", "Boleh diceritakan jenjang dan topiknya?")


class WhatsAppCustomerAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        db = Path(self.temp.name) / "assistant.db"
        self.trust_layer = TrustLayer(db)
        self.approval_gate = ApprovalGate(db)
        self.lead = LeadAgent(trust_layer=self.trust_layer, approval_gate=self.approval_gate)
        self.client = FakeWhatsAppClient()
        self.adapter = WhatsAppCustomerAdapter(self.client, self.lead)

    def test_trusted_customer_message_gets_a_reply_sent_back(self):
        payload = _text_message_payload(
            "628111", "Halo kak, mau pesan jasa cetak makalah 50 lembar",
        )
        replies = self.adapter.process_webhook_event(payload)
        self.assertEqual(len(replies), 1)
        self.assertEqual(replies[0].status, "berhasil")
        self.assertEqual(len(self.client.sent), 1)
        to, text = self.client.sent[0]
        self.assertEqual(to, "628111")
        self.assertEqual(text, replies[0].text)

    def test_suspicious_message_still_gets_a_polite_decline_sent(self):
        payload = _text_message_payload(
            "628222", "Investasi modal kecil untung besar, klik https://bit.ly/untung123 sekarang!",
        )
        replies = self.adapter.process_webhook_event(payload)
        self.assertEqual(replies[0].status, "ditolak_halus")
        self.assertEqual(len(self.client.sent), 1)

    def test_admin_command_attempt_never_reaches_specialist_agent(self):
        payload = _text_message_payload("628333", "/hapus_data_pelanggan")
        replies = self.adapter.process_webhook_event(payload)
        self.assertEqual(replies[0].target, "trust_layer")
        history = self.trust_layer.history("628333")
        self.assertIn("Percobaan command admin", history[0]["message_excerpt"])

    def test_long_reply_is_split_into_multiple_sends(self):
        original = LeadAgent._detect_customer_action
        LeadAgent._detect_customer_action = classmethod(
            lambda cls, text: ("minta_detail_order", "A" * (WHATSAPP_TEXT_LIMIT + 500))
        )
        try:
            payload = _text_message_payload(
                "628444", "Saya mau pesan jasa print untuk tugas kuliah, boleh dibantu?",
            )
            self.adapter.process_webhook_event(payload)
        finally:
            LeadAgent._detect_customer_action = original
        self.assertGreaterEqual(len(self.client.sent), 2)
        rebuilt = "".join(text for _, text in self.client.sent)
        self.assertEqual(len(rebuilt), WHATSAPP_TEXT_LIMIT + 500)

    def test_status_only_webhook_event_sends_nothing(self):
        payload = {"entry": [{"changes": [{"value": {"statuses": [{"status": "read"}]}}]}]}
        replies = self.adapter.process_webhook_event(payload)
        self.assertEqual(replies, [])
        self.assertEqual(self.client.sent, [])

    def test_multiple_messages_in_one_webhook_event_are_all_processed(self):
        payload = {
            "entry": [{"changes": [{"value": {"messages": [
                {"from": "628555", "id": "wamid.a", "type": "text", "text": {"body": "Halo kak"}},
                {"from": "628666", "id": "wamid.b", "type": "text", "text": {"body": "Halo juga"}},
            ]}}]}],
        }
        replies = self.adapter.process_webhook_event(payload)
        self.assertEqual(len(replies), 2)
        senders = {to for to, _ in self.client.sent}
        self.assertEqual(senders, {"628555", "628666"})


class WhatsAppHTTPClientMediaTests(unittest.TestCase):
    """upload_media/send_document — tidak pernah menyentuh jaringan asli, dimock
    seperti pola tests/test_telegram_integration.py."""

    def setUp(self):
        self.client = WhatsAppHTTPClient("token-uji", "123456")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.file_path = Path(self.temp.name) / "hasil.docx"
        self.file_path.write_bytes(b"isi dokumen palsu")

    def _response(self, data: dict):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = json.dumps(data).encode()
        return response

    def test_upload_missing_file_raises_without_network_call(self):
        with patch("urllib.request.urlopen") as network:
            with self.assertRaises(WhatsAppError):
                self.client.upload_media(str(Path(self.temp.name) / "tidak_ada.docx"), mime_type="application/pdf")
        network.assert_not_called()

    def test_upload_success_returns_media_id(self):
        with patch("urllib.request.urlopen", return_value=self._response({"id": "media-123"})) as call:
            media_id = self.client.upload_media(str(self.file_path), mime_type="application/pdf")
        self.assertEqual(media_id, "media-123")
        request = call.call_args.args[0]
        self.assertIn(b"isi dokumen palsu", request.data)
        self.assertIn("multipart/form-data", request.headers["Content-type"])

    def test_upload_http_error_is_wrapped(self):
        error = urllib.error.HTTPError("https://graph.facebook.com/media", 401, "unauthorized", {}, None)
        with patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(WhatsAppError) as raised:
                self.client.upload_media(str(self.file_path), mime_type="application/pdf")
        self.assertFalse(raised.exception.retryable)

    def test_upload_missing_media_id_in_response_is_rejected(self):
        with patch("urllib.request.urlopen", return_value=self._response({"unexpected": "shape"})):
            with self.assertRaises(WhatsAppError):
                self.client.upload_media(str(self.file_path), mime_type="application/pdf")

    def test_send_document_posts_expected_payload(self):
        with patch("urllib.request.urlopen", return_value=self._response({})) as call:
            self.client.send_document("628111", "media-123", filename="hasil.docx")
        body = json.loads(call.call_args.args[0].data.decode())
        self.assertEqual(body["type"], "document")
        self.assertEqual(body["document"], {"id": "media-123", "filename": "hasil.docx"})
        self.assertEqual(body["to"], "628111")

    def _raw_response(self, data: bytes):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = data
        return response

    def test_download_media_fetches_metadata_then_file_content(self):
        meta_response = self._response({"url": "https://cdn.example/media-123", "mime_type": "application/pdf"})
        file_response = self._raw_response(b"%PDF-1.4 isi file pelanggan")
        with patch("urllib.request.urlopen", side_effect=[meta_response, file_response]) as call:
            data, mime_type = self.client.download_media("media-123")
        self.assertEqual(data, b"%PDF-1.4 isi file pelanggan")
        self.assertEqual(mime_type, "application/pdf")
        first_request, second_request = call.call_args_list[0].args[0], call.call_args_list[1].args[0]
        self.assertIn("media-123", first_request.full_url)
        self.assertEqual(second_request.full_url, "https://cdn.example/media-123")
        self.assertEqual(second_request.headers["Authorization"], "Bearer token-uji")

    def test_download_media_empty_media_id_raises_without_network_call(self):
        with patch("urllib.request.urlopen") as network:
            with self.assertRaises(WhatsAppError):
                self.client.download_media("")
        network.assert_not_called()

    def test_download_media_missing_url_in_metadata_is_rejected(self):
        with patch("urllib.request.urlopen", return_value=self._response({"mime_type": "application/pdf"})):
            with self.assertRaises(WhatsAppError):
                self.client.download_media("media-123")

    def test_download_media_metadata_http_error_is_wrapped(self):
        error = urllib.error.HTTPError("https://graph.facebook.com/media-123", 404, "not found", {}, None)
        with patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(WhatsAppError) as raised:
                self.client.download_media("media-123")
        self.assertFalse(raised.exception.retryable)

    def test_download_media_file_fetch_http_error_is_wrapped(self):
        meta_response = self._response({"url": "https://cdn.example/media-123", "mime_type": "application/pdf"})
        error = urllib.error.HTTPError("https://cdn.example/media-123", 500, "server error", {}, None)
        with patch("urllib.request.urlopen", side_effect=[meta_response, error]):
            with self.assertRaises(WhatsAppError) as raised:
                self.client.download_media("media-123")
        self.assertTrue(raised.exception.retryable)


class WhatsAppAttachmentDeliveryTests(unittest.TestCase):
    """WhatsAppCustomerAdapter mengunggah lalu mengirim file saat LeadReply membawa
    attachment_path (jalur pelanggan -> Document Agent -> file makalah selesai)."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        db = Path(self.temp.name) / "assistant.db"
        self.trust_layer = TrustLayer(db)
        self.approval_gate = ApprovalGate(db)
        self.docx_path = Path(self.temp.name) / "makalah.docx"
        self.docx_path.write_bytes(b"palsu")
        self.fake_document = FakeCustomerDocumentAgent(
            responses=[DocumentResult("final_ready", "File makalah sudah selesai dibuat.")],
            final_docx_path=str(self.docx_path),
        )
        self.lead = LeadAgent(
            trust_layer=self.trust_layer, approval_gate=self.approval_gate,
            document_factory=lambda sender_id: self.fake_document,
        )
        self.client = FakeWhatsAppClient()
        self.adapter = WhatsAppCustomerAdapter(self.client, self.lead)

    def test_final_document_is_uploaded_and_sent_as_document_message(self):
        payload = _text_message_payload("628999", "Tolong buatkan makalah tentang gizi seimbang")
        self.adapter.process_webhook_event(payload)
        self.assertEqual(self.client.uploaded, [str(self.docx_path)])
        self.assertEqual(len(self.client.documents_sent), 1)
        to, media_id, filename = self.client.documents_sent[0]
        self.assertEqual(to, "628999")
        self.assertEqual(media_id, "fake-media-id")
        self.assertEqual(filename, "makalah.docx")

    def test_unrecognized_file_type_is_not_uploaded(self):
        self.fake_document.final_docx_path = str(Path(self.temp.name) / "berkas.xyz")
        Path(self.fake_document.final_docx_path).write_bytes(b"x")
        payload = _text_message_payload("628998", "Tolong buatkan makalah tentang gizi seimbang")
        self.adapter.process_webhook_event(payload)
        self.assertEqual(self.client.uploaded, [])
        self.assertEqual(self.client.documents_sent, [])

    def test_upload_failure_does_not_raise_and_text_reply_still_sent(self):
        failing_client = FakeWhatsAppClient()
        failing_client.upload_media = Mock(side_effect=WhatsAppError("gagal unggah"))
        adapter = WhatsAppCustomerAdapter(failing_client, self.lead)
        payload = _text_message_payload("628997", "Tolong buatkan makalah tentang gizi seimbang")
        replies = adapter.process_webhook_event(payload)
        self.assertEqual(len(failing_client.sent), 1)
        self.assertEqual(replies[0].status, "final_ready")


class WhatsAppAttachmentGuardIntegrationTests(unittest.TestCase):
    """WhatsAppCustomerAdapter <-> app/attachment_guard.py: file pelanggan diunduh dan
    diperiksa SEBELUM handle_customer_message() disentuh sama sekali."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        db = Path(self.temp.name) / "assistant.db"
        self.trust_layer = TrustLayer(db)
        self.approval_gate = ApprovalGate(db)
        self.lead = LeadAgent(trust_layer=self.trust_layer, approval_gate=self.approval_gate)
        self.attachment_guard = AttachmentGuard(Path(self.temp.name) / "quarantine", db)

    def test_safe_document_is_downloaded_inspected_and_processed_normally(self):
        client = FakeWhatsAppClient(media_content=b"%PDF-1.4 isi dummy", media_mime_type="application/pdf")
        adapter = WhatsAppCustomerAdapter(client, self.lead, attachment_guard=self.attachment_guard)
        payload = _document_message_payload("628111", filename="tugas.pdf", media_id="media-aman")
        replies = adapter.process_webhook_event(payload)
        self.assertEqual(client.downloaded_media_ids, ["media-aman"])
        self.assertNotEqual(replies[0].target, "attachment_guard")
        # Pesan tetap masuk Trust Layer seperti biasa (has_attachment=True sebagai sinyal).
        self.assertEqual(len(self.trust_layer.history("628111")), 1)

    def test_risky_executable_is_blocked_before_reaching_trust_layer(self):
        client = FakeWhatsAppClient(media_content=b"MZ\x90\x00", media_mime_type="application/octet-stream")
        adapter = WhatsAppCustomerAdapter(client, self.lead, attachment_guard=self.attachment_guard)
        payload = _document_message_payload("628222", filename="invoice.exe", media_id="media-jahat")
        replies = adapter.process_webhook_event(payload)
        self.assertEqual(replies[0].target, "attachment_guard")
        self.assertEqual(replies[0].status, "ditahan_keamanan")
        self.assertEqual(replies[0].text, ATTACHMENT_HOLD_TEXT)
        # Tidak pernah sampai ke Trust Layer sama sekali untuk pesan ini.
        self.assertEqual(self.trust_layer.history("628222"), [])
        # Eskalasi otomatis ke admin (Level 4, selalu wajib approval).
        pending = self.approval_gate.pending_for_admin()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["action_type"], "tinjau_attachment_pelanggan")

    def test_download_failure_holds_message_and_escalates(self):
        client = FakeWhatsAppClient(download_error=WhatsAppError("Koneksi terputus"))
        adapter = WhatsAppCustomerAdapter(client, self.lead, attachment_guard=self.attachment_guard)
        payload = _document_message_payload("628333", filename="tugas.pdf", media_id="media-gagal")
        replies = adapter.process_webhook_event(payload)
        self.assertEqual(replies[0].status, "tidak_dapat_diverifikasi")
        self.assertEqual(self.trust_layer.history("628333"), [])
        pending = self.approval_gate.pending_for_admin()
        self.assertEqual(len(pending), 1)

    def test_without_attachment_guard_configured_falls_back_to_old_behavior(self):
        client = FakeWhatsAppClient()
        adapter = WhatsAppCustomerAdapter(client, self.lead)  # attachment_guard tidak diberikan
        payload = _document_message_payload("628444", filename="invoice.exe", media_id="media-apa-saja")
        replies = adapter.process_webhook_event(payload)
        # Tanpa attachment_guard, media_id tidak pernah diunduh — perilaku lama tetap
        # jalan (has_attachment jadi sinyal Trust Layer saja).
        self.assertEqual(client.downloaded_media_ids, [])
        self.assertNotEqual(replies[0].target, "attachment_guard")

    def test_text_only_messages_never_trigger_download(self):
        client = FakeWhatsAppClient()
        adapter = WhatsAppCustomerAdapter(client, self.lead, attachment_guard=self.attachment_guard)
        payload = _text_message_payload("628555", "Halo kak, mau tanya harga cetak skripsi")
        adapter.process_webhook_event(payload)
        self.assertEqual(client.downloaded_media_ids, [])


if __name__ == "__main__":
    unittest.main()
