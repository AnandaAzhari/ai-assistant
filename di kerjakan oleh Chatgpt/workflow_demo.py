"""Demo antrean lokal dengan file contoh nyata; tidak memakai jaringan/API/token."""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import uuid
from pathlib import Path

from chatgpt_billing.pricing import QuoteRequest, make_quote
from chatgpt_billing.telegram_admin import payment_summary
from chatgpt_billing.workflow import Brief, JOB_LABELS, WorkflowStore
from chatgpt_billing.workers import OfflineDemoWorker

ROOT = Path(__file__).resolve().parent


def create_example(store: WorkflowStore, title: str = 'Pemanfaatan AI untuk administrasi dokumen') -> str:
    order = store.create_order(make_quote(QuoteRequest()), approved_by='operator-demo')
    store.accept_quote(order.order_id, actor='pelanggan-demo')
    store.register_brief(order.order_id, Brief(title), actor='pelanggan-demo')
    return order.order_id


def pay(store: WorkflowStore, order_id: str, *, settle: bool) -> None:
    order = store.get(order_id)
    amount = order.remaining if settle else max(0, order.required_before_work - order.paid)
    if not amount:
        print('Pembayaran yang diminta sudah terpenuhi.')
        return
    store.simulate_payment(order_id, 'MENU-' + uuid.uuid4().hex, amount, source='simulasi_qris',
                           actor='owner-demo')
    print(payment_summary(store.get(order_id)))


def overview(store: WorkflowStore, order_id: str | None) -> None:
    if order_id:
        print('\n' + payment_summary(store.get(order_id)))
    for job in store.jobs():
        print(f"{job['order_id']} | {JOB_LABELS[job['state']]} | percobaan {job['attempts']}/2")
        if job['problem']:
            print('  Keterangan:', job['problem'])


def open_local(path: Path) -> None:
    print('Lokasi:', path)
    if os.name == 'nt':
        os.startfile(str(path))
    else:
        print('Buka lokasi tersebut melalui pengelola file.')


def sample(store: WorkflowStore) -> None:
    order_id = create_example(store)
    print('Pesanan contoh baru:', order_id)
    if store.claim_next() is not None:
        raise ValueError('Skenario otomatis harus memakai database contoh kosong.')
    print('LULUS: pekerja ditahan sebelum DP.')
    pay(store, order_id, settle=False)
    result = store.run_next(OfflineDemoWorker())
    if not result or result['state'] != 'review':
        raise ValueError('Hasil gagal diperiksa: ' + str(result))
    print('Pratinjau:', store.preview(order_id))
    for label, approve in [('sebelum persetujuan', False), ('sebelum lunas', True)]:
        if approve:
            manifest = json.loads(store.job(order_id)['manifest_json'])
            store.approve_result(order_id, preview_sha256=manifest['files']['preview_pdf']['sha256'], actor='pelanggan-demo')
        try:
            store.release_result(order_id, actor='owner-demo')
        except ValueError:
            print('LULUS: file final ditahan ' + label + '.')
        else:
            raise ValueError('Penguncian file final gagal.')
    pay(store, order_id, settle=True)
    destination = store.release_result(order_id, actor='owner-demo')
    print('ALUR SELESAI. File contoh tersedia di:', destination)
    print('Word: hasil.docx | PDF: hasil.pdf | Bukti: BUKTI_PENYERAHAN.json')
    print('File disalin lokal; belum dikirim ke pelanggan atau Telegram.')


def interactive(store: WorkflowStore) -> None:
    current = None
    seen: dict[str, str] = {}
    print('Mulai dengan 1 untuk pesanan baru. Pesanan uji lama: pilih 2, lalu 10 untuk menambahkan brief.')
    while True:
        print('\nPesanan aktif:', current or '(belum dipilih)')
        print('1 Buat pesanan contoh     2 Pilih pesanan       3 Simulasikan DP')
        print('4 Kerjakan antrean        5 Buka pratinjau      6 Setujui pratinjau')
        print('7 Simulasikan pelunasan   8 Lepas file final    9 Status dan antrean')
        print('10 Tambah brief pesanan lama   11 Pulihkan yang terputus   12 Ulangi yang diblokir')
        print('0 Keluar')
        choice = input('Pilihan: ').strip()
        try:
            if choice == '0':
                return
            if choice == '1':
                title = input('Judul contoh [Pemanfaatan AI untuk administrasi dokumen]: ').strip()
                current = create_example(store, title or 'Pemanfaatan AI untuk administrasi dokumen')
                overview(store, current)
            elif choice == '2':
                for order in store.list_orders():
                    print(order.order_id, '|', order.status)
                selected = input('Salin ID pesanan: ').strip()
                store.get(selected)
                current = selected
            elif choice == '4':
                result = store.run_next(OfflineDemoWorker())
                if result:
                    current = result['order_id']
                    print('Pekerjaan:', current, '|', JOB_LABELS[result['state']])
                    if result['problem']:
                        print(result['problem'])
                else:
                    print('Belum ada antrean siap. Pastikan brief disetujui dan DP cukup.')
            elif choice == '9':
                overview(store, current)
            elif choice == '11':
                print('Pekerjaan yang dipulihkan:', store.recover_expired())
                print('Lease bawaan 15 menit. Pekerjaan aktif tidak dihentikan. Setelah diblokir, gunakan menu 12.')
            elif choice in ('3', '5', '6', '7', '8', '10', '12'):
                if not current:
                    raise ValueError('Pilih atau buat pesanan terlebih dahulu.')
                if choice in ('3', '7'):
                    pay(store, current, settle=choice == '7')
                elif choice == '5':
                    path = store.preview(current)
                    seen[current] = json.loads(store.job(current)['manifest_json'])['files']['preview_pdf']['sha256']
                    open_local(path)
                elif choice == '6':
                    if current not in seen:
                        raise ValueError('Buka pratinjau melalui menu 5 terlebih dahulu.')
                    store.approve_result(current, preview_sha256=seen[current], actor='pelanggan-demo')
                    print('Versi pratinjau yang ditampilkan telah disetujui dalam simulasi.')
                elif choice == '8':
                    path = store.release_result(current, actor='owner-demo')
                    print('File final tersedia lokal. Belum dikirim ke pelanggan.')
                    open_local(path)
                elif choice == '10':
                    title = input('Judul brief yang disetujui: ').strip()
                    store.register_brief(current, Brief(title), actor='pelanggan-demo')
                    overview(store, current)
                else:
                    store.retry(current, actor='owner-demo')
                    print('Pekerjaan masuk antrean kembali. Gunakan menu 4.')
            else:
                print('Pilihan tidak dikenal.')
        except (ValueError, OSError, sqlite3.Error) as exc:
            print('TIDAK DIPROSES:', exc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Antrean DP sampai file final - DEMO OFFLINE')
    parser.add_argument('--sample', action='store_true', help='Jalankan satu alur contoh otomatis')
    args = parser.parse_args(argv)
    print('=== DEMO ANTREAN: PEMBAYARAN SIMULASI, FILE CONTOH, TANPA AI/TELEGRAM ASLI ===')
    print('Dokumen contoh singkat bukan makalah 10 halaman; harga tetap usulan uji.')
    store = None
    try:
        if args.sample:
            # Tiap contoh otomatis terpisah dari pesanan interaktif pengguna.
            location = ROOT / 'runtime' / 'samples' / uuid.uuid4().hex
            store = WorkflowStore(location / 'demo.sqlite3', location / 'workflow')
        else:
            store = WorkflowStore(ROOT / 'runtime' / 'demo.sqlite3', ROOT / 'runtime' / 'workflow')
        sample(store) if args.sample else interactive(store)
        return 0
    except (EOFError, KeyboardInterrupt):
        print('\nDemo ditutup. Data yang telah tersimpan tetap tersedia.')
        return 0
    except (ValueError, OSError, sqlite3.Error) as exc:
        print('Demo berhenti:', exc)
        return 1
    finally:
        if store:
            store.close()


if __name__ == '__main__':
    raise SystemExit(main())
