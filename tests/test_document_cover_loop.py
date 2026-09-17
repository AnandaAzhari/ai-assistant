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
    def make_agent(self, tmp: str):
        store = DocumentPreferenceStore(Path(tmp) / "prefs.db")
        provider = FakeProvider()
        agent = DocumentAgent(
            provider,
            research=FakeResearch(),
            registry=FakeRegistry(),
            preference_store=store,
        )
        return agent, provider

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

    def test_explicit_correction_phrase_updates_existing_value(self):
        cover = MakalahCoverData(
            assignment_type="individu",
            author_name="Ananda",
            teacher_name="Purnama Sari",
        )

        cover.update("Nama gurunya bukan Purnama Sari, ganti menjadi Nurhayati.")

        self.assertEqual(cover.teacher_name, "Nurhayati")

    def test_plain_name_fills_active_author_question(self):
        cover = MakalahCoverData(assignment_type="individu")

        clarification = cover.update("Ananda Azhari Batubara", expected_field="author_name")

        self.assertEqual(clarification, "")
        self.assertEqual(cover.author_name, "Ananda Azhari Batubara")
        self.assertTrue(cover.complete)

    def test_explicit_student_name_can_be_sent_before_assignment_type(self):
        cover = MakalahCoverData()

        clarification = cover.update("Nama saya Ananda Azhari Batubara", expected_field="assignment_type")

        self.assertEqual(clarification, "")
        self.assertEqual(cover.author_name, "Ananda Azhari Batubara")
        self.assertEqual(cover.assignment_type, "")
        self.assertEqual(cover.next_required_field(), "assignment_type")

    def test_academic_year_can_be_answered_before_assignment_type(self):
        cover = MakalahCoverData()

        clarification = cover.update("2026/2027", expected_field="assignment_type")

        self.assertEqual(clarification, "")
        self.assertEqual(cover.academic_year, "2026/2027")
        self.assertEqual(cover.assignment_type, "")
        self.assertEqual(cover.next_required_field(), "assignment_type")

    def test_school_can_be_answered_while_agent_waits_for_author(self):
        cover = MakalahCoverData(assignment_type="individu")

        clarification = cover.update("SMK Negeri 2 Padangsidimpuan", expected_field="author_name")

        self.assertEqual(clarification, "")
        self.assertEqual(cover.institution_name, "SMK Negeri 2 Padangsidimpuan")
        self.assertEqual(cover.author_name, "")
        self.assertEqual(cover.next_required_field(), "author_name")

    def test_plain_name_is_not_guessed_when_active_question_is_not_a_name(self):
        cover = MakalahCoverData()

        clarification = cover.update("Purnama Sari", expected_field="assignment_type")

        self.assertIn("belum aman menentukan", clarification)
        self.assertEqual(cover.author_name, "")
        self.assertEqual(cover.teacher_name, "")

    def test_ready_for_draft_phase_keeps_cover_loop_open_and_confirms_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent, provider = self.make_agent(tmp)
            agent.cover.assignment_type = "individu"
            agent.cover.author_name = "Ananda Azhari Batubara"
            agent.phase = "ready_for_draft"

            result = agent.handle(
                "Nama Sekolah SMK Negeri 2 Padangsidimpuan\n"
                "tahun ajaran 2026/2027\n"
                "Nama Guru Purnama Sari"
            )

            self.assertEqual(result.status, "cover_updated")
            self.assertEqual(agent.cover.institution_name, "SMK Negeri 2 Padangsidimpuan")
            self.assertEqual(agent.cover.academic_year, "2026/2027")
            self.assertEqual(agent.cover.teacher_name, "Purnama Sari")
            self.assertIn("Data cover berhasil diperbarui", result.text)
            self.assertIn("SMK Negeri 2 Padangsidimpuan", result.text)
            self.assertIn("2026/2027", result.text)
            self.assertIn("Purnama Sari", result.text)
            self.assertEqual(provider.calls, [])

    def test_ready_for_draft_correction_confirms_latest_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent, provider = self.make_agent(tmp)
            agent.cover.assignment_type = "individu"
            agent.cover.author_name = "Ananda"
            agent.cover.teacher_name = "Purnama Sari"
            agent.phase = "ready_for_draft"

            result = agent.handle("Nama gurunya bukan Purnama Sari, ganti menjadi Nurhayati.")

            self.assertEqual(result.status, "cover_updated")
            self.assertEqual(agent.cover.teacher_name, "Nurhayati")
            self.assertIn("Guru/dosen: Nurhayati", result.text)
            self.assertNotIn("Guru/dosen: Purnama Sari", result.text)
            self.assertEqual(provider.calls, [])

    def test_agent_accepts_out_of_order_year_and_keeps_asking_required_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent, provider = self.make_agent(tmp)
            agent.phase = "cover"

            result = agent.handle("2026/2027")

            self.assertEqual(result.status, "needs_cover")
            self.assertEqual(agent.cover.academic_year, "2026/2027")
            self.assertEqual(agent.cover.assignment_type, "")
            self.assertIn("Tahun ajaran: 2026/2027", result.text)
            self.assertIn("individu atau kelompok", result.text)
            self.assertEqual(provider.calls, [])

    def test_agent_accepts_plain_author_name_from_active_question(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent, provider = self.make_agent(tmp)
            agent.phase = "cover"

            first = agent.handle("individu")
            self.assertEqual(first.status, "needs_cover")
            self.assertIn("nama penyusun", first.text.casefold())

            second = agent.handle("Ananda Azhari Batubara")

            self.assertEqual(second.status, "cover_complete")
            self.assertEqual(agent.cover.author_name, "Ananda Azhari Batubara")
            self.assertEqual(agent.phase, "ready_for_draft")
            self.assertEqual(provider.calls, [])

    def test_ready_for_draft_plain_name_requests_clarification_instead_of_guessing(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent, provider = self.make_agent(tmp)
            agent.cover.assignment_type = "individu"
            agent.cover.author_name = "Ananda"
            agent.phase = "ready_for_draft"

            result = agent.handle("Purnama Sari")

            self.assertEqual(result.status, "needs_cover_clarification")
            self.assertIn("nama penyusun/siswa", result.text)
            self.assertIn("nama guru/dosen", result.text)
            self.assertEqual(agent.cover.teacher_name, "")
            self.assertEqual(provider.calls, [])


if __name__ == "__main__":
    unittest.main()
