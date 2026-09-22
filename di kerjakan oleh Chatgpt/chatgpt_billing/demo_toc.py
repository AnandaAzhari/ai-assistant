"""Cache TOC contoh untuk LibreOffice; Word tetap memakai update field engine asli."""
from __future__ import annotations

import os
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
PLACEHOLDER = 'Daftar isi akan diperbarui saat dokumen dibuka di Microsoft Word.'


def _parts(docx):
    with zipfile.ZipFile(docx) as package:
        return {name: package.read(name) for name in package.namelist()}


def _entries(document, pdf):
    from pypdf import PdfReader
    paragraphs = list(document.find(W+'body'))
    headings = []
    for paragraph in paragraphs:
        style = paragraph.find(W+'pPr/'+W+'pStyle')
        if style is None or style.get(W+'val') not in ('Heading1','Heading2','Heading3'):
            continue
        value = ''.join((node.text or '') if node.tag == W+'t' else '\n'
                        for node in paragraph.iter() if node.tag in (W+'t', W+'br'))
        headings.append((int(style.get(W+'val')[-1]), ' '.join(value.split())))
    if not headings:
        raise ValueError('Heading untuk daftar isi tidak ditemukan.')
    normalize = lambda text: ' '.join(text.split())
    texts = [normalize(page.extract_text()) for page in PdfReader(pdf).pages]
    # Cover/preface tidak mempunyai baris heading BAB; seluruh TOC juga memuat BAB II.
    first = headings[0][1]
    second_chapter = next(title for level, title in headings[1:] if level == 1)
    starts = [i for i, text in enumerate(texts) if first in text and second_chapter not in text]
    if len(starts) != 1:
        raise ValueError('Halaman BAB I tidak dapat dipastikan. Periksa render daftar isi.')
    start = starts[0]
    entries = []
    for level, title in headings:
        found = [i for i in range(start, len(texts)) if title in texts[i]]
        if len(found) != 1:
            raise ValueError('Halaman heading tidak unik: ' + title)
        entries.append((level, title, str(found[0]-start+1)))
    return entries


def _cache(docx, parts, entries):
    document = ET.fromstring(parts['word/document.xml'])
    body = document.find(W+'body')
    begin = next((i for i, p in enumerate(body)
                  if any('TOC ' in (x.text or '') for x in p.iter(W+'instrText'))), None)
    if begin is None:
        raise ValueError('Field daftar isi hilang.')
    end = begin
    for end in range(begin, len(body)):
        if any(x.get(W+'fldCharType') == 'end' for x in body[end].iter(W+'fldChar')):
            break
    else:
        raise ValueError('Field daftar isi tidak lengkap.')
    for _ in range(end-begin+1):
        body.remove(body[begin])
    for i, (level, title, page) in enumerate(entries):
        p = ET.Element(W+'p')
        props = ET.SubElement(p, W+'pPr')
        ET.SubElement(props, W+'jc', {W+'val': 'left'})
        ET.SubElement(props, W+'ind', {W+'left': str((level-1)*360)})
        ET.SubElement(props, W+'spacing', {W+'line': '240', W+'lineRule': 'auto', W+'after': '80'})
        ET.SubElement(ET.SubElement(props, W+'tabs'), W+'tab',
                      {W+'val': 'right', W+'leader': 'dot', W+'pos': '7937'})
        if i == 0:
            ET.SubElement(ET.SubElement(p, W+'r'), W+'fldChar', {W+'fldCharType': 'begin'})
            ET.SubElement(ET.SubElement(p, W+'r'), W+'instrText',
                          {'{http://www.w3.org/XML/1998/namespace}space':'preserve'}).text = ' TOC \\o "1-3" \\h \\z \\u '
            ET.SubElement(ET.SubElement(p, W+'r'), W+'fldChar', {W+'fldCharType': 'separate'})
        ET.SubElement(ET.SubElement(p, W+'r'), W+'t').text = title
        ET.SubElement(ET.SubElement(p, W+'r'), W+'tab')
        ET.SubElement(ET.SubElement(p, W+'r'), W+'t').text = page
        if i == len(entries)-1:
            ET.SubElement(ET.SubElement(p, W+'r'), W+'fldChar', {W+'fldCharType': 'end'})
        body.insert(begin+i, p)
    parts['word/document.xml'] = ET.tostring(document, encoding='utf-8', xml_declaration=True)
    with zipfile.ZipFile(docx, 'w', zipfile.ZIP_DEFLATED) as package:
        for name, value in parts.items():
            package.writestr(name, value)


def ensure_demo_toc(docx: Path, pdf: Path, converter) -> Path:
    parts = _parts(docx)
    if PLACEHOLDER not in parts['word/document.xml'].decode('utf-8'):
        return pdf  # Word COM sudah memperbarui field dan menyimpan DOCX sebelum export.
    if os.name == 'nt':
        raise ValueError('Microsoft Word belum memperbarui daftar isi. Tahan hasil dan periksa konversinya.')
    for _ in range(3):
        before = _entries(ET.fromstring(parts['word/document.xml']), pdf)
        _cache(docx, parts, before)
        pdf, warning = converter(docx)
        if warning or pdf is None:
            raise ValueError('Konversi setelah pembaruan daftar isi gagal: ' + (warning or 'PDF tidak tersedia.'))
        pdf = Path(pdf)
        parts = _parts(docx)
        if _entries(ET.fromstring(parts['word/document.xml']), pdf) == before:
            return pdf
    raise ValueError('Nomor halaman daftar isi belum stabil setelah tiga render. Perlu pemeriksaan.')
