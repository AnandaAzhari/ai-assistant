import tempfile
import unittest
from pathlib import Path

from app.kill_switch import CUSTOMER_NOTICE_TEXT, GLOBAL_SCOPE, KillSwitch
from app.lead import LeadAgent


class KillSwitchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "assistant.db"
        self.gate = KillSwitch(self.db)

    def test_default_state_is_inactive(self):
        self.assertFalse(self.gate.is_active())
        self.assertFalse(self.gate.is_active("whatsapp"))
        state = self.gate.status("whatsapp")
        self.assertFalse(state.active)

    def test_activating_global_scope_affects_every_scope(self):
        self.gate.activate(reason="serangan spam masif", changed_by="admin:telegram")
        self.assertTrue(self.gate.is_active(GLOBAL_SCOPE))
        self.assertTrue(self.gate.is_active("whatsapp"))
        self.assertTrue(self.gate.is_active("channel_apa_pun_yang_belum_dikenal"))

    def test_activating_named_scope_only_affects_that_scope(self):
        self.gate.activate(scope="whatsapp", reason="uji", changed_by="admin:telegram")
        self.assertTrue(self.gate.is_active("whatsapp"))
        self.assertFalse(self.gate.is_active(GLOBAL_SCOPE))
        self.assertFalse(self.gate.is_active("web_customer"))

    def test_deactivate_restores_normal_processing(self):
        self.gate.activate(scope="whatsapp", changed_by="admin:telegram")
        self.gate.deactivate(scope="whatsapp", changed_by="admin:telegram")
        self.assertFalse(self.gate.is_active("whatsapp"))

    def test_changed_by_is_required(self):
        with self.assertRaises(ValueError):
            self.gate.activate(changed_by="")

    def test_history_is_append_only_and_never_overwritten(self):
        self.gate.activate(scope="whatsapp", reason="tes 1", changed_by="admin:telegram")
        self.gate.deactivate(scope="whatsapp", reason="tes 2", changed_by="admin:telegram")
        self.gate.activate(scope="whatsapp", reason="tes 3", changed_by="admin:telegram")
        events = self.gate.history(scope="whatsapp")
        self.assertEqual(len(events), 3)
        self.assertEqual(events[0]["reason"], "tes 3")  # terbaru dulu

    def test_status_reflects_most_recent_change(self):
        self.gate.activate(scope="whatsapp", reason="A", changed_by="admin:telegram")
        self.gate.activate(scope="whatsapp", reason="B", changed_by="admin:web")
        state = self.gate.status("whatsapp")
        self.assertTrue(state.active)
        self.assertEqual(state.reason, "B")
        self.assertEqual(state.changed_by, "admin:web")


class LeadAgentKillSwitchAdminCommandTests(unittest.TestCase):
    """Command Telegram/Web Admin (app/lead.py handle_admin_message) untuk mengatur
    KillSwitch — dikirim admin lewat `/matikan_otomatis`, `/nyalakan_otomatis`,
    `/status_otomatis`, dirutekan lewat runtime yang sama seperti /status, /sync, dst."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "assistant.db"
        self.kill_switch = KillSwitch(self.db)
        self.lead = LeadAgent(admin_channel="telegram", kill_switch=self.kill_switch)

    def test_without_kill_switch_configured_commands_report_unavailable(self):
        lead = LeadAgent(admin_channel="telegram")
        reply = lead.handle_admin_message("/matikan_otomatis alasan tes")
        self.assertEqual(reply.status, "belum_dikonfigurasi")

    def test_matikan_otomatis_without_scope_activates_global(self):
        reply = self.lead.handle_admin_message("/matikan_otomatis kena serangan spam masif")
        self.assertEqual(reply.status, "berhasil")
        self.assertIn("global", reply.text)
        self.assertTrue(self.kill_switch.is_active("whatsapp"))
        state = self.kill_switch.status(GLOBAL_SCOPE)
        self.assertEqual(state.reason, "kena serangan spam masif")
        self.assertEqual(state.changed_by, "admin:telegram")

    def test_matikan_otomatis_with_known_scope_only_affects_that_scope(self):
        reply = self.lead.handle_admin_message("/matikan_otomatis whatsapp maintenance server")
        self.assertEqual(reply.status, "berhasil")
        self.assertTrue(self.kill_switch.is_active("whatsapp"))
        self.assertFalse(self.kill_switch.is_active(GLOBAL_SCOPE))
        state = self.kill_switch.status("whatsapp")
        self.assertEqual(state.reason, "maintenance server")

    def test_nyalakan_otomatis_deactivates(self):
        self.lead.handle_admin_message("/matikan_otomatis whatsapp uji")
        reply = self.lead.handle_admin_message("/nyalakan_otomatis whatsapp")
        self.assertEqual(reply.status, "berhasil")
        self.assertFalse(self.kill_switch.is_active("whatsapp"))

    def test_status_otomatis_reports_all_known_scopes(self):
        self.lead.handle_admin_message("/matikan_otomatis whatsapp lagi maintenance")
        reply = self.lead.handle_admin_message("/status_otomatis")
        self.assertEqual(reply.status, "berhasil")
        self.assertIn("global: nonaktif", reply.text)
        self.assertIn("whatsapp: AKTIF", reply.text)
        self.assertIn("lagi maintenance", reply.text)


class HandleCustomerMessageKillSwitchTests(unittest.TestCase):
    """handle_customer_message() harus berhenti PALING AWAL saat kill switch aktif,
    sebelum Trust Layer disentuh sama sekali (lihat docstring app/kill_switch.py)."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "assistant.db"

    def _lead_with_kill_switch(self):
        from app.approval_gate import ApprovalGate
        from app.trust_layer import TrustLayer

        trust_layer = TrustLayer(self.db)
        approval_gate = ApprovalGate(self.db)
        kill_switch = KillSwitch(self.db)
        lead = LeadAgent(trust_layer=trust_layer, approval_gate=approval_gate, kill_switch=kill_switch)
        return lead, trust_layer, kill_switch

    def test_global_kill_switch_short_circuits_before_trust_layer(self):
        lead, trust_layer, kill_switch = self._lead_with_kill_switch()
        kill_switch.activate(reason="insiden keamanan", changed_by="admin:telegram")
        reply = lead.handle_customer_message("628111", "Halo kak, mau pesan cetak makalah")
        self.assertEqual(reply.target, "kill_switch")
        self.assertEqual(reply.status, "dimatikan_sementara")
        self.assertEqual(reply.text, CUSTOMER_NOTICE_TEXT)
        # Trust Layer sama sekali tidak dipanggil — tidak ada riwayat tercatat.
        self.assertEqual(trust_layer.history("628111"), [])

    def test_channel_scoped_kill_switch_only_blocks_that_channel(self):
        lead, trust_layer, kill_switch = self._lead_with_kill_switch()
        kill_switch.activate(scope="whatsapp", reason="uji", changed_by="admin:telegram")
        reply = lead.handle_customer_message("628222", "Halo kak", channel="whatsapp")
        self.assertEqual(reply.status, "dimatikan_sementara")
        # Channel lain yang tidak disebutkan scope-nya tetap diproses normal.
        reply_other = lead.handle_customer_message("628333", "Halo kak", channel="web_customer")
        self.assertNotEqual(reply_other.status, "dimatikan_sementara")

    def test_inactive_kill_switch_does_not_change_normal_behavior(self):
        lead, trust_layer, kill_switch = self._lead_with_kill_switch()
        reply = lead.handle_customer_message("628444", "Halo kak, mau pesan cetak makalah")
        self.assertNotEqual(reply.status, "dimatikan_sementara")


if __name__ == "__main__":
    unittest.main()
