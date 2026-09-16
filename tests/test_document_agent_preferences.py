import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.document_agent import DocumentAgent
from app.document_preferences import DocumentPreferenceStore, DocumentPreferences
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
            "Kerangka uji.",
            self.provider_name,
            self.model_name,
            10,
            5,
        )


class FakeRegistry:
    def __init__(self):
        self.sources = [object()]

    def list_sources(self, scope):
        return list(self.sources)

    def clear_scope(self, scope):
        return None


class FakeResearch:
    status_text = "Research Manager uji"


class FakeCitationEngine:
    def __init__(self):
        self.last_mode = None

    def build(self, spec, sources, *, create_pdf=True, citation_repeat_mode="auto"):
        self.last_mode = citation_repeat_mode
        return SimpleNamespace(
            status="berhasil",
            docx_path="uji.docx",
            pdf_path="uji.pdf",
            used_refs=("R1",),
            warning="",
        )


class DocumentAgentPreferenceIntegrationTests(unittest.TestCase):
    def make_agent(self, tmp: str, *, engine=None):
        store = DocumentPreferenceStore(Path(tmp) / "prefs.db")
        agent = DocumentAgent(
            FakeProvider(),
            engine=engine,
            research=FakeResearch(),
            registry=FakeRegistry(),
            preference_store=store,
        )
        return agent, store

    def test_natural_preference_message_updates_nara_without_ai(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent, store = self.make_agent(tmp)
            result = agent.handle("Jangan pakai Ibid.")

            self.assertEqual(result.status, "preference_updated")
            self.assertEqual(agent.citation_repeat_mode, "short")
            self.assertEqual(store.load(agent.source_scope).citation_repeat_mode, "short")
            self.assertEqual(agent.provider.calls, [])

    def test_combined_customer_message_keeps_preference_while_flow_continues(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent, store = self.make_agent(tmp)
            result = agent.handle(
                "Saya mau makalah tentang AI Agent, kelas XII semester 2, "
                "mapel Informatika, 8 halaman, jangan pakai Ibid."
            )

            self.assertNotEqual(result.status, "preference_updated")
            self.assertEqual(agent.citation_repeat_mode, "short")
            self.assertEqual(store.load(agent.source_scope).citation_repeat_mode, "short")

    def test_build_final_passes_order_preference_to_citation_engine(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent, store = self.make_agent(tmp, engine=object())
            store.save(agent.source_scope, DocumentPreferences(citation_repeat_mode="short"))
            agent.preferences = store.load(agent.source_scope)
            fake_citation = FakeCitationEngine()
            agent.citation_engine = fake_citation
            agent.phase = "draft_ready"
            agent._draft_spec = object()

            result = agent.build_final()

            self.assertEqual(result.status, "final_ready")
            self.assertEqual(fake_citation.last_mode, "short")
            self.assertIn("tanpa Ibid", result.text)

    def test_reset_returns_preference_to_default_auto(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent, store = self.make_agent(tmp)
            agent.handle("Tanpa Ibid.")
            self.assertEqual(agent.citation_repeat_mode, "short")

            result = agent.reset()

            self.assertEqual(result.status, "berhasil")
            self.assertEqual(agent.citation_repeat_mode, "auto")
            self.assertEqual(store.load(agent.source_scope).citation_repeat_mode, "auto")


if __name__ == "__main__":
    unittest.main()
