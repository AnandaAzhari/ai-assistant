"""Lead Agent routing minimum.

Desktop commands tetap dipertahankan. Pesan dari channel admin memakai router aturan
sederhana dulu; model Lead Agent belum dihubungkan pada tahap ini.

Jalur pelanggan (`handle_customer_message`, Fase 3 di
`docs/roadmap_customer_channel_v1.md`) sengaja terpisah total dari jalur admin
(`handle_admin_message`): setiap pesan pelanggan WAJIB melalui Security & Trust
Layer (`app/trust_layer.py`) dan Approval Gate (`app/approval_gate.py`) dulu
sebelum diproses lebih lanjut, konsisten dengan prinsip "Zero trust untuk input
pelanggan" di `policies/security_policy.md`. Intent pelanggan memakai
`app/customer_intent.py` (AI-first, lihat modul itu untuk detail) begitu provider
AI dikonfigurasi; router kata kunci di bawah ini tetap dipertahankan sebagai
fallback fail-safe saat AI belum dikonfigurasi, gagal, atau hasilnya tidak lolos
validasi. Router admin masih memakai aturan sederhana (belum berubah).

Begitu pelanggan jelas ingin dibuatkan dokumen (makalah/KTI/skripsi), jalur pelanggan
menyambung ke Document Agent (Nara) yang sama seperti dipakai admin — lihat
`_customer_document_agent`/`_continue_customer_document` di bawah. Setiap pelanggan
punya `DocumentAgent` tersendiri (scope `DOCSRC-WHATSAPP-<sender_id>`, lihat
`document_factory`), supaya sesi/brief satu pelanggan tidak pernah tercampur dengan
pelanggan lain (lihat "Isolasi Antar Pelanggan" di `policies/security_policy.md`).
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.approval_gate import ApprovalGate
from app.content_studio import ContentStudio
from app.customer_book import CustomerBookStore
from app.customer_intent import CustomerIntentClassifier
from app.desktop import DesktopAgent, Result
from app.document_agent import DocumentAgent
from app.finance import FinanceService
from app.finance_corrections import correct_latest_account
from app.google_sheets_sync import GoogleSheetsSync
from app.interaction_log import ALLOWED_REVIEW_LABELS, InteractionLogStore
from app.interaction_policy import is_admin_command
from app.kill_switch import CUSTOMER_NOTICE_TEXT, GLOBAL_SCOPE, KillSwitch
from app.order_status import OrderStatusStore
from app.pdf_compressor import PdfCompressor
from app.price_list import PriceListStore
from app.topic_guard import is_off_topic
from app.trust_layer import TrustLayer

# Scope kill switch yang dikenal untuk command admin `/matikan_otomatis <scope> ...` —
# scope lain di luar daftar ini tetap bisa dipakai lewat KillSwitch langsung (mis. skrip
# admin/testing), tapi command Telegram/Web Admin hanya mengenali nama-nama ini supaya
# admin tidak salah ketik scope yang tidak pernah dicek kode mana pun.
_KNOWN_KILL_SWITCH_SCOPES = {"whatsapp"}

# Daftar perintah untuk menu "/" bawaan Telegram (BotFather `setMyCommands`), supaya
# owner bisa mengetuk "/" di chat dan langsung melihat daftar perintah dengan
# keterangannya — tanpa ini, perintah tetap berfungsi kalau diketik manual (lihat
# `handle_admin_message` di bawah), tapi tidak muncul di menu bawaan Telegram.
# Dipisah jadi satu sumber di sini (bukan ditulis ulang di `telegram_main.py`) supaya
# tidak ada dua salinan daftar perintah yang bisa diam-diam berbeda dari teks
# `/bantuan` di bawah. Nama perintah HARUS huruf kecil/angka/underscore saja (aturan
# Telegram), keterangan singkat karena tampilannya dipotong di layar sempit.
TELEGRAM_COMMAND_MENU: tuple[tuple[str, str], ...] = (
    ("help", "Tampilkan daftar perintah"),
    ("status", "Cek status sistem"),
    ("saldo", "Saldo ledger per akun"),
    ("akun", "Daftar akun dan saldo awal"),
    ("kategori", "Kategori transaksi yang sudah dipelajari"),
    ("hari_ini", "Ringkasan transaksi hari ini"),
    ("minggu_ini", "Ringkasan minggu ini (Senin-Minggu)"),
    ("bulan_ini", "Ringkasan transaksi bulan ini"),
    ("laba_rugi", "Laba/rugi bulan ini per kategori"),
    ("arus_kas", "Saldo awal/masuk/keluar per akun"),
    ("sync_status", "Status Google Sheets Sync"),
    ("sync", "Sinkronkan ledger ke Google Sheets"),
    ("dokumen_status", "Cek Document Agent (Nara)"),
    ("dokumen_engine_status", "Cek mesin pembuat DOCX/PDF"),
    ("dokumen_demo", "Buat DOCX/PDF demo tanpa token AI"),
    ("research", "Cari sumber akademik tanpa token AI"),
    ("research_status", "Cek Research Manager"),
    ("research_save", "Simpan hasil riset sebagai referensi"),
    ("sources", "Lihat Source Registry sesi ini"),
    ("makalah", "Bicara langsung dengan Document Agent"),
    ("dokumen_baru", "Reset sesi percakapan dokumen"),
    ("matikan_otomatis", "Kill switch: hentikan proses otomatis"),
    ("nyalakan_otomatis", "Nyalakan kembali proses otomatis"),
    ("status_otomatis", "Cek status kill switch"),
    ("harga_set", "Simpan/ubah harga layanan"),
    ("harga_hapus", "Hapus harga layanan"),
    ("harga_list", "Lihat semua harga tersimpan"),
    ("status_set", "Catat status pesanan pelanggan"),
    ("status_lihat", "Lihat riwayat status order pelanggan"),
    ("pelanggan_nama", "Simpan/ubah nama dan bisnis pelanggan"),
    ("pelanggan_catat", "Catat order terstruktur milik pelanggan"),
    ("pelanggan_riwayat", "Lihat profil dan riwayat order pelanggan"),
    ("pelanggan_ringkasan", "Ringkasan jumlah order dan omzet per bisnis"),
    ("kompres_pdf_status", "Cek kesiapan kompresi PDF (Ghostscript)"),
    ("konten_baru", "Kirana: buat draft ide dan caption"),
    ("eval_sample", "Ambil sampel interaksi untuk ditinjau"),
    ("eval_tandai", "Catat hasil tinjauan satu interaksi"),
    ("eval_status", "Ringkasan tren kualitas dari tinjauan"),
)


@dataclass(frozen=True)
class LeadReply:
    target: str
    status: str
    text: str
    # Path file lokal (Word/PDF/dst.) yang perlu dikirim ke pelanggan sebagai
    # lampiran, kosong (tuple kosong) bila balasan ini tidak membawa file. Bisa
    # lebih dari satu — mis. makalah selesai sekarang mengirim DOCX DAN PDF
    # sekaligus (lihat _continue_customer_document) — dikirim berurutan oleh
    # WhatsAppCustomerAdapter, bukan cuma satu file per balasan seperti sebelumnya.
    attachment_paths: tuple[str, ...] = ()


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
        intent_classifier: CustomerIntentClassifier | None = None,
        document_factory: Callable[[str], DocumentAgent] | None = None,
        kill_switch: KillSwitch | None = None,
        price_list: PriceListStore | None = None,
        order_status: OrderStatusStore | None = None,
        content_studio: ContentStudio | None = None,
        interaction_log: InteractionLogStore | None = None,
        customer_book: CustomerBookStore | None = None,
        pdf_compressor: PdfCompressor | None = None,
    ):
        self.desktop = desktop
        self.finance = finance
        self.sheets_sync = sheets_sync
        self.document = document
        self.admin_channel = admin_channel
        self.trust_layer = trust_layer
        self.approval_gate = approval_gate
        self.intent_classifier = intent_classifier
        self.kill_switch = kill_switch
        self.price_list = price_list
        self.order_status = order_status
        self.content_studio = content_studio
        self.interaction_log = interaction_log
        self.customer_book = customer_book
        self.pdf_compressor = pdf_compressor
        # Rakit DocumentAgent per-pelanggan hanya saat pertama kali dibutuhkan
        # (lihat _customer_document_agent), supaya jalur pelanggan tetap ringan
        # kalau document_factory tidak diberikan (fitur belum diaktifkan).
        self.document_factory = document_factory
        self._customer_documents: dict[str, DocumentAgent] = {}
        # Pelanggan yang sudah kirim PDF tapi belum menyebutkan target ukuran (KB/MB)
        # di pesan yang sama — menunggu balasan berikutnya, lihat
        # _handle_customer_message_inner dan _run_pdf_compression di bawah. Per proses
        # (sama seperti _customer_documents), tidak persisten lintas restart — wajar,
        # karena kalau pelanggan tidak sempat balas sebelum server restart, mereka
        # tinggal kirim ulang PDF-nya.
        self._pending_pdf_compressions: dict[str, str] = {}

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

    @staticmethod
    def _parse_kill_switch_args(rest: str) -> tuple[str, str]:
        """Pisahkan scope opsional (kata pertama, harus persis salah satu nama di
        `_KNOWN_KILL_SWITCH_SCOPES`) dari sisa teks sebagai alasan. Tanpa kata pertama
        yang cocok, seluruh teks dianggap alasan dan scope default "global" (mematikan
        SEMUA channel pelanggan sekaligus) — supaya admin yang buru-buru cukup ketik
        `/matikan_otomatis kena serangan spam masif` tanpa perlu ingat nama scope."""
        rest = (rest or "").strip()
        if not rest:
            return GLOBAL_SCOPE, ""
        first, _, remainder = rest.partition(" ")
        if first.casefold() in _KNOWN_KILL_SWITCH_SCOPES:
            return first.casefold(), remainder.strip()
        return GLOBAL_SCOPE, rest

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
                "/hari_ini [usaha] - ringkasan hari ini (opsional filter usaha)\n"
                "/minggu_ini [usaha] - ringkasan minggu ini (Senin-Minggu)\n"
                "/bulan_ini [usaha] - ringkasan bulan ini (opsional filter usaha)\n"
                "/laba_rugi [usaha] - laba/rugi bulan ini, rincian per kategori pengeluaran\n"
                "/arus_kas [akun] - saldo awal/masuk/keluar/saldo akhir per akun bulan ini\n"
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
                "/matikan_otomatis [whatsapp] <alasan> - kill switch: hentikan proses otomatis pesan pelanggan\n"
                "/nyalakan_otomatis [whatsapp] - nyalakan kembali proses otomatis pesan pelanggan\n"
                "/status_otomatis - cek status kill switch\n"
                "/harga_set <layanan> | <harga> | <catatan opsional> - simpan/ubah harga layanan\n"
                "/harga_hapus <layanan> - hapus harga layanan\n"
                "/harga_list - lihat semua harga tersimpan\n"
                "/status_set <nomor_wa> <order_id> | <status> - catat status pesanan pelanggan\n"
                "/status_lihat <nomor_wa> - lihat riwayat status order pelanggan tsb\n"
                "/pelanggan_nama <nomor_wa> | <nama> | <bisnis opsional> - simpan/ubah nama dan bisnis pelanggan\n"
                "/pelanggan_catat <nomor_wa> <bisnis> | <item> | <harga opsional> - catat order terstruktur\n"
                "/pelanggan_riwayat <nomor_wa> - lihat profil dan riwayat order pelanggan\n"
                "/pelanggan_ringkasan <bisnis> - total order dan omzet bisnis tsb\n"
                "/kompres_pdf_status - cek kesiapan kompresi PDF (Ghostscript) di server ini\n"
                "/konten_baru <usaha> | <platform> | <brief> - Content Studio: buat draft caption\n"
                "/eval_sample [agent] [n] - Fase 5: ambil sampel interaksi produksi untuk ditinjau\n"
                "/eval_tandai <id> | <baik/perlu_perbaikan/tidak_baik> | <catatan opsional> - catat hasil tinjauan\n"
                "/eval_status [agent] - ringkasan tren kualitas dari tinjauan yang sudah dicatat\n"
                "Koreksi akun transaksi terakhir: `Koreksi transaksi terakhir, akun seharusnya BNI`.\n\n"
                f"Finance runtime: {finance_note}.\n"
                f"Google Sheets Sync: {sync_note}.\n"
                f"Document Agent: {document_note}.\n"
                f"Document Engine: {engine_note}.\n"
                f"Kill switch: {'siap' if self.kill_switch is not None else 'belum tersedia'}.\n"
                f"Price list: {'siap' if self.price_list is not None else 'belum tersedia'}.\n"
                f"Order status: {'siap' if self.order_status is not None else 'belum tersedia'}.\n"
                f"Content Studio: {'siap' if self.content_studio is not None and self.content_studio.configured else 'belum tersedia/menunggu API key'}.\n"
                f"Interaction Log (Fase 5): {'siap' if self.interaction_log is not None else 'belum tersedia'}.\n"
                f"Customer Book: {'siap' if self.customer_book is not None else 'belum tersedia'}.\n"
                f"Kompresi PDF (Nara): {'siap' if self.pdf_compressor is not None and self.pdf_compressor.available else 'belum tersedia'}."
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
                f"Finance runtime: {finance_status}\nGoogle Sheets Sync: {sync_status}\n"
                f"Kill switch: {'siap' if self.kill_switch is not None else 'belum tersedia'}"
            )

        if command == "/dokumen_status":
            if self.document is None:
                return LeadReply("document", "belum_dikonfigurasi", "Document Agent belum tersedia pada runtime ini.")
            result = self.document.status()
            return LeadReply("document", result.status, result.text)

        if command in {"/matikan_otomatis", "/killswitch_matikan"}:
            if self.kill_switch is None:
                return LeadReply("lead", "belum_dikonfigurasi", "Kill switch belum tersedia pada runtime ini.")
            parts = raw.split(maxsplit=1)
            rest = parts[1] if len(parts) > 1 else ""
            scope, reason = self._parse_kill_switch_args(rest)
            state = self.kill_switch.activate(scope=scope, reason=reason, changed_by=f"admin:{self.admin_channel}")
            return LeadReply(
                "kill_switch", "berhasil",
                f"Kill switch AKTIF untuk scope '{state.scope}'. Pesan pelanggan di scope ini otomatis ditolak "
                f"(tidak diproses sama sekali) sampai dinyalakan lagi dengan /nyalakan_otomatis.\n"
                f"Alasan: {state.reason or '(tidak diisi)'}"
            )

        if command in {"/nyalakan_otomatis", "/killswitch_nyalakan"}:
            if self.kill_switch is None:
                return LeadReply("lead", "belum_dikonfigurasi", "Kill switch belum tersedia pada runtime ini.")
            parts = raw.split(maxsplit=1)
            rest = parts[1] if len(parts) > 1 else ""
            scope, reason = self._parse_kill_switch_args(rest)
            state = self.kill_switch.deactivate(scope=scope, reason=reason, changed_by=f"admin:{self.admin_channel}")
            return LeadReply(
                "kill_switch", "berhasil",
                f"Kill switch NONAKTIF untuk scope '{state.scope}'. Pesan pelanggan diproses normal kembali."
            )

        if command in {"/status_otomatis", "/killswitch_status"}:
            if self.kill_switch is None:
                return LeadReply("lead", "belum_dikonfigurasi", "Kill switch belum tersedia pada runtime ini.")
            lines = []
            for scope in [GLOBAL_SCOPE, *sorted(_KNOWN_KILL_SWITCH_SCOPES)]:
                state = self.kill_switch.status(scope)
                label = "AKTIF (menghentikan proses otomatis)" if state.active else "nonaktif"
                if state.active and state.reason:
                    label += f" — alasan: {state.reason}"
                lines.append(f"{scope}: {label}")
            return LeadReply("kill_switch", "berhasil", "Status kill switch:\n" + "\n".join(lines))

        if command in {"/harga_set", "/harga_tambah"}:
            if self.price_list is None:
                return LeadReply("lead", "belum_dikonfigurasi", "Price list belum tersedia pada runtime ini.")
            parts = raw.split(maxsplit=1)
            rest = parts[1] if len(parts) > 1 else ""
            fields = [field.strip() for field in rest.split("|")]
            if len(fields) < 2 or not fields[0] or not fields[1]:
                return LeadReply(
                    "lead", "format_salah",
                    "Format: /harga_set <nama layanan> | <harga> | <catatan opsional>\n"
                    "Contoh: /harga_set Cetak Skripsi | Rp250/lembar hitam putih | Minimal 10 lembar",
                )
            service, price_text = fields[0], fields[1]
            note = fields[2] if len(fields) > 2 else ""
            try:
                entry = self.price_list.set_price(
                    service, price_text, note=note, updated_by=f"admin:{self.admin_channel}",
                )
            except ValueError as exc:
                return LeadReply("lead", "format_salah", str(exc))
            return LeadReply(
                "price_list", "berhasil",
                f"Harga tersimpan: {entry.display_name} = {entry.price_text}" + (f" ({entry.note})" if entry.note else ""),
            )

        if command in {"/harga_hapus", "/harga_hapus_layanan"}:
            if self.price_list is None:
                return LeadReply("lead", "belum_dikonfigurasi", "Price list belum tersedia pada runtime ini.")
            parts = raw.split(maxsplit=1)
            service = parts[1].strip() if len(parts) > 1 else ""
            if not service:
                return LeadReply("lead", "format_salah", "Format: /harga_hapus <nama layanan>")
            removed = self.price_list.remove(service)
            return LeadReply(
                "price_list", "berhasil" if removed else "tidak_ditemukan",
                f"Harga '{service}' dihapus." if removed else f"Layanan '{service}' tidak ditemukan di price list.",
            )

        if command in {"/harga_list", "/harga_daftar"}:
            if self.price_list is None:
                return LeadReply("lead", "belum_dikonfigurasi", "Price list belum tersedia pada runtime ini.")
            entries = self.price_list.list_all()
            if not entries:
                return LeadReply("price_list", "berhasil", "Price list masih kosong. Tambah dengan /harga_set.")
            lines = [f"- {entry.display_name}: {entry.price_text}" + (f" ({entry.note})" if entry.note else "") for entry in entries]
            return LeadReply("price_list", "berhasil", "Price list saat ini:\n" + "\n".join(lines))

        if command in {"/status_set", "/status_order_set"}:
            if self.order_status is None:
                return LeadReply("lead", "belum_dikonfigurasi", "Order status belum tersedia pada runtime ini.")
            parts = raw.split(maxsplit=1)
            rest = parts[1] if len(parts) > 1 else ""
            header, _, status_text = rest.partition("|")
            header_parts = header.split(maxsplit=1)
            status_text = status_text.strip()
            if len(header_parts) < 2 or not status_text:
                return LeadReply(
                    "lead", "format_salah",
                    "Format: /status_set <nomor_wa_pelanggan> <order_id> | <status>\n"
                    "Contoh: /status_set 628111222333 ORD-001 | Sedang dicetak, estimasi selesai besok sore",
                )
            sender_id, order_id = header_parts[0].strip(), header_parts[1].strip()
            try:
                entry = self.order_status.set_status(
                    order_id, sender_id, status_text, updated_by=f"admin:{self.admin_channel}",
                )
            except ValueError as exc:
                return LeadReply("lead", "format_salah", str(exc))
            return LeadReply(
                "order_status", "berhasil",
                f"Status order {entry.order_id} milik {entry.sender_id} tersimpan: {entry.status_text}",
            )

        if command in {"/status_lihat", "/status_order_lihat"}:
            if self.order_status is None:
                return LeadReply("lead", "belum_dikonfigurasi", "Order status belum tersedia pada runtime ini.")
            parts = raw.split(maxsplit=1)
            sender_id = parts[1].strip() if len(parts) > 1 else ""
            if not sender_id:
                return LeadReply("lead", "format_salah", "Format: /status_lihat <nomor_wa_pelanggan>")
            entries = self.order_status.list_for_customer(sender_id)
            if not entries:
                return LeadReply("order_status", "berhasil", f"Belum ada order tercatat untuk {sender_id}.")
            lines = [f"- {entry.order_id}: {entry.status_text} (diperbarui {entry.updated_at})" for entry in entries]
            return LeadReply("order_status", "berhasil", f"Order milik {sender_id}:\n" + "\n".join(lines))

        if command in {"/pelanggan_nama", "/pelanggan_profil"}:
            if self.customer_book is None:
                return LeadReply("lead", "belum_dikonfigurasi", "Customer Book belum tersedia pada runtime ini.")
            parts = raw.split(maxsplit=1)
            rest = parts[1] if len(parts) > 1 else ""
            fields = [field.strip() for field in rest.split("|")]
            sender_id = fields[0] if fields else ""
            display_name = fields[1] if len(fields) > 1 else ""
            business = fields[2] if len(fields) > 2 else ""
            if not sender_id or not display_name:
                return LeadReply(
                    "lead", "format_salah",
                    "Format: /pelanggan_nama <nomor_wa> | <nama> | <bisnis opsional>\n"
                    "Contoh: /pelanggan_nama 628111222333 | Budi | Risol Mamqi",
                )
            try:
                entry = self.customer_book.set_profile(sender_id, display_name=display_name, business=business)
            except ValueError as exc:
                return LeadReply("lead", "format_salah", str(exc))
            return LeadReply(
                "customer_book", "berhasil",
                f"Profil {entry.sender_id} tersimpan: {entry.display_name}"
                + (f" ({entry.business})" if entry.business else ""),
            )

        if command in {"/pelanggan_catat", "/pelanggan_order"}:
            if self.customer_book is None:
                return LeadReply("lead", "belum_dikonfigurasi", "Customer Book belum tersedia pada runtime ini.")
            parts = raw.split(maxsplit=1)
            rest = parts[1] if len(parts) > 1 else ""
            header, _, tail = rest.partition(" ")
            fields = [field.strip() for field in tail.split("|")]
            sender_id = header.strip()
            business = fields[0] if fields else ""
            item_description = fields[1] if len(fields) > 1 else ""
            amount_text = fields[2] if len(fields) > 2 else ""
            if not sender_id or not business or not item_description:
                return LeadReply(
                    "lead", "format_salah",
                    "Format: /pelanggan_catat <nomor_wa> <bisnis> | <item> | <harga opsional>\n"
                    "Contoh: /pelanggan_catat 628111222333 Risol Mamqi | Risol isi ayam x10 | 50000",
                )
            amount = None
            if amount_text:
                digits_only = re.sub(r"[^0-9]", "", amount_text)
                if not digits_only:
                    return LeadReply("lead", "format_salah", "Harga harus berupa angka, mis. 50000 atau Rp 50.000.")
                amount = int(digits_only)
            try:
                entry = self.customer_book.record_order(
                    sender_id, business, item_description, amount=amount, created_by=f"admin:{self.admin_channel}",
                )
            except ValueError as exc:
                return LeadReply("lead", "format_salah", str(exc))
            harga_note = f", Rp{entry.amount:,}".replace(",", ".") if entry.amount is not None else ""
            return LeadReply(
                "customer_book", "berhasil",
                f"Order {entry.id} milik {entry.sender_id} tercatat: {entry.item_description}{harga_note}",
            )

        if command in {"/pelanggan_riwayat", "/pelanggan_lihat"}:
            if self.customer_book is None:
                return LeadReply("lead", "belum_dikonfigurasi", "Customer Book belum tersedia pada runtime ini.")
            parts = raw.split(maxsplit=1)
            sender_id = parts[1].strip() if len(parts) > 1 else ""
            if not sender_id:
                return LeadReply("lead", "format_salah", "Format: /pelanggan_riwayat <nomor_wa>")
            customer = self.customer_book.get_customer(sender_id)
            orders = self.customer_book.list_orders_for_customer(sender_id)
            if customer is None and not orders:
                return LeadReply("customer_book", "berhasil", f"Belum ada data tercatat untuk {sender_id}.")
            lines = []
            if customer is not None:
                nama = customer.display_name or "(nama belum diisi)"
                bisnis = customer.business or "(bisnis belum diisi)"
                lines.append(f"Profil: {nama} — {bisnis}")
                lines.append(f"Kontak pertama: {customer.first_seen_at}, terakhir: {customer.last_seen_at}")
            if orders:
                lines.append("Riwayat order:")
                for entry in orders:
                    harga_note = f", Rp{entry.amount:,}".replace(",", ".") if entry.amount is not None else ""
                    lines.append(f"- {entry.id} ({entry.business}): {entry.item_description}{harga_note} [{entry.status}]")
            else:
                lines.append("Belum ada order tercatat.")
            return LeadReply("customer_book", "berhasil", "\n".join(lines))

        if command in {"/pelanggan_ringkasan", "/pelanggan_omzet"}:
            if self.customer_book is None:
                return LeadReply("lead", "belum_dikonfigurasi", "Customer Book belum tersedia pada runtime ini.")
            parts = raw.split(maxsplit=1)
            business = parts[1].strip() if len(parts) > 1 else ""
            if not business:
                return LeadReply("lead", "format_salah", "Format: /pelanggan_ringkasan <bisnis>")
            summary = self.customer_book.summary_by_business(business)
            omzet_text = f"Rp{summary['total_omzet']:,}".replace(",", ".")
            return LeadReply(
                "customer_book", "berhasil",
                f"Ringkasan {business}: {summary['total_order']} order tercatat, total omzet {omzet_text}.",
            )

        if command in {"/kompres_pdf_status", "/kompresi_pdf_status"}:
            if self.pdf_compressor is None:
                return LeadReply("lead", "belum_dikonfigurasi", "Kompresi PDF belum tersedia pada runtime ini.")
            return LeadReply("pdf_compressor", "berhasil", self.pdf_compressor.status_text)

        if command in {"/konten_baru", "/konten_baru_draft"}:
            if self.content_studio is None:
                return LeadReply("lead", "belum_dikonfigurasi", "Content Studio belum tersedia pada runtime ini.")
            parts = raw.split(maxsplit=1)
            rest = parts[1] if len(parts) > 1 else ""
            fields = [field.strip() for field in rest.split("|")]
            if len(fields) < 3 or not fields[0] or not fields[1] or not fields[2]:
                return LeadReply(
                    "lead", "format_salah",
                    "Format: /konten_baru <usaha> | <platform> | <brief>\n"
                    "Contoh: /konten_baru Risol Mamqi | instagram | promo risol weekend, tema ceria",
                )
            business, platform, brief = fields[0], fields[1], fields[2]
            result = self.content_studio.generate_draft(business, platform, brief)
            if result.status == "belum_dikonfigurasi":
                return LeadReply("content_studio", result.status, "Content Studio belum dikonfigurasi (API key AI belum diisi).")
            if result.status == "needs_review":
                return LeadReply("content_studio", result.status, result.note or "Draft perlu ditinjau sebelum dilanjutkan.")
            if result.status != "draft":
                return LeadReply(
                    "content_studio", result.status,
                    result.note or "Gagal membuat draft konten, coba lagi sebentar lagi.",
                )
            lines = [f"{i}. {caption}" for i, caption in enumerate(result.captions, start=1)]
            text = (
                f"Draft konten untuk {result.business} ({result.platform}), id {result.content_id}:\n"
                + "\n".join(lines)
                + "\n\nIni masih draft — tinjau/edit dulu sebelum dijadwalkan (belum ada auto-publish)."
            )
            if result.note:
                text += f"\nCatatan: {result.note}"
            return LeadReply("content_studio", "berhasil", text)

        if command in {"/eval_sample", "/eval_contoh"}:
            if self.interaction_log is None:
                return LeadReply("lead", "belum_dikonfigurasi", "Interaction Log belum tersedia pada runtime ini.")
            parts = raw.split(maxsplit=1)
            args = (parts[1].split() if len(parts) > 1 else [])
            agent = args[0] if args else None
            try:
                limit = int(args[1]) if len(args) > 1 else 5
            except ValueError:
                return LeadReply("lead", "format_salah", "Format: /eval_sample [agent] [jumlah]")
            entries = self.interaction_log.sample_for_review(agent, limit=limit)
            if not entries:
                return LeadReply(
                    "interaction_log", "berhasil",
                    "Tidak ada interaksi yang belum ditinjau" + (f" untuk agent '{agent}'." if agent else "."),
                )
            lines = []
            for entry in entries:
                lines.append(
                    f"id: {entry.id}\nagent: {entry.agent} | channel: {entry.channel} | {entry.created_at}\n"
                    f"input: {entry.input_text[:300]}\noutput: {entry.output_text[:300]}\n"
                    f"-> tandai: /eval_tandai {entry.id} | baik/perlu_perbaikan/tidak_baik | catatan"
                )
            return LeadReply("interaction_log", "berhasil", "\n\n".join(lines))

        if command in {"/eval_tandai", "/eval_review"}:
            if self.interaction_log is None:
                return LeadReply("lead", "belum_dikonfigurasi", "Interaction Log belum tersedia pada runtime ini.")
            parts = raw.split(maxsplit=1)
            rest = parts[1] if len(parts) > 1 else ""
            fields = [field.strip() for field in rest.split("|")]
            if len(fields) < 2 or not fields[0] or fields[1] not in ALLOWED_REVIEW_LABELS:
                return LeadReply(
                    "lead", "format_salah",
                    "Format: /eval_tandai <id> | <baik/perlu_perbaikan/tidak_baik> | <catatan opsional>",
                )
            entry_id, label = fields[0], fields[1]
            note = fields[2] if len(fields) > 2 else ""
            try:
                updated = self.interaction_log.mark_reviewed(
                    entry_id, label, note=note, reviewed_by=f"admin:{self.admin_channel}",
                )
            except ValueError as exc:
                return LeadReply("lead", "format_salah", str(exc))
            return LeadReply("interaction_log", "berhasil", f"Interaksi {updated.id} ditandai '{updated.review_label}'.")

        if command in {"/eval_status", "/eval_ringkasan"}:
            if self.interaction_log is None:
                return LeadReply("lead", "belum_dikonfigurasi", "Interaction Log belum tersedia pada runtime ini.")
            parts = raw.split(maxsplit=1)
            agent = parts[1].strip() if len(parts) > 1 else None
            summary = self.interaction_log.review_summary(agent)
            label = f" untuk agent '{agent}'" if agent else " (semua agent)"
            return LeadReply(
                "interaction_log", "berhasil",
                f"Ringkasan tinjauan{label}:\n"
                f"Total interaksi: {summary['total']}\n"
                f"Sudah ditinjau: {summary['reviewed']} (baik: {summary['baik']}, "
                f"perlu perbaikan: {summary['perlu_perbaikan']}, tidak baik: {summary['tidak_baik']})\n"
                f"Belum ditinjau: {summary['unreviewed']}",
            )

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
            "/saldo", "/akun", "/kategori", "/hari_ini", "/minggu_ini", "/bulan_ini",
            "/laba_rugi", "/arus_kas", "/pemasukan", "/pengeluaran", "/piutang", "/utang"
        }
        finance_words = (
            "pengeluaran", "pemasukan", "saldo", "saldo awal", "kategori", "cashflow", "arus kas",
            "laba", "rugi", "untung", "keuntungan", "profit", "piutang", "utang", "catat keluar",
            "catat masuk", "beli", "bayar pakai", "top up", "transfer", "kirim"
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

    # --- Teks balasan deterministik per action_type pelanggan ---
    # Dipakai baik oleh hasil klasifikasi AI (app/customer_intent.py) maupun router
    # kata kunci fallback di bawah, supaya teks yang benar-benar dikirim ke pelanggan
    # SELALU deterministik (guardrail hallucination-prevention tidak pernah dilewati
    # oleh keluaran model, lihat docstring app/customer_intent.py).
    _CUSTOMER_REPLY_TEXT = {
        "kirim_salam": "Halo, terima kasih sudah menghubungi kami! Ada yang bisa saya bantu?",
        "konfirmasi_file_diterima": "Baik, file sudah kami terima dan akan segera diperiksa. Terima kasih.",
        "kirim_status_antrean": (
            "Status pesanan Anda belum bisa saya pastikan otomatis saat ini; "
            "saya teruskan ke admin agar dicek dan dibalas langsung."
        ),
        "kirim_estimasi_harga_standar": (
            "Harga pastinya belum bisa saya pastikan otomatis saat ini; "
            "saya teruskan ke admin agar bisa dibalas dengan info harga yang akurat."
        ),
        "jawab_faq": "Pertanyaan ini akan diteruskan ke admin agar dijawab dengan informasi yang akurat.",
        # Dipakai hanya sebagai fallback bila document_factory belum diaktifkan
        # (lihat _classify_customer_intent/handle_customer_message); ketika aktif,
        # balasan sungguhan datang dari Document Agent lewat _continue_customer_document.
        "buat_dokumen_pelanggan": (
            "Baik, saya bantu proses pembuatan dokumennya. Boleh diceritakan jenjang/kelas, "
            "mata pelajaran atau mata kuliah, topik, dan target jumlah halamannya?"
        ),
        "minta_detail_order": (
            "Baik, boleh diceritakan kebutuhan layanannya (jenis jasa, jumlah/ukuran, dan tenggat waktu)? "
            "Supaya saya bisa bantu lebih lanjut."
        ),
        # Topic restriction (guardrail dari docs/roadmap_customer_channel_v1.md
        # "Guardrail Tambahan"): pengalihan sopan, tidak membahas isi topiknya sama
        # sekali, tidak menuduh, dan tetap membuka pintu kalau pelanggan sebenarnya
        # punya kebutuhan layanan.
        "di_luar_topik": (
            "Maaf, saya di sini khusus membantu kebutuhan layanan kami saja, jadi belum bisa "
            "menanggapi hal itu. Ada kebutuhan terkait layanan kami yang bisa saya bantu?"
        ),
        # Fitur kompresi PDF (app/pdf_compressor.py) — pelanggan diberi tahu proaktif
        # kalau bertanya soal ini, bukan cuma tersedia diam-diam. Alur sungguhan (kirim
        # file -> sebutkan target KB/MB) ditangani terpisah di
        # _handle_customer_message_inner, teks ini hanya balasan info sebelum file
        # benar-benar dikirim.
        "info_kompres_pdf": (
            "Bisa! Kirim file PDF-nya ke sini, lalu sebutkan mau dikompres jadi berapa "
            "(contoh: 500 KB atau 1 MB), nanti langsung saya proseskan."
        ),
    }

    # --- Kata kunci intent pelanggan (fallback fail-safe, dipakai saat AI-first di
    # app/customer_intent.py belum dikonfigurasi, gagal, atau hasilnya tidak valid) ---
    # action_type harus sama persis dengan yang dikenali app/approval_gate.py dan
    # app/customer_intent.py agar klasifikasi Level 0-4 dan daftar auto-send rutin
    # tetap konsisten satu sumber.
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
    # Fitur kompresi PDF (app/pdf_compressor.py) — dicek SEBELUM kata kunci dokumen di
    # bawah supaya "kompres pdf tugas saya" tidak salah diarahkan ke sesi pembuatan
    # dokumen baru (buat_dokumen_pelanggan).
    _CUSTOMER_PDF_COMPRESS_WORDS = (
        "kompres pdf", "kompres file pdf", "compress pdf", "perkecil ukuran pdf", "perkecil pdf",
        "kecilkan pdf", "kecilkan ukuran pdf", "pdf kegedean", "pdf terlalu besar", "pdf kebesaran",
    )
    # Sama seperti `document_words` di router admin (lihat handle_admin_message di atas),
    # tapi dicek SETELAH kata harga/status supaya guardrail hallucination-prevention tetap
    # menang saat fallback kata kunci dipakai (mis. "harga bikin makalah berapa" tetap
    # diarahkan ke estimasi harga, bukan langsung mulai sesi dokumen). Klasifikasi AI-first
    # (app/customer_intent.py) menangani nuansa ini lebih baik lewat prompt-nya sendiri.
    # Sengaja tidak memasukkan frasa umum seperti "tugas sekolah"/"tugas kuliah" saja:
    # itu bisa juga berarti pelanggan cuma minta jasa PRINT tugas yang sudah ada
    # (bukan minta ditulis/dibuatkan) — Taqi Desk melayani keduanya. Kata di
    # bawah ini dipilih karena cukup spesifik menandakan pelanggan ingin kontennya
    # DIBUATKAN, bukan sekadar dicetak.
    _CUSTOMER_DOCUMENT_WORDS = (
        "makalah", "karya tulis", "paper sekolah", "paper kuliah", "laporan sekolah",
        "laporan kuliah", "kti", "skripsi",
        "susun dokumen", "buat dokumen", "buatkan dokumen", "bikin makalah", "bikin dokumen",
    )
    # Topic restriction (fallback kata kunci, dipakai saat AI-first belum dikonfigurasi/
    # gagal/hasilnya tidak valid — sama seperti daftar kata kunci lain di atas). Daftar
    # kata kuncinya sekarang tinggal di `app/topic_guard.py` (guardrail bersama lintas
    # agent, dipakai juga oleh `app/document_agent.py`/Nara di tengah sesi dokumen —
    # lihat docstring modul itu), supaya Taqi dan Nara tidak punya dua daftar yang bisa
    # diam-diam berbeda. AI-first di app/customer_intent.py menangani nuansa yang lebih
    # halus lewat prompt-nya sendiri.

    @classmethod
    def _detect_customer_action(cls, text: str) -> tuple[str, str]:
        """Router kata kunci untuk intent pelanggan — fallback fail-safe.

        Dipakai saat AI-first (`app/customer_intent.py`) belum dikonfigurasi, gagal,
        atau hasilnya tidak lolos validasi kutipan bukti, supaya jalur pelanggan tidak
        pernah macet menunggu AI. Balasan untuk harga/status pesanan sengaja tidak
        mengarang angka: data price list/status order real belum tersambung ke jalur
        pelanggan, jadi balasannya jujur "belum bisa dipastikan otomatis" (hallucination
        prevention, lihat docs/roadmap_customer_channel_v1.md bagian "Guardrail Tambahan").
        """
        lowered = text.casefold()
        if any(word in lowered for word in cls._CUSTOMER_GREETING_WORDS):
            action_type = "kirim_salam"
        elif any(word in lowered for word in cls._CUSTOMER_FILE_CONFIRM_WORDS):
            action_type = "konfirmasi_file_diterima"
        elif any(word in lowered for word in cls._CUSTOMER_STATUS_WORDS):
            action_type = "kirim_status_antrean"
        elif any(word in lowered for word in cls._CUSTOMER_PRICE_WORDS):
            action_type = "kirim_estimasi_harga_standar"
        elif any(word in lowered for word in cls._CUSTOMER_FAQ_WORDS):
            action_type = "jawab_faq"
        elif any(word in lowered for word in cls._CUSTOMER_PDF_COMPRESS_WORDS):
            action_type = "info_kompres_pdf"
        elif any(word in lowered for word in cls._CUSTOMER_DOCUMENT_WORDS):
            action_type = "buat_dokumen_pelanggan"
        elif is_off_topic(lowered):
            action_type = "di_luar_topik"
        else:
            action_type = "minta_detail_order"
        return action_type, cls._CUSTOMER_REPLY_TEXT[action_type]

    def _classify_customer_intent(self, raw: str) -> tuple[str, str]:
        """AI-first dulu (`app/customer_intent.py`), fallback ke router kata kunci.

        AI hanya dipakai untuk menentukan action_type (dengan kutipan bukti yang
        tervalidasi terhadap pesan asli); teks balasan yang benar-benar dikirim tetap
        deterministik dari `_CUSTOMER_REPLY_TEXT`, sehingga AI tidak pernah punya
        kesempatan mengarang harga/status pesanan.
        """
        if self.intent_classifier is not None and self.intent_classifier.configured:
            result = self.intent_classifier.classify(raw)
            if result.status == "berhasil" and result.action_type in self._CUSTOMER_REPLY_TEXT:
                return result.action_type, self._CUSTOMER_REPLY_TEXT[result.action_type]
        return self._detect_customer_action(raw)

    def _customer_document_agent(self, sender_id: str) -> DocumentAgent | None:
        """DocumentAgent tersendiri per pelanggan (dibuat sekali, disimpan di memori
        proses ini). Isolasi antar pelanggan ditegakkan lewat `source_scope` berbeda
        yang dibuat `document_factory` untuk tiap `sender_id` (lihat
        `whatsapp_main.py`), bukan cuma instruksi ke AI — sesuai lapis 1
        "Isolasi Antar Pelanggan" di `policies/security_policy.md`."""
        if self.document_factory is None:
            return None
        agent = self._customer_documents.get(sender_id)
        if agent is None:
            agent = self.document_factory(sender_id)
            self._customer_documents[sender_id] = agent
        return agent

    # Ambang ukuran PDF yang dianggap "besar" — di atas ini, Nara proaktif
    # menyebut bahwa PDF-nya bisa dikompres lebih kecil (app/pdf_compressor.py)
    # begitu file makalah selesai dikirim. Di bawah/sama dengan ambang ini TIDAK
    # disebut sama sekali, supaya tidak jadi info berisik untuk file yang memang
    # sudah ringan.
    _PDF_COMPRESS_HINT_THRESHOLD_BYTES = 5 * 1024 * 1024

    def _maybe_append_pdf_compress_hint(self, text: str, pdf_path: str) -> str:
        """Tambahkan ajakan kompresi ke teks balasan kalau PDF yang baru dikirim
        cukup besar DAN fitur kompresinya benar-benar tersedia di runtime ini —
        tidak pernah menawarkan sesuatu yang tidak bisa dipenuhi. `text` dikembalikan
        apa adanya kalau salah satu syarat itu tidak terpenuhi."""
        if self.pdf_compressor is None:
            return text
        try:
            size_bytes = Path(pdf_path).stat().st_size
        except OSError:
            return text
        if size_bytes <= self._PDF_COMPRESS_HINT_THRESHOLD_BYTES:
            return text
        size_mb = size_bytes / (1024 * 1024)
        return (
            f"{text}\n\nFile PDF-nya sekitar {size_mb:.1f}MB. Kalau butuh versi yang lebih "
            "ringan untuk dikirim/disimpan, tinggal bilang mau dikompres jadi berapa KB."
        )

    def _continue_customer_document(self, document: DocumentAgent, sender_id: str, raw: str) -> LeadReply:
        """Serahkan giliran percakapan ke Document Agent (Nara) memakai pedoman
        penomoran/format yang sama seperti admin (`skills/document_academic/`,
        `policies/document_format_policy.md`). Saat file Word final selesai dibuat,
        catat `unggah_file_ke_pelanggan` ke Approval Gate (auto-send rutin, tetap
        wajib tercatat di audit log) dan sertakan path file di `LeadReply` supaya
        adapter channel (mis. `WhatsAppCustomerAdapter`) tahu harus mengirim lampiran.

        Mengirim DOCX DAN PDF sekaligus (kalau PDF-nya berhasil dibuat — lihat
        `app/document_engine.py`, tidak semua server punya LibreOffice/Word) supaya
        pelanggan tidak harus minta PDF terpisah; PDF yang besar sekalian ditawari
        kompresi lewat `_maybe_append_pdf_compress_hint`."""
        result = document.handle(raw)
        attachment_paths: list[str] = []
        reply_text = result.text
        if result.status == "final_ready" and document.final_docx_path:
            self.approval_gate.request(
                "unggah_file_ke_pelanggan",
                requested_by=f"customer:{sender_id}",
                summary=f"Kirim file makalah selesai ke pelanggan {sender_id}",
            )
            attachment_paths.append(document.final_docx_path)
            pdf_path = document.final_pdf_path
            if pdf_path:
                attachment_paths.append(pdf_path)
                reply_text = self._maybe_append_pdf_compress_hint(reply_text, pdf_path)
        return LeadReply("document", result.status, reply_text, tuple(attachment_paths))

    # Target ukuran WAJIB menyebut satuan eksplisit ("kb"/"mb") — sengaja tidak
    # menerima angka polos begitu saja supaya nomor telepon/angka lain di pesan
    # pelanggan tidak salah ditafsirkan sebagai target ukuran kompresi PDF.
    _TARGET_SIZE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(kb|mb)\b", re.IGNORECASE)

    @classmethod
    def _parse_target_size_bytes(cls, text: str) -> int | None:
        """Ambil target ukuran kompresi PDF dari pesan pelanggan, mis. "500kb",
        "500 KB", "1 mb", "0,5MB" — lihat `app/pdf_compressor.py` untuk pemakaiannya."""
        match = cls._TARGET_SIZE_RE.search(text or "")
        if not match:
            return None
        try:
            value = float(match.group(1).replace(",", "."))
        except ValueError:
            return None
        multiplier = 1024 * 1024 if match.group(2).casefold() == "mb" else 1024
        size_bytes = int(value * multiplier)
        return size_bytes if size_bytes > 0 else None

    def _run_pdf_compression(self, sender_id: str, source_path: str, target_bytes: int) -> LeadReply:
        """Jalankan kompresi sungguhan (`app/pdf_compressor.py`) dan laporkan hasilnya
        apa adanya ke pelanggan — termasuk jujur kalau target tidak tercapai persis
        (lihat docstring `PdfCompressor.compress_to_target`, prinsip "tidak berpura-
        pura selalu bisa tepat sasaran"). File hasil dikirim lewat `attachment_paths`
        di `LeadReply`, sama seperti file makalah dari Document Agent."""
        if self.pdf_compressor is None:
            return LeadReply("pdf_compressor", "belum_tersedia", "Fitur kompresi PDF belum aktif di server ini.")
        result = self.pdf_compressor.compress_to_target(source_path, target_bytes, order_id=f"WA-{sender_id}")
        if result.status != "berhasil":
            return LeadReply(
                "pdf_compressor", "gagal",
                result.warning or "Kompresi PDF gagal diproses. Silakan coba lagi atau hubungi admin.",
            )
        original_kb = result.original_size_bytes // 1024
        achieved_kb = result.compressed_size_bytes // 1024
        if result.achieved:
            text = f"Selesai! PDF berhasil dikompres dari {original_kb}KB menjadi {achieved_kb}KB."
            if result.warning:
                text += f" {result.warning}"
        else:
            text = f"PDF sudah dikompres dari {original_kb}KB menjadi {achieved_kb}KB. {result.warning}"
        self.approval_gate.request(
            "unggah_file_ke_pelanggan",
            requested_by=f"customer:{sender_id}",
            summary=f"Kirim hasil kompresi PDF ke pelanggan {sender_id}",
        )
        return LeadReply("pdf_compressor", "berhasil", text, (result.output_path,))

    def _augment_reply_with_real_data(self, action_type: str, raw: str, sender_id: str, reply_text: str) -> str:
        """Ganti balasan generik dengan data ASLI dari `price_list`/`order_status` kalau
        tersedia dan cocok — lihat `app/price_list.py`/`app/order_status.py` untuk
        alasan lengkap. `reply_text` (teks lama) dikembalikan apa adanya kalau modul
        belum dikonfigurasi ATAU datanya tidak ditemukan, supaya tidak pernah menebak."""
        if action_type == "kirim_estimasi_harga_standar" and self.price_list is not None:
            entry = self.price_list.find(raw)
            if entry is not None:
                text = f"Harga {entry.display_name}: {entry.price_text}."
                if entry.note:
                    text += f" {entry.note}"
                return text
        elif action_type == "kirim_status_antrean" and self.order_status is not None:
            # `sender_id` sendiri WAJIB — lihat "Isolasi Antar Pelanggan" di
            # policies/security_policy.md, ditegakkan lagi di app/order_status.py.
            entry = self.order_status.get_latest_for_customer(sender_id)
            if entry is not None:
                return f"Status pesanan Anda ({entry.order_id}): {entry.status_text}."
        return reply_text

    def handle_customer_message(
        self, sender_id: str, message: str, *, has_attachment: bool = False, channel: str = "whatsapp",
        attachment_path: str = "",
    ) -> LeadReply:
        """Bungkus `_handle_customer_message_inner` dengan Interaction Log (Fase 5 —
        Evaluasi & Observability, `docs/roadmap_customer_channel_v1.md`) dan Customer
        Book (`app/customer_book.py`), supaya setiap interaksi produksi dengan
        pelanggan tersimpan untuk ditinjau ulang dan setiap pelanggan tercatat
        kontaknya, tanpa mengubah alur/hasil balasan itu sendiri. Keduanya opsional
        (default nonaktif) dan hanya jalan kalau storenya diisi.

        `attachment_path` kosong untuk pesan tanpa lampiran ATAU lampiran yang belum
        lolos pemeriksaan `app/attachment_guard.py` — diisi WhatsAppCustomerAdapter
        hanya untuk file yang sudah aman disimpan di quarantine (lihat
        `app/whatsapp.py` `_handle_attachment_message`), supaya fitur yang butuh isi
        file pelanggan (mis. kompresi PDF) bisa mengaksesnya."""
        reply = self._handle_customer_message_inner(
            sender_id, message, has_attachment=has_attachment, channel=channel, attachment_path=attachment_path,
        )
        if self.interaction_log is not None:
            agent = "nara" if reply.target == "document" else "taqi"
            self.interaction_log.log(
                agent, sender_id, channel, message or "", reply.text, status=reply.status,
            )
        if self.customer_book is not None:
            # Hanya mencatat first_seen/last_seen/total_contacts — TIDAK PERNAH
            # menebak nama/bisnis pelanggan dari isi pesan. Lihat docstring
            # `CustomerBookStore.touch`.
            self.customer_book.touch(sender_id, channel=channel)
        return reply

    def _handle_customer_message_inner(
        self, sender_id: str, message: str, *, has_attachment: bool = False, channel: str = "whatsapp",
        attachment_path: str = "",
    ) -> LeadReply:
        """Jalur pelanggan: WAJIB melalui Kill Switch, lalu Trust Layer, lalu Approval
        Gate, terpisah total dari `handle_admin_message`. Lihat Fase 3 di
        `docs/roadmap_customer_channel_v1.md`.

        Kill Switch dicek PALING AWAL, sebelum apa pun lain disentuh — sesuai langkah
        pertama "Incident Response" di `policies/security_policy.md` ("aktifkan kill
        switch; hentikan channel/agent terdampak"). Saat aktif (baik scope `channel` ini
        maupun scope "global"), pesan tidak pernah sampai ke Trust Layer/AI/Document
        Agent sama sekali — hanya dibalas notice netral, tanpa detail insiden ke publik.
        """
        if self.kill_switch is not None and self.kill_switch.is_active(channel):
            return LeadReply("kill_switch", "dimatikan_sementara", CUSTOMER_NOTICE_TEXT)

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

        # Kompresi PDF (app/pdf_compressor.py): pelanggan kirim file PDF (lewat
        # attachment_path, sudah lolos app/attachment_guard.py) -> tanya/simpan target
        # ukuran KB/MB kalau belum disebut di caption -> kompres begitu targetnya
        # diketahui (bisa langsung di pesan yang sama atau balasan berikutnya).
        # Dicek SEBELUM sesi dokumen aktif supaya tidak pernah salah diarahkan ke
        # Document Agent (Nara) hanya karena pelanggan kebetulan juga sedang punya
        # sesi dokumen berjalan.
        if attachment_path and self.pdf_compressor is not None and Path(attachment_path).suffix.casefold() == ".pdf":
            self.approval_gate.request(
                "kompres_pdf_pelanggan",
                requested_by=f"customer:{sender_id}",
                summary=f"[{trust.category}] PDF diterima dari {sender_id} untuk dikompres.",
            )
            target_bytes = self._parse_target_size_bytes(raw)
            if target_bytes is not None:
                return self._run_pdf_compression(sender_id, attachment_path, target_bytes)
            self._pending_pdf_compressions[sender_id] = attachment_path
            return LeadReply(
                "pdf_compressor", "menunggu_target_ukuran",
                "File PDF sudah diterima. Mau dikompres jadi berapa? (contoh: 500 KB atau 1 MB)",
            )

        pending_pdf = self._pending_pdf_compressions.get(sender_id)
        if pending_pdf and not has_attachment:
            target_bytes = self._parse_target_size_bytes(raw)
            if target_bytes is not None:
                del self._pending_pdf_compressions[sender_id]
                return self._run_pdf_compression(sender_id, pending_pdf, target_bytes)

        # Pelanggan yang sudah punya sesi dokumen aktif (brief sedang diisi, kerangka
        # menunggu persetujuan, dst.) langsung diteruskan ke Document Agent tanpa
        # diklasifikasikan ulang setiap giliran — sama seperti admin
        # (`_document_session_active`), karena Trust Layer di atas sudah menjaga
        # setiap pesan tetap tepercaya.
        document = self._customer_document_agent(sender_id)
        if document is not None and document.session_active:
            return self._continue_customer_document(document, sender_id, raw)

        action_type, reply_text = self._classify_customer_intent(raw)
        # Hallucination prevention (docs/roadmap_customer_channel_v1.md "Guardrail
        # Tambahan"): kalau data ASLI (price list/order status yang diisi admin)
        # tersedia, jawab dari data itu, bukan teks generik "diteruskan ke admin".
        # Kalau tidak ketemu, reply_text TETAP teks generik lama — tidak pernah menebak.
        reply_text = self._augment_reply_with_real_data(action_type, raw, sender_id, reply_text)

        if action_type == "buat_dokumen_pelanggan":
            if document is None:
                return LeadReply(
                    "document", "belum_tersedia",
                    "Layanan pembuatan dokumen belum aktif pada runtime ini.",
                )
            self.approval_gate.request(
                "buat_dokumen_pelanggan",
                requested_by=f"customer:{sender_id}",
                summary=f"[{trust.category}] Mulai sesi dokumen: {raw[:200]}",
            )
            return self._continue_customer_document(document, sender_id, raw)

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
