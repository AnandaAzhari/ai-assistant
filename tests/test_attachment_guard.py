import tempfile
import unittest
from pathlib import Path

from app.attachment_guard import AttachmentGuard, CRITICAL, HIGH, LOW, MEDIUM


class AttachmentGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.quarantine_dir = Path(self.temp.name) / "quarantine"
        self.db = Path(self.temp.name) / "assistant.db"
        self.guard = AttachmentGuard(self.quarantine_dir, self.db)

    def test_ordinary_pdf_is_low_risk_and_allowed(self):
        decision = self.guard.inspect(b"%PDF-1.4 isi dummy", filename="tugas.pdf", sender_id="628111")
        self.assertEqual(decision.risk_level, LOW)
        self.assertTrue(decision.allowed)

    def test_ordinary_docx_is_low_risk_and_allowed(self):
        decision = self.guard.inspect(b"isi dummy", filename="laporan.docx", sender_id="628111")
        self.assertEqual(decision.risk_level, LOW)
        self.assertTrue(decision.allowed)

    def test_executable_extension_is_critical_and_blocked(self):
        decision = self.guard.inspect(b"MZ\x90\x00", filename="invoice.exe", sender_id="628222")
        self.assertEqual(decision.risk_level, CRITICAL)
        self.assertFalse(decision.allowed)

    def test_extension_ending_in_executable_is_critical_even_with_extra_extension(self):
        # "invoice.pdf.exe" -> ekstensi terakhir sungguhan tetap .exe (Windows yang
        # menyembunyikan ekstensi dikenal bisa membuat pelanggan awam mengira ini PDF).
        decision = self.guard.inspect(b"data", filename="invoice.pdf.exe", sender_id="628222")
        self.assertEqual(decision.risk_level, CRITICAL)
        self.assertFalse(decision.allowed)

    def test_double_extension_hiding_executable_before_safe_looking_suffix_is_critical(self):
        # "malware.exe.pdf" -> ekstensi terakhir terlihat aman (.pdf), tapi ada ekstensi
        # berisiko tinggi tersembunyi sebelumnya — pola "ekstensi ganda yang menyamarkan
        # tipe asli" di policies/attachment_link_security.md.
        decision = self.guard.inspect(b"data", filename="malware.exe.pdf", sender_id="628222")
        self.assertEqual(decision.risk_level, CRITICAL)
        self.assertFalse(decision.allowed)
        self.assertIn("ganda", decision.reason.casefold())

    def test_macro_enabled_document_is_high_risk_and_blocked(self):
        decision = self.guard.inspect(b"data", filename="formulir.docm", sender_id="628333")
        self.assertEqual(decision.risk_level, HIGH)
        self.assertFalse(decision.allowed)

    def test_archive_is_high_risk_and_blocked(self):
        decision = self.guard.inspect(b"PK\x03\x04", filename="berkas.zip", sender_id="628444")
        self.assertEqual(decision.risk_level, HIGH)
        self.assertFalse(decision.allowed)

    def test_unknown_extension_is_medium_and_still_allowed(self):
        decision = self.guard.inspect(b"data", filename="catatan.xyz", sender_id="628555")
        self.assertEqual(decision.risk_level, MEDIUM)
        self.assertTrue(decision.allowed)

    def test_empty_file_is_at_least_medium(self):
        decision = self.guard.inspect(b"", filename="kosong.pdf", sender_id="628666")
        self.assertEqual(decision.risk_level, MEDIUM)

    def test_oversized_file_is_at_least_medium(self):
        guard = AttachmentGuard(self.quarantine_dir, self.db, max_size_bytes=10)
        decision = guard.inspect(b"lebih dari sepuluh byte pasti", filename="besar.pdf", sender_id="628777")
        self.assertEqual(decision.risk_level, MEDIUM)

    def test_file_is_always_written_to_quarantine_regardless_of_risk(self):
        decision = self.guard.inspect(b"MZ\x90\x00", filename="invoice.exe", sender_id="628222")
        self.assertTrue(Path(decision.quarantine_path).is_file())
        self.assertTrue(str(Path(decision.quarantine_path).resolve()).startswith(str(self.quarantine_dir.resolve())))

    def test_quarantine_filename_is_sanitized(self):
        decision = self.guard.inspect(b"data", filename="../../etc/passwd", sender_id="628888")
        self.assertNotIn("..", Path(decision.quarantine_path).name)

    def test_sha256_matches_content(self):
        import hashlib
        data = b"isi file untuk dihash"
        decision = self.guard.inspect(data, filename="tugas.pdf", sender_id="628999")
        self.assertEqual(decision.sha256, hashlib.sha256(data).hexdigest())

    def test_scanner_can_escalate_risk_above_deterministic_checks(self):
        def fake_scanner(data, filename):
            return CRITICAL, "Terdeteksi signature malware oleh scanner eksternal."
        guard = AttachmentGuard(self.quarantine_dir, self.db, scanner=fake_scanner)
        decision = guard.inspect(b"%PDF-1.4", filename="tugas.pdf", sender_id="628111")
        self.assertEqual(decision.risk_level, CRITICAL)
        self.assertFalse(decision.allowed)

    def test_scanner_cannot_downgrade_risk_below_deterministic_checks(self):
        def optimistic_scanner(data, filename):
            return LOW, "Scanner bilang aman."
        guard = AttachmentGuard(self.quarantine_dir, self.db, scanner=optimistic_scanner)
        decision = guard.inspect(b"data", filename="invoice.exe", sender_id="628111")
        self.assertEqual(decision.risk_level, CRITICAL)

    def test_scanner_failure_does_not_crash_pipeline(self):
        def broken_scanner(data, filename):
            raise RuntimeError("scanner API down")
        guard = AttachmentGuard(self.quarantine_dir, self.db, scanner=broken_scanner)
        decision = guard.inspect(b"%PDF-1.4", filename="tugas.pdf", sender_id="628111")
        self.assertEqual(decision.risk_level, LOW)
        self.assertTrue(decision.allowed)

    def test_log_is_recorded_for_every_inspection(self):
        import sqlite3
        self.guard.inspect(b"%PDF-1.4", filename="tugas.pdf", sender_id="628111")
        with sqlite3.connect(self.db) as db:
            rows = db.execute("SELECT sender_id, filename, risk_level FROM attachment_log").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0], ("628111", "tugas.pdf", "LOW"))


if __name__ == "__main__":
    unittest.main()
