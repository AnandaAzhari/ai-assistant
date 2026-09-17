import json
import tempfile
import unittest
from pathlib import Path

from app.document_agent import DocumentAgent
from app.document_preferences import DocumentPreferenceStore
from app.makalah_brief import MakalahBrief
from app.providers.base import ModelReply


class ScriptedProvider:
    configured = True
    provider_name = "FakeAI"
    model_name = "fake-model"

    def __init__(self, payloads=None, *, fail=False):
        self.payloads = list(payloads or [])
        self.fail = fail
        self.calls = []

    def generate(self, messages, *, max_tokens=1200, temperature=0.4, timeout=45):
        self.calls.append(messages)
        if self.fail:
            return ModelReply("gagal", "provider gagal", self.provider_name, self.model_name, 0, 0)
        payload = self.payloads.pop(0) if self.payloads else {}
        return ModelReply(
            "berhasil",
            json.dumps(payload),
            self.provider_name,
            self.model_name,
            25,
            20,
        )


class FakeRegistry:
    def clear_scope(self, scope):
        return None

    def list_sources(self, scope):
        return []


class FakeResearch:
    status_text = "Research Manager uji"


class MakalahBriefV2Tests(unittest.TestCase):
    def make_agent(self, provider, tmp):
        return DocumentAgent(
            provider,
            research=FakeResearch(),
            registry=FakeRegistry(),
            preference_store=DocumentPreferenceStore(Path(tmp) / "prefs.db"),
        )

    def test_core_fields_gate_outline_but_quality_fields_are_optional(self):
        brief = MakalahBrief(
            institution_level="SMK",
            class_semester="Kelas XII, Semester 1",
            subject="Informatika",
            topic_title="AI Agent",
            target_length="8 halaman",
        )

        self.assertTrue(brief.complete)
        self.assertEqual(brief.missing_fields(), [])
        self.assertIn("focus", brief.quality_missing_fields())
        self.assertIn("teacher_instructions", brief.quality_missing_fields())

    def test_ai_values_can_correct_existing_field_without_erasing_other_fields(self):
        brief = MakalahBrief(
            institution_level="SMK",
            class_semester="Kelas XII, Semester 1",
            subject="Informatika",
            topic_title="AI Agent",
            target_length="8 halaman",
        )

        changed = brief.apply_ai_values({
            "class_semester": "Kelas XII, Semester 2",
            "subject": None,
            "topic_title": None,
        })

        self.assertEqual(brief.class_semester, "Kelas XII, Semester 2")
        self.assertEqual(brief.subject, "Informatika")
        self.assertEqual(brief.topic_title, "AI Agent")
        self.assertEqual(changed, ["class_semester"])

    def test_approved_focus_is_saved_only_when_customer_has_not_set_one(self):
        brief = MakalahBrief()

        self.assertTrue(brief.approve_focus("Penerapan AI Agent di sekolah"))
        self.assertEqual(brief.focus, "Penerapan AI Agent di sekolah")
        self.assertFalse(brief.approve_focus("Fokus lain dari model"))
        self.assertEqual(brief.focus, "Penerapan AI Agent di sekolah")

    def test_ibid_instruction_is_not_saved_as_must_avoid_content(self):
        brief = MakalahBrief()

        changed = brief.apply_ai_values({"must_avoid": "Ibid."})

        self.assertEqual(changed, [])
        self.assertEqual(brief.must_avoid, "")

    def test_agent_ai_first_understands_typo_and_random_order(self):
        payload = {
            "institution_level": "SMK",
            "class_semester": "Kelas XII, Semester 1",
            "subject": "Informatika",
            "topic_title": None,
            "target_length": None,
            "teacher_instructions": None,
            "focus": None,
            "language_level": None,
            "source_requirements": None,
            "citation_style": None,
            "must_include": None,
            "must_avoid": None,
            "official_guideline": None,
        }
        provider = ScriptedProvider([payload])

        with tempfile.TemporaryDirectory() as tmp:
            agent = self.make_agent(provider, tmp)
            result = agent.handle("Informatika, SMK, XII semseter 1")

        self.assertEqual(result.status, "needs_requirements")
        self.assertEqual(agent.brief.subject, "Informatika")
        self.assertEqual(agent.brief.institution_level, "SMK")
        self.assertEqual(agent.brief.class_semester, "Kelas XII, Semester 1")
        self.assertIn("Topik atau judul", result.text)
        self.assertIn("Target jumlah halaman", result.text)
        self.assertEqual(len(provider.calls), 1)

    def test_quality_preferences_are_stored_when_customer_mentions_them(self):
        payload = {
            "institution_level": None,
            "class_semester": None,
            "subject": None,
            "topic_title": None,
            "target_length": None,
            "teacher_instructions": None,
            "focus": "penerapan AI Agent di sekolah",
            "language_level": "sederhana dan mudah dipahami",
            "source_requirements": "sumber maksimal 5 tahun terakhir",
            "citation_style": None,
            "must_include": "contoh penggunaan sehari-hari",
            "must_avoid": None,
            "official_guideline": None,
        }
        provider = ScriptedProvider([payload])

        with tempfile.TemporaryDirectory() as tmp:
            agent = self.make_agent(provider, tmp)
            agent.handle(
                "Fokus ke penerapan AI Agent di sekolah, bahas dengan bahasa mudah, "
                "pakai sumber 5 tahun terakhir dan beri contoh penggunaan sehari-hari."
            )

        self.assertEqual(agent.brief.focus, "penerapan AI Agent di sekolah")
        self.assertEqual(agent.brief.language_level, "sederhana dan mudah dipahami")
        self.assertEqual(agent.brief.source_requirements, "sumber maksimal 5 tahun terakhir")
        self.assertEqual(agent.brief.must_include, "contoh penggunaan sehari-hari")
        self.assertEqual(len(provider.calls), 1)

    def test_local_parser_remains_fallback_when_ai_provider_fails(self):
        provider = ScriptedProvider(fail=True)

        with tempfile.TemporaryDirectory() as tmp:
            agent = self.make_agent(provider, tmp)
            agent._apply_intake_ai_first(
                "Saya mau makalah tentang AI Agent, SMK kelas XII semester 1, "
                "mapel Informatika, 8 halaman"
            )

        self.assertEqual(agent.brief.institution_level, "SMK")
        self.assertEqual(agent.brief.class_semester, "Kelas XII, Semester 1")
        self.assertEqual(agent.brief.subject, "Informatika")
        self.assertEqual(agent.brief.topic_title, "AI Agent")
        self.assertEqual(agent.brief.target_length, "8 halaman")
        self.assertTrue(agent.brief.complete)
        self.assertEqual(len(provider.calls), 1)


if __name__ == "__main__":
    unittest.main()
