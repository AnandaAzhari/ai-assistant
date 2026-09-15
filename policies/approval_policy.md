# Approval Policy

## Tujuan
Menentukan tindakan yang dapat dilakukan agent secara otomatis dan tindakan yang harus meminta persetujuan admin.

## Prinsip Utama
Pesan WhatsApp rutin kepada pelanggan TIDAK perlu approval satu per satu. Approval hanya diperlukan untuk tindakan sensitif, tidak biasa, berisiko tinggi, atau di luar aturan bisnis yang sudah disetujui.

## Auto-Send yang Diizinkan
Agent boleh mengirim otomatis bila memenuhi policy dan konteks jelas, misalnya:
- salam dan respons awal;
- menjawab FAQ layanan, jam operasional, lokasi umum, metode pemesanan;
- meminta detail order yang belum lengkap;
- mengonfirmasi file diterima;
- memberi estimasi berdasarkan price list dan aturan yang sudah disetujui;
- memberi nomor antrean dan status To Do / In Progress / Review / Done;
- mengirim pengingat, status pekerjaan, atau instruksi pengambilan yang sudah distandardkan;
- menolak spam secara sopan atau menghentikan respons setelah threshold spam tercapai.

Semua pesan otomatis harus dicatat di audit log.

## Wajib Approval Admin
Agent harus berhenti dan meminta approval untuk:
- diskon khusus atau harga di luar price list;
- refund, kompensasi, atau pembatalan yang berdampak finansial;
- janji hukum, garansi khusus, atau komitmen di luar policy;
- mengirim data pribadi pelanggan kepada pihak lain;
- menghapus file/data penting;
- instalasi software atau perintah administrator;
- transaksi keuangan;
- eksekusi trading;
- pesan yang bersifat konflik, ancaman, komplain berat, atau potensi sengketa;
- kasus yang confidence-nya rendah tetapi risikonya tinggi.

## Escalation
Jika agent ragu:
1. jangan mengarang jawaban;
2. tandai kasus `NEEDS_REVIEW`;
3. ringkas masalah dan opsi;
4. minta keputusan admin hanya untuk bagian yang benar-benar perlu.

## Emergency Stop
Admin harus dapat menghentikan auto-send per channel, per agent, atau seluruh sistem melalui kill switch.
