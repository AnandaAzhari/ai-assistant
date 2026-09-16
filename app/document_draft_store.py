"""Penyimpanan lokal sementara untuk isi makalah yang sudah dibuat AI.

Tujuannya agar isi makalah tidak hilang saat Web Admin direstart sebelum file Word/PDF
selesai dibuat. Data disimpan lokal di workspace/ dan tidak dikirim ke model AI.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from app.document_engine import DocumentSection, MakalahSpec


class DraftStore:
    def __init__(self, root: str | Path = "workspace/document_drafts"):
        self.root = Path(root)

    @classmethod
    def from_env(cls) -> "DraftStore":
        root = os.environ.get("DOCUMENT_DRAFT_STORE", "workspace/document_drafts").strip() or "workspace/document_drafts"
        return cls(root)

    @staticmethod
    def _safe_scope(scope: str) -> str:
        value = re.sub(r"[^A-Za-z0-9._-]+", "-", (scope or "default").strip()).strip("-._")
        return value[:100] or "default"

    def _path(self, scope: str) -> Path:
        return self.root / f"{self._safe_scope(scope)}.json"

    def save(self, scope: str, spec: MakalahSpec) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = {
            "order_id": spec.order_id,
            "title": spec.title,
            "institution": spec.institution,
            "class_semester": spec.class_semester,
            "subject": spec.subject,
            "author": spec.author,
            "teacher": spec.teacher,
            "year": spec.year,
            "group_name": spec.group_name,
            "members": list(spec.members),
            "preface": list(spec.preface),
            "sections": [
                {"title": item.title, "paragraphs": list(item.paragraphs), "level": item.level}
                for item in spec.sections
            ],
        }
        path = self._path(scope)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load(self, scope: str) -> MakalahSpec | None:
        path = self._path(scope)
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            sections = tuple(
                DocumentSection(
                    str(item.get("title") or "").strip(),
                    tuple(str(p).strip() for p in (item.get("paragraphs") or []) if str(p).strip()),
                    max(1, min(3, int(item.get("level") or 1))),
                )
                for item in (payload.get("sections") or [])
                if isinstance(item, dict) and str(item.get("title") or "").strip()
            )
            return MakalahSpec(
                order_id=str(payload.get("order_id") or "DRAFT"),
                title=str(payload.get("title") or "Makalah"),
                institution=str(payload.get("institution") or ""),
                class_semester=str(payload.get("class_semester") or ""),
                subject=str(payload.get("subject") or ""),
                author=str(payload.get("author") or ""),
                teacher=str(payload.get("teacher") or ""),
                year=str(payload.get("year") or ""),
                group_name=str(payload.get("group_name") or ""),
                members=tuple(str(x).strip() for x in (payload.get("members") or []) if str(x).strip()),
                preface=tuple(str(x).strip() for x in (payload.get("preface") or []) if str(x).strip()),
                sections=sections,
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None

    def clear(self, scope: str) -> None:
        try:
            self._path(scope).unlink(missing_ok=True)
        except OSError:
            pass
