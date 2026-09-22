"""Pratinjau berupa salinan PDF hasil Word dengan watermark di setiap halaman."""
from __future__ import annotations

from pathlib import Path

STAMP_TEXT = 'PRATINJAU - SIMULASI'


def require_pypdf():
    try:
        import pypdf
    except ImportError as exc:
        raise ValueError('Paket pypdf belum tersedia. Jalankan SIAPKAN_FORMAT.bat sekali, '
                         'lalu buka JALANKAN_CONTOH_ANTREAN.bat.') from exc
    return pypdf


def make_preview(source: Path, destination: Path) -> None:
    pypdf = require_pypdf()
    from pypdf.generic import DictionaryObject, NameObject, FloatObject, DecodedStreamObject
    if source.resolve() == destination.resolve():
        raise ValueError('Pratinjau harus terpisah dari PDF final.')
    try:
        writer = pypdf.PdfWriter(clone_from=str(source))
        if not writer.pages:
            raise ValueError('PDF final tidak mempunyai halaman.')
        for page in writer.pages:
            if page.rotation:
                page.transfer_rotation_to_content()
            width, height = float(page.mediabox.width), float(page.mediabox.height)
            stamp = pypdf.PageObject.create_blank_page(width=width, height=height)
            font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                                     NameObject('/Subtype'): NameObject('/Type1'),
                                     NameObject('/BaseFont'): NameObject('/Helvetica')})
            state = DictionaryObject({NameObject('/Type'): NameObject('/ExtGState'),
                                      NameObject('/ca'): FloatObject(0.20)})
            stamp[NameObject('/Resources')] = DictionaryObject({
                NameObject('/Font'): DictionaryObject({NameObject('/Fwm'): font}),
                NameObject('/ExtGState'): DictionaryObject({NameObject('/GS'): state}),
            })
            stream = DecodedStreamObject()
            size = min(38, width / 16)
            stream.set_data((f'q /GS gs 0.45 g BT /Fwm {size:.3f} Tf '
                             f'0.707 0.707 -0.707 0.707 {width * .18:.3f} {height * .30:.3f} Tm '
                             f'({STAMP_TEXT}) Tj ET Q').encode('ascii'))
            stamp[NameObject('/Contents')] = stream
            page.merge_page(stamp, over=True)
        writer.write(str(destination))
        writer.close()
    except Exception as exc:
        raise ValueError('PDF pratinjau gagal dibuat: ' + str(exc)[:250]) from exc
