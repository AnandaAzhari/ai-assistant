"""Alur proteksi pembayaran (watermark pratinjau -> /lunas admin -> rilis otomatis
saat pelanggan kirim pesan berikutnya) — lihat app/payment_gate.py dan
app/pdf_watermark.py untuk desain lengkapnya. Memakai stub PdfWatermarker (bukan
reportlab/pypdf sungguhan; sudah diuji terpisah di tests/test_pdf_watermark.py)
supaya test ini fokus ke ORKESTRASI di app/lead.py."""

import tempfile
import unittest
from pathlib import Path

from app.approval_gate import ApprovalGate
from app.document_agent import DocumentResult
from app.lead import LeadAgent
from app.payment_gate import PaymentGateStore
from app.pdf_watermark import WatermarkResult
from app.trust_layer import TrustLayer


class FakeCustomerDocumentAgent:
    """Sama seperti FakeCustomerDocumentAgent di tests/test_customer_channel.py —
    diduplikasi sesuai konvensi yang sudah dipakai di beberapa file test lain."""

    def __init__(self, *, session_active: bool = False, responses=None, final_docx_path: str = "",
                 final_pdf_path: str = ""):
        self.session_active = session_active
        self._responses = list(responses or [])
        self.final_docx_path = final_docx_path
        self.final_pdf_path = final_pdf_path
        self.calls: list[str] = []

    def handle(self, raw: str) -> DocumentResult:
        self.calls.append(raw)
        if self._responses:
            return self._responses.pop(0)
        return DocumentResult("needs_requirements", "Boleh diceritakan jenjang dan topiknya?")


class _FakeWatermarker:
    """Stub deterministik — tidak menyentuh reportlab/pypdf sama sekali."""

    def __init__(self, *, available=True, status="berhasil", output_path="/fake/preview.pdf", warning=""):
        self.calls: list[tuple[str, str]] = []
        self._available = available
        self._status = status
        self._output_path = output_path
        self._warning = warning

    @property
    def available(self) -> bool:
        return self._available

    @property
    def status_text(self) -> str:
        return "siap (stub)" if self._available else "belum terpasang (stub)"

    def add_preview_watermark(self, source_path, *, text=None, order_id=""):
        self.calls.append((str(source_path), order_id))
        return WatermarkResult(self._status, self._output_path, self._warning)


class PaymentFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "assistant.db"
        self.trust_layer = TrustLayer(self.db)
        self.approval_gate = ApprovalGate(self.db)
        self.payment_gate = PaymentGateStore(self.db)
        self.watermarker = _FakeWatermarker()

        pdf_path = Path(self.temp.name) / "makalah-628aaa.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 palsu")
        self.pdf_path = str(pdf_path)

    def _lead(self, *, payment_gate=None, pdf_watermarker=None) -> LeadAgent:
        return LeadAgent(
            trust_layer=self.trust_layer, approval_gate=self.approval_gate,
            payment_gate=payment_gate, pdf_watermarker=pdf_watermarker,
        )

    def _logged_action_types(self, requested_by: str) -> list[str]:
        with self.approval_gate.connect() as db:
            rows = db.execute(
                "SELECT action_type FROM approval_requests WHERE requested_by = ?",
                (requested_by,),
            ).fetchall()
        return [row["action_type"] for row in rows]

    def test_final_ready_sends_only_watermarked_preview_when_gate_active(self):
        fake_document = FakeCustomerDocumentAgent(
            session_active=True,
            responses=[DocumentResult("final_ready", "File makalah sudah tersedia.")],
            final_docx_path="/tmp/makalah-628aaa.docx",
            final_pdf_path=self.pdf_path,
        )
        lead = self._lead(payment_gate=self.payment_gate, pdf_watermarker=self.watermarker)
        lead.document_factory = lambda sender_id: fake_document

        reply = lead.handle_customer_message("628aaa", "Baik kak, makalahnya lanjutkan saja sampai selesai ya")

        self.assertEqual(reply.status, "final_ready")
        # HANYA PDF pratinjau ber-watermark yang dikirim, DOCX-nya tidak.
        self.assertEqual(reply.attachment_paths, ("/fake/preview.pdf",))
        self.assertIn("pratinjau", reply.text)
        self.assertIn("watermark", reply.text.casefold())
        self.assertIn("unggah_preview_watermark_ke_pelanggan", self._logged_action_types("customer:628aaa"))

        # DOCX + PDF bersih tersimpan sebagai pending, BELUM lunas.
        pending = self.payment_gate.get_pending("628aaa")
        self.assertIsNotNone(pending)
        self.assertEqual(pending.docx_path, "/tmp/makalah-628aaa.docx")
        self.assertEqual(pending.pdf_path, self.pdf_path)
        self.assertEqual(pending.paid_at, "")

    def test_payment_info_included_in_preview_message_when_set(self):
        self.payment_gate.set_payment_info(
            "Transfer BCA 1234567890 a.n. Ananda Azhari", updated_by="admin:telegram",
        )
        fake_document = FakeCustomerDocumentAgent(
            session_active=True,
            responses=[DocumentResult("final_ready", "File makalah sudah tersedia.")],
            final_docx_path="/tmp/makalah-628bbb.docx",
            final_pdf_path=self.pdf_path,
        )
        lead = self._lead(payment_gate=self.payment_gate, pdf_watermarker=self.watermarker)
        lead.document_factory = lambda sender_id: fake_document

        reply = lead.handle_customer_message("628bbb", "Baik kak, makalahnya lanjutkan saja sampai selesai ya")
        self.assertIn("Transfer BCA 1234567890 a.n. Ananda Azhari", reply.text)

    def test_watermark_failure_sends_nothing_and_does_not_save_pending(self):
        failing_watermarker = _FakeWatermarker(status="gagal", warning="reportlab error")
        fake_document = FakeCustomerDocumentAgent(
            session_active=True,
            responses=[DocumentResult("final_ready", "File makalah sudah tersedia.")],
            final_docx_path="/tmp/makalah-628ccc.docx",
            final_pdf_path=self.pdf_path,
        )
        lead = self._lead(payment_gate=self.payment_gate, pdf_watermarker=failing_watermarker)
        lead.document_factory = lambda sender_id: fake_document

        reply = lead.handle_customer_message("628ccc", "Baik kak, makalahnya lanjutkan saja sampai selesai ya")
        self.assertEqual(reply.status, "kendala_watermark")
        self.assertEqual(reply.attachment_paths, ())
        self.assertIsNone(self.payment_gate.get_pending("628ccc"))

    def test_gate_active_but_watermarker_unavailable_sends_nothing(self):
        """Bug yang sempat ditemukan saat implementasi: payment_gate diisi TAPI
        pdf_watermarker.available False TIDAK BOLEH jatuh diam-diam ke pengiriman
        file mentah tanpa proteksi (lihat docstring _continue_customer_document)."""
        unavailable_watermarker = _FakeWatermarker(available=False)
        fake_document = FakeCustomerDocumentAgent(
            session_active=True,
            responses=[DocumentResult("final_ready", "File makalah sudah tersedia.")],
            final_docx_path="/tmp/makalah-628ddd.docx",
            final_pdf_path=self.pdf_path,
        )
        lead = self._lead(payment_gate=self.payment_gate, pdf_watermarker=unavailable_watermarker)
        lead.document_factory = lambda sender_id: fake_document

        reply = lead.handle_customer_message("628ddd", "Baik kak, makalahnya lanjutkan saja sampai selesai ya")
        self.assertEqual(reply.status, "kendala_watermark")
        self.assertEqual(reply.attachment_paths, ())
        self.assertEqual(unavailable_watermarker.calls, [])  # tidak sempat dipanggil sama sekali
        self.assertIsNone(self.payment_gate.get_pending("628ddd"))

    def test_gate_active_but_pdf_not_created_sends_nothing(self):
        fake_document = FakeCustomerDocumentAgent(
            session_active=True,
            responses=[DocumentResult("final_ready", "File makalah sudah tersedia.")],
            final_docx_path="/tmp/makalah-628eee.docx",
            final_pdf_path="",  # LibreOffice/Word tidak tersedia di server ini
        )
        lead = self._lead(payment_gate=self.payment_gate, pdf_watermarker=self.watermarker)
        lead.document_factory = lambda sender_id: fake_document

        reply = lead.handle_customer_message("628eee", "Baik kak, makalahnya lanjutkan saja sampai selesai ya")
        self.assertEqual(reply.status, "kendala_watermark")
        self.assertEqual(reply.attachment_paths, ())

    def test_without_payment_gate_falls_back_to_old_behavior(self):
        """payment_gate=None (default, belum diaktifkan runtime ini) -> DOCX+PDF
        tetap dikirim langsung seperti sebelum fitur ini ada, tanpa regresi."""
        fake_document = FakeCustomerDocumentAgent(
            session_active=True,
            responses=[DocumentResult("final_ready", "File makalah sudah tersedia.")],
            final_docx_path="/tmp/makalah-628fff.docx",
            final_pdf_path=self.pdf_path,
        )
        lead = self._lead(payment_gate=None, pdf_watermarker=self.watermarker)
        lead.document_factory = lambda sender_id: fake_document

        reply = lead.handle_customer_message("628fff", "Baik kak, makalahnya lanjutkan saja sampai selesai ya")
        self.assertEqual(reply.attachment_paths, ("/tmp/makalah-628fff.docx", self.pdf_path))
        self.assertEqual(self.watermarker.calls, [])  # watermark tidak pernah dipanggil

    def test_admin_lunas_then_next_customer_message_delivers_clean_files(self):
        fake_document = FakeCustomerDocumentAgent(
            session_active=True,
            responses=[DocumentResult("final_ready", "File makalah sudah tersedia.")],
            final_docx_path="/tmp/makalah-628ggg.docx",
            final_pdf_path=self.pdf_path,
        )
        lead = self._lead(payment_gate=self.payment_gate, pdf_watermarker=self.watermarker)
        lead.document_factory = lambda sender_id: fake_document
        lead.handle_customer_message("628ggg", "Baik kak, makalahnya lanjutkan saja sampai selesai ya")

        # Sebelum admin /lunas -> pesan berikutnya diproses biasa, TIDAK dikirimi apa pun.
        before = lead.handle_customer_message("628ggg", "kapan ya biasanya selesai")
        self.assertEqual(before.attachment_paths, ())

        admin_reply = lead.handle_admin_message("/lunas 628ggg")
        self.assertEqual(admin_reply.status, "berhasil")
        self.assertIn("LUNAS", admin_reply.text)

        after = lead.handle_customer_message("628ggg", "sudah saya bayar ya kak")
        self.assertEqual(after.target, "payment_gate")
        self.assertEqual(after.attachment_paths, ("/tmp/makalah-628ggg.docx", self.pdf_path))
        self.assertIn("kirim_dokumen_setelah_lunas", self._logged_action_types("customer:628ggg"))

        # Sekali dikirim, tidak dikirim ulang untuk pesan berikutnya lagi.
        again = lead.handle_customer_message("628ggg", "makasih min")
        self.assertEqual(again.attachment_paths, ())

    def test_admin_lunas_without_pending_order_reports_not_found(self):
        lead = self._lead(payment_gate=self.payment_gate, pdf_watermarker=self.watermarker)
        reply = lead.handle_admin_message("/lunas 628unknown")
        self.assertEqual(reply.status, "tidak_ditemukan")

    def test_admin_lunas_without_payment_gate_configured(self):
        lead = self._lead(payment_gate=None, pdf_watermarker=self.watermarker)
        reply = lead.handle_admin_message("/lunas 628aaa")
        self.assertEqual(reply.status, "belum_dikonfigurasi")

    def test_admin_set_pembayaran_then_cek_pembayaran(self):
        lead = self._lead(payment_gate=self.payment_gate, pdf_watermarker=self.watermarker)
        set_reply = lead.handle_admin_message("/set_pembayaran Scan QR GoPay di 08111222333")
        self.assertEqual(set_reply.status, "berhasil")

        cek_reply = lead.handle_admin_message("/cek_pembayaran")
        self.assertIn("Scan QR GoPay di 08111222333", cek_reply.text)

    def test_admin_set_pembayaran_rejects_empty_text(self):
        lead = self._lead(payment_gate=self.payment_gate, pdf_watermarker=self.watermarker)
        reply = lead.handle_admin_message("/set_pembayaran")
        self.assertEqual(reply.status, "format_salah")

    def test_admin_cek_pembayaran_without_info_set_yet(self):
        lead = self._lead(payment_gate=self.payment_gate, pdf_watermarker=self.watermarker)
        reply = lead.handle_admin_message("/cek_pembayaran")
        self.assertIn("BELUM diisi", reply.text)


if __name__ == "__main__":
    unittest.main()
