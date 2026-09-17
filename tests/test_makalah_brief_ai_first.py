import json
import tempfile
import unittest
from pathlib import Path

from app.document_agent import DocumentAgent
from app.document_preferences import DocumentPreferenceStore
from app.makalah_brief import MakalahBrief
from app.providers.base import ModelReply


class FakeRegistry:
    def clear_scope(self, scope):
        return None

    def list_sources(self, scope):
        return []


class FakeResearch:
    status_text = "Research Manager uji"


class AIFirstProvider:
    configured = True
    provider_name = "FakeAI"
    model_name = "fake-model"

    def __init__(self):
        self.calls = []

    @staticmethod
    def _json_reply(values):
        keys = {
            "institution_level", "class_semester", "subject", "topic_title",
            "target_length", "teacher_instructions", "focus", "language_level",
            "source_requirements", "citation_style", "must_include", "must_avoid",
            "official_guideline",
        }
        payload = {key: None for key in keys}
        payload.update(values)
        return json.dumps(payload, ensure_ascii=False)

    def generate(self, messages, *, max_tokens=1200, temperature=0.4, timeout=45):
        self.calls.append(messages)
        system_text = "\n".join(item.get("content", "") for item in messages if item.get("role") == "system")
        user_text = "\n".join(item.get("content", "") for item in messages if item.get("role") == "user")

        if "interpreter MakalahBrief" in system_text:
            latest = user_text.split("PESAN PELANGGAN TERBARU:", 1)[-1]
            if "Saya mau membuat makalah tentang AI Agent" in latest:
                text = self._json_reply({
                    "topic_title": "AI Agent",
                    "target_length": "8 halaman",
                })
            elif "Informatika, SMK, XII semseter 1" in latest:
                text = self._json_reply({
                    "subject": "Informatika",
                    "institution_level": "SMK",
                    "class_semester": "Kelas XII, Semester 1",
                })
            elif "eh salah semester 2" in latest:
                text = self._json_reply({"class_semester": "Kelas XII, Semester 2"})
            else:
                text = self._json_reply({})
            return ModelReply("berhasil", text, self.provider_name, self.model_name, 100, 40)

        return ModelReply(
            "berhasil",
            "## Ringkasan Data\n- MakalahBrief lengkap\n\n## Kerangka Makalah\nBAB I — PENDAHULUAN",
            self.provider_name,
            self.model_name,
            300,
            80,
        )


class MakalahBriefTests(unittest.TestCase):
    def test_core_fields_determine_outline_readiness(self):
        brief = MakalahBrief(
            institution_level="SMK",
            class_semester="Kelas XII, Semester 1",
            subject="Informatika",
            topic_title="AI Agent",
            target_length="8 halaman",
        )
        self.assertTrue(brief.complete)
        self.assertEqual(brief.missing_fields(), [])

    def test_optional_quality_fields_do_not_block_outline(self):
        brief = MakalahBrief(
            institution_level="SMK",
            class_semester="Kelas XII, Semester 1",
            subject="Informatika",
            topic_title="AI Agent",
            target_length="8 halaman",
        )
        self.assertTrue(brief.complete)
        self.assertIn("focus", brief.quality_missing_fields())
        self.assertIn("source_requirements", brief.quality_missing_fields())

    def test_ai_update_can_correct_existing_class_semester(self):
        brief = MakalahBrief(
            institution_level="SMK",
            class_semester="Kelas XII, Semester 1",
            subject="Informatika",
            topic_title="AI Agent",
            target_length="8 halaman",
        )
        changed = brief.apply_ai_values({"class_semester": "Kelas XII, Semester 2"})
        self.assertEqual(brief.class_semester, "Kelas XII, Semester 2")
        self.assertEqual(changed, ["class_semester"])

    def test_ai_can_store_quality_preferences(self):
        brief = MakalahBrief()
        changed = brief.apply_ai_values({
            "focus": "Penerapan AI Agent dalam kehidupan sehari-hari",
            "language_level": "sederhana dan mudah dipahami siswa SMK",
            "source_requirements": "utamakan sumber 5 tahun terakhir",
        })
        self.assertEqual(len(changed), 3)
        self.assertIn("Penerapan AI Agent", brief.focus)
        self.assertIn("5 tahun", brief.source_requirements)

    def test_question_text_allows_free_order(self):
        brief = MakalahBrief(topic_title="AI Agent", target_length="8 halaman")
        text = brief.question_text()
        self.assertIn("urutan bebas", text)
        self.assertIn("bahasa biasa", text)

    def test_document_agent_uses_ai_first_for_typo_and_unordered_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            provider = AIFirstProvider()
            store = DocumentPreferenceStore(Path(tmp) / "prefs.db")
            agent = DocumentAgent(
                provider,
                research=FakeResearch(),
                registry=FakeRegistry(),
                preference_store=store,
            )

            first = agent.handle("Saya mau membuat makalah tentang AI Agent, 8 halaman")
            self.assertEqual(first.status, "needs_requirements")
            self.assertEqual(agent.brief.topic_title, "AI Agent")
            self.assertEqual(agent.brief.target_length, "8 halaman")

            second = agent.handle("Informatika, SMK, XII semseter 1")
            self.assertEqual(second.status, "berhasil")
            self.assertEqual(agent.brief.subject, "Informatika")
            self.assertEqual(agent.brief.institution_level, "SMK")
            self.assertEqual(agent.brief.class_semester, "Kelas XII, Semester 1")
            self.assertEqual(agent.phase, "outline_confirmation")
            # intake turn 1 + intake turn 2 + outline generation
            self.assertEqual(len(provider.calls), 3)


if __name__ == "__main__":
    unittest.main()
