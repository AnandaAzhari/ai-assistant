import tempfile
import unittest
from pathlib import Path

from app.document_agent import DocumentAgent
from app.document_cover import MakalahCoverData
from app.document_preferences import DocumentPreferenceStore
from app.providers.base import ModelReply


class FakeProvider:
    configured = True
    provider_name = "FakeAI"
    model_name = "fake-model"

    def __init__(self):
        self.calls = []

    def generate(self, messages, *, max_tokens=1200, temperature=0.4, timeout=45):
        self.calls.append(messages)
        return ModelReply("berhasil", "uji", self.provider_name, self.model_name, 0, 0)


class FakeRegistry:
    def clear_scope(self, scope):
        return None

    def list_sources(self, scope):
        return []


class FakeResearch:
    status_text = "Research Manager uji"


class DocumentCoverLoopTests(unittest.TestCase):
    def test_optional_cover_fields_accept_natural_language_without_colon(self):
        cover = MakalahCoverData(
            assignment_type="individu",
            author_name="Ananda Azhari Batubara",
            institution_name="Tidak dicantumkan",
            academic_year="Tidak dicantumkan",
            teacher_name="Tidak dicantumkan",
        )

        cover.update(
            "Nama Sekolah SMK Negeri 2 Padangsidimpuan\n"
            "tahun ajaran 2026/2027\n"
            "Nama Guru Purnama Sari"
        )

        self.assertEqual(cover.institution_name, "SMK Negeri 2 Padangsidimpuan")
        self.assertEqual(cover.academic_year, "2026/2027")
        self.assertEqual(cover.teacher_name, "Purnama Sari")

    def test_optional_cover_fields_can_be_changed_again(self):
        cover = MakalahCoverData(
            assignment_type="individu",
            author_name="Ananda",
            institution_name="SMK Lama",
            academic_year="2025/2026",
            teacher_name="Guru Lama",
        )

        cover.update("nama sekolah SMK Baru\ntahun ajaran 2026/2027\nnama guru Guru Baru")

        self.assertEqual(cover.institution_name, "SMK Baru")
        self.assertEqual(cover.academic_year, "2026/2027")
        self.assertEqual(cover.teacher_name, "Guru Baru")

    def test_ready_for_draft_phase_keeps_cover_loop_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DocumentPreferenceStore(Path(tmp) / "prefs.db")
            provider = FakeProvider()
            agent = DocumentAgent(
                provider,
                research=FakeResearch(),
                registry=FakeRegistry(),
                preference_store=store,
            )
            agent.cover.assignment_type = "individu"
            agent.cover.author_name = "Ananda Azhari Batubara"
            agent.phase = "ready_for_draft"

            result = agent.handle(
                "Nama Sekolah SMK Negeri 2 Padangsidimpuan\n"
                "tahun ajaran 2026/2027\n"
                "Nama Guru Purnama Sari"
            )

            self.assertEqual(result.status, "ready_for_draft")
            self.assertEqual(agent.cover.institution_name, "SMK Negeri 2 Padangsidimpuan")
            self.assertEqual(agent.cover.academic_year, "2026/2027")
            self.assertEqual(agent.cover.teacher_name, "Purnama Sari")
            self.assertEqual(provider.calls, [])


if __name__ == "__main__":
    unittest.main()
