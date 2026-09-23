"""Telegram delivery journal: never rerun a claimed business action on replay.

An interrupted action has an uncertain outcome and is reported for review. Telegram
cannot provide atomic delivery with local writes; a timeout may duplicate a reply
chunk, but must not trigger a second finance write or AI job.
"""
from contextlib import contextmanager
import sqlite3
from pathlib import Path


class TelegramUpdateStore:
    def __init__(self, db_path: str | Path, bot_id: int):
        self.db_path = Path(db_path)
        self.bot_id = bot_id
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS telegram_updates (
                bot_id INTEGER NOT NULL, update_id INTEGER NOT NULL, chat_id INTEGER NOT NULL,
                state TEXT NOT NULL, reply TEXT NOT NULL DEFAULT '', sent_chunks INTEGER NOT NULL DEFAULT 0,
                thread_id INTEGER, PRIMARY KEY(bot_id, update_id))''')
            db.execute('''CREATE TABLE IF NOT EXISTS telegram_cursors (
                bot_id INTEGER PRIMARY KEY, next_offset INTEGER NOT NULL)''')
            # Migrasi untuk database lama (sebelum fitur topik grup): tabel sudah ada
            # tanpa kolom thread_id, jadi CREATE TABLE IF NOT EXISTS di atas tidak
            # menambahkannya — ditambah manual di sini, aman dijalankan berulang kali.
            columns = {row[1] for row in db.execute('PRAGMA table_info(telegram_updates)')}
            if 'thread_id' not in columns:
                db.execute('ALTER TABLE telegram_updates ADD COLUMN thread_id INTEGER')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def reserve(self, update_id: int, chat_id: int, thread_id: int | None = None) -> bool:
        with self.connect() as db:
            result = db.execute('''INSERT OR IGNORE INTO telegram_updates(bot_id,update_id,chat_id,state,thread_id)
                VALUES(?,?,?,'processing',?)''', (self.bot_id, update_id, chat_id, thread_id))
            return result.rowcount == 1

    def get(self, update_id: int):
        with self.connect() as db:
            row = db.execute('SELECT * FROM telegram_updates WHERE bot_id=? AND update_id=?',
                             (self.bot_id, update_id)).fetchone()
            return dict(row) if row else None

    def complete(self, update_id: int, reply: str):
        with self.connect() as db:
            db.execute("UPDATE telegram_updates SET state='ready',reply=? WHERE bot_id=? AND update_id=?",
                       (reply, self.bot_id, update_id))

    def delivered(self, update_id: int, sent_chunks: int, *, done: bool):
        with self.connect() as db:
            db.execute('UPDATE telegram_updates SET sent_chunks=?,state=? WHERE bot_id=? AND update_id=?',
                       (sent_chunks, 'sent' if done else 'ready', self.bot_id, update_id))

    def pending(self, chat_id: int) -> list[dict]:
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT * FROM telegram_updates WHERE bot_id=? AND chat_id=? AND state!='sent' ORDER BY update_id",
                (self.bot_id, chat_id))]

    def offset(self) -> int | None:
        with self.connect() as db:
            row = db.execute('SELECT next_offset FROM telegram_cursors WHERE bot_id=?', (self.bot_id,)).fetchone()
            return row[0] if row else None

    def advance(self, offset: int):
        with self.connect() as db:
            db.execute('''INSERT INTO telegram_cursors(bot_id,next_offset) VALUES(?,?)
                ON CONFLICT(bot_id) DO UPDATE SET next_offset=MAX(next_offset,excluded.next_offset)''',
                (self.bot_id, offset))
