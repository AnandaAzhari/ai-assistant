"""Attachment Guard — menegakkan `policies/attachment_link_security.md` di kode.

Sebelum modul ini ada, isi file yang dikirim pelanggan (lewat WhatsApp) TIDAK PERNAH
benar-benar diunduh atau diperiksa — `has_attachment=True/False` hanya jadi sinyal
untuk Trust Layer. Pipeline "Pemeriksaan Attachment" di policy itu ada di dokumen
tapi 0% ditegakkan kode. Modul ini menutup bagian yang bisa ditegakkan DETERMINISTIK
tanpa layanan eksternal:

1. Terima isi file sebagai bytes (pemanggil yang mengunduhnya — lihat
   `WhatsAppHTTPClient.download_media`; modul ini sendiri tidak melakukan I/O jaringan).
2. Validasi ekstensi (termasuk ekstensi GANDA yang menyamarkan tipe asli, mis.
   "invoice.pdf.exe"), ukuran, dan nama file.
3. Simpan SELALU ke folder quarantine (bukan folder kerja agent) — lihat
   `policies/attachment_link_security.md` poin 2 dan 7: "Hanya file yang lolos
   kebijakan yang boleh dipindahkan ke workspace agent." Modul ini tidak pernah
   memindahkan file kemana pun sendiri; keputusan itu ada di pemanggil.
4. Catat log audit (sender, filename, hash, risk level, scan status, action) ke SQLite
   — lihat policy bagian "Logging". Tidak pernah mencatat isi file atau secret.
5. Tentukan risk level (LOW/MEDIUM/HIGH/CRITICAL persis seperti definisi policy).
   HIGH dan CRITICAL selalu `allowed=False` — pemanggil WAJIB tidak memproses
   otomatis file itu (lihat policy: "HIGH dan CRITICAL tidak boleh diproses otomatis").

Yang SENGAJA belum ada di sini (di luar cakupan realistis tanpa layanan eksternal):
malware/reputation scanning sungguhan. `AttachmentGuard.__init__` menerima parameter
`scanner` opsional persis seperti yang diminta policy ("Arsitektur harus mendukung
scanner yang dapat diganti ... Scanner eksternal bersifat opsional dan tidak boleh
menjadi satu-satunya lapisan pertahanan") — tanpa `scanner`, risk level murni dari
validasi deterministik di atas, dan defaultnya tetap konservatif (lihat "Default
Action" di policy: kalau tidak yakin aman, QUARANTINE + NO EXECUTION + ESCALATE).
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

LOW, MEDIUM, HIGH, CRITICAL = "LOW", "MEDIUM", "HIGH", "CRITICAL"
_RISK_ORDER = (LOW, MEDIUM, HIGH, CRITICAL)

# policies/attachment_link_security.md "Tipe File Berisiko Tinggi" — tidak boleh
# dieksekusi/diproses otomatis apa pun alasannya.
_HIGH_RISK_EXTENSIONS = {
    ".exe", ".msi", ".com", ".scr", ".bat", ".cmd", ".ps1",
    ".js", ".jse", ".vbs", ".vbe", ".wsf", ".jar", ".lnk",
}
# "dokumen macro-enabled ... tanpa pemeriksaan tambahan" -> HIGH, bukan otomatis LOW.
_MACRO_EXTENSIONS = {".docm", ".xlsm", ".pptm"}
# "Arsip tidak boleh diekstrak otomatis" -> HIGH (arsip terenkripsi dicek terpisah,
# lihat catatan di _classify_extension: tanpa membuka arsip, semua arsip diperlakukan
# HIGH secara konservatif — analisis isi arsip di luar cakupan modul ini).
_ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z"}
# Dokumen/gambar umum yang wajar dikirim pelanggan jasa cetak/dokumen.
_LOW_RISK_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".jpg", ".jpeg", ".png", ".heic", ".heif", ".txt", ".csv",
}

# Batas ukuran dokumen resmi WhatsApp Cloud API (Meta) per Sept 2026 — file yang lolos
# dari WhatsApp sendiri praktis tidak akan melebihi ini, tapi tetap divalidasi di sini
# sebagai defense-in-depth (jangan hanya percaya batas dari pihak luar).
DEFAULT_MAX_SIZE_BYTES = 100 * 1024 * 1024


def _risk_rank(level: str) -> int:
    return _RISK_ORDER.index(level) if level in _RISK_ORDER else 0


def _max_risk(a: str, b: str) -> str:
    return a if _risk_rank(a) >= _risk_rank(b) else b


@dataclass(frozen=True)
class AttachmentDecision:
    risk_level: str
    reason: str
    quarantine_path: str
    sha256: str
    allowed: bool


class AttachmentGuard:
    def __init__(
        self,
        quarantine_dir: str | Path,
        db_path: str | Path,
        *,
        max_size_bytes: int = DEFAULT_MAX_SIZE_BYTES,
        scanner: Callable[[bytes, str], tuple[str, str]] | None = None,
    ):
        self.quarantine_dir = Path(quarantine_dir)
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_size_bytes = max_size_bytes
        # Scanner eksternal opsional — lihat docstring modul. Signature:
        # (data: bytes, filename: str) -> (risk_level, reason).
        self.scanner = scanner
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS attachment_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created TEXT NOT NULL,
                    sender_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    declared_mime_type TEXT NOT NULL DEFAULT '',
                    sha256 TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    risk_level TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    scan_status TEXT NOT NULL,
                    allowed INTEGER NOT NULL,
                    quarantine_path TEXT NOT NULL
                )"""
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _extensions(filename: str) -> list[str]:
        """Semua ekstensi berurutan, untuk deteksi ekstensi ganda (mis. "invoice.pdf.exe"
        -> [".pdf", ".exe"])."""
        return [suffix.casefold() for suffix in Path(filename or "").suffixes]

    def _classify_extension(self, exts: list[str]) -> tuple[str, str]:
        last_ext = exts[-1] if exts else ""
        if len(exts) > 1 and last_ext not in _HIGH_RISK_EXTENSIONS and any(
            ext in _HIGH_RISK_EXTENSIONS for ext in exts[:-1]
        ):
            return CRITICAL, f"Ekstensi ganda mencurigakan ({''.join(exts)}) — menyamarkan tipe asli."
        if last_ext in _HIGH_RISK_EXTENSIONS:
            return CRITICAL, f"Ekstensi {last_ext} termasuk tipe berisiko tinggi (executable/script)."
        if last_ext in _MACRO_EXTENSIONS:
            return HIGH, f"Ekstensi {last_ext} adalah dokumen macro-enabled, perlu review admin."
        if last_ext in _ARCHIVE_EXTENSIONS:
            return HIGH, f"Ekstensi {last_ext} adalah arsip, tidak diekstrak/dipercaya otomatis."
        if last_ext in _LOW_RISK_EXTENSIONS:
            return LOW, ""
        return MEDIUM, f"Ekstensi {last_ext or '(tidak ada)'} tidak dikenal/tidak biasa."

    def _store(self, data: bytes, filename: str, sha256: str) -> str:
        safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", Path(filename or "").name)[:120] or "berkas"
        dest = self.quarantine_dir / f"{sha256[:16]}-{safe_name}"
        dest.write_bytes(data)
        return str(dest)

    def _log(self, **fields) -> None:
        with self._connect() as db:
            db.execute(
                """INSERT INTO attachment_log
                   (created, sender_id, filename, declared_mime_type, sha256, size_bytes,
                    risk_level, reason, scan_status, allowed, quarantine_path)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    datetime.now().isoformat(timespec="seconds"), fields["sender_id"], fields["filename"],
                    fields["declared_mime_type"], fields["sha256"], fields["size_bytes"],
                    fields["risk_level"], fields["reason"], fields["scan_status"],
                    int(fields["allowed"]), fields["quarantine_path"],
                ),
            )

    def inspect(self, data: bytes, *, filename: str, declared_mime_type: str = "", sender_id: str) -> AttachmentDecision:
        """Jalankan pipeline lengkap: klasifikasi ekstensi -> validasi ukuran -> scanner
        opsional -> simpan ke quarantine (SELALU, apa pun risk level-nya) -> log audit.
        """
        exts = self._extensions(filename)
        risk_level, reason = self._classify_extension(exts)
        size = len(data)

        if size == 0:
            risk_level = _max_risk(risk_level, MEDIUM)
            reason = (reason + "; " if reason else "") + "File kosong (0 byte)."
        elif size > self.max_size_bytes:
            risk_level = _max_risk(risk_level, MEDIUM)
            reason = (reason + "; " if reason else "") + f"Ukuran {size} byte melewati batas {self.max_size_bytes} byte."

        scan_status = "tidak_ada_scanner"
        if self.scanner is not None:
            try:
                scanner_level, scanner_reason = self.scanner(data, filename)
            except Exception as exc:  # scanner eksternal opsional, tidak boleh jadi satu-satunya lapisan pertahanan
                scan_status = f"scanner_gagal: {exc}"
            else:
                scan_status = "selesai"
                if _risk_rank(scanner_level) > _risk_rank(risk_level):
                    risk_level = scanner_level
                    reason = (reason + "; " if reason else "") + scanner_reason

        sha256 = hashlib.sha256(data).hexdigest()
        # SELALU disimpan ke quarantine, apa pun risk level-nya — lihat docstring modul
        # poin 3. Pemanggil yang memutuskan langkah berikutnya berdasarkan `allowed`.
        quarantine_path = self._store(data, filename, sha256)
        allowed = risk_level in (LOW, MEDIUM)

        self._log(
            sender_id=sender_id, filename=filename or "(tanpa nama)", declared_mime_type=declared_mime_type,
            sha256=sha256, size_bytes=size, risk_level=risk_level,
            reason=reason or "Lolos validasi dasar.", scan_status=scan_status,
            allowed=allowed, quarantine_path=quarantine_path,
        )
        return AttachmentDecision(risk_level, reason or "Lolos validasi dasar.", quarantine_path, sha256, allowed)
