"""Footnote + Daftar Pustaka Engine untuk dokumen makalah.

Engine ini tidak memakai model AI. Draft cukup memakai marker [[R1]], [[R2]], dst.
Daftar pustaka dibentuk dari source registry, lalu Microsoft Word COM mengubah marker
menjadi footnote asli dengan nomor otomatis dan posisi di bawah halaman.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path

from app.document_engine import DocumentBuildResult, DocumentEngine, DocumentSection, MakalahSpec
from app.source_registry import RegisteredSource


_REF_PATTERN = re.compile(r"\[\[(R\d+)\]\]", re.IGNORECASE)


@dataclass(frozen=True)
class CitationBuildResult:
    status: str
    docx_path: str = ""
    pdf_path: str = ""
    used_refs: tuple[str, ...] = ()
    warning: str = ""


class CitationEngine:
    def __init__(self, document_engine: DocumentEngine):
        self.document_engine = document_engine

    @property
    def status_text(self) -> str:
        return "Footnote + Daftar Pustaka Engine siap. Marker sumber: [[R1]], [[R2]], dst."

    @staticmethod
    def _author_text(source: RegisteredSource, *, short: bool = False) -> str:
        authors = [str(name).strip() for name in source.authors if str(name).strip()]
        if not authors:
            return "Penulis tidak tercantum"
        if short:
            return authors[0] + (" dkk." if len(authors) > 1 else "")
        if len(authors) <= 3:
            return ", ".join(authors)
        return ", ".join(authors[:3]) + " dkk."

    @staticmethod
    def _short_title(title: str, max_words: int = 8) -> str:
        words = re.sub(r"\s+", " ", (title or "").strip()).split()
        if len(words) <= max_words:
            return " ".join(words)
        return " ".join(words[:max_words]) + "…"

    @classmethod
    def footnote_full(cls, source: RegisteredSource) -> str:
        author = cls._author_text(source)
        title = (source.title or "Tanpa judul").strip()
        parts = [f'{author}, “{title}”']
        if source.venue:
            parts.append(source.venue.strip())
        if source.year:
            parts.append(f"({source.year})")
        locator = ""
        if source.doi:
            locator = f"https://doi.org/{source.doi}"
        elif source.url:
            locator = source.url.strip()
        text = ", ".join(part for part in parts if part)
        if locator:
            text += f", {locator}"
        return text.rstrip(". ") + "."

    @classmethod
    def footnote_short(cls, source: RegisteredSource) -> str:
        author = cls._author_text(source, short=True)
        title = cls._short_title(source.title)
        return f'{author}, “{title}”.'

    @classmethod
    def bibliography_entry(cls, source: RegisteredSource) -> str:
        author = cls._author_text(source)
        title = (source.title or "Tanpa judul").strip()
        text = f'{author}. “{title}.”'
        if source.venue:
            text += f" {source.venue.strip()}."
        if source.year:
            text += f" {source.year}."
        if source.doi:
            text += f" https://doi.org/{source.doi}."
        elif source.url:
            text += f" {source.url.strip()}"
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def used_ref_ids(spec: MakalahSpec) -> tuple[str, ...]:
        seen: set[str] = set()
        ordered: list[str] = []
        paragraphs = list(spec.preface)
        for section in spec.sections:
            paragraphs.extend(section.paragraphs)
        for paragraph in paragraphs:
            for match in _REF_PATTERN.finditer(paragraph or ""):
                ref_id = match.group(1).upper()
                if ref_id not in seen:
                    seen.add(ref_id)
                    ordered.append(ref_id)
        return tuple(ordered)

    @classmethod
    def _with_bibliography(cls, spec: MakalahSpec, sources: list[RegisteredSource]) -> tuple[MakalahSpec, tuple[str, ...], list[RegisteredSource]]:
        source_map = {source.ref_id.upper(): source for source in sources}
        used_refs = cls.used_ref_ids(spec)
        used_sources = [source_map[ref] for ref in used_refs if ref in source_map]
        if not used_sources:
            return spec, used_refs, []

        # Jangan menambah dua kali bila draft sudah memiliki heading Daftar Pustaka.
        has_bibliography = any(
            re.sub(r"\s+", " ", section.title.strip().casefold()) == "daftar pustaka"
            for section in spec.sections
        )
        if has_bibliography:
            return spec, used_refs, used_sources

        sorted_sources = sorted(
            used_sources,
            key=lambda item: ((item.authors[0] if item.authors else "zzzz").casefold(), item.year or 0, item.title.casefold()),
        )
        entries = tuple(cls.bibliography_entry(source) for source in sorted_sources)
        bibliography = DocumentSection("DAFTAR PUSTAKA", entries, 1)
        return replace(spec, sections=spec.sections + (bibliography,)), used_refs, used_sources

    @staticmethod
    def _apply_word_footnotes(docx_path: Path, sources: list[RegisteredSource], timeout: int = 75) -> str:
        if os.name != "nt":
            return "Footnote Word belum diterapkan: fitur ini membutuhkan Windows + Microsoft Word."
        if not sources:
            return ""

        citation_file = docx_path.with_suffix(".citations.json")
        payload = [
            {
                "ref_id": source.ref_id.upper(),
                "first": CitationEngine.footnote_full(source),
                "repeat": CitationEngine.footnote_short(source),
            }
            for source in sources
        ]
        citation_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        env = os.environ.copy()
        env["TAQI_CITATION_DOCX"] = str(docx_path.resolve())
        env["TAQI_CITATION_JSON"] = str(citation_file.resolve())
        script = r'''
$ErrorActionPreference = 'Stop'
$src = [System.IO.Path]::GetFullPath([string]$env:TAQI_CITATION_DOCX)
$jsonPath = [System.IO.Path]::GetFullPath([string]$env:TAQI_CITATION_JSON)
if (-not (Test-Path -LiteralPath $src -PathType Leaf)) { throw "DOCX tidak ditemukan: $src" }
if (-not (Test-Path -LiteralPath $jsonPath -PathType Leaf)) { throw "Data citation tidak ditemukan: $jsonPath" }
$items = Get-Content -LiteralPath $jsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
$word = $null
$doc = $null
try {
  $word = New-Object -ComObject Word.Application
  $word.Visible = $false
  $word.DisplayAlerts = 0
  $doc = $word.Documents.Open([string]$src)
  try { $doc.Footnotes.Location = 0 } catch {}
  try { $doc.Footnotes.NumberingRule = 0 } catch {}
  try { $doc.Footnotes.StartingNumber = 1 } catch {}
  foreach ($item in $items) {
    $marker = '[[' + [string]$item.ref_id + ']]'
    $firstUse = $true
    $searchStart = 0
    while ($true) {
      $range = $doc.Range($searchStart, $doc.Content.End)
      $find = $range.Find
      $find.ClearFormatting()
      $find.Text = $marker
      $find.Forward = $true
      $find.Wrap = 0
      $found = $find.Execute()
      if (-not $found) { break }
      $position = $range.Start
      $range.Text = ''
      $range.SetRange($position, $position)
      $noteText = if ($firstUse) { [string]$item.first } else { [string]$item.repeat }
      $doc.Footnotes.Add($range, [System.Type]::Missing, $noteText) | Out-Null
      $firstUse = $false
      $searchStart = $position + 1
    }
  }
  $doc.Save()
} finally {
  if ($doc -ne $null) { try { $doc.Close(0) } catch {} }
  if ($word -ne $null) { try { $word.Quit() } catch {} }
}
'''
        try:
            completed = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                env=env,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return f"Footnote Word belum berhasil diterapkan: {exc}"
        finally:
            try:
                citation_file.unlink(missing_ok=True)
            except OSError:
                pass

        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "Microsoft Word gagal menerapkan footnote.").strip()
            return f"Footnote Word belum berhasil diterapkan: {detail[:420]}"
        return ""

    def build(self, spec: MakalahSpec, sources: list[RegisteredSource], *, create_pdf: bool = True) -> CitationBuildResult:
        cited_spec, used_refs, used_sources = self._with_bibliography(spec, sources)
        source_ids = {source.ref_id.upper() for source in sources}
        unknown = tuple(ref for ref in used_refs if ref not in source_ids)
        if unknown:
            return CitationBuildResult(
                "gagal",
                used_refs=used_refs,
                warning="Marker sumber tidak ditemukan di Source Registry: " + ", ".join(unknown),
            )

        try:
            docx_path = self.document_engine.build_docx(cited_spec)
        except (OSError, ValueError) as exc:
            return CitationBuildResult("gagal", used_refs=used_refs, warning=f"Gagal membuat DOCX: {exc}")

        footnote_warning = self._apply_word_footnotes(docx_path, used_sources)
        if footnote_warning:
            return CitationBuildResult(
                "gagal",
                docx_path=str(docx_path),
                used_refs=used_refs,
                warning=footnote_warning,
            )

        pdf_path = None
        pdf_warning = ""
        if create_pdf:
            pdf_path, pdf_warning = self.document_engine.convert_to_pdf(docx_path)

        return CitationBuildResult(
            "berhasil",
            docx_path=str(docx_path),
            pdf_path=str(pdf_path) if pdf_path else "",
            used_refs=used_refs,
            warning=pdf_warning,
        )
