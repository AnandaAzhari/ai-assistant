"""Batas pembayaran, pemulihan, hasil file, dan adapter; tanpa API/jaringan."""
from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from chatgpt_billing.artifacts import ArtifactSet, check_docx, inspect_artifacts
from chatgpt_billing.payment_flow import DemoStore
from chatgpt_billing.pricing import QuoteRequest, make_quote
from chatgpt_billing.telegram_admin import DemoTelegramAdmin, payment_summary
from chatgpt_billing.workflow import Brief, WorkflowStore
from chatgpt_billing.workers import OfflineDemoWorker, PreparedNaraWorker


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='antrean dengan spasi ')
        self.base = Path(self.temp.name)
        self.path, self.root = self.base / 'demo.sqlite3', self.base / 'files'
        self.now = 1000.0
        self.store = self.open()

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def open(self):
        return WorkflowStore(self.path, self.root, clock=lambda: self.now, lease_seconds=10)

    def new(self, *, accept=True, brief=True):
        order = self.store.create_order(make_quote(QuoteRequest()), approved_by='tester')
        if accept:
            self.store.accept_quote(order.order_id, actor='customer')
        if brief:
            self.store.register_brief(order.order_id, Brief('Uji dokumen'), actor='customer')
        return order.order_id

    def ready(self):
        order = self.new()
        self.store.simulate_payment(order, 'dp-' + order, 18000)
        return order

    def review(self):
        order = self.ready()
        self.assertEqual(self.store.run_next(OfflineDemoWorker())['state'], 'review')
        return order

    def approve(self, order):
        manifest = json.loads(self.store.job(order)['manifest_json'])
        self.store.approve_result(order, preview_sha256=manifest['files']['preview_pdf']['sha256'], actor='customer')

    def settle(self, order):
        self.store.simulate_payment(order, 'balance-' + order, 42000)

    def test_pending_partial_and_threshold(self):
        order = self.new()
        self.store.simulate_payment(order, 'pending', 18000, status='pending')
        self.assertIsNone(self.store.claim_next())
        self.store.simulate_payment(order, 'partial', 17000)
        self.assertIsNone(self.store.claim_next())
        self.store.simulate_payment(order, 'last', 1000)
        self.assertEqual(self.store.job(order)['state'], 'queued')
        self.assertIsNotNone(self.store.claim_next())

    def test_payment_before_price_agreement_rejected(self):
        order = self.new(accept=False)
        with self.assertRaises(ValueError):
            self.store.simulate_payment(order, 'early', 18000)
        self.assertEqual(self.store.job(order)['state'], 'waiting')

    def test_brief_needed_and_can_be_added_after_old_payment(self):
        order = self.new(brief=False)
        self.store.simulate_payment(order, 'old-dp', 18000)
        self.assertIsNone(self.store.claim_next())
        self.store.register_brief(order, Brief('Ditambahkan setelah DP'), actor='owner')
        self.assertEqual(self.store.claim_next().order_id, order)

    def test_brief_immutable_and_duplicate_registration_idempotent(self):
        order = self.new()
        self.store.register_brief(order, Brief('Uji dokumen'), actor='owner')
        with self.assertRaises(ValueError):
            self.store.register_brief(order, Brief('Judul diubah'), actor='owner')
        self.assertEqual(len(self.store.jobs()), 1)

    def test_payment_and_enqueue_rollback_together(self):
        order = self.new()
        original = self.store._event

        def fail_enqueue(order_id, action, detail):
            if action == 'job_enqueued':
                raise RuntimeError('Simulasi penyimpanan gagal')
            original(order_id, action, detail)

        with patch.object(self.store, '_event', side_effect=fail_enqueue):
            with self.assertRaises(RuntimeError):
                self.store.simulate_payment(order, 'dp', 18000)
        self.assertEqual(self.store.get(order).paid, 0)
        self.assertEqual(self.store.job(order)['state'], 'waiting')

    def test_parallel_duplicate_payment_creates_one_job_event(self):
        order = self.new()

        def pay(_):
            with_store = self.open()
            try:
                return with_store.simulate_payment_update(order, 'same', 18000).credited_amount
            finally:
                with_store.close()

        with ThreadPoolExecutor(max_workers=4) as pool:
            self.assertEqual(sum(pool.map(pay, range(4))), 18000)
        self.assertEqual(sum(e['action'] == 'job_enqueued' for e in self.store.events(order)), 1)

    def test_parallel_workers_claim_once(self):
        order = self.ready()

        def claim(_):
            other = self.open()
            try:
                return other.claim_next()
            finally:
                other.close()

        with ThreadPoolExecutor(max_workers=4) as pool:
            claims = list(pool.map(claim, range(4)))
        self.assertEqual(sum(x is not None for x in claims), 1)
        self.assertEqual(self.store.job(order)['attempts'], 1)

    def test_fifo(self):
        first, second = self.ready(), self.ready()
        self.assertEqual(self.store.claim_next().order_id, first)
        self.assertEqual(self.store.claim_next().order_id, second)

    def test_restart_keeps_queue_and_completed_files(self):
        order = self.ready()
        self.store.close()
        self.store = self.open()
        self.assertEqual(self.store.job(order)['state'], 'queued')
        self.store.run_next(OfflineDemoWorker())
        preview = self.store.preview(order)
        self.store.close()
        self.store = self.open()
        self.assertEqual(self.store.preview(order), preview)
        self.assertTrue(preview.is_file())

    def test_expired_worker_cannot_overwrite_retry(self):
        order = self.ready()
        old = self.store.claim_next()
        self.now += 11
        self.assertEqual(self.store.recover_expired(), 1)
        self.store.retry(order, actor='owner')
        new = self.store.claim_next()
        old.output_dir.mkdir(parents=True)
        artifacts = OfflineDemoWorker().produce(old)
        with self.assertRaises(ValueError):
            self.store.complete(old, artifacts)
        self.store.fail(old, 'old failure')
        self.assertEqual(self.store.job(order)['run_token'], new.token)
        self.assertEqual(self.store.job(order)['state'], 'running')

    def test_live_worker_not_recovered_and_heartbeat_extends_lease(self):
        self.ready()
        item = self.store.claim_next()
        self.now += 9
        self.store.heartbeat(item)
        self.now += 2
        self.assertEqual(self.store.recover_expired(), 0)
        self.now += 9
        self.assertEqual(self.store.recover_expired(), 1)

    def test_two_failure_attempt_limit(self):
        order = self.ready()

        class Broken:
            def produce(self, item):
                raise OSError('Konverter gagal')

        self.assertEqual(self.store.run_next(Broken())['state'], 'blocked')
        self.store.retry(order, actor='owner')
        self.assertEqual(self.store.run_next(Broken())['state'], 'blocked')
        with self.assertRaises(ValueError):
            self.store.retry(order, actor='owner')

    def test_full_flow_and_idempotent_local_release(self):
        order = self.review()
        with self.assertRaises(ValueError):
            self.store.release_result(order, actor='owner')
        self.approve(order)
        with self.assertRaises(ValueError):
            self.store.release_result(order, actor='owner')
        self.settle(order)
        result = self.store.release_result(order, actor='owner')
        self.assertTrue((result / 'hasil.docx').is_file())
        self.assertTrue((result / 'hasil.pdf').is_file())
        self.assertTrue((result / 'BUKTI_PENYERAHAN.json').is_file())
        self.assertEqual(self.store.get(order).status, 'delivered')
        self.assertEqual(result, self.store.release_result(order, actor='owner'))

    def test_full_payment_still_needs_preview_approval(self):
        order = self.review()
        self.settle(order)
        with self.assertRaises(ValueError):
            self.store.release_result(order, actor='owner')
        self.assertFalse((self.root / 'released').exists())

    def test_old_preview_hash_rejected(self):
        order = self.review()
        with self.assertRaises(ValueError):
            self.store.approve_result(order, preview_sha256='old-version', actor='customer')
        self.assertEqual(self.store.job(order)['state'], 'review')

    def test_modified_final_file_after_approval_blocks_delivery(self):
        order = self.review()
        self.approve(order)
        self.settle(order)
        manifest = json.loads(self.store.job(order)['manifest_json'])
        (self.root / manifest['files']['docx']['path']).write_bytes(b'changed')
        with self.assertRaises(ValueError):
            self.store.release_result(order, actor='owner')
        self.assertEqual(self.store.get(order).stage, 'approved')
        self.assertFalse((self.root / 'released').exists())

    def test_missing_preview_blocks_approval(self):
        order = self.review()
        self.store.preview(order).unlink()
        with self.assertRaises(ValueError):
            self.approve(order)

    def test_bad_pdf_blocks_job(self):
        self.ready()

        class BadPDF(OfflineDemoWorker):
            def produce(self, item):
                result = super().produce(item)
                result.final_pdf.write_text('not PDF')
                return result

        result = self.store.run_next(BadPDF())
        self.assertEqual(result['state'], 'blocked')
        self.assertEqual(self.store.get(result['order_id']).stage, 'working')

    def test_same_preview_and_final_rejected(self):
        self.ready()

        class SamePDF(OfflineDemoWorker):
            def produce(self, item):
                result = super().produce(item)
                result.preview_pdf.write_bytes(result.final_pdf.read_bytes())
                return result

        self.assertEqual(self.store.run_next(SamePDF())['state'], 'blocked')

    def test_artifact_from_another_order_rejected(self):
        first, second = self.ready(), self.ready()
        a, b = self.store.claim_next(), self.store.claim_next()
        a.output_dir.mkdir(parents=True)
        result = OfflineDemoWorker().produce(a)
        with self.assertRaises(ValueError):
            self.store.complete(b, result)
        self.assertEqual(self.store.job(second)['state'], 'running')

    def test_symlink_escape_rejected(self):
        self.ready()
        item = self.store.claim_next()
        item.output_dir.mkdir(parents=True)
        result = OfflineDemoWorker().produce(item)
        outside = self.base / 'outside.pdf'
        outside.write_bytes(result.final_pdf.read_bytes())
        result.final_pdf.unlink()
        try:
            result.final_pdf.symlink_to(outside)
        except OSError:
            self.skipTest('Pembuatan symlink tidak diizinkan OS ini')
        with self.assertRaises(ValueError):
            self.store.complete(item, result)

    def test_old_menu_cannot_bypass_managed_job(self):
        order = self.review()
        other = DemoStore(self.path)
        try:
            with self.assertRaises(ValueError):
                other.approve_preview(order, actor='old-menu')
            with self.assertRaises(ValueError):
                other.request_revision(order, 'rework', actor='old-menu')
            with self.assertRaises(ValueError):
                other.release_final(order, 'fake.docx', actor='old-menu')
        finally:
            other.close()

    def test_old_telegram_payment_controller_enqueues(self):
        order = self.new()
        other = DemoStore(self.path)
        try:
            admin = DemoTelegramAdmin(other, admin_user_id=1, admin_chat_id=1)
            reply = admin.handle(f'/dp_konfirmasi {order} 18000 REF1', user_id=1, chat_id=1)
            self.assertEqual(reply.ready_order_id, order)
        finally:
            other.close()
        self.assertEqual(self.store.job(order)['state'], 'queued')

    def test_foreign_database_and_artifact_directory_untouched(self):
        foreign = self.base / 'shop.sqlite3'
        with sqlite3.connect(foreign) as db:
            db.execute('CREATE TABLE orders (id TEXT)')
        before = foreign.read_bytes()
        with self.assertRaises(ValueError):
            WorkflowStore(foreign, self.base / 'foreign-root')
        self.assertEqual(before, foreign.read_bytes())
        self.assertFalse((self.base / 'foreign-root').exists())
        path = self.base / 'existing'
        path.mkdir()
        (path / 'keep.txt').write_text('do not touch')
        with self.assertRaises(ValueError):
            WorkflowStore(self.path, path)
        self.assertEqual((path / 'keep.txt').read_text(), 'do not touch')

    def test_release_retry_after_copy_before_database_commit(self):
        order = self.review()
        self.approve(order)
        self.settle(order)
        original = self.store._set_stage

        def crash(order_id, stage, action, actor):
            if stage == 'delivered':
                raise RuntimeError('Crash setelah salin file, sebelum commit')
            original(order_id, stage, action, actor)

        with patch.object(self.store, '_set_stage', side_effect=crash):
            with self.assertRaises(RuntimeError):
                self.store.release_result(order, actor='owner')
        self.assertEqual(self.store.job(order)['state'], 'approved')
        result = self.store.release_result(order, actor='owner')
        self.assertTrue((result / 'hasil.docx').is_file())

    def test_modified_released_copy_rejected_on_repeat(self):
        order = self.review()
        self.approve(order)
        self.settle(order)
        destination = self.store.release_result(order, actor='owner')
        (destination / 'hasil.pdf').write_text('changed')
        with self.assertRaises(ValueError):
            self.store.release_result(order, actor='owner')

    def test_prepared_nara_adapter_uses_build_final_and_preview_builder(self):
        order = self.ready()

        def factory(item):
            artifacts = OfflineDemoWorker().produce(item)
            return SimpleNamespace(phase='draft_ready', final_docx_path=str(artifacts.docx),
                                   final_pdf_path=str(artifacts.final_pdf),
                                   build_final=lambda: SimpleNamespace(status='final_ready'))

        def preview_builder(source, destination):
            self.assertTrue(source.is_file())
            self.assertTrue(destination.is_file())  # Fixture sudah memiliki watermark.

        result = self.store.run_next(PreparedNaraWorker(factory, preview_builder))
        self.assertEqual(result['state'], 'review')
        self.assertEqual(self.store.get(order).stage, 'preview')

    def test_nara_unapproved_draft_blocks_without_build(self):
        self.ready()

        def build():
            self.fail('build_final tidak boleh dipanggil sebelum draft siap')

        worker = PreparedNaraWorker(lambda item: SimpleNamespace(phase='collecting', build_final=build),
                                    lambda a, b: None)
        self.assertEqual(self.store.run_next(worker)['state'], 'blocked')

    def test_nara_without_pdf_blocks(self):
        self.ready()
        worker = PreparedNaraWorker(lambda item: SimpleNamespace(
            phase='final_ready', build_final=lambda: SimpleNamespace(status='final_ready'),
            final_docx_path='', final_pdf_path=''), lambda a, b: None)
        self.assertEqual(self.store.run_next(worker)['state'], 'blocked')

    def test_payment_display_distinguishes_paid_from_work_status(self):
        order = self.ready()
        self.settle(order)
        text = payment_summary(self.store.get(order))
        self.assertIn('Status pembayaran: Lunas', text)
        self.assertIn('Status: Siap dikerjakan', text)

    def test_docx_fixture_has_real_footnote_reference(self):
        order = self.review()
        manifest = json.loads(self.store.job(order)['manifest_json'])
        result = check_docx(self.root / manifest['files']['docx']['path'])
        self.assertEqual(result['footnotes_referenced'], 1)


class WorkflowCLITests(unittest.TestCase):
    def test_sample_runs_from_unrelated_directory_without_touching_other_runtime(self):
        source = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix='uji folder spasi ') as tmp:
            copied = Path(tmp) / 'di_kerjakan_oleh_chatgpt'
            shutil.copytree(source, copied, ignore=shutil.ignore_patterns('runtime', '__pycache__'))
            runtime = copied / 'runtime'
            runtime.mkdir()
            (runtime / 'demo.sqlite3').write_text('not a demo database - must stay untouched')
            result = subprocess.run([sys.executable, '-B', str(copied / 'workflow_demo.py'), '--sample'],
                                    cwd=tmp, capture_output=True, text=True, encoding='utf-8', timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('ALUR SELESAI', result.stdout)
            self.assertEqual((runtime / 'demo.sqlite3').read_text(), 'not a demo database - must stay untouched')
            self.assertEqual(len(list((runtime / 'samples').rglob('BUKTI_PENYERAHAN.json'))), 1)


if __name__ == '__main__':
    unittest.main()
