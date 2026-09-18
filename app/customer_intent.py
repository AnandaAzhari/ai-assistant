"""Customer intent classifier — lapisan AI-first di depan router kata kunci (Fase 3 lanjutan).

Sebelumnya `app/lead.py` mengenali maksud pelanggan murni lewat pencocokan kata kunci
(`LeadAgent._detect_customer_action`), yang gampang salah paham kalau pelanggan menulis
dengan gaya bahasa, typo, atau susunan kalimat yang tidak persis ada di daftar kata kunci.

Modul ini menambahkan lapisan AI-first di depan router kata kunci, mengikuti pola yang
sama seperti `app/document_intake.py`: AI HANYA dipakai untuk *mengklasifikasikan*
action_type dari bahasa natural pelanggan, dengan kutipan bukti dari pesan asli sebagai
validasi (meniru `IntakeInterpreter._is_quote`). AI TIDAK PERNAH dipakai untuk mengarang
teks balasan harga/status pesanan — teks balasan tetap deterministik di `app/lead.py`
(`_CUSTOMER_REPLY_TEXT`), supaya guardrail hallucination-prevention di
`docs/roadmap_customer_channel_v1.md` ("Guardrail Tambahan") tidak pernah bisa dilewati
oleh keluaran model.

Fail-safe: kalau provider AI belum dikonfigurasi, gagal, timeout, atau hasilnya tidak
valid/tidak dikenal, `classify()` mengembalikan status selain "berhasil". Pemanggil
(`LeadAgent._classify_customer_intent`) WAJIB jatuh ke router kata kunci lokal sebagai
fallback saat itu terjadi — jalur pelanggan tidak pernah macet menunggu AI.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.providers.base import ModelProvider

# Harus sama persis dengan action_type yang dikenali `LeadAgent._detect_customer_action`
# (teks balasannya) dan `app/approval_gate.py` (`_ROUTINE_AUTO_SEND`), supaya klasifikasi
# AI tidak pernah menghasilkan action_type yang tidak dikenal state machine approval.
ALLOWED_ACTIONS = (
    "kirim_salam",
    "konfirmasi_file_diterima",
    "kirim_status_antrean",
    "kirim_estimasi_harga_standar",
    "jawab_faq",
    "minta_detail_order",
)

INTENT_PROMPT = """Kamu adalah pengklasifikasi maksud pesan pelanggan Taqi AI (jasa cetak/dokumen).
Tugasmu HANYA menentukan satu action_type yang paling sesuai dari daftar berikut:
- kirim_salam: pelanggan sekadar menyapa, belum menyebut kebutuhan.
- konfirmasi_file_diterima: pelanggan bilang sudah mengirim file.
- kirim_status_antrean: pelanggan menanyakan status/progress pesanan yang sudah ada.
- kirim_estimasi_harga_standar: pelanggan menanyakan harga/biaya/tarif.
- jawab_faq: pertanyaan umum seperti jam buka, lokasi, cara pesan.
- minta_detail_order: pelanggan menyebut kebutuhan jasa baru tetapi detailnya belum lengkap,
  atau pesannya tidak cocok kategori lain di atas.

Balas HANYA JSON tanpa markdown, dengan schema persis:
{"action_type": "salah satu dari daftar di atas", "evidence": "kutipan singkat persis dari pesan pelanggan yang mendasari klasifikasi ini"}

evidence WAJIB berupa kutipan kata-demi-kata dari pesan pelanggan (bukan parafrase).
Jangan mengarang balasan, harga, status pesanan, atau informasi apa pun di luar action_type dan evidence.
"""


@dataclass(frozen=True)
class IntentResult:
    status: str
    action_type: str = ""
    evidence: str = ""
    model: str = ""


class CustomerIntentClassifier:
    def __init__(self, provider: ModelProvider | None):
        self.provider = provider

    @property
    def configured(self) -> bool:
        return bool(self.provider and self.provider.configured)

    @staticmethod
    def _is_quote(evidence: object, raw: str) -> bool:
        def normalize(value: str) -> str:
            return re.sub(r"\s+", " ", value).strip().casefold()
        return isinstance(evidence, str) and bool(normalize(evidence)) and normalize(evidence) in normalize(raw)

    @staticmethod
    def _payload(text: str) -> dict:
        clean = re.sub(r"^```(?:json)?\s*", "", (text or "").strip(), flags=re.I)
        clean = re.sub(r"\s*```$", "", clean)
        payload = json.loads(clean)
        if not isinstance(payload, dict):
            raise ValueError("Respons klasifikasi harus object JSON.")
        return payload

    def classify(self, raw: str) -> IntentResult:
        """AI-first: kembalikan status != 'berhasil' pada kondisi apa pun yang tidak
        bisa divalidasi penuh, supaya pemanggil selalu punya jalur fallback ke router
        kata kunci lokal (lihat docstring modul)."""
        if not self.configured:
            return IntentResult("belum_dikonfigurasi")
        raw = (raw or "").strip()
        if not raw:
            return IntentResult("gagal")
        messages = [
            {"role": "system", "content": INTENT_PROMPT},
            {"role": "user", "content": "PESAN PELANGGAN:\n" + raw[:4000]},
        ]
        reply = self.provider.generate(messages, max_tokens=300, temperature=0.0, timeout=20)
        if reply.status != "berhasil":
            return IntentResult(reply.status)
        try:
            payload = self._payload(reply.text)
            action_type = payload.get("action_type")
            evidence = payload.get("evidence")
            if action_type not in ALLOWED_ACTIONS:
                raise ValueError("action_type tidak dikenal.")
            if not self._is_quote(evidence, raw):
                raise ValueError("Klasifikasi tanpa kutipan pesan pelanggan yang valid.")
        except (ValueError, TypeError, json.JSONDecodeError):
            return IntentResult("gagal")
        return IntentResult("berhasil", action_type=action_type, evidence=evidence, model=reply.model)
