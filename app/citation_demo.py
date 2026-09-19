"""Demo lokal Footnote + Daftar Pustaka Engine tanpa token AI.

Jalankan dari root repo:
    python -m app.citation_demo

Untuk menguji tanpa Ibid. dari Git Bash:
    CITATION_REPEAT_MODE=short python -m app.citation_demo
"""

from __future__ import annotations

import os
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
        institution="Taqi Desk - Dokumen Uji",
        class_semester="XI",
        subject="Biologi",
        author="Contoh Siswa",
        teacher="Contoh Guru",
        year=str(datetime.now().year),
        preface=("Dokumen ini dibuat khusus untuk menguji footnote, daftar pustaka, struktur BAB, dan nomor halaman otomatis.",),
        sections=(
            DocumentSection("BAB I PENDAHULUAN", (), 1),
            DocumentSection(
                "A. Latar Belakang",
                (
                    "Pencemaran lingkungan perlu dipahami melalui pembelajaran yang menghubungkan konsep dengan masalah nyata.[[R1]]",
                    "Pencegahan pencemaran juga berkaitan dengan pengaturan dan penegakan hukum lingkungan.[[R2]]",
                    "Materi pencemaran dapat kembali digunakan untuk memperkuat pemahaman siswa terhadap masalah lingkungan.[[R1]]",
                ),
                2,
            ),
            DocumentSection("B. Rumusan Masalah", ("Bagaimana upaya pencegahan pencemaran lingkungan?",), 2),
            DocumentSection("C. Tujuan Penulisan", ("Menjelaskan pencemaran lingkungan dan upaya pencegahannya.",), 2),
            DocumentSection("BAB II PEMBAHASAN", (), 1),
            DocumentSection("A. Konsep Pencemaran", ("Pencemaran berkaitan dengan perubahan kualitas lingkungan.[[R1]]",), 2),
            DocumentSection("B. Upaya Pencegahan", (), 2),
            DocumentSection("1. Melalui Pendidikan", ("Pendidikan dapat membantu meningkatkan pemahaman tentang pencegahan pencemaran.[[R1]]",), 3),
            DocumentSection("2. Melalui Regulasi", ("Pengaturan dan penegakan hukum dapat membantu mencegah pencemaran lingkungan.[[R2]]",), 3),
            DocumentSection("a. Pencegahan", ("Pencegahan dilakukan sebelum pencemaran menimbulkan dampak yang lebih luas.[[R2]]",), 4),
            DocumentSection("b. Penegakan", ("Penegakan aturan diperlukan ketika terjadi pelanggaran terhadap ketentuan lingkungan.[[R2]]",), 4),
            DocumentSection("BAB III PENUTUP", (), 1),
            DocumentSection("A. Kesimpulan", ("Pencegahan pencemaran memerlukan keterlibatan berbagai pihak.",), 2),
            DocumentSection("B. Saran", ("Upaya edukasi dan penegakan aturan perlu dilakukan secara konsisten.",), 2),
        ),
    )


def build_demo(
    engine: DocumentEngine | None = None,
    *,
    citation_repeat_mode: str | None = None,
) -> CitationBuildResult:
    document_engine = engine or DocumentEngine.from_env()
    citations = CitationEngine(document_engine)
    mode = citation_repeat_mode or os.environ.get("CITATION_REPEAT_MODE", "auto")
    return citations.build(
        demo_spec(),
        demo_sources(),
        create_pdf=True,
        citation_repeat_mode=mode,
    )


def main() -> None:
    mode = CitationEngine.normalize_repeat_mode(os.environ.get("CITATION_REPEAT_MODE", "auto"))
    result = build_demo(citation_repeat_mode=mode)
    print("Status:", result.status)
    print("Gaya sitasi: Chicago Notes & Bibliography")
    print("citation_repeat_mode:", mode)
    print("DOCX:", result.docx_path or "-")
    print("PDF:", result.pdf_path or "-")
    print("Sumber dipakai:", ", ".join(result.used_refs) or "-")
    if result.warning:
        print("Catatan:", result.warning)


if __name__ == "__main__":
    main()
