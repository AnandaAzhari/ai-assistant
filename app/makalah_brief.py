"""MakalahBrief v2 — schema pusat untuk memahami kebutuhan makalah pelanggan.

AI menjadi interpreter utama bahasa pelanggan. Kode deterministik tetap memegang
schema, validasi, state, dan fallback lokal sehingga model tidak menentukan alur
aplikasi secara bebas. Parser lama dipakai hanya sebagai fallback ketika AI gagal
atau tidak mengembalikan field yang aman dipakai.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, fields

from app.document_requirements import MakalahRequirements


DEFAULT_LENGTH_SENTINEL = "__confirm_default_8_12_pages__"
_EMPTY_TOPIC_VALUES = {
    "belum", "belum ada", "belum ditentukan", "belum punya", "tidak ada", "-",
    "makalah belum", "judul belum", "judul makalah belum", "belum ada judul",
}


@dataclass
class MakalahBrief:
    """State terstruktur yang menjadi sumber kebenaran tahap briefing makalah."""

    institution_level: str = ""
    class_semester: str = ""
    subject: str = ""
    topic_title: str = ""
    target_length: str = ""
    teacher_instructions: str = ""

    # Data kualitas. Tidak memblokir pembuatan kerangka jika pelanggan tidak punya
    # preferensi khusus; Nara boleh mengusulkan pilihan yang wajar pada kerangka.
    focus: str = ""
    language_level: str = ""
    source_requirements: str = ""
    citation_style: str = ""
    must_include: str = ""
    must_avoid: str = ""
    official_guideline: str = ""

    FIELD_LABELS = {
        "institution_level": "Jenjang",
        "class_semester": "Kelas/semester",
        "subject": "Mata pelajaran/mata kuliah",
        "topic_title": "Topik/judul",
        "target_length": "Jumlah halaman/kata",
        "teacher_instructions": "Arahan guru/dosen",
        "focus": "Fokus pembahasan",
        "language_level": "Tingkat bahasa",
        "source_requirements": "Ketentuan sumber",
        "citation_style": "Gaya sitasi",
        "must_include": "Wajib dimasukkan",
        "must_avoid": "Harus dihindari",
        "official_guideline": "Pedoman/template resmi",
    }

    CORE_REQUIRED_FIELDS = (
        "institution_level",
        "class_semester",
        "subject",
        "topic_title",
        "target_length",
    )

    QUALITY_FIELDS = (
        "teacher_instructions",
        "focus",
        "language_level",
        "source_requirements",
        "citation_style",
        "must_include",
        "must_avoid",
        "official_guideline",
    )

    def reset(self) -> None:
        for item in fields(self):
            setattr(self, item.name, "")

    @property
    def complete(self) -> bool:
        return not self.missing_fields()

    def missing_fields(self) -> list[str]:
        missing: list[str] = []
        for key in self.CORE_REQUIRED_FIELDS:
            value = getattr(self, key, "")
            if not value or value == DEFAULT_LENGTH_SENTINEL:
                missing.append(key)
        return missing

    def quality_missing_fields(self) -> list[str]:
        return [key for key in self.QUALITY_FIELDS if not getattr(self, key, "")]

    @staticmethod
    def _clean(value: object, limit: int = 500) -> str:
        if value is None:
            return ""
        return re.sub(r"\s+", " ", str(value).strip())[:limit]

    @staticmethod
    def _topic_is_missing(value: str) -> bool:
        clean = re.sub(r"\s+", " ", (value or "").strip().casefold())
        if clean in _EMPTY_TOPIC_VALUES:
            return True
        return bool(re.fullmatch(r"(?:judul\s+)?(?:makalah\s+)?belum(?:\s+(?:ada|ditentukan|punya))?", clean))

    @staticmethod
    def _normalize_target_length(value: str) -> str:
        clean = re.sub(r"\s+", " ", (value or "").strip())
        if not clean:
            return ""
        parsed = MakalahRequirements._extract_length(clean)
        if parsed:
            return parsed
        lowered = clean.casefold()
        if re.search(r"tidak ada|belum ada|belum ditentukan|terserah", lowered):
            return DEFAULT_LENGTH_SENTINEL
        return ""

    def apply_ai_values(self, values: dict[str, object]) -> list[str]:
        """Terapkan update AI terbaru dan izinkan koreksi field yang sudah terisi.

        Interpreter diwajibkan mengembalikan null untuk field yang tidak disebut pada
        pesan terbaru. Karena itu nilai non-null boleh menimpa nilai lama: ini yang
        membuat kalimat seperti `eh salah semester 2` bekerja secara natural.
        """
        if not isinstance(values, dict):
            return []

        changed: list[str] = []
        allowed = set(self.FIELD_LABELS)
        for key, raw_value in values.items():
            if key not in allowed or raw_value is None:
                continue
            value = self._clean(raw_value)
            if not value:
                continue
            lowered = value.casefold()

            if key == "topic_title" and self._topic_is_missing(value):
                continue
            if key == "teacher_instructions" and lowered in {
                "tidak ada", "tidak ada instruksi", "tidak ada arahan", "-", "skip"
            }:
                value = "Tidak ada arahan khusus"
            if key == "target_length":
                value = self._normalize_target_length(value)
                if not value:
                    continue

            old = getattr(self, key, "")
            if old != value:
                setattr(self, key, value)
                changed.append(key)
        return changed

    def apply_local_fallback(self, message: str) -> list[str]:
        """Isi hanya field inti yang masih kosong dengan parser deterministik lama."""
        legacy = MakalahRequirements(
            institution_level=self.institution_level,
            class_semester=self.class_semester,
            subject=self.subject,
            topic_title=self.topic_title,
            teacher_instructions=self.teacher_instructions,
            target_length=self.target_length,
        )
        legacy.update(message)

        changed: list[str] = []
        for key in (
            "institution_level", "class_semester", "subject", "topic_title",
            "teacher_instructions", "target_length",
        ):
            current = getattr(self, key, "")
            candidate = getattr(legacy, key, "")
            if not current and candidate:
                if key == "target_length" and candidate == "__confirm_default_8_12_pages__":
                    candidate = DEFAULT_LENGTH_SENTINEL
                setattr(self, key, candidate)
                changed.append(key)
        return changed

    def question_text(self) -> str:
        missing = self.missing_fields()
        if not missing:
            return "Data inti MakalahBrief sudah cukup untuk membuat kerangka."

        if self.target_length == DEFAULT_LENGTH_SENTINEL and missing == ["target_length"]:
            return (
                "Kalau tidak ada ketentuan jumlah halaman, saya sarankan **8–12 halaman**. "
                "Kalau cocok cukup jawab dengan bahasa biasa, misalnya `boleh`."
            )

        questions = {
            "institution_level": "Jenjang sekolah/kampus (mis. SMP, SMA, SMK, atau kuliah)",
            "class_semester": "Kelas dan/atau semester",
            "subject": "Mata pelajaran atau mata kuliah",
            "topic_title": "Topik atau judul makalah",
            "target_length": "Target jumlah halaman atau kata",
        }
        lines = ["Sebelum saya buat kerangka, masih ada data inti yang perlu saya pahami:"]
        for index, key in enumerate(missing, start=1):
            lines.append(f"{index}. **{questions[key]}**")
        lines.append("\nJawab dengan bahasa biasa; urutan bebas dan boleh sekaligus.")
        lines.append(
            "Kalau ada fokus khusus, arahan guru/dosen, ketentuan sumber, gaya bahasa, atau pedoman resmi, "
            "boleh dikirim juga. Data tambahan ini membantu kualitas tetapi tidak wajib jika memang tidak ada."
        )
        return "\n".join(lines)

    def structured_text(self) -> str:
        target = "8-12 halaman (menunggu konfirmasi)" if self.target_length == DEFAULT_LENGTH_SENTINEL else self.target_length
        return (
            "JENIS DOKUMEN: Makalah\n"
            f"Jenjang: {self.institution_level or 'Belum diketahui'}\n"
            f"Kelas/semester: {self.class_semester or 'Belum diketahui'}\n"
            f"Mata pelajaran/mata kuliah: {self.subject or 'Belum diketahui'}\n"
            f"Topik/judul: {self.topic_title or 'Belum diketahui'}\n"
            f"Target panjang: {target or 'Belum diketahui'}\n"
            f"Arahan guru/dosen: {self.teacher_instructions or 'Tidak disebutkan'}\n"
            f"Fokus pembahasan: {self.focus or 'Belum ditentukan; boleh diusulkan saat kerangka'}\n"
            f"Tingkat bahasa: {self.language_level or 'Sesuaikan dengan jenjang'}\n"
            f"Ketentuan sumber: {self.source_requirements or 'Tidak disebutkan'}\n"
            f"Gaya sitasi: {self.citation_style or 'Gunakan default/policy bila tidak ada arahan'}\n"
            f"Wajib dimasukkan: {self.must_include or 'Tidak disebutkan'}\n"
            f"Harus dihindari: {self.must_avoid or 'Tidak disebutkan'}\n"
            f"Pedoman/template resmi: {self.official_guideline or 'Tidak disebutkan'}"
        )

    def as_dict(self) -> dict[str, str]:
        return {item.name: getattr(self, item.name) for item in fields(self)}
