"""Lead Agent routing minimum.

Desktop commands tetap dipertahankan. Pesan dari channel admin memakai router aturan
sederhana dulu; model AI belum dihubungkan pada tahap ini.
"""

from dataclasses import dataclass

from app.desktop import DesktopAgent, Result
from app.finance import FinanceService
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
    ):
        self.desktop = desktop
        self.finance = finance
        self.sheets_sync = sheets_sync

    def dispatch(self, command: str, *, name: str = "", path: str = "") -> Result:
        """Kompatibilitas command desktop v0.1."""
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
        """Tentukan apakah Finance Agent baru saja mengubah ledger/config lokal.

        V0.3 hanya memiliki dua jalur write dari chat: set saldo awal dan catat
        pemasukan/pengeluaran. Report/read command tidak boleh memicu auto-sync.
        """
        if result.status != "berhasil":
            return False
        text = raw.casefold()
        if "saldo awal" in text:
            return True
        return result.text.startswith(("Pemasukan tercatat.", "Pengeluaran tercatat."))

    def _auto_sync_after_finance_write(self, raw: str, result) -> str:
        """Auto-sync best effort; kegagalan mirror tidak membatalkan ledger lokal."""
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
        """Router minimum untuk channel admin seperti Web Admin atau Telegram."""
        raw = (message or "").strip()
        if not raw:
            return LeadReply("lead", "membutuhkan_bantuan", "Pesan kosong. Ketik /bantuan untuk melihat perintah awal.")

        text = raw.casefold()
        command = text.split(maxsplit=1)[0].split("@", 1)[0]

        if command in {"/start", "/bantuan", "/help"} or text in {"bantuan", "help"}:
            finance_note = "aktif" if self.finance is not None else "belum diaktifkan"
            sync_note = "siap + auto-sync" if self.sheets_sync and self.sheets_sync.configured else "belum dikonfigurasi"
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
                "Kamu juga boleh menulis bahasa biasa, misalnya: Catat pengeluaran 80 ribu beli tinta untuk Taqi DocuTech pakai BCA.\n\n"
                f"Finance runtime: {finance_note}.\nGoogle Sheets Sync: {sync_note}."
            )

        if command == "/status" or text in {"status", "cek status", "health", "health check"}:
            finance_status = "aktif" if self.finance is not None else "belum diaktifkan"
            sync_status = "siap + auto-sync" if self.sheets_sync and self.sheets_sync.configured else "belum dikonfigurasi"
            return LeadReply(
                "lead",
                "berhasil",
                "Lead Agent: aktif\nWeb Admin: terhubung\nTelegram Admin: belum diaktifkan (opsional)\n"
                "Router: aturan minimum\nAI model: belum dihubungkan\n"
                f"Finance runtime: {finance_status}\nGoogle Sheets Sync: {sync_status}"
            )

        if command == "/sync_status":
            if self.sheets_sync is None:
                return LeadReply("finance", "belum_dikonfigurasi", "Google Sheets Sync belum tersedia pada runtime ini.")
            result = self.sheets_sync.status()
            text_result = result.text
            if self.sheets_sync.configured:
                text_result += " Auto-sync aktif setelah transaksi atau perubahan saldo awal berhasil disimpan."
            return LeadReply("finance", result.status, text_result)

        if command == "/sync":
            if self.sheets_sync is None:
                return LeadReply("finance", "belum_dikonfigurasi", "Google Sheets Sync belum tersedia pada runtime ini.")
            result = self.sheets_sync.sync_now()
            return LeadReply("finance", result.status, result.text)

        finance_commands = {
            "/saldo", "/akun", "/kategori", "/hari_ini", "/bulan_ini",
            "/pemasukan", "/pengeluaran", "/piutang", "/utang"
        }
        finance_words = (
            "pengeluaran", "pemasukan", "saldo", "saldo awal", "kategori", "cashflow", "arus kas",
            "laba", "rugi", "piutang", "utang", "catat keluar", "catat masuk", "beli", "bayar pakai"
        )
        if command in finance_commands or any(word in text for word in finance_words):
            if self.finance is None:
                return LeadReply(
                    "finance",
                    "terdeteksi",
                    "Saya mengenali ini sebagai tugas Finance Agent, tetapi Finance runtime belum diaktifkan."
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

        if command.startswith("/"):
            return LeadReply("lead", "membutuhkan_bantuan", "Perintah belum dikenal. Ketik /bantuan.")

        return LeadReply(
            "lead",
            "membutuhkan_bantuan",
            "Pesan sudah diterima Lead Agent, tetapi router minimum belum yakin agent tujuan. "
            "Tahap berikutnya akan menambahkan model/intent router."
        )
