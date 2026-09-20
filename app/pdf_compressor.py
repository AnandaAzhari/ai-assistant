"""PDF Compressor — kompresi ukuran file PDF ke target KB yang diminta pelanggan.

Dipakai lewat permintaan pelanggan "kompres PDF jadi sekian KB" lewat WhatsApp
(lihat `app/lead.py` — `_run_pdf_compression`/`_pending_pdf_compressions`), dan bisa
juga dicek statusnya oleh admin (`/kompres_pdf_status`). Memakai Ghostscript (`gs`),
alat command-line standar untuk optimasi ukuran PDF — BUKAN LibreOffice.
`app/document_engine.py` memakai LibreOffice untuk KONVERSI DOCX->PDF (tujuan
sama sekali berbeda: mengubah format), sedangkan modul ini KOMPRESI PDF->PDF yang
sudah ada (mengecilkan ukuran file, isi tetap PDF).

Prinsip jujur (bukan menjanjikan lebih dari yang bisa dilakukan): PDF TIDAK BISA
dikompres ke ukuran BEBAS berapa pun tanpa merusak kualitas di luar titik tertentu —
ini bukan resize gambar mentah, jadi modul ini tidak berpura-pura selalu bisa tepat
sasaran. Dicoba berurutan dari preset kualitas TERTINGGI ke TERENDAH
(/prepress -> /printer -> /ebook -> /screen, urutan resmi Ghostscript "-dPDFSETTINGS"),
berhenti begitu satu preset sudah menghasilkan ukuran <= target. Kalau preset paling
agresif (/screen) MASIH di atas target, hasil preset itu (ukuran terkecil yang bisa
dicapai) tetap dikembalikan dengan `achieved=False`, supaya pemanggil (app/lead.py)
bisa menyampaikan dengan jujur ke pelanggan berapa ukuran yang benar-benar didapat,
bukan diam-diam mengirim file yang tidak sesuai permintaan tanpa penjelasan.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

# Urutan dari kualitas TERTINGGI (ukuran hasil cenderung lebih besar) ke kualitas
# TERENDAH (ukuran hasil cenderung lebih kecil) — lihat dokumentasi resmi Ghostscript
# "-dPDFSETTINGS". Dicoba berurutan supaya kualitas yang dikorbankan seminimal mungkin
# untuk mencapai target ukuran pelanggan.
_PRESETS_HIGH_TO_LOW: tuple[str, ...] = ("/prepress", "/printer", "/ebook", "/screen")

# Nama binary Ghostscript berbeda-beda per platform: "gs" di Linux/macOS,
# "gswin64c"/"gswin32c" (versi console, bukan "gswin64.exe" yang membuka jendela GUI)
# di Windows.
_GS_CANDIDATES: tuple[str, ...] = ("gs", "gswin64c", "gswin32c")


def _find_ghostscript() -> str | None:
    for candidate in _GS_CANDIDATES:
        path = shutil.which(candidate)
        if path:
            return path
    return None


@dataclass(frozen=True)
class CompressionResult:
    status: str  # "berhasil" | "gagal"
    output_path: str
    original_size_bytes: int
    compressed_size_bytes: int
    target_bytes: int
    # True kalau compressed_size_bytes <= target_bytes benar-benar tercapai; False
    # kalau ini cuma hasil terbaik yang bisa dicapai (lihat docstring modul).
    achieved: bool
    warning: str = ""


class PdfCompressor:
    def __init__(self, root: str | Path = "workspace/pdf_compressed"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls) -> "PdfCompressor":
        root = os.environ.get("PDF_COMPRESS_WORKSPACE", "workspace/pdf_compressed").strip() or "workspace/pdf_compressed"
        return cls(root)

    @property
    def available(self) -> bool:
        return _find_ghostscript() is not None

    @property
    def status_text(self) -> str:
        if self.available:
            return f"Kompresi PDF siap (Ghostscript ditemukan). Workspace: {self.root}."
        return (
            "Kompresi PDF belum bisa dijalankan: Ghostscript tidak ditemukan di server ini. "
            "Install dengan `sudo apt install ghostscript` (Ubuntu/Debian), lalu coba lagi."
        )

    def compress_to_target(self, source_path: str | Path, target_bytes: int, *, order_id: str = "") -> CompressionResult:
        """Kompres `source_path` (harus PDF) supaya ukurannya <= `target_bytes` bila
        memungkinkan. Lihat docstring modul untuk strategi preset dan kejujuran
        `achieved=False` saat target tidak tercapai."""
        source = Path(source_path)
        if not source.is_file():
            return CompressionResult("gagal", "", 0, 0, target_bytes, False, f"File sumber tidak ditemukan: {source_path}")
        original_size = source.stat().st_size
        if source.suffix.casefold() != ".pdf":
            return CompressionResult("gagal", "", original_size, 0, target_bytes, False, "File yang dikirim bukan PDF.")
        if target_bytes <= 0:
            return CompressionResult("gagal", "", original_size, 0, target_bytes, False, "Target ukuran harus lebih dari 0 KB.")

        gs_path = _find_ghostscript()
        if gs_path is None:
            return CompressionResult(
                "gagal", "", original_size, 0, target_bytes, False,
                "Ghostscript belum terpasang di server, jadi kompresi PDF belum bisa dijalankan. "
                "Admin perlu memasang Ghostscript (`sudo apt install ghostscript` di VPS Linux) dulu.",
            )

        if original_size <= target_bytes:
            # Sudah cukup kecil — tidak perlu dikompres, jujur sampaikan begitu
            # daripada tetap menjalankan Ghostscript tanpa perlu.
            return CompressionResult(
                "berhasil", str(source), original_size, original_size, target_bytes, True,
                "File yang dikirim sudah lebih kecil dari target, tidak perlu dikompres lagi.",
            )

        name_seed = order_id or uuid.uuid4().hex[:8]
        best_path: Path | None = None
        best_size = original_size

        for preset in _PRESETS_HIGH_TO_LOW:
            candidate = self.root / f"{name_seed}-{preset.strip('/')}.pdf"
            # `cwd` sementara unik per percobaan preset (mirip `_convert_to_pdf_libreoffice`
            # di app/document_engine.py) supaya beberapa kompresi yang berjalan bersamaan
            # (whatsapp_main.py memakai ThreadingHTTPServer) tidak rebutan file sementara.
            with tempfile.TemporaryDirectory(prefix="taqi_gs_") as scratch_dir:
                try:
                    subprocess.run(
                        [
                            gs_path,
                            "-sDEVICE=pdfwrite",
                            "-dCompatibilityLevel=1.4",
                            f"-dPDFSETTINGS={preset}",
                            "-dNOPAUSE", "-dBATCH", "-dQUIET", "-dSAFER",
                            f"-sOutputFile={candidate}",
                            str(source),
                        ],
                        cwd=scratch_dir,
                        capture_output=True,
                        timeout=120,
                        check=True,
                    )
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
                    print(f"Kompresi PDF preset {preset} gagal untuk {source}: {exc}", flush=True)
                    continue

            if not candidate.is_file() or candidate.stat().st_size == 0:
                continue
            size = candidate.stat().st_size

            if best_path is None or size < best_size:
                if best_path is not None:
                    best_path.unlink(missing_ok=True)
                best_path, best_size = candidate, size
            else:
                candidate.unlink(missing_ok=True)

            if best_size <= target_bytes:
                return CompressionResult("berhasil", str(best_path), original_size, best_size, target_bytes, True)

        if best_path is None:
            return CompressionResult(
                "gagal", "", original_size, 0, target_bytes, False,
                "Kompresi gagal dijalankan (Ghostscript tidak menghasilkan file). Silakan coba lagi atau hubungi admin.",
            )
        return CompressionResult(
            "berhasil", str(best_path), original_size, best_size, target_bytes, False,
            f"Target {target_bytes // 1024}KB belum tercapai; ukuran terkecil yang bisa didapat "
            f"tanpa menurunkan kualitas terlalu jauh adalah {best_size // 1024}KB.",
        )
