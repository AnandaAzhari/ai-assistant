"""Alur kompresi PDF di jalur pelanggan (app/lead.py) — memakai stub PdfCompressor
(bukan Ghostscript sungguhan; kompresi sungguhan sudah diuji di
tests/test_pdf_compressor.py) supaya test ini fokus ke ORKESTRASI: kapan file
diteruskan ke PdfCompressor, kapan pelanggan ditanya dulu target ukurannya, dan
kapan pesan lain (bukan PDF/tanpa compressor) tidak pernah masuk alur ini sama
sekali."""

import tempfile
import unittest
from pathlib import Path

from app.approval_gate import ApprovalGate
from app.customer_book import CustomerBookStore
from app.lead import LeadAgent
from app.pdf_compressor import CompressionResult
from app.trust_layer import TrustLayer


class _FakePdfCompressor:
    """Stub deterministik — tidak menyentuh disk/Ghostscript sama sekali."""

    def __init__(self, *, achieved=True, original=500 * 1024, compressed=100 * 1024,
                 status="berhasil", warning="", output_path="/fake/hasil-kompres.pdf"):
        self.calls: list[tuple[str, int, str]] = []
        self._achieved = achieved
        self._original = original
        self._compressed = compressed
        self._status = status
        self._warning = warning
        self._output_path = output_path

    def compress_to_target(self, source_path, target_bytes, *, order_id=""):
        self.calls.append((str(source_path), target_bytes, order_id))
        return CompressionResult(
            self._status, self._output_path, self._original, self._compressed, target_bytes,
            self._achieved, self._warning,
        )


_UNSET = object()


class PdfCompressionFlowTests(unittest.TestCase):
    """Pesan uji sengaja menyertakan kata seperti "tugas"/"print" (salah satu dari
    `TrustLayer._SERVICE_WORDS`) supaya skor trust pasti mendarat di kategori
    LIKELY_CUSTOMER/TRUSTED (decision "proses") — bukan default UNCERTAIN (skor 50)
    yang minta verifikasi dulu. Ini murni supaya test fokus ke orkestrasi kompresi
    PDF di app/lead.py, bukan skenario trust scoring itu sendiri (sudah diuji
    terpisah di tests/test_trust_layer.py)."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "assistant.db"
        self.fake_compressor = _FakePdfCompressor()

    def _lead(self, *, pdf_compressor=_UNSET):
        if pdf_compressor is _UNSET:
            pdf_compressor = self.fake_compressor
        return LeadAgent(
            trust_layer=TrustLayer(self.db), approval_gate=ApprovalGate(self.db),
            customer_book=CustomerBookStore(self.db), pdf_compressor=pdf_compressor,
        )

    def test_pdf_without_target_in_caption_asks_for_size_and_does_not_compress_yet(self):
        lead = self._lead()
        reply = lead.handle_customer_message(
            "628111", "", has_attachment=True, attachment_path="/quarantine/berkas.pdf",
        )
        self.assertEqual(reply.status, "menunggu_target_ukuran")
        self.assertIn("KB", reply.text)
        self.assertEqual(self.fake_compressor.calls, [])

    def test_pdf_with_target_in_same_message_compresses_immediately(self):
        lead = self._lead()
        reply = lead.handle_customer_message(
            "628111", "Tolong kompres jadi 300kb ya", has_attachment=True,
            attachment_path="/quarantine/berkas.pdf",
        )
        self.assertEqual(reply.status, "berhasil")
        self.assertEqual(len(self.fake_compressor.calls), 1)
        source, target_bytes, order_id = self.fake_compressor.calls[0]
        self.assertEqual(source, "/quarantine/berkas.pdf")
        self.assertEqual(target_bytes, 300 * 1024)
        self.assertIn("628111", order_id)
        self.assertEqual(reply.attachment_paths, ("/fake/hasil-kompres.pdf",))
        self.assertIn("500KB", reply.text)
        self.assertIn("100KB", reply.text)

    def test_target_sent_in_next_message_resolves_pending_compression(self):
        lead = self._lead()
        first = lead.handle_customer_message(
            "628111", "", has_attachment=True, attachment_path="/quarantine/berkas.pdf",
        )
        self.assertEqual(first.status, "menunggu_target_ukuran")

        second = lead.handle_customer_message("628111", "500 kb saja ya, ini buat tugas kuliah")
        self.assertEqual(second.status, "berhasil")
        self.assertEqual(len(self.fake_compressor.calls), 1)
        source, target_bytes, _order_id = self.fake_compressor.calls[0]
        self.assertEqual(source, "/quarantine/berkas.pdf")
        self.assertEqual(target_bytes, 500 * 1024)

        # Sesudah terselesaikan, pending state bersih -> pesan angka berikutnya
        # tanpa satuan/PDF baru tidak lagi memicu kompresi ulang (balasan berikutnya
        # boleh saja "berhasil" untuk rute LAIN, tapi target-nya bukan pdf_compressor
        # lagi dan PdfCompressor tidak dipanggil kedua kalinya).
        third = lead.handle_customer_message("628111", "500 untuk tugas lain")
        self.assertEqual(len(self.fake_compressor.calls), 1)
        self.assertNotEqual(third.target, "pdf_compressor")

    def test_bare_number_without_unit_does_not_resolve_pending_target(self):
        lead = self._lead()
        lead.handle_customer_message("628111", "", has_attachment=True, attachment_path="/quarantine/berkas.pdf")
        reply = lead.handle_customer_message("628111", "500 saja untuk tugas ini")  # tanpa "kb"/"mb"
        self.assertEqual(self.fake_compressor.calls, [])
        self.assertNotEqual(reply.target, "pdf_compressor")

    def test_mb_unit_is_converted_correctly(self):
        lead = self._lead()
        lead.handle_customer_message(
            "628111", "kompres jadi 1 mb", has_attachment=True, attachment_path="/quarantine/berkas.pdf",
        )
        _source, target_bytes, _order_id = self.fake_compressor.calls[0]
        self.assertEqual(target_bytes, 1024 * 1024)

    def test_non_pdf_attachment_never_enters_compression_flow(self):
        lead = self._lead()
        reply = lead.handle_customer_message(
            "628111", "kompres jadi 300kb", has_attachment=True, attachment_path="/quarantine/berkas.docx",
        )
        self.assertEqual(self.fake_compressor.calls, [])
        self.assertNotEqual(reply.status, "menunggu_target_ukuran")

    def test_without_pdf_compressor_configured_attachment_falls_through_normally(self):
        lead = self._lead(pdf_compressor=None)
        reply = lead.handle_customer_message(
            "628111", "kompres jadi 300kb", has_attachment=True, attachment_path="/quarantine/berkas.pdf",
        )
        self.assertNotEqual(reply.status, "menunggu_target_ukuran")
        self.assertNotEqual(reply.target, "pdf_compressor")

    def test_compression_failure_reports_warning_text_not_success(self):
        failing_compressor = _FakePdfCompressor(status="gagal", warning="Ghostscript tidak ditemukan.")
        lead = self._lead(pdf_compressor=failing_compressor)
        reply = lead.handle_customer_message(
            "628111", "kompres jadi 300kb", has_attachment=True, attachment_path="/quarantine/berkas.pdf",
        )
        self.assertEqual(reply.status, "gagal")
        self.assertIn("Ghostscript", reply.text)

    def test_target_unreachable_still_reports_success_with_honest_warning(self):
        best_effort_compressor = _FakePdfCompressor(
            achieved=False, original=900 * 1024, compressed=400 * 1024,
            warning="Target 100KB belum tercapai; ukuran terkecil 400KB.",
        )
        lead = self._lead(pdf_compressor=best_effort_compressor)
        reply = lead.handle_customer_message(
            "628111", "kompres jadi 100kb", has_attachment=True, attachment_path="/quarantine/berkas.pdf",
        )
        self.assertEqual(reply.status, "berhasil")
        self.assertIn("400KB", reply.text)
        self.assertIn("belum tercapai", reply.text)

    def test_info_keyword_without_attachment_explains_the_feature(self):
        lead = self._lead()
        reply = lead.handle_customer_message("628111", "bisa kompres pdf tugas saya ga min?")
        self.assertEqual(self.fake_compressor.calls, [])
        self.assertIn("PDF", reply.text)
        self.assertIn("KB", reply.text)


if __name__ == "__main__":
    unittest.main()
