# Hasil pengujian prototipe

Tanggal: 22 September 2026.

- Lingkungan: Linux, Python 3.12.14.
- Acuan repository utama: `f49aff17e764c9bc32e5be493c5038cf52dfe307`.
- Lingkup: hanya folder `di kerjakan oleh Chatgpt`.
- Dependensi: Python standard library; tanpa instalasi paket tambahan.

## Hasil yang dijalankan

```text
python -B -m unittest discover -s tests -p 'test_*.py' -v
Ran 48 tests
OK
```

**48 tes lulus, 0 gagal.** Tes menggunakan database memori atau folder sementara.
Tidak memakai data owner, token Telegram, kunci Midtrans, atau layanan jaringan.

Contoh otomatis `python -B demo.py --sample` juga dijalankan dan berhasil:

```text
Makalah 10 halaman: Rp60.000
Bayar awal: Rp18.000
Mulai tanpa DP: ditolak
Notifikasi pending: Rp0 tercatat
DP sukses dikirim ulang: tetap Rp18.000
Sisa pelunasan: Rp42.000
Penyerahan final sebelum lunas: ditolak
Setelah lunas dan pratinjau disetujui: Selesai
```

## Cakupan

| Kelompok | Perilaku yang diperiksa |
| --- | --- |
| Harga | Batas paket, halaman tambahan, minimum perapian, bundle footnote, surcharge cepat, DP, pembulatan rupiah |
| Validasi | Input negatif/boolean/float, konfigurasi rusak, pilihan yang bertentangan, JSON ber-BOM dari editor Windows |
| Tahapan | Persetujuan harga, DP cukup, pratinjau, pelunasan, penyerahan final, revisi, koreksi gratis, pembatalan |
| Pembayaran | Pending/gagal/kedaluwarsa, retry, notifikasi terbalik, nominal/order berbeda, pembayaran berlebih |
| Persistensi | Restart, harga lama tetap, rollback transaksi, database asing tidak berubah |
| Konkurensi | Dua koneksi memproses transaksi sama: satu kredit dan satu sinyal kesiapan kerja |
| Telegram | Cek DP/sisa, konfirmasi manual, pesan simulasi Midtrans, owner/private-chat saja, perintah lain tetap diteruskan |
| Peluncuran Python | Demo otomatis dari direktori lain; simulasi chat Telegram di folder dengan spasi |

## Batas verifikasi

- File `.bat` disiapkan untuk Windows dengan path berpetik dan akhir baris CRLF,
  tetapi **belum dijalankan di PC Windows pengguna**. Jalankan peluncur di PC
  untuk memastikan instalasi Python dikenali.
- Bot Telegram sungguhan belum dihubungkan/dijalankan, sehingga `/dp` belum
  tersedia pada bot utama. Simulasi Telegram berjalan melalui terminal.
- Midtrans sandbox/live belum terhubung. Tidak ada pengujian transaksi nyata.
- Nara, Laras, TaqiDesk, watermark PDF, serta pengiriman dokumen belum terhubung
  ke prototipe ini.
- Suite seluruh aplikasi utama tidak dijalankan ulang; ini hasil pengujian modul
  terisolasi, bukan sertifikasi bahwa seluruh aplikasi bebas error.
- Tarif tetap berstatus usulan, belum diberlakukan kepada pelanggan.

Instruksi integrasi dan pengujian lanjutan ada di `README_UNTUK_CLAUDE.md`.
