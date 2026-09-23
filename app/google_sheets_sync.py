"""Google Sheets mirror sync untuk Finance Agent.

V0.1 memakai webhook Google Apps Script agar runtime lokal tidak membutuhkan
credential Google Cloud di repo. SQLite tetap source of truth; sinkronisasi
mengirim transaksi confirmed dan reversed supaya jejak koreksi terlihat di Sheet.
"""

from __future__ import annotations

import json
import os
import sqlite3
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class SheetsSyncResult:
    status: str
    text: str


class GoogleSheetsSync:
    def __init__(self, db_path: str | Path, webhook_url: str = "", secret: str = ""):
        self.db_path = Path(db_path)
        self.webhook_url = (webhook_url or "").strip()
        self.secret = (secret or "").strip()

    @classmethod
    def from_env(cls, db_path: str | Path) -> "GoogleSheetsSync":
        return cls(
            db_path,
            os.environ.get("GOOGLE_SHEETS_WEBHOOK_URL", ""),
            os.environ.get("GOOGLE_SHEETS_SYNC_SECRET", ""),
        )

    @property
    def configured(self) -> bool:
        return bool(self.webhook_url and self.secret)

    def status(self) -> SheetsSyncResult:
        if not self.configured:
            return SheetsSyncResult(
                "belum_dikonfigurasi",
                "Google Sheets Sync: belum dikonfigurasi. Ledger lokal tetap aman dan menjadi source of truth."
            )
        return SheetsSyncResult(
            "siap",
            "Google Sheets Sync: siap. Gunakan /sync untuk mengirim snapshot ledger ke dashboard."
        )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Buka transaksi SQLite dan selalu tutup handle file setelah dipakai.

        sqlite3.Connection sebagai context manager hanya commit/rollback; ia tidak
        menutup koneksi. Pada Windows hal itu membuat file database sementara tetap
        terkunci sehingga TemporaryDirectory gagal dibersihkan (WinError 32) — lihat
        pola yang sama di app/document_preferences.py.
        """
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def snapshot(self) -> dict:
        """Buat snapshot mirror tanpa mengubah data lokal."""
        with self._connect() as db:
            account_rows = db.execute(
                "SELECT name, opening_balance, active FROM finance_accounts WHERE active=1 ORDER BY name"
            ).fetchall()
            tx_rows = db.execute(
                """SELECT id,created,kind,amount,account,business,category,description,source,status
                   FROM finance_transactions
                   WHERE status IN ('confirmed','reversed')
                   ORDER BY created,id"""
            ).fetchall()
            category_rows = db.execute(
                "SELECT name,kind,created FROM finance_categories ORDER BY kind,name"
            ).fetchall()

        balances = {}
        with self._connect() as db:
            for row in db.execute("""SELECT a.name, a.opening_balance + COALESCE(SUM(
                    CASE WHEN t.kind='income' THEN t.amount WHEN t.kind='expense' THEN -t.amount ELSE 0 END
                ),0) AS balance
                FROM finance_accounts a
                LEFT JOIN finance_transactions t ON t.account=a.name AND t.status='confirmed'
                WHERE a.active=1
                GROUP BY a.name,a.opening_balance""").fetchall():
                balances[row["name"]] = int(row["balance"])

        accounts = [
            {
                "name": row["name"],
                "opening_balance": int(row["opening_balance"]),
                "balance": balances.get(row["name"], int(row["opening_balance"])),
            }
            for row in account_rows
        ]

        transactions = []
        for row in tx_rows:
            created = row["created"]
            try:
                dt = datetime.fromisoformat(created)
                date_value = dt.date().isoformat()
                time_value = dt.strftime("%H:%M:%S")
            except ValueError:
                date_value = created[:10]
                time_value = created[11:19] if len(created) >= 19 else ""
            transactions.append({
                "id": row["id"],
                "date": date_value,
                "time": time_value,
                "kind": row["kind"],
                "business": row["business"],
                "category": row["category"],
                "description": row["description"],
                "account": row["account"],
                "amount": int(row["amount"]),
                "status": row["status"],
                "source": row["source"],
                "timestamp": created,
                "source_event_id": row["id"],
            })

        categories = [
            {"name": row["name"], "kind": row["kind"], "created": row["created"]}
            for row in category_rows
        ]
        return {
            "schema_version": 1,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "accounts": accounts,
            "categories": categories,
            "transactions": transactions,
        }

    def sync_now(self, timeout: int = 30) -> SheetsSyncResult:
        if not self.configured:
            return self.status()
        if not self.webhook_url.startswith("https://"):
            return SheetsSyncResult("gagal", "Google Sheets webhook ditolak karena harus memakai HTTPS.")

        payload = self.snapshot()
        payload["secret"] = self.secret
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.webhook_url,
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
                result = json.loads(raw)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            return SheetsSyncResult(
                "gagal",
                f"Sinkronisasi Google Sheets gagal. Ledger lokal tidak berubah. Detail: {exc}"
            )

        if not isinstance(result, dict) or not result.get("ok"):
            message = result.get("error", "respons webhook tidak valid") if isinstance(result, dict) else "respons webhook tidak valid"
            return SheetsSyncResult("gagal", f"Google Sheets menolak sinkronisasi: {message}")

        tx = int(result.get("transactions", 0))
        accounts = int(result.get("accounts", 0))
        categories = int(result.get("categories", 0))
        return SheetsSyncResult(
            "berhasil",
            f"Google Sheets tersinkron. Transaksi: {tx}, akun: {accounts}, kategori: {categories}."
        )
