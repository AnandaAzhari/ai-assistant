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

    def test_common_chat_abbreviations_are_understood(self):
        req = MakalahRequirements()
        req.update(
            "sy mau buat makalah ttg AI agent, sy anak SMK kls XII smstr 2, "
            "mapel Informatika, jml 8 hal"
        )
        self.assertEqual(req.institution_level, "SMK")
        self.assertEqual(req.class_semester, "Kelas XII, Semester 2")
        self.assertEqual(req.subject, "Informatika")
        self.assertEqual(req.topic_title, "AI agent")
        self.assertEqual(req.target_length, "8 halaman")
        self.assertTrue(req.complete)

    def test_shortcuts_keep_missing_title_missing(self):
        req = MakalahRequirements()
        req.update("SMK kls XII smstr 2, mapel Informatika, judul blm, jml 8 hal")
        self.assertEqual(req.institution_level, "SMK")
        self.assertEqual(req.class_semester, "Kelas XII, Semester 2")
        self.assertEqual(req.subject, "Informatika")
        self.assertEqual(req.topic_title, "")
        self.assertEqual(req.target_length, "8 halaman")
        self.assertIn("topic_title", req.missing_fields())

    def test_other_common_shortcuts_are_normalized(self):
        req = MakalahRequirements()
        req.update(
            "sya mau makalah tentang keamanan data, SMA kelas XI, mapel Informatika, "
            "target 10 hlm, tdk ada arahan khusus"
        )
        self.assertEqual(req.institution_level, "SMA")
        self.assertEqual(req.class_semester, "Kelas XI")
        self.assertEqual(req.subject, "Informatika")
        self.assertEqual(req.topic_title, "keamanan data")
        self.assertEqual(req.target_length, "10 halaman")
        self.assertEqual(req.teacher_instructions, "Tidak ada arahan khusus")


if __name__ == "__main__":
    unittest.main()
