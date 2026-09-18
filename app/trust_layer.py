"""Security & Trust Layer — Fase 1 (`docs/roadmap_customer_channel_v1.md`).

Mengubah aturan di `policies/trust_spam_policy.md`, bagian "Aturan Trust & Spam" di
`agents/lead_agent.md`, aturan link/attachment di `policies/attachment_link_security.md`,
dan aturan "Isolasi Antar Pelanggan" di `policies/security_policy.md` menjadi satu fungsi
scoring bertahap yang dijalankan SEBELUM Lead Agent memproses isi pesan pelanggan.

Keputusan tidak pernah biner tolak/terima, mengikuti lima kategori trust score di
`policies/trust_spam_policy.md`:
    TRUSTED / LIKELY_CUSTOMER -> decision "proses"
    UNCERTAIN                -> decision "verifikasi"
    SPAM_SUSPECTED / HIGH_RISK -> decision "tolak_halus"

Fail-safe: permintaan data rahasia (OTP/password/API key), indikasi prompt injection,
dan permintaan data lintas pelanggan (lihat `security_policy.md` "Isolasi Antar
Pelanggan") selalu dipaksa ke HIGH_RISK apa pun skor numeriknya — konsisten dengan
prinsip "Jika ragu, jangan ambil tindakan berisiko tinggi" di trust_spam_policy.md.

Setiap evaluasi dicatat ke tabel `trust_events` (append-only, tidak pernah ditimpa atau
dihapus), mengikuti pola audit yang sama dengan `app/finance_corrections.py`. Isi pesan
yang disimpan sudah dipotong dan di-redact ringan agar tidak menyimpan token/secret
panjang, sesuai "Jangan simpan secret atau credential di log" di
`policies/attachment_link_security.md`.

Modul ini HANYA melakukan scoring pesan masuk. Penyaringan data per pelanggan
("lapis utama" isolasi data — query database difilter scope_id/order_id/nomor WA
milik pengirim sendiri) tetap menjadi tanggung jawab kode yang mengambil data
tersebut (lihat `docs/agent_memory_v1.md`), bukan modul ini.
"""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

TRUSTED = "TRUSTED"
LIKELY_CUSTOMER = "LIKELY_CUSTOMER"
UNCERTAIN = "UNCERTAIN"
SPAM_SUSPECTED = "SPAM_SUSPECTED"
HIGH_RISK = "HIGH_RISK"

_DECISION_BY_CATEGORY = {
    TRUSTED: "proses",
    LIKELY_CUSTOMER: "proses",
    UNCERTAIN: "verifikasi",
    SPAM_SUSPECTED: "tolak_halus",
    HIGH_RISK: "tolak_halus",
}

_SERVICE_WORDS = (
    "jasa", "pesan", "pesanan", "order", "cetak", "print", "makalah", "skripsi",
    "tugas", "foto", "photobooth", "sewa", "booking", "paket", "risol", "kue",
    "catering", "harga", "biaya", "produk", "layanan",
)

_QUANTITY_DEADLINE_PATTERN = re.compile(
    r"\d+\s*(lembar|halaman|pcs|pax|porsi|orang|jam|hari|minggu|bulan|buah|box|paket|set)"
    r"|deadline|besok|lusa|minggu depan|tanggal\s*\d",
    re.IGNORECASE,
)

_SECRET_REQUEST_PATTERN = re.compile(
    r"\b(otp|kode\s*otp|password|kata\s*sandi|api\s*key|apikey|kode\s*login|"
    r"kode\s*verifikasi|token\s*login|pin\s*atm)\b",
    re.IGNORECASE,
)

_PROMPT_INJECTION_PATTERN = re.compile(
    r"abaikan\s*(instruksi|aturan|perintah)|lupakan\s*aturan|ignore\s*(all\s*)?previous|"
    r"kamu\s*sekarang\s*(adalah|menjadi)|jailbreak|system\s*prompt|"
    r"bocorkan\s*(rahasia|system\s*prompt|prompt)|"
    r"berikan\s*(api\s*key|password|rahasia)|kirim(kan)?\s*(password|api\s*key)",
    re.IGNORECASE,
)

_CROSS_CUSTOMER_PATTERN = re.compile(
    r"pesanan\s*(si|milik)\s*\w+|data\s*pelanggan\s*lain|punya\s*pelanggan\s*lain|"
    r"punya\s*(customer|pelanggan)\s*lain|semua\s*pesanan|semua\s*order|rekap\s*semua|"
    r"data\s*(semua\s*)?pelanggan|nomor\s*(hp|wa|telepon)\s*pelanggan\s*lain",
    re.IGNORECASE,
)

_PROMO_SPAM_WORDS = (
    "promo spesial", "investasi", "klik link", "menang undian", "hadiah gratis",
    "kerja part time", "gaji harian", "modal kecil untung besar", "loker harian",
)

_URL_PATTERN = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)

_SHORTENER_DOMAINS = {
    "bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "s.id",
    "tiny.cc", "rb.gy", "shorturl.at", "linktr.ee",
}

_HIGH_RISK_LINK_SUFFIXES = (".apk", ".exe", ".scr", ".bat", ".msi", ".jar")

_LONG_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_\-]{20,}")


def _category_for_score(score: int) -> str:
    if score >= 80:
        return TRUSTED
    if score >= 60:
        return LIKELY_CUSTOMER
    if score >= 40:
        return UNCERTAIN
    if score >= 20:
        return SPAM_SUSPECTED
    return HIGH_RISK


def _is_suspicious_link(url: str) -> bool:
    lowered = url.lower()
    if lowered.endswith(_HIGH_RISK_LINK_SUFFIXES):
        return True
    domain_match = re.search(r"https?://(?:www\.)?([^/\s]+)|www\.([^/\s]+)", lowered)
    domain = ""
    if domain_match:
        domain = domain_match.group(1) or domain_match.group(2) or ""
    if any(domain == shortener or domain.endswith("." + shortener) for shortener in _SHORTENER_DOMAINS):
        return True
    if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?", domain):
        return True
    return False


def _redact(text: str) -> str:
    """Ganti token panjang (kemungkinan API key/password/OTP) dengan placeholder sebelum disimpan ke log."""
    return _LONG_TOKEN_PATTERN.sub("[REDACTED]", text)


@dataclass(frozen=True)
class TrustResult:
    sender_id: str
    category: str
    decision: str
    score: int
    signals: tuple[str, ...] = field(default_factory=tuple)
    reasons: tuple[str, ...] = field(default_factory=tuple)
    event_id: str = ""


class TrustLayer:
    """Scoring trust/spam bertahap untuk pesan pelanggan, dengan audit log append-only."""

    RATE_LIMIT_WINDOW_SECONDS = 60
    RATE_LIMIT_MAX_MESSAGES = 5
    POSITIVE_HISTORY_THRESHOLD = 2

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS trust_events (
                id TEXT PRIMARY KEY,
                created TEXT NOT NULL,
                sender_id TEXT NOT NULL,
                message_excerpt TEXT NOT NULL,
                score INTEGER NOT NULL,
                category TEXT NOT NULL,
                decision TEXT NOT NULL,
                signals TEXT NOT NULL
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_trust_events_sender ON trust_events(sender_id, created)")

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def evaluate(self, sender_id: str, message: str, *, has_attachment: bool = False) -> TrustResult:
        """Nilai satu pesan pelanggan dan catat hasilnya ke audit log.

        Tidak melempar exception untuk isi pesan apa pun (pesan pelanggan dianggap
        untrusted input); hanya `sender_id` kosong yang dianggap kesalahan pemanggil.
        """
        sender_id = (sender_id or "").strip()
        if not sender_id:
            raise ValueError("sender_id wajib diisi untuk evaluasi trust.")
        raw = (message or "").strip()

        score = 50
        signals: list[str] = []
        reasons: list[str] = []
        force_high_risk = False

        def add(delta: int, signal: str, reason: str) -> None:
            nonlocal score
            score += delta
            signals.append(signal)
            reasons.append(reason)

        if not raw and not has_attachment:
            add(-10, "pesan_kosong", "Pesan kosong tanpa teks maupun lampiran.")

        if _SECRET_REQUEST_PATTERN.search(raw):
            add(-60, "permintaan_data_rahasia", "Pesan meminta OTP/password/API key/kode login.")
            force_high_risk = True

        if _PROMPT_INJECTION_PATTERN.search(raw):
            add(-60, "indikasi_prompt_injection", "Pesan mencoba mengubah aturan/perintah agent (prompt injection).")
            force_high_risk = True

        if _CROSS_CUSTOMER_PATTERN.search(raw):
            add(-50, "permintaan_data_lintas_pelanggan",
                "Pesan meminta data/pesanan milik pelanggan lain atau rekap semua order — "
                "hanya channel admin terautentikasi yang boleh mengakses ini.")
            force_high_risk = True

        links = _URL_PATTERN.findall(raw)
        if links:
            suspicious_links = [link for link in links if _is_suspicious_link(link)]
            if suspicious_links:
                add(-30, "link_mencurigakan",
                    f"Pesan berisi link yang perlu pemeriksaan tambahan: {', '.join(suspicious_links[:3])}.")
            else:
                add(-5, "berisi_link", "Pesan berisi link; belum ditandai berisiko tinggi tapi tetap perlu perhatian.")

        lowered = raw.casefold()
        if any(word in lowered for word in _PROMO_SPAM_WORDS):
            add(-25, "pola_promosi_massal", "Pesan berpola promosi/undian massal yang umum dipakai spam.")

        if any(word in lowered for word in _SERVICE_WORDS):
            add(10, "kebutuhan_jasa_disebut", "Pesan menyebut kebutuhan jasa/layanan yang jelas.")

        if _QUANTITY_DEADLINE_PATTERN.search(raw):
            add(12, "detail_jumlah_atau_waktu", "Pesan menyertakan jumlah/ukuran/deadline yang konkret.")

        if has_attachment:
            add(12, "lampiran_dikirim", "Pelanggan mengirim file/foto terkait pesanan.")

        with self.connect() as db:
            recent_count = self._recent_message_count(db, sender_id, self.RATE_LIMIT_WINDOW_SECONDS)
            if recent_count >= self.RATE_LIMIT_MAX_MESSAGES:
                add(-20, "pesan_berulang_cepat",
                    f"Terdeteksi {recent_count + 1} pesan dari pengirim yang sama dalam "
                    f"{self.RATE_LIMIT_WINDOW_SECONDS} detik terakhir.")

            positive_history = self._positive_history_count(db, sender_id)
            if positive_history >= self.POSITIVE_HISTORY_THRESHOLD:
                add(10, "riwayat_positif", "Pengirim punya riwayat interaksi wajar sebelumnya.")

            score = max(0, min(100, score))
            category = _category_for_score(score)
            if force_high_risk and category not in (HIGH_RISK, SPAM_SUSPECTED):
                category = HIGH_RISK
            decision = _DECISION_BY_CATEGORY[category]

            event_id = str(uuid.uuid4())
            created = datetime.now().isoformat(timespec="seconds")
            excerpt = _redact(raw)[:300]
            db.execute(
                """INSERT INTO trust_events(id,created,sender_id,message_excerpt,score,category,decision,signals)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (event_id, created, sender_id, excerpt, score, category, decision,
                 json.dumps(signals, ensure_ascii=False)),
            )

        return TrustResult(sender_id, category, decision, score, tuple(signals), tuple(reasons), event_id)

    def _recent_message_count(self, db: sqlite3.Connection, sender_id: str, window_seconds: int) -> int:
        cutoff = (datetime.now() - timedelta(seconds=window_seconds)).isoformat(timespec="seconds")
        row = db.execute(
            "SELECT COUNT(*) FROM trust_events WHERE sender_id=? AND created>=?",
            (sender_id, cutoff),
        ).fetchone()
        return int(row[0]) if row else 0

    def _positive_history_count(self, db: sqlite3.Connection, sender_id: str) -> int:
        row = db.execute(
            "SELECT COUNT(*) FROM trust_events WHERE sender_id=? AND decision='proses'",
            (sender_id,),
        ).fetchone()
        return int(row[0]) if row else 0

    def history(self, sender_id: str, limit: int = 20) -> list[dict]:
        """Riwayat evaluasi trust satu pengirim, terbaru dulu — untuk admin/audit, bukan untuk pelanggan lain."""
        with self.connect() as db:
            rows = db.execute(
                """SELECT id,created,sender_id,message_excerpt,score,category,decision,signals
                   FROM trust_events WHERE sender_id=? ORDER BY created DESC, rowid DESC LIMIT ?""",
                (sender_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]
