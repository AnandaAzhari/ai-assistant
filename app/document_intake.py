"""Fallback AI ringan untuk memahami bahasa pelanggan saat parser lokal ragu.

Prinsip: parser lokal tetap utama dan gratis. AI hanya membantu mengisi field yang
masih kosong dari pesan pelanggan yang ambigu/typo. Output harus JSON kecil dan tidak
boleh mengarang data yang tidak disebutkan pelanggan.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.providers.base import ModelProvider


INTAKE_PROMPT = """Kamu adalah interpreter data pelanggan untuk layanan makalah.
Tugasmu HANYA mengekstrak data yang benar-benar disebutkan pelanggan.
Jangan membuat judul, kelas, sekolah, mata pelajaran, jumlah halaman, atau arahan yang tidak disebutkan.
Jika pelanggan mengatakan judul/topik belum ada, isi topic_title dengan null.
Jika ada typo ringan, pahami maksudnya secara wajar.

Keluarkan JSON VALID SAJA dengan key berikut:
{
  "institution_level": null,
  "class_semester": null,
  "subject": null,
  "topic_title": null,
  "teacher_instructions": null,
  "target_length": null
}

Contoh:
Pesan: "SMK, XII semester 2, mapel Informatika, judul belum, jumlah 8 halaman"
Hasil:
{"institution_level":"SMK","class_semester":"Kelas XII, Semester 2","subject":"Informatika","topic_title":null,"teacher_instructions":null,"target_length":"8 halaman"}
"""


@dataclass(frozen=True)
class IntakeResult:
    status: str
    values: dict[str, object]
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    warning: str = ""


class IntakeInterpreter:
    def __init__(self, provider: ModelProvider):
        self.provider = provider

    @staticmethod
    def should_use(raw: str, missing_fields: list[str]) -> bool:
        """Gunakan AI hanya jika pesan cukup natural/ambigu dan masih ada data kosong."""
        text = re.sub(r"\s+", " ", (raw or "").strip())
        if not text or not missing_fields:
            return False
        if text.startswith("/"):
            return False
        # Jawaban singkat sederhana lebih baik ditangani parser lokal.
        if len(text.split()) <= 2 and ":" not in text and "," not in text:
            return False
        # Pesan yang memuat beberapa potong data, typo, atau kalimat bebas layak dibantu AI.
        return len(text) >= 18 or "," in text or "makalah" in text.casefold()

    @staticmethod
    def _extract_json(text: str) -> dict[str, object]:
        clean = (text or "").strip()
        clean = re.sub(r"^```(?:json)?\s*", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\s*```$", "", clean)
        start = clean.find("{")
        end = clean.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Interpreter tidak mengembalikan JSON.")
        payload = json.loads(clean[start:end + 1])
        if not isinstance(payload, dict):
            raise ValueError("JSON interpreter harus berupa object.")
        allowed = {
            "institution_level", "class_semester", "subject", "topic_title",
            "teacher_instructions", "target_length",
        }
        return {key: payload.get(key) for key in allowed}

    def interpret(self, raw: str, current_text: str) -> IntakeResult:
        if not self.provider or not self.provider.configured:
            return IntakeResult("belum_dikonfigurasi", {}, warning="Provider AI belum tersedia.")
        messages = [
            {"role": "system", "content": INTAKE_PROMPT},
            {
                "role": "user",
                "content": "DATA YANG SUDAH TERSIMPAN:\n" + current_text[:1800]
                + "\n\nPESAN PELANGGAN BARU:\n" + (raw or "")[:1800],
            },
        ]
        reply = self.provider.generate(messages, max_tokens=220, temperature=0.0, timeout=25)
        if reply.status != "berhasil":
            return IntakeResult(
                reply.status, {}, model=reply.model, input_tokens=reply.input_tokens,
                output_tokens=reply.output_tokens, warning=reply.text,
            )
        try:
            values = self._extract_json(reply.text)
        except (ValueError, json.JSONDecodeError) as exc:
            return IntakeResult(
                "gagal", {}, model=reply.model, input_tokens=reply.input_tokens,
                output_tokens=reply.output_tokens, warning=str(exc),
            )
        return IntakeResult(
            "berhasil", values, model=reply.model,
            input_tokens=reply.input_tokens, output_tokens=reply.output_tokens,
        )
