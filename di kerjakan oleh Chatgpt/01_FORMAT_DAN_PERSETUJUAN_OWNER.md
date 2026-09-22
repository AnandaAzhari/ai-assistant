# Format dan persetujuan owner

Pada kelanjutan percakapan setelah perbaikan format, owner menyampaikan:

> hasilnya sudah sesuai

Konfirmasi ini merujuk hasil contoh Word/PDF setelah perbaikan pada commit
`70771143c0ce8f6b9213a648f50c495e5559307b`. Ini adalah penerimaan tampilan oleh
owner, bukan log pengujian Windows otomatis atau sertifikasi semua fitur produksi.
Kode di commit itu telah melewati 94 tes prototipe; hasil tes ulang tersedia di
`bukti_uji/hasil_unit_test.json`.

## Acuan yang harus dipertahankan

| Bagian | Format default |
| --- | --- |
| Kertas | A4 |
| Teks utama | Times New Roman 12 pt, spasi 1,5, rata kiri-kanan |
| Margin | Kiri 4 cm; atas, kanan, bawah 3 cm |
| Susunan | Sampul, kata pengantar, daftar isi, BAB I–III, daftar pustaka |
| BAB | BAB I pada baris sendiri, judul pada baris berikutnya, tengah dan tebal |
| Hierarki | BAB I → A. → 1. → a.; style Heading 1–4 |
| Indentasi heading | H2: 0 cm; H3: sekitar 0,63 cm; H4: sekitar 1,27 cm |
| Paragraf H2/H3 | Left indent 0 cm, first line sekitar 1,27 cm |
| Paragraf H4 | Left indent sekitar 0,63 cm, first line tambahan sekitar 0,63 cm |
| Pergantian bagian | Setiap BAB dan daftar pustaka mulai halaman baru |
| Nomor halaman | Sampul tanpa nomor; awal i, ii, ...; BAB I mulai 1 lalu berlanjut |
| Daftar isi | Field Word, sampai Heading 3, nomor sesuai hasil akhir |
| Footnote | Native Word, nomor superscript, TNR 10 pt, rata kiri, spasi tunggal |
| Daftar pustaka | Alfabetis, rata kiri, hanging indent sekitar 1,27 cm, spasi tunggal |
| PDF | Dikonversi dari DOCX yang sama; pratinjau adalah salinan PDF ber-watermark |

Pedoman/template resmi pelanggan mempunyai prioritas pada bagian yang diatur
khusus. Salinan empat acuan lengkap tersedia dalam `referensi/`, beserta asal dan
hash-nya. Gunakan engine proyek untuk menghasilkan format secara konsisten.

## Arti persetujuan ini

- Format contoh diterima; jangan kembali ke fixture Calibri/penomoran 1.1 untuk makalah.
- Contoh tujuh halaman pada pemeriksaan Linux digunakan untuk uji format dan alur.
  Jumlah itu bukan standar panjang setiap pesanan dan bukan makalah hasil riset AI.
- Isi serta catatan kaki pada contoh adalah data pengujian internal. Untuk pelanggan,
  isi, sumber, sitasi, dan jumlah halaman harus mengikuti brief serta verifikasi Nara.
- Harga dalam `config_harga.json` tetap usulan. Persetujuan tampilan tidak mengesahkan
  tarif, pilihan provider AI, atau aktivasi pembayaran/pengiriman sungguhan.
- Target halaman dokumen dan unit harga harus dibedakan: policy mengartikan permintaan
  “8 halaman” sebagai halaman setelah sampul, sedangkan “8 halaman isi” hanya isi.
  Paket harga prototipe memakai unit halaman isi. Jangan meneruskan angka brief ke
  kalkulator harga tanpa memperjelas cakupan penawaran.

## Batas format saat integrasi

`ProjectFormatWorker` memuat `app/document_engine.py` asli secara terpisah, kemudian
menambahkan satu catatan uji dan daftar pustaka internal. Ia bukan generator isi AI
atau pengganti penuh `CitationEngine`. Gunakan alur sitasi asli untuk sumber nyata.
Field daftar isi harus diperbarui setelah footnote dan bibliografi final selesai.
Pratinjau yang disetujui harus berasal dari versi DOCX/PDF final yang sama; perubahan
file setelah review harus menghasilkan pemeriksaan/persetujuan ulang.
