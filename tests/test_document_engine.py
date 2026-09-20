import os
import shutil
import threading
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from app.document_engine import DocumentEngine, DocumentSection, MakalahSpec

_LIBREOFFICE_AVAILABLE = shutil.which("soffice") is not None or shutil.which("libreoffice") is not None


def _simple_spec(order_id: str, title: str = "Uji Konversi PDF") -> MakalahSpec:
    return MakalahSpec(
        order_id=order_id,
        title=title,
        institution="MAN Contoh",
        class_semester="XI",
        subject="Biologi",
        sections=(DocumentSection("BAB I PENDAHULUAN", ("Paragraf uji.",), 1),),
    )


def test_document_engine_builds_docx_without_ai(tmp_path: Path):
    engine = DocumentEngine(tmp_path / "documents")
    spec = MakalahSpec(
        order_id="TEST-001",
        title="Uji Makalah",
        institution="MAN Contoh",
        class_semester="XI",
        subject="Biologi",
        sections=(
            DocumentSection("BAB I PENDAHULUAN", ("Paragraf uji.",), 1),
            DocumentSection("1.1 Latar Belakang", ("Isi latar belakang.",), 2),
        ),
    )

    result = engine.build(spec, create_pdf=False)

    assert result.status == "berhasil"
    docx = Path(result.docx_path)
    assert docx.is_file()
    assert docx.suffix == ".docx"

    with zipfile.ZipFile(docx) as package:
        names = set(package.namelist())
        assert "word/document.xml" in names
        assert "word/styles.xml" in names
        xml = package.read("word/document.xml").decode("utf-8")
        assert "UJI MAKALAH" in xml
        assert "BAB I PENDAHULUAN" in xml
        assert "MAN CONTOH" in xml


@pytest.mark.skipif(not _LIBREOFFICE_AVAILABLE, reason="LibreOffice tidak terpasang di lingkungan ini")
@pytest.mark.skipif(os.name == "nt", reason="Di Windows convert_to_pdf memakai Word COM, bukan LibreOffice")
def test_convert_to_pdf_uses_libreoffice_on_non_windows(tmp_path: Path):
    """Fondasi untuk `docs/roadmap_customer_channel_v1.md`: dokumen yang dibuat di VPS
    Linux (WhatsApp/Telegram produksi) tetap menghasilkan PDF, bukan cuma DOCX —
    sebelumnya `convert_to_pdf` langsung menyerah di non-Windows."""
    engine = DocumentEngine(tmp_path / "documents")
    result = engine.build(_simple_spec("PDF-001"), create_pdf=True)

    assert result.status == "berhasil"
    assert Path(result.docx_path).is_file()
    assert result.pdf_path, f"PDF gagal dibuat: {result.warning}"
    pdf_path = Path(result.pdf_path)
    assert pdf_path.is_file()
    assert pdf_path.stat().st_size > 0
    assert pdf_path.read_bytes().startswith(b"%PDF")


@pytest.mark.skipif(not _LIBREOFFICE_AVAILABLE, reason="LibreOffice tidak terpasang di lingkungan ini")
@pytest.mark.skipif(os.name == "nt", reason="Di Windows convert_to_pdf memakai Word COM, bukan LibreOffice")
def test_convert_to_pdf_concurrent_requests_do_not_crash(tmp_path: Path):
    """Simulasi beberapa pelanggan WhatsApp minta makalah nyaris bersamaan
    (`whatsapp_main.py` memakai `ThreadingHTTPServer`) — tanpa folder profil
    LibreOffice terpisah per konversi, ini bisa crash ("Fatal exception: Signal 6")."""
    engine = DocumentEngine(tmp_path / "documents")
    results: dict[int, object] = {}
    errors: dict[int, Exception] = {}

    def worker(i: int) -> None:
        try:
            results[i] = engine.build(_simple_spec(f"CONC-{i}", title=f"Uji Konkuren {i}"), create_pdf=True)
        except Exception as exc:  # pragma: no cover - kegagalan dilaporkan lewat assert di bawah
            errors[i] = exc

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors, errors
    assert len(results) == 3
    for result in results.values():
        assert result.status == "berhasil"
        assert result.pdf_path
        assert Path(result.pdf_path).is_file()


def test_convert_to_pdf_reports_clear_message_when_libreoffice_missing(tmp_path: Path):
    """Di Linux tanpa LibreOffice terpasang: DOCX tetap terkirim, PDF kosong dengan
    pesan yang menyebut cara instalasinya (bukan cuma "gagal") — lihat
    `DocumentEngine._convert_to_pdf_libreoffice`."""
    engine = DocumentEngine(tmp_path / "documents")
    with patch("app.document_engine.os.name", "posix"), patch("shutil.which", return_value=None):
        result = engine.build(_simple_spec("NOLIBRE-001"), create_pdf=True)

    assert result.status == "berhasil"
    assert Path(result.docx_path).is_file()
    assert result.pdf_path == ""
    assert "LibreOffice" in result.warning
    assert "install" in result.warning.casefold()
