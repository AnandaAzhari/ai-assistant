"""Pengklasifikasi pertanyaan keuangan bebas — lapisan AI-first di depan laporan
Finance Agent (Laras), khusus untuk owner lewat Telegram (bukan pelanggan).

Sebelumnya Laras hanya bisa dijawab lewat command tetap (`/hari_ini`, `/laba_rugi`,
`/arus_kas`, dst). Modul ini menambahkan lapisan AI-first di depannya, mengikuti pola
yang SAMA PERSIS seperti `app/customer_intent.py` dan `app/document_intake.py`: AI
HANYA dipakai untuk *mengklasifikasikan* pertanyaan owner ke field-field yang sudah
dienumerasi (report_type, period, business, account, kind) — AI TIDAK PERNAH dipakai
untuk menghitung atau mengarang angka jawaban. Semua angka tetap dihitung oleh kode
`app/finance.py` dari database asli, sama seperti command tetap yang sudah ada.

Keputusan desain penting (supaya tidak ada import melingkar dengan `app/finance.py`,
yang justru memiliki daftar `BUSINESSES`/`ACCOUNTS` asli): modul ini TIDAK mengimpor
apa pun dari `app/finance.py`. `business`/`account`/`kind` yang dikembalikan AI di sini
BELUM divalidasi terhadap daftar asli — validasi sesungguhnya dilakukan oleh
`FinanceService` (pemilik `BUSINESSES`/`ACCOUNTS`) setelah memanggil `interpret()`,
menolak/jatuh ke fallback kalau tidak cocok. `report_type`/`period` divalidasi di sini
karena keduanya murni milik modul ini (tidak berasal dari sumber lain).

Fail-safe: kalau provider AI belum dikonfigurasi, gagal, timeout, atau hasilnya tidak
valid/tidak dikenal, `interpret()` mengembalikan status selain "berhasil". Pemanggil
(`FinanceService.handle`) WAJIB jatuh ke router command/kata kunci deterministik yang
sudah ada sebagai fallback saat itu terjadi — perilaku lama (termasuk seluruh test yang
sudah ada) tidak pernah berubah.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.providers.base import ModelProvider
from app.topic_guard import is_verbatim_quote

# Jenis laporan yang bisa diminta lewat pertanyaan bebas. "tidak_didukung" dipakai AI
# untuk pertanyaan keuangan yang jelas tapi di luar cakupan V1 (mis. tren 12 bulan,
# piutang/utang, prediksi). "tidak_relevan" dipakai untuk pesan yang BUKAN pertanyaan
# laporan bebas (mis. ini sebenarnya instruksi mencatat transaksi baru, atau di luar
# topik keuangan) — pemanggil jatuh ke jalur lama tanpa menampilkan apa pun dari sini.
ALLOWED_REPORT_TYPES = (
    "ringkasan", "laba_rugi", "arus_kas", "saldo", "kategori_breakdown",
    "tidak_didukung", "tidak_relevan",
)
# Harus sama persis dengan periode yang dipahami `FinanceService._period_bounds`.
ALLOWED_PERIODS = ("hari_ini", "kemarin", "minggu_ini", "minggu_lalu", "bulan_ini", "bulan_lalu")
ALLOWED_KINDS = ("income", "expense")

QUERY_PROMPT = """Kamu adalah pengklasifikasi PERTANYAAN keuangan bebas dari OWNER (pemilik usaha,
BUKAN pelanggan) untuk Finance Agent (Laras) Taqi AI, dikirim lewat Telegram. Owner bertanya soal
laporan keuangan usahanya dengan bahasa bebas (bukan command /slash). Tugasmu HANYA mengklasifikasikan
pertanyaan itu ke field-field di bawah — kamu TIDAK PERNAH menghitung, mengingat, atau mengarang angka
jawaban sendiri; semua angka SELALU diambil dari database asli oleh kode, bukan olehmu.

Field yang harus kamu isi:
- report_type: pilih SATU dari:
  - "ringkasan": pemasukan/pengeluaran/arus kas bersih untuk satu periode (mis. "pemasukan bulan ini
    berapa", "pengeluaran minggu lalu berapa").
  - "laba_rugi": laba/rugi, untung/rugi bersih.
  - "arus_kas": saldo awal/masuk/keluar/saldo akhir per akun untuk satu periode.
  - "saldo": saldo akun SAAT INI (bukan untuk periode tertentu di masa lalu).
  - "kategori_breakdown": rincian pengeluaran ATAU pemasukan per kategori saja (bukan laba/rugi
    lengkap, mis. "pengeluaran paling besar kategori apa bulan ini").
  - "tidak_didukung": pertanyaan keuangan yang JELAS tapi laporannya di luar yang bisa dijawab sistem
    ini sekarang (mis. tren 12 bulan, piutang, utang, prediksi masa depan, tanggal spesifik di masa
    lalu selain hari_ini/kemarin).
  - "tidak_relevan": pesan BUKAN pertanyaan laporan keuangan bebas (mis. ini sebenarnya instruksi
    MENCATAT transaksi baru dengan nominal, atau di luar topik keuangan sama sekali).
- period: WAJIB salah satu dari "hari_ini", "kemarin", "minggu_ini", "minggu_lalu", "bulan_ini",
  "bulan_lalu". Kalau report_type "saldo" (tidak butuh periode) atau "tidak_didukung"/"tidak_relevan",
  isi saja "bulan_ini" sebagai default (akan diabaikan kode).
- business: nama usaha PERSIS seperti disebut owner dalam pesan (mis. "Risol Mamqi", "Taqi Desk"),
  atau null kalau owner tidak menyebut usaha tertentu (artinya semua usaha digabung).
- account: nama akun PERSIS seperti disebut owner dalam pesan (mis. "BCA", "Cash"), atau null kalau
  tidak disebutkan (artinya semua akun).
- kind: "income" kalau owner HANYA tanya soal pemasukan saja, "expense" kalau HANYA soal pengeluaran
  saja, atau null kalau tidak spesifik/menanyakan keduanya (arus kas bersih/laba-rugi).

Balas HANYA JSON tanpa markdown, dengan schema persis:
{"report_type": "salah satu dari daftar di atas", "period": "salah satu dari daftar periode", "business": "nama usaha atau null", "account": "nama akun atau null", "kind": "income atau expense atau null", "evidence": "kutipan singkat persis dari pesan owner yang mendasari klasifikasi ini"}

evidence WAJIB berupa kutipan kata-demi-kata dari pesan owner (bukan parafrase). JANGAN PERNAH
mengarang angka, nominal, saldo, atau jawaban laporan apa pun — itu sepenuhnya tugas kode, bukan kamu.
"""


@dataclass(frozen=True)
class FinanceQueryResult:
    status: str
    report_type: str = ""
    period: str = ""
    business: str = ""
    account: str = ""
    kind: str = ""
    evidence: str = ""
    model: str = ""


class FinanceQueryInterpreter:
    def __init__(self, provider: ModelProvider | None):
        self.provider = provider

    @property
    def configured(self) -> bool:
        return bool(self.provider and self.provider.configured)

    @staticmethod
    def _payload(text: str) -> dict:
        clean = re.sub(r"^```(?:json)?\s*", "", (text or "").strip(), flags=re.I)
        clean = re.sub(r"\s*```$", "", clean)
        payload = json.loads(clean)
        if not isinstance(payload, dict):
            raise ValueError("Respons klasifikasi harus object JSON.")
        return payload

    def interpret(self, raw: str) -> FinanceQueryResult:
        """AI-first: kembalikan status != 'berhasil' pada kondisi apa pun yang tidak
        bisa divalidasi penuh, supaya pemanggil (`FinanceService.handle`) selalu punya
        jalur fallback ke router command/kata kunci deterministik lama (lihat docstring
        modul)."""
        if not self.configured:
            return FinanceQueryResult("belum_dikonfigurasi")
        raw = (raw or "").strip()
        if not raw:
            return FinanceQueryResult("gagal")
        messages = [
            {"role": "system", "content": QUERY_PROMPT},
            {"role": "user", "content": "PESAN OWNER:\n" + raw[:4000]},
        ]
        reply = self.provider.generate(messages, max_tokens=300, temperature=0.0, timeout=20)
        if reply.status != "berhasil":
            return FinanceQueryResult(reply.status)
        try:
            payload = self._payload(reply.text)
            report_type = payload.get("report_type")
            period = payload.get("period")
            business = payload.get("business") or ""
            account = payload.get("account") or ""
            kind = payload.get("kind") or ""
            evidence = payload.get("evidence")
            if report_type not in ALLOWED_REPORT_TYPES:
                raise ValueError("report_type tidak dikenal.")
            if period not in ALLOWED_PERIODS:
                raise ValueError("period tidak dikenal.")
            if kind and kind not in ALLOWED_KINDS:
                raise ValueError("kind tidak dikenal.")
            if not isinstance(business, str) or not isinstance(account, str):
                raise ValueError("business/account harus string atau null.")
            if not is_verbatim_quote(evidence, raw):
                raise ValueError("Klasifikasi tanpa kutipan pesan owner yang valid.")
        except (ValueError, TypeError, json.JSONDecodeError):
            return FinanceQueryResult("gagal")
        return FinanceQueryResult(
            "berhasil", report_type=report_type, period=period, business=business,
            account=account, kind=kind, evidence=evidence, model=reply.model,
        )
