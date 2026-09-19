import unittest

from app.topic_guard import is_off_topic, is_verbatim_quote


class IsOffTopicTests(unittest.TestCase):
    def test_detects_generic_personal_topic_keyword(self):
        self.assertTrue(is_off_topic("aku lagi galau banget abis putus sama pacar"))

    def test_detects_other_business_mention(self):
        self.assertTrue(is_off_topic("kalau print foto buat photobooth bisa gak di sini?"))
        self.assertTrue(is_off_topic("boleh tanya soal Risol Mamqi dong"))
        self.assertTrue(is_off_topic("ada servis komputer juga gak?"))

    def test_is_case_insensitive(self):
        self.assertTrue(is_off_topic("LAGI GALAU NIH ABIS PUTUS SAMA PACAR"))

    def test_legitimate_business_message_is_not_off_topic(self):
        self.assertFalse(is_off_topic("Kak, mau minta tolong dibuatkan makalah tentang fotosintesis"))
        self.assertFalse(is_off_topic("Boleh minta tolong di-print dan dijilid juga filenya?"))

    def test_empty_or_none_is_not_off_topic(self):
        self.assertFalse(is_off_topic(""))
        self.assertFalse(is_off_topic(None))

    def test_document_keyword_does_not_false_positive_on_print(self):
        # Taqi Desk sendiri juga melayani print/jilid — kata "print"/"cetak" saja
        # sengaja TIDAK ada di OTHER_BUSINESS_KEYWORDS supaya tidak salah tertahan.
        self.assertFalse(is_off_topic("mau cetak dan jilid laporan PKL"))


class IsVerbatimQuoteTests(unittest.TestCase):
    def test_exact_substring_is_valid(self):
        self.assertTrue(is_verbatim_quote("nama saya Rani", "Halo, nama saya Rani dari kelas 8"))

    def test_whitespace_and_case_are_normalized(self):
        self.assertTrue(is_verbatim_quote("NAMA   SAYA rani", "halo nama saya Rani dari kelas 8"))

    def test_paraphrase_is_rejected(self):
        self.assertFalse(is_verbatim_quote("dia bernama Rani", "Halo, nama saya Rani dari kelas 8"))

    def test_non_string_quote_is_rejected(self):
        self.assertFalse(is_verbatim_quote(None, "Halo, nama saya Rani"))
        self.assertFalse(is_verbatim_quote(123, "Halo, nama saya Rani"))

    def test_empty_quote_is_rejected(self):
        self.assertFalse(is_verbatim_quote("", "Halo, nama saya Rani"))
        self.assertFalse(is_verbatim_quote("   ", "Halo, nama saya Rani"))

    def test_empty_source_text_is_rejected(self):
        self.assertFalse(is_verbatim_quote("nama saya Rani", ""))
        self.assertFalse(is_verbatim_quote("nama saya Rani", None))


if __name__ == "__main__":
    unittest.main()
