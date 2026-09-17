"""Generator isi makalah terstruktur untuk Document Agent.

Model hanya mendapat data makalah, kerangka yang sudah disetujui, policy format,
dan Source Registry. Sumber direferensikan dengan marker [[R1]], [[R2]], dst.;
format catatan kaki dan daftar pustaka tetap dilakukan CitationEngine secara
deterministik.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

from app.document_engine import DocumentSection
from app.document_policy import load_document_format_policy
from app.nara_context import load_nara_identity
from app.providers.base import ModelProvider
from app.source_registry import RegisteredSource


DRAFT_PROMPT = """Kamu adalah penulis Makalah Taqi DocuTech.
Buat isi makalah berdasarkan data dan kerangka yang SUDAH DISETUJUI.

ATURAN SUMBER WAJIB:
- Hanya gunakan sumber dari SOURCE REGISTRY yang diberikan.
- Jangan pernah membuat nama penulis, judul, DOI, data, atau sumber baru.
- Saat sebuah pernyataan memang didukung sumber, letakkan marker seperti [[R1]] tepat setelah kalimat/klaim.
- Jangan menulis footnote manual dan jangan membuat daftar pustaka; engine lokal yang akan mengerjakannya.
- Jika abstrak sumber tersedia, gunakan hanya informasi yang memang didukung abstrak tersebut.
- Jika abstrak tidak tersedia, jangan mengarang rincian hasil penelitian dari sumber itu; gunakan metadata hanya secara konservatif.
- Jangan memberi marker sumber pada opini umum/kalimat transisi bila tidak diperlukan.

ATURAN DOKUMEN:
- Bahasa Indonesia formal dan mudah dipahami sesuai jenjang.
- Instruksi guru/dosen/sekolah/kampus lebih tinggi prioritasnya daripada format default.
- WAJIB mengikuti DOCUMENT FORMAT POLICY yang diberikan.
- Pertahankan struktur heading dari kerangka yang disetujui.
- Default Makalah Taqi AI adalah BAB I -> A. -> 1. -> a.
- Jangan mengganti default Makalah menjadi BAB I -> 1.1 -> 1.1.1 atau I. -> A. -> 1. -> a. kecuali kerangka/pedoman resmi memang meminta begitu.
- Tingkat 1. dan a. hanya digunakan jika benar-benar diperlukan; jangan dipaksakan untuk dokumen pendek.
- Bullet hanya boleh berada di dalam isi bila memang berupa daftar, bukan sebagai pengganti heading.
- Hormati target jumlah halaman setelah cover. Cover tidak dihitung kecuali pelanggan secara khusus berkata lain.
- Sertakan Kata Pengantar singkat.
- Jangan membuat Cover, Daftar Isi, atau Daftar Pustaka di JSON; engine lokal membuatnya.
- Jangan menulis Markdown.

KELUARKAN JSON VALID SAJA dengan bentuk persis:
{
  "preface": ["paragraf 1", "paragraf 2"],
  "sections": [
    {"title": "BAB I PENDAHULUAN", "level": 1, "paragraphs": []},
    {"title": "A. Latar Belakang", "level": 2, "paragraphs": ["..."]},
    {"title": "1. Pokok Bahasan", "level": 3, "paragraphs": ["..."]},
    {"title": "a. Rincian", "level": 4, "paragraphs": ["..."]}
  ]
}
"""


@dataclass(frozen=True)
class DraftGenerationResult:
    status: str
    preface: tuple[str, ...] = ()
    sections: tuple[DocumentSection, ...] = ()
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    warning: str = ""


class DraftGenerator:
    def __init__(self, provider: ModelProvider):
        self.provider = provider

    @staticmethod
    def _source_block(source: RegisteredSource) -> str:
        authors = ", ".join(source.authors) or "Penulis tidak tercantum"
        metadata = [
            f"ID: {source.ref_id}",
            f"Judul: {source.title}",
            f"Penulis: {authors}",
            f"Tahun: {source.year or 'tidak diketahui'}",
            f"Jurnal/Penerbit: {source.venue or source.publisher or 'tidak diketahui'}",
        ]
        if source.volume:
            metadata.append(f"Volume: {source.volume}")
        if source.issue:
            metadata.append(f"Nomor: {source.issue}")
        if source.pages:
            metadata.append(f"Halaman artikel: {source.pages}")
        if source.doi:
            metadata.append(f"DOI: {source.doi}")
        if source.abstract:
            metadata.append("Abstrak: " + re.sub(r"\s+", " ", source.abstract).strip()[:3500])
        else:
            metadata.append("Abstrak: TIDAK TERSEDIA — jangan mengarang isi/temuan spesifik sumber ini.")
        return "\n".join(metadata)

    @staticmethod
    def _length_guidance(requirements_text: str) -> str:
        """Target halaman default dihitung setelah cover; cover tidak termasuk."""
        text = requirements_text or ""
        word_match = re.search(r"(?:Jumlah halaman/kata|Target panjang):\s*(\d+)\s*kata", text, re.IGNORECASE)
        if word_match:
            return f"Target panjang eksplisit: sekitar {word_match.group(1)} kata."

        page_match = re.search(r"(?:Jumlah halaman/kata|Target panjang):\s*(\d+)\s*halaman", text, re.IGNORECASE)
        if not page_match:
            return "Ikuti target panjang pada data makalah secara proporsional."

        pages = max(1, int(page_match.group(1)))
        if pages <= 8:
            return (
                f"Target dokumen sekitar {pages} halaman SETELAH COVER; cover tidak dihitung. "
                "Kata Pengantar, Daftar Isi, isi utama, dan Daftar Pustaka ikut dalam target. "
                "Gunakan struktur ringkas dan jangan membuat tingkat heading yang tidak perlu."
            )
        if pages <= 12:
            return (
                f"Target dokumen sekitar {pages} halaman SETELAH COVER; cover tidak dihitung. "
                "Kata Pengantar, Daftar Isi, isi utama, dan Daftar Pustaka ikut dalam target."
            )
        return f"Target dokumen sekitar {pages} halaman SETELAH COVER; jaga pembagian panjang antarbagian tetap proporsional."

    @classmethod
    def _messages(
        cls,
        requirements_text: str,
        cover_text: str,
        outline_text: str,
        sources: list[RegisteredSource],
    ) -> list[dict[str, str]]:
        source_text = "\n\n---\n\n".join(cls._source_block(source) for source in sources)
        user = (
            "DATA MAKALAH:\n" + requirements_text +
            "\n\nPANDUAN PANJANG:\n" + cls._length_guidance(requirements_text) +
            "\n\nDATA COVER (untuk konteks saja):\n" + cover_text +
            "\n\nKERANGKA DISETUJUI:\n" + outline_text[:12000] +
            "\n\nSOURCE REGISTRY:\n" + source_text[:30000]
        )
        system = load_nara_identity() + "\n\n" + DRAFT_PROMPT + "\n\nDOCUMENT FORMAT POLICY WAJIB:\n" + load_document_format_policy()
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    @staticmethod
    def _extract_json(text: str) -> dict:
        clean = (text or "").strip()
        clean = re.sub(r"^```(?:json)?\s*", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\s*```$", "", clean)
        start = clean.find("{")
        end = clean.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Model tidak mengembalikan JSON isi makalah yang valid.")
        payload = json.loads(clean[start:end + 1])
        if not isinstance(payload, dict):
            raise ValueError("JSON isi makalah harus berupa object.")
        return payload

    @staticmethod
    def _validate(payload: dict, allowed_refs: set[str]) -> tuple[tuple[str, ...], tuple[DocumentSection, ...]]:
        preface_raw = payload.get("preface") or []
        sections_raw = payload.get("sections") or []
        if not isinstance(preface_raw, list) or not isinstance(sections_raw, list):
            raise ValueError("Struktur JSON isi makalah tidak sesuai.")
        preface = tuple(str(item).strip() for item in preface_raw if str(item).strip())[:5]
        if any("[[" in item for item in preface):
            raise ValueError("Marker sumber hanya boleh berada pada isi makalah.")
        sections: list[DocumentSection] = []
        used_markers: set[str] = set()
        marker_pattern = re.compile(r"\[\[(R\d+)\]\]", re.IGNORECASE)
        for item in sections_raw:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            if "[[" in title:
                raise ValueError("Marker sumber tidak boleh berada pada judul bagian.")
            if not title or re.sub(r"^[IVXLCDM]+\.\s*", "", title, flags=re.IGNORECASE).strip().casefold() == "daftar pustaka":
                continue
            try:
                level = max(1, min(4, int(item.get("level") or 1)))
            except (TypeError, ValueError):
                level = 1
            paragraphs_raw = item.get("paragraphs") or []
            if not isinstance(paragraphs_raw, list):
                paragraphs_raw = []
            paragraphs: list[str] = []
            for paragraph in paragraphs_raw:
                value = str(paragraph).strip()
                if not value:
                    continue
                for match in marker_pattern.finditer(value):
                    used_markers.add(match.group(1).upper())
                if "[[" in marker_pattern.sub("", value) or "]]" in marker_pattern.sub("", value):
                    raise ValueError("Marker sumber tidak valid.")
                paragraphs.append(value)
            sections.append(DocumentSection(title, tuple(paragraphs), level))
        unknown = sorted(used_markers - allowed_refs)
        if unknown:
            raise ValueError("Isi makalah memakai marker sumber yang tidak terdaftar: " + ", ".join(unknown))
        if not sections:
            raise ValueError("Model tidak menghasilkan bagian makalah.")
        if not used_markers:
            raise ValueError("Isi makalah belum memiliki sitasi sumber yang terdaftar.")
        return preface, tuple(sections)

    def generate(
        self,
        requirements_text: str,
        cover_text: str,
        outline_text: str,
        sources: list[RegisteredSource],
    ) -> DraftGenerationResult:
        if not self.provider or not self.provider.configured:
            return DraftGenerationResult("belum_dikonfigurasi", warning="Provider AI untuk isi makalah belum dikonfigurasi.")
        if not sources:
            return DraftGenerationResult("membutuhkan_sumber", warning="Source Registry masih kosong.")
        max_tokens = int(os.environ.get("DOCUMENT_DRAFT_MAX_TOKENS", "6000") or 6000)
        max_tokens = max(1200, min(max_tokens, 8000))
        reply = self.provider.generate(
            self._messages(requirements_text, cover_text, outline_text, sources),
            max_tokens=max_tokens,
            temperature=0.25,
            timeout=120,
        )
        if reply.status != "berhasil":
            return DraftGenerationResult(
                reply.status,
                model=reply.model,
                input_tokens=reply.input_tokens,
                output_tokens=reply.output_tokens,
                warning=reply.text,
            )
        try:
            payload = self._extract_json(reply.text)
            preface, sections = self._validate(payload, {source.ref_id.upper() for source in sources})
        except (ValueError, json.JSONDecodeError) as exc:
            return DraftGenerationResult(
                "gagal",
                model=reply.model,
                input_tokens=reply.input_tokens,
                output_tokens=reply.output_tokens,
                warning=str(exc),
            )
        return DraftGenerationResult(
            "berhasil",
            preface=preface,
            sections=sections,
            model=reply.model,
            input_tokens=reply.input_tokens,
            output_tokens=reply.output_tokens,
        )
