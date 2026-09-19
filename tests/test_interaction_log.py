import tempfile
import unittest
from pathlib import Path

from app.interaction_log import InteractionLogStore


class InteractionLogStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "assistant.db"
        self.store = InteractionLogStore(self.db)

    def test_log_stores_entry_with_defaults(self):
        entry = self.store.log(
            "nara", "628111", "whatsapp", "Bantu buat makalah tentang fotosintesis",
            "Baik, boleh saya tahu untuk jenjang apa?", status="berhasil", model="deepseek-v4-pro",
        )
        self.assertTrue(entry.id)
        self.assertEqual(entry.agent, "nara")
        self.assertFalse(entry.reviewed)
        self.assertEqual(entry.review_label, "")

    def test_log_requires_agent(self):
        with self.assertRaises(ValueError):
            self.store.log("", "628111", "whatsapp", "halo", "halo juga")

    def test_log_truncates_overly_long_text(self):
        long_text = "a" * 5000
        entry = self.store.log("nara", "628111", "whatsapp", long_text, long_text)
        self.assertEqual(len(entry.input_text), 4000)
        self.assertEqual(len(entry.output_text), 4000)

    def test_get_returns_none_for_unknown_id(self):
        self.assertIsNone(self.store.get("tidak-ada"))

    def test_get_returns_logged_entry(self):
        entry = self.store.log("taqi", "628111", "whatsapp", "halo", "Halo kak, ada yang bisa dibantu?")
        fetched = self.store.get(entry.id)
        self.assertEqual(fetched, entry)

    def test_sample_for_review_returns_oldest_unreviewed_first(self):
        first = self.store.log("nara", "628111", "whatsapp", "pesan 1", "balasan 1")
        self.store.log("nara", "628222", "whatsapp", "pesan 2", "balasan 2")
        sample = self.store.sample_for_review("nara", limit=10)
        self.assertEqual(sample[0].id, first.id)

    def test_sample_for_review_filters_by_agent(self):
        self.store.log("nara", "628111", "whatsapp", "pesan nara", "balasan nara")
        self.store.log("kirana", "risol_mamqi", "telegram", "brief kirana", "draft kirana")
        sample = self.store.sample_for_review("kirana", limit=10)
        self.assertEqual(len(sample), 1)
        self.assertEqual(sample[0].agent, "kirana")

    def test_sample_for_review_excludes_reviewed_by_default(self):
        entry = self.store.log("nara", "628111", "whatsapp", "pesan", "balasan")
        self.store.mark_reviewed(entry.id, "baik")
        sample = self.store.sample_for_review("nara")
        self.assertEqual(sample, [])

    def test_sample_for_review_can_include_reviewed(self):
        entry = self.store.log("nara", "628111", "whatsapp", "pesan", "balasan")
        self.store.mark_reviewed(entry.id, "baik")
        sample = self.store.sample_for_review("nara", only_unreviewed=False)
        self.assertEqual(len(sample), 1)

    def test_mark_reviewed_updates_entry(self):
        entry = self.store.log("nara", "628111", "whatsapp", "pesan", "balasan")
        updated = self.store.mark_reviewed(
            entry.id, "perlu_perbaikan", note="Kurang jelas soal deadline", reviewed_by="admin:telegram",
        )
        self.assertTrue(updated.reviewed)
        self.assertEqual(updated.review_label, "perlu_perbaikan")
        self.assertEqual(updated.review_note, "Kurang jelas soal deadline")
        self.assertEqual(updated.reviewed_by, "admin:telegram")
        self.assertTrue(updated.reviewed_at)

    def test_mark_reviewed_rejects_unknown_label(self):
        entry = self.store.log("nara", "628111", "whatsapp", "pesan", "balasan")
        with self.assertRaises(ValueError):
            self.store.mark_reviewed(entry.id, "luar_biasa")

    def test_mark_reviewed_rejects_unknown_id(self):
        with self.assertRaises(ValueError):
            self.store.mark_reviewed("tidak-ada", "baik")

    def test_review_summary_counts_by_label(self):
        e1 = self.store.log("nara", "1", "whatsapp", "a", "b")
        e2 = self.store.log("nara", "2", "whatsapp", "a", "b")
        self.store.log("nara", "3", "whatsapp", "a", "b")
        self.store.mark_reviewed(e1.id, "baik")
        self.store.mark_reviewed(e2.id, "tidak_baik")
        summary = self.store.review_summary("nara")
        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["reviewed"], 2)
        self.assertEqual(summary["unreviewed"], 1)
        self.assertEqual(summary["baik"], 1)
        self.assertEqual(summary["tidak_baik"], 1)

    def test_review_summary_isolated_per_agent(self):
        self.store.log("nara", "1", "whatsapp", "a", "b")
        self.store.log("kirana", "2", "telegram", "a", "b")
        summary = self.store.review_summary("nara")
        self.assertEqual(summary["total"], 1)


if __name__ == "__main__":
    unittest.main()
