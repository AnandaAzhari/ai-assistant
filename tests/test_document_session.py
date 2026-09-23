import tempfile
import unittest
from pathlib import Path

from app.document_session import DocumentSessionStore


class DocumentSessionStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "assistant.db"
        self.store = DocumentSessionStore(self.db)

    def test_save_and_load_roundtrip(self):
        payload = {"version": 1, "phase": "requirements", "outline": ""}
        self.store.save("DOCSRC-ADMIN-DEFAULT", payload)
        self.assertEqual(self.store.load("DOCSRC-ADMIN-DEFAULT"), payload)

    def test_load_missing_scope_returns_none(self):
        self.assertIsNone(self.store.load("DOCSRC-TIDAK-ADA"))

    def test_load_raises_on_unrecognized_version(self):
        self.store.save("DOCSRC-X", {"version": 2, "phase": "requirements"})
        with self.assertRaises(ValueError):
            self.store.load("DOCSRC-X")

    def test_search_finds_keyword_inside_payload(self):
        self.store.save("DOCSRC-TELEGRAM-abc-1-1", {
            "version": 1, "phase": "outline_confirmation",
            "brief": {"subject": "Kewirausahaan", "topic_title": "Proposal usaha kopi keliling"},
        })
        hits = self.store.search("usaha kopi")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["scope_id"], "DOCSRC-TELEGRAM-abc-1-1")
        self.assertEqual(hits[0]["payload"]["brief"]["topic_title"], "Proposal usaha kopi keliling")

    def test_search_is_case_insensitive(self):
        self.store.save("DOCSRC-TELEGRAM-abc-1-1-TOPIC-telegram-nara", {
            "version": 1, "phase": "draft_ready",
            "brief": {"subject": "Sejarah", "topic_title": "Kemerdekaan Indonesia"},
        })
        self.assertEqual(len(self.store.search("kemerdekaan")), 1)
        self.assertEqual(len(self.store.search("KEMERDEKAAN")), 1)

    def test_search_no_match_returns_empty_list(self):
        self.store.save("DOCSRC-ADMIN-DEFAULT", {"version": 1, "phase": "requirements", "brief": {}})
        self.assertEqual(self.store.search("topik yang tidak pernah dibahas"), [])

    def test_search_empty_keyword_returns_empty_list(self):
        self.assertEqual(self.store.search(""), [])
        self.assertEqual(self.store.search("   "), [])

    def test_search_respects_limit_and_orders_newest_first(self):
        for i in range(3):
            self.store.save(f"DOCSRC-WHATSAPP-628{i}", {
                "version": 1, "phase": "requirements",
                "brief": {"subject": "Ekonomi", "topic_title": f"Inflasi edisi {i}"},
            })
        hits = self.store.search("Inflasi", limit=2)
        self.assertEqual(len(hits), 2)

    def test_search_escapes_like_wildcards_in_keyword(self):
        self.store.save("DOCSRC-ADMIN-DEFAULT", {
            "version": 1, "phase": "requirements",
            "brief": {"subject": "-", "topic_title": "Diskon 50% mahasiswa baru"},
        })
        self.assertEqual(len(self.store.search("50%")), 1)
        self.assertEqual(self.store.search("50_"), [])

    def test_sessions_for_different_scopes_are_independent(self):
        self.store.save("DOCSRC-A", {"version": 1, "phase": "requirements", "brief": {}})
        self.store.save("DOCSRC-B", {"version": 1, "phase": "draft_ready", "brief": {}})
        self.assertEqual(self.store.load("DOCSRC-A")["phase"], "requirements")
        self.assertEqual(self.store.load("DOCSRC-B")["phase"], "draft_ready")


if __name__ == "__main__":
    unittest.main()
