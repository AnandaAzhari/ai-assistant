"""Pengumpul data cover makalah lokal tanpa token AI.

Data cover boleh dilengkapi atau diubah berulang selama sesi/order masih aktif.
Parser lokal menangani bahasa pelanggan yang umum agar informasi cover tidak perlu
selalu dikirim dengan format `Label: Nilai` dan tidak memboroskan token AI.
"""

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
        if not self.assignment_type:
            return False
        if self.assignment_type == "individu":
            return bool(self.author_name)
        if self.assignment_type == "kelompok":
            return bool(self.group_members)
        return False

    @staticmethod
    def _looks_like_plain_name(value: str) -> bool:
        """Deteksi jawaban nama sederhana saat sistem memang sedang menunggu nama.

        Contoh: `Ananda Azhari Batubara` atau `Siti Nurhaliza`.
        Sengaja konservatif supaya kalimat seperti `lanjut buat file` tidak dianggap nama.
        """
        clean = re.sub(r"\s+", " ", (value or "").strip())
        if not clean or ":" in clean or "," in clean or len(clean) > 90:
            return False
        words = clean.split()
        if not 1 <= len(words) <= 7:
            return False
        blocked = {
            "lanjut", "setuju", "oke", "ok", "iya", "ya", "boleh", "skip",
            "individu", "kelompok", "sekolah", "kampus", "guru", "dosen",
            "tahun", "ajaran", "tidak", "ada", "buat", "file", "word", "pdf",
        }
        lowered_words = {word.casefold().strip(".,") for word in words}
        if lowered_words & blocked:
            return False
        return all(re.fullmatch(r"[\w.'’-]+", word, flags=re.UNICODE) for word in words)

    @staticmethod
    def _clean_value(value: str) -> str:
        value = re.sub(r"\s+", " ", (value or "").strip(" \t:-=.,"))
        return value[:500]

    def _apply_optional_value(self, key: str, value: str) -> None:
        clean = self._clean_value(value)
        if not clean:
            return
        if clean.casefold() in {
            "tidak ada", "tidak perlu", "opsional", "-", "skip", "tidak dicantumkan"
        }:
            setattr(self, key, "Tidak dicantumkan")
        else:
            setattr(self, key, clean)

    def _update_natural_optional_fields(self, raw: str) -> None:
        """Baca data cover opsional dari bahasa biasa, tanpa AI.

        Contoh yang didukung:
        - `Nama sekolah SMK Negeri 2 Padangsidimpuan`
        - `sekolah saya SMK Negeri 2 Padangsidimpuan`
        - `tahun ajaran 2026/2027`
        - `Nama Guru Purnama Sari`
        - `dosen pengampu Budi Santoso`

        Parser dijalankan setiap kali ada pesan baru, jadi nilai yang sebelumnya
        `Tidak dicantumkan` tetap bisa ditambahkan atau diganti kemudian.
        """
        line_patterns = {
            "institution_name": (
                r"^(?:nama\s+)?(?:sekolah|kampus|universitas|instansi)\s+(?:saya\s+)?(.+)$",
                r"^(?:sekolah|kampus|universitas)\s+saya\s+(?:adalah\s+)?(.+)$",
            ),
            "academic_year": (
                r"^(?:tahun\s+ajaran|tahun\s+akademik)\s+(?:adalah\s+)?(.+)$",
            ),
            "teacher_name": (
                r"^(?:nama\s+)?(?:guru|dosen)(?:\s+(?:pembimbing|pengampu))?\s+(?:saya\s+)?(.+)$",
                r"^(?:guru|dosen)\s+saya\s+(?:adalah\s+)?(.+)$",
            ),
            "group_name": (
                r"^(?:nama|nomor)\s+kelompok\s+(.+)$",
            ),
        }

        for source_line in raw.splitlines():
            line = re.sub(r"^\s*(?:[-*>•]\s*)?", "", source_line).strip()
            if not line or ":" in line:
                continue
            for key, patterns in line_patterns.items():
                matched = False
                for pattern in patterns:
                    match = re.match(pattern, line, re.IGNORECASE)
                    if match:
                        self._apply_optional_value(key, match.group(1))
                        matched = True
                        break
                if matched:
                    break

    def update(self, message: str) -> None:
        raw = (message or "").strip()
        if not raw:
            return

        label_map = {
            "sekolah": "institution_name",
            "nama sekolah": "institution_name",
            "kampus": "institution_name",
            "nama kampus": "institution_name",
            "universitas": "institution_name",
            "nama universitas": "institution_name",
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
            "tahun akademik": "academic_year",
            "tahun": "academic_year",
            "guru": "teacher_name",
            "guru pembimbing": "teacher_name",
            "nama guru": "teacher_name",
            "dosen": "teacher_name",
            "dosen pengampu": "teacher_name",
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
            if key in {"institution_name", "group_name", "academic_year", "teacher_name"}:
                self._apply_optional_value(key, value)
                continue
            setattr(self, key, value[:500])

        # Jalankan parser natural setiap pesan, termasuk setelah data wajib cover lengkap.
        # Dengan begitu pelanggan boleh menambahkan data opsional belakangan tanpa reset.
        self._update_natural_optional_fields(raw)

        lowered = raw.casefold()
        if not self.assignment_type:
            if re.search(r"\bkelompok\b", lowered):
                self.assignment_type = "kelompok"
            elif re.search(r"\b(?:individu|sendiri)\b", lowered):
                self.assignment_type = "individu"

        # Bahasa natural untuk nama, mis. `nama saya Ananda Azhari Batubara`.
        if self.assignment_type == "individu" and not self.author_name:
            match = re.search(r"\b(?:nama\s+saya|saya\s+bernama|atas\s+nama)\s+(.+)$", raw, re.IGNORECASE)
            if match:
                candidate = match.group(1).strip(" .")
                if self._looks_like_plain_name(candidate):
                    self.author_name = candidate[:500]
            elif self._looks_like_plain_name(raw):
                # Jika satu-satunya data yang sedang ditunggu adalah nama penyusun,
                # jawaban nama polos harus diterima tanpa wajib menulis `Nama:`.
                self.author_name = raw[:500]

        if self.assignment_type == "kelompok" and not self.group_members:
            match = re.search(r"\b(?:anggota(?:\s+kelompok)?|nama\s+anggota)\s*[:=]?\s*(.+)$", raw, re.IGNORECASE)
            if match:
                self.group_members = match.group(1).strip()[:500]

    def question_text(self) -> str:
        missing: list[str] = []
        if not self.assignment_type:
            missing.append("Tugas individu atau kelompok")
        elif self.assignment_type == "individu":
            if not self.author_name:
                missing.append("Nama penyusun")
        elif self.assignment_type == "kelompok":
            if not self.group_members:
                missing.append("Nama anggota kelompok")

        if not missing:
            return (
                "Data utama untuk cover sudah cukup.\n\n"
                "Data opsional tetap boleh ditambahkan atau diubah kapan saja sebelum file final dibuat, "
                "misalnya nama sekolah/kampus, nama/nomor kelompok, tahun ajaran, dan nama guru/dosen."
            )

        lines = ["Sebelum saya buat isi makalah, saya masih perlu data untuk cover:"]
        for index, item in enumerate(missing, start=1):
            lines.append(f"{index}. **{item}**")
        lines.append(
            "\nOpsional dan boleh ditambahkan belakangan: nama sekolah/kampus, nama/nomor kelompok, "
            "tahun ajaran, dan nama guru/dosen."
        )
        return "\n".join(lines)

    def structured_text(self) -> str:
        institution = self.institution_name or "Tidak dicantumkan"
        group_name = self.group_name or "Tidak dicantumkan"
        return (
            f"Sekolah/kampus: {institution}\n"
            f"Jenis tugas: {self.assignment_type}\n"
            f"Nama penyusun: {self.author_name}\n"
            f"Kelompok: {group_name}\n"
            f"Anggota: {self.group_members}\n"
            f"Tahun ajaran: {self.academic_year or 'Tidak dicantumkan'}\n"
            f"Guru/dosen: {self.teacher_name or 'Tidak dicantumkan'}"
        )
