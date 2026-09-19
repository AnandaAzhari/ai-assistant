"""Content Studio — pembuat draft caption/naskah untuk Social Media Agent.

Modul kedua dari `docs/social_media_v1.md` ("Content Studio: Ide & Naskah").
Mengikuti pola AI-first + validasi deterministik yang sama seperti
`app/customer_intent.py`: AI HANYA dipakai untuk *menghasilkan* alternatif
caption dari brief + Brand Profile + Content Learning — hasilnya SELALU berstatus
draft yang menunggu review owner, tidak pernah langsung terpublikasi (Content
Calendar/Scheduling/Publishing di `docs/social_media_v1.md` belum diimplementasikan,
jadi secara desain tidak ada jalur auto-publish dari modul ini).

Guardrail:
- Tidak membuat draft kalau Brand Profile usaha belum lengkap — ditandai
  needs_review, bukan menebak gaya (`agents/social_media_agent.md`, "Brand
  Profile per Usaha").
- Caption yang menyebut angka rupiah ("Rp...") yang TIDAK muncul di brief owner
  dibuang sebelum draft disimpan — meniru guardrail hallucination-prevention di
  `docs/roadmap_customer_channel_v1.md` ("AI tidak pernah mengarang harga").
- Sebelum membuat draft baru, pola koreksi yang BERULANG dari Content Learning
  (`app/content_learning.py`) untuk usaha+platform yang sama disuntikkan sebagai
  instruksi tambahan ke AI (Content Learning aturan 1-4 di
  `agents/social_media_agent.md`).
- Draft yang berhasil dibuat disimpan ke Working Memory (`app/content_session.py`)
  supaya alur kerja bisa dilanjutkan/direview tanpa mengulang dari nol.
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass

from app.brand_profile import BrandProfile, BrandProfileStore
from app.content_learning import ContentLearningStore, FeedbackPattern
from app.content_session import ContentSessionStore
from app.interaction_log import InteractionLogStore
from app.providers.base import ModelProvider

DEFAULT_ALTERNATIVES = 3
MAX_ALTERNATIVES = 5

SYSTEM_PROMPT_TEMPLATE = """Kamu adalah asisten penulis caption media sosial untuk usaha "{business}".

PROFIL BRAND (WAJIB DIIKUTI, jangan menebak di luar ini):
- Deskripsi usaha: {description}
- Tone of voice: {tone_of_voice}
- Target audiens: {target_audience}
- Larangan tema/kata (JANGAN DILANGGAR): {forbidden_themes}
{examples_block}
{learning_block}
Tugasmu: buat {n} alternatif caption ASLI untuk platform {platform}, berdasarkan brief owner
di bawah. Jangan menyalin contoh caption favorit kata demi kata, cukup jadikan gaya referensi.

JANGAN menyebutkan harga, nominal rupiah, promo, atau diskon KECUALI angka tersebut memang
disebutkan persis di brief owner. Kalau brief tidak menyebut harga, jangan mengarang harga
sama sekali.

Balas HANYA JSON tanpa markdown, dengan schema persis:
{{"captions": ["caption 1", "caption 2", ...]}}
"""


@dataclass(frozen=True)
class ContentDraftResult:
    status: str
    business: str = ""
    platform: str = ""
    content_id: str = ""
    scope: str = ""
    captions: tuple[str, ...] = ()
    note: str = ""


def _format_examples(examples: tuple[str, ...]) -> str:
    if not examples:
        return ""
    bullets = "\n".join(f"  - {caption}" for caption in examples[:3])
    return f"- Contoh caption favorit owner (gaya referensi, JANGAN disalin persis):\n{bullets}\n"


def _format_learning(patterns: list[FeedbackPattern]) -> str:
    if not patterns:
        return ""
    lines = []
    for pattern in patterns[:5]:
        direction = "sering DIEDIT" if pattern.feedback_type == "edited" else "sering DITOLAK"
        examples = "; ".join(pattern.examples[:2])
        detail = f" — contoh: {examples}" if examples else ""
        lines.append(f"  - Aspek '{pattern.aspect}' {direction} owner ({pattern.occurrences}x){detail}")
    return "- Pola dari draft-draft sebelumnya usaha ini (perhatikan, jangan diulang):\n" + "\n".join(lines) + "\n"


def _extract_price_digit_sets(text: str) -> set[str]:
    return {re.sub(r"\D", "", match) for match in re.findall(r"Rp\s?[\d.,]+", text or "", flags=re.I)}


def _parse_json_object(text: str) -> dict:
    clean = re.sub(r"^```(?:json)?\s*", "", (text or "").strip(), flags=re.I)
    clean = re.sub(r"\s*```$", "", clean)
    payload = json.loads(clean)
    if not isinstance(payload, dict):
        raise ValueError("Respons AI harus berupa object JSON.")
    return payload


class ContentStudio:
    def __init__(
        self,
        provider: ModelProvider | None,
        *,
        brand_profiles: BrandProfileStore,
        content_learning: ContentLearningStore | None = None,
        content_session: ContentSessionStore | None = None,
        interaction_log: InteractionLogStore | None = None,
    ):
        self.provider = provider
        self.brand_profiles = brand_profiles
        self.content_learning = content_learning
        self.content_session = content_session
        # Fase 5 (Evaluasi & Observability, docs/roadmap_customer_channel_v1.md): catat
        # setiap draft yang dihasilkan AI supaya bisa ditinjau berkala lewat
        # /eval_sample di Telegram Admin (app/lead.py). Opsional, default nonaktif.
        self.interaction_log = interaction_log

    @property
    def configured(self) -> bool:
        return bool(self.provider and self.provider.configured)

    def _build_prompt(self, profile: BrandProfile, platform: str, n: int, patterns: list[FeedbackPattern]) -> str:
        return SYSTEM_PROMPT_TEMPLATE.format(
            business=profile.business,
            description=profile.description or "-",
            tone_of_voice=profile.tone_of_voice,
            target_audience=profile.target_audience or "-",
            forbidden_themes=profile.forbidden_themes,
            n=n,
            platform=platform,
            examples_block=_format_examples(profile.example_captions),
            learning_block=_format_learning(patterns),
        )

    def generate_draft(
        self,
        business: str,
        platform: str,
        brief: str,
        *,
        content_id: str = "",
        n_alternatives: int = DEFAULT_ALTERNATIVES,
    ) -> ContentDraftResult:
        business = (business or "").strip()
        platform = (platform or "").strip()
        brief = (brief or "").strip()
        if not business or not platform:
            return ContentDraftResult("format_salah", note="Usaha dan platform wajib diisi.")
        if not brief:
            return ContentDraftResult("format_salah", note="Brief tidak boleh kosong.")
        if not self.configured:
            return ContentDraftResult("belum_dikonfigurasi", business=business, platform=platform)

        profile = self.brand_profiles.load(business)
        if profile is None or not self.brand_profiles.is_ready(business):
            return ContentDraftResult(
                "needs_review",
                business=business,
                platform=platform,
                note=(
                    f"Brand profile untuk '{business}' belum lengkap (tone of voice/larangan "
                    "tema masih kosong atau placeholder) — lengkapi dulu di brand_profiles/ "
                    "sebelum Social Media Agent membuat draft."
                ),
            )

        patterns: list[FeedbackPattern] = []
        if self.content_learning is not None:
            patterns = self.content_learning.recurring_feedback_patterns(business, platform)

        n = max(1, min(int(n_alternatives), MAX_ALTERNATIVES))
        prompt = self._build_prompt(profile, platform, n, patterns)
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "BRIEF OWNER:\n" + brief[:2000]},
        ]
        reply = self.provider.generate(messages, max_tokens=1200, temperature=0.7, timeout=45)
        if reply.status != "berhasil":
            return ContentDraftResult(reply.status, business=business, platform=platform)

        try:
            payload = _parse_json_object(reply.text)
            raw_captions = payload.get("captions")
            if not isinstance(raw_captions, list) or not raw_captions:
                raise ValueError("captions kosong/tidak valid.")
            captions = [str(item).strip() for item in raw_captions if str(item or "").strip()]
            if not captions:
                raise ValueError("Semua caption kosong.")
        except (ValueError, TypeError, json.JSONDecodeError):
            return ContentDraftResult(
                "gagal", business=business, platform=platform,
                note="Keluaran AI tidak valid (bukan JSON caption yang dikenali). Coba lagi.",
            )

        brief_numbers = _extract_price_digit_sets(brief)
        safe_captions = []
        dropped = 0
        for caption in captions:
            caption_numbers = _extract_price_digit_sets(caption)
            if caption_numbers - brief_numbers:
                dropped += 1
                continue
            safe_captions.append(caption)

        if not safe_captions:
            return ContentDraftResult(
                "needs_review", business=business, platform=platform,
                note=(
                    "Semua alternatif caption menyebut harga yang tidak ada di brief — dibuang "
                    "demi mencegah harga karangan. Sebutkan harga secara eksplisit di brief bila "
                    "memang perlu, lalu coba lagi."
                ),
            )

        resolved_content_id = content_id.strip() or uuid.uuid4().hex[:12]
        scope = ""
        if self.content_session is not None:
            scope = ContentSessionStore.build_scope(business, platform, resolved_content_id)
            self.content_session.save(scope, {
                "version": 1,
                "stage": "draft",
                "brief": brief,
                "captions": safe_captions,
                "business": profile.business,
                "platform": platform,
            })

        note = f"{dropped} alternatif dibuang karena menyebut harga yang tidak ada di brief." if dropped else ""
        if self.interaction_log is not None:
            self.interaction_log.log(
                "kirana", f"{business}:{platform}", "content_studio", brief,
                "\n".join(f"{i}. {c}" for i, c in enumerate(safe_captions, start=1)),
                status="draft", model=reply.model,
            )
        return ContentDraftResult(
            "draft", business=business, platform=platform, content_id=resolved_content_id,
            scope=scope, captions=tuple(safe_captions), note=note,
        )
