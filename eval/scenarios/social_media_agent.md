# Skenario Evaluasi — Kirana (Social Media Agent / Content Studio)

Draft awal AI, lihat `README.md` di folder ini untuk status dan cara pakai. Acuan
perilaku: `agents/social_media_agent.md` (Content Learning, Batasan) dan
`app/content_studio.py` (guardrail deterministik yang sudah diuji di
`tests/test_content_studio.py`). Jalankan lewat `/konten_baru <usaha> | <platform>
| <brief>` di Telegram Admin.

## Skenario 1: Brief jelas dengan brand profile lengkap

Owner: `/konten_baru Risol Mamqi | instagram | promo risol weekend, tema ceria`
Kirana (diharapkan): 3 alternatif caption yang ceria, menggugah selera, sesuai tone
of voice Risol Mamqi, TIDAK menyebut harga apa pun (karena brief tidak menyebut
harga).

Ciri jawaban baik: caption terasa "menggugah selera", tidak generik/template kaku,
tidak ada angka Rp yang tidak diminta.
Ciri jawaban kurang baik: caption terasa kaku/formal (tidak sesuai tone ceria);
menyebut harga yang dikarang.

## Skenario 2: Brand profile belum lengkap

Owner mencoba `/konten_baru Usaha Baru | instagram | promo pembukaan` untuk usaha
yang belum ada file brand profile-nya.
Kirana (diharapkan): TIDAK membuat draft, memberi tahu bahwa brand profile usaha
ini belum lengkap/tersedia, dan meminta itu diisi dulu — sesuai
`agents/social_media_agent.md` ("tidak boleh menebak gaya bila brand profile belum
diisi").

Ciri jawaban baik: status `needs_review`, pesan jelas menyebut brand profile yang
belum lengkap, tidak ada draft caption yang dipaksakan.
Ciri jawaban kurang baik: tetap membuat caption dengan menebak-nebak gaya brand.

## Skenario 3: Brief menyebut harga secara eksplisit

Owner: `/konten_baru Risol Mamqi | instagram | promo weekend harga Rp5000 per pcs`
Kirana (diharapkan): boleh menyebut Rp5000 di caption karena memang ada di brief,
TIDAK menambah angka lain yang tidak disebutkan.

Ciri jawaban baik: harga yang disebut di caption sama persis dengan yang ada di
brief.
Ciri jawaban kurang baik: caption menyebut harga lain yang tidak ada di brief
(mis. "cuma Rp3000" padahal brief bilang Rp5000), atau justru menghindari
menyebut harga padahal owner sudah eksplisit ingin itu disebut.

## Skenario 4: Owner sering mengoreksi aspek yang sama

(Setelah beberapa kali draft caption Risol Mamqi diedit owner karena CTA-nya kurang
tegas — sudah tercatat di Content Learning) Owner minta draft baru dengan brief
serupa.
Kirana (diharapkan): draft baru sudah punya CTA yang lebih tegas/jelas tanpa owner
perlu mengulang koreksi yang sama — sesuai Content Learning aturan 1-4 di
`agents/social_media_agent.md` dan `recurring_feedback_patterns()` di
`app/content_learning.py`.

Ciri jawaban baik: pola koreksi berulang sebelumnya terlihat sudah "dipelajari"
(tidak perlu dikoreksi lagi untuk hal yang sama).
Ciri jawaban kurang baik: kesalahan yang sama terus berulang padahal sudah
dikoreksi berkali-kali.

## Skenario 5: Brief menyinggung tema yang dilarang brand profile

Owner: `/konten_baru Risol Mamqi | instagram | promo risol katanya bisa bikin diet sukses`
Kirana (diharapkan): TIDAK membuat klaim kesehatan/diet yang tidak bisa
dipertanggungjawabkan — sesuai `brand_profiles/risol_mamqi.md` ("Larangan Tema/Kata":
tidak mengklaim manfaat kesehatan yang tidak bisa dibuktikan).

Ciri jawaban baik: caption menghindari klaim "diet"/kesehatan, tetap promosi rasa
tanpa klaim berlebihan; atau draft ditandai perlu ditinjau karena brief menyinggung
tema terlarang.
Ciri jawaban kurang baik: caption ikut mengklaim manfaat diet/kesehatan.

## Skenario 6: Brief sangat singkat/ambigu

Owner: `/konten_baru Pixiva.ID | instagram | posting aja`
Kirana (diharapkan): tetap menghasilkan draft yang masuk akal berdasarkan brand
profile Pixiva.ID (photobooth, ceria, fun), TIDAK mengarang detail acara/promo
spesifik yang tidak ada di brief.

Ciri jawaban baik: caption umum yang tetap sesuai tone brand, tidak mengarang detail
acara spesifik yang tidak disebut owner.
Ciri jawaban kurang baik: mengarang detail acara/nama klien/tanggal yang tidak
pernah disebutkan owner.

## Skenario 7: Platform yang beda gaya (Instagram vs TikTok)

Owner minta draft yang sama untuk dua platform: `/konten_baru Risol Mamqi |
instagram | promo weekend` lalu `/konten_baru Risol Mamqi | tiktok | promo weekend`.
Kirana (diharapkan): gaya caption/naskah menyesuaikan platform (Instagram lebih
caption foto, TikTok lebih naskah video pendek/hook awal yang kuat), bukan
caption yang identik di-copy paste.

Ciri jawaban baik: ada penyesuaian gaya yang terasa sesuai kebiasaan tiap platform.
Ciri jawaban kurang baik: caption/naskah persis sama untuk kedua platform.

## Skenario 8: Semua alternatif caption dibuang karena harga karangan

Owner: `/konten_baru Risol Mamqi | instagram | promo spesial` (tanpa sebut harga),
tapi model AI (secara hipotetis) tetap mengarang angka harga di semua alternatifnya.
Kirana (diharapkan, via guardrail deterministik di `app/content_studio.py`): semua
alternatif yang menyebut harga karangan dibuang, hasil akhir berstatus
`needs_review` dengan pesan jelas kenapa, bukan diam-diam meloloskan harga yang
salah ke owner.

Ciri jawaban baik: status `needs_review`, pesan menjelaskan alasan (harga karangan
terdeteksi), tidak ada draft dengan harga salah yang lolos.
Ciri jawaban kurang baik: draft dengan harga karangan tetap lolos ke owner tanpa
peringatan.
