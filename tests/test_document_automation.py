import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from app.document_agent import DocumentAgent
from app.document_draft import DraftGenerator
from app.document_preferences import DocumentPreferenceStore
from app.document_research import DocumentResearch
from app.providers.base import ModelReply
from app.research_manager import ResearchResult, ResearchSource
from app.source_registry import SourceRegistry


SOURCE = ResearchSource(
    provider="test", title="Agents for education", authors=("Test Author",),
    year=2025, doi="10.1234/test", work_type="journal-article",
    abstract="Agents assist students with learning tasks.",
)
OUTLINE = "## Kerangka Makalah\nBAB I\nBAB II\nBAB III\nDAFTAR PUSTAKA"
DRAFT = {"preface": ["Kata pengantar."], "sections": [
    {"title": "BAB I PENDAHULUAN", "level": 1, "paragraphs": ["Agen membantu siswa [[R1]]."]},
    {"title": "BAB II PEMBAHASAN", "level": 1, "paragraphs": ["Pemanfaatan agen [[R1]]."]},
    {"title": "BAB III PENUTUP", "level": 1, "paragraphs": ["Kesimpulan."]},
]}


class Provider:
    configured = True
    provider_name = "test"
    model_name = "test"

    def __init__(self):
        self.calls = []
        self.selection = {"sufficient": True, "selected_indices": [1]}
        self.draft = DRAFT
        self.fail_draft = False

    def generate(self, messages, **kwargs):
        self.calls.append(messages)
        instruction = messages[0]["content"]
        if "kueri pencarian" in instruction:
            value = {"queries": ["AI agents education"]}
        elif "Pilih sumber" in instruction:
            value = self.selection
        else:
            if self.fail_draft:
                return ModelReply("gagal", "timeout", "test", "test")
            value = self.draft
        return ModelReply("berhasil", json.dumps(value), "test", "test")


class Research:
    def __init__(self):
        self.calls = []
        self.sources = (SOURCE,)

    def search(self, query, **kwargs):
        self.calls.append(query)
        return ResearchResult("berhasil", query, self.sources)


class DocumentAutomationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.provider = Provider()
        self.research = Research()
        self.registry = SourceRegistry(Path(self.tmp.name) / "sources.db")
        self.agent = DocumentAgent(
            self.provider, research=self.research, registry=self.registry,
            preference_store=DocumentPreferenceStore(Path(self.tmp.name) / "prefs.db"),
            source_scope="order-a",
        )
        self.agent.brief.apply_ai_values({
            "institution_level": "SMK", "class_semester": "XII Semester 1",
            "subject": "Informatika", "topic_title": "AI Agent", "target_length": "8 halaman",
            "focus": "AI Agent untuk pembelajaran",
        })
        self.agent.cover.assignment_type = "individu"
        self.agent.cover.author_name = "Siswa Uji"
        self.agent._outline_text = OUTLINE
        self.agent.phase = "ready_for_draft"

    def test_natural_continue_researches_registers_and_drafts_without_commands(self):
        self.registry.add_sources("order-b", [replace(SOURCE, title="Other order")])
        result = self.agent.handle("lanjutkan")
        self.assertEqual(result.status, "draft_ready")
        self.assertEqual(self.agent.phase, "draft_ready")
        self.assertEqual(len(self.registry.list_sources("order-a")), 1)
        self.assertEqual(self.registry.list_sources("order-b")[0].title, "Other order")
        self.assertEqual(len(self.provider.calls), 3)
        for call in self.provider.calls:
            self.assertIn("AI Agent untuk pembelajaran", call[-1]["content"])
        self.assertNotIn("Siswa Uji", self.provider.calls[0][-1]["content"])
        self.assertNotIn("Other order", self.provider.calls[-1][-1]["content"])
        self.assertNotIn("/draft", result.text)
        with patch.object(self.agent, "build_final", return_value=result) as final:
            self.agent.handle("lanjutkan")
            final.assert_called_once()
        self.assertEqual(len(self.provider.calls), 3)

    def test_source_without_abstract_stops_before_draft_and_preserves_data(self):
        self.research.sources = (replace(SOURCE, abstract=""),)
        result = self.agent.handle("sudah cukup")
        self.assertEqual(result.status, "membutuhkan_sumber")
        self.assertEqual(self.agent.phase, "ready_for_draft")
        self.assertEqual(self.agent.cover.author_name, "Siswa Uji")
        self.assertIsNone(self.agent.draft_spec)
        self.assertEqual(len(self.provider.calls), 1)
        self.assertEqual(self.registry.list_sources("order-a"), [])

    def test_unmet_source_requirements_stop_without_registry_write(self):
        self.agent.brief.source_requirements = "minimal 3 jurnal tahun 2026"
        self.provider.selection = {"sufficient": False, "selected_indices": []}
        result = self.agent.handle("lanjutkan")
        self.assertEqual(result.status, "membutuhkan_sumber")
        self.assertIn("minimal 3 jurnal tahun 2026", self.provider.calls[-1][-1]["content"])
        self.assertEqual(self.registry.list_sources("order-a"), [])

    def test_invalid_selection_never_writes_or_drafts(self):
        for indices in ([99], [True], [1, 1], "1"):
            with self.subTest(indices=indices):
                self.provider.selection = {"sufficient": True, "selected_indices": indices}
                self.assertEqual(self.agent.handle("lanjutkan").status, "sementara_gagal")
                self.assertEqual(self.registry.list_sources("order-a"), [])
                self.assertIsNone(self.agent.draft_spec)

    def test_draft_failure_reuses_selected_sources_on_retry(self):
        self.provider.fail_draft = True
        self.assertNotEqual(self.agent.handle("lanjutkan").status, "draft_ready")
        self.assertEqual(self.agent.phase, "ready_for_draft")
        self.provider.fail_draft = False
        self.assertEqual(self.agent.handle("lanjutkan").status, "draft_ready")
        self.assertEqual(len(self.research.calls), 1)
        self.assertEqual(len(self.registry.list_sources("order-a")), 1)

    def test_revision_and_cover_correction_do_not_start_research(self):
        self.agent.handle("Nama guru Nurhayati")
        self.assertEqual(self.agent.cover.teacher_name, "Nurhayati")
        self.agent.handle("jangan lanjut dulu")
        self.assertEqual(self.research.calls, [])

    def test_incomplete_cover_cannot_start_automatic_work(self):
        self.agent.cover.author_name = ""
        self.assertEqual(self.agent.handle("lanjutkan").status, "membutuhkan_bantuan")
        self.assertEqual(self.research.calls, [])

    def test_concurrent_message_cannot_duplicate_work_or_reset_session(self):
        self.agent._handle_lock.acquire()
        try:
            self.assertEqual(self.agent.handle("lanjutkan").status, "sedang_diproses")
            self.assertEqual(self.agent.handle("/makalah_baru").status, "sedang_diproses")
        finally:
            self.agent._handle_lock.release()
        self.assertEqual(self.research.calls, [])
        self.assertEqual(self.agent.brief.topic_title, "AI Agent")

    def test_reset_invalidates_cached_selection(self):
        self.agent.handle("lanjutkan")
        self.agent.handle("/makalah_baru")
        self.assertEqual(self.agent._automatic_source_ids, set())
        self.assertEqual(self.registry.list_sources("order-a"), [])

    def test_unknown_or_absent_citations_do_not_become_draft_ready(self):
        for paragraph in ("Klaim [[R999]].", "Klaim tanpa sitasi.", "Klaim [[R1, R2]]."):
            with self.subTest(paragraph=paragraph):
                self.provider.draft = {"sections": [{"title": "BAB I", "paragraphs": [paragraph]}]}
                result = self.agent.handle("lanjutkan")
                self.assertNotEqual(result.status, "draft_ready")
                self.assertIsNone(self.agent.draft_spec)

    def test_citations_cannot_hide_in_preface_or_heading(self):
        for payload in (
            {**DRAFT, "preface": ["[[R999]]"]},
            {"sections": [{"title": "BAB I [[R999]]", "paragraphs": ["Isi [[R1]]."]}]},
        ):
            with self.assertRaises(ValueError):
                DraftGenerator._validate(payload, {"R1"})

    def test_length_guidance_accepts_brief_v2_label(self):
        self.assertIn("8 halaman SETELAH COVER", DraftGenerator._length_guidance(self.agent.brief.structured_text()))

    def test_ineligible_metadata_is_not_treated_as_verified_source(self):
        for source in (replace(SOURCE, authors=()), replace(SOURCE, year=9999),
                       replace(SOURCE, doi="", url="file:///tmp/source")):
            with self.subTest(source=source):
                self.assertFalse(DocumentResearch.eligible(source))

    def test_negative_request_cannot_trigger_final_file(self):
        self.assertFalse(DocumentAgent._wants_final_file("jangan buat file dulu"))

    def test_sudah_cukup_is_accepted_and_retry_uses_natural_language(self):
        self.research.sources = (replace(SOURCE, abstract=""),)
        result = self.agent.handle("sudah cukup")
        self.assertIn("Persetujuan Anda sudah diterima", result.text)
        self.assertIn("abstraknya belum lengkap", result.text)
        self.assertNotIn("`lanjutkan`", result.text)
        self.assertEqual(len(self.research.calls), 1)
        self.research.sources = (SOURCE,)
        self.assertEqual(self.agent.handle("coba lagi").status, "draft_ready")
        self.assertEqual(len(self.research.calls), 2)

    def test_search_failure_has_its_own_message(self):
        with patch.object(self.research, "search", return_value=ResearchResult("gagal", "test")):
            result = self.agent.handle("ulangi riset")
        self.assertIn("Pencarian sumber belum berhasil", result.text)
        self.assertNotIn("abstraknya belum lengkap", result.text)
        self.assertIsNone(self.agent.draft_spec)

    def test_invalid_plan_is_not_reported_as_missing_sources(self):
        with patch.object(self.provider, "generate", return_value=ModelReply("berhasil", "bad JSON", "test", "test")):
            result = self.agent.handle("sudah cukup")
        self.assertIn("Kata kunci pencarian dari AI belum dapat diproses", result.text)
        self.assertEqual(self.research.calls, [])

    def test_invalid_selection_is_distinct_from_insufficient_sources(self):
        self.provider.selection = {"sufficient": "true", "selected_indices": [1]}
        result = self.agent.handle("coba lagi")
        self.assertIn("hasil pemilihan sumber dari AI belum dapat diproses", result.text)
        self.assertEqual(self.registry.list_sources("order-a"), [])

    def test_research_retry_does_not_treat_negative_or_question_as_consent(self):
        for raw in ("jangan coba lagi", "sudah cukup tapi ubah guru", "coba lagi?"):
            with self.subTest(raw=raw):
                self.assertFalse(DocumentAgent._wants_research(raw))


if __name__ == "__main__":
    unittest.main()
