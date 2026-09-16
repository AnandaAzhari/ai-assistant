"""Document Engine v0.5 untuk membuat DOCX/PDF lokal tanpa memboroskan token AI.

DOCX dibuat langsung dengan Open XML menggunakan Python standard library.
Penomoran halaman tidak lagi ditambal oleh Word COM: section cover, bagian awal,
dan isi utama dibuat langsung di struktur DOCX agar Word/PDF stabil.

Default Makalah mengikuti policy Taqi AI: BAB I -> A. -> 1. -> a.
"""

from __future__ import annotations

import os
import re
import subprocess
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape


@dataclass(frozen=True)
class DocumentSection:
    title: str
    paragraphs: tuple[str, ...] = ()
    level: int = 1


@dataclass(frozen=True)
class MakalahSpec:
    order_id: str
    title: str
    institution: str
    class_semester: str
    subject: str
    author: str = ""
    teacher: str = ""
    year: str = ""
    group_name: str = ""
    members: tuple[str, ...] = field(default_factory=tuple)
    preface: tuple[str, ...] = field(default_factory=tuple)
    sections: tuple[DocumentSection, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DocumentBuildResult:
    status: str
    docx_path: str = ""
    pdf_path: str = ""
    warning: str = ""


class DocumentEngine:
    def __init__(self, root: str | Path = "workspace/documents"):
        self.root = Path(root)

    @classmethod
    def from_env(cls) -> "DocumentEngine":
        root = os.environ.get("DOCUMENT_WORKSPACE", "workspace/documents").strip() or "workspace/documents"
        return cls(root)

    @property
    def status_text(self) -> str:
        return (
            f"Document Engine siap. Workspace: {self.root}. "
            "Nomor halaman native DOCX: cover tanpa nomor, bagian awal Romawi, isi Arab mulai 1."
        )

    @staticmethod
    def _safe_name(value: str, fallback: str = "dokumen") -> str:
        value = re.sub(r"[^A-Za-z0-9._-]+", "-", (value or "").strip()).strip("-._")
        return value[:80] or fallback

    @staticmethod
    def _run(text: str, *, bold: bool = False, size: int | None = None) -> str:
        props: list[str] = []
        if bold:
            props.append("<w:b/>")
        if size:
            props.append(f'<w:sz w:val="{int(size) * 2}"/><w:szCs w:val="{int(size) * 2}"/>')
        rpr = f"<w:rPr>{''.join(props)}</w:rPr>" if props else ""
        parts = str(text or "").split("\n")
        content: list[str] = []
        for index, part in enumerate(parts):
            if index:
                content.append("<w:br/>")
            content.append(f'<w:t xml:space="preserve">{escape(part)}</w:t>')
        return f'<w:r>{rpr}{"".join(content)}</w:r>'

    @classmethod
    def _paragraph(
        cls,
        text: str = "",
        *,
        style: str = "Normal",
        align: str = "both",
        bold: bool = False,
        size: int | None = None,
        before: int = 0,
        after: int = 120,
        line: int = 360,
        left: int = 0,
        first_line: int = 0,
    ) -> str:
        ppr = [f'<w:pStyle w:val="{style}"/>'] if style else []
        if align:
            ppr.append(f'<w:jc w:val="{align}"/>')
        if left or first_line:
            ppr.append(f'<w:ind w:left="{int(left)}" w:firstLine="{int(first_line)}"/>')
        ppr.append(f'<w:spacing w:before="{before}" w:after="{after}" w:line="{line}" w:lineRule="auto"/>')
        return f'<w:p><w:pPr>{"".join(ppr)}</w:pPr>{cls._run(text, bold=bold, size=size)}</w:p>'

    @staticmethod
    def _page_break() -> str:
        return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'

    @staticmethod
    def _toc() -> str:
        return (
            '<w:p><w:pPr><w:jc w:val="left"/></w:pPr>'
            '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
            '<w:r><w:instrText xml:space="preserve"> TOC \\o "1-4" \\h \\z \\u </w:instrText></w:r>'
            '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
            '<w:r><w:t>Daftar isi akan diperbarui saat dokumen dibuka di Microsoft Word.</w:t></w:r>'
            '<w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>'
        )

    @staticmethod
    def _page_geometry() -> str:
        return (
            '<w:pgSz w:w="11906" w:h="16838"/>'
            '<w:pgMar w:top="1701" w:right="1701" w:bottom="1701" w:left="2268" '
            'w:header="720" w:footer="720" w:gutter="0"/>'
        )

    @classmethod
    def _section_properties(
        cls,
        *,
        footer_rid: str | None = None,
        number_format: str | None = None,
        start: int | None = None,
        next_page: bool = False,
    ) -> str:
        parts: list[str] = ["<w:sectPr>"]
        if footer_rid:
            parts.append(f'<w:footerReference w:type="default" r:id="{footer_rid}"/>')
        if next_page:
            parts.append('<w:type w:val="nextPage"/>')
        parts.append(cls._page_geometry())
        if number_format or start is not None:
            attrs: list[str] = []
            if number_format:
                attrs.append(f'w:fmt="{number_format}"')
            if start is not None:
                attrs.append(f'w:start="{int(start)}"')
            parts.append(f'<w:pgNumType {" ".join(attrs)}/>')
        parts.append("</w:sectPr>")
        return "".join(parts)

    @classmethod
    def _section_break(
        cls,
        *,
        footer_rid: str | None = None,
        number_format: str | None = None,
        start: int | None = None,
    ) -> str:
        sect = cls._section_properties(
            footer_rid=footer_rid,
            number_format=number_format,
            start=start,
            next_page=True,
        )
        return f"<w:p><w:pPr>{sect}</w:pPr></w:p>"

    @staticmethod
    def _footer_xml() -> str:
        return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:p>
    <w:pPr><w:jc w:val="center"/></w:pPr>
    <w:r><w:fldChar w:fldCharType="begin"/></w:r>
    <w:r><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>
    <w:r><w:fldChar w:fldCharType="separate"/></w:r>
    <w:r><w:t>1</w:t></w:r>
    <w:r><w:fldChar w:fldCharType="end"/></w:r>
  </w:p>
</w:ftr>'''

    @staticmethod
    def _legacy_chapter_title(title: str) -> str:
        cleaned = re.sub(r"\s+", " ", (title or "").strip())
        match = re.match(r"^(BAB\s+[IVXLCDM]+)\s+(.+)$", cleaned, flags=re.IGNORECASE)
        if not match:
            return title
        return f"{match.group(1).upper()}\n{match.group(2).upper()}"

    @staticmethod
    def _infer_heading_level(title: str, fallback: int) -> int:
        clean = re.sub(r"\s+", " ", (title or "").strip())
        # Penting: level utama Makalah hanya dikenali melalui label BAB.
        # Huruf C, D, M, dst. bisa merupakan angka Romawi, tetapi dalam pola
        # Makalah "C. Tujuan" tetap subbab (Heading 2), bukan Heading 1.
        if re.match(r"^BAB\s+[IVXLCDM]+\b", clean, re.IGNORECASE):
            return 1
        if re.match(r"^[A-Z]\.\s+\S", clean):
            return 2
        if re.match(r"^\d+\.\s+\S", clean):
            return 3
        if re.match(r"^[a-z]\.\s+\S", clean):
            return 4
        if re.match(r"^\d+\.\d+\.\d+\s+\S", clean):
            return 3
        if re.match(r"^\d+\.\d+\s+\S", clean):
            return 2
        return max(1, min(int(fallback or 1), 4))

    @staticmethod
    def _heading_left(level: int) -> int:
        return {1: 0, 2: 360, 3: 720, 4: 1080}.get(level, 0)

    @staticmethod
    def _styles_xml() -> str:
        return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault><w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="Times New Roman"/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr></w:rPrDefault>
    <w:pPrDefault><w:pPr><w:spacing w:line="360" w:lineRule="auto"/></w:pPr></w:pPrDefault>
  </w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:qFormat/><w:rPr><w:b/><w:sz w:val="32"/><w:szCs w:val="32"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:spacing w:before="240" w:after="120"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:spacing w:before="180" w:after="80"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:spacing w:before="120" w:after="60"/><w:outlineLvl w:val="2"/></w:pPr><w:rPr><w:b/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading4"><w:name w:val="heading 4"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:spacing w:before="100" w:after="40"/><w:outlineLvl w:val="3"/></w:pPr><w:rPr><w:b/></w:rPr></w:style>
</w:styles>'''

    @staticmethod
    def _settings_xml() -> str:
        return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:updateFields w:val="true"/></w:settings>'''

    @staticmethod
    def _content_types_xml() -> str:
        return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
  <Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>
  <Override PartName="/word/footer2.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>'''

    @staticmethod
    def _root_rels_xml() -> str:
        return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>'''

    @staticmethod
    def _document_rels_xml() -> str:
        return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>
  <Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer2.xml"/>
</Relationships>'''

    @staticmethod
    def _core_xml(title: str) -> str:
        now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>{escape(title)}</dc:title><dc:creator>Taqi AI Document Engine</dc:creator><cp:lastModifiedBy>Taqi AI Document Engine</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>
</cp:coreProperties>'''

    @staticmethod
    def _app_xml() -> str:
        return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>Taqi AI Document Engine</Application></Properties>'''

    def _document_xml(self, spec: MakalahSpec) -> str:
        body: list[str] = []

        # SECTION 1 — COVER: sengaja tanpa footer/nomor halaman.
        body.append(self._paragraph("MAKALAH", align="center", bold=True, size=16, after=220))
        body.append(self._paragraph(spec.title.upper(), align="center", bold=True, size=16, after=260))
        body.append(self._paragraph(f"Disusun untuk Memenuhi Tugas Mata Pelajaran/Mata Kuliah {spec.subject}", align="center", after=120))
        if spec.teacher:
            body.append(self._paragraph(f"Guru/Dosen Pembimbing: {spec.teacher}", align="center", after=160))

        if spec.group_name or spec.members or spec.author:
            body.append(self._paragraph("Disusun Oleh:", align="center", bold=True, after=80))
        if spec.group_name:
            body.append(self._paragraph(spec.group_name, align="center", bold=True, after=60))
        if spec.members:
            for member in spec.members:
                if member.strip():
                    body.append(self._paragraph(member.strip(), align="center", after=30, line=240))
        elif spec.author:
            body.append(self._paragraph(spec.author, align="center", after=80))
        body.append(self._paragraph(f"KELAS/SEMESTER: {spec.class_semester}", align="center", bold=True, after=90))
        body.append(self._paragraph(spec.institution.upper(), align="center", bold=True, after=80))
        body.append(self._paragraph(spec.year or str(datetime.now().year), align="center", bold=True, after=80))
        body.append(self._section_break())

        # SECTION 2 — BAGIAN AWAL: footer PAGE + lowerRoman mulai i.
        if spec.preface:
            body.append(self._paragraph("KATA PENGANTAR", align="center", bold=True, size=14, after=220))
            for paragraph in spec.preface:
                if paragraph.strip():
                    body.append(self._paragraph(paragraph.strip(), align="both", first_line=709))
            body.append(self._page_break())
        body.append(self._paragraph("DAFTAR ISI", align="center", bold=True, size=14))
        body.append(self._toc())
        body.append(self._section_break(footer_rid="rId3", number_format="lowerRoman", start=1))

        # SECTION 3 — ISI UTAMA: footer PAGE + decimal mulai 1.
        chapter_seen = False
        for section in spec.sections:
            level = self._infer_heading_level(section.title, section.level)
            clean_title = re.sub(r"\s+", " ", section.title.strip())
            is_chapter = bool(re.match(r"^BAB\s+", clean_title, re.IGNORECASE))
            is_bibliography = clean_title.casefold() == "daftar pustaka"

            # BAB I sudah dimulai oleh section break dari Daftar Isi. BAB berikutnya
            # wajib dimulai pada halaman baru agar konsisten dengan format makalah.
            if is_chapter:
                if chapter_seen:
                    body.append(self._page_break())
                chapter_seen = True

            title = self._legacy_chapter_title(section.title) if is_chapter else section.title
            align = "center" if (is_chapter or is_bibliography) else "left"
            body.append(
                self._paragraph(
                    title,
                    style=f"Heading{level}",
                    align=align,
                    bold=True,
                    size=14 if level == 1 else 12,
                    left=0 if (is_chapter or is_bibliography) else self._heading_left(level),
                )
            )
            for paragraph in section.paragraphs:
                if paragraph.strip():
                    body.append(self._paragraph(paragraph.strip(), align="both", first_line=709))

        body.append(
            self._section_properties(
                footer_rid="rId4",
                number_format="decimal",
                start=1,
                next_page=False,
            )
        )
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<w:body>{"".join(body)}</w:body></w:document>'
        )

    def build_docx(self, spec: MakalahSpec) -> Path:
        order_id = self._safe_name(spec.order_id, "DOC")
        folder = self.root / order_id / "final"
        folder.mkdir(parents=True, exist_ok=True)
        filename = self._safe_name(spec.title, "makalah") + ".docx"
        output = folder / filename

        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as package:
            package.writestr("[Content_Types].xml", self._content_types_xml())
            package.writestr("_rels/.rels", self._root_rels_xml())
            package.writestr("word/document.xml", self._document_xml(spec))
            package.writestr("word/styles.xml", self._styles_xml())
            package.writestr("word/settings.xml", self._settings_xml())
            package.writestr("word/_rels/document.xml.rels", self._document_rels_xml())
            package.writestr("word/footer1.xml", self._footer_xml())
            package.writestr("word/footer2.xml", self._footer_xml())
            package.writestr("docProps/core.xml", self._core_xml(spec.title))
            package.writestr("docProps/app.xml", self._app_xml())
        return output

    @staticmethod
    def convert_to_pdf(docx_path: Path, timeout: int = 75) -> tuple[Path | None, str]:
        """Convert DOCX ke PDF memakai Microsoft Word COM bila tersedia."""
        if os.name != "nt":
            return None, "PDF belum dibuat: konversi Word COM hanya tersedia di Windows pada tahap ini."
        try:
            src_path = docx_path.resolve(strict=True)
        except (OSError, FileNotFoundError) as exc:
            return None, f"PDF belum dibuat otomatis: file DOCX tidak ditemukan ({exc})."

        pdf_path = src_path.with_suffix(".pdf")
        ps_env = os.environ.copy()
        ps_env["TAQI_DOCX_SOURCE"] = str(src_path)
        ps_env["TAQI_PDF_DEST"] = str(pdf_path)
        script = r'''
$ErrorActionPreference = 'Stop'
$src = [System.IO.Path]::GetFullPath([string]$env:TAQI_DOCX_SOURCE)
$dst = [System.IO.Path]::GetFullPath([string]$env:TAQI_PDF_DEST)
if (-not (Test-Path -LiteralPath $src -PathType Leaf)) { throw "DOCX tidak ditemukan: $src" }
$word = $null
$doc = $null
try {
  if (Test-Path -LiteralPath $dst) { Remove-Item -LiteralPath $dst -Force }
  $word = New-Object -ComObject Word.Application
  $word.Visible = $false
  $word.DisplayAlerts = 0
  $doc = $word.Documents.Open([string]$src)
  try { $doc.Repaginate() } catch {}
  try { $doc.Fields.Update() | Out-Null } catch {}
  foreach ($toc in $doc.TablesOfContents) { try { $toc.Update() | Out-Null } catch {} }
  try { $doc.Repaginate() } catch {}
  $doc.Save()
  $doc.ExportAsFixedFormat([string]$dst, 17)
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
                env=ps_env,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return None, f"PDF belum dibuat otomatis: {exc}"

        if completed.returncode != 0 or not pdf_path.is_file():
            detail = (completed.stderr or completed.stdout or "Microsoft Word tidak tersedia.").strip()
            return None, f"PDF belum dibuat otomatis: {detail[:360]}"
        return pdf_path, ""

    def build(self, spec: MakalahSpec, *, create_pdf: bool = True) -> DocumentBuildResult:
        try:
            docx_path = self.build_docx(spec)
        except (OSError, ValueError, zipfile.BadZipFile) as exc:
            return DocumentBuildResult("gagal", warning=f"Gagal membuat DOCX: {exc}")

        pdf_path: Path | None = None
        warning = ""
        if create_pdf:
            pdf_path, warning = self.convert_to_pdf(docx_path)

        return DocumentBuildResult(
            "berhasil",
            str(docx_path),
            str(pdf_path) if pdf_path else "",
            warning,
        )


def demo_spec() -> MakalahSpec:
    """Data demo lokal untuk menguji format Makalah tanpa memakai token AI."""
    return MakalahSpec(
        order_id="DEMO-MAKALAH",
        title="Pencemaran Lingkungan",
        institution="Taqi DocuTech - Dokumen Uji",
        class_semester="XI",
        subject="Biologi",
        teacher="Contoh Guru",
        group_name="Kelompok 4",
        members=("Anggota Satu", "Anggota Dua", "Anggota Tiga"),
        year=str(datetime.now().year),
        preface=(
            "Puji syukur kami panjatkan ke hadirat Tuhan Yang Maha Esa karena makalah ini dapat diselesaikan dengan baik.",
            "Makalah ini dibuat sebagai dokumen uji untuk memastikan struktur dan penomoran halaman Taqi AI.",
        ),
        sections=(
            DocumentSection("BAB I PENDAHULUAN", (), 1),
            DocumentSection("A. Latar Belakang", (
                "Pencemaran lingkungan merupakan perubahan kondisi lingkungan akibat masuknya zat, energi, atau komponen lain yang dapat menurunkan kualitas lingkungan.",
            ), 2),
            DocumentSection("B. Rumusan Masalah", (
                "Rumusan masalah disusun untuk menentukan pokok persoalan yang akan dibahas dalam makalah.",
            ), 2),
            DocumentSection("C. Tujuan Penulisan", (
                "Tujuan penulisan makalah ini adalah menjelaskan penyebab, dampak, dan upaya mengurangi pencemaran lingkungan.",
            ), 2),
            DocumentSection("BAB II PEMBAHASAN", (), 1),
            DocumentSection("A. Pengertian Pencemaran", (
                "Pencemaran dapat terjadi pada air, udara, dan tanah.",
            ), 2),
            DocumentSection("B. Jenis Pencemaran", (), 2),
            DocumentSection("1. Pencemaran Air", (
                "Pencemaran air terjadi ketika kualitas air menurun akibat masuknya bahan pencemar.",
            ), 3),
            DocumentSection("a. Sumber Pencemar", (
                "Sumber pencemar air dapat berasal dari kegiatan rumah tangga, industri, dan aktivitas lain.",
            ), 4),
            DocumentSection("BAB III PENUTUP", (), 1),
            DocumentSection("A. Kesimpulan", (
                "Upaya pencegahan pencemaran membutuhkan kesadaran bersama dan pengelolaan lingkungan yang bertanggung jawab.",
            ), 2),
            DocumentSection("B. Saran", (
                "Masyarakat perlu mengurangi sumber pencemar dan menjaga kebersihan lingkungan secara konsisten.",
            ), 2),
        ),
    )