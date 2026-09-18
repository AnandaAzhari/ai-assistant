"""Lead Agent routing minimum.

Desktop commands tetap dipertahankan. Pesan dari channel admin memakai router aturan
sederhana dulu; model Lead Agent belum dihubungkan pada tahap ini.

Jalur pelanggan (`handle_customer_message`, Fase 3 di
`docs/roadmap_customer_channel_v1.md`) sengaja terpisah total dari jalur admin
(`handle_admin_message`): setiap pesan pelanggan WAJIB melalui Security & Trust
Layer (`app/trust_layer.py`) dan Approval Gate (`app/approval_gate.py`) dulu
sebelum diproses lebih lanjut, konsisten dengan prinsip "Zero trust untuk input
pelanggan" di `policies/security_policy.md`. Intent pelanggan memakai router
aturan sederhana juga (kata kunci) untuk saat ini — sama seperti router admin —
sampai model AI benar-benar disambungkan pada iterasi berikutnya.
"""

import re
from dataclasses import dataclass

from app.approval_gate import ApprovalGate
from app.desktop import DesktopAgent, Result
from app.document_agent import DocumentAgent
from app.finance import FinanceService
from app.finance_corrections import correct_latest_account
from app.google_sheets_sync import GoogleSheetsSync
from app.interaction_policy import is_admin_command
from app.trust_layer import TrustLayer


@dataclass(frozen=True)
class LeadReply:
    target: str
    status: str
    text: str


class LeadAgent:
    def __init__(
        self,
        desktop: DesktopAgent | None = None,
        finance: FinanceService | None = None,
        sheets_sync: GoogleSheetsSync | None = None,
        document: DocumentAgent | None = None,
        admin_channel: str = "web",
        trust_layer: TrustLayer | None = None,
        approval_gate: ApprovalGate | None = None,
    ):
        self.desktop = desktop
        self.finance = finance
        self.sheets_sync = sheets_sync
        self.document = document
        self.admin_channel = admin_channel
        self.trust_layer = trust_layer
        self.approval_gate = approval_gate

    def dispatch(self, command: str, *, name: str = "", path: str = "") -> Result:
        command = command.strip().lower()
        if self.desktop is None:
            return Result("tidak_tersedia", ["Desktop Agent belum diaktifkan pada proses ini."])
        if command == "folder":
            return self.desktop.create_folder(name)
        if command == "buka":
            return self.desktop.open_file(path)
        if command == "pesanan":
            return self.desktop.prepare_order(name, path)
        return Result("membutuhkan_bantuan", ["Perintah belum dikenal. Ketik bantuan untuk melihat pilihan."])

    @staticmethod
    def _finance_write_succeeded(raw: str, result) -> bool:
        if result.status != "berhasil":
            return False
        text = raw.casefold()
        if "saldo awal" in text:
            return True
        return result.text.startswith((
            "Pemasukan tercatat.",
            "Pengeluaran tercatat.",
            "Koreksi transaksi berhasil.",
        ))

    @staticmethod
    def _topup_needs_source_account(text: str) -> bool:
        lowered = text.casefold()
        if not re.search(r"\b(?:top\s*up|transfer|kirim)\b", lowered):
            return False
        source_marker = r"\b(?:pakai|menggunakan|via|dari|bayar\s+pakai|dibayar\s+dengan)\b"
        return re.search(source_marker, lowered) is None

    def _document_session_active(self) -> bool:
        if self.document is None:
            return False
        session_active = getattr(self.document, "session_active", None)
        if isinstance(session_active, bool):
            return session_active
        requirements = getattr(self.document, "requirements", None)
        if requirements is None:
            return False
        labels = getattr(requirements, "FIELD_LABELS", {})
        return any(bool(getattr(requirements, key, "")) for key in labels)

    def _auto_sync_after_finance_write(self, raw: str, result) -> str:
        if not self._finance_write_succeeded(raw, result):
            return ""
        if self.sheets_sync is None or not self.sheets_sync.configured:
            return ""
        sync_result = self.sheets_sync.sync_now(timeout=8)
        if sync_result.status == "berhasil":
            return "\n\nGoogle Sheets: tersinkron otomatis."
        return (
            "\n\nGoogle Sheets: auto-sync belum berhasil. Data lokal tetap tersimpan. "
            "Gunakan /sync untuk mencoba lagi."
        )

    def handle_admin_message(self, message: str) -> LeadReply:
        raw = (message or "").strip()
        if not raw:
            return LeadReply("lead", "membutuhkan_bantuan", "Pesan kosong. Ketik /bantuan untuk melihat perintah awal.")

        text = raw.casefold()
        command = text.split(maxsplit=1)[0].split("@", 1)[0]

        if command in {"/start", "/bantuan", "/help"} or text in {"bantuan", "help"}:
            finance_note = "aktif" if self.finance is not None else "belum diaktifkan"
            sync_note = "siap + auto-sync" if self.sheets_sync and self.sheets_sync.configured else "belum dikonfigurasi"
            if self.document is None:
                document_note = "belum tersedia"
            elif self.document.configured:
                document_note = f"siap ({self.document.model_label})"
            else:
                document_note = "menunggu DeepSeek API key"
            engine_note = "siap" if self.document and self.document.engine_ready else "belum tersedia"
            return LeadReply(
                "lead",
                "berhasil",
                "AI Assistant aktif.\n\n"
                "Perintah tahap awal:\n"
                "/status - cek sistem\n"
                "/saldo - saldo ledger per akun\n"
                "/akun - akun dan saldo awal\n"
                "/kategori - kategori yang sudah dipelajari\n"
                "/hari_ini - ringkasan hari ini\n"
                "/bulan_ini - ringkasan bulan ini\n"
                "/sync_status - status Google Sheets Sync\n"
                "/sync - sinkronkan ledger ke Google Sheets secara manual\n"
                "/dokumen_status - cek Document Agent\n"
                "/dokumen_engine_status - cek mesin DOCX/PDF lokal\n"
                "/dokumen_demo - buat DOCX/PDF demo tanpa token AI\n"
                "/research <topik> - cari sumber akademik tanpa token AI\n"
                "/research_status - cek Research Manager\n"
                "/research_save all - simpan semua hasil research sebagai R1/R2/...\n"
                "/research_save 1,2,4-6 - simpan pilihan hasil research\n"
                "/sources - lihat Source Registry sesi saat ini\n"
                "/makalah <permintaan> - bicara dengan Document Agent\n"
                "/dokumen_baru - reset konteks percakapan dokumen\n"
                "Koreksi akun transaksi terakhir: `Koreksi transaksi terakhir, akun seharusnya BNI`.\n\n"
                f"Finance runtime: {finance_note}.\n"
                f"Google Sheets Sync: {sync_note}.\n"
                f"Document Agent: {document_note}.\n"
                f"Document Engine: {engine_note}."
            )

        if command == "/status" or text in {"status", "cek status", "health", "health check"}:
            finance_status = "aktif" if self.finance is not None else "belum diaktifkan"
            sync_status = "siap + auto-sync" if self.sheets_sync and self.sheets_sync.configured else "belum_dikonfigurasi"
            if self.document is None:
                document_status = "belum tersedia"
            elif self.document.configured:
                document_status = f"siap ({self.document.model_label})"
            else:
                document_status = "tersedia, menunggu API key"
            engine_status = "siap" if self.document and self.document.engine_ready else "belum tersedia"
            return LeadReply(
                "lead",
                "berhasil",
                "Lead Agent: aktif\n"
                + ("Telegram Admin: terhubung\n" if self.admin_channel == "telegram" else "Web Admin: terhubung\nTelegram: jalankan runtime terpisah untuk terhubung\n") +
                "Router Lead: aturan minimum\nLead AI model: belum dihubungkan\n"
                f"Document Agent: {document_status}\n"
                f"Document Engine: {engine_status}\n"
                f"Finance runtime: {finance_status}\nGoogle Sheets Sync: {sync_status}"
            )

        if command == "/dokumen_status":
            if self.document is None:
                return LeadReply("document", "belum_dikonfigurasi", "Document Agent belum tersedia pada runtime ini.")
            result = self.document.status()
            return LeadReply("document", result.status, result.text)

        document_utility_commands = {
            "/dokumen_engine_status", "/dokumen_demo",
            "/research_status", "/riset_status", "/research", "/riset",
            "/research_save", "/riset_simpan", "/sources", "/sumber",
        }
        if command in document_utility_commands:
            if self.document is None:
                return LeadReply("document", "belum_dikonfigurasi", "Document Agent belum tersedia pada runtime ini.")
            result = self.document.handle(raw)
            return LeadReply("document", result.status, result.text)

        if command in {"/dokumen_baru", "/makalah_baru"}:
            if self.document is None:
                return LeadReply("document", "belum_dikonfigurasi", "Document Agent belum tersedia pada runtime ini.")
            result = self.document.handle(raw)
            return LeadReply("document", result.status, result.text)

        document_commands = {"/makalah", "/dokumen", "/paper", "/laporan"}
        document_words = (
            "makalah", "karya tulis", "paper sekolah", "paper kuliah", "laporan sekolah",
            "laporan kuliah", "bab i", "bab 1", "bab ii", "bab 2", "daftar pustaka",
            "susun dokumen", "buat dokumen"
        )
        if command in document_commands or any(word in text for word in document_words):
            if self.document is None:
                return LeadReply("document", "belum_dikonfigurasi", "Document Agent belum tersedia pada runtime ini.")
            result = self.document.handle(raw)
            return LeadReply("document", result.status, result.text)

        if command == "/sync_status":
            if self.sheets_sync is None:
                return LeadReply("finance", "belum_dikonfigurasi", "Google Sheets Sync belum tersedia pada runtime ini.")
            result = self.sheets_sync.status()
            text_result = result.text
            if self.sheets_sync.configured:
                text_result += " Auto-sync aktif setelah transaksi, koreksi, atau perubahan saldo awal berhasil disimpan."
            return LeadReply("finance", result.status, text_result)

        if command == "/sync":
            if self.sheets_sync is None:
                return LeadReply("finance", "belum_dikonfigurasi", "Google Sheets Sync belum tersedia pada runtime ini.")
            result = self.sheets_sync.sync_now()
            return LeadReply("finance", result.status, result.text)

        correction_words = ("koreksi transaksi", "ubah transaksi", "akun seharusnya", "akun harusnya")
        if any(word in text for word in correction_words):
            if self.finance is None:
                return LeadReply("finance", "terdeteksi", "Finance runtime belum diaktifkan.")
            result = correct_latest_account(self.finance, raw)
            sync_note = self._auto_sync_after_finance_write(raw, result)
            return LeadReply("finance", result.status, result.text + sync_note)

        finance_commands = {
            "/saldo", "/akun", "/kategori", "/hari_ini", "/bulan_ini",
            "/pemasukan", "/pengeluaran", "/piutang", "/utang"
        }
        finance_words = (
            "pengeluaran", "pemasukan", "saldo", "saldo awal", "kategori", "cashflow", "arus kas",
            "laba", "rugi", "piutang", "utang", "catat keluar", "catat masuk", "beli", "bayar pakai",
            "top up", "transfer", "kirim"
        )
        if command in finance_commands or any(word in text for word in finance_words):
            if self.finance is None:
                return LeadReply("finance", "terdeteksi", "Saya mengenali ini sebagai tugas Finance Agent, tetapi Finance runtime belum diaktifkan.")
            if self._topup_needs_source_account(text) and any(word in text for word in ("pengeluaran", "catat keluar", "beli", "belanja")):
                return LeadReply(
                    "finance",
                    "needs_review",
                    "Belum saya catat karena akun sumber belum disebutkan. Untuk top up/transfer, tulis sumbernya agar akun tujuan tidak salah dianggap sebagai sumber.\n"
                    "Contoh: Catat pengeluaran 300 ribu top up saldo DANA istri pakai BNI."
                )
            result = self.finance.handle(raw)
            sync_note = self._auto_sync_after_finance_write(raw, result)
            return LeadReply("finance", result.status, result.text + sync_note)

        taqidesk_words = ("taqidesk", "taqi desk", "pesanan", "order", "antrean", "pelanggan", "cetak")
        if any(word in text for word in taqidesk_words):
            return LeadReply(
                "docutech",
                "terdeteksi",
                "Saya mengenali ini sebagai tugas TaqiDesk/DocuTech. Integrasi TaqiDesk belum diaktifkan pada tahap runtime minimum."
            )

        if self._document_session_active():
            result = self.document.handle(raw)
            return LeadReply("document", result.status, result.text)

        if command.startswith("/"):
            return LeadReply("lead", "membutuhkan_bantuan", "Perintah belum dikenal. Ketik /bantuan.")

        return LeadReply(
            "lead",
            "membutuhkan_bantuan",
            "Pesan sudah diterima Lead Agent, tetapi router minimum belum yakin agent tujuan. "
            "Nanti Claude Lead Agent akan menggantikan routing aturan ini."
        )

    # --- Kata kunci intent pelanggan (Fase 3, router aturan sederhana) ---
    # action_type harus sama persis dengan yang dikenali app/approval_gate.py agar
    # klasifikasi Level 0-4 dan daftar auto-send rutin tetap konsisten satu sumber.
    _CUSTOMER_GREETING_WORDS = (
        "halo", "hai", "hi", "hy", "permisi", "assalamualaikum",
        "selamat pagi", "selamat siang", "selamat sore", "selamat malam",
    )
    _CUSTOMER_FILE_CONFIRM_WORDS = (
        "sudah saya kirim", "sudah dikirim filenya", "filenya sudah saya kirim", "file sudah dikirim",
    )
    _CUSTOMER_STATUS_WORDS = (
        "status pesanan", "status order", "sudah sampai mana", "antrean saya",
        "progress pesanan", "pesanan saya gimana", "orderan saya gimana",
    )
    _CUSTOMER_PRICE_WORDS = (
        "harga", "biaya", "berapa duit", "berapa harga", "price list", "tarif", "ongkos",
    )
    _CUSTOMER_FAQ_WORDS = (
        "jam buka", "jam operasional", "lokasi", "alamat", "cara pesan", "cara order", "cara pemesanan",
    )

    @classmethod
    def _detect_customer_action(cls, text: str) -> tuple[str, str]:
        """Router aturan sederhana untuk intent pelanggan (bukan AI, dulu).

        Balasan untuk harga/status pesanan sengaja tidak mengarang angka: data
        price list/status order real belum tersambung ke jalur pelanggan, jadi
        balasannya jujur "belum bisa dipastikan otomatis" (hallucination prevention,
        lihat docs/roadmap_customer_channel_v1.md bagian "Guardrail Tambahan").
        """
        lowered = text.casefold()
        if any(word in lowered for word in cls._CUSTOMER_GREETING_WORDS):
            return "kirim_salam", "Halo, terima kasih sudah menghubungi kami! Ada yang bisa saya bantu?"
        if any(word in lowered for word in cls._CUSTOMER_FILE_CONFIRM_WORDS):
            return "konfirmasi_file_diterima", "Baik, file sudah kami terima dan akan segera diperiksa. Terima kasih."
        if any(word in lowered for word in cls._CUSTOMER_STATUS_WORDS):
            return "kirim_status_antrean", (
                "Status pesanan Anda belum bisa saya pastikan otomatis saat ini; "
                "saya teruskan ke admin agar dicek dan dibalas langsung."
            )
        if any(word in lowered for word in cls._CUSTOMER_PRICE_WORDS):
            return "kirim_estimasi_harga_standar", (
                "Harga pastinya belum bisa saya pastikan otomatis saat ini; "
                "saya teruskan ke admin agar bisa dibalas dengan info harga yang akurat."
            )
        if any(word in lowered for word in cls._CUSTOMER_FAQ_WORDS):
            return "jawab_faq", "Pertanyaan ini akan diteruskan ke admin agar dijawab dengan informasi yang akurat."
        return "minta_detail_order", (
            "Baik, boleh diceritakan kebutuhan layanannya (jenis jasa, jumlah/ukuran, dan tenggat waktu)? "
            "Supaya saya bisa bantu lebih lanjut."
        )

    def handle_customer_message(self, sender_id: str, message: str, *, has_attachment: bool = False) -> LeadReply:
        """Jalur pelanggan: WAJIB melalui Trust Layer lalu Approval Gate, terpisah
        total dari `handle_admin_message`. Lihat Fase 3 di
        `docs/roadmap_customer_channel_v1.md`.
        """
        if self.trust_layer is None or self.approval_gate is None:
            return LeadReply("lead", "belum_tersedia", "Jalur pelanggan belum aktif pada runtime ini.")

        raw = (message or "").strip()
        if not raw and not has_attachment:
            return LeadReply("lead", "membutuhkan_bantuan", "Pesan kosong.")

        if is_admin_command(raw):
            # Percobaan memakai command admin dari channel pelanggan diperlakukan
            # sebagai sinyal mencurigakan (lihat app/interaction_policy.py), bukan
            # sekadar diabaikan — dicatat ke Trust Layer sebagai bagian audit trail.
            self.trust_layer.evaluate(sender_id, "Percobaan command admin dari channel pelanggan: " + raw)
            return LeadReply(
                "trust_layer", "ditolak_halus",
                "Maaf, perintah itu tidak tersedia di sini. Silakan sampaikan kebutuhan Anda dengan bahasa biasa.",
            )

        trust = self.trust_layer.evaluate(sender_id, raw, has_attachment=has_attachment)
        if trust.decision == "tolak_halus":
            return LeadReply(
                "trust_layer", "ditolak_halus",
                "Maaf, pesan ini belum dapat kami proses lebih lanjut. Jika Anda pelanggan yang membutuhkan "
                "layanan kami, silakan jelaskan kebutuhan Anda secara lebih spesifik.",
            )
        if trust.decision == "verifikasi":
            return LeadReply(
                "trust_layer", "perlu_verifikasi",
                "Sebelum saya lanjutkan, boleh diceritakan dulu jenis layanan yang Anda butuhkan, "
                "beserta jumlah/ukuran dan tenggat waktunya?",
            )

        action_type, reply_text = self._detect_customer_action(raw)
        approval = self.approval_gate.request(
            action_type,
            requested_by=f"customer:{sender_id}",
            summary=f"[{trust.category}] {raw[:200]}",
        )
        if approval.status == "pending_approval":
            return LeadReply(
                "approval_gate", "menunggu_persetujuan",
                "Terima kasih, permintaan Anda sudah kami terima dan sedang ditinjau oleh admin kami. "
                "Kami akan segera membalas.",
            )
        return LeadReply(action_type, "berhasil", reply_text)
