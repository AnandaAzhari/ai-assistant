import tempfile
import unittest
from pathlib import Path

from app.dp_policy import DpPolicyStore


class DpPolicyStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = DpPolicyStore(Path(self.temp.name) / "assistant.db")

    def test_default_is_optional_before_ever_changed(self):
        self.assertFalse(self.store.is_mandatory())
        state = self.store.status()
        self.assertFalse(state.mandatory)
        self.assertEqual(state.reason, "")
        self.assertEqual(state.changed_by, "")

    def test_set_mandatory_flips_status_and_records_audit_fields(self):
        state = self.store.set_mandatory(reason="Banyak yang kabur setelah pesan", changed_by="admin:telegram")
        self.assertTrue(state.mandatory)
        self.assertEqual(state.reason, "Banyak yang kabur setelah pesan")
        self.assertEqual(state.changed_by, "admin:telegram")
        self.assertTrue(self.store.is_mandatory())

    def test_set_optional_flips_back(self):
        self.store.set_mandatory(changed_by="admin:telegram")
        state = self.store.set_optional(reason="Sudah stabil lagi", changed_by="admin:telegram")
        self.assertFalse(state.mandatory)
        self.assertFalse(self.store.is_mandatory())

    def test_changed_by_is_required(self):
        with self.assertRaises(ValueError):
            self.store.set_mandatory(changed_by="")
        with self.assertRaises(ValueError):
            self.store.set_optional(changed_by="")

    def test_reason_is_optional(self):
        state = self.store.set_mandatory(changed_by="admin:telegram")
        self.assertEqual(state.reason, "")

    def test_status_persists_across_reopened_store(self):
        self.store.set_mandatory(reason="uji", changed_by="admin:telegram")
        reopened = DpPolicyStore(self.store.db_path)
        self.assertTrue(reopened.is_mandatory())

    def test_history_is_append_only_and_most_recent_first(self):
        self.store.set_mandatory(reason="satu", changed_by="admin:telegram")
        self.store.set_optional(reason="dua", changed_by="admin:telegram")
        self.store.set_mandatory(reason="tiga", changed_by="admin:telegram")
        history = self.store.history()
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0]["reason"], "tiga")
        self.assertEqual(history[-1]["reason"], "satu")

    def test_history_respects_limit(self):
        for i in range(5):
            self.store.set_mandatory(reason=str(i), changed_by="admin:telegram")
        self.assertEqual(len(self.store.history(limit=2)), 2)


if __name__ == "__main__":
    unittest.main()
