import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.document_agent import DocumentAgent, OUTLINE_MAX_TOKENS
from app.document_preferences import DocumentPreferenceStore
from app.providers.base import ModelReply


class FakeProvider:
    configured = True
    provider_name = "FakeAI"
    model_name = "fake-model"

    def __init__(self, response_text=None):
        self.calls = []
        self.response_text = response_text or (
            "## Usulan Fokus\n"
            "Pengenalan AI Agent, cara kerja, penerapan, manfaat, dan tantangannya.\n\n"
            "## Kerangka Makalah\n"
            "COVER\nKATA PENGANTAR\nDAFTAR ISI\nBAB I — PENDAHULUAN\n"
            "BAB II — PEMBAHASAN\nBAB III — PENUTUP\nDAFTAR PUSTAKA\n\n"
            "<!-- TAQI_PROPOSED_FOCUS: Pengenalan AI Agent, cara kerja, penerapan, manfaat, dan tantangannya -->"
        )

    def generate(self, messages, *, max_tokens=1200, temperature=0.4, timeout=45):
        self.calls.append({
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "timeout": timeout,
        })
        return ModelReply(
            "berhasil",
            self.response_text,
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
    def make_agent(self, tmp: str, response_text=None):
        agent = DocumentAgent(
            FakeProvider(response_text),
            research=FakeResearch(),
            registry=FakeRegistry(),
            preference_store=DocumentPreferenceStore(Path(tmp) / "prefs.db"),
        )
        agent.brief.institution_level = "SMK"
        agent.brief.class_semester = "Kelas XII, Semester 1"
        agent.brief.subject = "Informatika"
        agent.brief.topic_title = "AI Agent"
        agent.brief.target_length = "8 halaman"
        return agent

    def test_outline_uses_provider_ceiling_instead_of_old_850_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = self.make_agent(tmp)
            result = agent._generate_outline("buat kerangka")

            self.assertEqual(result.status, "berhasil")
            self.assertEqual(agent.provider.calls[-1]["max_tokens"], OUTLINE_MAX_TOKENS)
            self.assertEqual(OUTLINE_MAX_TOKENS, 8000)

    def test_outline_has_deterministic_customer_summary_and_reply_hint(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = self.make_agent(tmp)
            result = agent._generate_outline("buat kerangka")

            self.assertIn("## Ringkasan Kebutuhan", result.text)
            self.assertIn("Jenjang: SMK", result.text)
            self.assertIn("Kelas/semester: Kelas XII, Semester 1", result.text)
            self.assertIn("Mata pelajaran/mata kuliah: Informatika", result.text)
            self.assertIn("Topik/judul: AI Agent", result.text)
            self.assertIn("Target: 8 halaman", result.text)
            self.assertIn("lanjutkan", result.text)
            self.assertIn("sudah sesuai", result.text)
            self.assertIn("Jika ingin diubah", result.text)

    def test_outline_hides_focus_marker_but_keeps_proposed_focus_in_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = self.make_agent(tmp)
            result = agent._generate_outline("buat kerangka")

            self.assertNotIn("TAQI_PROPOSED_FOCUS", result.text)
            self.assertEqual(
                agent._proposed_focus,
                "Pengenalan AI Agent, cara kerja, penerapan, manfaat, dan tantangannya",
            )
            self.assertEqual(agent.brief.focus, "")

    def test_technical_note_section_is_removed_from_customer_output(self):
        response = (
            "## Usulan Fokus\nFokus singkat.\n\n"
            "## Kerangka Makalah\nBAB I\nBAB II\nBAB III\nDAFTAR PUSTAKA\n\n"
            "## Catatan Penyusunan\nHeading 1, reset nomor halaman, TOC 1-3.\n\n"
            "<!-- TAQI_PROPOSED_FOCUS: Fokus singkat -->"
        )
        with tempfile.TemporaryDirectory() as tmp:
            agent = self.make_agent(tmp, response)
            result = agent._generate_outline("buat kerangka")

            self.assertNotIn("Catatan Penyusunan", result.text)
            self.assertNotIn("reset nomor halaman", result.text)
            self.assertNotIn("TOC 1-3", result.text)

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

    def test_lanjutkan_locks_proposed_focus_then_moves_to_cover_without_ai_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = self.make_agent(tmp)
            agent.phase = "outline_confirmation"
            agent._outline_text = "Kerangka sudah ada."
            agent._proposed_focus = "Penerapan AI Agent di sekolah"

            result = agent.handle("lanjutkan")

            self.assertEqual(result.status, "needs_cover")
            self.assertEqual(agent.phase, "cover")
            self.assertEqual(agent.brief.focus, "Penerapan AI Agent di sekolah")
            self.assertEqual(agent._proposed_focus, "")
            self.assertEqual(agent.provider.calls, [])
            self.assertIn("Fokus kerangka disetujui", result.text)
            self.assertIn("Penerapan AI Agent di sekolah", result.text)
            self.assertIn("cover", result.text.casefold())

    def test_customer_focus_is_never_overwritten_by_model_proposal(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = self.make_agent(tmp)
            agent.brief.focus = "AI Agent untuk pembelajaran"
            agent.phase = "outline_confirmation"
            agent._outline_text = "Kerangka sudah ada."
            agent._proposed_focus = "Fokus buatan model yang berbeda"

            result = agent.handle("lanjutkan")

            self.assertEqual(result.status, "needs_cover")
            self.assertEqual(agent.brief.focus, "AI Agent untuk pembelajaran")
            self.assertNotIn("Fokus kerangka disetujui", result.text)
            self.assertEqual(agent.provider.calls, [])

    def test_duplicate_summary_approval_and_internal_notes_are_hidden(self):
        response = (
            "## Catatan Teknis\nHeading 1 dan TOC\n"
            "## Ringkasan Data\nChicago default\n"
            "## Usulan Fokus\nPenerapan AI Agent di sekolah.\n"
            "## Kerangka Makalah\nBAB I (Heading 1)\nBAB II\nBAB III\nDAFTAR PUSTAKA\n"
            "Jika sudah sesuai, balas `lanjutkan`.\nJika ingin diubah, tuliskan revisi.\n"
            "<!-- TAQI_PROPOSED_FOCUS: Penerapan AI Agent di sekolah -->"
        )
        with tempfile.TemporaryDirectory() as tmp:
            agent = self.make_agent(tmp, response)
            result = agent._generate_outline("buat kerangka")
            self.assertEqual(result.text.count("`lanjutkan`"), 1)
            self.assertEqual(result.text.count("Jika ingin diubah"), 1)
            for internal in ("Heading", "TOC", "Chicago default", "token", "TAQI_PROPOSED_FOCUS"):
                self.assertNotIn(internal, result.text)
            self.assertIn("BAB I", result.text)
            self.assertIn("DAFTAR PUSTAKA", result.text)

    def test_visible_focus_is_used_when_marker_is_missing_or_disagrees(self):
        for marker in ("", "<!-- TAQI_PROPOSED_FOCUS: Fokus tersembunyi -->"):
            with self.subTest(marker=marker), tempfile.TemporaryDirectory() as tmp:
                agent = self.make_agent(tmp, "## Usulan Fokus\nAI di sekolah.\n## Kerangka Makalah\nBAB I\nBAB II\nBAB III\n" + marker)
                agent._generate_outline("buat kerangka")
                self.assertEqual(agent.brief.focus, "")
                agent.handle("lanjutkan")
                self.assertEqual(agent.brief.focus, "AI di sekolah.")

    def test_model_proposal_is_removed_when_customer_has_explicit_focus(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = self.make_agent(tmp)
            agent.brief.focus = "AI untuk bengkel"
            result = agent._generate_outline("buat kerangka")
            self.assertNotIn("## Usulan Fokus", result.text)
            self.assertEqual(agent._proposed_focus, "")

    def test_failed_revision_cannot_approve_previous_outline_or_focus(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = self.make_agent(tmp)
            agent._generate_outline("buat kerangka")
            with patch.object(agent, "_apply_intake_ai_first"), patch.object(
                agent.provider, "generate", return_value=ModelReply("gagal", "timeout", "fake", "fake")
            ):
                result = agent.handle("ubah BAB II")
            self.assertEqual(result.status, "sementara_gagal")
            self.assertEqual(agent._proposed_focus, "")
            self.assertEqual(agent._outline_text, "")
            result = agent.handle("lanjutkan")
            self.assertEqual(result.status, "berhasil")
            self.assertEqual(agent.phase, "outline_confirmation")
            self.assertEqual(agent.brief.focus, "")
            self.assertIn("ubah BAB II", agent.provider.calls[-1]["messages"][-1]["content"])
            agent.handle("lanjutkan")
            self.assertEqual(agent.phase, "cover")

    def test_conditional_approval_and_new_data_are_not_approval(self):
        for text in ("setuju tapi fokus ke sekolah", "oke lanjut semester 2", "setuju, hapus", "boleh lanjut?", "sudah sesuai kecuali BAB II", "setuju asal lebih ringkas"):
            with self.subTest(text=text):
                self.assertFalse(DocumentAgent._outline_approved(text))

    def test_citation_preference_preserves_actual_content_restriction(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = self.make_agent(tmp)
            agent.brief.apply_ai_values({"must_avoid": "tanpa Ibid, jangan bahas sejarah AI"})
            self.assertEqual(agent.brief.must_avoid, "jangan bahas sejarah AI")
            agent.brief.apply_ai_values({"must_avoid": "pakai short note"})
            self.assertEqual(agent.brief.must_avoid, "jangan bahas sejarah AI")


if __name__ == "__main__":
    unittest.main()
