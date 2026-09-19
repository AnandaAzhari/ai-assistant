import tempfile
import unittest
from pathlib import Path

from app.approval_gate import (
    LEVEL_CONTROLLED_WRITE,
    LEVEL_EXTERNAL_ACTION,
    LEVEL_HIGH_RISK,
    LEVEL_LOW_RISK,
    LEVEL_READ_ONLY,
    ApprovalGate,
)


class ApprovalGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "assistant.db"
        self.gate = ApprovalGate(self.db)

    # --- Level 0-2: selalu jalan otomatis ---

    def test_read_only_action_runs_automatically(self):
        decision = self.gate.request("baca_status_sistem", requested_by="lead_agent")
        self.assertEqual(decision.level, LEVEL_READ_ONLY)
        self.assertEqual(decision.status, "auto_jalan")

    def test_low_risk_and_controlled_write_run_automatically(self):
        low_risk = self.gate.request("buka_folder", requested_by="desktop_agent")
        controlled_write = self.gate.request("buat_dokumen_kerja", requested_by="document_agent")
        self.assertEqual(low_risk.level, LEVEL_LOW_RISK)
        self.assertEqual(low_risk.status, "auto_jalan")
        self.assertEqual(controlled_write.level, LEVEL_CONTROLLED_WRITE)
        self.assertEqual(controlled_write.status, "auto_jalan")

    # --- Level 3: rutin auto-send, di luar itu wajib approval ---

    def test_customer_document_session_action_is_controlled_write_and_auto_runs(self):
        # Mulai/lanjutkan sesi pembuatan dokumen pelanggan (app/lead.py
        # `_continue_customer_document`) adalah Level 2, bukan Level 3 — jadi tidak
        # pernah menunggu approval admin per giliran percakapan (lihat
        # policies/permissions.md Level 2).
        decision = self.gate.request("buat_dokumen_pelanggan", requested_by="customer:628111")
        self.assertEqual(decision.level, LEVEL_CONTROLLED_WRITE)
        self.assertEqual(decision.status, "auto_jalan")

    def test_routine_level3_business_workflow_runs_automatically(self):
        decision = self.gate.request("kirim_status_antrean", requested_by="social_media_agent")
        self.assertEqual(decision.level, LEVEL_EXTERNAL_ACTION)
        self.assertEqual(decision.status, "auto_jalan")

    def test_off_topic_redirect_runs_automatically(self):
        # Topic restriction (app/lead.py "di_luar_topik") hanya balasan pengalihan sopan,
        # bukan aksi berisiko — jadi tetap auto-send rutin seperti jawab_faq/kirim_salam.
        decision = self.gate.request("di_luar_topik", requested_by="customer:628111")
        self.assertEqual(decision.level, LEVEL_EXTERNAL_ACTION)
        self.assertEqual(decision.status, "auto_jalan")

    def test_non_routine_level3_action_requires_approval(self):
        decision = self.gate.request(
            "diskon_khusus", requested_by="finance_agent",
            summary="Pelanggan minta diskon 20% di luar price list.",
        )
        self.assertEqual(decision.level, LEVEL_EXTERNAL_ACTION)
        self.assertEqual(decision.status, "pending_approval")

    # --- Level 4: selalu wajib approval ---

    def test_high_risk_action_always_requires_approval(self):
        decision = self.gate.request("transaksi_keuangan", requested_by="finance_agent")
        self.assertEqual(decision.level, LEVEL_HIGH_RISK)
        self.assertEqual(decision.status, "pending_approval")

    # --- Fail-safe untuk action_type yang tidak dikenal ---

    def test_unknown_action_defaults_to_pending_not_auto(self):
        decision = self.gate.request("aksi_baru_yang_belum_terdaftar", requested_by="lead_agent")
        self.assertEqual(decision.level, LEVEL_EXTERNAL_ACTION)
        self.assertEqual(decision.status, "pending_approval")

    def test_unknown_action_with_high_risk_keyword_escalates_to_level4(self):
        decision = self.gate.request("hapus_folder_pesanan_lama", requested_by="desktop_agent")
        self.assertEqual(decision.level, LEVEL_HIGH_RISK)
        self.assertEqual(decision.status, "pending_approval")

    # --- State machine: pending -> approved / rejected ---

    def test_pending_request_can_be_approved(self):
        pending = self.gate.request("transaksi_keuangan", requested_by="finance_agent")
        decided = self.gate.approve(pending.request_id, decided_by="owner")
        self.assertEqual(decided.status, "approved")
        stored = self.gate.get(pending.request_id)
        self.assertEqual(stored["status"], "approved")
        self.assertEqual(stored["decided_by"], "owner")
        self.assertNotEqual(stored["decided_at"], "")

    def test_pending_request_can_be_rejected_with_reason(self):
        pending = self.gate.request("diskon_khusus", requested_by="finance_agent")
        decided = self.gate.reject(pending.request_id, decided_by="owner", reason="Belum ada budget promo.")
        self.assertEqual(decided.status, "rejected")
        stored = self.gate.get(pending.request_id)
        self.assertEqual(stored["reason"], "Belum ada budget promo.")

    def test_decided_request_cannot_be_decided_again(self):
        pending = self.gate.request("transaksi_keuangan", requested_by="finance_agent")
        self.gate.approve(pending.request_id, decided_by="owner")
        with self.assertRaises(ValueError):
            self.gate.approve(pending.request_id, decided_by="owner")
        with self.assertRaises(ValueError):
            self.gate.reject(pending.request_id, decided_by="owner")

    def test_auto_jalan_request_cannot_be_approved_again(self):
        auto = self.gate.request("baca_status_sistem", requested_by="lead_agent")
        with self.assertRaises(ValueError):
            self.gate.approve(auto.request_id, decided_by="owner")

    def test_deciding_unknown_request_id_raises(self):
        with self.assertRaises(ValueError):
            self.gate.approve("id-tidak-ada", decided_by="owner")

    # --- Antrean & notifikasi untuk Telegram Admin ---

    def test_pending_for_admin_lists_only_pending_oldest_first(self):
        first = self.gate.request("transaksi_keuangan", requested_by="finance_agent")
        self.gate.request("baca_status_sistem", requested_by="lead_agent")  # auto, tidak masuk antrean
        second = self.gate.request("diskon_khusus", requested_by="finance_agent")
        queue = self.gate.pending_for_admin()
        self.assertEqual([row["id"] for row in queue], [first.request_id, second.request_id])

    def test_notification_text_contains_action_and_reply_commands(self):
        pending = self.gate.request(
            "transaksi_keuangan", requested_by="finance_agent",
            summary="Top up saldo DANA 300 ribu.",
        )
        text = self.gate.notification_text(pending.request_id)
        self.assertIn("transaksi_keuangan", text)
        self.assertIn("Top up saldo DANA 300 ribu.", text)
        self.assertIn(f"/approve {pending.request_id}", text)
        self.assertIn(f"/reject {pending.request_id}", text)

    def test_empty_action_type_or_requester_is_rejected(self):
        with self.assertRaises(ValueError):
            self.gate.request("", requested_by="lead_agent")
        with self.assertRaises(ValueError):
            self.gate.request("baca_status_sistem", requested_by="")


if __name__ == "__main__":
    unittest.main()
