import tempfile
import unittest
from pathlib import Path

from app.content_learning import ContentLearningStore


class ContentFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "assistant.db"
        self.store = ContentLearningStore(self.db)

    def test_record_feedback_stores_entry_with_defaults(self):
        entry = self.store.record_feedback(
            "risol_mamqi", "instagram", "edited", "hook",
            old_value="Risol enak nih", new_value="Risol anget, isian melimpah!",
            note="Owner suka hook yang lebih deskriptif",
        )
        self.assertTrue(entry.id)
        self.assertEqual(entry.business, "risol_mamqi")
        self.assertEqual(entry.feedback_type, "edited")
        self.assertEqual(entry.aspect, "hook")

    def test_record_feedback_rejects_unknown_feedback_type(self):
        with self.assertRaises(ValueError):
            self.store.record_feedback("risol_mamqi", "instagram", "dihapus_paksa", "hook")

    def test_record_feedback_requires_business_platform_aspect(self):
        with self.assertRaises(ValueError):
            self.store.record_feedback("", "instagram", "edited", "hook")
        with self.assertRaises(ValueError):
            self.store.record_feedback("risol_mamqi", "", "edited", "hook")
        with self.assertRaises(ValueError):
            self.store.record_feedback("risol_mamqi", "instagram", "edited", "")

    def test_recent_feedback_orders_most_recent_first_and_filters_business(self):
        self.store.record_feedback("risol_mamqi", "instagram", "edited", "hook", note="pertama")
        self.store.record_feedback("pixiva_id", "instagram", "edited", "hook", note="usaha lain")
        self.store.record_feedback("risol_mamqi", "instagram", "rejected", "tema", note="kedua")

        entries = self.store.recent_feedback("risol_mamqi")
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].note, "kedua")
        self.assertEqual(entries[1].note, "pertama")

    def test_recent_feedback_filters_by_platform_when_given(self):
        self.store.record_feedback("risol_mamqi", "instagram", "edited", "hook", note="ig")
        self.store.record_feedback("risol_mamqi", "tiktok", "edited", "hook", note="tiktok")

        entries = self.store.recent_feedback("risol_mamqi", "tiktok")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].note, "tiktok")

    def test_recurring_feedback_patterns_ignores_single_occurrence(self):
        self.store.record_feedback("risol_mamqi", "instagram", "rejected", "tema", note="bahas kompetitor")
        patterns = self.store.recurring_feedback_patterns("risol_mamqi")
        self.assertEqual(patterns, [])

    def test_recurring_feedback_patterns_surfaces_repeated_correction(self):
        for _ in range(3):
            self.store.record_feedback(
                "risol_mamqi", "instagram", "edited", "cta",
                note="owner selalu ganti jadi ajakan order langsung",
            )
        self.store.record_feedback("risol_mamqi", "instagram", "rejected", "tema", note="sekali saja")

        patterns = self.store.recurring_feedback_patterns("risol_mamqi", min_occurrences=2)
        self.assertEqual(len(patterns), 1)
        self.assertEqual(patterns[0].aspect, "cta")
        self.assertEqual(patterns[0].occurrences, 3)

    def test_recurring_feedback_patterns_ignores_approved_as_is(self):
        for _ in range(3):
            self.store.record_feedback("risol_mamqi", "instagram", "approved_as_is", "hook")
        patterns = self.store.recurring_feedback_patterns("risol_mamqi")
        self.assertEqual(patterns, [])

    def test_recurring_feedback_patterns_does_not_generalize_across_business(self):
        for _ in range(3):
            self.store.record_feedback("risol_mamqi", "instagram", "rejected", "tema", note="tolak tema A")
        patterns = self.store.recurring_feedback_patterns("pixiva_id")
        self.assertEqual(patterns, [])

    def test_has_sufficient_history_true_false(self):
        self.assertFalse(self.store.has_sufficient_history("risol_mamqi", min_entries=3))
        for _ in range(3):
            self.store.record_feedback("risol_mamqi", "instagram", "edited", "hook")
        self.assertTrue(self.store.has_sufficient_history("risol_mamqi", min_entries=3))


class ContentPerformanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "assistant.db"
        self.store = ContentLearningStore(self.db)

    def test_record_performance_stores_entry(self):
        entry = self.store.record_performance(
            "risol_mamqi", "instagram", "content-1",
            content_type="feed", topic="promo_weekend", reach=1000, likes=80,
        )
        self.assertTrue(entry.id)
        self.assertEqual(entry.topic, "promo_weekend")
        self.assertEqual(entry.reach, 1000)

    def test_record_performance_requires_business_and_platform(self):
        with self.assertRaises(ValueError):
            self.store.record_performance("", "instagram", "content-1")
        with self.assertRaises(ValueError):
            self.store.record_performance("risol_mamqi", "", "content-1")

    def test_recent_performance_orders_most_recent_first_and_filters_business(self):
        self.store.record_performance("risol_mamqi", "instagram", "c1", topic="promo")
        self.store.record_performance("pixiva_id", "instagram", "c2", topic="promo")
        self.store.record_performance("risol_mamqi", "tiktok", "c3", topic="edukasi")

        entries = self.store.recent_performance("risol_mamqi")
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].content_ref, "c3")
        self.assertEqual(entries[1].content_ref, "c1")

    def test_top_performing_topics_ranks_by_average_metric(self):
        self.store.record_performance("risol_mamqi", "instagram", "c1", topic="promo_weekend", reach=500)
        self.store.record_performance("risol_mamqi", "instagram", "c2", topic="promo_weekend", reach=1500)
        self.store.record_performance("risol_mamqi", "instagram", "c3", topic="edukasi_resep", reach=100)

        results = self.store.top_performing_topics("risol_mamqi", metric="reach")
        self.assertEqual(results[0].topic, "promo_weekend")
        self.assertAlmostEqual(results[0].average_metric, 1000.0)
        self.assertEqual(results[0].sample_count, 2)

    def test_top_performing_topics_rejects_unknown_metric(self):
        with self.assertRaises(ValueError):
            self.store.top_performing_topics("risol_mamqi", metric="jumlah_dm")

    def test_top_performing_topics_ignores_entries_without_topic(self):
        self.store.record_performance("risol_mamqi", "instagram", "c1", topic="", reach=99999)
        results = self.store.top_performing_topics("risol_mamqi", metric="reach")
        self.assertEqual(results, [])

    def test_top_performing_topics_respects_min_samples(self):
        self.store.record_performance("risol_mamqi", "instagram", "c1", topic="promo_weekend", reach=500)
        results = self.store.top_performing_topics("risol_mamqi", metric="reach", min_samples=2)
        self.assertEqual(results, [])

    def test_performance_isolated_per_business(self):
        self.store.record_performance("risol_mamqi", "instagram", "c1", topic="promo", reach=1000)
        self.store.record_performance("pixiva_id", "instagram", "c2", topic="promo", reach=5000)

        risol_results = self.store.top_performing_topics("risol_mamqi", metric="reach")
        self.assertEqual(len(risol_results), 1)
        self.assertAlmostEqual(risol_results[0].average_metric, 1000.0)


if __name__ == "__main__":
    unittest.main()
