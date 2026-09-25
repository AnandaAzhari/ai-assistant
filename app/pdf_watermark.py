"""PDF Watermark — tandai PDF pratinjau makalah dengan watermark "belum lunas"
sebelum pelanggan membayar penuh.

Bagian dari alur proteksi pembayaran (lihat `app/payment_gate.py` untuk penyimpanan
status lunas/pending release, dan `app/lead.py` -> `_continue_customer_document` untuk
titik pemakaiannya): begitu makalah selesai dibuat, pelanggan HANYA menerima PDF
pratinjau ber-watermark dari modul ini dulu — DOCX dan PDF bersih (tanpa watermark)
ditahan sampai admin menandai order itu lunas lewat `/lunas` (Telegram), baru dikirim
otomatis lewat `PaymentGateStore`.

Prinsip jujur yang sama dengan `app/pdf_compressor.py`: modul ini TIDAK PERNAH diam-
diam membiarkan file tanpa watermark dianggap "berhasil". Kalau watermark gagal
dibuat atau library-nya belum terpasang, pemanggil WAJIB mengecek `status`/`available`
dan tidak boleh mengirim file mentah sebagai gantinya — supaya proteksi "PDF bersih
baru boleh keluar setelah lunas" tidak pernah bocor karena kegagalan diam-diam.

Memakai `reportlab` (membuat lapisan teks watermark) + `pypdf` (menimpakan lapisan
itu ke setiap halaman PDF asli) — murni Python, tidak perlu Ghostscript/LibreOffice
tambahan seperti dua modul lain di paket ini. Install: `pip install reportlab pypdf`.
"""

from __future__ import annotations

import io
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

try:
    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas

    _LIBS_AVAILABLE = True
except ImportError:  # reportlab/pypdf belum terpasang di server ini
    _LIBS_AVAILABLE = False


DEFAULT_WATERMARK_TEXT = "CONTOH — BELUM LUNAS — Taqi Desk"


@dataclass(frozen=True)
class WatermarkResult:
    status: str  # "berhasil" | "gagal"
    output_path: str
    warning: str = ""


def _build_overlay_bytes(width: float, height: float, text: str) -> bytes:
    """Bikin satu halaman lapisan watermark ukuran `width`x`height` (satuan poin
    PDF, sama seperti mediabox halaman aslinya), teks diulang berjajar secara
    diagonal supaya menutup seluruh halaman — bukan cuma satu cap di tengah yang
    gampang hilang kalau di-crop sebagian."""
    buffer = io.BytesIO()
    pdf_canvas = canvas.Canvas(buffer, pagesize=(width, height))
    pdf_canvas.setFillColorRGB(0.5, 0.5, 0.5)
    pdf_canvas.setFillAlpha(0.35)
    pdf_canvas.setFont("Helvetica-Bold", 26)
    pdf_canvas.saveState()
    pdf_canvas.translate(width / 2, height / 2)
    pdf_canvas.rotate(45)
    step_y = 130
    rows = int(height / step_y) + 4
    for row in range(-rows, rows):
        pdf_canvas.drawCentredString(0, row * step_y, text)
    pdf_canvas.restoreState()
    pdf_canvas.showPage()
    pdf_canvas.save()
    return buffer.getvalue()


class PdfWatermarker:
    def __init__(self, root: str | Path = "workspace/pdf_watermark"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls) -> "PdfWatermarker":
        root = os.environ.get("PDF_WATERMARK_WORKSPACE", "workspace/pdf_watermark").strip() or "workspace/pdf_watermark"
        return cls(root)

    @property
    def available(self) -> bool:
        return _LIBS_AVAILABLE

    @property
    def status_text(self) -> str:
        if self.available:
            return f"Watermark PDF siap (reportlab + pypdf ditemukan). Workspace: {self.root}."
        return (
            "Watermark PDF belum bisa dijalankan: library `reportlab`/`pypdf` belum terpasang "
            "di server ini. Install dengan `pip install reportlab pypdf`, lalu coba lagi."
        )

    def add_preview_watermark(
        self, source_path: str | Path, *, text: str = DEFAULT_WATERMARK_TEXT, order_id: str = "",
    ) -> WatermarkResult:
        """Hasilkan salinan `source_path` (harus PDF) dengan watermark `text` di
        setiap halaman. File asli TIDAK diubah — hasil watermark disimpan sebagai
        file baru di `self.root`."""
        source = Path(source_path)
        if not source.is_file():
            return WatermarkResult("gagal", "", f"File sumber tidak ditemukan: {source_path}")
        if source.suffix.casefold() != ".pdf":
            return WatermarkResult("gagal", "", "File yang diberi watermark harus PDF.")
        if not self.available:
            return WatermarkResult(
                "gagal", "", "Library watermark (`reportlab`/`pypdf`) belum terpasang di server ini.",
            )

        # Nama file pratinjau ikut judul makalah (nama file `source_path` sudah
        # di-slugify oleh DocumentEngine._safe_name saat file final dibuat, lihat
        # app/document_engine.py) supaya pelanggan melihat nama yang rapi, bukan
        # order_id mentah. Suffix acak pendek tetap ditambahkan supaya tidak ada
        # tabrakan nama file kalau dua order kebetulan berjudul sama; `order_id`
        # dipakai sebagai fallback kalau nama sumbernya kosong/generik.
        title_part = source.stem or order_id or "makalah"
        output_path = self.root / f"{title_part}-{uuid.uuid4().hex[:6]}-preview.pdf"

        try:
            reader = PdfReader(str(source))
            writer = PdfWriter()
            for page in reader.pages:
                box = page.mediabox
                overlay_bytes = _build_overlay_bytes(float(box.width), float(box.height), text)
                overlay_reader = PdfReader(io.BytesIO(overlay_bytes))
                page.merge_page(overlay_reader.pages[0])
                writer.add_page(page)
            with open(output_path, "wb") as handle:
                writer.write(handle)
        except Exception as exc:  # pypdf/reportlab bisa lempar banyak jenis error untuk PDF rusak
            output_path.unlink(missing_ok=True)
            return WatermarkResult("gagal", "", f"Gagal membuat watermark: {exc}")

        if not output_path.is_file() or output_path.stat().st_size == 0:
            return WatermarkResult("gagal", "", "Watermark gagal dibuat (file hasil kosong).")
        return WatermarkResult("berhasil", str(output_path))
