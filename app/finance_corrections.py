"""Aman untuk koreksi transaksi Finance Agent tanpa hard-delete.

Strategi V0.1:
- transaksi lama diubah status menjadi `reversed`;
- transaksi pengganti dibuat sebagai `confirmed`;
- jejak koreksi dicatat di tabel audit `finance_corrections`.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime

from app.finance import ACCOUNTS, FinanceResult, detect_account, rupiah


def _ensure_audit_table(db: sqlite3.Connection) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS finance_corrections (
        id TEXT PRIMARY KEY,
        created TEXT NOT NULL,
        original_transaction_id TEXT NOT NULL,
        replacement_transaction_id TEXT NOT NULL,
        field_name TEXT NOT NULL,
        old_value TEXT NOT NULL,
        new_value TEXT NOT NULL,
        reason TEXT NOT NULL
    )""")


def correct_latest_account(finance, message: str) -> FinanceResult:
    """Koreksi akun pada transaksi confirmed terakhir dengan reversal + replacement."""
    new_account = detect_account(message)
    if new_account is None or new_account not in ACCOUNTS:
        return FinanceResult(
            "needs_review",
            "Koreksi belum dilakukan. Sebutkan akun yang benar, misalnya: "
            "Koreksi transaksi terakhir, akun seharusnya BNI."
        )

    created = datetime.now().isoformat(timespec="seconds")
    replacement_id = str(uuid.uuid4())
    correction_id = str(uuid.uuid4())

    with finance.connect() as db:
        _ensure_audit_table(db)
        row = db.execute(
            """SELECT id,created,kind,amount,account,business,category,description,source,status
               FROM finance_transactions
               WHERE status='confirmed'
               ORDER BY created DESC, rowid DESC
               LIMIT 1"""
        ).fetchone()
        if row is None:
            return FinanceResult("needs_review", "Belum ada transaksi aktif yang dapat dikoreksi.")

        old_account = row["account"]
        if old_account == new_account:
            return FinanceResult(
                "needs_review",
                f"Transaksi terakhir sudah memakai akun {new_account}; tidak ada perubahan yang dilakukan."
            )

        db.execute(
            "UPDATE finance_transactions SET status='reversed' WHERE id=? AND status='confirmed'",
            (row["id"],),
        )
        db.execute(
            """INSERT INTO finance_transactions
               (id,created,kind,amount,account,business,category,description,source,status)
               VALUES(?,?,?,?,?,?,?,?,?,'confirmed')""",
            (
                replacement_id,
                created,
                row["kind"],
                int(row["amount"]),
                new_account,
                row["business"],
                row["category"],
                row["description"],
                "web_admin_correction",
            ),
        )
        db.execute(
            """INSERT INTO finance_corrections
               (id,created,original_transaction_id,replacement_transaction_id,
                field_name,old_value,new_value,reason)
               VALUES(?,?,?,?,?,?,?,?)""",
            (
                correction_id,
                created,
                row["id"],
                replacement_id,
                "account",
                old_account,
                new_account,
                message.strip(),
            ),
        )

    return FinanceResult(
        "berhasil",
        "Koreksi transaksi berhasil.\n"
        f"Nominal: {rupiah(int(row['amount']))}\n"
        f"Akun lama: {old_account}\n"
        f"Akun benar: {new_account}\n"
        f"Usaha: {row['business']}\n"
        f"Kategori: {row['category']}\n"
        "Transaksi lama ditandai dibatalkan/reversed dan transaksi pengganti dibuat. "
        "Riwayat koreksi tetap tersimpan."
    )
