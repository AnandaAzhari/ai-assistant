import unittest

from app.citation_engine import CitationEngine
from app.document_draft import DRAFT_PROMPT
from app.document_engine import DocumentEngine, DocumentSection, MakalahSpec
from app.document_policy import load_document_format_policy


class MakalahStructureTests(unittest.TestCase):
    def test_heading_levels_follow_bab_a_1_a(self):
        self.assertEqual(DocumentEngine._infer_heading_level("BAB I PENDAHULUAN", 1), 1)
        self.assertEqual(DocumentEngine._infer_heading_level("BAB II PEMBAHASAN", 1), 1)
        self.assertEqual(DocumentEngine._infer_heading_level("A. Latar Belakang", 2), 2)
        self.assertEqual(DocumentEngine._infer_heading_level("B. Rumusan Masalah", 2), 2)
        self.assertEqual(DocumentEngine._infer_heading_level("C. Tujuan Penulisan", 2), 2)
        self.assertEqual(DocumentEngine._infer_heading_level("D. Manfaat Penulisan", 2), 2)
        self.assertEqual(DocumentEngine._infer_heading_level("1. Pokok Bahasan", 3), 3)
        self.assertEqual(DocumentEngine._infer_heading_level("a. Rincian", 4), 4)
        self.assertEqual(DocumentEngine._infer_heading_level("DAFTAR PUSTAKA", 1), 1)

    def test_default_heading_indents_follow_academic_fallback(self):
        self.assertEqual(DocumentEngine._heading_left(1), 0)
        self.assertEqual(DocumentEngine._heading_left(2), 0)
        self.assertEqual(DocumentEngine._heading_left(3), 360)
        self.assertEqual(DocumentEngine._heading_left(4), 720)

    def test_body_paragraph_indent_depends_on_heading_level(self):
        self.assertEqual(DocumentEngine._body_paragraph_indent(2), (0, 720))
        self.assertEqual(DocumentEngine._body_paragraph_indent(3), (0, 720))
        self.assertEqual(DocumentEngine._body_paragraph_indent(4), (360, 360))

    def test_body_paragraph_is_justify_with_word_indentation(self):
        standard = DocumentEngine._paragraph(
            "Isi paragraf uji.", align="both", left=0, first_line=720
        )
        level4 = DocumentEngine._paragraph(
            "Isi level empat.", align="both", left=360, first_line=360
        )
        self.assertIn('w:jc w:val="both"', standard)
        self.assertIn('w:left="0" w:firstLine="720"', standard)
        self.assertIn('w:jc w:val="both"', level4)
        self.assertIn('w:left="360" w:firstLine="360"', level4)

    def test_policy_and_skill_use_same_default(self):
        policy = load_document_format_policy()
        self.assertIn("BAB I", policy)
        self.assertIn("A.", policy)
        self.assertIn("1.", policy)
        self.assertIn("a.", policy)
        self.assertIn("DAFTAR PUSTAKA", policy)
        self.assertIn("Document Academic Skill", policy)
        self.assertIn("Heading 4", policy)
        self.assertIn("0,63 cm", policy)
        self.assertIn("Justify", policy)
        self.assertIn("BAB I -> A. -> 1. -> a.", DRAFT_PROMPT)

    def test_bibliography_is_not_numbered_as_an_extra_bab(self):
        spec = MakalahSpec(
            order_id="TEST",
            title="Uji",
            institution="Sekolah",
            class_semester="XII",
            subject="Informatika",
            sections=(
                DocumentSection("BAB I PENDAHULUAN", (), 1),
                DocumentSection("BAB II PEMBAHASAN", (), 1),
                DocumentSection("BAB III PENUTUP", (), 1),
            ),
        )
        self.assertEqual(CitationEngine._bibliography_title(spec), "DAFTAR PUSTAKA")

    def test_page_number_sections_are_native_docx(self):
        spec = MakalahSpec(
            order_id="TEST",
            title="Uji",
            institution="Sekolah",
            class_semester="XII",
            subject="Informatika",
            preface=("Kata pengantar uji.",),
            sections=(
                DocumentSection("BAB I PENDAHULUAN", (), 1),
                DocumentSection("A. Latar Belakang", ("Isi uji.",), 2),
                DocumentSection("BAB III PENUTUP", (), 1),
                DocumentSection("A. Kesimpulan", ("Kesimpulan uji.",), 2),
                DocumentSection("DAFTAR PUSTAKA", ("Contoh sumber.",), 1),
            ),
        )
        xml = DocumentEngine()._document_xml(spec)
        self.assertIn('w:fmt="lowerRoman" w:start="1"', xml)
        self.assertIn('w:fmt="decimal" w:start="1"', xml)
        self.assertIn('w:jc w:val="both"', xml)
        self.assertIn('w:firstLine="720"', xml)
        self.assertIn("BAB I", xml)
        self.assertIn("PENDAHULUAN", xml)
        self.assertIn("DAFTAR PUSTAKA", xml)

    def test_level4_paragraph_uses_selected_visual_indent(self):
        spec = MakalahSpec(
            order_id="TEST",
            title="Uji",
            institution="Sekolah",
            class_semester="XII",
            subject="Informatika",
            sections=(
                DocumentSection("BAB I PENDAHULUAN", (), 1),
                DocumentSection("A. Pembahasan", (), 2),
                DocumentSection("1. Rincian", (), 3),
                DocumentSection("a. Pencegahan", ("Isi level empat.",), 4),
            ),
        )
        xml = DocumentEngine()._document_xml(spec)
        self.assertIn('w:left="720"', xml)
        self.assertIn('w:left="360" w:firstLine="360"', xml)
        self.assertIn("Isi level empat.", xml)

    def test_each_heading1_after_first_starts_on_new_page(self):
        spec = MakalahSpec(
            order_id="TEST",
            title="Uji",
            institution="Sekolah",
            class_semester="XII",
            subject="Informatika",
            sections=(
                DocumentSection("BAB I PENDAHULUAN", (), 1),
                DocumentSection("A. Latar Belakang", ("Isi satu.",), 2),
                DocumentSection("BAB II PEMBAHASAN", (), 1),
                DocumentSection("A. Pembahasan", ("Isi dua.",), 2),
                DocumentSection("BAB III PENUTUP", (), 1),
                DocumentSection("A. Kesimpulan", ("Isi tiga.",), 2),
                DocumentSection("DAFTAR PUSTAKA", ("Contoh sumber.",), 1),
            ),
        )
        xml = DocumentEngine()._document_xml(spec)
        page_break = '<w:br w:type="page"/>'
        # BAB II, BAB III, dan DAFTAR PUSTAKA masing-masing harus mendapat page break.
        self.assertGreaterEqual(xml.count(page_break), 3)
        self.assertLess(xml.find("BAB I"), xml.find("BAB II"))
        self.assertLess(xml.find("BAB II"), xml.find("BAB III"))
        self.assertLess(xml.find("BAB III"), xml.find("DAFTAR PUSTAKA"))


if __name__ == "__main__":
    unittest.main()
