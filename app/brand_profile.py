"""Pembaca terstruktur untuk Brand Profile per usaha (`brand_profiles/*.md`).

Brand Profile tetap berupa file markdown yang ditulis/diedit manual oleh owner
(Reference/Static Knowledge, lihat `docs/agent_memory_v1.md` lapis 3) — modul ini
TIDAK PERNAH menulis ke file tersebut, hanya membaca dan mem-parsing bagian-bagian
yang relevan supaya bisa dipakai secara terprogram oleh Content Studio
(`app/content_studio.py`) tanpa mengubah format aslinya (lihat template di
`brand_profiles/BRAND_PROFILE_TEMPLATE.md`).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_PLACEHOLDER_MARKER = "[ISI"


@dataclass(frozen=True)
class BrandProfile:
    business: str
    description: str
    tone_of_voice: str
    target_audience: str
    forbidden_themes: str
    example_captions: tuple[str, ...]
    status_raw: str
    source_path: str


def _parse_sections(text: str) -> dict[str, str]:
    """Pecah body markdown per header `## ...` menjadi dict {nama_section: isi}."""
    sections: dict[str, str] = {}
    current: str | None = None
    buffer: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current is not None:
                sections[current] = "\n".join(buffer).strip()
            current = line[3:].strip()
            buffer = []
        elif current is not None:
            buffer.append(line)
    if current is not None:
        sections[current] = "\n".join(buffer).strip()
    return sections


def _extract_bullets(block: str) -> tuple[str, ...]:
    items = []
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith("- ") and _PLACEHOLDER_MARKER not in stripped:
            items.append(stripped[2:].strip())
    return tuple(items)


class BrandProfileStore:
    def __init__(self, root: str | Path = "brand_profiles"):
        self.root = Path(root)

    @staticmethod
    def slug(business: str) -> str:
        """Normalisasi nama usaha jadi nama file, mis. "Pixiva.ID" -> "pixiva_id"."""
        value = re.sub(r"[^a-z0-9]+", "_", (business or "").strip().casefold()).strip("_")
        return value

    def _path(self, business: str) -> Path:
        return self.root / f"{self.slug(business)}.md"

    def load(self, business: str) -> BrandProfile | None:
        path = self._path(business)
        if not path.is_file():
            return None
        sections = _parse_sections(path.read_text(encoding="utf-8"))
        tone_of_voice = sections.get("Tone of Voice", "").strip()
        forbidden_themes = sections.get("Larangan Tema/Kata", "").strip()
        return BrandProfile(
            business=sections.get("Usaha", "").strip() or str(business).strip(),
            description=sections.get("Deskripsi Singkat", "").strip(),
            tone_of_voice=tone_of_voice,
            target_audience=sections.get("Target Audiens", "").strip(),
            forbidden_themes=forbidden_themes,
            example_captions=_extract_bullets(sections.get("Contoh Caption Favorit", "")),
            status_raw=sections.get("Status", "").strip(),
            source_path=str(path),
        )

    def is_ready(self, business: str) -> bool:
        """Brand profile dianggap cukup lengkap untuk dipakai Content Studio kalau
        tone of voice dan larangan tema/kata sudah diisi (bukan placeholder kosong).

        Warna/logo/aset visual boleh masih placeholder — itu dipakai Visual Studio,
        bukan untuk membuat draft caption/naskah.
        """
        profile = self.load(business)
        if profile is None:
            return False
        if not profile.tone_of_voice or _PLACEHOLDER_MARKER in profile.tone_of_voice:
            return False
        if not profile.forbidden_themes or _PLACEHOLDER_MARKER in profile.forbidden_themes:
            return False
        return True

    def list_known_businesses(self) -> tuple[str, ...]:
        if not self.root.is_dir():
            return ()
        names = []
        for path in sorted(self.root.glob("*.md")):
            if path.stem.upper() == "BRAND_PROFILE_TEMPLATE":
                continue
            profile = self.load(path.stem)
            names.append(profile.business if profile else path.stem)
        return tuple(names)
