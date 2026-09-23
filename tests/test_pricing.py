import tempfile
import unittest
from pathlib import Path

from app.pricing import (
    PRICING_SETTING_KEYS,
    PricingConfigStore,
    Quote,
    QuoteRequest,
    make_quote,
)


class PricingConfigStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_path = Path(self.temp.name) / "assistant.db"

    def test_seeds_default_packages_and_settings_on_first_use(self):
        store = PricingConfigStore(self.db_path)
        tiers = store.list_packages()
        names = {tier.name for tier in tiers}
        self.assertEqual(names, {"Ringkas", "Standar", "Lengkap"})
        settings = store.all_settings()
        self.assertEqual(set(settings), PRICING_SETTING_KEYS)
        self.assertEqual(settings["halaman_tambahan"], 6000)
        self.assertEqual(settings["dp_ambang"], 35000)
        self.assertEqual(settings["dp_persen"], 30)

    def test_reopening_store_does_not_reseed_or_overwrite_changes(self):
        store = PricingConfigStore(self.db_path)
        store.set_setting("halaman_tambahan", 7000, updated_by="admin:telegram")
        store.remove_package("Lengkap")
        reopened = PricingConfigStore(self.db_path)
        self.assertEqual(reopened.all_settings()["halaman_tambahan"], 7000)
        self.assertNotIn("Lengkap", {t.name for t in reopened.list_packages()})

    def test_set_package_creates_and_updates(self):
        store = PricingConfigStore(self.db_path)
        store.set_package("Ekonomis", 3, 20000, updated_by="admin:telegram")
        tier = next(t for t in store.list_packages() if t.name == "Ekonomis")
        self.assertEqual((tier.page_limit, tier.price), (3, 20000))
        store.set_package("Ekonomis", 4, 22000, updated_by="admin:telegram")
        tier = next(t for t in store.list_packages() if t.name == "Ekonomis")
        self.assertEqual((tier.page_limit, tier.price), (4, 22000))

    def test_set_package_rejects_invalid_values(self):
        store = PricingConfigStore(self.db_path)
        with self.assertRaises(ValueError):
            store.set_package("", 5, 10000, updated_by="admin:telegram")
        with self.assertRaises(ValueError):
            store.set_package("X", 0, 10000, updated_by="admin:telegram")
        with self.assertRaises(ValueError):
            store.set_package("X", 5, 0, updated_by="admin:telegram")
        with self.assertRaises(ValueError):
            store.set_package("X", 5, 10000, updated_by="")

    def test_remove_package_returns_false_when_not_found(self):
        store = PricingConfigStore(self.db_path)
        self.assertFalse(store.remove_package("Tidak Ada"))
        self.assertTrue(store.remove_package("Ringkas"))

    def test_list_packages_sorted_by_page_limit(self):
        store = PricingConfigStore(self.db_path)
        limits = [t.page_limit for t in store.list_packages()]
        self.assertEqual(limits, sorted(limits))

    def test_set_setting_rejects_unknown_key(self):
        store = PricingConfigStore(self.db_path)
        with self.assertRaises(ValueError):
            store.set_setting("kunci_ngawur", 100, updated_by="admin:telegram")

    def test_set_setting_rejects_negative_value(self):
        store = PricingConfigStore(self.db_path)
        with self.assertRaises(ValueError):
            store.set_setting("halaman_tambahan", -1, updated_by="admin:telegram")

    def test_set_setting_rejects_percent_over_100(self):
        store = PricingConfigStore(self.db_path)
        with self.assertRaises(ValueError):
            store.set_setting("rush_persen", 101, updated_by="admin:telegram")
        with self.assertRaises(ValueError):
            store.set_setting("dp_persen", 150, updated_by="admin:telegram")

    def test_set_setting_requires_updated_by(self):
        store = PricingConfigStore(self.db_path)
        with self.assertRaises(ValueError):
            store.set_setting("rush_persen", 20, updated_by="")

    def test_load_config_reflects_current_store_state(self):
        store = PricingConfigStore(self.db_path)
        store.set_setting("rush_persen", 25, updated_by="admin:telegram")
        config = store.load_config()
        self.assertEqual(config.settings["rush_persen"], 25)
        self.assertEqual(len(config.packages), 3)


class MakeQuoteMakalahTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = PricingConfigStore(Path(self.temp.name) / "assistant.db")
        self.config = self.store.load_config()

    def test_auto_package_selection_picks_smallest_sufficient_tier(self):
        quote = make_quote(QuoteRequest(pages=8), self.config)
        self.assertIn("Standar", quote.label)
        self.assertEqual(quote.total, 60000)

    def test_explicit_package_keeps_choice_and_adds_overage(self):
        quote = make_quote(QuoteRequest(pages=8, package_name="Ringkas"), self.config)
        self.assertEqual(quote.total, 35000 + 3 * 6000)

    def test_unknown_explicit_package_raises(self):
        with self.assertRaises(ValueError):
            make_quote(QuoteRequest(pages=8, package_name="Paket Ngawur"), self.config)

    def test_pages_beyond_largest_tier_auto_flags_review_reason(self):
        quote = make_quote(QuoteRequest(pages=25), self.config)
        self.assertTrue(quote.review_reasons)
        self.assertIn("Lengkap", quote.label)

    def test_explicit_package_beyond_its_limit_does_not_flag_review(self):
        quote = make_quote(QuoteRequest(pages=25, package_name="Lengkap"), self.config)
        self.assertEqual(quote.review_reasons, ())

    def test_zero_or_negative_pages_rejected(self):
        with self.assertRaises(ValueError):
            make_quote(QuoteRequest(pages=0), self.config)

    def test_dp_split_at_and_above_threshold(self):
        below = make_quote(QuoteRequest(pages=5), self.config)  # total 35000, tepat di ambang
        self.assertEqual((below.dp_amount, below.sisa), (35000, 0))
        above = make_quote(QuoteRequest(pages=8), self.config)  # total 60000
        self.assertEqual((above.dp_amount, above.sisa), (18000, 42000))
        self.assertEqual(above.dp_amount + above.sisa, above.total)

    def test_footnote_within_bundle_limit_charges_flat_bundle_price(self):
        quote = make_quote(QuoteRequest(pages=8, footnote_count=5), self.config)
        self.assertEqual(quote.footnote_fee, 15000)

    def test_footnote_beyond_bundle_limit_charges_extra_per_note(self):
        quote = make_quote(QuoteRequest(pages=8, footnote_count=13), self.config)
        self.assertEqual(quote.footnote_fee, 15000 + 3 * 1000)

    def test_no_footnote_means_zero_fee(self):
        quote = make_quote(QuoteRequest(pages=8), self.config)
        self.assertEqual(quote.footnote_fee, 0)

    def test_rush_fee_is_percent_of_subtotal_rounded_up(self):
        quote = make_quote(QuoteRequest(pages=8, rush=True), self.config)
        self.assertEqual(quote.rush_fee, 18000)  # 30% dari 60000
        self.assertEqual(quote.total, 60000 + 18000)

    def test_rush_fee_applies_on_top_of_footnote_subtotal(self):
        quote = make_quote(QuoteRequest(pages=8, footnote_count=5, rush=True), self.config)
        subtotal = 60000 + 15000
        self.assertEqual(quote.rush_fee, round(subtotal * 0.3))
        self.assertEqual(quote.total, subtotal + quote.rush_fee)

    def test_both_pages_and_tidy_level_given_raises(self):
        with self.assertRaises(ValueError):
            make_quote(QuoteRequest(pages=5, tidy_level="dasar", tidy_pages=3), self.config)

    def test_neither_pages_nor_tidy_level_given_raises(self):
        with self.assertRaises(ValueError):
            make_quote(QuoteRequest(), self.config)


class MakeQuoteRapikanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = PricingConfigStore(Path(self.temp.name) / "assistant.db")
        self.config = self.store.load_config()

    def test_dasar_level_uses_per_page_rate_when_above_minimum(self):
        quote = make_quote(QuoteRequest(tidy_level="dasar", tidy_pages=10), self.config)
        self.assertEqual(quote.base_price, 20000)  # 10 x 2000, di atas minimum 15000

    def test_dasar_level_enforces_minimum_for_small_documents(self):
        quote = make_quote(QuoteRequest(tidy_level="dasar", tidy_pages=2), self.config)
        self.assertEqual(quote.base_price, 15000)  # minimum, bukan 2 x 2000

    def test_struktur_level_pricing(self):
        quote = make_quote(QuoteRequest(tidy_level="struktur", tidy_pages=10), self.config)
        self.assertEqual(quote.base_price, 35000)  # 10 x 3500

    def test_khusus_level_flags_review_reason(self):
        quote = make_quote(QuoteRequest(tidy_level="khusus", tidy_pages=10), self.config)
        self.assertTrue(quote.review_reasons)

    def test_unknown_tidy_level_rejected(self):
        with self.assertRaises(ValueError):
            make_quote(QuoteRequest(tidy_level="super", tidy_pages=10), self.config)

    def test_zero_tidy_pages_rejected(self):
        with self.assertRaises(ValueError):
            make_quote(QuoteRequest(tidy_level="dasar", tidy_pages=0), self.config)

    def test_rapikan_mode_dp_split_uses_same_threshold(self):
        quote = make_quote(QuoteRequest(tidy_level="khusus", tidy_pages=10), self.config)  # total 50000
        self.assertEqual(quote.total, 50000)
        self.assertEqual((quote.dp_amount, quote.sisa), (15000, 35000))


if __name__ == "__main__":
    unittest.main()
