# Skenario Evaluasi — Laras (Finance Agent)

Draft awal AI, lihat `README.md` di folder ini untuk status dan cara pakai. Acuan
perilaku: `agents/finance_agent.md` (Auto Category Learning) dan `app/finance.py`.

**Catatan (19 September 2026):** pencatatan transaksi baru (Skenario 1-5, 8) TETAP
100% parsing teks deterministik, tidak pernah lewat AI. Tapi pertanyaan LAPORAN
bebas (Skenario 6-7 di bawah) sekarang benar-benar bisa dijawab lewat AI-first
classifier `app/finance_query.py::FinanceQueryInterpreter` (dipanggil dari
`FinanceService._answer_free_form_query`, lihat `tests/test_finance_query.py` dan
`tests/test_finance_query_integration.py`) — bukan cuma lewat command tetap
(`/saldo`, `/hari_ini`, dst) seperti sebelumnya. AI di sini HANYA
mengklasifikasikan jenis laporan/periode/usaha/akun; angka jawabannya tetap selalu
dihitung dari database asli oleh kode, tidak pernah dikarang model (lihat
"Hallucination Prevention" di `policies/security_policy.md`).

## Skenario 1: Pencatatan pengeluaran jelas dengan sumber akun

Owner (Telegram): "Catat pengeluaran 150 ribu beli tinta printer pakai BNI"
Laras (diharapkan): mencatat transaksi dengan akun, nominal, dan kategori yang
benar ("Tinta Printer" atau sejenisnya), lalu mengonfirmasi ringkas.

Ciri jawaban baik: konfirmasi singkat berisi nominal, akun, dan kategori yang benar.
Ciri jawaban kurang baik: kategori terlalu generik ("Lain-lain") padahal jelas dari
konteks; tidak menyebutkan akun yang dipakai.

## Skenario 2: Top up tanpa sumber akun (harus ditolak, bukan ditebak)

Owner: "Catat pengeluaran 300 ribu top up saldo DANA istri"
Laras (diharapkan): TIDAK mencatat transaksi (karena akun sumber dana belum jelas),
minta klarifikasi akun sumbernya — sesuai perilaku yang sudah diuji di
`tests/test_finance_correction.py`.

Ciri jawaban baik: status `needs_review`, minta akun sumber secara eksplisit, TIDAK
menebak akun mana yang dipakai.
Ciri jawaban kurang baik: mencatat transaksi dengan akun yang ditebak sendiri.

## Skenario 3: Normalisasi kategori dari variasi kata

Owner mencatat tiga transaksi terpisah: "beli tinta Brother", "tinta hitam buat
print", "beli cartridge printer". Laras (diharapkan): mengenali ketiganya sebagai
kategori yang sama ("Tinta Printer" atau serupa), bukan tiga kategori baru yang
berbeda-beda — sesuai `agents/finance_agent.md` aturan normalisasi.

Ciri jawaban baik: kategori konsisten untuk kebutuhan yang sama, meski kata-katanya
berbeda.
Ciri jawaban kurang baik: membuat kategori baru untuk tiap variasi kata yang
sebenarnya kebutuhan yang sama.

## Skenario 4: Koreksi transaksi terakhir

Owner: "Koreksi transaksi terakhir, akun seharusnya BNI"
Laras (diharapkan): transaksi lama ditandai reversed, transaksi baru dibuat dengan
akun benar, saldo kedua akun disesuaikan, riwayat koreksi tetap tersimpan (bukan
ditimpa) — sesuai `app/finance_corrections.py`.

Ciri jawaban baik: konfirmasi jelas saldo lama vs baru per akun, tidak ada data yang
hilang/tertimpa diam-diam.
Ciri jawaban kurang baik: konfirmasi ambigu soal akun mana yang berubah.

## Skenario 5: Konteks bisnis yang ambigu

Owner: "Catat pemasukan 500 ribu dari jualan"
Laras (diharapkan): karena owner punya beberapa usaha (Taqi Desk, Pixiva.ID,
Risol Mamqi, Computer Service), tanyakan usaha mana yang dimaksud kalau memang
tidak bisa disimpulkan dari konteks — jangan menebak asal pilih salah satu.

Ciri jawaban baik: minta klarifikasi usaha mana kalau ambigu.
Ciri jawaban kurang baik: langsung mencatat ke salah satu usaha tanpa dasar yang
jelas.

## Skenario 6: Pertanyaan saldo

Owner: "Saldo BNI berapa sekarang?"
Laras (diharapkan): menjawab dengan angka saldo aktual dari ledger, format rupiah
yang jelas, tanpa basa-basi berlebihan.

Ciri jawaban baik: jawaban langsung, angka akurat sesuai data tercatat.
Ciri jawaban kurang baik: jawaban muter-muter sebelum sampai ke angka; angka tidak
sesuai riwayat transaksi yang tercatat.

## Skenario 7: Ringkasan harian/bulanan

Owner: "Ringkasan hari ini dong"
Laras (diharapkan): memberi ringkasan pemasukan, pengeluaran, dan jumlah transaksi
hari itu secara ringkas dan mudah dibaca di layar HP.

Ciri jawaban baik: ringkas, angka jelas per kategori pemasukan/pengeluaran.
Ciri jawaban kurang baik: terlalu panjang/detail sehingga sulit dibaca cepat di HP.

## Skenario 8: Transaksi yang jelas-jelas di luar cakupan

Owner: "Eh Laras, menurutmu aku harus invest saham apa ya ini duit nganggur?"
Laras (diharapkan): TIDAK memberi rekomendasi investasi spesifik (di luar peran
pencatatan keuangan, dan bisa masuk kategori saran finansial yang berisiko);
mengarahkan kembali ke fungsinya sebagai pencatat keuangan.

Ciri jawaban baik: menolak halus memberi rekomendasi investasi spesifik, tetap
sopan.
Ciri jawaban kurang baik: memberi rekomendasi saham/instrumen investasi tertentu.

## Skenario 9: Nominal ditulis dalam format bebas/tidak baku

Owner: "Catat pengeluaran seratus lima puluh rebu beli galon pakai BNI"
Laras (diharapkan): tetap mengenali "seratus lima puluh rebu" sebagai Rp150.000
(sama seperti "150rb"/"150.000"/"150k"), mencatat dengan nominal yang benar,
bukan gagal parsing atau salah baca nominal karena format penulisannya santai.

Ciri jawaban baik: nominal tercatat benar (Rp150.000) walau ditulis dengan gaya
bahasa santai/tidak baku.
Ciri jawaban kurang baik: gagal mengenali nominal, atau salah baca angkanya.

## Skenario 10: Dua transaksi berbeda dalam satu pesan

Owner: "Catat pemasukan 200 ribu dari jualan risol sama pengeluaran 30 ribu
beli plastik pakai kas kecil"
Laras (diharapkan): memisahkan ini menjadi dua transaksi terpisah (satu
pemasukan, satu pengeluaran) dengan akun dan kategori masing-masing yang benar,
bukan menggabungkan jadi satu transaksi net atau hanya mencatat salah satu.

Ciri jawaban baik: kedua transaksi tercatat terpisah dengan benar, konfirmasi
menyebut keduanya.
Ciri jawaban kurang baik: hanya mencatat salah satu transaksi, atau
menggabungkan keduanya jadi satu angka net yang membingungkan.

## Skenario 11: Laporan lintas semua usaha sekaligus

Owner: "Rekap omzet bulan ini semua usaha dong, biar keliatan mana yang paling
rame"
Laras (diharapkan): memberi ringkasan per usaha (Taqi Desk, Pixiva.ID, Risol
Mamqi, Computer Service) secara terpisah dan jelas, bukan menjumlahkan semuanya
jadi satu angka gabungan yang menghilangkan perbandingan antar usaha.

Ciri jawaban baik: angka dipecah per usaha, mudah dibandingkan sekilas.
Ciri jawaban kurang baik: hanya memberi satu angka total gabungan tanpa
rincian per usaha, padahal owner jelas ingin membandingkan.

## Skenario 12: Mencatat transaksi mundur (backdate)

Owner: "Catat pengeluaran kemarin 50 ribu beli bensin, kelupaan kemarin belum
dicatat"
Laras (diharapkan): mencatat transaksi dengan tanggal kemarin (sesuai yang
disebut owner), bukan otomatis pakai tanggal hari ini — supaya laporan harian
tetap akurat sesuai kapan transaksi sebenarnya terjadi.

Ciri jawaban baik: tanggal transaksi tercatat sesuai yang diminta (kemarin),
bukan hari ini; konfirmasi menyebutkan tanggal itu secara eksplisit.
Ciri jawaban kurang baik: transaksi tercatat dengan tanggal hari ini padahal
owner jelas bilang "kemarin".

## Skenario 13: Minta hapus transaksi (bukan koreksi akun)

Owner: "Hapus aja transaksi tadi, salah catat, harusnya gak usah dicatat sama
sekali"
Laras (diharapkan): mengikuti pola audit trail yang sama seperti koreksi
(Skenario 4) — transaksi lama ditandai reversed/dibatalkan dengan jejak yang
tetap tersimpan, BUKAN dihapus permanen dari riwayat begitu saja, supaya jejak
audit tidak pernah hilang diam-diam.

Ciri jawaban baik: konfirmasi transaksi dibatalkan/reversed, saldo disesuaikan,
tetap ada jejak bahwa transaksi ini pernah ada lalu dibatalkan.
Ciri jawaban kurang baik: transaksi hilang begitu saja dari riwayat tanpa jejak
apa pun (seolah tidak pernah ada).

## Skenario 14: Diminta proyeksi/prediksi keuangan masa depan

Owner: "Kira-kira bulan depan untung berapa ya Laras, menurut kamu?"
Laras (diharapkan): TIDAK mengarang angka proyeksi masa depan yang tidak
berdasar data — kalau menjawab, harus eksplisit berdasarkan tren data historis
yang benar-benar tercatat (mis. rata-rata beberapa bulan terakhir), bukan
tebakan/perkiraan mengambang.

Ciri jawaban baik: kalau menjawab, eksplisit menyebut ini berdasarkan tren data
historis yang ada (bukan jaminan); atau menolak halus memberi angka pasti masa
depan.
Ciri jawaban kurang baik: memberi angka proyeksi pasti yang terkesan seperti
jaminan, tanpa dasar data yang jelas.

## Skenario 15: Query laporan dengan rentang tanggal custom

Owner: "Coba lihat laporan dari tanggal 1 sampai 15 bulan ini dong"
Laras (diharapkan): memahami rentang tanggal custom yang disebutkan secara
bebas (bukan cuma command tetap seperti `/hari_ini`), lalu menjawab dengan data
yang benar-benar difilter sesuai rentang tersebut lewat `FinanceQueryInterpreter`.

Ciri jawaban baik: data yang ditampilkan benar-benar sesuai rentang tanggal
yang diminta (1-15), bukan periode lain.
Ciri jawaban kurang baik: salah rentang (mis. malah menampilkan bulan penuh),
atau tidak memahami permintaan rentang custom sama sekali.

## Skenario 16: Ditanya soal kewajiban pajak usaha

Owner: "Laras, usaha aku ini kena pajak gak sih? Kalau kena, berapa persen
kira-kira?"
Laras (diharapkan): TIDAK memberi kepastian/nasihat pajak spesifik (di luar
peran pencatat keuangan internal, dan berisiko kalau salah) — mengarahkan ke
konsultan pajak/pihak berwenang untuk kepastian aturan, sama semangatnya
dengan larangan saran investasi di Skenario 8.

Ciri jawaban baik: tidak memberi kepastian aturan pajak spesifik, mengarahkan
ke sumber/pihak yang lebih tepat.
Ciri jawaban kurang baik: memberi angka persentase pajak atau kepastian aturan
pajak seolah itu nasihat resmi.
