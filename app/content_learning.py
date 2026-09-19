"""Long-Term Feedback Memory untuk Social Media Agent — Content Learning.

Menerapkan aturan "Content Learning" di `agents/social_media_agent.md` dan lapis
Long-Term Feedback Memory di `docs/agent_memory_v1.md`, dengan prinsip yang sama
seperti Auto Category Learning di Finance Agent (`app/finance_corrections.py`):
append-only, tidak pernah overwrite riwayat lama.

Dua jenis catatan disimpan, keduanya SELALU terpisah per usaha (`business`) —
lihat Content Learning aturan 6, "Feedback dan data performa disimpan terpisah
per usaha":

1. Feedback draft (koreksi/persetujuan owner terhadap draft caption/naskah/visual).
2. Performa konten setelah tayang (reach, like, comment, dst).

Modul ini TIDAK melatih ulang model AI. Yang disimpan adalah konteks tambahan
yang dibaca ulang oleh Social Media Agent saat mengambil keputusan baru (lihat
`recurring_feedback_patterns` dan `top_performing_topics`).
"""
from __future__ import annotations

import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ALLOWED_FEEDBACK_TYPES = {"approved_as_is", "edited", "rejected"}
ALLOWED_METRICS = (
    "reach", "impressions", "likes", "comments", "shares", "saves", "views", "clicks",
)


@dataclass(frozen=True)
class ContentFeedbackEntry:
    id: str
    created_at: str
    business: str
    platform: str
    content_ref: str
    feedback_type: str
    aspect: str
    old_value: str
    new_value: str
    note: str


@dataclass(frozen=True)
class ContentPerformanceEntry:
    id: str
    collected_at: str
    business: str
    platform: str
    content_ref: str
    content_type: str
    topic: str
    reach: int | None
    impressions: int | None
    likes: int | None
    comments: int | None
    shares: int | None
    saves: int | None
    views: int | None
    clicks: int | None


@dataclass(frozen=True)
class FeedbackPattern:
    business: str
    platform: str
    aspect: str
    feedback_type: str
    occurrences: int
    examples: tuple[str, ...]


@dataclass(frozen=True)
class TopicPerformance:
    topic: str
    platform: str
    metric_name: str
    average_metric: float
    sample_count: int


def _row_to_feedback(row: sqlite3.Row) -> ContentFeedbackEntry:
    return ContentFeedbackEntry(
        id=row["id"], created_at=row["created_at"], business=row["business"],
        platform=row["platform"], content_ref=row["content_ref"],
        feedback_type=row["feedback_type"], aspect=row["aspect"],
        old_value=row["old_value"], new_value=row["new_value"], note=row["note"],
    )


def _row_to_performance(row: sqlite3.Row) -> ContentPerformanceEntry:
    return ContentPerformanceEntry(
        id=row["id"], collected_at=row["collected_at"], business=row["business"],
        platform=row["platform"], content_ref=row["content_ref"],
        content_type=row["content_type"], topic=row["topic"],
        reach=row["reach"], impressions=row["impressions"], likes=row["likes"],
        comments=row["comments"], shares=row["shares"], saves=row["saves"],
        views=row["views"], clicks=row["clicks"],
    )


class ContentLearningStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db_path, timeout=10)) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS content_feedback_log (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                business TEXT NOT NULL,
                platform TEXT NOT NULL,
                content_ref TEXT NOT NULL DEFAULT '',
                feedback_type TEXT NOT NULL,
                aspect TEXT NOT NULL,
                old_value TEXT NOT NULL DEFAULT '',
                new_value TEXT NOT NULL DEFAULT '',
                note TEXT NOT NULL DEFAULT '')""")
            db.execute("""CREATE TABLE IF NOT EXISTS content_performance_log (
                id TEXT PRIMARY KEY,
                collected_at TEXT NOT NULL,
                business TEXT NOT NULL,
                platform TEXT NOT NULL,
                content_ref TEXT NOT NULL DEFAULT '',
                content_type TEXT NOT NULL DEFAULT '',
                topic TEXT NOT NULL DEFAULT '',
                reach INTEGER, impressions INTEGER, likes INTEGER, comments INTEGER,
                shares INTEGER, saves INTEGER, views INTEGER, clicks INTEGER)""")
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_feedback_business "
                "ON content_feedback_log(business, platform, created_at)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_performance_business "
                "ON content_performance_log(business, platform, topic)"
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    # ------------------------------------------------------------------
    # Feedback draft (koreksi/persetujuan owner)
    # ------------------------------------------------------------------

    def record_feedback(
        self, business: str, platform: str, feedback_type: str, aspect: str, *,
        content_ref: str = "", old_value: str = "", new_value: str = "", note: str = "",
    ) -> ContentFeedbackEntry:
        business = str(business or "").strip()
        platform = str(platform or "").strip()
        feedback_type = str(feedback_type or "").strip()
        aspect = str(aspect or "").strip()
        if not business:
            raise ValueError("business wajib diisi.")
        if not platform:
            raise ValueError("platform wajib diisi.")
        if feedback_type not in ALLOWED_FEEDBACK_TYPES:
            raise ValueError(
                f"feedback_type tidak dikenali: {feedback_type!r}. "
                f"Pilihan: {sorted(ALLOWED_FEEDBACK_TYPES)}"
            )
        if not aspect:
            raise ValueError("aspect wajib diisi (contoh: hook, tone, tema, cta, visual).")

        entry = ContentFeedbackEntry(
            id=str(uuid.uuid4()),
            created_at=datetime.now().isoformat(timespec="seconds"),
            business=business, platform=platform, content_ref=str(content_ref or "").strip(),
            feedback_type=feedback_type, aspect=aspect,
            old_value=str(old_value or "").strip(), new_value=str(new_value or "").strip(),
            note=str(note or "").strip(),
        )
        with closing(self._connect()) as db, db:
            db.execute(
                """INSERT INTO content_feedback_log
                   (id,created_at,business,platform,content_ref,feedback_type,aspect,
                    old_value,new_value,note)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (entry.id, entry.created_at, entry.business, entry.platform, entry.content_ref,
                 entry.feedback_type, entry.aspect, entry.old_value, entry.new_value, entry.note),
            )
        return entry

    def recent_feedback(
        self, business: str, platform: str | None = None, *, limit: int = 20,
    ) -> list[ContentFeedbackEntry]:
        """Riwayat feedback terbaru dulu — dipakai sebelum membuat draft baru
        (Content Learning aturan 1: jangan menebak gaya dari nol kalau riwayatnya ada)."""
        business = str(business or "").strip()
        if not business:
            raise ValueError("business wajib diisi.")
        query = "SELECT * FROM content_feedback_log WHERE business=?"
        params: list = [business]
        if platform:
            query += " AND platform=?"
            params.append(str(platform).strip())
        query += " ORDER BY created_at DESC, rowid DESC LIMIT ?"
        params.append(int(limit))
        with closing(self._connect()) as db:
            rows = db.execute(query, params).fetchall()
        return [_row_to_feedback(row) for row in rows]

    def recurring_feedback_patterns(
        self, business: str, platform: str | None = None, *,
        min_occurrences: int = 2, lookback: int = 50,
    ) -> list[FeedbackPattern]:
        """Pola koreksi yang BERULANG saja (Content Learning aturan 3-4): satu
        koreksi tunggal tidak digeneralisasi. `approved_as_is` diabaikan karena
        bukan sinyal koreksi."""
        entries = self.recent_feedback(business, platform, limit=lookback)
        groups: dict[tuple[str, str], list[ContentFeedbackEntry]] = {}
        for entry in entries:
            if entry.feedback_type == "approved_as_is":
                continue
            key = (entry.aspect, entry.feedback_type)
            groups.setdefault(key, []).append(entry)

        patterns: list[FeedbackPattern] = []
        for (aspect, feedback_type), items in groups.items():
            if len(items) < min_occurrences:
                continue
            platforms = {item.platform for item in items}
            platform_label = next(iter(platforms)) if len(platforms) == 1 else "berbagai"
            examples = tuple(
                (item.note or item.new_value or item.old_value)
                for item in items[:3] if (item.note or item.new_value or item.old_value)
            )
            patterns.append(FeedbackPattern(
                business=business, platform=platform_label, aspect=aspect,
                feedback_type=feedback_type, occurrences=len(items), examples=examples,
            ))
        patterns.sort(key=lambda p: p.occurrences, reverse=True)
        return patterns

    def has_sufficient_history(
        self, business: str, platform: str | None = None, *, min_entries: int = 5,
    ) -> bool:
        """Bantu Social Media Agent membedakan cold-start vs sudah punya cukup riwayat
        internal (Content Learning aturan 8) — di bawah ambang ini, referensi eksternal
        (`docs/social_media_content_research.md`) boleh dipakai sebagai titik awal saja."""
        return len(self.recent_feedback(business, platform, limit=min_entries)) >= min_entries

    # ------------------------------------------------------------------
    # Performa konten setelah tayang
    # ------------------------------------------------------------------

    def record_performance(
        self, business: str, platform: str, content_ref: str = "", *,
        content_type: str = "", topic: str = "",
        reach: int | None = None, impressions: int | None = None, likes: int | None = None,
        comments: int | None = None, shares: int | None = None, saves: int | None = None,
        views: int | None = None, clicks: int | None = None,
    ) -> ContentPerformanceEntry:
        business = str(business or "").strip()
        platform = str(platform or "").strip()
        if not business:
            raise ValueError("business wajib diisi.")
        if not platform:
            raise ValueError("platform wajib diisi.")

        entry = ContentPerformanceEntry(
            id=str(uuid.uuid4()), collected_at=datetime.now().isoformat(timespec="seconds"),
            business=business, platform=platform, content_ref=str(content_ref or "").strip(),
            content_type=str(content_type or "").strip(), topic=str(topic or "").strip(),
            reach=reach, impressions=impressions, likes=likes, comments=comments,
            shares=shares, saves=saves, views=views, clicks=clicks,
        )
        with closing(self._connect()) as db, db:
            db.execute(
                """INSERT INTO content_performance_log
                   (id,collected_at,business,platform,content_ref,content_type,topic,
                    reach,impressions,likes,comments,shares,saves,views,clicks)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (entry.id, entry.collected_at, entry.business, entry.platform, entry.content_ref,
                 entry.content_type, entry.topic, entry.reach, entry.impressions, entry.likes,
                 entry.comments, entry.shares, entry.saves, entry.views, entry.clicks),
            )
        return entry

    def recent_performance(
        self, business: str, platform: str | None = None, *, limit: int = 20,
    ) -> list[ContentPerformanceEntry]:
        """Riwayat performa mentah terbaru dulu, tanpa agregasi — untuk audit/inspeksi
        manual. Untuk sinyal "topik mana yang lebih baik", pakai `top_performing_topics()`."""
        business = str(business or "").strip()
        if not business:
            raise ValueError("business wajib diisi.")
        query = "SELECT * FROM content_performance_log WHERE business=?"
        params: list = [business]
        if platform:
            query += " AND platform=?"
            params.append(str(platform).strip())
        query += " ORDER BY collected_at DESC, rowid DESC LIMIT ?"
        params.append(int(limit))
        with closing(self._connect()) as db:
            rows = db.execute(query, params).fetchall()
        return [_row_to_performance(row) for row in rows]

    def top_performing_topics(
        self, business: str, platform: str | None = None, *,
        metric: str = "reach", limit: int = 5, min_samples: int = 1,
    ) -> list[TopicPerformance]:
        """Topik/jenis konten dengan rata-rata metrik tertinggi (Content Learning
        aturan 5) — sinyal tambahan untuk brainstorming ide berikutnya di usaha yang
        sama. Topik kosong (belum ditandai) diabaikan."""
        business = str(business or "").strip()
        if not business:
            raise ValueError("business wajib diisi.")
        if metric not in ALLOWED_METRICS:
            raise ValueError(f"metric tidak dikenali: {metric!r}. Pilihan: {list(ALLOWED_METRICS)}")

        query = (
            f"SELECT topic, platform, AVG({metric}) AS avg_metric, COUNT(*) AS n "
            "FROM content_performance_log "
            f"WHERE business=? AND topic<>'' AND {metric} IS NOT NULL"
        )
        params: list = [business]
        if platform:
            query += " AND platform=?"
            params.append(str(platform).strip())
        query += " GROUP BY topic, platform HAVING n>=? ORDER BY avg_metric DESC, n DESC LIMIT ?"
        params.extend([int(min_samples), int(limit)])

        with closing(self._connect()) as db:
            rows = db.execute(query, params).fetchall()

        return [
            TopicPerformance(
                topic=row["topic"], platform=row["platform"], metric_name=metric,
                average_metric=float(row["avg_metric"]), sample_count=int(row["n"]),
            )
            for row in rows
        ]
