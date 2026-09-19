"""Unit test `app/finance_query.py` (klasifikasi AI-first untuk pertanyaan keuangan
bebas) — terpisah dari test integrasi jalur `FinanceService.handle()` yang ada di
`tests/test_finance_query_integration.py`."""

import unittest

from app.finance_query import ALLOWED_PERIODS, ALLOWED_REPORT_TYPES, FinanceQueryInterpreter
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


def _reply(text: str, *, status: str = "berhasil") -> ModelReply:
    return ModelReply(status, text, "Fake", "fake-model", 10, 5)


class FinanceQueryInterpreterTests(unittest.TestCase):
    def test_unconfigured_provider_returns_not_configured_without_calling_it(self):
        provider = FakeProvider(_reply("{}"), configured=False)
        interpreter = FinanceQueryInterpreter(provider)
        result = interpreter.interpret("pemasukan bulan ini berapa")
        self.assertEqual(result.status, "belum_dikonfigurasi")
        self.assertEqual(provider.calls, [])

    def test_none_provider_is_treated_as_not_configured(self):
        interpreter = FinanceQueryInterpreter(None)
        self.assertFalse(interpreter.configured)
        self.assertEqual(interpreter.interpret("saldo berapa").status, "belum_dikonfigurasi")

    def test_empty_message_fails_without_calling_provider(self):
        provider = FakeProvider(_reply("{}"))
        interpreter = FinanceQueryInterpreter(provider)
        result = interpreter.interpret("   ")
        self.assertEqual(result.status, "gagal")
        self.assertEqual(provider.calls, [])

    def test_valid_ringkasan_classification_succeeds(self):
        raw = "pemasukan bulan lalu berapa Risol Mamqi?"
        provider = FakeProvider(_reply(
            '{"report_type": "ringkasan", "period": "bulan_lalu", "business": "Risol Mamqi", '
            '"account": null, "kind": "income", "evidence": "pemasukan bulan lalu"}'
        ))
        interpreter = FinanceQueryInterpreter(provider)
        result = interpreter.interpret(raw)
        self.assertEqual(result.status, "berhasil")
        self.assertEqual(result.report_type, "ringkasan")
        self.assertEqual(result.period, "bulan_lalu")
        self.assertEqual(result.business, "Risol Mamqi")
        self.assertEqual(result.kind, "income")
        self.assertEqual(result.model, "fake-model")

    def test_unknown_report_type_is_rejected(self):
        provider = FakeProvider(_reply(
            '{"report_type": "prediksi_masa_depan", "period": "bulan_ini", "business": null, '
            '"account": null, "kind": null, "evidence": "berapa"}'
        ))
        interpreter = FinanceQueryInterpreter(provider)
        result = interpreter.interpret("prediksi bulan depan berapa")
        self.assertEqual(result.status, "gagal")

    def test_unknown_period_is_rejected(self):
        provider = FakeProvider(_reply(
            '{"report_type": "ringkasan", "period": "tahun_ini", "business": null, '
            '"account": null, "kind": null, "evidence": "tahun ini"}'
        ))
        interpreter = FinanceQueryInterpreter(provider)
        result = interpreter.interpret("pemasukan tahun ini berapa")
        self.assertEqual(result.status, "gagal")

    def test_evidence_not_found_in_message_is_rejected(self):
        provider = FakeProvider(_reply(
            '{"report_type": "saldo", "period": "bulan_ini", "business": null, '
            '"account": null, "kind": null, "evidence": "kalimat yang tidak ada di pesan asli"}'
        ))
        interpreter = FinanceQueryInterpreter(provider)
        result = interpreter.interpret("saldo BCA berapa sekarang")
        self.assertEqual(result.status, "gagal")

    def test_malformed_json_is_rejected(self):
        provider = FakeProvider(_reply("bukan json sama sekali"))
        interpreter = FinanceQueryInterpreter(provider)
        result = interpreter.interpret("saldo berapa")
        self.assertEqual(result.status, "gagal")

    def test_json_wrapped_in_markdown_fence_is_parsed(self):
        raw = "laba bulan ini berapa?"
        provider = FakeProvider(_reply(
            '```json\n{"report_type": "laba_rugi", "period": "bulan_ini", "business": null, '
            '"account": null, "kind": null, "evidence": "laba bulan ini"}\n```'
        ))
        interpreter = FinanceQueryInterpreter(provider)
        result = interpreter.interpret(raw)
        self.assertEqual(result.status, "berhasil")
        self.assertEqual(result.report_type, "laba_rugi")

    def test_recording_instruction_is_classified_as_tidak_relevan(self):
        raw = "Catat pengeluaran 80 ribu beli tinta untuk Taqi Desk pakai BCA"
        provider = FakeProvider(_reply(
            '{"report_type": "tidak_relevan", "period": "bulan_ini", "business": null, '
            '"account": null, "kind": null, "evidence": "Catat pengeluaran 80 ribu"}'
        ))
        interpreter = FinanceQueryInterpreter(provider)
        result = interpreter.interpret(raw)
        self.assertEqual(result.status, "berhasil")
        self.assertEqual(result.report_type, "tidak_relevan")

    def test_provider_failure_status_is_passed_through(self):
        provider = FakeProvider(_reply("gagal menghubungi API", status="gagal"))
        interpreter = FinanceQueryInterpreter(provider)
        result = interpreter.interpret("saldo berapa")
        self.assertEqual(result.status, "gagal")

    def test_allowed_report_types_and_periods_are_non_empty_tuples(self):
        self.assertIn("ringkasan", ALLOWED_REPORT_TYPES)
        self.assertIn("tidak_relevan", ALLOWED_REPORT_TYPES)
        self.assertIn("bulan_lalu", ALLOWED_PERIODS)


if __name__ == "__main__":
    unittest.main()
