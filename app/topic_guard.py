"""Guardrail lintas-agent: validator kutipan-bukti + topic restriction.

Sebelum modul ini ada, dua guardrail penting hidup terpisah-pisah di tiap agent:

1. Validator kutipan-bukti ("evidence-quote"): `app/customer_intent.py` dan
   `app/document_intake.py` masing-masing menuliskan sendiri fungsi `_is_quote` yang
   nyaris identik — AI hanya boleh mengusulkan nilai/aksi dari pesan pengguna kalau AI
   itu sendiri menyertakan kutipan kata-demi-kata dari pesan tersebut sebagai bukti,
   dan Python memvalidasi kutipan itu benar-benar ada di teks asli sebelum nilainya
   dipakai. Duplikasi ini berisiko drift (dua implementasi yang harusnya identik bisa
   diam-diam berbeda kalau salah satu diubah tanpa yang lain).
2. Topic restriction: hanya ada di `app/lead.py` (`LeadAgent._OFF_TOPIC_WORDS`), dipakai
   Taqi untuk pesan PERTAMA pelanggan. `app/document_agent.py` (Nara) tidak punya
   guardrail kode untuk pertanyaan di luar topik yang muncul DI TENGAH sesi dokumen yang
   sudah berjalan (lihat `eval/scenarios/nara.md` Skenario 7) — sebelumnya hanya
   mengandalkan instruksi persona AI di `agents/document_agent.md`, tanpa validasi
   deterministik yang bisa gagal dengan aman.

Modul ini menyatukan keduanya jadi SATU tempat yang dipakai lintas agent, konsisten
dengan pola AI-first + validasi deterministik yang dipakai di seluruh proyek: AI boleh
mengusulkan, tapi kode Python yang punya kata putus akhir. Lihat
`docs/roadmap_customer_channel_v1.md` bagian "Guardrail Tambahan" dan
`policies/security_policy.md` untuk kebijakan lengkapnya.
"""

from __future__ import annotations

import re

# Topik pribadi/sosial yang jelas tidak berkaitan dengan layanan usaha apa pun di sini.
# Sengaja pendek dan konservatif: daftar yang longgar berisiko salah menahan pesan
# pelanggan yang sebenarnya masih terkait bisnis. Nuansa bahasa yang lebih halus tetap
# ditangani lapisan AI-first masing-masing agent (prompt-nya sendiri) di ATAS guardrail
# deterministik ini, bukan menggantikannya.
OFF_TOPIC_KEYWORDS: tuple[str, ...] = (
    "curhat", "galau", "putus sama pacar", "putus cinta", "masalah pribadi",
    "cerita pribadi", "gosip artis", "ramalan zodiak", "horoskop",
)

# Sinyal bahwa pesan sebenarnya soal usaha LAIN milik owner yang sama (mis. pelanggan
# Taqi Desk bertanya soal Pixiva.ID), bukan usaha yang sedang dilayani agent ini.
# Perbarui daftar ini saat ada usaha baru terdaftar di `brand_profiles/`. Sengaja pakai
# frasa (bukan kata tunggal pendek seperti "foto"/"servis" saja) supaya tidak salah
# cocok dengan kebutuhan bisnis yang sah (mis. Taqi Desk sendiri juga melayani
# print/jilid, jadi kata "print"/"cetak" saja TIDAK dimasukkan di sini).
OTHER_BUSINESS_KEYWORDS: tuple[str, ...] = (
    "photobooth", "photo booth", "pixiva",
    "risol mamqi",
    "servis komputer", "servis laptop", "servis pc",
    "perbaikan komputer", "perbaikan laptop",
)


def is_off_topic(text: str) -> bool:
    """True kalau `text` mengandung sinyal topik pribadi/sosial di luar layanan, atau
    menyebut usaha lain milik owner yang sama.

    Ini adalah lapis fail-safe deterministik (konservatif by design, lihat docstring
    modul) — dipakai sebagai backstop yang selalu bisa dievaluasi tanpa AI, bukan
    pengganti penilaian AI yang lebih bernuansa."""
    lowered = (text or "").casefold()
    return any(word in lowered for word in OFF_TOPIC_KEYWORDS) or any(
        word in lowered for word in OTHER_BUSINESS_KEYWORDS
    )


def is_verbatim_quote(quote: object, source_text: str) -> bool:
    """True kalau `quote` adalah kutipan kata-demi-kata (whitespace/kapitalisasi
    diabaikan) dari `source_text`.

    Dipakai untuk memvalidasi kutipan-bukti yang WAJIB disertakan AI saat mengusulkan
    nilai/aksi dari pesan pengguna (lihat docstring modul) — mencegah AI mengarang data
    tanpa dasar teks asli yang benar-benar dikirim pengguna."""
    def normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip().casefold()
    return (
        isinstance(quote, str)
        and bool(normalize(quote))
        and normalize(quote) in normalize(source_text or "")
    )
