"""Pengumpul data awal makalah secara lokal tanpa token AI.

Lima data utama dikumpulkan sebelum AI membuat kerangka makalah. Arahan guru/dosen
bersifat opsional agar pelanggan tidak dipaksa mengisi hal yang memang tidak ada.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, fields


_DEFAULT_LENGTH_SENTINEL = "__confirm_default_8_12_pages__"


@dataclass
class MakalahRequirements:
    institution_level: str = ""
    class_semester: str = ""
    subject: str = ""
    topic_title: str = ""
    teacher_instructions: str = ""
    target_length: str = ""

    FIELD_LABELS = {
        "institution_level": "Jenjang",
        "class_semester": "Kelas/semester",
        "subject": "Mata pelajaran/mata kuliah",
        "topic_title": "Topik/judul",
        "teacher_instructions": "Arahan guru/dosen",
        "target_length": "Jumlah halaman/kata",
    }

    REQUIRED_FIELDS = (
        "institution_level",
        "class_semester",
        "subject",
        "topic_title",
        "target_length",
    )

    def reset(self) -> None:
        for item in fields(self):
            setattr(self, item.name, "")

    @property
    def complete(self) -> bool:
        return not self.missing_fields()

    def missing_fields(self) -> list[str]:
        missing: list[str] = []
        for key in self.REQUIRED_FIELDS:
            value = getattr(self, key)
            if not value or value == _DEFAULT_LENGTH_SENTINEL:
                missing.append(key)
        return missing

    def update(self, message: str) -> None:
        raw = (message or "").strip()
        if not raw:
            return
        lowered = raw.casefold()

        if self.target_length == _DEFAULT_LENGTH_SENTINEL:
            if re.search(r"\b(?:setuju|boleh|oke|ok|ya|iya|sip)\b", lowered):
                self.target_length = "8-12 halaman"
            else:
                length = self._extract_length(raw)
                if length:
                    self.target_length = length

        self._parse_labeled_lines(raw)
        self._parse_natural_text(raw)

    def _parse_labeled_lines(self, raw: str) -> None:
        label_map = {
            "jenjang": "institution_level",
            "instansi": "institution_level",
            "jenjang/instansi": "institution_level",
            "kelas": "class_semester",
            "semester": "class_semester",
            "kelas/semester": "class_semester",
            "mapel": "subject",
            "mata pelajaran": "subject",
            "mata kuliah": "subject",
            "mata pelajaran/mata kuliah": "subject",
            "topik": "topic_title",
            "judul": "topic_title",
            "topik/judul": "topic_title",
            "instruksi": "teacher_instructions",
            "instruksi guru": "teacher_instructions",
            "instruksi dosen": "teacher_instructions",
            "instruksi guru/dosen": "teacher_instructions",
            "arahan": "teacher_instructions",
            "arahan guru": "teacher_instructions",
            "arahan dosen": "teacher_instructions",
            "arahan guru/dosen": "teacher_instructions",
            "target": "target_length",
            "target panjang": "target_length",
            "panjang": "target_length",
            "jumlah halaman": "target_length",
            "jumlah kata": "target_length",
        }
        for line in raw.splitlines():
            match = re.match(r"^\s*(?:[-*>•]\s*)?([^:]{2,40})\s*:\s*(.+?)\s*$", line)
            if not match:
                continue
            label = re.sub(r"\s+", " ", match.group(1).strip().casefold())
            value = match.group(2).strip()
            key = label_map.get(label)
            if not key or not value:
                continue
            value_lower = value.casefold()
            if key == "topic_title" and value_lower in {"belum ada", "belum ditentukan", "tidak ada", "-"}:
                continue
            if key == "teacher_instructions" and value_lower in {
                "tidak ada", "tidak ada instruksi", "tidak ada arahan", "-", "skip"
            }:
                value = "Tidak ada arahan khusus"
            if key == "target_length" and re.search(r"tidak ada|belum ada|belum ditentukan", value_lower):
                setattr(self, key, _DEFAULT_LENGTH_SENTINEL)
                continue
            if key == "target_length":
                parsed = self._extract_length(f"jumlah halaman {value}") or self._extract_length(value)
                if parsed:
                    value = parsed
            setattr(self, key, value[:300])

    @staticmethod
    def _extract_length(raw: str) -> str:
        """Ambil target panjang dari bahasa natural dengan urutan yang fleksibel.

        Contoh yang didukung: `8 halaman`, `sekitar 8 halaman`,
        `jumlah halaman 8`, `halaman 8`, `target 1200 kata`.
        """
        text = re.sub(r"\s+", " ", (raw or "").strip())

        # Bentuk paling umum: angka lalu satuan.
        match = re.search(
            r"\b(\d+\s*(?:[-–—]\s*\d+\s*)?(?:halaman|page|pages|kata))\b",
            text,
            re.IGNORECASE,
        )
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip()

        # Bahasa natural Indonesia sering membalik urutan: `jumlah halaman 8`.
        match = re.search(
            r"\b(?:jumlah\s+|target\s+|sekitar\s+|kira[- ]?kira\s+)?"
            r"(halaman|page|pages|kata)\s*(?:sebanyak\s*)?(\d+)"
            r"(?:\s*[-–—]\s*(\d+))?\b",
            text,
            re.IGNORECASE,
        )
        if match:
            unit = match.group(1).casefold()
            start = match.group(2)
            end = match.group(3)
            canonical_unit = "halaman" if unit in {"halaman", "page", "pages"} else "kata"
            return f"{start}-{end} {canonical_unit}" if end else f"{start} {canonical_unit}"

        # Bentuk `jumlah halaman: 8` / `target halaman = 8`.
        match = re.search(
            r"\b(?:jumlah|target)\s+(halaman|page|pages|kata)\s*[:=]?\s*(\d+)"
            r"(?:\s*[-–—]\s*(\d+))?\b",
            text,
            re.IGNORECASE,
        )
        if match:
            unit = match.group(1).casefold()
            start = match.group(2)
            end = match.group(3)
            canonical_unit = "halaman" if unit in {"halaman", "page", "pages"} else "kata"
            return f"{start}-{end} {canonical_unit}" if end else f"{start} {canonical_unit}"
        return ""

    def _parse_natural_text(self, raw: str) -> None:
        lowered = raw.casefold()

        if not self.institution_level:
            level_patterns = [
                (r"\bperguruan tinggi\b|\bkampus\b|\bkuliah\b", "Perguruan tinggi"),
                (r"\bman\b", "MAN"),
                (r"\bmadrasah aliyah\b", "MA"),
                (r"\bsma\b", "SMA"),
                (r"\bsmk\b", "SMK"),
                (r"\bmts\b", "MTs"),
                (r"\bsmp\b", "SMP"),
                (r"\bmi\b|\bmadrasah ibtidaiyah\b", "MI"),
                (r"\bsd\b|\bsekolah dasar\b", "SD"),
            ]
            for pattern, value in level_patterns:
                if re.search(pattern, lowered):
                    self.institution_level = value
                    break

        if not self.class_semester:
            match = re.search(r"\bkelas\s+([0-9]{1,2}|[ivxlcdm]{1,7})(?:\s+([a-z]+\s*\d*))?", raw, re.IGNORECASE)
            if match:
                extra = (match.group(2) or "").strip()
                value = f"Kelas {match.group(1).upper()}"
                if extra and extra.casefold() not in {"atau", "dan", "dengan", "untuk"}:
                    value += f" {extra.upper()}"
                self.class_semester = value[:80]
            else:
                match = re.search(r"\bsemester\s+([0-9]{1,2}|[ivxlcdm]{1,7})\b", raw, re.IGNORECASE)
                if match:
                    self.class_semester = f"Semester {match.group(1).upper()}"

        if not self.subject:
            common_subjects = [
                "Bahasa Indonesia", "Bahasa Inggris", "Matematika", "Pendidikan Pancasila",
                "Pancasila", "Biologi", "Kimia", "Fisika", "Geografi", "Sejarah", "Ekonomi",
                "Sosiologi", "Informatika", "TIK", "IPAS", "IPA", "IPS", "Fiqih", "PAI",
                "PKN", "PPKn",
            ]
            for subject in common_subjects:
                if re.search(rf"\b{re.escape(subject)}\b", raw, re.IGNORECASE):
                    self.subject = subject
                    break

        if not self.topic_title:
            match = re.search(
                r"\b(?:makalah\s+tentang|tentang|topik(?:nya)?\s*[:=]?|judul(?:nya)?\s*[:=]?)\s*[\"“]?([^\n?.]+)",
                raw,
                re.IGNORECASE,
            )
            if match:
                value = match.group(1).strip(" \t\"”'")
                if value and value.casefold() not in {"belum ada", "belum ditentukan", "tidak ada"}:
                    self.topic_title = value[:240]

        if not self.teacher_instructions:
            if re.search(r"\b(?:tidak ada|tanpa)\s+(?:instruksi|arahan|ketentuan)(?:\s+khusus)?\b", lowered):
                self.teacher_instructions = "Tidak ada arahan khusus"

        if not self.target_length:
            length = self._extract_length(raw)
            if length:
                self.target_length = length
            elif re.search(r"\b(?:tidak ada|belum ada|tanpa)\s+(?:ketentuan\s+)?(?:panjang|jumlah halaman|target)\b", lowered):
                self.target_length = _DEFAULT_LENGTH_SENTINEL

    def question_text(self) -> str:
        missing = self.missing_fields()
        if not missing:
            return "Data utama makalah sudah lengkap."

        if self.target_length == _DEFAULT_LENGTH_SENTINEL and missing == ["target_length"]:
            return "Kalau tidak ada ketentuan jumlah halaman, saya sarankan **8–12 halaman**. Apakah boleh?"

        questions = {
            "institution_level": "Jenjang sekolah/kampus (mis. SMP, SMA, SMK, atau kuliah)",
            "class_semester": "Kelas atau semester",
            "subject": "Mata pelajaran atau mata kuliah",
            "topic_title": "Topik atau judul makalah",
            "target_length": "Jumlah halaman atau kata yang diinginkan",
        }
        lines = ["Sebelum saya buat kerangka makalah, saya masih perlu:"]
        for index, key in enumerate(missing, start=1):
            lines.append(f"{index}. **{questions[key]}**")
        lines.append("\nBoleh dijawab sekaligus.")
        lines.append("Kalau ada arahan khusus dari guru/dosen, boleh dikirim juga **(opsional)**.")
        return "\n".join(lines)

    def structured_text(self) -> str:
        target = "8-12 halaman" if self.target_length == _DEFAULT_LENGTH_SENTINEL else self.target_length
        teacher_note = self.teacher_instructions or "Tidak ada arahan khusus"
        return (
            f"Jenjang: {self.institution_level}\n"
            f"Kelas/semester: {self.class_semester}\n"
            f"Mata pelajaran/mata kuliah: {self.subject}\n"
            f"Topik/judul: {self.topic_title}\n"
            f"Arahan guru/dosen: {teacher_note}\n"
            f"Jumlah halaman/kata: {target}"
        )
