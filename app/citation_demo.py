"""Demo lokal Footnote + Daftar Pustaka Engine tanpa token AI.

Jalankan dari root repo:
    python -m app.citation_demo
"""

from __future__ import annotations

from datetime import datetime

from app.citation_engine import CitationBuildResult, CitationEngine
from app.document_engine import DocumentEngine, DocumentSection, MakalahSpec
from app.source_registry import RegisteredSource


def demo_sources() -> list[RegisteredSource]:
    now = datetime.now().isoformat(timespec="seconds")
    return [
        RegisteredSource(
            ref_id="R1",
            provider="Crossref",
            title="Pengembangan Perangkat Pembelajaran Konsep Pencemaran Lingkungan Menggunakan Model Pembelajaran Berdasarkan Masalah untuk SMA Kelas X",
            authors=("Agustina Fatmawati",),
            year=2016,
            venue="Edu Sains: Jurnal Pendidikan Sains dan Matematika",
            doi="10.23971/eds.v4i2.512",
            url="https://doi.org/10.23971/eds.v4i2.512",
            work_type="journal-article",
            is_open_access=True,
            created=now,
            volume="4",
            issue="2",
            pages="94-103",
        ),
        RegisteredSource(
            ref_id="R2",
            provider="Crossref",
            title="Urgensi Hukum Perizinan dan Penegakannya sebagai Sarana Pencegahan Pencemaran Lingkungan Hidup",
            authors=("Sulistyani Eka Lestari", "Hardianto Djanggih"),
            year=2019,
            venue="Masalah-Masalah Hukum",
            doi="10.14710/mmh.48.2.2019.147-163",
            url="https://doi.org/10.14710/mmh.48.2.2019.147-163",
            work_type="journal-article",
            is_open_access=True,
            created=now,
            volume="48",
            issue="2",
            pages="147-163",
            publisher="Faculty of Law, Universitas Diponegoro",
        ),
    ]


def demo_spec() -> MakalahSpec:
    return MakalahSpec(
        order_id="DEMO-FOOTNOTE",
        title="Pencemaran Lingkungan",
        institution="Taqi DocuTech - Dokumen Uji",
        class_semester="XI",
        subject="Biologi",
        author="Contoh Siswa",
        teacher="Contoh Guru",
        year=str(datetime.now().year),
        preface=("Dokumen ini dibuat khusus untuk menguji footnote dan daftar pustaka otomatis.",),
        sections=(
            DocumentSection("BAB I PENDAHULUAN", (), 1),
            DocumentSection(
                "1.1 Latar Belakang",
                (
                    "Pencemaran lingkungan perlu dipahami melalui pembelajaran yang menghubungkan konsep dengan masalah nyata.[[R1]]",
                    "Pencegahan pencemaran juga berkaitan dengan pengaturan dan penegakan hukum lingkungan.[[R2]]",
                    "Materi pencemaran dapat kembali digunakan untuk memperkuat pemahaman siswa terhadap masalah lingkungan.[[R1]]",
                ),
                2,
            ),
            DocumentSection("BAB II PEMBAHASAN", (), 1),
            DocumentSection(
                "2.1 Upaya Pencegahan",
                ("Upaya pencegahan membutuhkan pendekatan pendidikan dan regulasi yang saling mendukung.[[R1]][[R2]]",),
                2,
            ),
            DocumentSection("BAB III PENUTUP", (), 1),
            DocumentSection("3.1 Kesimpulan", ("Pencegahan pencemaran memerlukan keterlibatan berbagai pihak.",), 2),
        ),
    )


def build_demo(engine: DocumentEngine | None = None) -> CitationBuildResult:
    document_engine = engine or DocumentEngine.from_env()
    citations = CitationEngine(document_engine)
    return citations.build(demo_spec(), demo_sources(), create_pdf=True)


def main() -> None:
    result = build_demo()
    print("Status:", result.status)
    print("Gaya sitasi: Chicago Notes & Bibliography")
    print("DOCX:", result.docx_path or "-")
    print("PDF:", result.pdf_path or "-")
    print("Sumber dipakai:", ", ".join(result.used_refs) or "-")
    if result.warning:
        print("Catatan:", result.warning)


if __name__ == "__main__":
    main()
