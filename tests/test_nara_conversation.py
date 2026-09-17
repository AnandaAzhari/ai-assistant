"""Protocol/state integration tests. Live model understanding is a separate smoke test."""
import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from app.document_agent import DocumentAgent, DocumentResult
from app.document_engine import DocumentSection, MakalahSpec
from app.document_intake import IntakeInterpreter
from app.document_preferences import DocumentPreferenceStore
from app.document_session import DocumentSessionStore
from app.lead import LeadAgent
from app.providers.base import ModelReply
from app.source_registry import SourceRegistry

OUTLINE = '## Usulan Fokus\nAI untuk belajar.\n## Kerangka Makalah\nBAB I\nBAB II\nBAB III\nDAFTAR PUSTAKA'


class Provider:
    configured = True
    provider_name = model_name = 'test'

    def __init__(self):
        self.payload = None
        self.calls = []
        self.fail = False

    def generate(self, messages, **kwargs):
        self.calls.append(messages)
        if self.fail:
            return ModelReply('gagal', 'timeout', 'test', 'test')
        text = json.dumps(self.payload, ensure_ascii=False) if 'interpreter MakalahBrief' in messages[0]['content'] else OUTLINE
        return ModelReply('berhasil', text, 'test', 'test')


class NaraConversationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / 'nara.db'
        self.provider = Provider()
        self.agent = self.make_agent()

    def make_agent(self, scope='a'):
        return DocumentAgent(self.provider,
            preference_store=DocumentPreferenceStore(self.db),
            registry=SourceRegistry(self.db), source_scope=scope,
            session_store=DocumentSessionStore(self.db))

    def brief(self):
        self.agent.brief.apply_ai_values(dict(institution_level='SMK', class_semester='Kelas XII, Semester 1',
            subject='Informatika', topic_title='AI Agent', target_length='8 halaman'))

    def outline(self):
        self.brief()
        self.agent._outline_text = OUTLINE
        self.agent._proposed_focus = 'AI untuk belajar.'
        self.agent.phase = 'outline_confirmation'

    def cover(self):
        self.outline()
        self.agent.phase = 'cover'

    def ready(self):
        self.cover()
        self.agent.cover.assignment_type = 'individu'
        self.agent.cover.author_name = 'Rani'
        self.agent.phase = 'ready_for_draft'

    def turn(self, raw, intent='update', *, brief=None, cover=None, clarification='', reply=''):
        b, c = brief or {}, cover or {}
        self.provider.payload = {'brief': b, 'cover': c,
            'evidence': {f'{kind}.{key}': raw for kind, values in [('brief', b), ('cover', c)] for key in values},
            'intent': intent, 'intent_evidence': raw, 'reply': reply, 'clarification': clarification}
        return self.agent.handle(raw)

    def test_combined_user_report_captures_five_fields_without_reasking_name(self):
        self.cover()
        result = self.turn('individu, ananda azhari batubara, SMK negeri 2 padangsidimpuan, 2026/2027, guru purnama sari', cover={
            'assignment_type': 'individu', 'author_name': 'Ananda Azhari Batubara',
            'institution_name': 'SMK Negeri 2 Padangsidimpuan', 'academic_year': '2026/2027', 'teacher_name': 'Purnama Sari'})
        self.assertEqual(self.agent.cover.author_name, 'Ananda Azhari Batubara')
        self.assertEqual(self.agent.cover.academic_year, '2026/2027')
        self.assertEqual(self.agent.cover.teacher_name, 'Purnama Sari')
        self.assertNotIn('Siapa **nama penyusun', result.text)
        self.assertEqual(self.agent.phase, 'ready_for_draft')
        self.assertEqual(len(self.provider.calls), 1)

    def test_cover_saved_before_requirements_complete(self):
        self.turn('saya Rani, ngerjain sendiri', cover={'author_name': 'Rani', 'assignment_type': 'individu'})
        self.assertEqual(self.agent.phase, 'requirements')
        self.assertEqual(self.agent.cover.author_name, 'Rani')
        self.assertEqual(self.agent.brief.topic_title, '')

    def test_ai_success_does_not_run_keyword_fallback(self):
        with patch.object(self.agent.cover, 'update') as local_cover, patch.object(self.agent.brief, 'apply_local_fallback') as local_brief:
            self.turn('nama belum diputuskan', clarification='Nama siapa yang akan digunakan?')
        local_cover.assert_not_called()
        local_brief.assert_not_called()
        self.assertEqual(self.agent.cover.author_name, '')

    def test_partial_correction_preserves_other_data_and_revises_outline(self):
        self.outline()
        result = self.turn('eh salah semester dua', brief={'class_semester': 'Kelas XII, Semester 2'})
        self.assertEqual(self.agent.brief.class_semester, 'Kelas XII, Semester 2')
        self.assertEqual(self.agent.brief.subject, 'Informatika')
        self.assertEqual(self.agent.phase, 'outline_confirmation')
        self.assertEqual(result.status, 'berhasil')
        self.assertEqual(self.agent.brief.focus, '')

    def test_semantic_approval_locks_focus_and_asks_only_missing_cover(self):
        self.outline()
        result = self.turn('rancangannya cocok buat tugas saya', 'approve', cover={})
        self.assertEqual(self.agent.brief.focus, 'AI untuk belajar.')
        self.assertEqual(self.agent.phase, 'cover')
        self.assertEqual(result.status, 'needs_cover')

    def test_approval_is_retained_while_cover_is_completed(self):
        self.outline()
        self.turn('boleh diteruskan', 'continue')
        with patch.object(self.agent, '_research_and_draft', return_value=DocumentResult('draft_ready', 'Draft uji')) as research:
            self.turn('Rani, saya mengerjakannya sendiri', cover={'author_name': 'Rani', 'assignment_type': 'individu'})
        research.assert_called_once()

    def test_conditional_approval_revises_instead_of_locking(self):
        self.outline()
        with patch.object(self.agent, '_research_and_draft') as research:
            self.turn('boleh, tapi BAB II bahas dampak di sekolah', 'revise')
        self.assertEqual(self.agent.phase, 'outline_confirmation')
        self.assertEqual(self.agent.brief.focus, '')
        research.assert_not_called()

    def test_question_keeps_outline_and_no_generation(self):
        self.outline()
        result = self.turn('kenapa perlu BAB II?', 'question', reply='BAB II memuat pembahasan utama.')
        self.assertEqual(result.status, 'answered')
        self.assertEqual(self.agent._outline_text, OUTLINE)
        self.assertEqual(self.agent.phase, 'outline_confirmation')
        self.assertEqual(len(self.provider.calls), 1)

    def test_ambiguous_name_never_assigned_to_wrong_role(self):
        self.cover()
        result = self.turn('Rani atau Ratna saya lupa', clarification='Siapa nama penyusunnya?')
        self.assertEqual(result.status, 'needs_clarification')
        self.assertEqual(self.agent.cover.author_name, '')
        self.assertEqual(self.agent.cover.teacher_name, '')

    def test_pause_stores_correction_without_triggering_research(self):
        self.ready()
        self.agent._continue_after_cover = True
        with patch.object(self.agent, '_research_and_draft') as research:
            result = self.turn('tunggu dulu, tahun 2027/2028', 'pause', cover={'academic_year': '2027/2028'})
        self.assertEqual(result.status, 'paused')
        self.assertEqual(self.agent.cover.academic_year, '2027/2028')
        self.assertFalse(self.agent._continue_after_cover)
        research.assert_not_called()

    def test_cukup_runs_research_once_with_complete_cover(self):
        self.ready()
        with patch.object(self.agent, '_research_and_draft', return_value=DocumentResult('membutuhkan_sumber', 'Sumber belum cukup')) as research:
            result = self.turn('datanya sudah cukup kok', 'continue')
        research.assert_called_once()
        self.assertEqual(result.status, 'membutuhkan_sumber')

    def test_continue_with_missing_cover_cannot_bypass_guard(self):
        self.cover()
        with patch.object(self.agent, '_research_and_draft') as research:
            result = self.turn('teruskan saja sampai selesai', 'continue')
        self.assertEqual(result.status, 'needs_cover')
        research.assert_not_called()

    def test_brief_revision_invalidates_previous_draft(self):
        self.ready()
        self.set_draft()
        self.turn('ubah jadi 10 halaman lalu lanjut', 'continue', brief={'target_length': '10 halaman'})
        self.assertIsNone(self.agent.draft_spec)
        self.assertEqual(self.agent.phase, 'outline_confirmation')
        self.assertEqual(self.agent._final_docx_path, '')

    def set_draft(self):
        self.agent._draft_spec = MakalahSpec('test', 'AI Agent', 'Sekolah', 'XII', 'Informatika', author='Rani',
            preface=('Kata pengantar',), sections=(DocumentSection('a. Rincian', ('Teks [[R1]]',), 4),))
        self.agent.phase = 'draft_ready'

    def test_cover_correction_updates_existing_draft_without_regeneration(self):
        self.ready()
        self.set_draft()
        self.agent.phase = 'final_ready'
        self.agent._final_docx_path = 'old.docx'
        self.turn('gurunya Bu Ratna', cover={'teacher_name': 'Bu Ratna'})
        self.assertEqual(self.agent.draft_spec.teacher, 'Bu Ratna')
        self.assertEqual(self.agent.draft_spec.sections[0].level, 4)
        self.assertEqual(self.agent.phase, 'draft_ready')
        self.assertEqual(self.agent._final_docx_path, '')

    def test_group_switch_does_not_leak_previous_author(self):
        self.ready()
        self.set_draft()
        self.turn('ternyata kelompok Rani dan Budi', cover={'assignment_type': 'kelompok', 'group_members': 'Rani, Budi'})
        self.assertEqual(self.agent.cover.author_name, '')
        self.assertEqual(self.agent.draft_spec.author, '')
        self.assertEqual(self.agent.draft_spec.members, ('Rani', 'Budi'))

    def test_explicit_clear_reopens_required_question(self):
        self.ready()
        result = self.turn('hapus dulu nama penyusunnya', cover={'author_name': ''})
        self.assertEqual(self.agent.cover.author_name, '')
        self.assertEqual(result.status, 'needs_cover')

    def test_new_turn_has_previous_question_and_real_state_in_context(self):
        self.cover()
        self.turn('individu', cover={'assignment_type': 'individu'})
        self.turn('Rani', cover={'author_name': 'Rani'})
        context = self.provider.calls[-1][1]['content']
        self.assertIn('nama penyusun', context)
        self.assertIn('"assignment_type": "individu"', context)

    def test_identity_and_skill_are_loaded_at_runtime(self):
        self.turn('halo', 'question', reply='Halo, saya Nara.')
        instruction = self.provider.calls[-1][0]['content']
        self.assertIn('Nara — Document Agent', instruction)
        self.assertIn('Percakapan Nara — AI-first', instruction)

    def test_restart_restores_data_outline_focus_and_conversation(self):
        self.outline()
        self.turn('setuju, nama saya Rani', 'approve', cover={'author_name': 'Rani'})
        restored = self.make_agent()
        self.assertEqual(restored.cover.author_name, 'Rani')
        self.assertEqual(restored.brief.focus, 'AI untuk belajar.')
        self.assertEqual(restored.phase, 'cover')
        self.assertTrue(restored._continue_after_cover)
        self.assertTrue(restored._conversation)
        self.assertEqual(restored._outline_text, OUTLINE)

    def test_restart_restores_draft_level_four_and_scope_isolation(self):
        self.ready()
        self.set_draft()
        self.turn('gurunya Ratna', cover={'teacher_name': 'Ratna'})
        restored = self.make_agent()
        self.assertEqual(restored.draft_spec.teacher, 'Ratna')
        self.assertEqual(restored.draft_spec.sections[0].level, 4)
        other = self.make_agent('b')
        self.assertEqual(other.cover.author_name, '')
        self.assertEqual(other._conversation, [])
        self.assertIsNone(other.draft_spec)

    def test_reset_persists_empty_session(self):
        self.turn('nama saya Rani', cover={'author_name': 'Rani'})
        self.agent.handle('/makalah_baru')
        restored = self.make_agent()
        self.assertEqual(restored.cover.author_name, '')
        self.assertEqual(restored.phase, 'requirements')
        self.assertEqual(restored._conversation, [])

    def test_lead_reset_also_clears_persisted_session(self):
        self.turn('nama saya Rani', cover={'author_name': 'Rani'})
        lead = LeadAgent(document=self.agent)
        lead.handle_admin_message('/makalah_baru')
        self.assertEqual(self.make_agent().cover.author_name, '')

    def test_missing_final_file_is_rebuilt_from_restored_draft(self):
        self.ready()
        self.set_draft()
        self.agent.phase = 'final_ready'
        self.agent._final_docx_path = str(Path(self.tmp.name) / 'missing.docx')
        self.agent._save_session()
        restored = self.make_agent()
        self.assertEqual(restored.phase, 'draft_ready')
        self.assertEqual(restored._final_docx_path, '')
        self.assertIsNotNone(restored.draft_spec)

    def test_data_checkpoint_exists_before_outline_provider_call(self):
        self.brief()
        self.agent.cover.author_name = 'Rani'
        original = self.provider.generate
        def check_saved(messages, **kwargs):
            payload = self.agent.session_store.load('a')
            self.assertEqual(payload['cover']['author_name'], 'Rani')
            return original(messages, **kwargs)
        with patch.object(self.provider, 'generate', side_effect=check_saved):
            self.agent._generate_outline('buat kerangka')

    def test_failed_revision_does_not_restore_stale_approval(self):
        self.outline()
        payload = {'brief': {}, 'cover': {}, 'evidence': {}, 'intent': 'revise',
            'intent_evidence': 'ubah BAB II', 'reply': '', 'clarification': ''}
        real = self.provider.generate
        def fail_outline(messages, **kwargs):
            if 'interpreter MakalahBrief' in messages[0]['content']:
                return ModelReply('berhasil', json.dumps(payload), 'test', 'test')
            return ModelReply('gagal', 'timeout', 'test', 'test')
        with patch.object(self.provider, 'generate', side_effect=fail_outline):
            result = self.agent.handle('ubah BAB II')
        self.assertEqual(result.status, 'sementara_gagal')
        restored = self.make_agent()
        self.assertEqual(restored._outline_text, '')
        self.assertEqual(restored._proposed_focus, '')
        self.agent = restored
        self.turn('setuju', 'approve')
        self.assertEqual(self.agent.phase, 'outline_confirmation')
        self.assertEqual(self.agent.brief.focus, '')

    def test_storage_failure_is_reported_and_memory_preserved(self):
        with patch.object(self.agent.session_store, 'save', side_effect=OSError('disk full')):
            result = self.turn('saya Rani', cover={'author_name': 'Rani'})
        self.assertEqual(result.status, 'session_save_failed')
        self.assertEqual(self.agent.cover.author_name, 'Rani')

    def test_invalid_schema_and_ungrounded_updates_are_rejected(self):
        base = {'brief': {}, 'cover': {}, 'evidence': {}, 'intent': 'update'}
        bad = [
            {**base, 'cover': {'author_name': 42}},
            {**base, 'cover': {'author_name': 'Nama karangan'}},
            {**base, 'cover': {'academic_year': '2026/2027, sekolah SMK'}, 'evidence': {'cover.academic_year': '2026/2027'}},
            {**base, 'phase': 'final_ready'},
            {**base, 'intent': 'execute_shell'},
            {**base, 'intent': 'approve', 'intent_evidence': 'setuju'},
            {**base, 'brief': {'target_length': {'x': 1}}},
        ]
        for payload in bad:
            with self.subTest(payload=payload):
                self.provider.payload = payload
                result = self.agent.intake_interpreter.interpret('2026/2027', '')
                self.assertEqual(result.status, 'gagal')
                self.assertEqual(result.values, {})
                self.assertEqual(result.cover_values, {})

    def test_provider_failure_uses_local_fallback_only_once(self):
        self.provider.fail = True
        self.cover()
        result = self.agent.handle('individu, Rani, SMK Contoh, 2026/2027, guru Ratna')
        self.assertEqual(self.agent.cover.author_name, 'Rani')
        self.assertEqual(result.status, 'cover_complete')
        self.assertEqual(len(self.provider.calls), 1)


if __name__ == '__main__':
    unittest.main()
