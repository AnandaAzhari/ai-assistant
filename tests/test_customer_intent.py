import unittest

from app.customer_intent import ALLOWED_ACTIONS, CustomerIntentClassifier, IntentResult
from app.providers.base import ModelReply


class FakeProvider:
    def __init__(self, reply: ModelReply, *, configured: bool = True):
        self._reply = reply
        self._configured = configured
        self.calls: list[list[dict[str, str]]] = []

    @property
    def configured(self) -> bool:
        return self._configured

    @property
    def provider_name(self) -> str:
        return "Fake"

    @property
    def model_name(self) -> str:
        return "fake-model"

    def generate(self, messages, *, max_tokens=300, temperature=0.0, timeout=20):
        self.calls.append(messages)
        return self._reply


def _reply(text: str, *, status: str = "berhasil") -> ModelReply:
    return ModelReply(status, text, "Fake", "fake-model", 10, 5)


class CustomerIntentClassifierTests(unittest.TestCase):
    def test_unconfigured_provider_returns_not_configured_without_calling_it(self):
        provider = FakeProvider(_reply("{}"), configured=False)
        classifier = CustomerIntentClassifier(provider)
        result = classifier.classify("Halo kak")
        self.assertEqual(result.status, "belum_dikonfigurasi")
        self.assertEqual(provider.calls, [])

    def test_none_provider_is_treated_as_not_configured(self):
        classifier = CustomerIntentClassifier(None)
        self.assertFalse(classifier.configured)
        self.assertEqual(classifier.classify("Halo").status, "belum_dikonfigurasi")

    def test_empty_message_fails_without_calling_provider(self):
        provider = FakeProvider(_reply("{}"))
        classifier = CustomerIntentClassifier(provider)
        result = classifier.classify("   ")
        self.assertEqual(result.status, "gagal")
        self.assertEqual(provider.calls, [])

    def test_valid_classification_with_matching_quote_succeeds(self):
        raw = "Kak mau tanya harga cetak skripsi 50 lembar dong"
        provider = FakeProvider(_reply(
            '{"action_type": "kirim_estimasi_harga_standar", "evidence": "mau tanya harga cetak skripsi"}'
        ))
        classifier = CustomerIntentClassifier(provider)
        result = classifier.classify(raw)
        self.assertEqual(result.status, "berhasil")
        self.assertEqual(result.action_type, "kirim_estimasi_harga_standar")
        self.assertEqual(result.model, "fake-model")

    def test_unknown_action_type_is_rejected(self):
        provider = FakeProvider(_reply('{"action_type": "diskon_khusus", "evidence": "kak"}'))
        raw = "kak boleh diskon gak"
        classifier = CustomerIntentClassifier(provider)
        result = classifier.classify(raw)
        self.assertEqual(result.status, "gagal")

    def test_evidence_not_found_in_message_is_rejected(self):
        provider = FakeProvider(_reply(
            '{"action_type": "kirim_salam", "evidence": "kalimat yang tidak ada di pesan asli"}'
        ))
        classifier = CustomerIntentClassifier(provider)
        result = classifier.classify("Halo kak")
        self.assertEqual(result.status, "gagal")

    def test_malformed_json_is_rejected(self):
        provider = FakeProvider(_reply("bukan json sama sekali"))
        classifier = CustomerIntentClassifier(provider)
        result = classifier.classify("Halo kak")
        self.assertEqual(result.status, "gagal")

    def test_json_wrapped_in_markdown_fence_is_parsed(self):
        raw = "Halo kak, jam buka toko jam berapa ya?"
        provider = FakeProvider(_reply(
            '```json\n{"action_type": "jawab_faq", "evidence": "jam buka toko jam berapa"}\n```'
        ))
        classifier = CustomerIntentClassifier(provider)
        result = classifier.classify(raw)
        self.assertEqual(result.status, "berhasil")
        self.assertEqual(result.action_type, "jawab_faq")

    def test_provider_failure_status_is_passed_through(self):
        provider = FakeProvider(_reply("gagal menghubungi API", status="gagal"))
        classifier = CustomerIntentClassifier(provider)
        result = classifier.classify("Halo kak")
        self.assertEqual(result.status, "gagal")

    def test_allowed_actions_match_reply_text_keys_in_lead_agent(self):
        # Konsistensi satu sumber: app/lead.py._CUSTOMER_REPLY_TEXT harus persis
        # mengenal semua action_type yang boleh dikembalikan classifier ini.
        from app.lead import LeadAgent
        self.assertEqual(set(ALLOWED_ACTIONS), set(LeadAgent._CUSTOMER_REPLY_TEXT))


if __name__ == "__main__":
    unittest.main()
