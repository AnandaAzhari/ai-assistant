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

    def test_policy_and_draft_prompt_use_same_default(self):
        policy = load_document_format_policy()
        self.assertIn("BAB I", policy)
        self.assertIn("A.", policy)
        self.assertIn("1.", policy)
        self.assertIn("a.", policy)
        self.assertIn("DAFTAR PUSTAKA", policy)
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
        self.assertIn("BAB I", xml)
        self.assertIn("PENDAHULUAN", xml)
        self.assertIn("DAFTAR PUSTAKA", xml)

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
