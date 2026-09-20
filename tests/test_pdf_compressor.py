import shutil
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest

from app.pdf_compressor import PdfCompressor

_GHOSTSCRIPT_AVAILABLE = (
    shutil.which("gs") is not None or shutil.which("gswin64c") is not None or shutil.which("gswin32c") is not None
)

# numpy/Pillow/reportlab HANYA dipakai di sini untuk membuat PDF uji beresolusi
# tinggi (lihat _make_test_pdf) — bukan dependency app/pdf_compressor.py itu sendiri.
# Kalau belum terpasang di lingkungan tempat test dijalankan (mis. VPS produksi yang
# tidak butuh dev-dependencies), test yang butuh Ghostscript sungguhan di bawah ini
# di-skip dengan pesan jelas, bukan bikin seluruh file test gagal collect.
try:
    import numpy as np
    from PIL import Image
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
    _PDF_TEST_LIBS_AVAILABLE = True
except ImportError:
    _PDF_TEST_LIBS_AVAILABLE = False

_REAL_COMPRESSION_TESTABLE = _GHOSTSCRIPT_AVAILABLE and _PDF_TEST_LIBS_AVAILABLE


def _make_test_pdf(path: Path, *, pixels: int = 1600, seed: int = 42) -> None:
    """Buat PDF satu halaman berisi gambar noise beresolusi tinggi ditempatkan di
    area kecil (3x3 inci) — jauh melebihi resolusi cetak wajar, supaya preset
    `-dPDFSETTINGS` Ghostscript yang men-downsample resolusi gambar (mis. /screen ke
    ~72dpi) benar-benar memangkas ukuran file secara signifikan. PDF teks murni
    nyaris tidak berubah oleh preset ini, jadi tidak cocok untuk menguji kompresi
    sungguhan."""
    rng = np.random.default_rng(seed)
    array = rng.integers(0, 256, size=(pixels, pixels, 3), dtype=np.uint8)
    image = Image.fromarray(array, mode="RGB")
    canvas_obj = canvas.Canvas(str(path), pagesize=(4 * 72, 4 * 72))
    canvas_obj.drawImage(ImageReader(image), 50, 50, width=3 * 72, height=3 * 72)
    canvas_obj.save()


class PdfCompressorValidationTests(unittest.TestCase):
    """Validasi input yang tidak butuh Ghostscript sungguhan sama sekali."""

    def setUp(self):
        import tempfile
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.compressor = PdfCompressor(self.root / "hasil")

    def test_rejects_missing_source_file(self):
        result = self.compressor.compress_to_target(self.root / "tidak-ada.pdf", 500 * 1024)
        self.assertEqual(result.status, "gagal")
        self.assertIn("tidak ditemukan", result.warning)

    def test_rejects_non_pdf_file(self):
        bukan_pdf = self.root / "catatan.txt"
        bukan_pdf.write_text("halo")
        result = self.compressor.compress_to_target(bukan_pdf, 500 * 1024)
        self.assertEqual(result.status, "gagal")
        self.assertIn("bukan PDF", result.warning)

    def test_rejects_non_positive_target(self):
        pdf = self.root / "dummy.pdf"
        pdf.write_bytes(b"%PDF-1.4\n%%EOF")
        result = self.compressor.compress_to_target(pdf, 0)
        self.assertEqual(result.status, "gagal")
        self.assertIn("lebih dari 0", result.warning)

    def test_returns_source_unchanged_when_already_under_target(self):
        pdf = self.root / "kecil.pdf"
        pdf.write_bytes(b"%PDF-1.4\n%%EOF")
        result = self.compressor.compress_to_target(pdf, 10 * 1024 * 1024)
        self.assertEqual(result.status, "berhasil")
        self.assertTrue(result.achieved)
        self.assertEqual(result.output_path, str(pdf))
        self.assertEqual(result.compressed_size_bytes, result.original_size_bytes)

    def test_reports_clear_message_when_ghostscript_missing(self):
        pdf = self.root / "besar.pdf"
        pdf.write_bytes(b"%PDF-1.4\n" + b"0" * (2 * 1024 * 1024) + b"\n%%EOF")
        with patch("app.pdf_compressor.shutil.which", return_value=None):
            result = self.compressor.compress_to_target(pdf, 500 * 1024)
        self.assertEqual(result.status, "gagal")
        self.assertIn("Ghostscript", result.warning)
        self.assertIn("install", result.warning.casefold())

    def test_available_property_reflects_ghostscript_presence(self):
        with patch("app.pdf_compressor.shutil.which", return_value=None):
            self.assertFalse(self.compressor.available)
            self.assertIn("Ghostscript", self.compressor.status_text)


@pytest.mark.skipif(
    not _REAL_COMPRESSION_TESTABLE,
    reason="Ghostscript dan/atau numpy+Pillow+reportlab (khusus pembuat PDF uji) tidak tersedia di lingkungan ini",
)
class PdfCompressorRealGhostscriptTests(unittest.TestCase):
    """Kompresi sungguhan lewat Ghostscript — bukan cuma review kode, lihat pola yang
    sama di tests/test_document_engine.py untuk LibreOffice."""

    def setUp(self):
        import tempfile
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.compressor = PdfCompressor(self.root / "hasil")
        self.source = self.root / "besar.pdf"
        _make_test_pdf(self.source, pixels=1600)
        self.assertTrue(self.source.stat().st_size > 0)

    def test_reduces_pdf_and_reports_achieved_when_target_is_reachable(self):
        original_size = self.source.stat().st_size

        # Baseline: target yang mustahil tercapai preset apa pun -> ukuran terkecil
        # yang benar-benar bisa dicapai Ghostscript untuk PDF uji ini (menghindari
        # angka target "ajaib" yang bisa flaky tergantung versi Ghostscript).
        floor_result = self.compressor.compress_to_target(self.source, 1, order_id="FLOOR")
        self.assertEqual(floor_result.status, "berhasil")
        self.assertFalse(floor_result.achieved)
        self.assertLess(floor_result.compressed_size_bytes, original_size)

        target = floor_result.compressed_size_bytes + 20_000
        result = self.compressor.compress_to_target(self.source, target, order_id="ACHIEVABLE")
        self.assertEqual(result.status, "berhasil")
        self.assertTrue(result.achieved)
        self.assertLessEqual(result.compressed_size_bytes, target)
        output = Path(result.output_path)
        self.assertTrue(output.is_file())
        self.assertTrue(output.read_bytes().startswith(b"%PDF"))

    def test_reports_best_effort_honestly_when_target_unreachable(self):
        result = self.compressor.compress_to_target(self.source, 200, order_id="UNREACHABLE")
        self.assertEqual(result.status, "berhasil")
        self.assertFalse(result.achieved)
        self.assertIn("Target", result.warning)
        self.assertIn("belum tercapai", result.warning)
        output = Path(result.output_path)
        self.assertTrue(output.is_file())
        self.assertLess(result.compressed_size_bytes, result.original_size_bytes)

    def test_concurrent_compressions_do_not_crash(self):
        """Simulasi beberapa pelanggan WhatsApp minta kompresi nyaris bersamaan
        (whatsapp_main.py memakai ThreadingHTTPServer) — file scratch per percobaan
        preset harus terisolasi antar-thread."""
        results: dict[int, object] = {}
        errors: dict[int, Exception] = {}

        def worker(i: int) -> None:
            try:
                results[i] = self.compressor.compress_to_target(self.source, 60_000, order_id=f"CONC-{i}")
            except Exception as exc:  # pragma: no cover - dilaporkan lewat assert di bawah
                errors[i] = exc

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertFalse(errors, errors)
        self.assertEqual(len(results), 3)
        for result in results.values():
            self.assertEqual(result.status, "berhasil")
            self.assertTrue(Path(result.output_path).is_file())


if __name__ == "__main__":
    unittest.main()
