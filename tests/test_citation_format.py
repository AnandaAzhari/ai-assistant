import unittest

from app.citation_engine import CitationEngine
from app.document_policy import load_document_format_policy
from app.source_registry import RegisteredSource


class CitationFormatTests(unittest.TestCase):
    @staticmethod
    def _source() -> RegisteredSource:
        return RegisteredSource(
            ref_id="R1",
            provider="test",
            title="Pengembangan Perangkat Pembelajaran Konsep Pencemaran Lingkungan Menggunakan Model Pembelajaran Berdasarkan Masalah untuk SMA Kelas X",
            authors=("Agustina Fatmawati",),
            year=2016,
            venue="Edusains: Jurnal Pendidikan Sains dan Matematika",
            doi="10.23971/eds.v4i2.512",
            url="",
            work_type="journal-article",
            is_open_access=True,
            created="2026-09-17T00:00:00",
            volume="4",
            issue="2",
            pages="94-103",
        )

    def test_first_note_is_complete(self):
        note = CitationEngine.footnote_full(self._source())
        self.assertIn("Agustina Fatmawati", note)
        self.assertIn("Pengembangan Perangkat Pembelajaran Konsep Pencemaran Lingkungan", note)
        self.assertIn("Edusains: Jurnal Pendidikan Sains dan Matematika", note)
        self.assertIn("https://doi.org/10.23971/eds.v4i2.512", note)

    def test_nonconsecutive_repeat_note_is_short_without_ellipsis(self):
        full = CitationEngine.footnote_full(self._source())
        short = CitationEngine.footnote_short(self._source())
        self.assertTrue(short.startswith("Fatmawati,"))
        self.assertLess(len(short), len(full))
        self.assertNotIn("...", short)
        self.assertNotIn("…", short)

    def test_ibid_is_only_for_immediate_same_source_repeat(self):
        plan = CitationEngine.note_plan(["R1", "R1", "R2", "R1", "R2", "R2"])
        self.assertEqual(
            plan,
            (
                ("R1", "full"),
                ("R1", "ibid"),
                ("R2", "full"),
                ("R1", "short"),
                ("R2", "short"),
                ("R2", "ibid"),
            ),
        )
        self.assertEqual(CitationEngine.IBID_TEXT, "Ibid.")

    def test_default_footnote_visual_settings(self):
        self.assertEqual(CitationEngine.FOOTNOTE_FONT, "Times New Roman")
        self.assertEqual(CitationEngine.FOOTNOTE_SIZE, 10)

    def test_citation_skill_is_loaded_into_active_policy(self):
        policy = load_document_format_policy()
        self.assertIn("Citation Style Skill", policy)
        self.assertIn("full note", policy)
        self.assertIn("short note", policy)
        self.assertIn("Ibid.", policy)
        self.assertIn("nama jurnal dicetak miring", policy)
        self.assertIn("Times New Roman 10 pt", policy)
        self.assertIn("tidak memakai `...` atau `…`", policy)


if __name__ == "__main__":
    unittest.main()
