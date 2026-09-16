"""Pengumpul data cover makalah lokal tanpa token AI."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class MakalahCoverData:
    institution_name: str = ""
    assignment_type: str = ""  # individu | kelompok
    author_name: str = ""
    group_name: str = ""
    group_members: str = ""
    academic_year: str = ""
    teacher_name: str = ""

    def reset(self) -> None:
        self.institution_name = ""
        self.assignment_type = ""
        self.author_name = ""
        self.group_name = ""
        self.group_members = ""
        self.academic_year = ""
        self.teacher_name = ""

    @property
    def complete(self) -> bool:
        if not self.institution_name or not self.assignment_type:
            return False
        if self.assignment_type == "individu":
            return bool(self.author_name)
        if self.assignment_type == "kelompok":
            return bool(self.group_name and self.group_members)
        return False

    def update(self, message: str) -> None:
        raw = (message or "").strip()
        if not raw:
            return

        label_map = {
            "sekolah": "institution_name",
            "nama sekolah": "institution_name",
            "kampus": "institution_name",
            "nama kampus": "institution_name",
            "instansi": "institution_name",
            "jenis tugas": "assignment_type",
            "tugas": "assignment_type",
            "nama penyusun": "author_name",
            "penyusun": "author_name",
            "nama": "author_name",
            "kelompok": "group_name",
            "nama kelompok": "group_name",
            "nomor kelompok": "group_name",
            "anggota": "group_members",
            "anggota kelompok": "group_members",
            "nama anggota": "group_members",
            "tahun ajaran": "academic_year",
            "tahun": "academic_year",
            "guru": "teacher_name",
            "guru pembimbing": "teacher_name",
            "nama guru": "teacher_name",
            "dosen": "teacher_name",
            "nama dosen": "teacher_name",
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
            if key == "assignment_type":
                if "kelompok" in value_lower:
                    self.assignment_type = "kelompok"
                elif "individu" in value_lower or "sendiri" in value_lower:
                    self.assignment_type = "individu"
                continue
            if key in {"academic_year", "teacher_name"} and value_lower in {
                "tidak ada", "tidak perlu", "opsional", "-", "skip"
            }:
                setattr(self, key, "Tidak dicantumkan")
                continue
            setattr(self, key, value[:500])

        lowered = raw.casefold()
        if not self.assignment_type:
            if re.search(r"\bkelompok\b", lowered):
                self.assignment_type = "kelompok"
            elif re.search(r"\b(?:individu|sendiri)\b", lowered):
                self.assignment_type = "individu"

    def question_text(self) -> str:
        missing: list[str] = []
        if not self.institution_name:
            missing.append("Nama sekolah/kampus")
        if not self.assignment_type:
            missing.append("Jenis tugas: individu atau kelompok")
        elif self.assignment_type == "individu":
            if not self.author_name:
                missing.append("Nama penyusun")
        elif self.assignment_type == "kelompok":
            if not self.group_name:
                missing.append("Nama/nomor kelompok")
            if not self.group_members:
                missing.append("Nama seluruh anggota kelompok")

        if not missing:
            return (
                "Data cover utama sudah lengkap. Tahun ajaran dan nama guru/dosen bersifat opsional. "
                "Jika ingin dicantumkan, kirim sekarang; jika tidak, lanjutkan ke draft."
            )

        lines = ["Sebelum membuat draft, saya masih perlu data cover:"]
        for index, item in enumerate(missing, start=1):
            lines.append(f"{index}. **{item}**")
        lines.append("\nOpsional: tahun ajaran dan nama guru/dosen.")
        lines.append("Tahap ini diproses lokal tanpa token AI.")
        return "\n".join(lines)

    def structured_text(self) -> str:
        return (
            f"Sekolah/kampus: {self.institution_name}\n"
            f"Jenis tugas: {self.assignment_type}\n"
            f"Nama penyusun: {self.author_name}\n"
            f"Kelompok: {self.group_name}\n"
            f"Anggota: {self.group_members}\n"
            f"Tahun ajaran: {self.academic_year or 'Tidak dicantumkan'}\n"
            f"Guru/dosen: {self.teacher_name or 'Tidak dicantumkan'}"
        )
