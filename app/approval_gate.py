"""Approval Gate — Fase 2 (`docs/roadmap_customer_channel_v1.md`).

Mengubah `policies/permissions.md` (Level 0-4) dan `policies/approval_policy.md`
(auto-send vs wajib approval) menjadi state machine nyata: setiap aksi yang mau
dijalankan agent dicek levelnya dulu, dan aksi sensitif berhenti sebagai
`pending_approval` sampai owner memutuskan — bukan lagi cuma tertulis di dokumen.

State machine:
    pending_approval -> approved
    pending_approval -> rejected
    (Level 0-2, atau Level 3 yang termasuk workflow bisnis rutin) -> auto_jalan

Prinsip fail-safe (konsisten dengan `app/trust_layer.py` dan
"Model AI tidak boleh dianggap sebagai sumber otorisasi" di `security_policy.md`):
aksi dengan action_type yang tidak dikenali TIDAK PERNAH otomatis dianggap aman.
Default-nya level 3 (butuh approval), dan naik ke level 4 kalau mengandung kata
kunci berisiko tinggi (hapus data, instalasi, transaksi keuangan, dst).

Modul ini belum mengirim pesan Telegram sungguhan — itu bagian dari Fase 3/4 saat
`app/lead.py` dan `app/telegram.py` disambungkan ke gate ini. `notification_text()`
di sini menyiapkan teks permintaan approval yang siap dikirim lewat command Telegram
Admin yang sudah ada (`/approve <id>`, `/reject <id> <alasan>`), mengikuti gaya
command yang sudah dipakai `app/lead.py`.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from sqlite3 import Connection, Row, connect as sqlite_connect

LEVEL_READ_ONLY = 0
LEVEL_LOW_RISK = 1
LEVEL_CONTROLLED_WRITE = 2
LEVEL_EXTERNAL_ACTION = 3
LEVEL_HIGH_RISK = 4

_LEVEL_LABEL = {
    LEVEL_READ_ONLY: "Level 0 — Read Only",
    LEVEL_LOW_RISK: "Level 1 — Low-Risk Action",
    LEVEL_CONTROLLED_WRITE: "Level 2 — Controlled Write",
    LEVEL_EXTERNAL_ACTION: "Level 3 — External Action",
    LEVEL_HIGH_RISK: "Level 4 — High Risk",
}

# Contoh langsung dari policies/permissions.md.
_ACTION_LEVELS: dict[str, int] = {
    # Level 0 — Read Only
    "baca_status_sistem": LEVEL_READ_ONLY,
    "baca_knowledge_base": LEVEL_READ_ONLY,
    "baca_file_diizinkan": LEVEL_READ_ONLY,
    # Level 1 — Low-Risk Action
    "buka_aplikasi": LEVEL_LOW_RISK,
    "buka_folder": LEVEL_LOW_RISK,
    "cari_file": LEVEL_LOW_RISK,
    "buat_draft_lokal": LEVEL_LOW_RISK,
    # Level 2 — Controlled Write
    "buat_dokumen_kerja": LEVEL_CONTROLLED_WRITE,
    "edit_dokumen_kerja": LEVEL_CONTROLLED_WRITE,
    "simpan_output_folder_kerja": LEVEL_CONTROLLED_WRITE,
    # Mulai/lanjutkan sesi pembuatan dokumen (makalah/KTI/skripsi) dari channel
    # pelanggan (WhatsApp dst.) lewat Document Agent — lihat app/lead.py
    # `_classify_customer_intent` dan `_continue_customer_document`.
    "buat_dokumen_pelanggan": LEVEL_CONTROLLED_WRITE,
    # Pelanggan mengirim PDF untuk dikompres (app/pdf_compressor.py) — sama seperti
    # buat_dokumen_pelanggan, mengolah file yang sudah lolos app/attachment_guard.py,
    # bukan aksi eksternal berisiko, jadi auto-jalan.
    "kompres_pdf_pelanggan": LEVEL_CONTROLLED_WRITE,
    # Level 3 — External Action, auto-send diizinkan (lihat approval_policy.md "Auto-Send yang Diizinkan")
    "kirim_salam": LEVEL_EXTERNAL_ACTION,
    "jawab_faq": LEVEL_EXTERNAL_ACTION,
    "minta_detail_order": LEVEL_EXTERNAL_ACTION,
    "konfirmasi_file_diterima": LEVEL_EXTERNAL_ACTION,
    "kirim_estimasi_harga_standar": LEVEL_EXTERNAL_ACTION,
    "kirim_status_antrean": LEVEL_EXTERNAL_ACTION,
    "kirim_pengingat_status": LEVEL_EXTERNAL_ACTION,
    "tolak_spam_sopan": LEVEL_EXTERNAL_ACTION,
    # Topic restriction (app/customer_intent.py, app/lead.py `_detect_customer_action`):
    # balasan pengalihan sopan saat pesan di luar topik layanan usaha — bukan aksi
    # berisiko, cukup auto-send rutin seperti jawab_faq/kirim_salam.
    "di_luar_topik": LEVEL_EXTERNAL_ACTION,
    # Balasan info fitur kompresi PDF (app/lead.py `_CUSTOMER_REPLY_TEXT`) — teks
    # deterministik, tidak beda risikonya dari jawab_faq.
    "info_kompres_pdf": LEVEL_EXTERNAL_ACTION,
    "ubah_status_order": LEVEL_EXTERNAL_ACTION,
    "unggah_file_ke_pelanggan": LEVEL_EXTERNAL_ACTION,
    # Level 3 — External Action, wajib approval (lihat approval_policy.md "Wajib Approval Admin")
    "diskon_khusus": LEVEL_EXTERNAL_ACTION,
    "harga_di_luar_price_list": LEVEL_EXTERNAL_ACTION,
    "janji_garansi_khusus": LEVEL_EXTERNAL_ACTION,
    "kirim_data_pribadi_ke_pihak_lain": LEVEL_EXTERNAL_ACTION,
    "balas_pesan_konflik_atau_ancaman": LEVEL_EXTERNAL_ACTION,
    "balas_komplain_berat": LEVEL_EXTERNAL_ACTION,
    # Level 4 — High Risk, selalu wajib approval admin
    # File dari pelanggan yang ditahan app/attachment_guard.py (risk HIGH/CRITICAL) —
    # lihat policies/attachment_link_security.md "HIGH dan CRITICAL tidak boleh
    # diproses otomatis" dan WhatsAppCustomerAdapter._handle_attachment_message.
    "tinjau_attachment_pelanggan": LEVEL_HIGH_RISK,
    "hapus_data_permanen": LEVEL_HIGH_RISK,
    "command_administrator": LEVEL_HIGH_RISK,
    "instal_software": LEVEL_HIGH_RISK,
    "transaksi_keuangan": LEVEL_HIGH_RISK,
    "refund_atau_kompensasi": LEVEL_HIGH_RISK,
    "eksekusi_trading": LEVEL_HIGH_RISK,
    "ubah_security_setting": LEVEL_HIGH_RISK,
}

# Aksi Level 3 yang boleh auto-jalan karena termasuk workflow bisnis rutin
# (approval_policy.md "Auto-Send yang Diizinkan"). Di luar daftar ini, Level 3
# selalu berhenti dan minta approval meski policy-nya sama-sama "External Action".
_ROUTINE_AUTO_SEND = {
    "kirim_salam", "jawab_faq", "minta_detail_order", "konfirmasi_file_diterima",
    "di_luar_topik", "info_kompres_pdf",
    "kirim_estimasi_harga_standar", "kirim_status_antrean", "kirim_pengingat_status",
    "tolak_spam_sopan", "ubah_status_order", "unggah_file_ke_pelanggan",
}

_HIGH_RISK_KEYWORDS = (
    "hapus", "delete", "instal", "install", "trading", "transfer dana",
    "password", "credential", "kredensial", "keuangan", "financial",
    "security setting", "pengaturan keamanan", "administrator",
)

_STATUS_AUTO = "auto_jalan"
_STATUS_PENDING = "pending_approval"
_STATUS_APPROVED = "approved"
_STATUS_REJECTED = "rejected"


def level_label(level: int) -> str:
    return _LEVEL_LABEL.get(level, f"Level {level}")


def _infer_level(action_type: str) -> int:
    if action_type in _ACTION_LEVELS:
        return _ACTION_LEVELS[action_type]
    normalized = action_type.replace("_", " ").casefold()
    if any(keyword in normalized for keyword in _HIGH_RISK_KEYWORDS):
        return LEVEL_HIGH_RISK
    # Fail-safe: action_type yang tidak dikenal tidak pernah dianggap otomatis aman.
    return LEVEL_EXTERNAL_ACTION


@dataclass(frozen=True)
class ApprovalDecision:
    request_id: str
    action_type: str
    level: int
    status: str
    reason: str


class ApprovalGate:
    """State machine approval berbasis level, dengan audit log di SQLite."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS approval_requests (
                id TEXT PRIMARY KEY,
                created TEXT NOT NULL,
                action_type TEXT NOT NULL,
                level INTEGER NOT NULL,
                status TEXT NOT NULL,
                requested_by TEXT NOT NULL,
                summary TEXT NOT NULL,
                payload TEXT NOT NULL,
                decided_by TEXT NOT NULL DEFAULT '',
                decided_at TEXT NOT NULL DEFAULT '',
                reason TEXT NOT NULL DEFAULT ''
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_approval_status ON approval_requests(status, created)")

    def connect(self) -> Connection:
        connection = sqlite_connect(self.db_path, timeout=10)
        connection.row_factory = Row
        return connection

    def request(self, action_type: str, *, requested_by: str, summary: str = "",
                payload: dict | None = None) -> ApprovalDecision:
        """Ajukan satu aksi ke gate. Level 0-2 dan Level 3 rutin langsung `auto_jalan`;
        selain itu tercatat sebagai `pending_approval` dan menunggu keputusan owner."""
        action_type = (action_type or "").strip()
        if not action_type:
            raise ValueError("action_type wajib diisi untuk permintaan approval.")
        requested_by = (requested_by or "").strip()
        if not requested_by:
            raise ValueError("requested_by wajib diisi agar audit trail jelas.")

        level = _infer_level(action_type)
        if level <= LEVEL_CONTROLLED_WRITE:
            status = _STATUS_AUTO
            reason = f"{level_label(level)}: berjalan otomatis, tidak memerlukan approval."
        elif level == LEVEL_EXTERNAL_ACTION and action_type in _ROUTINE_AUTO_SEND:
            status = _STATUS_AUTO
            reason = f"{level_label(level)}: termasuk workflow bisnis rutin yang diizinkan auto-send."
        else:
            status = _STATUS_PENDING
            reason = f"{level_label(level)}: menunggu persetujuan owner sebelum dijalankan."

        request_id = str(uuid.uuid4())
        created = datetime.now().isoformat(timespec="seconds")
        encoded_payload = json.dumps(payload or {}, ensure_ascii=False)
        with self.connect() as db:
            db.execute(
                """INSERT INTO approval_requests
                   (id,created,action_type,level,status,requested_by,summary,payload)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (request_id, created, action_type, level, status, requested_by, summary.strip(), encoded_payload),
            )
        return ApprovalDecision(request_id, action_type, level, status, reason)

    def _transition(self, request_id: str, *, new_status: str, decided_by: str, reason: str) -> ApprovalDecision:
        decided_by = (decided_by or "").strip()
        if not decided_by:
            raise ValueError("decided_by wajib diisi agar audit trail jelas.")
        with self.connect() as db:
            row = db.execute("SELECT * FROM approval_requests WHERE id=?", (request_id,)).fetchone()
            if row is None:
                raise ValueError(f"Permintaan approval dengan id {request_id} tidak ditemukan.")
            if row["status"] != _STATUS_PENDING:
                raise ValueError(
                    f"Permintaan ini sudah berstatus '{row['status']}' dan tidak bisa diputuskan ulang."
                )
            decided_at = datetime.now().isoformat(timespec="seconds")
            db.execute(
                """UPDATE approval_requests
                   SET status=?, decided_by=?, decided_at=?, reason=?
                   WHERE id=?""",
                (new_status, decided_by, decided_at, reason, request_id),
            )
        return ApprovalDecision(request_id, row["action_type"], row["level"], new_status, reason)

    def approve(self, request_id: str, *, decided_by: str, reason: str = "") -> ApprovalDecision:
        return self._transition(
            request_id, new_status=_STATUS_APPROVED, decided_by=decided_by,
            reason=reason or "Disetujui owner.",
        )

    def reject(self, request_id: str, *, decided_by: str, reason: str = "") -> ApprovalDecision:
        return self._transition(
            request_id, new_status=_STATUS_REJECTED, decided_by=decided_by,
            reason=reason or "Ditolak owner.",
        )

    def get(self, request_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM approval_requests WHERE id=?", (request_id,)).fetchone()
        return dict(row) if row else None

    def pending_for_admin(self, limit: int = 20) -> list[dict]:
        """Daftar permintaan yang masih menunggu keputusan, terlama dulu (urutan antrean)."""
        with self.connect() as db:
            rows = db.execute(
                """SELECT * FROM approval_requests WHERE status=?
                   ORDER BY created ASC, rowid ASC LIMIT ?""",
                (_STATUS_PENDING, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def notification_text(self, request_id: str) -> str:
        """Teks siap kirim ke Telegram Admin untuk satu permintaan pending."""
        row = self.get(request_id)
        if row is None:
            raise ValueError(f"Permintaan approval dengan id {request_id} tidak ditemukan.")
        summary = row["summary"] or "(tidak ada ringkasan tambahan)"
        return (
            f"Butuh persetujuan — {level_label(row['level'])}\n"
            f"Aksi: {row['action_type']}\n"
            f"Diajukan oleh: {row['requested_by']}\n"
            f"Ringkasan: {summary}\n\n"
            f"Balas /approve {row['id']} untuk menyetujui, atau /reject {row['id']} <alasan> untuk menolak."
        )
