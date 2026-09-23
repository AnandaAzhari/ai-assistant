"""Source Registry untuk referensi akademik Document Agent.

Menyimpan kandidat sumber yang sudah dipilih ke SQLite dengan ID stabil per scope
(R1, R2, ...). Metadata bibliografi tambahan disimpan agar footnote dan daftar pustaka
bisa diformat secara deterministik tanpa menyerahkan formatting ke model AI.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator

from app.research_manager import ResearchSource


@dataclass(frozen=True)
class RegisteredSource:
    ref_id: str
    provider: str
    title: str
    authors: tuple[str, ...]
    year: int | None
    venue: str
    doi: str
    url: str
    work_type: str
    is_open_access: bool
    created: str
    volume: str = ""
    issue: str = ""
    pages: str = ""
    publisher: str = ""
    abstract: str = ""


class SourceRegistry:
    def __init__(self, db_path: str | Path = "data/assistant.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate()

    @classmethod
    def from_env(cls) -> "SourceRegistry":
        path = os.environ.get("DATABASE_PATH", "data/assistant.db").strip() or "data/assistant.db"
        return cls(path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Buka transaksi SQLite dan selalu tutup handle file setelah dipakai.

        sqlite3.Connection sebagai context manager hanya commit/rollback; ia tidak
        menutup koneksi. Pada Windows hal itu membuat file database sementara tetap
        terkunci sehingga TemporaryDirectory gagal dibersihkan (WinError 32) — lihat
        pola yang sama di app/document_preferences.py.
        """
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _column_names(db: sqlite3.Connection) -> set[str]:
        return {str(row[1]) for row in db.execute("PRAGMA table_info(document_sources)").fetchall()}

    def _migrate(self) -> None:
        with self.connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS document_sources (
                    scope_id TEXT NOT NULL,
                    ref_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    title TEXT NOT NULL,
                    authors_json TEXT NOT NULL DEFAULT '[]',
                    year INTEGER,
                    venue TEXT NOT NULL DEFAULT '',
                    doi TEXT NOT NULL DEFAULT '',
                    url TEXT NOT NULL DEFAULT '',
                    work_type TEXT NOT NULL DEFAULT '',
                    is_open_access INTEGER NOT NULL DEFAULT 0,
                    created TEXT NOT NULL,
                    volume TEXT NOT NULL DEFAULT '',
                    issue TEXT NOT NULL DEFAULT '',
                    pages TEXT NOT NULL DEFAULT '',
                    publisher TEXT NOT NULL DEFAULT '',
                    abstract TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY(scope_id, ref_id)
                )
            """)
            existing = self._column_names(db)
            for name in ("volume", "issue", "pages", "publisher", "abstract"):
                if name not in existing:
                    db.execute(f"ALTER TABLE document_sources ADD COLUMN {name} TEXT NOT NULL DEFAULT ''")
            db.execute("CREATE INDEX IF NOT EXISTS document_sources_scope ON document_sources(scope_id)")
            db.execute("CREATE INDEX IF NOT EXISTS document_sources_doi ON document_sources(doi)")

    @staticmethod
    def _normalize_doi(value: str) -> str:
        doi = (value or "").strip().lower()
        for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
            if doi.startswith(prefix):
                doi = doi[len(prefix):].strip()
        return doi

    def _next_number(self, scope_id: str, db: sqlite3.Connection) -> int:
        rows = db.execute("SELECT ref_id FROM document_sources WHERE scope_id=?", (scope_id,)).fetchall()
        highest = 0
        for row in rows:
            ref = str(row["ref_id"] or "")
            if ref.startswith("R") and ref[1:].isdigit():
                highest = max(highest, int(ref[1:]))
        return highest + 1

    def add_sources(self, scope_id: str, sources: Iterable[ResearchSource]) -> list[RegisteredSource]:
        scope = (scope_id or "").strip()
        if not scope:
            raise ValueError("scope_id wajib diisi.")
        added: list[RegisteredSource] = []
        with self.connect() as db:
            next_number = self._next_number(scope, db)
            existing_rows = db.execute("SELECT doi,title FROM document_sources WHERE scope_id=?", (scope,)).fetchall()
            existing_doi = {self._normalize_doi(row["doi"]) for row in existing_rows if row["doi"]}
            existing_title = {str(row["title"]).strip().casefold() for row in existing_rows}
            for source in sources:
                doi = self._normalize_doi(source.doi)
                title_key = (source.title or "").strip().casefold()
                if (doi and doi in existing_doi) or (title_key and title_key in existing_title):
                    continue
                ref_id = f"R{next_number}"
                next_number += 1
                created = datetime.now().isoformat(timespec="seconds")
                authors = tuple(source.authors)
                volume = getattr(source, "volume", "") or ""
                issue = getattr(source, "issue", "") or ""
                pages = getattr(source, "pages", "") or ""
                publisher = getattr(source, "publisher", "") or ""
                abstract = getattr(source, "abstract", "") or ""
                db.execute(
                    """
                    INSERT INTO document_sources(
                        scope_id,ref_id,provider,title,authors_json,year,venue,doi,url,
                        work_type,is_open_access,created,volume,issue,pages,publisher,abstract
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (scope, ref_id, source.provider, source.title, json.dumps(authors, ensure_ascii=False),
                     source.year, source.venue, doi, source.url, source.work_type,
                     1 if source.is_open_access else 0, created, volume, issue, pages, publisher, abstract),
                )
                if doi:
                    existing_doi.add(doi)
                existing_title.add(title_key)
                added.append(RegisteredSource(
                    ref_id=ref_id, provider=source.provider, title=source.title, authors=authors,
                    year=source.year, venue=source.venue, doi=doi, url=source.url,
                    work_type=source.work_type, is_open_access=bool(source.is_open_access), created=created,
                    volume=volume, issue=issue, pages=pages, publisher=publisher, abstract=abstract,
                ))
        return added

    def list_sources(self, scope_id: str) -> list[RegisteredSource]:
        with self.connect() as db:
            rows = db.execute(
                """
                SELECT ref_id,provider,title,authors_json,year,venue,doi,url,work_type,is_open_access,
                       created,volume,issue,pages,publisher,abstract
                FROM document_sources
                WHERE scope_id=?
                ORDER BY CAST(SUBSTR(ref_id,2) AS INTEGER), ref_id
                """,
                (scope_id,),
            ).fetchall()
        result: list[RegisteredSource] = []
        for row in rows:
            try:
                authors = tuple(json.loads(row["authors_json"] or "[]"))
            except (TypeError, ValueError, json.JSONDecodeError):
                authors = ()
            result.append(RegisteredSource(
                ref_id=row["ref_id"], provider=row["provider"], title=row["title"], authors=authors,
                year=row["year"], venue=row["venue"], doi=row["doi"], url=row["url"],
                work_type=row["work_type"], is_open_access=bool(row["is_open_access"]), created=row["created"],
                volume=row["volume"], issue=row["issue"], pages=row["pages"],
                publisher=row["publisher"], abstract=row["abstract"],
            ))
        return result

    def clear_scope(self, scope_id: str) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM document_sources WHERE scope_id=?", (scope_id,))

    @staticmethod
    def format_sources(sources: list[RegisteredSource]) -> str:
        if not sources:
            return "Belum ada sumber pada Source Registry sesi ini."
        lines = [f"Source Registry berisi {len(sources)} sumber:"]
        for source in sources:
            authors = ", ".join(source.authors[:3]) or "Penulis tidak tercantum"
            if len(source.authors) > 3:
                authors += " dkk."
            year = str(source.year) if source.year else "tanpa tahun"
            doi = f" | DOI: {source.doi}" if source.doi else ""
            extra = ""
            if source.volume:
                extra += f" vol. {source.volume}"
            if source.issue:
                extra += f" no. {source.issue}"
            if source.pages:
                extra += f" pp. {source.pages}"
            lines.append(f"{source.ref_id}. **{source.title}** — {authors} ({year}){extra}{doi}")
        lines.append("\nID R1/R2/... dipakai untuk footnote dan daftar pustaka otomatis.")
        return "\n".join(lines)
