"""Antrean lokal terisolasi. Tidak mengirim pesan, mengakses token, atau memanggil AI.

Pembayaran dan enqueue berbagi transaksi SQLite. Lease + token mencegah pekerja
lama menyelesaikan percobaan baru. Retry selalu eksplisit dan dibatasi.
"""
from __future__ import annotations

import json
import shutil
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Protocol

from .artifacts import ArtifactSet, inspect_artifacts, verify_manifest
from .payment_flow import DemoStore, OrderView, _text

JOB_LABELS = {
    "waiting": "Menunggu persetujuan harga atau DP",
    "queued": "Dalam antrean",
    "running": "Sedang dikerjakan",
    "blocked": "Perlu pemeriksaan operator",
    "review": "Pratinjau siap diperiksa",
    "approved": "Pratinjau disetujui",
    "released": "File final tersedia lokal",
}


@dataclass(frozen=True)
class Brief:
    title: str
    requirements: str = "Contoh uji alur, bukan makalah pesanan pelanggan."

    def validated(self) -> "Brief":
        return Brief(_text(self.title, "Judul", 160), _text(self.requirements, "Ketentuan", 1500))


@dataclass(frozen=True)
class WorkItem:
    order_id: str
    brief: Brief
    attempt: int
    token: str
    output_dir: Path


class DocumentWorker(Protocol):
    def produce(self, item: WorkItem) -> ArtifactSet: ...


class WorkflowStore(DemoStore):
    """Satu koneksi per thread/proses. Root file hanya untuk demo ini.

Database v1 dapat dipakai kembali. Pesanan lama perlu brief yang disetujui
operator sebelum masuk antrean; data pembayaran lama tetap dipertahankan.
"""

    def __init__(self, db_path: str | Path, artifact_root: str | Path, *,
                 clock: Callable[[], float] = time.time, lease_seconds: int = 900):
        if type(lease_seconds) is not int or not 1 <= lease_seconds <= 3600:
            raise ValueError("Lease harus 1 sampai 3600 detik.")
        self.clock, self.lease_seconds = clock, lease_seconds
        raw_root = Path(artifact_root)
        if raw_root.is_symlink():
            raise ValueError("Folder hasil tidak boleh berupa symlink.")
        self.root = raw_root.resolve()
        super().__init__(db_path)
        try:
            self.db.execute("""CREATE TABLE IF NOT EXISTS demo_jobs (
                order_id TEXT PRIMARY KEY REFERENCES demo_orders(id),
                brief_json TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'waiting',
                attempts INTEGER NOT NULL DEFAULT 0, run_token TEXT NOT NULL DEFAULT '',
                lease_until REAL NOT NULL DEFAULT 0, manifest_json TEXT NOT NULL DEFAULT '',
                problem TEXT NOT NULL DEFAULT '', created REAL NOT NULL,
                released_path TEXT NOT NULL DEFAULT '')""")
            self._init_root()
            self.reconcile()
        except Exception:
            self.close()
            raise

    def _init_root(self) -> None:
        marker = self.root / '.workflow-demo'
        with self._transaction():
            row = self.db.execute("SELECT value FROM demo_meta WHERE name='workflow_id'").fetchone()
            identity = row[0] if row else uuid.uuid4().hex
            if self.root.exists() and any(self.root.iterdir()):
                if not marker.is_file() or marker.is_symlink() or marker.read_text() != identity:
                    raise ValueError("Folder hasil bukan milik demo ini. Gunakan folder runtime/workflow demo.")
            else:
                self.root.mkdir(parents=True, exist_ok=True)
                marker.write_text(identity, encoding='ascii')
            self.db.execute("INSERT OR IGNORE INTO demo_meta VALUES('workflow_id',?)", (identity,))

    def job(self, order_id: str) -> dict:
        row = self.db.execute("SELECT * FROM demo_jobs WHERE order_id=?", (order_id,)).fetchone()
        if row is None:
            raise ValueError("Pesanan belum memiliki brief antrean.")
        return dict(row)

    def jobs(self) -> list[dict]:
        return [dict(r) for r in self.db.execute("SELECT * FROM demo_jobs ORDER BY created, rowid")]

    def register_brief(self, order_id: str, brief: Brief, *, actor: str) -> dict:
        brief = brief.validated()
        actor = _text(actor, "Penyetuju brief")
        encoded = json.dumps(asdict(brief), ensure_ascii=False, sort_keys=True)
        with self._transaction():
            order = self.get(order_id)
            prior = self.db.execute("SELECT brief_json FROM demo_jobs WHERE order_id=?", (order_id,)).fetchone()
            if prior:
                if prior[0] != encoded:
                    raise ValueError("Brief sudah dikunci. Perubahan cakupan memerlukan penawaran baru.")
                return self.job(order_id)
            if order.stage not in ('quoted', 'accepted'):
                raise ValueError("Brief antrean harus didaftarkan sebelum pengerjaan dimulai.")
            if order.quote['service'] != 'makalah':
                raise ValueError("Antrean versi ini untuk makalah; perapian file pelanggan belum dihubungkan.")
            self.db.execute("INSERT INTO demo_jobs(order_id,brief_json,created) VALUES(?,?,?)",
                            (order_id, encoded, self.clock()))
            self._event(order_id, 'brief_approved', actor)
            self._payment_recorded(order)
        return self.job(order_id)

    def reconcile(self) -> None:
        with self._transaction():
            for row in self.db.execute("SELECT order_id FROM demo_jobs WHERE state='waiting'").fetchall():
                self._payment_recorded(self.get(row[0]))

    def recover_expired(self) -> int:
        with self._transaction():
            rows = self.db.execute("SELECT order_id FROM demo_jobs WHERE state='running' AND lease_until<=?",
                                   (self.clock(),)).fetchall()
            for row in rows:
                self.db.execute("UPDATE demo_jobs SET state='blocked',run_token='',problem=? WHERE order_id=?",
                                ('Pekerjaan terputus atau lease habis. Periksa sebelum mengulang.', row[0]))
                self._event(row[0], 'job_interrupted', 'Hasil pekerja lama tidak lagi diterima.')
        return len(rows)

    def claim_next(self) -> WorkItem | None:
        self.reconcile()
        self.recover_expired()
        with self._transaction():
            rows = self.db.execute("SELECT * FROM demo_jobs WHERE state='queued' ORDER BY created,rowid").fetchall()
            for row in rows:
                if row['attempts'] >= 2:
                    raise ValueError('Batas dua percobaan tercapai. Perlu pemeriksaan operator.')
                order = self.get(row['order_id'])
                if order.stage not in ('accepted', 'working') or order.paid < order.required_before_work:
                    raise ValueError("Antrean tidak cocok dengan tahap/pembayaran pesanan. Perlu pemeriksaan.")
                token = uuid.uuid4().hex
                if order.stage == 'accepted':
                    self._set_stage(order.order_id, 'working', 'start_work', 'queue-worker')
                self.db.execute("""UPDATE demo_jobs SET state='running',attempts=attempts+1,
                    run_token=?,lease_until=?,problem='' WHERE order_id=?""",
                    (token, self.clock() + self.lease_seconds, order.order_id))
                self._event(order.order_id, 'job_claimed', token)
                output = self.root / 'private' / order.order_id / token
                # Resolusi juga memblokir direktori perantara yang diarahkan ke luar root.
                if not output.resolve().is_relative_to(self.root):
                    raise ValueError("Folder pengerjaan keluar dari folder demo.")
                return WorkItem(order.order_id, Brief(**json.loads(row['brief_json'])),
                                row['attempts'] + 1, token, output)
        return None

    def _owned(self, item: WorkItem) -> dict:
        row = self.job(item.order_id)
        if (row['state'] != 'running' or row['run_token'] != item.token
                or row['lease_until'] <= self.clock()):
            raise ValueError("Percobaan ini sudah kedaluwarsa atau telah digantikan.")
        return row

    def heartbeat(self, item: WorkItem) -> None:
        with self._transaction():
            self._owned(item)
            self.db.execute("UPDATE demo_jobs SET lease_until=? WHERE order_id=?",
                            (self.clock() + self.lease_seconds, item.order_id))

    def complete(self, item: WorkItem, artifacts: ArtifactSet) -> dict:
        manifest = inspect_artifacts(artifacts, item.output_dir, self.root)
        with self._transaction():
            self._owned(item)
            order = self.get(item.order_id)
            if order.stage != 'working':
                raise ValueError("Tahap pengerjaan berubah sebelum hasil selesai.")
            self.db.execute("UPDATE demo_jobs SET state='review',manifest_json=?,lease_until=0 WHERE order_id=?",
                            (json.dumps(manifest, sort_keys=True), item.order_id))
            preview = manifest['files']['preview_pdf']['path']
            self.db.execute("UPDATE demo_orders SET preview_reference=? WHERE id=?", (preview, item.order_id))
            self._set_stage(item.order_id, 'preview', 'artifacts_checked', 'queue-worker')
        return self.job(item.order_id)

    def fail(self, item: WorkItem, reason: str) -> None:
        with self._transaction():
            row = self.job(item.order_id)
            if row['state'] != 'running' or row['run_token'] != item.token:
                return  # Hasil terlambat tidak boleh merusak percobaan pengganti.
            reason = str(reason)[:800] or 'Pekerja gagal tanpa keterangan.'
            self.db.execute("UPDATE demo_jobs SET state='blocked',problem=?,lease_until=0 WHERE order_id=?",
                            (reason, item.order_id))
            self._event(item.order_id, 'job_blocked', reason)

    def run_next(self, worker: DocumentWorker) -> dict | None:
        item = self.claim_next()
        if item is None:
            return None
        try:
            item.output_dir.mkdir(parents=True, exist_ok=False)
            self.complete(item, worker.produce(item))
        except Exception as exc:
            self.fail(item, str(exc))
        return self.job(item.order_id)

    def retry(self, order_id: str, *, actor: str) -> None:
        actor = _text(actor, 'Operator pengulang pekerjaan')
        with self._transaction():
            row = self.job(order_id)
            if row['state'] != 'blocked' or row['attempts'] >= 2:
                raise ValueError("Hanya pekerjaan diblokir yang dapat diulang; maksimal dua percobaan.")
            self.db.execute("UPDATE demo_jobs SET state='queued',run_token='',problem='' WHERE order_id=?", (order_id,))
            self._event(order_id, 'job_retry', actor)

    def _manifest(self, order_id: str) -> dict:
        row = self.job(order_id)
        if not row['manifest_json']:
            raise ValueError("Hasil belum tersedia.")
        manifest = json.loads(row['manifest_json'])
        verify_manifest(manifest, self.root)
        return manifest

    def preview(self, order_id: str) -> Path:
        with self._transaction():
            return self.root / self._manifest(order_id)['files']['preview_pdf']['path']

    def approve_result(self, order_id: str, *, preview_sha256: str, actor: str) -> None:
        actor = _text(actor, 'Penyetuju pratinjau')
        with self._transaction():
            row = self.job(order_id)
            manifest = self._manifest(order_id)
            if preview_sha256 != manifest['files']['preview_pdf']['sha256']:
                raise ValueError("Persetujuan tidak cocok dengan versi pratinjau ini.")
            if row['state'] != 'review' or self.get(order_id).stage != 'preview':
                raise ValueError("Pratinjau belum siap atau sudah disetujui.")
            self.db.execute("UPDATE demo_jobs SET state='approved' WHERE order_id=?", (order_id,))
            self._set_stage(order_id, 'approved', 'approve_preview', actor)

    def release_result(self, order_id: str, *, actor: str) -> Path:
        actor = _text(actor, 'Operator penyerahan file')
        with self._transaction():
            row = self.job(order_id)
            order = self.get(order_id)
            manifest = self._manifest(order_id)
            if row['state'] == 'released':
                destination = self.root / row['released_path']
                verify_manifest(manifest, self.root, released_dir=destination)
                return destination
            if row['state'] != 'approved' or not order.can_deliver:
                raise ValueError("File final ditahan: pratinjau harus disetujui dan tagihan harus lunas.")
            destination = self.root / 'released' / order_id / row['run_token']
            if not destination.resolve().is_relative_to(self.root):
                raise ValueError("Folder penyerahan keluar dari folder demo.")
            if not destination.exists():
                staging = self.root / 'private' / ('release-' + uuid.uuid4().hex)
                staging.mkdir(parents=True)
                try:
                    for key in ('docx', 'final_pdf'):
                        source = self.root / manifest['files'][key]['path']
                        shutil.copyfile(source, staging / ('hasil.docx' if key == 'docx' else 'hasil.pdf'))
                    verify_manifest(manifest, self.root, released_dir=staging)
                    (staging / 'BUKTI_PENYERAHAN.json').write_text(json.dumps({
                        'order_id': order_id, 'paid': order.paid, 'total': order.total,
                        'preview_sha256': manifest['files']['preview_pdf']['sha256'],
                        'note': 'SIMULASI. File disalin lokal; belum dikirim ke pelanggan.',
                    }, ensure_ascii=False, indent=2), encoding='utf-8')
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    staging.rename(destination)
                finally:
                    if staging.exists():
                        shutil.rmtree(staging)
            # Juga memvalidasi direktori yang tersisa sesudah crash sebelum commit.
            verify_manifest(manifest, self.root, released_dir=destination)
            relative = destination.relative_to(self.root).as_posix()
            self.db.execute("UPDATE demo_jobs SET state='released',released_path=? WHERE order_id=?", (relative, order_id))
            self.db.execute("UPDATE demo_orders SET final_reference=? WHERE id=?", (relative, order_id))
            self._set_stage(order_id, 'delivered', 'local_final_released', actor)
        return destination

    def _legacy_guard(self, order_id: str) -> None:
        if self.db.execute("SELECT 1 FROM demo_jobs WHERE order_id=?", (order_id,)).fetchone():
            raise ValueError("Pesanan ini dikelola antrean. Gunakan pemeriksaan hasil dan pelepasan file antrean.")

    def start_work(self, order_id: str, **kwargs):
        self._legacy_guard(order_id)
        return super().start_work(order_id, **kwargs)

    def send_preview(self, order_id: str, reference: str, **kwargs):
        self._legacy_guard(order_id)
        return super().send_preview(order_id, reference, **kwargs)

    def approve_preview(self, order_id: str, **kwargs):
        self._legacy_guard(order_id)
        return super().approve_preview(order_id, **kwargs)

    def request_revision(self, order_id: str, note: str, **kwargs):
        self._legacy_guard(order_id)
        return super().request_revision(order_id, note, **kwargs)

    def release_final(self, order_id: str, reference: str, **kwargs):
        self._legacy_guard(order_id)
        return super().release_final(order_id, reference, **kwargs)
