"""Source Registry untuk referensi akademik Document Agent.

Menyimpan kandidat sumber yang sudah dipilih ke SQLite dengan ID stabil per scope
(R1, R2, ...). Scope saat ini masih berupa sesi dokumen; setelah Order System dibuat,
scope dapat diganti dengan Order ID tanpa mengubah format referensi internal.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

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


class SourceRegistry:
    def __init__(self, db_path: str | Path = "data/assistant.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate()

    @classmethod
    def from_env(cls) -> "SourceRegistry":
        path = os.environ.get("DATABASE_PATH", "data/assistant.db").strip() or "data/assistant.db"
        return cls(path)

    def connect(self):
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

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
                    PRIMARY KEY(scope_id, ref_id)
                )
            """)
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
        rows = db.execute(
            "SELECT ref_id FROM document_sources WHERE scope_id=?",
            (scope_id,),
        ).fetchall()
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
            existing_rows = db.execute(
                "SELECT doi,title FROM document_sources WHERE scope_id=?",
                (scope,),
            ).fetchall()
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
                db.execute(
                    """
                    INSERT INTO document_sources(
                        scope_id,ref_id,provider,title,authors_json,year,venue,doi,url,
                        work_type,is_open_access,created
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        scope,
                        ref_id,
                        source.provider,
                        source.title,
                        json.dumps(authors, ensure_ascii=False),
                        source.year,
                        source.venue,
                        doi,
                        source.url,
                        source.work_type,
                        1 if source.is_open_access else 0,
                        created,
                    ),
                )
                existing_doi.add(doi) if doi else None
                existing_title.add(title_key)
                added.append(
                    RegisteredSource(
                        ref_id=ref_id,
                        provider=source.provider,
                        title=source.title,
                        authors=authors,
                        year=source.year,
                        venue=source.venue,
                        doi=doi,
                        url=source.url,
                        work_type=source.work_type,
                        is_open_access=bool(source.is_open_access),
                        created=created,
                    )
                )
        return added

    def list_sources(self, scope_id: str) -> list[RegisteredSource]:
        with self.connect() as db:
            rows = db.execute(
                """
                SELECT ref_id,provider,title,authors_json,year,venue,doi,url,work_type,is_open_access,created
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
            result.append(
                RegisteredSource(
                    ref_id=row["ref_id"],
                    provider=row["provider"],
                    title=row["title"],
                    authors=authors,
                    year=row["year"],
                    venue=row["venue"],
                    doi=row["doi"],
                    url=row["url"],
                    work_type=row["work_type"],
                    is_open_access=bool(row["is_open_access"]),
                    created=row["created"],
                )
            )
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
            lines.append(f"{source.ref_id}. **{source.title}** — {authors} ({year}){doi}")
        lines.append("\nID R1/R2/... inilah yang nanti dipakai untuk footnote dan daftar pustaka otomatis.")
        return "\n".join(lines)
