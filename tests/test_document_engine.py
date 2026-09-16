import zipfile
from pathlib import Path

from app.document_engine import DocumentEngine, DocumentSection, MakalahSpec


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
