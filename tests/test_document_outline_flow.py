import tempfile
import unittest
from pathlib import Path

from app.document_agent import DocumentAgent, OUTLINE_MAX_TOKENS
from app.document_preferences import DocumentPreferenceStore
from app.providers.base import ModelReply


class FakeProvider:
    configured = True
    provider_name = "FakeAI"
    model_name = "fake-model"

    def __init__(self):
        self.calls = []

    def generate(self, messages, *, max_tokens=1200, temperature=0.4, timeout=45):
        self.calls.append({
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "timeout": timeout,
        })
        return ModelReply(
            "berhasil",
            "Ringkasan lengkap.\n\nKerangka lengkap sampai DAFTAR PUSTAKA.",
            self.provider_name,
            self.model_name,
            100,
            120,
        )


class FakeRegistry:
    def clear_scope(self, scope):
        return None

    def list_sources(self, scope):
        return []


class FakeResearch:
    status_text = "Research Manager uji"


class DocumentOutlineFlowTests(unittest.TestCase):
    def make_agent(self, tmp: str):
        return DocumentAgent(
            FakeProvider(),
            research=FakeResearch(),
            registry=FakeRegistry(),
            preference_store=DocumentPreferenceStore(Path(tmp) / "prefs.db"),
        )

    def test_outline_uses_provider_ceiling_instead_of_old_850_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = self.make_agent(tmp)
            result = agent._generate_outline("buat kerangka")

            self.assertEqual(result.status, "berhasil")
            self.assertEqual(agent.provider.calls[-1]["max_tokens"], OUTLINE_MAX_TOKENS)
            self.assertEqual(OUTLINE_MAX_TOKENS, 8000)

    def test_outline_always_has_clear_local_reply_hint(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = self.make_agent(tmp)
            result = agent._generate_outline("buat kerangka")

            self.assertIn("lanjutkan", result.text)
            self.assertIn("sudah sesuai", result.text)
            self.assertIn("Jika ingin diubah", result.text)

    def test_natural_approval_variants_are_local(self):
        approved = (
            "lanjutkan",
            "lanjut aja",
            "lanjut saja",
            "oke lanjut",
            "boleh lanjut",
            "sudah sesuai",
            "sudah pas",
            "iya",
        )
        for message in approved:
            with self.subTest(message=message):
                self.assertTrue(DocumentAgent._outline_approved(message))

    def test_revision_language_is_not_mistaken_for_approval(self):
        rejected = (
            "lanjutkan tapi ubah BAB II",
            "belum sesuai",
            "jangan lanjut dulu",
            "tolong revisi pembahasan",
            "oke lanjut tapi tambahkan satu subbab",
        )
        for message in rejected:
            with self.subTest(message=message):
                self.assertFalse(DocumentAgent._outline_approved(message))

    def test_lanjutkan_moves_to_cover_without_second_ai_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = self.make_agent(tmp)
            agent.phase = "outline_confirmation"
            agent._outline_text = "Kerangka sudah ada."

            result = agent.handle("lanjutkan")

            self.assertEqual(result.status, "needs_cover")
            self.assertEqual(agent.phase, "cover")
            self.assertEqual(agent.provider.calls, [])
            self.assertIn("cover", result.text.casefold())


if __name__ == "__main__":
    unittest.main()
