"""Regresi format yang disepakati; render Word COM tetap diuji di PC Windows."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from xml.etree import ElementTree as ET

from chatgpt_billing.project_format import ProjectFormatWorker, REPO_ROOT, NOTE_MARKER, load_engine
from chatgpt_billing.pdf_preview import make_preview, STAMP_TEXT
from chatgpt_billing.workflow import Brief, WorkItem, WorkflowStore
from chatgpt_billing.pricing import QuoteRequest, make_quote
from chatgpt_billing.workers import _pdf
from chatgpt_billing import demo_toc

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


class ProjectFormatTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='format makalah ')
        self.root = Path(self.temp.name)
        self.output = self.root / 'hasil'
        self.output.mkdir()
        self.item = WorkItem('DEMO-FORMAT', Brief('Uji Format Makalah'), 1, 'token', self.output)
        self.seen_docx = None

    def tearDown(self):
        self.temp.cleanup()

    def converter(self, docx):
        self.seen_docx = docx
        _pdf(docx.with_suffix('.pdf'), ['HALAMAN DARI KONVERSI', 'Isi contoh converter uji.'], preview=False)
        return docx.with_suffix('.pdf'), ''

    def produce(self):
        worker = ProjectFormatWorker(converter=self.converter, build_root=self.root / 'build')
        return worker.produce(self.item)

    def parts(self, path):
        with zipfile.ZipFile(path) as package:
            return {name: ET.fromstring(package.read(name)) for name in
                    ('word/document.xml', 'word/styles.xml', 'word/footnotes.xml')}

    def test_loads_exact_project_engine_without_starting_runtime(self):
        engine = load_engine()
        self.assertEqual(Path(engine.__file__).resolve(), (REPO_ROOT / 'app/document_engine.py').resolve())
        self.assertEqual(engine.DocumentEngine._page_geometry(),
                         load_engine(REPO_ROOT).DocumentEngine._page_geometry())
        self.assertFalse((self.root / 'data/assistant.db').exists())

    def test_missing_project_engine_is_clear_error(self):
        with self.assertRaisesRegex(ValueError, 'checkout ai-assistant'):
            load_engine(self.root)

    def test_document_uses_a4_margins_and_times_new_roman(self):
        parts = self.parts(self.produce().docx)
        doc, styles = parts['word/document.xml'], parts['word/styles.xml']
        for section in doc.iter(W + 'sectPr'):
            self.assertEqual(section.find(W + 'pgSz').attrib, {W + 'w': '11906', W + 'h': '16838'})
            margins = section.find(W + 'pgMar')
            self.assertEqual(margins.get(W + 'left'), '2268')
            self.assertEqual([margins.get(W + k) for k in ('top','right','bottom')], ['1701'] * 3)
        defaults = styles.find(W + 'docDefaults')
        self.assertEqual(defaults.find('.//' + W + 'rFonts').get(W + 'ascii'), 'Times New Roman')
        self.assertEqual(defaults.find('.//' + W + 'sz').get(W + 'val'), '24')

    def test_heading_hierarchy_body_indent_and_new_chapter_pages(self):
        doc = self.parts(self.produce().docx)['word/document.xml']
        paragraphs = list(doc.find(W + 'body'))
        headings = {}
        for i, p in enumerate(paragraphs):
            text = ''.join(t.text or '' for t in p.iter(W + 't'))
            ppr = p.find(W + 'pPr')
            style = ppr.find(W + 'pStyle') if ppr is not None else None
            if style is not None and style.get(W + 'val').startswith('Heading'):
                headings[text] = style.get(W + 'val')
                if text.startswith(('BAB II','BAB III','DAFTAR PUSTAKA')):
                    self.assertIsNotNone(paragraphs[i-1].find('.//' + W + 'br'))
        self.assertEqual(headings['A. Latar Belakang'], 'Heading2')
        self.assertEqual(headings['1. Pemeriksaan Indentasi'], 'Heading3')
        self.assertEqual(headings['a. Paragraf Tingkat Keempat'], 'Heading4')
        for text in headings:
            self.assertNotIn('1.1', text)
        body = next(p for p in doc.iter(W+'p') if ''.join(t.text or '' for t in p.iter(W+'t')).startswith('Format dokumen perlu'))
        props = body.find(W+'pPr')
        self.assertEqual(props.find(W+'jc').get(W+'val'), 'both')
        self.assertEqual(props.find(W+'spacing').get(W+'line'), '360')
        self.assertEqual(props.find(W+'ind').get(W+'firstLine'), '720')

    def test_cover_front_matter_body_numbering_and_toc_depth(self):
        doc = self.parts(self.produce().docx)['word/document.xml']
        sections = list(doc.iter(W+'sectPr'))
        self.assertEqual(len(sections), 3)
        self.assertIsNone(sections[0].find(W+'footerReference'))
        self.assertEqual(sections[1].find(W+'pgNumType').attrib, {W+'fmt':'lowerRoman', W+'start':'1'})
        self.assertEqual(sections[2].find(W+'pgNumType').attrib, {W+'fmt':'decimal', W+'start':'1'})
        self.assertIn('TOC \\o "1-3"', ''.join(x.text or '' for x in doc.iter(W+'instrText')))

    def test_native_footnote_style_and_bibliography_layout(self):
        parts = self.parts(self.produce().docx)
        doc, styles, notes = (parts[k] for k in ('word/document.xml','word/styles.xml','word/footnotes.xml'))
        self.assertNotIn(NOTE_MARKER, ET.tostring(doc, encoding='unicode'))
        self.assertEqual(len(list(doc.iter(W+'footnoteReference'))), 1)
        self.assertEqual(len(list(notes.iter(W+'footnoteRef'))), 1)
        note_style = next(s for s in styles.iter(W+'style') if s.get(W+'styleId')=='FootnoteText')
        self.assertEqual(note_style.find('.//'+W+'sz').get(W+'val'), '20')
        self.assertEqual(note_style.find('.//'+W+'spacing').get(W+'line'), '240')
        ref_style = next(s for s in styles.iter(W+'style') if s.get(W+'styleId')=='FootnoteReference')
        self.assertEqual(ref_style.find('.//'+W+'vertAlign').get(W+'val'), 'superscript')
        entries = [p for p in doc.iter(W+'p') if ''.join(t.text or '' for t in p.iter(W+'t')).startswith('AnandaAzhari/')]
        self.assertEqual(len(entries), 2)
        for entry in entries:
            props = entry.find(W+'pPr')
            self.assertEqual(props.find(W+'jc').get(W+'val'), 'left')
            self.assertEqual(props.find(W+'ind').get(W+'hanging'), '720')
            self.assertEqual(props.find(W+'spacing').get(W+'line'), '240')
            self.assertIsNotNone(entry.find('.//'+W+'i'))

    def test_package_metadata_keeps_office_compatible_namespaces(self):
        with zipfile.ZipFile(self.produce().docx) as package:
            for name, root in (('[Content_Types].xml', 'Types'),
                               ('word/_rels/document.xml.rels', 'Relationships')):
                content = package.read(name).decode('utf-8')
                self.assertIn('<' + root + ' xmlns=', content)
                self.assertNotIn('<ns0:', content)

    def test_windows_unupdated_toc_is_blocked(self):
        artifacts = self.produce()
        with patch.object(demo_toc, 'os', SimpleNamespace(name='nt')):
            with self.assertRaisesRegex(ValueError, 'belum memperbarui daftar isi'):
                demo_toc.ensure_demo_toc(artifacts.docx, artifacts.final_pdf, self.converter)

    def test_linux_toc_caches_real_page_numbers_and_preserves_field(self):
        from pypdf import PdfReader, PdfWriter
        artifacts = self.produce()
        pages = [
            ['SAMPUL'], ['KATA PENGANTAR'], ['DAFTAR ISI'],
            ['BAB I PENDAHULUAN', 'A. Latar Belakang', 'B. Rumusan Masalah', 'C. Tujuan Penulisan'],
            ['BAB II PEMBAHASAN', 'A. Hierarki Bagian', '1. Pemeriksaan Indentasi',
             'a. Paragraf Tingkat Keempat', 'B. Pemeriksaan Pembayaran dan Pratinjau'],
            ['BAB III PENUTUP', 'A. Kesimpulan', 'B. Saran'], ['DAFTAR PUSTAKA'],
        ]
        writer = PdfWriter()
        for i, lines in enumerate(pages):
            page_file = self.root / f'page-{i}.pdf'
            _pdf(page_file, lines, preview=False)
            writer.append(PdfReader(page_file))
        writer.write(artifacts.final_pdf)
        with patch.object(demo_toc, 'os', SimpleNamespace(name='posix')):
            result = demo_toc.ensure_demo_toc(artifacts.docx, artifacts.final_pdf,
                                             lambda docx: (artifacts.final_pdf, ''))
        self.assertEqual(result, artifacts.final_pdf)
        document = self.parts(artifacts.docx)['word/document.xml']
        serialized = ET.tostring(document, encoding='unicode')
        self.assertNotIn(demo_toc.PLACEHOLDER, serialized)
        self.assertIn('TOC \\o "1-3"', ''.join(x.text or '' for x in document.iter(W+'instrText')))
        entries = [p for p in document.iter(W+'p') if p.find(W+'r/'+W+'tab') is not None]
        texts = [''.join(t.text or '' for t in p.iter(W+'t')) for p in entries]
        self.assertIn('BAB I PENDAHULUAN1', texts)
        self.assertIn('BAB II PEMBAHASAN2', texts)
        self.assertIn('DAFTAR PUSTAKA4', texts)
        self.assertFalse(any('Tingkat Keempat' in t for t in texts))

    def test_linux_toc_stops_when_page_numbers_keep_changing(self):
        artifacts = self.produce()
        mappings = [[(1, 'BAB I PENDAHULUAN', str(i))] for i in range(6)]
        with patch.object(demo_toc, 'os', SimpleNamespace(name='posix')), \
             patch.object(demo_toc, '_entries', side_effect=mappings), \
             patch.object(demo_toc, '_cache'):
            with self.assertRaisesRegex(ValueError, 'belum stabil setelah tiga render'):
                demo_toc.ensure_demo_toc(artifacts.docx, artifacts.final_pdf, self.converter)

    def test_preview_keeps_converted_pdf_and_source_unchanged(self):
        from pypdf import PdfReader
        artifacts = self.produce()
        self.assertEqual(self.seen_docx, artifacts.docx)
        final = PdfReader(artifacts.final_pdf)
        preview = PdfReader(artifacts.preview_pdf)
        self.assertEqual(len(final.pages), len(preview.pages))
        self.assertNotIn(STAMP_TEXT, final.pages[0].extract_text())
        self.assertIn('HALAMAN DARI KONVERSI', preview.pages[0].extract_text())
        self.assertIn(STAMP_TEXT, preview.pages[0].extract_text())
        before = artifacts.final_pdf.read_bytes()
        make_preview(artifacts.final_pdf, self.output/'kedua.pdf')
        self.assertEqual(artifacts.final_pdf.read_bytes(), before)

    def test_conversion_failure_blocks_order_without_fake_pdf(self):
        store = WorkflowStore(self.root/'queue.db', self.root/'workflow')
        try:
            order = store.create_order(make_quote(QuoteRequest()), approved_by='tester')
            store.accept_quote(order.order_id, actor='customer')
            store.register_brief(order.order_id, Brief('Format'), actor='customer')
            store.simulate_payment(order.order_id, 'dp', 18000)
            worker = ProjectFormatWorker(converter=lambda docx: (None, 'Word tidak tersedia'),
                                         build_root=self.root/'build')
            result = store.run_next(worker)
            self.assertEqual(result['state'], 'blocked')
            self.assertIn('Word tidak tersedia', result['problem'])
            self.assertFalse(list((self.root/'workflow').rglob('hasil.pdf')))
        finally:
            store.close()

    def test_provenance_records_actual_engine_hash(self):
        self.produce()
        data = json.loads((self.output/'ACUAN_FORMAT.json').read_text())
        engine = REPO_ROOT/'app/document_engine.py'
        self.assertEqual(data['sources']['app/document_engine.py'], hashlib.sha256(engine.read_bytes()).hexdigest())
        self.assertFalse(data['ai_used'])

    def test_watermark_on_every_page_with_different_page_sizes(self):
        from pypdf import PdfReader, PdfWriter
        source, result = self.output/'sizes.pdf', self.output/'preview.pdf'
        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)
        writer.add_blank_page(width=842, height=595)
        writer.write(source)
        make_preview(source, result)
        original, preview = PdfReader(source), PdfReader(result)
        for a, b in zip(original.pages, preview.pages):
            self.assertEqual(tuple(a.mediabox), tuple(b.mediabox))
            self.assertIn(STAMP_TEXT, b.extract_text())


if __name__ == '__main__':
    unittest.main()
