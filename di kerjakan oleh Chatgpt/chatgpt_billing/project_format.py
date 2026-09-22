"""Contoh format memakai DocumentEngine repository, tanpa runtime bot atau API AI."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import zipfile
from functools import lru_cache
from pathlib import Path
from xml.etree import ElementTree as ET

from .artifacts import ArtifactSet
from .workflow import WorkItem

DEMO_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = DEMO_ROOT.parent
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NOTE_MARKER = '[[CATATAN_UJI_FORMAT]]'
NOTE_TEXT = ('Catatan pengujian format. Acuan: kebijakan Document Format Policy - Makalah '
             'dalam repository AnandaAzhari/ai-assistant, policies/document_format_policy.md. '
             'Catatan ini bukan kutipan penelitian akademik.')
REFERENCES = (
    ('Document Format Policy - Makalah', 'policies/document_format_policy.md'),
    ('Document Type Structure Policy', 'policies/document_type_structure_policy.md'),
)


@lru_cache(maxsize=4)
def load_engine(repo_root: Path = REPO_ROOT):
    """Muat hanya modul pembuat DOCX yang tidak mempunyai side effect runtime."""
    path = Path(repo_root).resolve() / 'app' / 'document_engine.py'
    if not path.is_file():
        raise ValueError('app/document_engine.py tidak ditemukan. Jalankan dari folder '
                         'ChatGPT di dalam checkout ai-assistant yang lengkap.')
    name = '_chatgpt_document_engine_' + hashlib.sha256(str(path).encode()).hexdigest()[:12]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # Dataclass memerlukan identitas modul saat import.
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return module


def format_spec(engine, item: WorkItem):
    section = engine.DocumentSection
    return engine.MakalahSpec(
        order_id=item.order_id,
        title=item.brief.title,
        institution='TAQI AI - DOKUMEN UJI FORMAT',
        class_semester='Data contoh',
        subject='Pengujian Format Dokumen',
        author='Penyusun Contoh',
        teacher='Guru atau Dosen Contoh',
        preface=(
            'Dokumen ini merupakan contoh untuk memeriksa format makalah dan alur pembayaran. '
            'Susunan halaman, huruf, paragraf, dan heading mengikuti pembuat dokumen pada '
            'repository ai-assistant. Isi serta identitas sampul merupakan data simulasi '
            'dan tidak mewakili tugas akademik pelanggan.',
            'Pemeriksaan mencakup halaman awal, penomoran bagian, catatan kaki, serta daftar '
            'pustaka. Pembayaran dalam percobaan ini tidak melibatkan uang sebenarnya. '
            'Ketentuan brief yang dicatat untuk percobaan: ' + item.brief.requirements,
        ),
        sections=(
            section('BAB I PENDAHULUAN', (), 1),
            section('A. Latar Belakang', (
                'Format dokumen perlu konsisten dengan ketentuan yang telah disepakati. '
                'Contoh ini memakai DocumentEngine pada repository yang sama dengan AI Assistant. '
                'Acuan tipografi mencakup A4, Times New Roman 12, spasi 1,5, dan paragraf '
                'rata kiri-kanan.' + NOTE_MARKER,
            ), 2),
            section('B. Rumusan Masalah', (
                'Pemeriksaan ini menilai apakah format Word mengikuti aturan proyek. '
                'Pemeriksaan juga membandingkan hasil konversi PDF dengan dokumen Word '
                'dan memastikan pratinjau berasal dari PDF final yang sama.',
            ), 2),
            section('C. Tujuan Penulisan', (
                'Contoh ini membantu owner meninjau susunan dokumen sebelum integrasi Nara. '
                'Hasil pemeriksaan menjadi dasar untuk memperbaiki tampilan yang masih berbeda. '
                'Dokumen ini tidak digunakan untuk menilai mutu riset atau memenuhi target '
                'halaman makalah pelanggan.',
            ), 2),
            section('BAB II PEMBAHASAN', (), 1),
            section('A. Hierarki Bagian', (
                'Kebijakan struktur dokumen proyek menetapkan urutan BAB, huruf kapital, '
                'angka, lalu huruf kecil untuk makalah. Setiap tingkat menggunakan style '
                'heading Word agar dapat dikenali oleh daftar isi. Contoh di bawah '
                'sengaja menampilkan tingkat ketiga dan keempat untuk memeriksa indentasi.',
            ), 2),
            section('1. Pemeriksaan Indentasi', (
                'Judul tingkat ketiga masuk sekitar 0,63 cm dari margin utama. Paragraf '
                'setelah judul tetap memakai blok teks utama dan indentasi baris pertama '
                'sekitar 1,27 cm. Pengaturan dilakukan melalui properti paragraf.',
            ), 3),
            section('a. Paragraf Tingkat Keempat', (
                'Judul tingkat keempat masuk sekitar 1,27 cm dari margin utama. Baris '
                'lanjutan paragrafnya masuk sekitar 0,63 cm, sedangkan baris pertama '
                'mendapat tambahan indentasi sekitar 0,63 cm. Tingkat ini tetap berada '
                'dalam isi tetapi tidak ditampilkan pada daftar isi default.',
            ), 4),
            section('B. Pemeriksaan Pembayaran dan Pratinjau', (
                'Pesanan hanya masuk antrean setelah harga, brief, dan pembayaran awal '
                'memenuhi persyaratan. Pratinjau dibuat dengan memberi watermark pada '
                'PDF hasil konversi Word. File final dilepas setelah versi pratinjau '
                'disetujui dan sisa tagihan nol.',
            ), 2),
            section('BAB III PENUTUP', (), 1),
            section('A. Kesimpulan', (
                'Contoh ini memperlihatkan format dokumen dan batas pembayaran pada '
                'alur percobaan. Word dibuat dengan pembuat dokumen milik proyek, '
                'kemudian dikonversi menjadi PDF. Keberhasilan contoh belum membuktikan '
                'pengerjaan makalah oleh AI atau pengiriman kepada pelanggan.',
            ), 2),
            section('B. Saran', (
                'Owner perlu memeriksa tampilan dokumen di Microsoft Word serta PDF. '
                'Pedoman resmi pelanggan tetap menjadi acuan jika mempunyai ketentuan '
                'khusus. Penyambungan Nara dan Telegram dilanjutkan melalui integrasi '
                'yang menjaga aturan format serta gerbang pembayaran.',
            ), 2),
            section('DAFTAR PUSTAKA', tuple(
                f'AnandaAzhari/ai-assistant. {title}. Dokumen kebijakan repository: {path}.'
                for title, path in REFERENCES
            ), 1),
        ),
    )


def finish_demo_notes(docx: Path) -> None:
    """Catatan uji native dan bibliografi internal; bukan pengganti CitationEngine."""
    ET.register_namespace('w', W)
    ET.register_namespace('r', R)
    q = lambda name: f'{{{W}}}{name}'
    with zipfile.ZipFile(docx) as package:
        parts = {name: package.read(name) for name in package.namelist()}
    document = ET.fromstring(parts['word/document.xml'])
    matches = [r for r in document.iter(q('r'))
               if any(NOTE_MARKER in (t.text or '') for t in r.iter(q('t')))]
    if len(matches) != 1 or 'word/footnotes.xml' in parts:
        raise ValueError('Struktur catatan contoh berubah. Periksa kompatibilitas DocumentEngine.')
    run = matches[0]
    text = next(t for t in run.iter(q('t')) if NOTE_MARKER in (t.text or ''))
    before, after = text.text.split(NOTE_MARKER)
    text.text = before
    parent = next(p for p in document.iter(q('p')) if run in list(p))
    position = list(parent).index(run) + 1
    ref_run = ET.Element(q('r'))
    ET.SubElement(ET.SubElement(ref_run, q('rPr')), q('rStyle'), {q('val'): 'FootnoteReference'})
    ET.SubElement(ref_run, q('footnoteReference'), {q('id'): '1'})
    parent.insert(position, ref_run)
    if after:
        suffix = ET.Element(q('r'))
        ET.SubElement(suffix, q('t')).text = after
        parent.insert(position + 1, suffix)
    bibliography = False
    for paragraph in document.iter(q('p')):
        value = ''.join(t.text or '' for t in paragraph.iter(q('t')))
        if value == 'DAFTAR PUSTAKA':
            bibliography = True
            continue
        if bibliography and value:
            ppr = paragraph.find(q('pPr'))
            ppr.find(q('jc')).set(q('val'), 'left')
            ind = ppr.find(q('ind'))
            if ind is None:
                ind = ET.SubElement(ppr, q('ind'))
            ind.attrib.clear()
            ind.attrib.update({q('left'): '720', q('hanging'): '720'})
            spacing = ppr.find(q('spacing'))
            spacing.attrib.update({q('line'): '240', q('before'): '0', q('after'): '120'})
            for title, _ in REFERENCES:
                if title not in value:
                    continue
                for child in list(paragraph):
                    if child.tag == q('r'):
                        paragraph.remove(child)
                left, right = value.split(title, 1)
                for content, italic in ((left, False), (title, True), (right, False)):
                    new_run = ET.SubElement(paragraph, q('r'))
                    if italic:
                        ET.SubElement(ET.SubElement(new_run, q('rPr')), q('i'))
                    ET.SubElement(new_run, q('t'), {'{http://www.w3.org/XML/1998/namespace}space': 'preserve'}).text = content
    styles = ET.fromstring(parts['word/styles.xml'])
    styles.append(ET.fromstring(f'''<w:style xmlns:w="{W}" w:type="character" w:styleId="FootnoteReference">
      <w:name w:val="footnote reference"/><w:rPr><w:vertAlign w:val="superscript"/></w:rPr></w:style>'''))
    styles.append(ET.fromstring(f'''<w:style xmlns:w="{W}" w:type="paragraph" w:styleId="FootnoteText">
      <w:name w:val="footnote text"/><w:basedOn w:val="Normal"/>
      <w:pPr><w:jc w:val="left"/><w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>
      <w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr></w:style>'''))
    notes = ET.Element(q('footnotes'))
    for identity, kind in (('-1', 'separator'), ('0', 'continuationSeparator')):
        note = ET.SubElement(notes, q('footnote'), {q('id'): identity, q('type'): kind})
        ET.SubElement(ET.SubElement(ET.SubElement(note, q('p')), q('r')), q(kind))
    note = ET.SubElement(notes, q('footnote'), {q('id'): '1'})
    p = ET.SubElement(note, q('p'))
    ET.SubElement(ET.SubElement(p, q('pPr')), q('pStyle'), {q('val'): 'FootnoteText'})
    r = ET.SubElement(p, q('r'))
    ET.SubElement(ET.SubElement(r, q('rPr')), q('rStyle'), {q('val'): 'FootnoteReference'})
    ET.SubElement(r, q('footnoteRef'))
    ET.SubElement(ET.SubElement(p, q('r')), q('t'),
                  {'{http://www.w3.org/XML/1998/namespace}space': 'preserve'}).text = ' ' + NOTE_TEXT
    relationships = ET.fromstring(parts['word/_rels/document.xml.rels'])
    ET.SubElement(relationships, '{http://schemas.openxmlformats.org/package/2006/relationships}Relationship',
                  {'Id': 'rIdChatGPTNotes', 'Type': R + '/footnotes', 'Target': 'footnotes.xml'})
    types = ET.fromstring(parts['[Content_Types].xml'])
    ET.SubElement(types, '{http://schemas.openxmlformats.org/package/2006/content-types}Override',
                  {'PartName': '/word/footnotes.xml', 'ContentType':
                   'application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml'})
    for name, root in (('word/document.xml', document), ('word/styles.xml', styles),
                       ('word/footnotes.xml', notes), ('word/_rels/document.xml.rels', relationships),
                       ('[Content_Types].xml', types)):
        # Office/LibreOffice mengenali metadata paket dengan namespace default.
        if name.endswith('.rels'):
            ET.register_namespace('', 'http://schemas.openxmlformats.org/package/2006/relationships')
        elif name == '[Content_Types].xml':
            ET.register_namespace('', 'http://schemas.openxmlformats.org/package/2006/content-types')
        parts[name] = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    with zipfile.ZipFile(docx, 'w', zipfile.ZIP_DEFLATED) as package:
        for name, content in parts.items():
            package.writestr(name, content)


class ProjectFormatWorker:
    """Memakai engine asli dengan workspace eksplisit; tidak memanggil from_env()."""

    def __init__(self, repo_root: Path = REPO_ROOT, *, converter=None, preview_builder=None,
                 build_root: Path | None = None):
        from .pdf_preview import make_preview, require_pypdf
        require_pypdf()
        self.repo_root = Path(repo_root).resolve()
        self.module = load_engine(self.repo_root)
        self.converter = converter or self.module.DocumentEngine.convert_to_pdf
        self._uses_project_converter = converter is None
        self.preview_builder = preview_builder or make_preview
        self.build_root = Path(build_root) if build_root else DEMO_ROOT / 'runtime' / 'format_builds'

    def produce(self, item: WorkItem) -> ArtifactSet:
        self.build_root.mkdir(parents=True, exist_ok=True)
        # Build sementara memakai path pendek dalam folder demo, untuk Windows.
        with tempfile.TemporaryDirectory(prefix='format-', dir=self.build_root) as temporary:
            engine = self.module.DocumentEngine(root=temporary)
            built = engine.build_docx(format_spec(self.module, item))
            docx = item.output_dir / 'hasil.docx'
            shutil.move(str(built), docx)
        finish_demo_notes(docx)
        pdf, warning = self.converter(docx)
        if warning or pdf is None or not Path(pdf).is_file():
            raise ValueError('Konversi PDF belum berhasil. ' + (warning or 'PDF hasil Word tidak tersedia.'))
        pdf = Path(pdf)
        if self._uses_project_converter:
            from .demo_toc import ensure_demo_toc
            pdf = ensure_demo_toc(docx, pdf, self.converter)
        if not pdf.resolve().is_relative_to(item.output_dir.resolve()):
            raise ValueError('PDF konversi harus berada di folder percobaan yang sama.')
        preview = item.output_dir / 'pratinjau.pdf'
        self.preview_builder(pdf, preview)
        sources = ['app/document_engine.py', 'policies/document_format_policy.md',
                   'policies/document_type_structure_policy.md', 'skills/document_academic/SKILL.md',
                   'skills/document_academic/CITATION_STYLE.md']
        provenance = {'worker': 'ProjectFormatWorker', 'ai_used': False,
                      'pdf_origin': 'Konversi DOCX melalui DocumentEngine', 'sources': {}}
        for relative in sources:
            provenance['sources'][relative] = hashlib.sha256((self.repo_root / relative).read_bytes()).hexdigest()
        (item.output_dir / 'ACUAN_FORMAT.json').write_text(json.dumps(provenance, indent=2), encoding='utf-8')
        return ArtifactSet(docx, pdf, preview)
