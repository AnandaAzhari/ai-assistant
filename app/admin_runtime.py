"""Shared services for the Web Admin and Telegram entrypoints."""

import os

from app.document_agent import DocumentAgent
from app.document_engine import DocumentEngine
from app.document_preferences import DocumentPreferenceStore
from app.document_session import DocumentSessionStore
from app.finance import FinanceService
from app.google_sheets_sync import GoogleSheetsSync
from app.lead import LeadAgent
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
    )
