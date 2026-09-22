from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from chatgpt_billing.payment_flow import DemoStore
from chatgpt_billing.pricing import QuoteRequest, load_config, make_quote
from chatgpt_billing.telegram_admin import DemoTelegramAdmin


class PricingTests(unittest.TestCase):
    def test_package_boundaries(self):
        for pages, total in [(1, 35000), (5, 35000), (6, 60000), (10, 60000),
                             (11, 90000), (15, 90000), (16, 96000)]:
            with self.subTest(pages=pages):
                quote = make_quote(QuoteRequest(pages=pages))
                self.assertEqual(quote.total, total)

    def test_explicit_package_preserves_agreed_base_and_extra_pages(self):
        quote = make_quote(QuoteRequest(pages=8, package="ringkas"))
        self.assertEqual(quote.total, 53000)
        self.assertEqual(len(quote.lines), 2)

    def test_basic_format_is_included_in_makalah(self):
        quote = make_quote(QuoteRequest())
        self.assertEqual(quote.total, 60000)
        self.assertEqual(len(quote.lines), 1)

    def test_formatting_levels_are_alternatives_not_cumulative(self):
        for level, total in [("dasar", 20000), ("struktur", 35000), ("khusus", 50000)]:
            with self.subTest(level=level):
                quote = make_quote(QuoteRequest(service="rapikan", pages=10, formatting=level))
                self.assertEqual(quote.total, total)
                self.assertEqual(len(quote.lines), 1)

    def test_formatting_minimum(self):
        for level, total in [("dasar", 15000), ("struktur", 25000), ("khusus", 40000)]:
            with self.subTest(level=level):
                quote = make_quote(QuoteRequest(service="rapikan", pages=1, formatting=level))
                self.assertEqual(quote.total, total)

    def test_bundle_never_charges_included_footnotes_twice(self):
        for count, total in [(1, 75000), (10, 75000), (12, 77000)]:
            with self.subTest(count=count):
                quote = make_quote(QuoteRequest(footnote_mode="bundle", footnote_count=count))
                self.assertEqual(quote.total, total)

    def test_existing_footnotes_minimum(self):
        quote = make_quote(QuoteRequest(service="rapikan", pages=1, footnote_mode="rapikan", footnote_count=2))
        self.assertEqual(quote.total, 25000)

    def test_rush_adds_30_percent_of_all_services_once(self):
        quote = make_quote(QuoteRequest(footnote_mode="bundle", footnote_count=10, rush=True))
        self.assertEqual(quote.total, 97500)
        self.assertEqual(quote.required_before_work, 29250)
        self.assertTrue(quote.review_reasons)

    def test_source_and_revision_prices_require_manual_review(self):
        quote = make_quote(QuoteRequest(sources_to_verify=2, extra_revision_rounds=1))
        self.assertEqual(quote.total, 80000)
        self.assertEqual(quote.revision_rounds, 2)
        self.assertEqual(len(quote.review_reasons), 2)

    def test_payment_threshold_uses_total_including_addons(self):
        small = make_quote(QuoteRequest(pages=5))
        bundle = make_quote(QuoteRequest(pages=5, footnote_mode="bundle", footnote_count=1))
        self.assertEqual(small.required_before_work, 35000)
        self.assertEqual(bundle.required_before_work, 15000)

    def test_fractional_rupiah_rounded_up(self):
        cfg = load_config()
        cfg["packages"]["standar"]["price"] = 60001
        quote = make_quote(QuoteRequest(), cfg)
        self.assertEqual(quote.required_before_work, 18001)

    def test_boolean_float_and_negative_counts_rejected(self):
        for value in [True, False, 1.5, -1, 0, "10", 1001]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                make_quote(QuoteRequest(pages=value))

    def test_invalid_choices_rejected_instead_of_silently_ignored(self):
        for changes in [dict(service="lain"), dict(package="premium"), dict(formatting="struktur"),
                        dict(footnote_count=1), dict(footnote_mode="bundle", footnote_count=0),
                        dict(service="rapikan", package="ringkas"),
                        dict(service="rapikan", footnote_mode="bundle", footnote_count=10),
                        dict(footnote_mode="rapikan", footnote_count=10), dict(rush=1)]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                make_quote(QuoteRequest(**changes))

    def test_invalid_config_is_not_used(self):
        mutations = [lambda c: c["payment"].update(deposit_percent=0),
                     lambda c: c.update(rush_percent=True),
                     lambda c: c["packages"]["standar"].update(pages=4),
                     lambda c: c.update(status="PRODUCTION"),
                     lambda c: c.update(unknown=1)]
        for mutate in mutations:
            cfg = load_config()
            mutate(cfg)
            with self.assertRaises(ValueError):
                make_quote(QuoteRequest(), cfg)

    def test_utf8_bom_config_supported_and_corrupt_json_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps(load_config()), encoding="utf-8-sig")
            self.assertEqual(load_config(path)["status"], "USULAN_UNTUK_UJI")
            path.write_text("{", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_config(path)


class PaymentTests(unittest.TestCase):
    def setUp(self):
        self.store = DemoStore()
        self.quote = make_quote(QuoteRequest())
        self.order = self.store.create_order(self.quote, approved_by="operator-uji")
        self.ident = self.order.order_id

    def tearDown(self):
        self.store.close()

    def accepted(self):
        return self.store.accept_quote(self.ident, actor="pelanggan-uji")

    def paid_initial(self):
        self.accepted()
        return self.store.simulate_payment(self.ident, "dp-1", 18000)

    def preview(self):
        self.paid_initial()
        self.store.start_work(self.ident, actor="operator-uji")
        return self.store.send_preview(self.ident, "pratinjau-demo.pdf", actor="operator-uji")

    def test_quote_must_be_accepted_before_payment_and_work(self):
        with self.assertRaises(ValueError):
            self.store.simulate_payment(self.ident, "p-1", 18000)
        with self.assertRaises(ValueError):
            self.store.start_work(self.ident, actor="operator-uji")
        self.assertEqual(self.store.get(self.ident).paid, 0)

    def test_partial_deposit_blocks_work_until_threshold(self):
        self.accepted()
        order = self.store.simulate_payment(self.ident, "dp-1", 17999)
        self.assertFalse(order.can_start)
        with self.assertRaises(ValueError):
            self.store.start_work(self.ident, actor="operator-uji")
        order = self.store.simulate_payment(self.ident, "dp-2", 1)
        self.assertTrue(order.can_start)
        self.assertEqual(self.store.start_work(self.ident, actor="operator-uji").status, "working")

    def test_pending_failed_and_expired_do_not_count_as_money(self):
        self.accepted()
        for status in ("pending", "deny", "expire"):
            self.store.simulate_payment(self.ident, status, 18000, status=status)
        self.assertEqual(self.store.get(self.ident).paid, 0)

    def test_pending_can_become_settled(self):
        self.accepted()
        self.store.simulate_payment(self.ident, "dp-1", 18000, status="pending")
        order = self.store.simulate_payment(self.ident, "dp-1", 18000)
        self.assertEqual(order.paid, 18000)

    def test_retries_and_out_of_order_events_do_not_double_or_reverse_money(self):
        self.paid_initial()
        for status in ("settlement", "pending", "expire", "deny", "settlement"):
            self.store.simulate_payment(self.ident, "dp-1", 18000, status=status)
        self.assertEqual(self.store.get(self.ident).paid, 18000)
        self.assertEqual(sum(e["action"] == "simulated_payment" for e in self.store.events(self.ident)), 1)

    def test_transaction_reference_cannot_change_amount_or_customer_order(self):
        self.paid_initial()
        with self.assertRaises(ValueError):
            self.store.simulate_payment(self.ident, "dp-1", 18001)
        other = self.store.create_order(self.quote, approved_by="operator-uji")
        self.store.accept_quote(other.order_id, actor="pelanggan-lain")
        with self.assertRaises(ValueError):
            self.store.simulate_payment(other.order_id, "dp-1", 18000)
        self.assertEqual(self.store.get(other.order_id).paid, 0)

    def test_bad_amounts_and_real_provider_labels_rejected(self):
        self.accepted()
        for amount in (0, -1, True, 1.5, "18000", 60001):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                self.store.simulate_payment(self.ident, "bad", amount)
        with self.assertRaises(ValueError):
            self.store.simulate_payment(self.ident, "live", 18000, source="midtrans")
        self.assertEqual(self.store.get(self.ident).paid, 0)

    def test_final_requires_full_payment_and_preview_approval(self):
        self.preview()
        with self.assertRaises(ValueError):
            self.store.release_final(self.ident, "final.docx", actor="operator-uji")
        self.store.approve_preview(self.ident, actor="pelanggan-uji")
        self.assertEqual(self.store.get(self.ident).status, "waiting_balance")
        with self.assertRaises(ValueError):
            self.store.release_final(self.ident, "final.docx", actor="operator-uji")
        self.store.simulate_payment(self.ident, "balance", 42000)
        self.assertTrue(self.store.get(self.ident).can_deliver)
        order = self.store.release_final(self.ident, "final.docx", actor="operator-uji")
        self.assertEqual(order.status, "delivered")
        self.assertEqual(order.paid, 60000)
        self.assertEqual(order.remaining, 0)

    def test_early_full_payment_does_not_skip_review(self):
        self.accepted()
        self.store.simulate_payment(self.ident, "full", 60000)
        self.store.start_work(self.ident, actor="operator-uji")
        self.store.send_preview(self.ident, "preview.pdf", actor="operator-uji")
        with self.assertRaises(ValueError):
            self.store.release_final(self.ident, "final.docx", actor="operator-uji")
        self.store.approve_preview(self.ident, actor="pelanggan-uji")
        self.assertTrue(self.store.get(self.ident).can_deliver)

    def test_small_job_requires_full_payment(self):
        quote = make_quote(QuoteRequest(service="rapikan", pages=1))
        order = self.store.create_order(quote, approved_by="operator-uji")
        self.store.accept_quote(order.order_id, actor="pelanggan-uji")
        order = self.store.simulate_payment(order.order_id, "small-dp", 4500)
        self.assertFalse(order.can_start)
        order = self.store.simulate_payment(order.order_id, "small-rest", 10500)
        self.assertTrue(order.can_start)

    def test_revision_limit_and_free_provider_correction(self):
        self.preview()
        self.store.request_revision(self.ident, "Judul kurang sesuai", actor="pelanggan-uji")
        self.store.send_preview(self.ident, "preview-v2.pdf", actor="operator-uji")
        with self.assertRaises(ValueError):
            self.store.request_revision(self.ident, "Tambahan revisi", actor="pelanggan-uji")
        self.store.request_revision(self.ident, "Perbaiki salah ketik penyedia", actor="operator-uji", correction=True)
        order = self.store.get(self.ident)
        self.assertEqual(order.revisions_used, 1)
        self.assertEqual(order.stage, "working")
        self.assertEqual(order.preview_reference, "")
        self.assertEqual(order.total, 60000)

    def test_manual_review_cannot_be_silently_skipped(self):
        quote = make_quote(QuoteRequest(rush=True))
        with self.assertRaises(ValueError):
            self.store.create_order(quote, approved_by="operator-uji")
        order = self.store.create_order(quote, approved_by="operator-uji", manual_review_confirmed=True)
        self.assertEqual(order.total, 78000)

    def test_quote_snapshot_is_not_changed_by_future_prices(self):
        cfg = load_config()
        cfg["packages"]["standar"]["price"] = 70000
        cfg["payment"]["deposit_percent"] = 50
        new = make_quote(QuoteRequest(), cfg)
        self.assertEqual(new.required_before_work, 35000)
        old = self.store.get(self.ident)
        self.assertEqual((old.total, old.required_before_work), (60000, 18000))

    def test_malformed_quote_total_rejected(self):
        with self.assertRaises(ValueError):
            self.store.create_order(replace(self.quote, total=1), approved_by="operator-uji")

    def test_failed_action_rolls_back_stage_and_event(self):
        self.paid_initial()
        before = self.store.events(self.ident)
        with self.assertRaises(ValueError):
            self.store.start_work(self.ident, actor=" ")
        self.assertEqual(self.store.get(self.ident).stage, "accepted")
        self.assertEqual(self.store.events(self.ident), before)

    def test_cancellation_and_late_payment_require_operator(self):
        self.accepted()
        self.store.simulate_payment(self.ident, "pending-1", 18000, status="pending")
        self.store.cancel_unpaid(self.ident, "Pelanggan membatalkan", actor="operator-uji")
        with self.assertRaises(ValueError):
            self.store.simulate_payment(self.ident, "pending-1", 18000)
        self.assertEqual(self.store.get(self.ident).status, "cancelled")

    def test_paid_order_cannot_be_cancelled_as_if_no_money_received(self):
        self.paid_initial()
        with self.assertRaises(ValueError):
            self.store.cancel_unpaid(self.ident, "Batal", actor="operator-uji")
        self.assertEqual(self.store.get(self.ident).paid, 18000)


class PersistenceTests(unittest.TestCase):
    def test_restart_preserves_payment_deduplication(self):
        with tempfile.TemporaryDirectory(prefix="billing test ") as tmp:
            path = Path(tmp) / "demo.sqlite3"
            store = DemoStore(path)
            ident = store.create_order(make_quote(QuoteRequest()), approved_by="operator-uji").order_id
            store.accept_quote(ident, actor="pelanggan-uji")
            store.simulate_payment(ident, "repeat", 18000)
            store.close()
            store = DemoStore(path)
            try:
                order = store.simulate_payment(ident, "repeat", 18000)
                self.assertEqual(order.paid, 18000)
                self.assertEqual(len(store.list_orders()), 1)
            finally:
                store.close()

    def test_existing_foreign_database_is_rejected_without_modification(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "assistant.db"
            db = sqlite3.connect(path)
            db.execute("CREATE TABLE important_data (value TEXT)")
            db.commit()
            db.close()
            original = path.read_bytes()
            with self.assertRaises(ValueError):
                DemoStore(path)
            self.assertEqual(path.read_bytes(), original)

    def test_parallel_duplicate_notifications_credit_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo.sqlite3"
            store = DemoStore(path)
            ident = store.create_order(make_quote(QuoteRequest()), approved_by="operator-uji").order_id
            store.accept_quote(ident, actor="pelanggan-uji")
            store.close()

            def notify(_):
                worker = DemoStore(path)
                try:
                    return worker.simulate_payment(ident, "same-event", 18000).paid
                finally:
                    worker.close()

            with ThreadPoolExecutor(max_workers=2) as pool:
                self.assertEqual(list(pool.map(notify, range(2))), [18000, 18000])

    def test_parallel_owner_confirmation_emits_one_work_ready_signal(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo.sqlite3"
            store = DemoStore(path)
            ident = store.create_order(make_quote(QuoteRequest()), approved_by="operator-uji").order_id
            store.accept_quote(ident, actor="pelanggan-uji")
            store.close()

            def confirm(_):
                worker = DemoStore(path)
                try:
                    admin = DemoTelegramAdmin(worker, admin_user_id=42, admin_chat_id=42)
                    reply = admin.handle(f"/dp_konfirmasi {ident} 18000 SAME", user_id=42, chat_id=42)
                    return reply.ready_order_id
                finally:
                    worker.close()

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(confirm, range(2)))
            self.assertEqual(results.count(ident), 1)
            self.assertEqual(results.count(None), 1)


class TelegramAdminTests(unittest.TestCase):
    def setUp(self):
        self.store = DemoStore()
        self.admin = DemoTelegramAdmin(self.store, admin_user_id=42, admin_chat_id=42)
        self.order = self.store.create_order(make_quote(QuoteRequest()), approved_by="operator-uji")
        self.ident = self.order.order_id
        self.store.accept_quote(self.ident, actor="pelanggan-uji")

    def tearDown(self):
        self.store.close()

    def say(self, text):
        return self.admin.handle(text, user_id=42, chat_id=42)

    def test_only_configured_owner_in_private_chat_can_see_or_confirm(self):
        for identity in [dict(user_id=99, chat_id=42), dict(user_id=42, chat_id=99),
                         dict(user_id=42, chat_id=42, chat_type="group"),
                         dict(user_id=True, chat_id=42)]:
            with self.subTest(identity=identity):
                self.assertIsNone(self.admin.handle("/dp", **identity))
                self.assertIsNone(self.admin.handle(f"/dp_konfirmasi {self.ident} 18000 DP", **identity))
        self.assertEqual(self.store.get(self.ident).paid, 0)

    def test_owner_can_check_dp_from_telegram_text(self):
        reply = self.say(f"/dp {self.ident}")
        self.assertIn("Rp18.000", reply.text)
        self.assertIn("belum terpenuhi", reply.text)
        self.assertIn(self.ident, self.say("/dp").text)

    def test_manual_confirmation_is_audited_and_ready_once(self):
        command = f"/dp_konfirmasi {self.ident} 18000 QR-001"
        reply = self.say(command)
        self.assertEqual(reply.ready_order_id, self.ident)
        self.assertIn("Siap diteruskan ke Nara", reply.text)
        self.assertIsNone(self.say(command).ready_order_id)
        self.assertEqual(self.store.get(self.ident).paid, 18000)
        self.assertIn("telegram-owner:42", " ".join(e["detail"] for e in self.store.events(self.ident)))
        self.assertNotIn(self.ident, self.say("/dp").text)

    def test_small_partial_confirmation_does_not_unlock_work(self):
        reply = self.say(f"/dp_konfirmasi {self.ident} 1000 QR-001")
        self.assertIsNone(reply.ready_order_id)
        self.assertIn("belum terpenuhi", reply.text)
        self.assertFalse(self.store.get(self.ident).can_start)

    def test_midtrans_demo_pending_then_settlement(self):
        first = self.say(f"/simulasi_midtrans {self.ident} 18000 MT-001 pending")
        self.assertIsNone(first.ready_order_id)
        self.assertEqual(self.store.get(self.ident).paid, 0)
        settled = self.say(f"/simulasi_midtrans {self.ident} 18000 MT-001 settlement")
        self.assertEqual(settled.ready_order_id, self.ident)
        self.assertEqual(self.store.get(self.ident).paid, 18000)

    def test_final_confirmation_does_not_force_unpaid_balance_to_zero(self):
        self.say(f"/dp_konfirmasi {self.ident} 18000 QR-001")
        reply = self.say(f"/lunas_konfirmasi {self.ident} 10000 QR-002")
        self.assertIn("Rp32.000", reply.text)
        self.assertEqual(self.store.get(self.ident).remaining, 32000)
        reply = self.say(f"/lunas_konfirmasi {self.ident} 32000 QR-003")
        self.assertEqual(self.store.get(self.ident).remaining, 0)
        self.assertFalse(self.store.get(self.ident).can_deliver)  # belum review pratinjau

    def test_bad_command_is_replied_to_without_changing_money(self):
        for command in [f"/dp_konfirmasi {self.ident} 18.000 QR", "/dp_konfirmasi", "/dp invalid", "/dp x y"]:
            with self.subTest(command=command):
                self.assertTrue(self.say(command).text.startswith("Tidak diproses:"))
        self.assertEqual(self.store.get(self.ident).paid, 0)

    def test_unrelated_commands_fall_through_to_original_router(self):
        self.assertIsNone(self.say("/saldo"))
        self.assertIsNone(self.say("Buat makalah tentang komputer"))

    def test_payment_notice_only_formats_state(self):
        before = self.store.events(self.ident)
        message = self.admin.payment_notice(self.ident)
        self.assertIn("Pembaruan pembayaran", message.text)
        self.assertEqual(self.store.events(self.ident), before)

    def test_invalid_admin_configuration_rejected(self):
        for value in [0, -42, True, "42"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                DemoTelegramAdmin(self.store, admin_user_id=value, admin_chat_id=42)


class DemoCommandTests(unittest.TestCase):
    def test_sample_runs_from_unrelated_working_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.run([sys.executable, "-B", str(ROOT / "demo.py"), "--sample"],
                                       cwd=tmp, capture_output=True, text=True, encoding="utf-8", timeout=15)
        self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
        self.assertIn("Rp18.000", completed.stdout)
        self.assertIn("Rp42.000", completed.stdout)
        self.assertIn("Selesai", completed.stdout)
        self.assertIn("Tidak ada uang", completed.stdout)

    def test_telegram_demo_can_check_dp_without_real_telegram(self):
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / "di kerjakan oleh Chatgpt"
            shutil.copytree(ROOT, copied, ignore=shutil.ignore_patterns("runtime", "__pycache__", ".pytest_cache"))
            completed = subprocess.run([sys.executable, "-B", str(copied / "demo.py"), "--telegram-demo"],
                                       input="/dp\n0\n", cwd=tmp, capture_output=True, text=True,
                                       encoding="utf-8", timeout=15)
        self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
        self.assertIn("Bot demo: [SIMULASI] Menunggu pembayaran awal:", completed.stdout)
        self.assertIn("Rp18.000", completed.stdout)


if __name__ == "__main__":
    unittest.main()
