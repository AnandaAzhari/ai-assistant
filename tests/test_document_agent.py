import unittest

from app.document_agent import DocumentAgent
from app.lead import LeadAgent
from app.providers.base import ModelReply


class FakeProvider:
    configured = True
    provider_name = "FakeAI"
    model_name = "fake-model"

    def __init__(self):
        self.calls = []

    def generate(self, messages, *, max_tokens=1200, temperature=0.4, timeout=45):
        self.calls.append(messages)
        return ModelReply(
            "berhasil",
            "Baik. Berapa halaman dan apakah ada format khusus dari guru?",
            self.provider_name,
            self.model_name,
            120,
            18,
        )


class UnconfiguredProvider(FakeProvider):
    configured = False


class DocumentAgentTests(unittest.TestCase):
    def test_document_agent_calls_provider(self):
        provider = FakeProvider()
        agent = DocumentAgent(provider)
        result = agent.handle("Saya mau membuat makalah tentang pencemaran lingkungan untuk kelas 8")
        self.assertEqual(result.status, "berhasil")
        self.assertEqual(len(provider.calls), 1)
        self.assertIn("Berapa halaman", result.text)
        self.assertIn("token masuk", result.text)

    def test_context_is_kept_for_admin_session(self):
        provider = FakeProvider()
        agent = DocumentAgent(provider)
        agent.handle("Saya mau membuat makalah tentang pencemaran lingkungan")
        agent.handle("Untuk kelas 8 dan sekitar 10 halaman")
        second_messages = provider.calls[1]
        self.assertTrue(any(
            item.get("role") == "user" and "pencemaran lingkungan" in item.get("content", "")
            for item in second_messages
        ))

    def test_unconfigured_provider_does_not_call_api(self):
        provider = UnconfiguredProvider()
        agent = DocumentAgent(provider)
        result = agent.handle("Buat makalah")
        self.assertEqual(result.status, "belum_dikonfigurasi")
        self.assertEqual(provider.calls, [])

    def test_lead_routes_makalah_to_document_agent(self):
        provider = FakeProvider()
        document = DocumentAgent(provider)
        lead = LeadAgent(document=document)
        reply = lead.handle_admin_message("Saya mau membuat makalah tentang sampah plastik")
        self.assertEqual(reply.target, "document")
        self.assertEqual(reply.status, "berhasil")
        self.assertEqual(len(provider.calls), 1)

    def test_reset_clears_document_context(self):
        provider = FakeProvider()
        document = DocumentAgent(provider)
        document.handle("Makalah pertama")
        result = document.reset()
        self.assertEqual(result.status, "berhasil")
        self.assertEqual(document._history, [])


if __name__ == "__main__":
    unittest.main()
