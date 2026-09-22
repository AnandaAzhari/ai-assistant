"""Pekerja contoh offline dan adapter Nara siap-draft untuk integrasi oleh Claude."""
from __future__ import annotations

import textwrap
import zipfile
from pathlib import Path
from typing import Callable
from xml.sax.saxutils import escape

from .artifacts import ArtifactSet
from .workflow import WorkItem


def _pdf(path: Path, paragraphs: list[str], *, preview: bool) -> None:
    """PDF fixture sederhana tanpa dependensi. Bukan pengganti renderer Nara."""
    lines = []
    for paragraph in paragraphs:
        lines.extend(textwrap.wrap(paragraph, 78) or [''])
        lines.append('')
    pages = [lines[i:i + 43] for i in range(0, len(lines), 43)] or [[]]
    objects: list[bytes] = []
    objects.append(b'<< /Type /Catalog /Pages 2 0 R >>')
    kids = ' '.join(f'{4 + i * 2} 0 R' for i in range(len(pages)))
    objects.append(f'<< /Type /Pages /Count {len(pages)} /Kids [{kids}] >>'.encode())
    objects.append(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>')

    def literal(text: str) -> bytes:
        return text.encode('cp1252', errors='replace').replace(b'\\', b'\\\\').replace(b'(', b'\\(').replace(b')', b'\\)')

    for i, page in enumerate(pages):
        objects.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] '
                       f'/Resources << /Font << /F1 3 0 R >> >> /Contents {5 + i * 2} 0 R >>'.encode())
        stream = bytearray()
        if preview:
            stream.extend(b'q 0.90 g BT /F1 32 Tf 0.707 0.707 -0.707 0.707 80 250 Tm '
                          b'(PRATINJAU - SIMULASI) Tj ET Q\n')
        stream.extend(b'BT /F1 11 Tf 0 g 50 748 Td 15 TL\n')
        for line in page:
            stream.extend(b'(' + literal(line) + b') Tj T*\n')
        stream.extend(b'ET\nBT /F1 9 Tf 50 30 Td (' + literal(
            f'Halaman {i + 1}/{len(pages)} | CONTOH UJI ALUR | ' + ('PRATINJAU' if preview else 'FINAL DEMO')) + b') Tj ET')
        objects.append(f'<< /Length {len(stream)} >>\nstream\n'.encode() + stream + b'\nendstream')
    result = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(result))
        result.extend(f'{i} 0 obj\n'.encode() + obj + b'\nendobj\n')
    offset = len(result)
    result.extend(f'xref\n0 {len(objects) + 1}\n0000000000 65535 f \n'.encode())
    for position in offsets[1:]:
        result.extend(f'{position:010d} 00000 n \n'.encode())
    result.extend(f'trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{offset}\n%%EOF\n'.encode())
    path.write_bytes(result)


def _docx(path: Path, paragraphs: list[str]) -> None:
    ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    body = []
    for i, text in enumerate(paragraphs):
        style = 'Title' if i == 0 else ('Heading1' if text.startswith('BAB ') else 'Normal')
        note = '<w:r><w:footnoteReference w:id="1"/></w:r>' if i == 1 else ''
        body.append(f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr><w:r><w:t xml:space="preserve">'
                    f'{escape(text)}</w:t></w:r>{note}</w:p>')
    xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    document = xml + f'<w:document xmlns:w="{ns}"><w:body>' + ''.join(body) + (
        '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/>'
        '<w:pgMar w:top="1000" w:right="1100" w:bottom="1000" w:left="1100"/>'
        '</w:sectPr></w:body></w:document>')
    types = xml + '''<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/word/footnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"/>
</Types>'''
    relns = 'http://schemas.openxmlformats.org/package/2006/relationships'
    office = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
    root_rels = xml + f'<Relationships xmlns="{relns}"><Relationship Id="rId1" Type="{office}officeDocument" Target="word/document.xml"/></Relationships>'
    rels = xml + f'<Relationships xmlns="{relns}"><Relationship Id="rId1" Type="{office}styles" Target="styles.xml"/><Relationship Id="rId2" Type="{office}footnotes" Target="footnotes.xml"/></Relationships>'
    styles = xml + f'''<w:styles xmlns:w="{ns}">
<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="22"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="140" w:line="270" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:after="240"/></w:pPr><w:rPr><w:b/><w:sz w:val="32"/><w:color w:val="000000"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="200" w:after="100"/></w:pPr><w:rPr><w:b/><w:sz w:val="24"/></w:rPr></w:style>
</w:styles>'''
    footnotes = xml + f'<w:footnotes xmlns:w="{ns}"><w:footnote w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:footnote><w:footnote w:id="1"><w:p><w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:footnoteRef/></w:r><w:r><w:t xml:space="preserve"> Catatan uji teknis tanpa rujukan akademik.</w:t></w:r></w:p></w:footnote></w:footnotes>'
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in {'[Content_Types].xml': types, '_rels/.rels': root_rels,
                           'word/document.xml': document, 'word/styles.xml': styles,
                           'word/_rels/document.xml.rels': rels, 'word/footnotes.xml': footnotes}.items():
            z.writestr(name, data.encode('utf-8'))


class OfflineDemoWorker:
    """Menghasilkan fixture singkat; tidak memakai AI dan tidak memenuhi target halaman pesanan."""

    def produce(self, item: WorkItem) -> ArtifactSet:
        paragraphs = [
            'Contoh hasil uji alur dokumen',
            'SIMULASI. Dokumen singkat ini menguji antrean, pratinjau, dan pembayaran. '
            'Isinya bukan makalah pesanan pelanggan dan belum melalui riset akademik.',
            'Judul brief: ' + item.brief.title,
            'Ketentuan: ' + item.brief.requirements,
            'BAB I PENDAHULUAN',
            '1.1 Tujuan pengujian',
            'Pesanan hanya boleh mulai dikerjakan setelah harga disetujui, brief dicatat, '
            'dan pembayaran awal terpenuhi. Semua nominal pada demo adalah simulasi.',
            'BAB II PEMBAHASAN',
            '2.1 Antrean dan pemeriksaan hasil',
            'Pekerja menghasilkan Word, PDF final, dan PDF pratinjau. Sistem memeriksa '
            'struktur dasar serta menyimpan hash file untuk mendeteksi perubahan.',
            '2.2 Persetujuan dan pelunasan',
            'Pratinjau diperiksa terlebih dahulu. File final dapat disalin ke folder '
            'penyerahan setelah versi pratinjau itu disetujui dan sisa tagihan nol.',
            'BAB III PENUTUP',
            'Uji ini selesai ketika Word dan PDF final tersedia di folder penyerahan. '
            'Pengiriman Telegram dan pengerjaan AI Nara memerlukan integrasi runtime.',
            'Catatan 1: catatan uji teknis tanpa rujukan akademik.',
        ]
        artifacts = ArtifactSet(item.output_dir / 'hasil.docx', item.output_dir / 'hasil.pdf',
                                item.output_dir / 'pratinjau.pdf')
        _docx(artifacts.docx, paragraphs[:-1])  # Word memakai footnote asli, bukan catatan ganda.
        _pdf(artifacts.final_pdf, paragraphs, preview=False)
        _pdf(artifacts.preview_pdf, paragraphs, preview=True)
        return artifacts


class PreparedNaraWorker:
    """Adapter nyata untuk DocumentAgent yang draft-nya sudah siap/disetujui.

    factory(item) mengembalikan instance Nara per pesanan, dengan workspace dan
    database uji terisolasi. preview_builder(final_pdf, output_path) harus membuat
    PDF ber-watermark dari PDF asli. Tidak ada import app/ atau .env otomatis.
    Pengumpulan brief, persetujuan kerangka, riset, dan AI draft tetap milik Nara.
    """

    def __init__(self, factory: Callable, preview_builder: Callable):
        self.factory, self.preview_builder = factory, preview_builder

    def produce(self, item: WorkItem) -> ArtifactSet:
        agent = self.factory(item)
        if getattr(agent, 'phase', None) not in ('draft_ready', 'final_ready'):
            raise ValueError('Draft Nara belum siap. Lengkapi riset dan persetujuan di alur Nara.')
        result = agent.build_final()
        if getattr(result, 'status', None) != 'final_ready':
            raise ValueError('Nara belum berhasil menghasilkan file final; periksa status dan sumbernya.')
        paths = [Path(getattr(agent, key, '') or '__missing__') for key in ('final_docx_path', 'final_pdf_path')]
        for path in paths:
            if not path.is_file() or not path.resolve().is_relative_to(item.output_dir.resolve()):
                raise ValueError('Nara harus menghasilkan DOCX dan PDF di folder percobaan ini.')
        preview = item.output_dir / 'pratinjau.pdf'
        self.preview_builder(paths[1], preview)
        return ArtifactSet(paths[0], paths[1], preview)
