"""Shared services for the Web Admin and Telegram entrypoints."""

import os

from app.brand_profile import BrandProfileStore
from app.content_learning import ContentLearningStore
from app.content_session import ContentSessionStore
from app.content_studio import ContentStudio
from app.customer_book import CustomerBookStore
from app.document_agent import DocumentAgent
from app.document_engine import DocumentEngine
from app.document_preferences import DocumentPreferenceStore
from app.document_session import DocumentSessionStore
from app.dp_policy import DpPolicyStore
from app.finance import FinanceService
from app.finance_query import FinanceQueryInterpreter
from app.google_sheets_sync import GoogleSheetsSync
from app.interaction_log import InteractionLogStore
from app.kill_switch import KillSwitch
from app.lead import LeadAgent
from app.order_status import OrderStatusStore
from app.payment_gate import PaymentGateStore
from app.pdf_compressor import PdfCompressor
from app.pdf_watermark import PdfWatermarker
from app.price_list import PriceListStore
from app.pricing import PricingConfigStore
from app.providers.deepseek import DeepSeekProvider
from app.source_registry import SourceRegistry


def create_admin_lead(*, channel: str = "web", document_scope: str | None = None) -> LeadAgent:
    db_path = os.environ.get("DATABASE_PATH", "data/assistant.db").strip() or "data/assistant.db"
    document = DocumentAgent(
        DeepSeekProvider.from_env(), engine=DocumentEngine.from_env(),
        registry=SourceRegistry(db_path), preference_store=DocumentPreferenceStore(db_path),
        source_scope=document_scope, session_store=DocumentSessionStore(db_path),
    )

    def topic_document_factory(topic_key: str) -> DocumentAgent:
        # DocumentAgent TERPISAH per topik Telegram (mis. topik "Nara" di grup admin
        # "Taqi AI — Ruang Admin") — dipakai LeadAgent lewat _topic_document_agent
        # (app/lead.py) supaya sesi susun makalah di topik itu tidak pernah bercampur
        # dengan chat pribadi atau topik lain. Scope dibangun dari document_scope
        # dasar runtime ini + topic_key, tetap unik per (bot, admin, topik) dan
        # tersimpan di database yang sama (DocumentSessionStore/SourceRegistry).
        base_scope = document_scope or f"DOCSRC-{channel.upper()}"
        return DocumentAgent(
            DeepSeekProvider.from_env(), engine=DocumentEngine.from_env(),
            registry=SourceRegistry(db_path), preference_store=DocumentPreferenceStore(db_path),
            source_scope=f"{base_scope}-TOPIC-{topic_key}", session_store=DocumentSessionStore(db_path),
        )

    return LeadAgent(
        # Laras (Finance Agent) sekarang bisa menjawab pertanyaan keuangan bebas lewat AI
        # (mis. "pemasukan bulan lalu Risol Mamqi berapa?"), bukan cuma command tetap
        # (/hari_ini dkk) — lihat app/finance_query.py. AI HANYA mengklasifikasikan
        # pertanyaan; angka jawaban tetap dihitung FinanceService dari database asli,
        # tidak pernah dikarang model, sama seperti agent lain.
        finance=FinanceService(db_path, query_interpreter=FinanceQueryInterpreter(DeepSeekProvider.from_env())),
        sheets_sync=GoogleSheetsSync.from_env(db_path),
        document=document, admin_channel=channel,
        # Database yang sama dengan yang dipakai whatsapp_main.py, supaya kill switch
        # yang diaktifkan admin lewat Telegram/Web Admin langsung berlaku di runtime
        # WhatsApp yang terpisah (proses berbeda, tapi status disimpan di SQLite yang
        # sama — lihat app/kill_switch.py).
        kill_switch=KillSwitch(db_path),
        # Admin mengisi harga/status order dari sini (Telegram/Web Admin); WhatsApp
        # membaca dari database yang sama untuk menjawab pelanggan tanpa mengarang
        # (lihat app/price_list.py, app/order_status.py).
        price_list=PriceListStore(db_path),
        order_status=OrderStatusStore(db_path),
        # Content Studio (Social Media Agent) memakai provider AI yang sama dengan
        # Document Agent (satu konfigurasi DeepSeek untuk seluruh runtime admin), dan
        # database yang sama untuk Long-Term Feedback Memory/Working Memory-nya
        # (lihat app/content_learning.py, app/content_session.py).
        content_studio=ContentStudio(
            DeepSeekProvider.from_env(), brand_profiles=BrandProfileStore("brand_profiles"),
            content_learning=ContentLearningStore(db_path), content_session=ContentSessionStore(db_path),
            interaction_log=InteractionLogStore(db_path),
        ),
        # Fase 5 (Evaluasi & Observability): setiap interaksi pelanggan (Taqi/Nara) dan
        # draft Kirana tersimpan ke database yang sama, ditinjau berkala lewat
        # /eval_sample, /eval_tandai, /eval_status (lihat app/interaction_log.py).
        interaction_log=InteractionLogStore(db_path),
        # Profil pelanggan dan riwayat order terstruktur, diisi/dilihat admin lewat
        # /pelanggan_nama, /pelanggan_catat, /pelanggan_riwayat, /pelanggan_ringkasan
        # (lihat app/customer_book.py). Database yang sama dengan whatsapp_main.py,
        # supaya kontak pelanggan yang tercatat otomatis dari WhatsApp langsung
        # terlihat di sini juga.
        customer_book=CustomerBookStore(db_path),
        # Dipakai admin lewat /kompres_pdf_status untuk cek apakah Ghostscript sudah
        # terpasang di server ini (lihat app/pdf_compressor.py). Instance terpisah
        # dari whatsapp_main.py (proses berbeda), tapi cukup untuk cek status karena
        # tidak menyimpan state apa pun selain lokasi workspace.
        pdf_compressor=PdfCompressor.from_env(),
        # Payment Gate (app/payment_gate.py, app/pdf_watermark.py): admin menandai
        # order lunas lewat /lunas dan mengisi info QR/DANA/rekening lewat
        # /set_pembayaran di sini. Database yang sama dengan whatsapp_main.py
        # (proses berbeda), supaya status lunas yang admin catat di Telegram/Web
        # Admin langsung terlihat oleh runtime WhatsApp yang terpisah begitu
        # pelanggan itu kirim pesan berikutnya (lihat docstring app/payment_gate.py).
        payment_gate=PaymentGateStore(db_path),
        pdf_watermarker=PdfWatermarker.from_env(),
        # Kalkulator harga (/paket_set, /tarif_set, /hitung_harga, /hitung_rapikan)
        # dan kebijakan DP wajib/opsional (/dp_wajib, /dp_opsional, /dp_status) —
        # lihat app/pricing.py dan app/dp_policy.py. Database yang sama dengan
        # yang lain di runtime ini, supaya angka harga & status DP yang admin
        # ubah lewat Telegram/Web Admin langsung konsisten di mana pun dibaca.
        pricing=PricingConfigStore(db_path),
        dp_policy=DpPolicyStore(db_path),
        topic_document_factory=topic_document_factory,
    )
