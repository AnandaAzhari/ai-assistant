"""Lead Agent routing minimum.

Desktop commands tetap dipertahankan. Pesan dari channel admin memakai router aturan
sederhana dulu; model AI belum dihubungkan pada tahap ini.
"""

from dataclasses import dataclass

from app.desktop import DesktopAgent, Result
from app.finance import FinanceService


@dataclass(frozen=True)
class LeadReply:
    target: str
    status: str
    text: str


class LeadAgent:
    def __init__(self, desktop: DesktopAgent | None = None, finance: FinanceService | None = None):
        self.desktop = desktop
        self.finance = finance

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

    def handle_admin_message(self, message: str) -> LeadReply:
        """Router minimum untuk channel admin seperti Web Admin atau Telegram."""
        raw = (message or "").strip()
        if not raw:
            return LeadReply("lead", "membutuhkan_bantuan", "Pesan kosong. Ketik /bantuan untuk melihat perintah awal.")

        text = raw.casefold()
        command = text.split(maxsplit=1)[0].split("@", 1)[0]

        if command in {"/start", "/bantuan", "/help"} or text in {"bantuan", "help"}:
            finance_note = "aktif" if self.finance is not None else "belum diaktifkan"
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
                "Kamu juga boleh menulis bahasa biasa, misalnya: Catat pengeluaran 80 ribu beli tinta untuk Taqi DocuTech pakai BCA.\n\n"
                f"Finance runtime: {finance_note}."
            )

        if command == "/status" or text in {"status", "cek status", "health", "health check"}:
            finance_status = "aktif" if self.finance is not None else "belum diaktifkan"
            return LeadReply(
                "lead",
                "berhasil",
                "Lead Agent: aktif\nWeb Admin: terhubung\nTelegram Admin: belum diaktifkan (opsional)\n"
                "Router: aturan minimum\nAI model: belum dihubungkan\n"
                f"Finance runtime: {finance_status}"
            )

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
            return LeadReply("finance", result.status, result.text)

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
