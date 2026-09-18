import hashlib
import hmac
import json
import tempfile
import unittest
from pathlib import Path

from app.approval_gate import ApprovalGate
from app.lead import LeadAgent
from app.trust_layer import TrustLayer
from app.whatsapp import (
    WHATSAPP_TEXT_LIMIT,
    WhatsAppCustomerAdapter,
    WhatsAppHTTPClient,
    extract_inbound_messages,
    verify_webhook_challenge,
    verify_webhook_signature,
)


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
    def __init__(self):
        self.sent: list[tuple[str, str]] = []

    def send_text(self, to: str, text: str) -> None:
        self.sent.append((to, text))


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


if __name__ == "__main__":
    unittest.main()
