"""Pengumpul data cover makalah lokal tanpa token AI.

Data cover boleh dilengkapi atau diubah berulang selama sesi/order masih aktif.
Parser lokal menangani bahasa pelanggan yang umum, jawaban tidak berurutan, dan
jawaban polos yang aman dipetakan dari konteks pertanyaan aktif.
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
        return not bool(self.next_required_field())

    def next_required_field(self) -> str:
        """Field wajib berikutnya yang sedang diminta sistem.

        Field ini hanya menjadi konteks untuk jawaban polos. Pelanggan tetap boleh
        mengirim field lain lebih dulu; parser eksplisit/value-shaped tetap diproses.
        """
        if not self.assignment_type:
            return "assignment_type"
        if self.assignment_type == "individu" and not self.author_name:
            return "author_name"
        if self.assignment_type == "kelompok" and not self.group_members:
            return "group_members"
        return ""

    @staticmethod
    def _looks_like_plain_name(value: str) -> bool:
        """Deteksi nama orang sederhana tanpa label."""
        clean = re.sub(r"\s+", " ", (value or "").strip())
        if not clean or ":" in clean or "," in clean or len(clean) > 90:
            return False
        words = clean.split()
        if not 1 <= len(words) <= 7:
            return False
        blocked = {
            "lanjut", "lanjutkan", "setuju", "oke", "ok", "iya", "ya", "boleh", "skip",
            "individu", "kelompok", "sekolah", "kampus", "universitas", "instansi",
            "guru", "dosen", "tahun", "ajaran", "akademik", "tidak", "ada", "buat",
            "file", "word", "pdf", "sudah", "cukup",
        }
        lowered_words = {word.casefold().strip(".,") for word in words}
        if lowered_words & blocked:
            return False
        return all(re.fullmatch(r"[\w.'’\-]+", word, flags=re.UNICODE) for word in words)

    @classmethod
    def _looks_like_member_list(cls, value: str) -> bool:
        clean = (value or "").strip()
        if not clean or len(clean) > 500:
            return False
        parts = [part.strip() for part in re.split(r"[,;\n]+", clean) if part.strip()]
        return bool(parts) and all(cls._looks_like_plain_name(part) for part in parts)

    @staticmethod
    def _looks_like_academic_year(value: str) -> bool:
        clean = re.sub(r"\s+", "", (value or "").strip().casefold())
        clean = re.sub(r"^(?:ta|t\.a\.?)[.:=-]?", "", clean)
        return bool(re.fullmatch(r"20\d{2}[/\-]20\d{2}", clean))

    @staticmethod
    def _looks_like_institution(value: str) -> bool:
        clean = re.sub(r"\s+", " ", (value or "").strip().casefold())
        prefixes = (
            "sd ", "sdn ", "mi ", "min ", "smp ", "smpn ", "mts ", "mtsn ",
            "sma ", "sman ", "smk ", "smkn ", "ma ", "man ", "universitas ",
            "institut ", "politeknik ", "akademi ", "sekolah tinggi ", "stai ", "uin ",
        )
        return clean.startswith(prefixes)

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

    def _update_corrections(self, raw: str) -> None:
        """Tangani koreksi eksplisit seperti `nama gurunya ... ganti menjadi ...`."""
        for source_line in raw.splitlines():
            line = re.sub(r"^\s*(?:[-*>•]\s*)?", "", source_line).strip()
            if not line:
                continue
            match = re.search(
                r"\b(?:ganti|ubah|diganti|diubah)\s+(?:menjadi|jadi|ke)\s+(.+?)\s*[.!]?$",
                line,
                re.IGNORECASE,
            )
            if not match:
                continue
            value = match.group(1)
            lowered = line.casefold()
            if any(term in lowered for term in ("sekolah", "kampus", "universitas", "instansi")):
                self._apply_optional_value("institution_name", value)
            elif "tahun ajaran" in lowered or "tahun akademik" in lowered:
                self._apply_optional_value("academic_year", value)
            elif "guru" in lowered or "dosen" in lowered:
                self._apply_optional_value("teacher_name", value)
            elif "kelompok" in lowered and "anggota" not in lowered:
                self._apply_optional_value("group_name", value)
            elif "anggota" in lowered:
                clean = self._clean_value(value)
                if clean:
                    self.group_members = clean
            elif any(term in lowered for term in ("nama penyusun", "penyusun", "nama saya", "nama siswa", "nama murid")):
                clean = self._clean_value(value)
                if clean:
                    self.author_name = clean

    def _update_natural_fields(self, raw: str) -> None:
        """Baca field berlabel secara natural walaupun urutannya acak."""
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
                r"^(?:guru|dosen)(?:nya|\s+saya)?\s+(?:adalah\s+)?(.+)$",
                r"^(.+?)\s+(?:itu\s+)?nama\s+(?:guru|dosen)(?:nya)?$",
            ),
            "group_name": (
                r"^(?:nama|nomor)\s+kelompok\s+(.+)$",
            ),
            "group_members": (
                r"^(?:anggota(?:\s+kelompok)?|nama\s+anggota)\s*(?:adalah\s+)?(.+)$",
            ),
            "author_name": (
                r"^(?:nama\s+)?(?:penyusun|siswa|murid)\s+(?:saya\s+)?(.+)$",
                r"^(?:nama\s+saya|saya\s+bernama|atas\s+nama)\s+(.+)$",
            ),
        }

        for source_line in raw.splitlines():
            line = re.sub(r"^\s*(?:[-*>•]\s*)?", "", source_line).strip()
            if not line or ":" in line:
                continue
            if re.search(r"\b(?:ganti|ubah|diganti|diubah)\b", line, re.IGNORECASE):
                continue
            for key, patterns in line_patterns.items():
                matched = False
                for pattern in patterns:
                    match = re.match(pattern, line, re.IGNORECASE)
                    if not match:
                        continue
                    value = match.group(1)
                    if key in {"institution_name", "academic_year", "teacher_name", "group_name"}:
                        self._apply_optional_value(key, value)
                    else:
                        clean = self._clean_value(value)
                        if clean:
                            setattr(self, key, clean)
                    matched = True
                    break
                if matched:
                    break

    def _apply_contextual_plain_value(self, raw: str, expected_field: str) -> str:
        """Gunakan bentuk nilai + konteks pertanyaan untuk jawaban tanpa label.

        Return string non-kosong berarti jawaban ambigu dan perlu klarifikasi lokal.
        """
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        if len(lines) != 1:
            return ""
        clean = self._clean_value(lines[0])
        if not clean or ":" in lines[0]:
            return ""

        lowered = clean.casefold()
        if lowered in {"individu", "sendiri", "tugas individu"}:
            self.assignment_type = "individu"
            return ""
        if lowered in {"kelompok", "tugas kelompok"}:
            self.assignment_type = "kelompok"
            return ""
        if self._looks_like_academic_year(clean):
            self.academic_year = clean
            return ""
        if self._looks_like_institution(clean):
            self.institution_name = clean
            return ""

        if expected_field == "author_name" and self._looks_like_plain_name(clean):
            self.author_name = clean
            return ""
        if expected_field == "teacher_name" and self._looks_like_plain_name(clean):
            self.teacher_name = clean
            return ""
        if expected_field == "group_members" and self._looks_like_member_list(clean):
            self.group_members = clean
            return ""
        if expected_field == "institution_name" and self._looks_like_institution(clean):
            self.institution_name = clean
            return ""
        if expected_field == "academic_year" and self._looks_like_academic_year(clean):
            self.academic_year = clean
            return ""

        # Nama polos tanpa konteks nama yang aktif tidak boleh ditebak. Bisa jadi
        # nama penyusun, guru/dosen, anggota kelompok, atau koreksi nilai sebelumnya.
        if self._looks_like_plain_name(clean):
            return (
                f"Saya membaca **{clean}** sebagai nama, tetapi belum aman menentukan untuk siapa. "
                "Apakah ini nama penyusun/siswa, nama guru/dosen, atau anggota kelompok?"
            )
        return ""

    def update(self, message: str, *, expected_field: str = "") -> str:
        """Perbarui data cover dan kembalikan pesan klarifikasi jika ada ambiguitas."""
        raw = (message or "").strip()
        if not raw:
            return ""

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
            "nama siswa": "author_name",
            "nama murid": "author_name",
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
            clean = self._clean_value(value)
            if clean:
                setattr(self, key, clean)

        # Koreksi terbaru menang atas nilai lama.
        self._update_corrections(raw)
        # Field eksplisit boleh dikirim dalam urutan apa pun.
        self._update_natural_fields(raw)

        lowered = raw.casefold()
        if not self.assignment_type:
            if re.search(r"\bkelompok\b", lowered):
                self.assignment_type = "kelompok"
            elif re.search(r"\b(?:individu|sendiri)\b", lowered):
                self.assignment_type = "individu"

        return self._apply_contextual_plain_value(raw, expected_field)

    def question_text(self) -> str:
        expected = self.next_required_field()
        if not expected:
            return (
                "Data utama untuk cover sudah cukup.\n\n"
                "Data opsional tetap boleh ditambahkan atau diubah kapan saja sebelum file final dibuat, "
                "misalnya nama sekolah/kampus, nama/nomor kelompok, tahun ajaran, dan nama guru/dosen. "
                "Data tidak harus dikirim berurutan."
            )

        if expected == "assignment_type":
            question = "Tugas ini **individu atau kelompok**?"
            hint = "Cukup jawab `individu` atau `kelompok`."
        elif expected == "author_name":
            question = "Siapa **nama penyusun/siswa** yang akan dicantumkan di cover?"
            hint = "Cukup balas namanya saja, misalnya `Ananda Azhari Batubara`."
        else:
            question = "Siapa saja **anggota kelompok** yang akan dicantumkan di cover?"
            hint = "Boleh kirim nama satu per satu atau beberapa nama dipisahkan koma."

        return (
            "Sebelum saya buat isi makalah, saya masih perlu satu data wajib:\n"
            f"**{question}**\n\n{hint}\n\n"
            "Data cover lain boleh dikirim lebih dulu atau belakangan dan tidak harus berurutan, "
            "misalnya sekolah/kampus, tahun ajaran, atau nama guru/dosen."
        )

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
