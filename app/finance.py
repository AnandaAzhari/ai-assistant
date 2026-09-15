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


ACCOUNTS = (
    "Cash", "BCA", "BNI", "SeaBank", "Jago", "QRIS", "DANA", "GoPay", "ShopeePay"
)
BUSINESSES = (
    "Taqi DocuTech", "Pixiva.ID", "Computer Service", "Risol Mamqi", "Personal"
)

CATEGORY_RULES = {
    "expense": (
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
    lowered = text.casefold()
    aliases = {
        "cash": "Cash", "tunai": "Cash", "bca": "BCA", "bni": "BNI",
        "seabank": "SeaBank", "sea bank": "SeaBank", "jago": "Jago",
        "bank jago": "Jago", "qris": "QRIS", "dana": "DANA",
        "gopay": "GoPay", "go pay": "GoPay", "shopeepay": "ShopeePay",
        "shopee pay": "ShopeePay",
    }
    for alias in sorted(aliases, key=len, reverse=True):
        if re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", lowered):
            return aliases[alias]
    return None


def detect_business(text: str) -> str | None:
    lowered = text.casefold()
    aliases = {
        "taqi docutech": "Taqi DocuTech", "docutech": "Taqi DocuTech",
        "taqi desk": "Taqi DocuTech", "taqidesk": "Taqi DocuTech",
        "pixiva.id": "Pixiva.ID", "pixiva": "Pixiva.ID",
        "computer service": "Computer Service", "service komputer": "Computer Service",
        "risol mamqi": "Risol Mamqi", "mamqi": "Risol Mamqi",
        "personal": "Personal", "pribadi": "Personal",
    }
    for alias in sorted(aliases, key=len, reverse=True):
        if alias in lowered:
            return aliases[alias]
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
    def __init__(self, db_path: str | Path = "data/assistant.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
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
            db.executemany(
                "INSERT OR IGNORE INTO finance_accounts(name, opening_balance, active) VALUES(?,0,1)",
                [(name,) for name in ACCOUNTS],
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

    def summary(self, start: str, end: str) -> dict[str, int]:
        with self.connect() as db:
            rows = db.execute(
                """SELECT kind, COALESCE(SUM(amount),0) AS total, COUNT(*) AS count
                   FROM finance_transactions
                   WHERE status='confirmed' AND created>=? AND created<? GROUP BY kind""",
                (start, end),
            ).fetchall()
        result = {"income": 0, "expense": 0, "count": 0}
        for row in rows:
            result[row["kind"]] = int(row["total"])
            result["count"] += int(row["count"])
        result["net"] = result["income"] - result["expense"]
        return result

    def today_summary(self) -> dict[str, int]:
        now = datetime.now()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        return self.summary(start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds"))

    def month_summary(self) -> dict[str, int]:
        now = datetime.now()
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        return self.summary(start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds"))

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

        if command in {"/hari_ini", "/pemasukan", "/pengeluaran"}:
            data = self.today_summary()
            return FinanceResult(
                "berhasil",
                f"Hari ini — {data['count']} transaksi\n"
                f"Pemasukan: {rupiah(data['income'])}\n"
                f"Pengeluaran: {rupiah(data['expense'])}\n"
                f"Arus kas bersih: {rupiah(data['net'])}",
            )

        if command == "/bulan_ini":
            data = self.month_summary()
            return FinanceResult(
                "berhasil",
                f"Bulan ini — {data['count']} transaksi\n"
                f"Pemasukan: {rupiah(data['income'])}\n"
                f"Pengeluaran: {rupiah(data['expense'])}\n"
                f"Arus kas bersih: {rupiah(data['net'])}",
            )

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
                    "Contoh: Catat pengeluaran 80 ribu beli tinta untuk Taqi DocuTech pakai BCA.",
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
