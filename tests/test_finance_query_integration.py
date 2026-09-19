"""Integrasi jalur pertanyaan keuangan bebas AI-first: `FinanceService.handle()` dan
`LeadAgent.handle_admin_message()` bersama `FinanceQueryInterpreter`. Unit test murni
klasifikasi AI ada di `tests/test_finance_query.py`; file ini fokus ke dispatch, fallback
deterministik, dan disambiguasi pencatatan-vs-pertanyaan."""

import tempfile
import unittest
from pathlib import Path

from app.finance import FinanceService
from app.finance_query import FinanceQueryInterpreter
from app.lead import LeadAgent
from app.providers.base import ModelReply


class FakeProvider:
    def __init__(self, reply: ModelReply, *, configured: bool = True):
        self._reply = reply
        self._configured = configured
        self.calls: list[list[dict[str, str]]] = []

    @property
    def configured(self) -> bool:
        return self._configured

    @property
    def provider_name(self) -> str:
        return "Fake"

    @property
    def model_name(self) -> str:
        return "fake-model"

    def generate(self, messages, *, max_tokens=300, temperature=0.0, timeout=20):
        self.calls.append(messages)
        return self._reply


def _reply(payload_json: str, *, status: str = "berhasil") -> ModelReply:
    return ModelReply(status, payload_json, "Fake", "fake-model", 10, 5)


class FinanceServiceFreeFormQueryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "finance.db"

    def _service(self, reply: ModelReply, *, configured: bool = True) -> tuple[FinanceService, FakeProvider]:
        provider = FakeProvider(reply, configured=configured)
        interpreter = FinanceQueryInterpreter(provider)
        return FinanceService(self.db, query_interpreter=interpreter), provider

    def test_free_form_ringkasan_question_answers_from_real_data(self):
        finance, provider = self._service(_reply(
            '{"report_type": "ringkasan", "period": "bulan_ini", "business": null, '
            '"account": null, "kind": "income", "evidence": "pemasukan bulan ini"}'
        ))
        finance.record(
            kind="income", amount=250000, account="Cash", business="Taqi Desk",
            category="Jasa", description="jasa print",
        )
        result = finance.handle("pemasukan bulan ini berapa ya?")
        self.assertEqual(result.status, "berhasil")
        self.assertIn("Rp250.000", result.text)
        self.assertEqual(len(provider.calls), 1)

    def test_free_form_saldo_question_for_specific_account(self):
        finance, _ = self._service(_reply(
            '{"report_type": "saldo", "period": "bulan_ini", "business": null, '
            '"account": "BCA", "kind": null, "evidence": "saldo BCA"}'
        ))
        finance.set_opening_balance("BCA", 500000)
        result = finance.handle("saldo BCA sekarang berapa?")
        self.assertEqual(result.status, "berhasil")
        self.assertIn("Rp500.000", result.text)

    def test_free_form_laba_rugi_question(self):
        finance, _ = self._service(_reply(
            '{"report_type": "laba_rugi", "period": "bulan_ini", "business": null, '
            '"account": null, "kind": null, "evidence": "untung berapa"}'
        ))
        finance.record(
            kind="income", amount=1000000, account="Cash", business="Taqi Desk",
            category="Jasa", description="jasa print",
        )
        finance.record(
            kind="expense", amount=300000, account="Cash", business="Taqi Desk",
            category="Tinta", description="beli tinta",
        )
        result = finance.handle("bulan ini untung berapa?")
        self.assertEqual(result.status, "berhasil")
        self.assertIn("Laba bersih: Rp700.000", result.text)

    def test_unrecognized_business_from_ai_is_rejected_with_helpful_message(self):
        finance, _ = self._service(_reply(
            '{"report_type": "ringkasan", "period": "bulan_ini", "business": "Usaha Fiktif", '
            '"account": null, "kind": null, "evidence": "Usaha Fiktif"}'
        ))
        result = finance.handle("pemasukan Usaha Fiktif bulan ini berapa?")
        self.assertEqual(result.status, "needs_review")
        self.assertIn("tidak dikenali", result.text)
        self.assertIn("Taqi Desk", result.text)

    def test_unsupported_report_type_gives_helpful_fallback_message(self):
        finance, _ = self._service(_reply(
            '{"report_type": "tidak_didukung", "period": "bulan_ini", "business": null, '
            '"account": null, "kind": null, "evidence": "piutang"}'
        ))
        result = finance.handle("piutang saya sama pelanggan berapa total?")
        self.assertEqual(result.status, "membutuhkan_bantuan")
        self.assertIn("belum bisa", result.text)

    def test_recording_instruction_with_amount_never_reaches_ai_query_path(self):
        """Disambiguasi inti: pesan yang punya kind + nominal SELALU dianggap instruksi
        pencatatan, bukan pertanyaan — walaupun AI-nya (kalau dipanggil) akan salah
        mengklasifikasikan sebagai laporan. Provider di sini akan error kalau sampai
        dipanggil (reply "gagal" dipaksa), supaya test ini gagal kalau kode ternyata
        salah memanggil AI untuk instruksi pencatatan."""
        finance, provider = self._service(_reply("harus tidak pernah dipanggil", status="gagal"))
        result = finance.handle(
            "Catat pemasukan 100 ribu jasa print untuk Taqi Desk pakai Cash"
        )
        self.assertEqual(result.status, "berhasil")
        self.assertTrue(result.text.startswith("Pemasukan tercatat."))
        self.assertEqual(provider.calls, [])

    def test_ai_classifying_recording_message_as_tidak_relevan_falls_through_to_recording(self):
        finance, _ = self._service(_reply(
            '{"report_type": "tidak_relevan", "period": "bulan_ini", "business": null, '
            '"account": null, "kind": null, "evidence": "Catat pengeluaran"}'
        ))
        # Pesan ini TIDAK punya nominal yang bisa diparse otomatis dalam bentuk umum,
        # jadi tetap lolos ke AI dulu; AI menjawab tidak_relevan -> harus jatuh ke jalur
        # deterministik lama (needs_review minta kelengkapan), bukan macet/error.
        result = finance.handle("Catat pengeluaran beli tinta untuk Taqi Desk")
        self.assertEqual(result.status, "needs_review")

    def test_unconfigured_query_interpreter_falls_back_to_old_needs_review_flow(self):
        finance = FinanceService(self.db)  # query_interpreter=None, perilaku lama persis.
        # Tanpa AI, "pemasukan" terdeteksi sebagai instruksi pencatatan (kind="income")
        # yang nominalnya belum lengkap -> needs_review, PERSIS perilaku lama sebelum
        # fitur pertanyaan bebas ada (lihat tests/test_finance.py) — bukti fallback
        # tidak mengubah perilaku ketika AI belum dikonfigurasi.
        result = finance.handle("pemasukan bulan lalu berapa?")
        self.assertEqual(result.status, "needs_review")
        self.assertIn("nominal", result.text)

    def test_ai_failure_falls_back_to_deterministic_path_without_crashing(self):
        finance, _ = self._service(_reply("bukan json", status="berhasil"))
        result = finance.handle("pemasukan bulan lalu berapa?")
        # AI gagal parse -> None -> jatuh ke fallback lama (kind terdeteksi "income" tapi
        # tanpa nominal/akun/usaha -> needs_review, bukan crash).
        self.assertEqual(result.status, "needs_review")

    def test_period_bounds_resolves_bulan_lalu_correctly(self):
        finance = FinanceService(self.db)
        from datetime import datetime
        start, end = finance._period_bounds("bulan_lalu")
        this_month_start, _ = finance._month_bounds(datetime.now())
        self.assertEqual(end, this_month_start)
        self.assertLess(start, end)

    def test_period_bounds_rejects_unknown_period(self):
        finance = FinanceService(self.db)
        with self.assertRaises(ValueError):
            finance._period_bounds("tahun_ini")


class LeadAgentFreeFormFinanceQueryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "finance.db"

    def test_free_form_question_routes_through_lead_agent_to_finance(self):
        provider = FakeProvider(_reply(
            '{"report_type": "ringkasan", "period": "bulan_ini", "business": null, '
            '"account": null, "kind": null, "evidence": "pemasukan bulan ini"}'
        ))
        finance = FinanceService(self.db, query_interpreter=FinanceQueryInterpreter(provider))
        lead = LeadAgent(finance=finance)
        reply = lead.handle_admin_message("pemasukan bulan ini berapa sih?")
        self.assertEqual(reply.target, "finance")
        self.assertEqual(reply.status, "berhasil")

    def test_fixed_slash_commands_never_call_ai_query_interpreter(self):
        provider = FakeProvider(_reply("harus tidak pernah dipanggil", status="gagal"))
        finance = FinanceService(self.db, query_interpreter=FinanceQueryInterpreter(provider))
        lead = LeadAgent(finance=finance)
        reply = lead.handle_admin_message("/bulan_ini")
        self.assertEqual(reply.status, "berhasil")
        self.assertEqual(provider.calls, [])


if __name__ == "__main__":
    unittest.main()
