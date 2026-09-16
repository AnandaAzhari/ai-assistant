import tempfile
import unittest
from pathlib import Path

from app.document_preferences import (
    DocumentPreferenceParser,
    DocumentPreferences,
    DocumentPreferenceStore,
)


class DocumentPreferenceTests(unittest.TestCase):
    def test_default_repeat_mode_is_auto(self):
        prefs = DocumentPreferences()
        self.assertEqual(prefs.citation_repeat_mode, "auto")

    def test_natural_language_without_ibid_becomes_short(self):
        prefs, result = DocumentPreferenceParser.apply(
            "Untuk makalah ini jangan pakai Ibid ya.",
            DocumentPreferences(),
        )
        self.assertTrue(result.matched)
        self.assertFalse(result.ambiguous)
        self.assertTrue(result.changed)
        self.assertEqual(result.field, "citation_repeat_mode")
        self.assertEqual(result.value, "short")
        self.assertEqual(prefs.citation_repeat_mode, "short")

    def test_natural_language_use_ibid_becomes_auto(self):
        current = DocumentPreferences(citation_repeat_mode="short")
        prefs, result = DocumentPreferenceParser.apply("Pakai Ibid saja.", current)
        self.assertTrue(result.matched)
        self.assertEqual(result.value, "auto")
        self.assertTrue(result.changed)
        self.assertEqual(prefs.citation_repeat_mode, "auto")

    def test_combined_customer_message_still_detects_preference(self):
        prefs, result = DocumentPreferenceParser.apply(
            "Saya mau makalah AI Agent 8 halaman, tapi tanpa Ibid untuk catatan kaki.",
            DocumentPreferences(),
        )
        self.assertTrue(result.matched)
        self.assertEqual(prefs.citation_repeat_mode, "short")

    def test_unrelated_message_does_not_change_preferences(self):
        current = DocumentPreferences(citation_repeat_mode="short")
        prefs, result = DocumentPreferenceParser.apply(
            "Saya kelas XII semester 2 mapel Informatika.", current
        )
        self.assertFalse(result.matched)
        self.assertEqual(prefs, current)

    def test_short_note_phrase_is_supported(self):
        prefs, result = DocumentPreferenceParser.apply(
            "Kalau sumber berulang gunakan short note.", DocumentPreferences()
        )
        self.assertTrue(result.matched)
        self.assertEqual(result.value, "short")
        self.assertEqual(prefs.citation_repeat_mode, "short")

    def test_store_persists_per_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DocumentPreferenceStore(Path(tmp) / "prefs.db")
            order_a = "MKL-2026-0001"
            order_b = "MKL-2026-0002"

            updated, result = store.apply_message(order_a, "Jangan gunakan Ibid.")
            self.assertTrue(result.matched)
            self.assertEqual(updated.citation_repeat_mode, "short")
            self.assertEqual(store.load(order_a).citation_repeat_mode, "short")
            self.assertEqual(store.load(order_b).citation_repeat_mode, "auto")

    def test_store_can_switch_back_to_auto(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DocumentPreferenceStore(Path(tmp) / "prefs.db")
            scope = "MKL-TEST"
            store.apply_message(scope, "Tanpa Ibid.")
            prefs, result = store.apply_message(scope, "Sekarang pakai Ibid saja.")
            self.assertTrue(result.changed)
            self.assertEqual(prefs.citation_repeat_mode, "auto")
            self.assertEqual(store.load(scope).citation_repeat_mode, "auto")


if __name__ == "__main__":
    unittest.main()
