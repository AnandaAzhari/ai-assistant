import unittest

from app.document_requirements import MakalahRequirements


class MakalahRequirementsTests(unittest.TestCase):
    def test_typo_tentan_still_extracts_topic(self):
        req = MakalahRequirements()
        req.update("saya ingin membuat makalah tentan AI agen")
        self.assertEqual(req.topic_title, "AI agen")

    def test_customer_sentence_extracts_class_semester_and_length(self):
        req = MakalahRequirements(topic_title="AI agen")
        req.update("SMK, XII semester 2, mata pelajaran Informatika, judul makalah belum, jumlah 8 halaman")
        self.assertEqual(req.institution_level, "SMK")
        self.assertEqual(req.class_semester, "Kelas XII, Semester 2")
        self.assertEqual(req.subject, "Informatika")
        self.assertEqual(req.topic_title, "AI agen")
        self.assertEqual(req.target_length, "8 halaman")
        self.assertTrue(req.complete)

    def test_judul_belum_is_not_saved_as_title(self):
        req = MakalahRequirements()
        req.update("SMK, kelas XII, Informatika, judul belum, 8 halaman")
        self.assertEqual(req.topic_title, "")
        self.assertIn("topic_title", req.missing_fields())


if __name__ == "__main__":
    unittest.main()
