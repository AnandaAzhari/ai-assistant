# Citation Style Skill — Footnote + Daftar Pustaka

Skill ini adalah referensi aktif untuk Document Agent ketika membuat sitasi akademik pada Makalah dan dokumen lain yang memakai catatan kaki.

## Prioritas

1. Pedoman resmi guru, dosen, sekolah, program studi, fakultas, atau kampus.
2. Gaya sitasi yang diminta pelanggan secara jelas.
3. Default Taqi AI pada skill ini.

Jika institusi meminta APA, IEEE, Harvard, Chicago, Vancouver, atau format kampus tertentu, ikuti pedoman tersebut. Default di bawah hanya dipakai bila tidak ada arahan lain.

## Default Taqi AI

Default sitasi Makalah memakai pola **Chicago Notes & Bibliography** secara praktis:

- Sitasi di isi menggunakan nomor superscript Word asli.
- Kemunculan pertama sebuah sumber menggunakan **full note / catatan kaki lengkap**.
- Jika catatan kaki berikutnya secara langsung merujuk **sumber yang sama dengan catatan tepat sebelumnya**, gunakan **`Ibid.`**.
- Jika sumber yang sama dipakai lagi tetapi telah diselingi sumber lain, gunakan **short note**, bukan `Ibid.`.
- Short note memakai nama belakang penulis pertama + judul singkat yang masih dapat mengenali sumber.
- Short note **tidak memakai `...` atau `…` sebagai tanda potongan buatan engine**.
- Pada full note artikel jurnal, **nama jurnal dicetak miring**; judul artikel tetap berada dalam tanda kutip dan tidak dicetak miring.
- Jika sumber memiliki DOI, gunakan URL DOI `https://doi.org/...`; jika tidak ada DOI, gunakan URL sumber bila tersedia.
- Jangan membuat sumber, DOI, halaman, nama jurnal, atau metadata yang tidak ada pada Source Registry.

## Tampilan footnote Word

Jika tidak ada pedoman resmi yang menentukan lain:

- Font: **Times New Roman 10 pt**.
- Alignment: **Left / rata kiri**.
- Line spacing: **single / 1,0**.
- Space Before: **0 pt**.
- Space After: **0 pt**.
- Nomor footnote: superscript native Microsoft Word.
- Footnote berada di bagian bawah halaman sesuai perilaku native Word.
- Jangan mengubah nomor footnote menjadi angka yang diketik manual.

## Full note, Ibid., dan short note

Contoh pola:

Kemunculan pertama:

`Agustina Fatmawati, “Judul Artikel Lengkap,” *Nama Jurnal* 4, no. 2 (2016): 94–103, https://doi.org/... .`

Catatan tepat berikutnya masih sumber yang sama:

`Ibid.`

Sumber yang sama dipakai lagi setelah diselingi sumber lain:

`Fatmawati, “Judul Artikel Singkat.”`

`Ibid.` tidak boleh dipakai bila catatan kaki tepat sebelumnya berasal dari sumber berbeda karena akan membuat rujukan menjadi ambigu atau salah.

Jika kelak sistem memiliki locator spesifik per kutipan, seperti halaman 98, locator tersebut dapat ditambahkan pada `Ibid.` atau short note sesuai kebutuhan. Jangan memakai rentang halaman artikel sebagai locator kutipan spesifik jika sistem tidak mengetahui halaman kutipan yang sebenarnya.

## Daftar Pustaka

- Hanya sumber yang benar-benar digunakan yang masuk Daftar Pustaka.
- Urutkan secara alfabetis berdasarkan nama belakang penulis pertama.
- Nama penulis pertama dibalik untuk kebutuhan bibliografi.
- Gunakan hanging indent sekitar 1,25–1,27 cm.
- Gunakan spasi tunggal pada setiap entri dan jarak antar-entri yang rapi.
- Nama jurnal atau judul karya utama dicetak miring sesuai jenis sumber.
- DOI/URL dicantumkan bila tersedia.
- Daftar Pustaka tidak diberi nomor atau bullet kecuali pedoman resmi meminta demikian.

## Aturan stabilitas

Citation Engine harus bersifat deterministik. AI boleh membantu memilih sumber dan menulis isi, tetapi format full note, `Ibid.`, short note, italic nama jurnal, footnote Word, dan Daftar Pustaka ditangani engine agar konsisten.