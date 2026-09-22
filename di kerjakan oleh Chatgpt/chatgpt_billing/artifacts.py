"""Pemeriksaan struktur dasar + hash file. Bukan penilai kebenaran akademik/layout."""
from __future__ import annotations

import hashlib
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

MAX_FILE_BYTES = 32 * 1024 * 1024
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


@dataclass(frozen=True)
class ArtifactSet:
    docx: Path
    final_pdf: Path
    preview_pdf: Path


def file_info(path: Path, root: Path) -> dict:
    path, root = Path(path), Path(root).resolve()
    resolved = path.resolve()
    if path.is_symlink() or not resolved.is_relative_to(root) or not path.is_file():
        raise ValueError('File hasil hilang atau berada di luar folder pengerjaan.')
    size = path.stat().st_size
    if not 0 < size <= MAX_FILE_BYTES:
        raise ValueError('File kosong atau melebihi batas demo 32 MB.')
    data = path.read_bytes()
    return {'path': resolved.relative_to(root).as_posix(), 'size': len(data),
            'sha256': hashlib.sha256(data).hexdigest()}


def check_docx(path: Path) -> dict:
    try:
        with zipfile.ZipFile(path) as z:
            entries = z.infolist()
            if len(entries) > 2000 or sum(i.file_size for i in entries) > MAX_FILE_BYTES:
                raise ValueError('Isi DOCX melebihi batas pemeriksaan demo.')
            for name in ('[Content_Types].xml', '_rels/.rels', 'word/document.xml'):
                if name not in z.namelist():
                    raise ValueError('Bagian wajib DOCX tidak ditemukan: ' + name)
            for entry in entries:
                if entry.filename.endswith(('.xml', '.rels')):
                    data = z.read(entry.filename)
                    if b'<!DOCTYPE' in data or b'<!ENTITY' in data:
                        raise ValueError('Deklarasi entitas XML tidak didukung.')
                    ET.fromstring(data)
            doc = ET.fromstring(z.read('word/document.xml'))
            texts = list(doc.iter(W + 't'))
            if not any((t.text or '').strip() for t in texts):
                raise ValueError('DOCX tidak memiliki isi teks.')
            refs = {r.get(W + 'id') for r in doc.iter(W + 'footnoteReference')}
            if refs:
                notes = ET.fromstring(z.read('word/footnotes.xml'))
                ids = {n.get(W + 'id') for n in notes.iter(W + 'footnote')}
                if not refs.issubset(ids):
                    raise ValueError('Ada referensi footnote tanpa catatan yang sesuai.')
            return {'paragraphs': len(list(doc.iter(W + 'p'))), 'footnotes_referenced': len(refs)}
    except (zipfile.BadZipFile, KeyError, ET.ParseError, RuntimeError) as exc:
        raise ValueError('Struktur DOCX tidak dapat dibaca.') from exc


def check_pdf(path: Path) -> None:
    data = path.read_bytes()
    if not data.startswith(b'%PDF-') or b'%%EOF' not in data[-1024:] or b'startxref' not in data[-2048:]:
        raise ValueError('PDF tidak memiliki penanda struktur yang lengkap.')


def inspect_artifacts(artifacts: ArtifactSet, output_dir: Path, root: Path) -> dict:
    files = {}
    for key in ('docx', 'final_pdf', 'preview_pdf'):
        path = Path(getattr(artifacts, key))
        file_info(path, output_dir)  # Wajib berasal dari percobaan ini, bukan pesanan lain.
        files[key] = file_info(path, root)
        if key.endswith('pdf'):
            check_pdf(path)
    if len({v['path'] for v in files.values()}) != 3:
        raise ValueError('File Word, PDF final, dan pratinjau harus terpisah.')
    if files['preview_pdf']['sha256'] == files['final_pdf']['sha256']:
        raise ValueError('Pratinjau identik dengan PDF final. Periksa pembuat watermark.')
    checks = check_docx(Path(artifacts.docx))
    return {'version': 1, 'files': files, 'checks': checks,
            'limits': 'Pemeriksaan struktur dasar dan hash; isi, layout, sumber, dan watermark perlu review.'}


def verify_manifest(manifest: dict, root: Path, *, released_dir: Path | None = None) -> None:
    for key, expected in manifest['files'].items():
        if released_dir is not None:
            if key == 'preview_pdf':
                continue
            path = released_dir / ('hasil.docx' if key == 'docx' else 'hasil.pdf')
        else:
            path = root / expected['path']
        actual = file_info(path, root)
        if any(actual[k] != expected[k] for k in ('size', 'sha256')):
            raise ValueError('File berubah setelah diperiksa: ' + key + '. Tahan penyerahan dan periksa ulang.')
