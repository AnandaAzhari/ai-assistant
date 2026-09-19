"""`TELEGRAM_COMMAND_MENU` (app/lead.py) — daftar perintah untuk menu "/" bawaan
Telegram (`TelegramHTTPClient.set_my_commands`, lihat `telegram_main.py`). Dua hal
yang perlu dijaga supaya menu ini tidak diam-diam basi/salah:
1. Setiap nama perintah memenuhi aturan format Telegram (huruf kecil/angka/underscore,
   1-32 karakter) dan tidak ada duplikat.
2. Setiap perintah di menu benar-benar dikenali `LeadAgent.handle_admin_message` —
   supaya menu tidak pernah menawarkan perintah yang ternyata jatuh ke fallback
   "Perintah belum dikenal" kalau diketuk."""

import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.admin_runtime import create_admin_lead
from app.lead import TELEGRAM_COMMAND_MENU

_COMMAND_NAME_PATTERN = re.compile(r"^[a-z0-9_]{1,32}$")
_UNKNOWN_COMMAND_TEXT = "Perintah belum dikenal. Ketik /bantuan."


class TelegramCommandMenuFormatTests(unittest.TestCase):
    def test_command_names_follow_telegram_naming_rules(self):
        for command, _description in TELEGRAM_COMMAND_MENU:
            with self.subTest(command=command):
                self.assertRegex(command, _COMMAND_NAME_PATTERN)

    def test_descriptions_are_non_empty_and_reasonably_short(self):
        for command, description in TELEGRAM_COMMAND_MENU:
            with self.subTest(command=command):
                self.assertTrue(description.strip())
                self.assertLessEqual(len(description), 256)  # batas API Telegram

    def test_no_duplicate_command_names(self):
        names = [command for command, _description in TELEGRAM_COMMAND_MENU]
        self.assertEqual(len(names), len(set(names)))

    def test_help_is_registered_in_the_menu(self):
        self.assertIn("help", [command for command, _description in TELEGRAM_COMMAND_MENU])


class TelegramCommandMenuRoutingTests(unittest.TestCase):
    """Setiap perintah di menu harus dikenali router admin sungguhan — bukan cuma
    format namanya valid, tapi juga benar-benar ada di `handle_admin_message`."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        patcher = patch.dict(os.environ, {
            "DATABASE_PATH": str(Path(self.temp.name) / "assistant.db"),
            "DEEPSEEK_API_KEY": "", "GOOGLE_SHEETS_WEBHOOK_URL": "", "GOOGLE_SHEETS_SYNC_SECRET": "",
        })
        patcher.start()
        self.addCleanup(patcher.stop)
        self.lead = create_admin_lead(channel="telegram", document_scope="DOCSRC-TELEGRAM-menu-test")

    def test_every_menu_command_is_recognized_by_the_admin_router(self):
        for command, _description in TELEGRAM_COMMAND_MENU:
            with self.subTest(command=command):
                reply = self.lead.handle_admin_message("/" + command)
                self.assertNotEqual(reply.text, _UNKNOWN_COMMAND_TEXT)

    def test_help_shows_the_full_command_list(self):
        reply = self.lead.handle_admin_message("/help")
        self.assertEqual(reply.status, "berhasil")
        self.assertIn("/laba_rugi", reply.text)
        self.assertIn("/arus_kas", reply.text)


if __name__ == "__main__":
    unittest.main()
