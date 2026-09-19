import tempfile
import unittest
from pathlib import Path

from app.brand_profile import BrandProfileStore


class BrandProfileStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = BrandProfileStore(self.root)

    def _write(self, filename: str, content: str) -> None:
        (self.root / filename).write_text(content, encoding="utf-8")

    def test_slug_normalizes_business_name(self):
        self.assertEqual(BrandProfileStore.slug("Pixiva.ID"), "pixiva_id")
        self.assertEqual(BrandProfileStore.slug("Risol Mamqi"), "risol_mamqi")
        self.assertEqual(BrandProfileStore.slug("  Taqi   DocuTech  "), "taqi_docutech")

    def test_load_returns_none_when_file_missing(self):
        self.assertIsNone(self.store.load("Usaha Belum Ada"))

    def test_load_parses_sections(self):
        self._write("risol_mamqi.md", """# Brand Profile: Risol Mamqi

## Usaha
Risol Mamqi

## Deskripsi Singkat
Usaha kuliner rumahan.

## Tone of Voice
Ceria dan menggugah selera.

## Target Audiens
Warga sekitar dan pelanggan online.

## Larangan Tema/Kata
- Tidak mengklaim manfaat kesehatan.
- Tidak membahas isu SARA/politik.

## Contoh Caption Favorit
- Risol anget nih!
- Ngemil sore makin seru.

## Status
- Draft/Final: Draft
""")
        profile = self.store.load("Risol Mamqi")
        self.assertIsNotNone(profile)
        self.assertEqual(profile.business, "Risol Mamqi")
        self.assertEqual(profile.description, "Usaha kuliner rumahan.")
        self.assertEqual(profile.tone_of_voice, "Ceria dan menggugah selera.")
        self.assertEqual(profile.target_audience, "Warga sekitar dan pelanggan online.")
        self.assertIn("SARA/politik", profile.forbidden_themes)
        self.assertEqual(profile.example_captions, ("Risol anget nih!", "Ngemil sore makin seru."))

    def test_is_ready_false_when_tone_of_voice_missing(self):
        self._write("pixiva_id.md", """## Usaha
Pixiva.ID

## Larangan Tema/Kata
- Tidak posting tanpa izin.
""")
        self.assertFalse(self.store.is_ready("Pixiva.ID"))

    def test_is_ready_false_when_placeholder_still_present(self):
        self._write("pixiva_id.md", """## Usaha
Pixiva.ID

## Tone of Voice
[ISI: belum diisi]

## Larangan Tema/Kata
- Tidak posting tanpa izin.
""")
        self.assertFalse(self.store.is_ready("Pixiva.ID"))

    def test_is_ready_true_when_key_sections_filled(self):
        self._write("pixiva_id.md", """## Usaha
Pixiva.ID

## Tone of Voice
Kreatif dan fun.

## Larangan Tema/Kata
- Tidak posting tanpa izin.
""")
        self.assertTrue(self.store.is_ready("Pixiva.ID"))

    def test_is_ready_false_when_file_missing(self):
        self.assertFalse(self.store.is_ready("Usaha Tidak Ada"))

    def test_example_captions_skip_placeholder_lines(self):
        self._write("taqi_docutech.md", """## Usaha
Taqi DocuTech

## Contoh Caption Favorit
- [ISI: contoh caption yang owner suka, sementara kosong]
- Deadline mepet? Serahkan ke kami.
""")
        profile = self.store.load("Taqi DocuTech")
        self.assertEqual(profile.example_captions, ("Deadline mepet? Serahkan ke kami.",))

    def test_list_known_businesses_excludes_template(self):
        self._write("BRAND_PROFILE_TEMPLATE.md", "# Template\n\n## Usaha\n[Nama usaha]\n")
        self._write("risol_mamqi.md", "## Usaha\nRisol Mamqi\n")
        businesses = self.store.list_known_businesses()
        self.assertEqual(businesses, ("Risol Mamqi",))


if __name__ == "__main__":
    unittest.main()
