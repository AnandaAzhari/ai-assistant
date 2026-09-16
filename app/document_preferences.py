"""Document Preferences untuk preferensi format per order/sesi.

Parser lokal memahami bahasa natural pelanggan untuk preferensi format yang aman
secara deterministik. Tahap awal hanya mengatur citation_repeat_mode agar pelanggan
tidak perlu menulis setting teknis seperti `citation_repeat_mode=short`.
"""

from __future__ import annotations

import os
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class PreferenceParseResult:
    matched: bool
    field: str = ""
    value: str = ""
    changed: bool = False
    ambiguous: bool = False
    message: str = ""


@dataclass(frozen=True)
class DocumentPreferences:
    citation_style: str = "chicago_notes_bibliography"
    citation_repeat_mode: str = "auto"

    VALID_REPEAT_MODES = ("auto", "short")

    def __post_init__(self) -> None:
        if self.citation_repeat_mode not in self.VALID_REPEAT_MODES:
            raise ValueError("citation_repeat_mode harus 'auto' atau 'short'.")

    def with_repeat_mode(self, value: str) -> "DocumentPreferences":
        mode = DocumentPreferenceParser.normalize_repeat_mode(value)
        return replace(self, citation_repeat_mode=mode)

    def structured_text(self) -> str:
        return (
            f"citation_style: {self.citation_style}\n"
            f"citation_repeat_mode: {self.citation_repeat_mode}"
        )


class DocumentPreferenceParser:
    """Parser lokal untuk preferensi pelanggan tanpa memakai token AI."""

    _SHORT_PATTERNS = (
        r"\bjangan\s+(?:pakai|gunakan|pake)\s+ibid\b",
        r"\btanpa\s+ibid\b",
        r"\btidak\s+(?:perlu|usah|pakai|gunakan)\s+ibid\b",
        r"\b(?:ga|gak|nggak|enggak)\s+(?:usah|pakai|gunakan)\s+ibid\b",
        r"\bno\s+ibid\b",
        r"\bwithout\s+ibid\b",
        r"\bpakai\s+short\s+note\b",
        r"\bgunakan\s+short\s+note\b",
        r"\bsemua\s+pengulangan\s+(?:pakai|gunakan)\s+short\s+note\b",
        r"\btulis\s+(?:nama\s+)?penulis\s+lagi\b",
    )
    _AUTO_PATTERNS = (
        r"\bpakai\s+ibid\b",
        r"\bgunakan\s+ibid\b",
        r"\bpake\s+ibid\b",
        r"\bboleh\s+ibid\b",
        r"\bdengan\s+ibid\b",
        r"\bibid\s+saja\b",
        r"\bwith\s+ibid\b",
    )

    @staticmethod
    def _normalize_text(value: str) -> str:
        text = (value or "").casefold()
        text = text.replace("’", "'").replace("`", "'")
        text = re.sub(r"[^a-z0-9\s'-]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @classmethod
    def normalize_repeat_mode(cls, value: str | None) -> str:
        raw = cls._normalize_text(value or "auto").replace("-", "_").replace(" ", "_")
        aliases = {
            "auto": "auto",
            "default": "auto",
            "ibid": "auto",
            "with_ibid": "auto",
            "pakai_ibid": "auto",
            "gunakan_ibid": "auto",
            "short": "short",
            "short_note": "short",
            "no_ibid": "short",
            "without_ibid": "short",
            "tanpa_ibid": "short",
            "jangan_pakai_ibid": "short",
            "jangan_gunakan_ibid": "short",
        }
        mode = aliases.get(raw, raw)
        if mode not in DocumentPreferences.VALID_REPEAT_MODES:
            raise ValueError("citation_repeat_mode tidak dikenal. Gunakan 'auto' atau 'short'.")
        return mode

    @classmethod
    def parse(cls, message: str, current: DocumentPreferences | None = None) -> PreferenceParseResult:
        prefs = current or DocumentPreferences()
        text = cls._normalize_text(message)
        if not text or "ibid" not in text and "short note" not in text and "penulis lagi" not in text:
            return PreferenceParseResult(False)

        short_match = any(re.search(pattern, text) for pattern in cls._SHORT_PATTERNS)
        auto_match = any(re.search(pattern, text) for pattern in cls._AUTO_PATTERNS)

        # Pola negasi seperti "jangan pakai Ibid" juga mengandung kata "pakai Ibid".
        # Karena itu jika ada pola short/negasi yang eksplisit, short menang.
        if short_match:
            value = "short"
        elif auto_match:
            value = "auto"
        else:
            return PreferenceParseResult(
                matched=True,
                ambiguous=True,
                field="citation_repeat_mode",
                message="Preferensi Ibid belum jelas. Pilih: pakai Ibid atau tanpa Ibid.",
            )

        changed = value != prefs.citation_repeat_mode
        if value == "short":
            message_out = "Baik, catatan kaki tidak akan memakai Ibid.; pengulangan sumber memakai short note."
        else:
            message_out = "Baik, Ibid. boleh dipakai untuk pengulangan sumber yang langsung berurutan."
        return PreferenceParseResult(
            matched=True,
            field="citation_repeat_mode",
            value=value,
            changed=changed,
            message=message_out,
        )

    @classmethod
    def apply(cls, message: str, current: DocumentPreferences | None = None) -> tuple[DocumentPreferences, PreferenceParseResult]:
        prefs = current or DocumentPreferences()
        result = cls.parse(message, prefs)
        if not result.matched or result.ambiguous or not result.value:
            return prefs, result
        return prefs.with_repeat_mode(result.value), result


class DocumentPreferenceStore:
    """SQLite store kecil untuk preferensi per order/scope."""

    def __init__(self, db_path: str | Path = "data/assistant.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate()

    @classmethod
    def from_env(cls) -> "DocumentPreferenceStore":
        path = os.environ.get("DATABASE_PATH", "data/assistant.db").strip() or "data/assistant.db"
        return cls(path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Buka transaksi SQLite dan selalu tutup handle file setelah dipakai.

        sqlite3.Connection sebagai context manager hanya commit/rollback; ia tidak
        menutup koneksi. Pada Windows hal itu membuat file database sementara tetap
        terkunci sehingga TemporaryDirectory gagal dibersihkan (WinError 32).
        """
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def _migrate(self) -> None:
        with self.connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS document_preferences (
                    scope_id TEXT PRIMARY KEY,
                    citation_style TEXT NOT NULL DEFAULT 'chicago_notes_bibliography',
                    citation_repeat_mode TEXT NOT NULL DEFAULT 'auto',
                    updated_at TEXT NOT NULL
                )
                """
            )

    def load(self, scope_id: str) -> DocumentPreferences:
        scope = (scope_id or "").strip()
        if not scope:
            raise ValueError("scope_id wajib diisi.")
        with self.connect() as db:
            row = db.execute(
                "SELECT citation_style,citation_repeat_mode FROM document_preferences WHERE scope_id=?",
                (scope,),
            ).fetchone()
        if not row:
            return DocumentPreferences()
        return DocumentPreferences(
            citation_style=str(row["citation_style"] or "chicago_notes_bibliography"),
            citation_repeat_mode=DocumentPreferenceParser.normalize_repeat_mode(row["citation_repeat_mode"]),
        )

    def save(self, scope_id: str, preferences: DocumentPreferences) -> None:
        scope = (scope_id or "").strip()
        if not scope:
            raise ValueError("scope_id wajib diisi.")
        now = datetime.now().isoformat(timespec="seconds")
        with self.connect() as db:
            db.execute(
                """
                INSERT INTO document_preferences(scope_id,citation_style,citation_repeat_mode,updated_at)
                VALUES(?,?,?,?)
                ON CONFLICT(scope_id) DO UPDATE SET
                    citation_style=excluded.citation_style,
                    citation_repeat_mode=excluded.citation_repeat_mode,
                    updated_at=excluded.updated_at
                """,
                (scope, preferences.citation_style, preferences.citation_repeat_mode, now),
            )

    def apply_message(self, scope_id: str, message: str) -> tuple[DocumentPreferences, PreferenceParseResult]:
        current = self.load(scope_id)
        updated, result = DocumentPreferenceParser.apply(message, current)
        if result.matched and not result.ambiguous and result.value:
            self.save(scope_id, updated)
        return updated, result

    def reset(self, scope_id: str) -> None:
        scope = (scope_id or "").strip()
        if not scope:
            return
        with self.connect() as db:
            db.execute("DELETE FROM document_preferences WHERE scope_id=?", (scope,))
