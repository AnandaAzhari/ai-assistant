"""Finance Agent runtime minimum.

V0.2 menyimpan ledger lokal di SQLite. Uang disimpan sebagai integer rupiah.
Tidak ada koneksi bank, pembayaran otomatis, atau hard-delete transaksi.
Kategori dapat tumbuh dari transaksi nyata dengan normalisasi sederhana.
"""

from __future__ import annotations

import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from app.finance_query import FinanceQueryInterpreter


ACCOUNTS = (
    "Cash", "BCA", "BNI", "SeaBank", "Jago", "QRIS", "DANA", "GoPay", "ShopeePay"
)
BUSINESSES = (
    "Taqi Desk", "Pixiva.ID", "Computer Service", "Risol Mamqi", "Personal"
)

CATEGORY_RULES = {
    "expense": (
        ((
            "top up saldo dana istri", "top up istri", "transfer istri", "kirim ke istri", "uang istri",
            "top up saldo suami", "top up suami", "transfer suami", "kirim ke suami", "uang suami",
            "uang anak", "untuk anak", "uang keluarga", "untuk keluarga"
        ), "Keluarga"),
        (("tinta", "toner"), "Tinta Printer"),
        (("kertas", "hvs", "a4", "f4"), "Kertas"),
        (("internet", "wifi", "wi-fi"), "Internet"),
        (("listrik", "token pln", "pln"), "Listrik"),
        (("ongkir", "kurir", "pengiriman"), "Ongkir"),
        (("bbm", "bensin", "pertalite", "pertamax", "solar"), "BBM"),
        (("parkir",), "Parkir"),
        (("iklan", "ads", "promosi"), "Marketing/Iklan"),
        (("software", "langganan", "subscription"), "Software/Langganan"),
        (("makan", "minum", "kopi"), "Makan & Minum"),
        (("service", "servis", "perawatan"), "Perawatan/Service"),
    ),
    "income": (
        (("print", "cetak", "fotocopy", "fotokopi"), "Jasa Cetak/Fotocopy"),
        (("photobooth", "foto booth"), "Photobooth"),
        (("install windows", "service komputer", "servis komputer"), "Service Komputer"),
        (("risol", "makanan"), "Penjualan Makanan"),
        (("jasa",), "Pendapatan Jasa"),
    ),
}


@dataclass(frozen=True)
class FinanceResult:
    status: str
    text: str


def rupiah(value: int) -> str:
    sign = "-" if value < 0 else ""
    return sign + "Rp" + f"{abs(value):,}".replace(",", ".")


def parse_amount(text: str) -> int | None:
    """Ambil nominal pertama yang wajar dari bahasa Indonesia sederhana."""
    patterns = (
        r"(?<!\w)(\d+(?:[.,]\d+)?)\s*(juta|jt)(?!\w)",
        r"(?<!\w)(\d+(?:[.,]\d+)?)\s*(ribu|rb|k)(?!\w)",
        r"(?<!\w)(\d{1,3}(?:\.\d{3})+|\d{4,12})(?!\w)",
    )
    lowered = text.casefold()
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if not match:
            continue
        raw = match.group(1)
        unit = match.group(2) if match.lastindex and match.lastindex >= 2 else ""
        if unit in {"juta", "jt"}:
            number = float(raw.replace(",", "."))
            return int(round(number * 1_000_000))
        if unit in {"ribu", "rb", "k"}:
            number = float(raw.replace(",", "."))
            return int(round(number * 1_000))
        return int(raw.replace(".", ""))
    return None


def detect_account(text: str) -> str | None:
    """Deteksi akun sumber pembayaran.

    Frasa eksplisit seperti `pakai BNI` atau `dari BCA` diprioritaskan agar nama
    akun yang hanya muncul sebagai tujuan/keterangan (mis. `saldo DANA istri`)
    tidak salah dianggap sebagai akun sumber.
    """
    lowered = text.casefold()
    aliases = {
        "cash": "Cash", "tunai": "Cash", "bca": "BCA", "bni": "BNI",
        "seabank": "SeaBank", "sea bank": "SeaBank", "jago": "Jago",
        "bank jago": "Jago", "qris": "QRIS", "dana": "DANA",
        "gopay": "GoPay", "go pay": "GoPay", "shopeepay": "ShopeePay",
        "shopee pay": "ShopeePay",
    }

    marker = r"(?:pakai|menggunakan|via|dari|akun|metode(?:\s+pembayaran)?|bayar(?:\s+pakai)?|dibayar\s+dengan)"
    for alias in sorted(aliases, key=len, reverse=True):
        if re.search(rf"(?<!\w){marker}\s+{re.escape(alias)}(?!\w)", lowered):
            return aliases[alias]

    for alias in sorted(aliases, key=len, reverse=True):
        if re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", lowered):
            return aliases[alias]
    return None


def detect_business(text: str) -> str | None:
    """Deteksi unit usaha atau konteks Personal.

    Nama usaha eksplisit selalu menang. Untuk catatan rumah tangga yang jelas,
    seperti top up untuk istri/anak, sistem dapat menyimpulkan `Personal`
    tanpa memaksa user menulis kata Personal setiap kali.
    """
    lowered = text.casefold()
    aliases = {
        # "Taqi DocuTech" nama lama (rebrand 19 September 2026) — tetap dikenali
        # sebagai alias supaya kebiasaan lama tidak tiba-tiba gagal tercatat.
        "taqi docutech": "Taqi Desk", "docutech": "Taqi Desk",
        "taqi desk": "Taqi Desk", "taqidesk": "Taqi Desk",
        "pixiva.id": "Pixiva.ID", "pixiva": "Pixiva.ID",
        "computer service": "Computer Service", "service komputer": "Computer Service",
        "risol mamqi": "Risol Mamqi", "mamqi": "Risol Mamqi",
        "personal": "Personal", "pribadi": "Personal",
    }
    for alias in sorted(aliases, key=len, reverse=True):
        if alias in lowered:
            return aliases[alias]

    personal_patterns = (
        r"\b(?:top\s*up|transfer|kirim|uang|saldo)\b.*\b(?:istri|suami|anak)\b",
        r"\b(?:beli|belanja|bayar)\b.*\b(?:untuk|buat)\s+(?:istri|suami|anak|keluarga)\b",
        r"\b(?:untuk|buat|ke)\s+(?:istri|suami|anak|keluarga)\b",
        r"\bkebutuhan\s+(?:rumah|keluarga|pribadi)\b",
        r"\brumah\s+tangga\b",
    )
    if any(re.search(pattern, lowered) for pattern in personal_patterns):
        return "Personal"
    return None


def detect_kind(text: str) -> str | None:
    lowered = text.casefold()
    if any(word in lowered for word in ("pengeluaran", "catat keluar", "keluar ", "beli ", "belanja ")):
        return "expense"
    if any(word in lowered for word in ("pemasukan", "catat masuk", "masuk ", "pendapatan", "terima ")):
        return "income"
    return None


def normalize_category_name(value: str) -> str:
    value = re.sub(r"\s+", " ", value.strip(" .,:;-_"))
    if not value:
        return ""
    if len(value) > 60:
        value = value[:60].rstrip()
    # Pertahankan singkatan umum, judul lain dibuat mudah dibaca.
    words = []
    for word in value.split():
        upper = word.upper()
        if upper in {"BBM", "PLN", "USB", "SSD", "RAM", "QRIS", "HP", "PC"}:
            words.append(upper)
        else:
            words.append(word[:1].upper() + word[1:].lower())
    return " ".join(words)


def explicit_category(text: str) -> str | None:
    match = re.search(
        r"\bkategori\s*[:=]?\s+(.+?)(?=\s+(?:untuk|pakai|via|dari|metode|akun)\b|[,.]|$)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    value = normalize_category_name(match.group(1))
    return value or None


def category_phrase(text: str, kind: str) -> str | None:
    """Ambil frasa kegunaan singkat untuk kategori baru bila aturan belum cocok.

    Ini sengaja konservatif: jika frasa tidak cukup jelas, caller harus meminta
    user menuliskan `kategori ...` daripada membuat kategori acak.
    """
    cleaned = text.casefold()
    # Buang prefix transaksi dan nominal agar frasa inti lebih mudah diambil.
    cleaned = re.sub(r"\b(?:catat\s+)?(?:pengeluaran|pemasukan|keluar|masuk|pendapatan)\b", " ", cleaned)
    cleaned = re.sub(r"\b\d+(?:[.,]\d+)?\s*(?:juta|jt|ribu|rb|k)\b", " ", cleaned)
    cleaned = re.sub(r"\b(?:\d{1,3}(?:\.\d{3})+|\d{4,12})\b", " ", cleaned)

    starters = r"beli|belanja|bayar" if kind == "expense" else r"terima|dapat|penjualan|jual"
    match = re.search(
        rf"\b(?:{starters})\b\s+(.+?)(?=\s+(?:untuk|pakai|via|dengan|dari|ke|metode|akun)\b|[,.]|$)",
        cleaned,
    )
    phrase = match.group(1) if match else ""
    if not phrase and kind == "income":
        # Contoh: "pemasukan 100 ribu desain poster untuk Pixiva pakai BCA".
        match = re.search(r"^\s*(.+?)(?=\s+(?:untuk|pakai|via|dengan|dari|ke|metode|akun)\b|[,.]|$)", cleaned)
        phrase = match.group(1) if match else ""

    phrase = re.sub(r"\bkategori\b.*$", "", phrase).strip()
    phrase = re.sub(r"\s+", " ", phrase)
    filler = {"buat", "keperluan", "kebutuhan", "barang", "sesuatu", "lainnya", "lain"}
    words = [word for word in phrase.split() if word not in filler]
    if not words or len(words) > 5:
        return None
    result = normalize_category_name(" ".join(words))
    if len(result) < 3:
        return None
    return result


class FinanceService:
    def __init__(
        self, db_path: str | Path = "data/assistant.db", *,
        query_interpreter: FinanceQueryInterpreter | None = None,
    ):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # Lapisan AI-first opsional untuk pertanyaan keuangan bebas (lihat
        # `app/finance_query.py`). None/tidak dikonfigurasi = perilaku lama persis
        # (hanya command tetap + pencatatan deterministik), tidak ada perubahan.
        self.query_interpreter = query_interpreter
        self._migrate()

    def connect(self):
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _migrate(self) -> None:
        with self.connect() as db:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("""CREATE TABLE IF NOT EXISTS finance_accounts (
                name TEXT PRIMARY KEY,
                opening_balance INTEGER NOT NULL DEFAULT 0 CHECK(opening_balance >= 0),
                active INTEGER NOT NULL DEFAULT 1
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS finance_categories (
                name TEXT NOT NULL,
                kind TEXT NOT NULL CHECK(kind IN ('income','expense')),
                created TEXT NOT NULL,
                PRIMARY KEY(name, kind)
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS finance_category_aliases (
                alias TEXT NOT NULL,
                kind TEXT NOT NULL CHECK(kind IN ('income','expense')),
                category TEXT NOT NULL,
                created TEXT NOT NULL,
                PRIMARY KEY(alias, kind)
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS finance_transactions (
                id TEXT PRIMARY KEY,
                created TEXT NOT NULL,
                kind TEXT NOT NULL CHECK(kind IN ('income','expense')),
                amount INTEGER NOT NULL CHECK(amount > 0),
                account TEXT NOT NULL REFERENCES finance_accounts(name),
                business TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                source TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'confirmed'
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS finance_tx_created ON finance_transactions(created)")
            db.execute("CREATE INDEX IF NOT EXISTS finance_tx_account ON finance_transactions(account)")
            db.execute("CREATE INDEX IF NOT EXISTS finance_tx_business ON finance_transactions(business)")
            db.execute("CREATE INDEX IF NOT EXISTS finance_tx_category ON finance_transactions(category)")
            db.executemany(
                "INSERT OR IGNORE INTO finance_accounts(name, opening_balance, active) VALUES(?,0,1)",
                [(name,) for name in ACCOUNTS],
            )
            # Rebrand 19 September 2026: "Taqi DocuTech" -> "Taqi Desk". Transaksi lama
            # yang sudah tercatat dengan nama bisnis lama disatukan ke nama baru supaya
            # laporan (saldo/laba-rugi/breakdown per usaha) tidak terpecah dua. Aman
            # dijalankan berkali-kali (no-op setelah baris lama habis dimigrasikan).
            db.execute(
                "UPDATE finance_transactions SET business='Taqi Desk' WHERE business='Taqi DocuTech'"
            )

    def set_opening_balance(self, account: str, amount: int) -> None:
        if account not in ACCOUNTS:
            raise ValueError("Akun belum dikenal.")
        if type(amount) is not int or not 0 <= amount <= 1_000_000_000_000:
            raise ValueError("Saldo awal harus rupiah bulat antara Rp0 dan Rp1 triliun.")
        with self.connect() as db:
            count = db.execute(
                "SELECT COUNT(*) FROM finance_transactions WHERE account=? AND status='confirmed'",
                (account,),
            ).fetchone()[0]
            if count:
                raise ValueError(
                    "Saldo awal tidak boleh diubah setelah akun memiliki transaksi. "
                    "Gunakan transaksi koreksi/adjustment pada tahap berikutnya."
                )
            db.execute("UPDATE finance_accounts SET opening_balance=? WHERE name=?", (amount, account))

    def account_rows(self) -> list[dict]:
        balances = self.balances()
        with self.connect() as db:
            rows = db.execute(
                "SELECT name, opening_balance FROM finance_accounts WHERE active=1 ORDER BY name"
            ).fetchall()
        return [
            {"name": row["name"], "opening_balance": int(row["opening_balance"]), "balance": balances[row["name"]]}
            for row in rows
        ]

    def categories(self) -> list[dict]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT name,kind FROM finance_categories ORDER BY kind,name COLLATE NOCASE"
            ).fetchall()
        return [{"name": row["name"], "kind": row["kind"]} for row in rows]

    def _learn_alias(self, alias: str | None, kind: str, category: str) -> None:
        if not alias:
            return
        alias_key = re.sub(r"\s+", " ", alias.casefold().strip())
        if len(alias_key) < 3 or len(alias_key) > 80:
            return
        with self.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO finance_category_aliases(alias,kind,category,created) VALUES(?,?,?,?)",
                (alias_key, kind, category, datetime.now().isoformat(timespec="seconds")),
            )

    def resolve_category(self, text: str, kind: str) -> tuple[str | None, bool]:
        explicit = explicit_category(text)
        phrase = category_phrase(text, kind)
        if explicit:
            with self.connect() as db:
                exists = db.execute(
                    "SELECT 1 FROM finance_categories WHERE name=? AND kind=?", (explicit, kind)
                ).fetchone() is not None
            self._learn_alias(phrase, kind, explicit)
            return explicit, not exists

        lowered = text.casefold()
        for keywords, category in CATEGORY_RULES.get(kind, ()):
            if any(keyword in lowered for keyword in keywords):
                with self.connect() as db:
                    exists = db.execute(
                        "SELECT 1 FROM finance_categories WHERE name=? AND kind=?", (category, kind)
                    ).fetchone() is not None
                return category, not exists

        with self.connect() as db:
            aliases = db.execute(
                "SELECT alias,category FROM finance_category_aliases WHERE kind=? ORDER BY length(alias) DESC",
                (kind,),
            ).fetchall()
        for row in aliases:
            if row["alias"] in lowered:
                return row["category"], False

        if phrase:
            with self.connect() as db:
                exists = db.execute(
                    "SELECT 1 FROM finance_categories WHERE name=? AND kind=?", (phrase, kind)
                ).fetchone() is not None
            self._learn_alias(phrase, kind, phrase)
            return phrase, not exists
        return None, False

    def record(self, *, kind: str, amount: int, account: str, business: str,
               category: str, description: str, source: str = "web_admin") -> str:
        if kind not in {"income", "expense"}:
            raise ValueError("Jenis transaksi tidak valid.")
        if type(amount) is not int or not 1 <= amount <= 1_000_000_000_000:
            raise ValueError("Nominal harus rupiah bulat lebih dari nol.")
        if account not in ACCOUNTS:
            raise ValueError("Akun pembayaran belum dikenal.")
        if business not in BUSINESSES:
            raise ValueError("Usaha belum dikenal.")
        category = normalize_category_name(category)
        if not category:
            raise ValueError("Kategori transaksi kosong.")
        description = description.strip()
        if not description:
            raise ValueError("Deskripsi transaksi kosong.")
        created = datetime.now().isoformat(timespec="seconds")
        ident = str(uuid.uuid4())
        with self.connect() as db:
            duplicate = db.execute(
                """SELECT id FROM finance_transactions
                   WHERE kind=? AND amount=? AND account=? AND business=? AND description=?
                   AND created>=? LIMIT 1""",
                (kind, amount, account, business, description,
                 (datetime.now() - timedelta(seconds=30)).isoformat(timespec="seconds")),
            ).fetchone()
            if duplicate:
                raise ValueError("Transaksi sangat mirip baru saja dicatat. Periksa agar tidak duplikat.")
            db.execute(
                "INSERT OR IGNORE INTO finance_categories(name,kind,created) VALUES(?,?,?)",
                (category, kind, created),
            )
            db.execute(
                """INSERT INTO finance_transactions
                   (id,created,kind,amount,account,business,category,description,source,status)
                   VALUES(?,?,?,?,?,?,?,?,?,'confirmed')""",
                (ident, created, kind, amount, account, business, category, description, source),
            )
        return ident

    def balances(self) -> dict[str, int]:
        with self.connect() as db:
            rows = db.execute("""SELECT a.name, a.opening_balance + COALESCE(SUM(
                    CASE WHEN t.kind='income' THEN t.amount WHEN t.kind='expense' THEN -t.amount ELSE 0 END
                ),0) AS balance
                FROM finance_accounts a
                LEFT JOIN finance_transactions t ON t.account=a.name AND t.status='confirmed'
                WHERE a.active=1
                GROUP BY a.name,a.opening_balance
                ORDER BY a.name""").fetchall()
        return {row["name"]: int(row["balance"]) for row in rows}

    def summary(self, start: str, end: str, *, business: str | None = None) -> dict[str, int]:
        query = """SELECT kind, COALESCE(SUM(amount),0) AS total, COUNT(*) AS count
                   FROM finance_transactions
                   WHERE status='confirmed' AND created>=? AND created<?"""
        params: list = [start, end]
        if business:
            query += " AND business=?"
            params.append(business)
        query += " GROUP BY kind"
        with self.connect() as db:
            rows = db.execute(query, params).fetchall()
        result = {"income": 0, "expense": 0, "count": 0}
        for row in rows:
            result[row["kind"]] = int(row["total"])
            result["count"] += int(row["count"])
        result["net"] = result["income"] - result["expense"]
        return result

    @staticmethod
    def _day_bounds(now: datetime) -> tuple[datetime, datetime]:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, start + timedelta(days=1)

    @staticmethod
    def _week_bounds(now: datetime) -> tuple[datetime, datetime]:
        # Minggu dimulai Senin (ISO), mengikuti kebiasaan bisnis Indonesia — bukan
        # "7 hari terakhir" yang bergeser tiap hari dan sulit dibandingkan minggu ke minggu.
        start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        return start, start + timedelta(days=7)

    @staticmethod
    def _month_bounds(now: datetime) -> tuple[datetime, datetime]:
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        return start, end

    def _period_bounds(self, period: str) -> tuple[datetime, datetime]:
        """Resolve salah satu `app.finance_query.ALLOWED_PERIODS` ke rentang datetime
        aktual, dipakai jalur pertanyaan bebas (`_answer_free_form_query`). Dipisah
        dari `_day_bounds`/`_week_bounds`/`_month_bounds` supaya kata kunci periode
        baru (kemarin, minggu lalu, bulan lalu) tidak mengubah perilaku command tetap
        lama (`/hari_ini`, `/minggu_ini`, `/bulan_ini`) yang masih memakai method asli."""
        now = datetime.now()
        if period == "hari_ini":
            return self._day_bounds(now)
        if period == "kemarin":
            return self._day_bounds(now - timedelta(days=1))
        if period == "minggu_ini":
            return self._week_bounds(now)
        if period == "minggu_lalu":
            return self._week_bounds(now - timedelta(days=7))
        if period == "bulan_ini":
            return self._month_bounds(now)
        if period == "bulan_lalu":
            start_this_month, _ = self._month_bounds(now)
            return self._month_bounds(start_this_month - timedelta(days=1))
        raise ValueError("Periode tidak dikenal.")

    def today_summary(self, *, business: str | None = None) -> dict[str, int]:
        start, end = self._day_bounds(datetime.now())
        return self.summary(start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds"), business=business)

    def week_summary(self, *, business: str | None = None) -> dict[str, int]:
        start, end = self._week_bounds(datetime.now())
        return self.summary(start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds"), business=business)

    def month_summary(self, *, business: str | None = None) -> dict[str, int]:
        start, end = self._month_bounds(datetime.now())
        return self.summary(start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds"), business=business)

    def category_breakdown(
        self, start: str, end: str, kind: str, *, business: str | None = None,
    ) -> list[dict]:
        """Rincian total per kategori untuk satu `kind` ('income'/'expense') dalam
        rentang waktu tertentu, diurutkan dari nominal terbesar. Dasar untuk laporan
        laba/rugi (`profit_loss`) — dipisah jadi method sendiri supaya bisa dipakai
        ulang untuk laporan lain tanpa duplikasi query."""
        query = """SELECT category, COALESCE(SUM(amount),0) AS total, COUNT(*) AS count
                   FROM finance_transactions
                   WHERE status='confirmed' AND kind=? AND created>=? AND created<?"""
        params: list = [kind, start, end]
        if business:
            query += " AND business=?"
            params.append(business)
        query += " GROUP BY category ORDER BY total DESC"
        with self.connect() as db:
            rows = db.execute(query, params).fetchall()
        return [{"category": row["category"], "total": int(row["total"]), "count": int(row["count"])} for row in rows]

    def profit_loss(self, start: str, end: str, *, business: str | None = None) -> dict:
        """Laba/rugi sederhana untuk satu usaha (atau semua usaha kalau `business`
        kosong): total pendapatan, rincian pengeluaran per kategori, total
        pengeluaran, dan laba/rugi bersih. TIDAK memisahkan HPP/beban operasional
        secara akuntansi formal (di luar cakupan V1 — lihat `docs/finance_saas_v1.md`
        "Batas V1"); ini murni pendapatan dikurangi seluruh pengeluaran tercatat."""
        totals = self.summary(start, end, business=business)
        expense_breakdown = self.category_breakdown(start, end, "expense", business=business)
        return {
            "income": totals["income"],
            "expense": totals["expense"],
            "net": totals["net"],
            "count": totals["count"],
            "expense_breakdown": expense_breakdown,
        }

    def cash_flow(self, start: str, end: str, *, account: str | None = None) -> list[dict]:
        """Arus kas per akun untuk rentang waktu tertentu: saldo awal (posisi TEPAT
        sebelum `start`), total masuk, total keluar, dan saldo akhir periode. Kalau
        `account` tidak diisi, mengembalikan satu baris per akun aktif. Saldo awal
        dihitung dari `opening_balance` akun + seluruh transaksi confirmed SEBELUM
        `start` (bukan cuma dari tanggal berjalan), supaya laporan tetap benar untuk
        periode mana pun, bukan cuma bulan/minggu berjalan."""
        with self.connect() as db:
            account_query = "SELECT name, opening_balance FROM finance_accounts WHERE active=1"
            account_params: list = []
            if account:
                account_query += " AND name=?"
                account_params.append(account)
            account_query += " ORDER BY name"
            accounts = db.execute(account_query, account_params).fetchall()

            results = []
            for row in accounts:
                name, opening_balance = row["name"], int(row["opening_balance"])
                before = db.execute(
                    """SELECT COALESCE(SUM(CASE WHEN kind='income' THEN amount WHEN kind='expense' THEN -amount ELSE 0 END),0) AS delta
                       FROM finance_transactions WHERE status='confirmed' AND account=? AND created<?""",
                    (name, start),
                ).fetchone()["delta"]
                period = db.execute(
                    """SELECT
                           COALESCE(SUM(CASE WHEN kind='income' THEN amount ELSE 0 END),0) AS in_total,
                           COALESCE(SUM(CASE WHEN kind='expense' THEN amount ELSE 0 END),0) AS out_total
                       FROM finance_transactions
                       WHERE status='confirmed' AND account=? AND created>=? AND created<?""",
                    (name, start, end),
                ).fetchone()
                opening = opening_balance + int(before)
                results.append({
                    "account": name,
                    "opening": opening,
                    "in_total": int(period["in_total"]),
                    "out_total": int(period["out_total"]),
                    "closing": opening + int(period["in_total"]) - int(period["out_total"]),
                })
        return results

    def search(self, keyword: str, *, limit: int = 10) -> list[dict]:
        """Cari transaksi (confirmed) yang deskripsi/kategori/usahanya mengandung
        `keyword`, terbaru lebih dulu. Dipakai Lead Agent (/cari_riwayat) supaya
        angka yang ditampilkan tetap dari data ledger asli (tidak pernah dikarang
        AI), sama seperti jalur Finance Agent lain di modul ini."""
        keyword = (keyword or "").strip()
        if not keyword:
            return []
        pattern = "%" + keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        with self.connect() as db:
            rows = db.execute(
                """SELECT kind, amount, account, business, category, description, created
                   FROM finance_transactions
                   WHERE status='confirmed' AND (
                       description LIKE ? ESCAPE '\\' OR category LIKE ? ESCAPE '\\'
                       OR business LIKE ? ESCAPE '\\' OR account LIKE ? ESCAPE '\\')
                   ORDER BY created DESC LIMIT ?""",
                (pattern, pattern, pattern, pattern, limit),
            ).fetchall()
        return [
            {
                "kind": row["kind"], "amount": int(row["amount"]), "account": row["account"],
                "business": row["business"], "category": row["category"],
                "description": row["description"], "created": row["created"],
            }
            for row in rows
        ]

    def _answer_free_form_query(self, raw: str) -> FinanceResult | None:
        """Coba jawab pertanyaan keuangan bebas lewat AI classifier
        (`self.query_interpreter`). AI HANYA mengklasifikasikan field (report_type,
        period, business, account, kind) — angka jawaban tetap dihitung dari database
        asli lewat method yang sama dipakai command tetap (`summary`, `profit_loss`,
        `cash_flow`, dst), sama seperti pola hallucination-prevention di seluruh agent
        lain (lihat `policies/security_policy.md`).

        Mengembalikan None kalau AI gagal/tidak yakin/hasil tidak valid/pesannya
        ternyata bukan pertanyaan laporan (report_type == "tidak_relevan"), supaya
        caller (`handle`) selalu jatuh ke jalur command/pencatatan deterministik lama
        sebagai fallback — perilaku lama (dan seluruh test yang sudah ada) tidak pernah
        berubah."""
        result = self.query_interpreter.interpret(raw)
        if result.status != "berhasil" or result.report_type == "tidak_relevan":
            return None
        if result.report_type == "tidak_didukung":
            return FinanceResult(
                "membutuhkan_bantuan",
                "Laporan itu belum bisa saya buat otomatis (mis. tren 12 bulan, "
                "piutang/utang, atau tanggal spesifik di masa lalu belum didukung). "
                "Coba /bantuan untuk melihat laporan yang sudah tersedia.",
            )

        business = result.business or None
        if business and business not in BUSINESSES:
            return FinanceResult(
                "needs_review",
                f"Usaha \"{business}\" tidak dikenali. Usaha yang tersedia: " + ", ".join(BUSINESSES) + ".",
            )
        account = result.account or None
        if account and account not in ACCOUNTS:
            return FinanceResult(
                "needs_review",
                f"Akun \"{account}\" tidak dikenali. Akun yang tersedia: " + ", ".join(ACCOUNTS) + ".",
            )
        kind_filter = result.kind or None
        if kind_filter and kind_filter not in {"income", "expense"}:
            return None
        try:
            start, end = self._period_bounds(result.period)
        except ValueError:
            return None

        period_labels = {
            "hari_ini": "Hari ini", "kemarin": "Kemarin", "minggu_ini": "Minggu ini",
            "minggu_lalu": "Minggu lalu", "bulan_ini": "Bulan ini", "bulan_lalu": "Bulan lalu",
        }
        label = period_labels.get(result.period, "Periode ini")
        start_iso = start.isoformat(timespec="seconds")
        end_iso = end.isoformat(timespec="seconds")
        scope_note = f" ({business})" if business else ""

        if result.report_type == "saldo":
            balances = self.balances()
            if account:
                if account not in balances:
                    return None
                return FinanceResult("berhasil", f"Saldo {account} saat ini: {rupiah(balances[account])}")
            lines = [f"{name}: {rupiah(value)}" for name, value in balances.items()]
            return FinanceResult("berhasil", "Saldo ledger saat ini:\n" + "\n".join(lines))

        if result.report_type == "kategori_breakdown":
            effective_kind = kind_filter or "expense"
            rows = self.category_breakdown(start_iso, end_iso, effective_kind, business=business)
            kind_label = "Pemasukan" if effective_kind == "income" else "Pengeluaran"
            if not rows:
                return FinanceResult(
                    "berhasil", f"{label}{scope_note} — belum ada {kind_label.lower()} tercatat."
                )
            lines = [f"{label}{scope_note} — {kind_label} per kategori:"]
            lines.extend(f"  - {row['category']}: {rupiah(row['total'])}" for row in rows)
            return FinanceResult("berhasil", "\n".join(lines))

        if result.report_type == "laba_rugi":
            data = self.profit_loss(start_iso, end_iso, business=business)
            lines = [f"Laba/Rugi {label.lower()}{scope_note}:", f"Pendapatan: {rupiah(data['income'])}"]
            if data["expense_breakdown"]:
                lines.append("Pengeluaran per kategori:")
                lines.extend(f"  - {row['category']}: {rupiah(row['total'])}" for row in data["expense_breakdown"])
            else:
                lines.append("Pengeluaran: belum ada transaksi tercatat.")
            lines.append(f"Total pengeluaran: {rupiah(data['expense'])}")
            net_label = "Laba bersih" if data["net"] >= 0 else "Rugi bersih"
            lines.append(f"{net_label}: {rupiah(abs(data['net']))}")
            return FinanceResult("berhasil", "\n".join(lines))

        if result.report_type == "arus_kas":
            rows = self.cash_flow(start_iso, end_iso, account=account)
            if not rows:
                return FinanceResult("berhasil", "Belum ada akun aktif untuk ditampilkan.")
            lines = [f"Arus kas {label.lower()}:"]
            for row in rows:
                lines.append(
                    f"{row['account']}: saldo awal {rupiah(row['opening'])} | "
                    f"masuk {rupiah(row['in_total'])} | keluar {rupiah(row['out_total'])} | "
                    f"saldo akhir {rupiah(row['closing'])}"
                )
            return FinanceResult("berhasil", "\n".join(lines))

        # "ringkasan" (default).
        data = self.summary(start_iso, end_iso, business=business)
        if kind_filter == "income":
            return FinanceResult("berhasil", f"{label}{scope_note} — Pemasukan: {rupiah(data['income'])}")
        if kind_filter == "expense":
            return FinanceResult("berhasil", f"{label}{scope_note} — Pengeluaran: {rupiah(data['expense'])}")
        return FinanceResult(
            "berhasil",
            f"{label}{scope_note} — {data['count']} transaksi\n"
            f"Pemasukan: {rupiah(data['income'])}\n"
            f"Pengeluaran: {rupiah(data['expense'])}\n"
            f"Arus kas bersih: {rupiah(data['net'])}",
        )

    def handle(self, message: str) -> FinanceResult:
        raw = message.strip()
        text = raw.casefold()
        command = text.split(maxsplit=1)[0].split("@", 1)[0] if text else ""

        if command == "/saldo" or text in {"saldo", "cek saldo"}:
            balances = self.balances()
            lines = [f"{name}: {rupiah(value)}" for name, value in balances.items()]
            return FinanceResult("berhasil", "Saldo ledger saat ini:\n" + "\n".join(lines))

        if command == "/akun":
            lines = [
                f"{row['name']}: saldo awal {rupiah(row['opening_balance'])} | sekarang {rupiah(row['balance'])}"
                for row in self.account_rows()
            ]
            return FinanceResult(
                "berhasil",
                "Akun keuangan:\n" + "\n".join(lines) +
                "\n\nAtur sebelum ada transaksi, contoh: Set saldo awal BCA 500 ribu."
            )

        if command == "/kategori":
            rows = self.categories()
            if not rows:
                return FinanceResult(
                    "berhasil",
                    "Belum ada kategori tersimpan. Kategori akan dibuat dari transaksi nyata."
                )
            income = [row["name"] for row in rows if row["kind"] == "income"]
            expense = [row["name"] for row in rows if row["kind"] == "expense"]
            parts = []
            if income: parts.append("Pemasukan: " + ", ".join(income))
            if expense: parts.append("Pengeluaran: " + ", ".join(expense))
            return FinanceResult("berhasil", "Kategori yang sudah dipelajari:\n" + "\n".join(parts))

        if "saldo awal" in text:
            account = detect_account(raw)
            amount = parse_amount(raw)
            missing = []
            if account is None: missing.append("akun")
            if amount is None: missing.append("nominal")
            if missing:
                return FinanceResult(
                    "needs_review",
                    "Saldo awal belum diubah. Mohon lengkapi: " + ", ".join(missing) +
                    ". Contoh: Set saldo awal BCA 500 ribu."
                )
            self.set_opening_balance(account, amount)
            return FinanceResult(
                "berhasil",
                f"Saldo awal {account} disetel ke {rupiah(amount)}. Belum ada uang yang dipindahkan; ini hanya posisi awal ledger."
            )

        if command in {"/hari_ini", "/minggu_ini", "/bulan_ini", "/pemasukan", "/pengeluaran"}:
            # Argumen usaha opsional (mis. `/bulan_ini Risol Mamqi`) — tanpa argumen,
            # tetap agregat semua usaha seperti sebelumnya (kompatibel dengan perilaku lama).
            rest = raw.split(maxsplit=1)[1] if " " in raw else ""
            business = detect_business(rest) if rest else None
            if rest and business is None:
                return FinanceResult(
                    "needs_review",
                    f"Usaha \"{rest.strip()}\" tidak dikenali. Usaha yang tersedia: "
                    + ", ".join(BUSINESSES) + ".",
                )
            if command == "/minggu_ini":
                label, data = "Minggu ini", self.week_summary(business=business)
            elif command == "/bulan_ini":
                label, data = "Bulan ini", self.month_summary(business=business)
            else:
                label, data = "Hari ini", self.today_summary(business=business)
            scope_note = f" ({business})" if business else ""
            return FinanceResult(
                "berhasil",
                f"{label}{scope_note} — {data['count']} transaksi\n"
                f"Pemasukan: {rupiah(data['income'])}\n"
                f"Pengeluaran: {rupiah(data['expense'])}\n"
                f"Arus kas bersih: {rupiah(data['net'])}",
            )

        if command == "/laba_rugi":
            rest = raw.split(maxsplit=1)[1] if " " in raw else ""
            business = detect_business(rest) if rest else None
            if rest and business is None:
                return FinanceResult(
                    "needs_review",
                    f"Usaha \"{rest.strip()}\" tidak dikenali. Usaha yang tersedia: "
                    + ", ".join(BUSINESSES) + ".",
                )
            start, end = self._month_bounds(datetime.now())
            data = self.profit_loss(
                start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds"), business=business,
            )
            scope_note = f" — {business}" if business else " — semua usaha"
            lines = [f"Laba/Rugi bulan ini{scope_note}:", f"Pendapatan: {rupiah(data['income'])}"]
            if data["expense_breakdown"]:
                lines.append("Pengeluaran per kategori:")
                lines.extend(
                    f"  - {row['category']}: {rupiah(row['total'])}" for row in data["expense_breakdown"]
                )
            else:
                lines.append("Pengeluaran: belum ada transaksi tercatat.")
            lines.append(f"Total pengeluaran: {rupiah(data['expense'])}")
            net_label = "Laba bersih" if data["net"] >= 0 else "Rugi bersih"
            lines.append(f"{net_label}: {rupiah(abs(data['net']))}")
            lines.append(
                "\nCatatan: ini laba/rugi sederhana (pendapatan dikurangi seluruh pengeluaran "
                "tercatat), belum memisahkan HPP/beban operasional secara akuntansi formal."
            )
            return FinanceResult("berhasil", "\n".join(lines))

        if command == "/arus_kas":
            rest = raw.split(maxsplit=1)[1] if " " in raw else ""
            account = detect_account(rest) if rest else None
            if rest and account is None:
                return FinanceResult(
                    "needs_review",
                    f"Akun \"{rest.strip()}\" tidak dikenali. Akun yang tersedia: " + ", ".join(ACCOUNTS) + ".",
                )
            start, end = self._month_bounds(datetime.now())
            rows = self.cash_flow(
                start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds"), account=account,
            )
            if not rows:
                return FinanceResult("berhasil", "Belum ada akun aktif untuk ditampilkan.")
            lines = ["Arus kas bulan ini:"]
            for row in rows:
                lines.append(
                    f"{row['account']}: saldo awal {rupiah(row['opening'])} | "
                    f"masuk {rupiah(row['in_total'])} | keluar {rupiah(row['out_total'])} | "
                    f"saldo akhir {rupiah(row['closing'])}"
                )
            return FinanceResult("berhasil", "\n".join(lines))

        # AI-first pertanyaan bebas (mis. "pemasukan bulan lalu berapa Risol Mamqi?") —
        # HANYA dicoba kalau pesan BUKAN instruksi pencatatan transaksi baru. Instruksi
        # pencatatan asli SELALU menyebut kind + nominal bersamaan; pertanyaan bebas
        # biasanya tidak menyebut nominal sama sekali. Kalau AI tidak dikonfigurasi,
        # gagal, atau hasilnya tidak valid, jatuh ke jalur command/pencatatan
        # deterministik di bawah tanpa perubahan perilaku apa pun.
        probe_kind = detect_kind(raw)
        probe_amount = parse_amount(raw) if probe_kind else None
        is_recording_instruction = bool(probe_kind and probe_amount is not None)
        if not is_recording_instruction and self.query_interpreter is not None and self.query_interpreter.configured:
            query_reply = self._answer_free_form_query(raw)
            if query_reply is not None:
                return query_reply

        kind = detect_kind(raw)
        if kind:
            amount = parse_amount(raw)
            account = detect_account(raw)
            business = detect_business(raw)
            missing = []
            if amount is None: missing.append("nominal")
            if account is None: missing.append("akun/metode pembayaran")
            if business is None: missing.append("usaha atau Personal")
            if missing:
                return FinanceResult(
                    "needs_review",
                    "Belum saya catat. Mohon lengkapi: " + ", ".join(missing) + ".\n"
                    "Contoh usaha: Catat pengeluaran 80 ribu beli tinta untuk Taqi Desk pakai BCA.\n"
                    "Contoh personal: Catat pengeluaran 300 ribu top up saldo DANA istri pakai BNI.",
                )
            category, category_new = self.resolve_category(raw, kind)
            if not category:
                return FinanceResult(
                    "needs_review",
                    "Belum saya catat karena kegunaan/kategorinya belum cukup jelas. "
                    "Tambahkan misalnya `kategori Perlengkapan` pada pesan yang sama."
                )
            self.record(kind=kind, amount=amount, account=account, business=business,
                        category=category, description=raw)
            label = "Pemasukan" if kind == "income" else "Pengeluaran"
            category_note = " (kategori baru dibuat)" if category_new else ""
            return FinanceResult(
                "berhasil",
                f"{label} tercatat.\nNominal: {rupiah(amount)}\nUsaha: {business}\n"
                f"Akun: {account}\nKategori: {category}{category_note}",
            )

        return FinanceResult("membutuhkan_bantuan", "Finance Agent belum memahami perintah itu.")