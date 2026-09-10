"""Tindakan desktop terbatas untuk uji coba pertama."""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Result:
    status: str
    messages: list[str] = field(default_factory=list)
    pending_file: Path | None = None


def open_in_windows(path: Path) -> None:
    if os.name != "nt":
        raise OSError("Membuka file memerlukan komputer Windows.")
    # Tidak melewati shell atau menafsirkan path sebagai perintah.
    os.startfile(str(path), "open")


class DesktopAgent:
    DOCUMENT_TYPES = {".pdf", ".txt", ".docx", ".xlsx", ".pptx", ".png", ".jpg", ".jpeg"}

    def __init__(self, workspace: Path, opener=None):
        self.workspace = workspace.expanduser().resolve(strict=True)
        if not self.workspace.is_dir():
            raise ValueError("Folder kerja harus berupa direktori yang sudah ada.")
        self.opener = opener if opener is not None else open_in_windows

    def create_folder(self, name: str) -> Result:
        # Satu nama folder, tanpa path bertingkat atau nama khusus Windows.
        reserved = r"(?:CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\..*)?"
        if (not name or name != name.strip() or name in {".", ".."}
                or len(name) > 100 or name.endswith(".")
                or re.search(r'[<>:"/\\|?*\x00-\x1f]', name)
                or re.fullmatch(reserved, name, re.IGNORECASE)):
            return Result("gagal", ["Gunakan satu nama folder biasa (maksimal 100 karakter), tanpa pemisah path atau nama khusus Windows."])
        target = self.workspace / name
        try:
            # Jangan mengikuti symlink/junction ke lokasi lain.
            if target.resolve().parent != self.workspace:
                return Result("gagal", ["Target folder mengarah keluar dari folder kerja."])
            try:
                target.mkdir()
                message = "Folder dibuat"
            except FileExistsError:
                if not target.is_dir():
                    return Result("gagal", [f"Nama sudah dipakai oleh sebuah file: {target}"])
                message = "Folder sudah ada; isi dipertahankan"
            if not target.is_dir():
                return Result("gagal", ["Keberadaan folder belum dapat diverifikasi."])
            return Result("berhasil", [f"{message}: {target}", "Verifikasi: folder tersedia."])
        except (OSError, ValueError, RuntimeError) as exc:
            return Result("gagal", [f"Folder belum berhasil disiapkan: {exc}"])

    def open_file(self, raw_path: str) -> Result:
        try:
            value = raw_path.strip()
            if len(value) >= 2 and value[0] == value[-1] == '"':
                value = value[1:-1]
            if not value:
                raise ValueError("Path file belum diisi.")
            target = Path(value)
            if not target.is_absolute():
                target = self.workspace / target
            target = target.resolve(strict=True)
            if not target.is_relative_to(self.workspace):
                raise ValueError("Pilih file di dalam folder kerja yang ditampilkan.")
            if not target.is_file():
                raise ValueError("Target bukan file.")
            if target.suffix.lower() not in self.DOCUMENT_TYPES:
                raise ValueError("Jenis file belum didukung. Gunakan PDF, TXT, DOCX, XLSX, PPTX, PNG, atau JPG/JPEG.")
            self.opener(target)
            return Result("menunggu_verifikasi", [
                f"File ditemukan: {target}",
                "Permintaan membuka file dikirim ke Windows; tampilan aplikasi belum diverifikasi.",
            ], pending_file=target)
        except (OSError, ValueError, RuntimeError) as exc:
            return Result("gagal", [f"File belum berhasil dibuka: {exc}"])

    def prepare_order(self, name: str, raw_path: str) -> Result:
        folder = self.create_folder(name)
        if folder.status != "berhasil":
            return folder
        opened = self.open_file(raw_path)
        status = "sebagian_selesai" if opened.status == "gagal" else opened.status
        return Result(status, folder.messages + opened.messages, opened.pending_file)
