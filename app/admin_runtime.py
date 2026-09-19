"""Shared services for the Web Admin and Telegram entrypoints."""

import os

from app.brand_profile import BrandProfileStore
from app.content_learning import ContentLearningStore
from app.content_session import ContentSessionStore
from app.content_studio import ContentStudio
from app.document_agent import DocumentAgent
from app.document_engine import DocumentEngine
from app.document_preferences import DocumentPreferenceStore
from app.document_session import DocumentSessionStore
from app.finance import FinanceService
from app.google_sheets_sync import GoogleSheetsSync
from app.kill_switch import KillSwitch
from app.lead import LeadAgent
from app.order_status import OrderStatusStore
from app.price_list import PriceListStore
from app.providers.deepseek import DeepSeekProvider
from app.source_registry import SourceRegistry


def create_admin_lead(*, channel: str = "web", document_scope: str | None = None) -> LeadAgent:
    db_path = os.environ.get("DATABASE_PATH", "data/assistant.db").strip() or "data/assistant.db"
    document = DocumentAgent(
        DeepSeekProvider.from_env(), engine=DocumentEngine.from_env(),
        registry=SourceRegistry(db_path), preference_store=DocumentPreferenceStore(db_path),
        source_scope=document_scope, session_store=DocumentSessionStore(db_path),
    )
    return LeadAgent(
        finance=FinanceService(db_path), sheets_sync=GoogleSheetsSync.from_env(db_path),
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
        ),
    )
