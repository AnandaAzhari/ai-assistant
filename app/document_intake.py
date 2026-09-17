"""AI-first interpreter untuk MakalahBrief.

Model memahami bahasa pelanggan, typo, urutan acak, dan koreksi. Kode aplikasi tetap
memegang schema/state dan hanya menerima JSON terstruktur. Field yang tidak disebut
pada pesan terbaru wajib null agar data lama tidak tertimpa tanpa alasan.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.providers.base import ModelProvider


INTAKE_PROMPT = """Kamu adalah interpreter MakalahBrief untuk Document Agent Taqi DocuTech.
Tugasmu memahami PESAN PELANGGAN TERBARU dan mengubahnya menjadi update data terstruktur.

ATURAN WAJIB:
- pahami bahasa Indonesia natural, singkatan chat, typo ringan, dan urutan informasi yang acak;
- ekstrak hanya informasi yang benar-benar disebut atau dikoreksi pada PESAN TERBARU;
- untuk field yang tidak disebut pada pesan terbaru, isi null; JANGAN mengulang data lama hanya karena ada di konteks;
- jika pelanggan mengoreksi data lama, kembalikan nilai terbaru pada field tersebut;
- jika koreksi hanya menyebut sebagian nilai gabungan, gunakan DATA TERSIMPAN untuk menjaga bagian yang masih berlaku.
  Contoh: data lama `Kelas XII, Semester 1`, pesan baru `eh salah semester 2` -> `class_semester` menjadi `Kelas XII, Semester 2`;
- `Informatika, SMK, XII semseter 1` harus dipahami sebagai subject=Informatika, institution_level=SMK, class_semester=`Kelas XII, Semester 1`;
- jangan mengarang judul, fokus, sumber, kelas, sekolah, atau arahan yang tidak disebut pelanggan;
- jika pelanggan mengatakan topik/judul belum ada, isi topic_title dengan null;
- fokus, tingkat bahasa, ketentuan sumber, sitasi, hal wajib/larangan, dan pedoman resmi bersifat opsional;
- keluarkan JSON VALID SAJA, tanpa Markdown dan tanpa penjelasan.

Gunakan semua key berikut:
{
  "institution_level": null,
  "class_semester": null,
  "subject": null,
  "topic_title": null,
  "target_length": null,
  "teacher_instructions": null,
  "focus": null,
  "language_level": null,
  "source_requirements": null,
  "citation_style": null,
  "must_include": null,
  "must_avoid": null,
  "official_guideline": null
}

NORMALISASI PRAKTIS:
- `XII semseter 1`, `kelas 12 semester 1` -> `Kelas XII, Semester 1` bila maksudnya jelas;
- `8 hal`, `8 hlm`, `8 halaman` -> `8 halaman`;
- `SMK`, `SMA`, `SMP`, `SD`, `kuliah` boleh langsung menjadi institution_level;
- nama mata pelajaran boleh disebut tanpa kata `mapel`, misalnya hanya `Informatika`;
- `bahas yang mudah dipahami` dapat menjadi language_level=`sederhana/mudah dipahami`;
- `pakai sumber 5 tahun terakhir` dapat menjadi source_requirements=`sumber maksimal 5 tahun terakhir`;
- jangan membuat nilai default untuk field opsional bila pelanggan tidak menyebutkannya.
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
    ALLOWED_FIELDS = {
        "institution_level", "class_semester", "subject", "topic_title",
        "target_length", "teacher_instructions", "focus", "language_level",
        "source_requirements", "citation_style", "must_include", "must_avoid",
        "official_guideline",
    }

    def __init__(self, provider: ModelProvider):
        self.provider = provider

    @staticmethod
    def should_use(raw: str, missing_fields: list[str] | None = None) -> bool:
        """Kompatibilitas lama: pada fase briefing semua pesan natural boleh diinterpretasi AI."""
        text = re.sub(r"\s+", " ", (raw or "").strip())
        return bool(text and not text.startswith("/"))

    @classmethod
    def _extract_json(cls, text: str) -> dict[str, object]:
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
        return {key: payload.get(key) for key in cls.ALLOWED_FIELDS}

    def interpret(self, raw: str, current_text: str) -> IntakeResult:
        if not self.provider or not self.provider.configured:
            return IntakeResult("belum_dikonfigurasi", {}, warning="Provider AI belum tersedia.")
        messages = [
            {"role": "system", "content": INTAKE_PROMPT},
            {
                "role": "user",
                "content": "DATA TERSIMPAN SAAT INI:\n" + current_text[:3500]
                + "\n\nPESAN PELANGGAN TERBARU:\n" + (raw or "")[:2500],
            },
        ]
        reply = self.provider.generate(messages, max_tokens=500, temperature=0.0, timeout=25)
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
