"""Lead Agent routing minimum.

Desktop commands tetap dipertahankan. Pesan dari channel admin memakai router aturan
sederhana dulu; model Lead Agent belum dihubungkan pada tahap ini.
"""

import re
from dataclasses import dataclass

from app.desktop import DesktopAgent, Result
from app.document_agent import DocumentAgent
from app.finance import FinanceService
from app.finance_corrections import correct_latest_account
from app.google_sheets_sync import GoogleSheetsSync


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
    ):
        self.desktop = desktop
        self.finance = finance
        self.sheets_sync = sheets_sync
        self.document = document

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
        """True jika Document Agent sudah mengumpulkan sebagian requirement.

        Follow-up seperti `Kelas: XI` tidak selalu mengandung kata 'makalah'. Tanpa
        affinity sederhana ini, router aturan minimum akan mengembalikannya ke Lead.
        """
        if self.document is None:
            return False
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
            sync_status = "siap + auto-sync" if self.sheets_sync and self.sheets_sync.configured else "belum dikonfigurasi"
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
                "Lead Agent: aktif\nWeb Admin: terhubung\nTelegram Admin: belum diaktifkan (opsional)\n"
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

        if command in {"/dokumen_engine_status", "/dokumen_demo"}:
            if self.document is None:
                return LeadReply("document", "belum_dikonfigurasi", "Document Agent belum tersedia pada runtime ini.")
            result = self.document.handle(raw)
            return LeadReply("document", result.status, result.text)

        if command in {"/dokumen_baru", "/makalah_baru"}:
            if self.document is None:
                return LeadReply("document", "belum_dikonfigurasi", "Document Agent belum tersedia pada runtime ini.")
            result = self.document.reset()
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

        # Jika percakapan makalah sudah dimulai, pertahankan affinity ke Document Agent.
        # Ini menangani follow-up seperti `Jenjang: SMA`, `Kelas: XI`, atau `Target: 10 halaman`
        # yang memang tidak mengandung kata kunci 'makalah'. Perintah eksplisit Finance/TaqiDesk
        # tetap diprioritaskan di atas affinity ini.
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
