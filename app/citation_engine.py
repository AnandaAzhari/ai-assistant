"""Footnote + Daftar Pustaka Engine untuk dokumen akademik Taqi AI.

Citation Engine mengurus marker sumber, footnote Word asli, daftar pustaka, update
Daftar Isi, dan ekspor PDF. Struktur section serta nomor halaman dibuat langsung oleh
DocumentEngine di OOXML agar tidak berubah-ubah saat Word melakukan repagination.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path

from app.document_engine import DocumentEngine, DocumentSection, MakalahSpec
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
    STYLE_NAME = "Chicago Notes & Bibliography"
    FOOTNOTE_FONT = "Times New Roman"
    FOOTNOTE_SIZE = 10
    IBID_TEXT = "Ibid."
    DEFAULT_REPEAT_MODE = "auto"
    VALID_REPEAT_MODES = ("auto", "short")
    # Pesan tetap dari _apply_word_footnotes saat server ini bukan Windows (mis. VPS
    # Linux produksi) sehingga footnote Word COM memang tidak tersedia -- bukan
    # kegagalan sungguhan. build() memakai konstanta ini (bukan mencocokkan teks
    # bebas) supaya HANYA kasus "tidak ada Word di platform ini" yang dianggap
    # non-fatal; error Word COM yang sesungguhnya di Windows (timeout, dokumen
    # corrupt, dll) tetap dianggap "gagal" seperti sebelumnya.
    NO_WORD_WARNING = "Footnote Word belum diterapkan: fitur ini membutuhkan Windows + Microsoft Word."

    def __init__(self, document_engine: DocumentEngine):
        self.document_engine = document_engine

    @property
    def status_text(self) -> str:
        return (
            f"Footnote + Daftar Pustaka Engine siap. Default: {self.STYLE_NAME}. "
            "citation_repeat_mode=auto; pelanggan dapat memilih short untuk tanpa Ibid."
        )

    @staticmethod
    def _clean(value: str) -> str:
        return re.sub(r"\s+", " ", (value or "").strip())

    @classmethod
    def normalize_repeat_mode(cls, value: str | None) -> str:
        """Normalisasi preferensi pengulangan citation per order.

        `auto`  : full note -> Ibid. untuk pengulangan langsung -> short note jika diselingi.
        `short` : full note pada kemunculan pertama -> semua pengulangan memakai short note.
        """
        raw = cls._clean(value or cls.DEFAULT_REPEAT_MODE).casefold().replace("-", "_").replace(" ", "_")
        aliases = {
            "auto": "auto",
            "default": "auto",
            "ibid": "auto",
            "with_ibid": "auto",
            "pakai_ibid": "auto",
            "short": "short",
            "short_note": "short",
            "no_ibid": "short",
            "without_ibid": "short",
            "tanpa_ibid": "short",
            "jangan_pakai_ibid": "short",
        }
        mode = aliases.get(raw, raw)
        if mode not in cls.VALID_REPEAT_MODES:
            raise ValueError(
                "citation_repeat_mode tidak dikenal. Gunakan 'auto' atau 'short'."
            )
        return mode

    @classmethod
    def _split_name(cls, name: str) -> tuple[str, str]:
        clean = cls._clean(name)
        parts = clean.split()
        if len(parts) <= 1:
            return clean, ""
        return parts[-1], " ".join(parts[:-1])

    @classmethod
    def _note_authors(cls, source: RegisteredSource, *, short: bool = False) -> str:
        authors = [cls._clean(name) for name in source.authors if cls._clean(name)]
        if not authors:
            return "Penulis tidak tercantum"
        if short:
            surname, _ = cls._split_name(authors[0])
            return surname or authors[0]
        if len(authors) == 1:
            return authors[0]
        if len(authors) == 2:
            return f"{authors[0]} dan {authors[1]}"
        return f"{authors[0]} dkk."

    @classmethod
    def _bibliography_authors(cls, source: RegisteredSource) -> str:
        authors = [cls._clean(name) for name in source.authors if cls._clean(name)]
        if not authors:
            return "Penulis tidak tercantum"
        first_last, first_given = cls._split_name(authors[0])
        first = f"{first_last}, {first_given}" if first_given else first_last
        if len(authors) == 1:
            return first
        if len(authors) == 2:
            return f"{first}, dan {authors[1]}"
        if len(authors) <= 10:
            return f"{first}, " + ", ".join(authors[1:-1]) + f", dan {authors[-1]}"
        return f"{first}, " + ", ".join(authors[1:7]) + ", dkk."

    @classmethod
    def _sort_key(cls, source: RegisteredSource) -> tuple[str, int, str]:
        if source.authors:
            surname, _ = cls._split_name(source.authors[0])
            author_key = surname.casefold()
        else:
            author_key = "zzzz"
        return author_key, source.year or 0, cls._clean(source.title).casefold()

    @staticmethod
    def _short_title(title: str, max_words: int = 6) -> str:
        """Judul singkat untuk repeat note tanpa elipsis/titik-titik buatan."""
        words = re.sub(r"\s+", " ", (title or "").strip()).split()
        if not words:
            return "Tanpa judul"
        return " ".join(words[:max_words])

    @classmethod
    def footnote_full(cls, source: RegisteredSource) -> str:
        """Catatan kaki lengkap untuk kemunculan pertama sebuah sumber."""
        author = cls._note_authors(source)
        title = cls._clean(source.title) or "Tanpa judul"
        venue = cls._clean(source.venue)
        details = ""
        if source.volume:
            details += f" {source.volume}"
        if source.issue:
            details += f", no. {source.issue}"
        if source.year:
            details += f" ({source.year})"
        if source.pages:
            details += f": {source.pages}"
        if venue:
            text = f'{author}, “{title},” {venue}{details}'
        else:
            publisher = cls._clean(source.publisher)
            if publisher and source.year:
                text = f"{author}, {title} ({publisher}, {source.year})"
            elif source.year:
                text = f"{author}, {title} ({source.year})"
            else:
                text = f"{author}, {title}"
        locator = f"https://doi.org/{source.doi}" if source.doi else cls._clean(source.url)
        if locator:
            text += f", {locator}"
        return text.rstrip(". ") + "."

    @classmethod
    def footnote_short(cls, source: RegisteredSource) -> str:
        """Short note untuk pengulangan sumber yang sudah pernah dipakai."""
        author = cls._note_authors(source, short=True)
        title = cls._short_title(source.title)
        return f'{author}, “{title}.”'

    @classmethod
    def note_plan(
        cls,
        ref_ids: tuple[str, ...] | list[str],
        *,
        repeat_mode: str = "auto",
    ) -> tuple[tuple[str, str], ...]:
        """Rencana full/ibid/short berdasarkan urutan catatan kaki dan preferensi order."""
        mode = cls.normalize_repeat_mode(repeat_mode)
        seen: set[str] = set()
        previous = ""
        plan: list[tuple[str, str]] = []
        for value in ref_ids:
            ref_id = str(value or "").strip().upper()
            if not ref_id:
                continue
            if ref_id not in seen:
                kind = "full"
            elif mode == "auto" and ref_id == previous:
                kind = "ibid"
            else:
                kind = "short"
            plan.append((ref_id, kind))
            seen.add(ref_id)
            previous = ref_id
        return tuple(plan)

    @classmethod
    def bibliography_entry(cls, source: RegisteredSource) -> str:
        author = cls._bibliography_authors(source)
        title = cls._clean(source.title) or "Tanpa judul"
        venue = cls._clean(source.venue)
        work_type = cls._clean(source.work_type).casefold()
        locator = f"https://doi.org/{source.doi}" if source.doi else cls._clean(source.url)
        is_article = bool(venue) or "article" in work_type or "journal" in work_type

        if is_article:
            text = f'{author}. “{title}.”'
            if venue:
                text += f" {venue}"
            if source.volume:
                text += f" {source.volume}"
            if source.issue:
                text += f", no. {source.issue}"
            if source.year:
                text += f" ({source.year})"
            if source.pages:
                text += f": {source.pages}"
            text += "."
        else:
            text = f"{author}. {title}."
            if source.publisher:
                text += f" {cls._clean(source.publisher)}"
                if source.year:
                    text += f", {source.year}"
                text += "."
            elif source.year:
                text += f" {source.year}."
        if locator:
            text += f" {locator}."
        return re.sub(r"\s+", " ", text).strip()

    @classmethod
    def _is_bibliography_title(cls, title: str) -> bool:
        clean = cls._clean(title).casefold()
        clean = re.sub(r"^[ivxlcdm]+\.\s*", "", clean, flags=re.IGNORECASE)
        return clean == "daftar pustaka"

    @classmethod
    def _bibliography_title(cls, spec: MakalahSpec) -> str:
        """Makalah default selalu memakai judul DAFTAR PUSTAKA tanpa nomor BAB/Romawi."""
        return "DAFTAR PUSTAKA"

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
    def _with_bibliography(
        cls,
        spec: MakalahSpec,
        sources: list[RegisteredSource],
    ) -> tuple[MakalahSpec, tuple[str, ...], list[RegisteredSource]]:
        source_map = {source.ref_id.upper(): source for source in sources}
        used_refs = cls.used_ref_ids(spec)
        used_sources = [source_map[ref] for ref in used_refs if ref in source_map]
        if not used_sources:
            return spec, used_refs, []
        if any(cls._is_bibliography_title(section.title) for section in spec.sections):
            return spec, used_refs, used_sources

        sorted_sources = sorted(used_sources, key=cls._sort_key)
        entries = tuple(cls.bibliography_entry(source) for source in sorted_sources)
        bibliography = DocumentSection(cls._bibliography_title(spec), entries, 1)
        return replace(spec, sections=spec.sections + (bibliography,)), used_refs, used_sources

    @staticmethod
    def _apply_word_footnotes(
        docx_path: Path,
        sources: list[RegisteredSource],
        *,
        citation_repeat_mode: str = "auto",
        create_pdf: bool = True,
        timeout: int = 90,
    ) -> str:
        if os.name != "nt":
            return CitationEngine.NO_WORD_WARNING

        repeat_mode = CitationEngine.normalize_repeat_mode(citation_repeat_mode)
        citation_file = docx_path.with_suffix(".citations.json")
        payload = []
        for source in sources:
            work_type = CitationEngine._clean(source.work_type).casefold()
            is_article = bool(CitationEngine._clean(source.venue)) or "article" in work_type or "journal" in work_type
            payload.append({
                "ref_id": source.ref_id.upper(),
                "first": CitationEngine.footnote_full(source),
                "repeat": CitationEngine.footnote_short(source),
                "ibid": CitationEngine.IBID_TEXT,
                "title": CitationEngine._clean(source.title),
                "venue": CitationEngine._clean(source.venue),
                "is_article": is_article,
            })
        citation_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        env = os.environ.copy()
        env["TAQI_CITATION_DOCX"] = str(docx_path.resolve())
        env["TAQI_CITATION_JSON"] = str(citation_file.resolve())
        env["TAQI_CITATION_PDF"] = str(docx_path.with_suffix(".pdf").resolve()) if create_pdf else ""
        env["TAQI_FOOTNOTE_FONT"] = CitationEngine.FOOTNOTE_FONT
        env["TAQI_FOOTNOTE_SIZE"] = str(CitationEngine.FOOTNOTE_SIZE)
        env["TAQI_CITATION_REPEAT_MODE"] = repeat_mode

        script = r'''
$ErrorActionPreference = 'Stop'
$src = [System.IO.Path]::GetFullPath([string]$env:TAQI_CITATION_DOCX)
$jsonPath = [System.IO.Path]::GetFullPath([string]$env:TAQI_CITATION_JSON)
$pdfOut = [string]$env:TAQI_CITATION_PDF
$footnoteFont = [string]$env:TAQI_FOOTNOTE_FONT
$footnoteSize = [double]$env:TAQI_FOOTNOTE_SIZE
$repeatMode = ([string]$env:TAQI_CITATION_REPEAT_MODE).Trim().ToLowerInvariant()
if ([string]::IsNullOrWhiteSpace($repeatMode)) { $repeatMode = 'auto' }
if (-not [string]::IsNullOrWhiteSpace($pdfOut)) { $pdfOut = [System.IO.Path]::GetFullPath($pdfOut) }
if (-not (Test-Path -LiteralPath $src -PathType Leaf)) { throw "DOCX tidak ditemukan: $src" }
if (-not (Test-Path -LiteralPath $jsonPath -PathType Leaf)) { throw "Data citation tidak ditemukan: $jsonPath" }
$items = Get-Content -LiteralPath $jsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
$itemMap = @{}
foreach ($item in $items) { $itemMap[[string]$item.ref_id] = $item }
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

  # Tahap 1: marker internal -> footnote Word dengan token sumber sementara.
  foreach ($item in $items) {
    $marker = '[[' + [string]$item.ref_id + ']]'
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
      $token = '[[TAQI_REF:' + [string]$item.ref_id + ']]'
      $doc.Footnotes.Add($range, [System.Type]::Missing, $token) | Out-Null
      $searchStart = $position + 1
    }
  }

  # Tahap 2: format berdasarkan citation_repeat_mode order.
  # auto  = full -> Ibid. bila sumber sama persis dengan note sebelumnya -> short.
  # short = full -> semua pengulangan short note; tidak pernah memakai Ibid.
  $seen = @{}
  $previousRef = ''
  foreach ($fn in $doc.Footnotes) {
    $raw = (($fn.Range.Text -replace '[\r\a]+$','').Trim())
    if ($raw -notmatch '^\[\[TAQI_REF:(R\d+)\]\]$') { continue }
    $refId = [string]$Matches[1]
    if (-not $itemMap.ContainsKey($refId)) { continue }
    $item = $itemMap[$refId]

    $isFirst = -not $seen.ContainsKey($refId)
    $isImmediateRepeat = (-not $isFirst) -and ($previousRef -eq $refId)
    if ($isFirst) {
      $noteText = [string]$item.first
    } elseif (($repeatMode -eq 'auto') -and $isImmediateRepeat) {
      $noteText = [string]$item.ibid
    } else {
      $noteText = [string]$item.repeat
    }

    $r = $fn.Range
    try {
      if ($r.End -gt $r.Start -and $r.Text.EndsWith("`r")) { $r.End = $r.End - 1 }
      $r.Text = $noteText
    } catch {}

    # Default tampilan footnote: TNR 10 pt, rata kiri, spasi tunggal.
    $r = $fn.Range
    try { $r.Font.Name = $footnoteFont } catch {}
    try { $r.Font.NameAscii = $footnoteFont } catch {}
    try { $r.Font.NameFarEast = $footnoteFont } catch {}
    try { $r.Font.Size = $footnoteSize } catch {}
    try { $r.Font.Bold = 0 } catch {}
    try { $r.Font.Italic = 0 } catch {}
    try { $r.ParagraphFormat.Alignment = 0 } catch {}
    try { $r.ParagraphFormat.LineSpacingRule = 0 } catch {}
    try { $r.ParagraphFormat.SpaceBefore = 0 } catch {}
    try { $r.ParagraphFormat.SpaceAfter = 0 } catch {}
    try { $r.ParagraphFormat.LeftIndent = 0 } catch {}
    try { $r.ParagraphFormat.RightIndent = 0 } catch {}
    try { $r.ParagraphFormat.FirstLineIndent = 0 } catch {}

    # Pada full note artikel jurnal, nama jurnal/venue dicetak miring.
    if ($isFirst -and [bool]$item.is_article -and -not [string]::IsNullOrWhiteSpace([string]$item.venue)) {
      $venueSearch = $fn.Range.Duplicate
      $venueFind = $venueSearch.Find
      $venueFind.ClearFormatting()
      $venueFind.Text = [string]$item.venue
      $venueFind.Forward = $true
      $venueFind.Wrap = 0
      if ($venueFind.Execute()) { try { $venueSearch.Font.Italic = 1 } catch {} }
    }

    $seen[$refId] = $true
    $previousRef = $refId
  }

  # Rapikan heading dan isi Daftar Pustaka.
  $bibliographyStart = -1
  foreach ($p in $doc.Paragraphs) {
    $text = (($p.Range.Text -replace '[\r\a]+$','').Trim())
    if ($text -match '^(?:[IVXLCDM]+\.\s*)?DAFTAR PUSTAKA$') {
      $bibliographyStart = $p.Range.End
      try { $p.Range.ParagraphFormat.Alignment = 1 } catch {}
      try { $p.Range.ParagraphFormat.LeftIndent = 0 } catch {}
      try { $p.Range.ParagraphFormat.FirstLineIndent = 0 } catch {}
      try { $p.Range.ParagraphFormat.SpaceBefore = 0 } catch {}
      try { $p.Range.ParagraphFormat.SpaceAfter = 12 } catch {}
      try { $p.Range.Font.Bold = 1 } catch {}
      try { $p.Range.Font.Italic = 0 } catch {}
      break
    }
  }

  if ($bibliographyStart -ge 0) {
    $biblioRange = $doc.Range($bibliographyStart, $doc.Content.End)
    foreach ($p in $biblioRange.Paragraphs) {
      $text = (($p.Range.Text -replace '[\r\a]+$','').Trim())
      if ([string]::IsNullOrWhiteSpace($text)) { continue }
      try { $p.Range.ParagraphFormat.Alignment = 0 } catch {}
      try { $p.Range.ParagraphFormat.LeftIndent = 36 } catch {}
      try { $p.Range.ParagraphFormat.FirstLineIndent = -36 } catch {}
      try { $p.Range.ParagraphFormat.RightIndent = 0 } catch {}
      try { $p.Range.ParagraphFormat.LineSpacingRule = 0 } catch {}
      try { $p.Range.ParagraphFormat.SpaceBefore = 0 } catch {}
      try { $p.Range.ParagraphFormat.SpaceAfter = 6 } catch {}
      try { $p.Range.ParagraphFormat.KeepTogether = -1 } catch {}
      try { $p.Range.Font.Bold = 0 } catch {}
      try { $p.Range.Font.Italic = 0 } catch {}
    }

    foreach ($item in $items) {
      $needle = if ([bool]$item.is_article -and -not [string]::IsNullOrWhiteSpace([string]$item.venue)) {
        [string]$item.venue
      } else {
        [string]$item.title
      }
      if ([string]::IsNullOrWhiteSpace($needle)) { continue }
      $search = $doc.Range($bibliographyStart, $doc.Content.End)
      $find = $search.Find
      $find.ClearFormatting()
      $find.Text = $needle
      $find.Forward = $true
      $find.Wrap = 0
      if ($find.Execute()) { try { $search.Font.Italic = 1 } catch {} }
    }
  }

  # Nomor halaman sudah native OOXML. Word hanya diminta menghitung ulang field dan TOC.
  try { $doc.Repaginate() } catch {}
  foreach ($section in $doc.Sections) {
    foreach ($footer in $section.Footers) {
      try { $footer.Range.Fields.Update() | Out-Null } catch {}
    }
  }
  try { $doc.Fields.Update() | Out-Null } catch {}
  foreach ($toc in $doc.TablesOfContents) { try { $toc.Update() | Out-Null } catch {} }
  try { $doc.Repaginate() } catch {}

  # Rapikan daftar isi: default Makalah hanya sampai Heading 3.
  foreach ($toc in $doc.TablesOfContents) {
    foreach ($p in $toc.Range.Paragraphs) {
      $text = (($p.Range.Text -replace '[\r\a]+$','').Trim())
      if ([string]::IsNullOrWhiteSpace($text)) { continue }
      try { $p.Range.ParagraphFormat.Alignment = 0 } catch {}
      try { $p.Range.ParagraphFormat.FirstLineIndent = 0 } catch {}
      try { $p.Range.ParagraphFormat.SpaceBefore = 0 } catch {}
      try { $p.Range.ParagraphFormat.SpaceAfter = 0 } catch {}
      if (($text -match '^BAB\s+[IVXLCDM]+\b') -or ($text -match '^DAFTAR PUSTAKA\b')) {
        try { $p.Range.ParagraphFormat.LeftIndent = 0 } catch {}
      } elseif ($text -match '^[A-Z]\.\s+\S') {
        try { $p.Range.ParagraphFormat.LeftIndent = 18 } catch {}
      } elseif ($text -match '^\d+\.\s+\S') {
        try { $p.Range.ParagraphFormat.LeftIndent = 36 } catch {}
      }
    }
  }

  try { $doc.Repaginate() } catch {}
  foreach ($toc in $doc.TablesOfContents) { try { $toc.Update() | Out-Null } catch {} }
  try { $doc.Repaginate() } catch {}
  $doc.Save()

  if (-not [string]::IsNullOrWhiteSpace($pdfOut)) {
    if (Test-Path -LiteralPath $pdfOut) { Remove-Item -LiteralPath $pdfOut -Force }
    $doc.ExportAsFixedFormat([string]$pdfOut, 17)
  }
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
            return f"Footnote/daftar pustaka/PDF belum berhasil diterapkan: {exc}"
        finally:
            try:
                citation_file.unlink(missing_ok=True)
            except OSError:
                pass
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "Microsoft Word gagal memproses dokumen.").strip()
            return f"Footnote/daftar pustaka/PDF belum berhasil diterapkan: {detail[:420]}"
        return ""

    def build(
        self,
        spec: MakalahSpec,
        sources: list[RegisteredSource],
        *,
        create_pdf: bool = True,
        citation_repeat_mode: str = "auto",
    ) -> CitationBuildResult:
        try:
            repeat_mode = self.normalize_repeat_mode(citation_repeat_mode)
        except ValueError as exc:
            return CitationBuildResult("gagal", warning=str(exc))

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

        footnote_warning = self._apply_word_footnotes(
            docx_path,
            used_sources,
            citation_repeat_mode=repeat_mode,
            create_pdf=create_pdf,
        )
        # Dulu: warning apa pun di sini (termasuk "server ini bukan Windows") membuat
        # build() langsung "gagal" total -- akibatnya di VPS Linux (tidak pernah punya
        # Microsoft Word) status final_ready TIDAK PERNAH bisa tercapai sama sekali,
        # walau DOCX (OOXML murni lewat DocumentEngine.build_docx, tidak butuh Word)
        # dan PDF (lewat LibreOffice di convert_to_pdf, lihat app/document_engine.py)
        # sebenarnya tetap berhasil dibuat tanpa Word sama sekali. Sekarang HANYA kasus
        # "tidak ada Word di platform ini" (NO_WORD_WARNING) yang diperlakukan sebagai
        # catatan non-fatal -- proses tetap lanjut ke "berhasil" supaya pelanggan/admin
        # tetap menerima DOCX+PDF (footnote otomatis Word saja yang belum diterapkan).
        # Error Word COM yang sesungguhnya di Windows (timeout, dokumen corrupt, dll)
        # tetap dianggap "gagal" seperti perilaku lama.
        if footnote_warning and footnote_warning != CitationEngine.NO_WORD_WARNING:
            return CitationBuildResult(
                "gagal", docx_path=str(docx_path), used_refs=used_refs, warning=footnote_warning,
            )

        pdf_path: Path | None = None
        pdf_warning = ""
        if create_pdf:
            same_session_pdf = docx_path.with_suffix(".pdf")
            if same_session_pdf.is_file():
                pdf_path = same_session_pdf
            else:
                pdf_path, pdf_warning = self.document_engine.convert_to_pdf(docx_path)

        combined_warning = " ".join(w for w in (footnote_warning, pdf_warning) if w)
        return CitationBuildResult(
            "berhasil",
            docx_path=str(docx_path),
            pdf_path=str(pdf_path) if pdf_path else "",
            used_refs=used_refs,
            warning=combined_warning,
        )
