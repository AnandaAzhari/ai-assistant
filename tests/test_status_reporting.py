"""Fitur "indikator status berjalan" (branch `fitur-status-indikator-telegram`):
`on_status` opsional yang diteruskan `LeadAgent.handle_admin_message` ->
`DocumentAgent.handle`/`FinanceService.handle`/`ContentStudio.generate_draft`,
serta `_StatusReporter` di `app/telegram.py` yang memakainya untuk mengedit SATU
pesan status Telegram di tempat (bukan menumpuk pesan baru tiap tahap).

Prinsip yang diuji di sini:
1. Best-effort murni: kegagalan pelapor status (exception dari callback, atau
   TelegramError dari API) TIDAK PERNAH menggagalkan proses utama.
2. Channel-agnostic: `on_status` defaultnya None di semua tempat -> WhatsApp
   dan Web Admin (yang tidak pernah mengirim argumen ini) nol perubahan
   perilaku (dibuktikan terpisah di tests/test_customer_channel.py, di mana
   FakeCustomerDocumentAgent.handle(raw) TIDAK menerima on_status sama sekali
   -> kalau app/lead.py pernah salah meneruskannya ke jalur pelanggan, test
   itu akan gagal dengan TypeError).
3. `_StatusReporter`: kirim sekali, lalu edit di tempat untuk pembaruan
   berikutnya -- tidak pernah menumpuk pesan status terpisah.
"""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, Mock

from app.content_studio import ContentStudio
from app.brand_profile import BrandProfileStore
from app.document_agent import DocumentAgent
from app.finance import FinanceService
from app.finance_query import FinanceQueryInterpreter
from app.lead import LeadAgent, LeadReply
from app.providers.base import ModelReply
from app.telegram import AdminIdentity, TelegramAdminAdapter, TelegramError, _StatusReporter


# ---------------------------------------------------------------------------
# _StatusReporter (app/telegram.py) — pelapor satu-pesan per update Telegram.
# ---------------------------------------------------------------------------

class FakeTelegramClient:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.sent: list[tuple[int, str, int | None]] = []
        self.edits: list[tuple[int, int, str]] = []
        self.deletes: list[tuple[int, int]] = []
        self._next_message_id = 100

    def send_message(self, chat_id, text, *, message_thread_id=None):
        if self.fail:
            raise TelegramError("gagal kirim")
        self.sent.append((chat_id, text, message_thread_id))
        message_id = self._next_message_id
        self._next_message_id += 1
        return {"message_id": message_id}

    def edit_message_text(self, chat_id, message_id, text):
        if self.fail:
            raise TelegramError("gagal edit")
        self.edits.append((chat_id, message_id, text))

    def delete_message(self, chat_id, message_id):
        if self.fail:
            raise TelegramError("gagal hapus")
        self.deletes.append((chat_id, message_id))


class StatusReporterTests(unittest.TestCase):
    def test_first_call_sends_a_new_message(self):
        client = FakeTelegramClient()
        reporter = _StatusReporter(client, 111, None)
        reporter("Tahap 1...")
        self.assertEqual(client.sent, [(111, "Tahap 1...", None)])
        self.assertEqual(client.edits, [])

    def test_second_call_with_different_text_edits_the_same_message_in_place(self):
        client = FakeTelegramClient()
        reporter = _StatusReporter(client, 111, None)
        reporter("Tahap 1...")
        reporter("Tahap 2...")
        self.assertEqual(len(client.sent), 1)
        self.assertEqual(client.edits, [(111, 100, "Tahap 2...")])

    def test_repeated_identical_text_is_a_no_op(self):
        client = FakeTelegramClient()
        reporter = _StatusReporter(client, 111, None)
        reporter("Tahap 1...")
        reporter("Tahap 1...")
        self.assertEqual(len(client.sent), 1)
        self.assertEqual(client.edits, [])

    def test_empty_text_is_a_no_op(self):
        client = FakeTelegramClient()
        reporter = _StatusReporter(client, 111, None)
        reporter("")
        self.assertEqual(client.sent, [])

    def test_clear_deletes_the_status_message(self):
        client = FakeTelegramClient()
        reporter = _StatusReporter(client, 111, None)
        reporter("Tahap 1...")
        reporter.clear()
        self.assertEqual(client.deletes, [(111, 100)])

    def test_clear_without_any_status_sent_is_a_no_op(self):
        client = FakeTelegramClient()
        reporter = _StatusReporter(client, 111, None)
        reporter.clear()
        self.assertEqual(client.deletes, [])

    def test_reporter_survives_telegram_errors_without_raising(self):
        client = FakeTelegramClient(fail=True)
        reporter = _StatusReporter(client, 111, None)
        reporter("Tahap 1...")  # tidak boleh melempar TelegramError
        reporter.clear()  # begitu juga ini
        self.assertEqual(client.sent, [])
        self.assertEqual(client.deletes, [])

    def test_thread_id_is_forwarded_to_send_message_for_topic_replies(self):
        client = FakeTelegramClient()
        reporter = _StatusReporter(client, 111, 42)
        reporter("Tahap 1...")
        self.assertEqual(client.sent, [(111, "Tahap 1...", 42)])


# ---------------------------------------------------------------------------
# TelegramAdminAdapter.process_update -> on_status wiring end-to-end.
# ---------------------------------------------------------------------------

class TelegramStatusWiringTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeTelegramClient()

    def _adapter(self, handler):
        return TelegramAdminAdapter(self.client, AdminIdentity(user_id=1, chat_id=2), handler)

    def _update(self, text="halo"):
        return {
            "update_id": 1,
            "message": {"from": {"id": 1}, "chat": {"id": 2, "type": "private"}, "text": text},
        }

    def test_handler_receives_a_status_reporter_it_can_call(self):
        seen = []

        def handler(text, *, agent_hint=None, on_status=None):
            if on_status is not None:
                on_status("Sedang memproses...")
            seen.append(on_status)
            return LeadReply("lead", "berhasil", "Selesai")

        adapter = self._adapter(handler)
        adapter.process_update(self._update())
        self.assertEqual(len(seen), 1)
        self.assertIsNotNone(seen[0])
        # Pesan status terkirim selama pemrosesan (sebelum balasan final "Selesai").
        self.assertEqual([s[1] for s in self.client.sent], ["Sedang memproses...", "Selesai"])

    def test_status_message_is_deleted_before_final_reply_is_sent(self):
        def handler(text, *, agent_hint=None, on_status=None):
            on_status("Sedang memproses...")
            return LeadReply("lead", "berhasil", "Selesai")

        adapter = self._adapter(handler)
        adapter.process_update(self._update())
        # ...dan dibersihkan (dihapus) sebelum balasan final ("Selesai") dikirim.
        self.assertEqual(self.client.deletes, [(2, 100)])
        self.assertEqual(self.client.sent[-1], (2, "Selesai", None))

    def test_status_reporter_is_still_cleared_when_handler_raises(self):
        def handler(text, *, agent_hint=None, on_status=None):
            on_status("Sedang memproses...")
            raise RuntimeError("meledak di tengah jalan")

        adapter = self._adapter(handler)
        adapter.process_update(self._update())
        self.assertEqual(self.client.deletes, [(2, 100)])

    def test_no_status_call_means_no_extra_message_sent(self):
        def handler(text, *, agent_hint=None, on_status=None):
            return LeadReply("lead", "berhasil", "Selesai")

        adapter = self._adapter(handler)
        adapter.process_update(self._update())
        # Cuma balasan final -- tidak ada pesan status yang sempat terkirim/dihapus.
        self.assertEqual(self.client.sent, [(2, "Selesai", None)])
        self.assertEqual(self.client.deletes, [])


# ---------------------------------------------------------------------------
# DocumentAgent (Nara) — 4 tahap: kerangka, riset, tulis draft, render file.
# ---------------------------------------------------------------------------

class OutlineProvider:
    """1 panggilan melengkapi brief lewat parser lokal, panggilan ke-2 membuat
    kerangka -- pola sama dengan BriefCompletingProvider di test_document_agent.py."""
    configured = True
    provider_name = "FakeAI"
    model_name = "fake-model"

    def __init__(self):
        self.calls = []

    def generate(self, messages, *, max_tokens=1200, temperature=0.4, timeout=45):
        self.calls.append(messages)
        return ModelReply(
            "berhasil",
            "## Kerangka Makalah\nBAB I Pendahuluan\nBAB II Pembahasan\nBAB III Penutup",
            self.provider_name, self.model_name, 80, 40,
        )


class DocumentAgentStatusReportingTests(unittest.TestCase):
    def test_on_status_receives_outline_stage_message(self):
        provider = OutlineProvider()
        agent = DocumentAgent(provider)
        seen: list[str] = []
        result = agent.handle(
            "Saya SMK kelas XII semester 2, mata pelajaran Informatika, "
            "mau bikin makalah tentang AI Agent, jumlah 8 halaman, individu, nama saya Budi",
            on_status=seen.append,
        )
        self.assertIn("✍️ Nara sedang menyusun kerangka...", seen)

    def test_omitting_on_status_does_not_raise(self):
        provider = OutlineProvider()
        agent = DocumentAgent(provider)
        # Sama sekali tidak mengirim on_status -- harus berperilaku persis seperti
        # sebelum fitur ini ada (default None, lihat _emit_status).
        result = agent.handle(
            "Saya SMK kelas XII semester 2, mata pelajaran Informatika, "
            "mau bikin makalah tentang AI Agent, jumlah 8 halaman, individu, nama saya Budi",
        )
        self.assertNotEqual(result.status, "sementara_gagal")

    def test_on_status_is_cleared_after_handle_returns(self):
        provider = OutlineProvider()
        agent = DocumentAgent(provider)
        agent.handle("Saya mau makalah tentang AI", on_status=lambda text: None)
        self.assertIsNone(agent._on_status)

    def test_a_raising_on_status_callback_never_breaks_the_document_flow(self):
        provider = OutlineProvider()
        agent = DocumentAgent(provider)

        def boom(text):
            raise RuntimeError("pelapor status rusak")

        result = agent.handle(
            "Saya SMK kelas XII semester 2, mata pelajaran Informatika, "
            "mau bikin makalah tentang AI Agent, jumlah 8 halaman, individu, nama saya Budi",
            on_status=boom,
        )
        # Best-effort: kegagalan callback status tidak pernah menggagalkan alur utama.
        self.assertIn(result.status, {"berhasil", "cover_complete", "draft_ready"})


SOURCE_KW = dict(
    provider="test", title="Agents for education", authors=("Test Author",),
    year=2025, doi="10.1234/test", work_type="journal-article",
    abstract="Agents assist students with learning tasks.",
)
DRAFT = {"preface": ["Kata pengantar."], "sections": [
    {"title": "BAB I PENDAHULUAN", "level": 1, "paragraphs": ["Agen membantu siswa [[R1]]."]},
]}


class ResearchDraftProvider:
    configured = True
    provider_name = "test"
    model_name = "test"

    def __init__(self):
        self.calls = []

    def generate(self, messages, **kwargs):
        self.calls.append(messages)
        instruction = messages[0]["content"]
        if "kueri pencarian" in instruction:
            value = {"queries": ["AI agents education"]}
        elif "Pilih sumber" in instruction:
            value = {"sufficient": True, "selected_indices": [1]}
        else:
            value = DRAFT
        return ModelReply("berhasil", json.dumps(value), "test", "test")


class ResearchManager:
    def __init__(self, source):
        self.source = source

    def search(self, query, **kwargs):
        from app.research_manager import ResearchResult
        return ResearchResult("berhasil", query, (self.source,))


class DocumentAgentResearchAndDraftStatusTests(unittest.TestCase):
    def setUp(self):
        from app.document_preferences import DocumentPreferenceStore
        from app.research_manager import ResearchSource
        from app.source_registry import SourceRegistry

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        source = ResearchSource(**SOURCE_KW)
        self.provider = ResearchDraftProvider()
        self.registry = SourceRegistry(Path(self.tmp.name) / "sources.db")
        self.agent = DocumentAgent(
            self.provider, research=ResearchManager(source), registry=self.registry,
            preference_store=DocumentPreferenceStore(Path(self.tmp.name) / "prefs.db"),
            source_scope="order-status-test",
        )
        self.agent.brief.apply_ai_values({
            "institution_level": "SMK", "class_semester": "XII Semester 1",
            "subject": "Informatika", "topic_title": "AI Agent", "target_length": "8 halaman",
            "focus": "AI Agent untuk pembelajaran",
        })
        self.agent.cover.assignment_type = "individu"
        self.agent.cover.author_name = "Siswa Uji"
        self.agent._outline_text = "## Kerangka Makalah\nBAB I\nBAB II\nBAB III\nDAFTAR PUSTAKA"
        self.agent.phase = "ready_for_draft"

    def test_on_status_receives_research_then_draft_stage_messages_in_order(self):
        seen: list[str] = []
        result = self.agent.handle("lanjutkan", on_status=seen.append)
        self.assertEqual(result.status, "draft_ready")
        self.assertEqual(seen, [
            "🔍 Nara sedang mencari sumber referensi...",
            "📝 Nara sedang menulis draft...",
        ])


class FakeCitationEngine:
    def build(self, spec, sources, *, create_pdf=True, citation_repeat_mode="auto"):
        return SimpleNamespace(status="berhasil", docx_path="uji.docx", pdf_path="uji.pdf",
                                used_refs=("R1",), warning="")


class DocumentAgentBuildFinalStatusTests(unittest.TestCase):
    def test_on_status_receives_build_file_stage_message(self):
        from app.document_preferences import DocumentPreferenceStore

        with tempfile.TemporaryDirectory() as tmp:
            store = DocumentPreferenceStore(Path(tmp) / "prefs.db")
            agent = DocumentAgent(
                OutlineProvider(), engine=object(), research=object(),
                registry=SimpleNamespace(list_sources=lambda scope: [object()]),
                preference_store=store,
            )
            agent.citation_engine = FakeCitationEngine()
            agent.phase = "draft_ready"
            agent._draft_spec = object()
            seen: list[str] = []
            agent._on_status = seen.append  # build_final() dipanggil langsung, bukan via handle().
            result = agent.build_final()
            self.assertEqual(result.status, "final_ready")
            self.assertIn("📄 Nara sedang membuat file Word/PDF...", seen)


# ---------------------------------------------------------------------------
# FinanceService (Laras) — hanya jalur pertanyaan bebas yang melapor status.
# ---------------------------------------------------------------------------

class FinanceQueryProvider:
    def __init__(self, reply: ModelReply):
        self._reply = reply
        self.calls = []

    @property
    def configured(self):
        return True

    @property
    def provider_name(self):
        return "Fake"

    @property
    def model_name(self):
        return "fake-model"

    def generate(self, messages, *, max_tokens=300, temperature=0.0, timeout=20):
        self.calls.append(messages)
        return self._reply


class FinanceStatusReportingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "finance.db"

    def test_on_status_is_called_for_free_form_report_question(self):
        provider = FinanceQueryProvider(ModelReply(
            "berhasil",
            '{"report_type": "ringkasan", "period": "bulan_ini", "business": null, '
            '"account": null, "kind": null, "evidence": "pemasukan bulan ini"}',
            "Fake", "fake-model", 10, 5,
        ))
        finance = FinanceService(self.db, query_interpreter=FinanceQueryInterpreter(provider))
        seen: list[str] = []
        result = finance.handle("pemasukan bulan ini berapa ya?", on_status=seen.append)
        self.assertEqual(result.status, "berhasil")
        self.assertEqual(seen, ["🔎 Laras sedang menganalisis pertanyaan Anda..."])

    def test_on_status_is_not_called_for_deterministic_transaction_recording(self):
        provider = FinanceQueryProvider(ModelReply("gagal", "harus tidak pernah dipanggil", "Fake", "fake-model", 0, 0))
        finance = FinanceService(self.db, query_interpreter=FinanceQueryInterpreter(provider))
        seen: list[str] = []
        result = finance.handle(
            "Catat pemasukan 100 ribu jasa print untuk Taqi Desk pakai Cash",
            on_status=seen.append,
        )
        self.assertEqual(result.status, "berhasil")
        self.assertEqual(seen, [])

    def test_on_status_is_not_called_for_fixed_slash_commands(self):
        finance = FinanceService(self.db)
        seen: list[str] = []
        finance.handle("/saldo", on_status=seen.append)
        self.assertEqual(seen, [])

    def test_a_raising_on_status_callback_never_breaks_the_finance_answer(self):
        provider = FinanceQueryProvider(ModelReply(
            "berhasil",
            '{"report_type": "ringkasan", "period": "bulan_ini", "business": null, '
            '"account": null, "kind": null, "evidence": "pemasukan bulan ini"}',
            "Fake", "fake-model", 10, 5,
        ))
        finance = FinanceService(self.db, query_interpreter=FinanceQueryInterpreter(provider))

        def boom(text):
            raise RuntimeError("pelapor status rusak")

        result = finance.handle("pemasukan bulan ini berapa ya?", on_status=boom)
        self.assertEqual(result.status, "berhasil")


# ---------------------------------------------------------------------------
# ContentStudio (Kirana) — satu pesan status sebelum draft caption dibuat.
# ---------------------------------------------------------------------------

class ContentStudioStatusReportingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        brand_root = root / "brand_profiles"
        brand_root.mkdir()
        (brand_root / "risol_mamqi.md").write_text("""## Usaha
Risol Mamqi

## Deskripsi Singkat
Usaha kuliner rumahan.

## Tone of Voice
Ceria dan menggugah selera.

## Target Audiens
Warga sekitar.

## Larangan Tema/Kata
- Tidak mengklaim manfaat kesehatan.

## Contoh Caption Favorit
- Risol anget nih!
""", encoding="utf-8")
        self.brand_profiles = BrandProfileStore(brand_root)

    def test_on_status_is_called_once_before_caption_generation(self):
        class Provider:
            configured = True
            provider_name = "Fake"
            model_name = "fake-model"

            def generate(self, messages, *, max_tokens=1200, temperature=0.7, timeout=45):
                return ModelReply("berhasil", json.dumps({"captions": ["Caption 1"]}), "Fake", "fake-model", 10, 5)

        studio = ContentStudio(Provider(), brand_profiles=self.brand_profiles)
        seen: list[str] = []
        result = studio.generate_draft("Risol Mamqi", "instagram", "promo weekend", on_status=seen.append)
        self.assertEqual(result.status, "draft")
        self.assertEqual(seen, ["🎨 Kirana sedang menyusun draft caption..."])

    def test_omitting_on_status_still_works(self):
        class Provider:
            configured = True
            provider_name = "Fake"
            model_name = "fake-model"

            def generate(self, messages, *, max_tokens=1200, temperature=0.7, timeout=45):
                return ModelReply("berhasil", json.dumps({"captions": ["Caption 1"]}), "Fake", "fake-model", 10, 5)

        studio = ContentStudio(Provider(), brand_profiles=self.brand_profiles)
        result = studio.generate_draft("Risol Mamqi", "instagram", "promo weekend")
        self.assertEqual(result.status, "draft")


if __name__ == "__main__":
    unittest.main()
