import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from app.desktop import DesktopAgent, open_in_windows
from app.lead import LeadAgent
from main import main, report


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.opener = Mock()
        self.desktop = DesktopAgent(self.root, opener=self.opener)
        self.lead = LeadAgent(self.desktop)
        self.document = self.root / "contoh pelanggan.txt"
        self.document.write_text("Dokumen uji", encoding="utf-8")

    def test_order_creates_folder_and_waits_for_visual_verification(self):
        result = self.lead.dispatch("pesanan", name="Uji-001", path=self.document.name)
        self.assertTrue((self.root / "Uji-001").is_dir())
        self.opener.assert_called_once_with(self.document)
        self.assertEqual(result.status, "menunggu_verifikasi")
        self.assertEqual(self.document.read_text(encoding="utf-8"), "Dokumen uji")
        self.assertFalse((self.root / "Uji-001" / self.document.name).exists())

    def test_existing_folder_keeps_contents(self):
        folder = self.root / "Lama"
        folder.mkdir()
        old = folder / "catatan.txt"
        old.write_text("Tetap", encoding="utf-8")
        result = self.lead.dispatch("folder", name="Lama")
        self.assertEqual(result.status, "berhasil")
        self.assertIn("sudah ada", result.messages[0])
        self.assertEqual(old.read_text(encoding="utf-8"), "Tetap")

    def test_invalid_folder_names_do_not_create_or_open(self):
        for name in ["", "..", "../keluar", "a/b", "a\\b", "CON", "con.txt", "LPT1", "COM¹", "nama.", " nama", "C:folder", "a\x00b"]:
            with self.subTest(name=name):
                result = self.lead.dispatch("pesanan", name=name, path=self.document.name)
                self.assertEqual(result.status, "gagal")
        self.opener.assert_not_called()

    def test_collision_with_file_stops_order(self):
        result = self.lead.dispatch("pesanan", name=self.document.name, path=self.document.name)
        self.assertEqual(result.status, "gagal")
        self.opener.assert_not_called()
        self.assertEqual(self.document.read_text(encoding="utf-8"), "Dokumen uji")

    def test_missing_document_reports_partial_and_keeps_folder(self):
        result = self.lead.dispatch("pesanan", name="Uji-002", path="hilang.pdf")
        self.assertEqual(result.status, "sebagian_selesai")
        self.assertTrue((self.root / "Uji-002").is_dir())
        self.opener.assert_not_called()

    def test_opener_failure_is_not_success_or_retried(self):
        self.opener.side_effect = OSError("Aplikasi tidak tersedia")
        result = self.lead.dispatch("pesanan", name="Uji-003", path=self.document.name)
        self.assertEqual(result.status, "sebagian_selesai")
        self.assertIsNone(result.pending_file)
        self.assertTrue((self.root / "Uji-003").is_dir())
        self.opener.assert_called_once()

    def test_exact_quoted_path_with_spaces(self):
        result = self.lead.dispatch("buka", path=f'"{self.document}"')
        self.assertEqual(result.pending_file, self.document)
        self.opener.assert_called_once_with(self.document)

    def test_no_fuzzy_selection(self):
        result = self.lead.dispatch("buka", path="contoh")
        self.assertEqual(result.status, "gagal")
        self.opener.assert_not_called()

    def test_executable_and_directory_are_not_opened(self):
        executable = self.root / "script.bat"
        executable.write_text("echo test", encoding="utf-8")
        for target in [executable.name, str(self.root), ""]:
            self.assertEqual(self.lead.dispatch("buka", path=target).status, "gagal")
        self.opener.assert_not_called()

    def test_outside_workspace_and_traversal_are_rejected(self):
        workspace = self.root / "kerja"
        workspace.mkdir()
        agent = DesktopAgent(workspace, opener=self.opener)
        for target in [str(self.document), "../" + self.document.name]:
            self.assertEqual(agent.open_file(target).status, "gagal")
        self.opener.assert_not_called()

    def test_symlink_to_outside_workspace_is_rejected(self):
        workspace = self.root / "kerja"
        workspace.mkdir()
        link = workspace / "tautan.txt"
        try:
            link.symlink_to(self.document)
        except OSError:
            self.skipTest("Lingkungan ini tidak mengizinkan pembuatan symlink.")
        agent = DesktopAgent(workspace, opener=self.opener)
        self.assertEqual(agent.open_file(link.name).status, "gagal")
        self.opener.assert_not_called()

    def test_unknown_command_has_no_side_effects(self):
        before = set(self.root.iterdir())
        result = self.lead.dispatch("hapus semua", name="Baru")
        self.assertEqual(result.status, "membutuhkan_bantuan")
        self.assertEqual(before, set(self.root.iterdir()))
        self.opener.assert_not_called()

    def test_missing_workspace_is_not_created(self):
        missing = self.root / "belum-ada"
        with self.assertRaises(FileNotFoundError):
            DesktopAgent(missing)
        self.assertFalse(missing.exists())

    def test_report_only_claims_visual_success_on_user_confirmation(self):
        for answer, expected in [("y", "berhasil. Verifikasi tampilan berdasarkan konfirmasi pengguna"),
                                 ("n", "sebagian selesai"), ("", "menunggu verifikasi")]:
            with self.subTest(answer=answer):
                result = self.desktop.open_file(self.document.name)
                output = io.StringIO()
                with patch("builtins.input", return_value=answer), redirect_stdout(output):
                    report(result)
                self.assertIn("Status akhir: " + expected, output.getvalue())

    def test_terminal_routes_order_and_exits(self):
        output = io.StringIO()
        responses = ["pesanan", "Terminal-001", self.document.name, "y", "keluar"]
        with patch("sys.argv", ["main.py", "--workspace", str(self.root)]), \
                patch("sys.platform", "win32"), \
                patch("app.desktop.open_in_windows", self.opener), \
                patch("builtins.input", side_effect=responses), redirect_stdout(output):
            self.assertEqual(main(), 0)
        self.assertTrue((self.root / "Terminal-001").is_dir())
        self.opener.assert_called_once_with(self.document)
        self.assertIn("berdasarkan konfirmasi pengguna", output.getvalue())
        self.assertIn("Program ditutup", output.getvalue())

    def test_windows_adapter_uses_startfile_open(self):
        with patch("app.desktop.os.name", "nt"), patch("app.desktop.os.startfile", create=True) as start:
            open_in_windows(self.document)
        start.assert_called_once_with(str(self.document), "open")

    @unittest.skipIf(os.name == "nt", "Hanya memeriksa penolakan sistem selain Windows.")
    def test_non_windows_open_fails_explicitly(self):
        with self.assertRaisesRegex(OSError, "Windows"):
            open_in_windows(self.document)


if __name__ == "__main__":
    unittest.main()
