import unittest
from pathlib import Path
from unittest.mock import patch

import pytest

from app.pdf_watermark import DEFAULT_WATERMARK_TEXT, PdfWatermarker

# reportlab/pypdf HANYA dipakai di sini (dan di app/pdf_watermark.py itu sendiri,
# lihat docstringnya) untuk membuat PDF uji dan memverifikasi hasil watermark —
# kalau belum terpasang di lingkungan test, test yang butuh keduanya di-skip dengan
# pesan jelas, bukan bikin seluruh file test gagal collect.
try:
    from pypdf import PdfReader
    from reportlab.pdfgen import canvas as reportlab_canvas

    _PDF_TEST_LIBS_AVAILABLE = True
except ImportError:
    _PDF_TEST_LIBS_AVAILABLE = False


def _make_test_pdf(path: Path, *, pages: int = 2) -> None:
    canvas_obj = reportlab_canvas.Canvas(str(path), pagesize=(595, 842))  # A4 poin
    for i in range(pages):
        canvas_obj.drawString(72, 750, f"Halaman contoh {i + 1}")
        canvas_obj.showPage()
    canvas_obj.save()


class PdfWatermarkValidationTests(unittest.TestCase):
    """Validasi input yang tidak butuh reportlab/pypdf sungguhan sama sekali."""

    def setUp(self):
        import tempfile
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.watermarker = PdfWatermarker(self.root / "hasil")

    def test_rejects_missing_source_file(self):
        result = self.watermarker.add_preview_watermark(self.root / "tidak-ada.pdf")
        self.assertEqual(result.status, "gagal")
        self.assertIn("tidak ditemukan", result.warning)

    def test_rejects_non_pdf_file(self):
        bukan_pdf = self.root / "catatan.txt"
        bukan_pdf.write_text("halo")
        result = self.watermarker.add_preview_watermark(bukan_pdf)
        self.assertEqual(result.status, "gagal")
        self.assertIn("harus PDF", result.warning)

    def test_reports_clear_message_when_libs_missing(self):
        pdf = self.root / "berkas.pdf"
        pdf.write_bytes(b"%PDF-1.4\n%%EOF")
        with patch("app.pdf_watermark._LIBS_AVAILABLE", False):
            result = self.watermarker.add_preview_watermark(pdf)
        self.assertEqual(result.status, "gagal")
        self.assertIn("belum terpasang", result.warning)

    def test_available_property_reflects_libs_presence(self):
        with patch("app.pdf_watermark._LIBS_AVAILABLE", False):
            self.assertFalse(self.watermarker.available)
            self.assertIn("belum terpasang", self.watermarker.status_text)


@pytest.mark.skipif(
    not _PDF_TEST_LIBS_AVAILABLE,
    reason="reportlab dan/atau pypdf tidak tersedia di lingkungan ini",
)
class PdfWatermarkRealTests(unittest.TestCase):
    """Watermark sungguhan lewat reportlab+pypdf — bukan cuma review kode."""

    def setUp(self):
        import tempfile
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.watermarker = PdfWatermarker(self.root / "hasil")
        self.source = self.root / "makalah.pdf"
        _make_test_pdf(self.source, pages=3)
        self.assertTrue(self.source.stat().st_size > 0)

    def test_adds_default_watermark_text_to_every_page(self):
        result = self.watermarker.add_preview_watermark(self.source, order_id="WA-628111")
        self.assertEqual(result.status, "berhasil")
        output = Path(result.output_path)
        self.assertTrue(output.is_file())

        reader = PdfReader(str(output))
        self.assertEqual(len(reader.pages), 3)
        for page in reader.pages:
            text = page.extract_text() or ""
            self.assertIn("BELUM LUNAS", text)

    def test_accepts_custom_watermark_text(self):
        result = self.watermarker.add_preview_watermark(self.source, text="CONTOH KHUSUS TAQI")
        self.assertEqual(result.status, "berhasil")
        reader = PdfReader(result.output_path)
        text = reader.pages[0].extract_text() or ""
        self.assertIn("CONTOH KHUSUS TAQI", text)

    def test_original_file_untouched(self):
        original_bytes = self.source.read_bytes()
        self.watermarker.add_preview_watermark(self.source)
        self.assertEqual(self.source.read_bytes(), original_bytes)

    def test_original_page_content_still_present_under_watermark(self):
        result = self.watermarker.add_preview_watermark(self.source)
        reader = PdfReader(result.output_path)
        text = reader.pages[0].extract_text() or ""
        self.assertIn("Halaman contoh 1", text)

    def test_default_watermark_text_constant_matches_module(self):
        self.assertIn("BELUM LUNAS", DEFAULT_WATERMARK_TEXT)


if __name__ == "__main__":
    unittest.main()
