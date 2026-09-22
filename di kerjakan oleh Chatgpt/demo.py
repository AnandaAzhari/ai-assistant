"""Demo terminal lokal, Python 3.11+, tanpa paket tambahan atau koneksi internet."""
from __future__ import annotations

import argparse
import sqlite3
import uuid
from pathlib import Path

from chatgpt_billing.payment_flow import DemoStore, LABELS, OrderView
from chatgpt_billing.pricing import QuoteRequest, load_config, make_quote, rupiah
from chatgpt_billing.telegram_admin import DemoTelegramAdmin

ROOT = Path(__file__).resolve().parent


def show(order: OrderView) -> None:
    print(f"\n{order.order_id} | {LABELS[order.status]}")
    print(f"Total {rupiah(order.total)} | Dibayar (SIMULASI) {rupiah(order.paid)} | Sisa {rupiah(order.remaining)}")
    print(f"Syarat mulai: {rupiah(order.required_before_work)} | Revisi: {order.revisions_used}/{order.revisions_allowed}")


def number(prompt: str, default: int = 0) -> int:
    while True:
        raw = input(f"{prompt} [{default}]: ").strip()
        try:
            value = int(raw) if raw else default
            if value < 0:
                raise ValueError
            return value
        except ValueError:
            print("Masukkan angka bulat tanpa Rp atau titik, contoh 18000.")


def yes(prompt: str) -> bool:
    return input(prompt + " [y/t, default t]: ").strip().lower() in ("y", "ya")


def new_order(store: DemoStore) -> OrderView:
    service = input("Layanan makalah/rapikan [makalah]: ").strip().lower() or "makalah"
    pages = number("Halaman isi makalah / halaman yang dirapikan", 10)
    package, formatting = "otomatis", "dasar"
    if service == "makalah":
        package = input("Paket otomatis/ringkas/standar/lengkap [otomatis]: ").strip().lower() or "otomatis"
    elif service == "rapikan":
        formatting = input("Tingkat dasar/struktur/khusus [dasar]: ").strip().lower() or "dasar"
    note_mode = "tidak"
    note_count = 0
    if yes("Tambahkan layanan footnote dari sumber lengkap?"):
        note_mode = "bundle" if service == "makalah" else "rapikan"
        note_count = number("Jumlah footnote", 10)
    request = QuoteRequest(service=service, pages=pages, package=package, formatting=formatting,
                           footnote_mode=note_mode, footnote_count=note_count,
                           sources_to_verify=number("Sumber yang perlu dicari/diverifikasi"),
                           extra_revision_rounds=number("Tambahan putaran revisi kecil"),
                           rush=yes("Pengerjaan cepat kurang dari 24 jam?"))
    quote = make_quote(request)
    print("\nPENAWARAN CONTOH - TARIF USULAN")
    for line in quote.lines:
        print(f"  {line.description}: {rupiah(line.amount)}")
    print(f"  TOTAL: {rupiah(quote.total)} | Bayar awal: {rupiah(quote.required_before_work)}")
    reviewed = False
    if quote.review_reasons:
        print("\nMemerlukan pemeriksaan operator:")
        for reason in quote.review_reasons:
            print("  - " + reason)
        reviewed = yes("Simulasikan bahwa operator sudah memeriksa dan menyetujui penawaran ini?")
    return store.create_order(quote, approved_by="operator-demo", manual_review_confirmed=reviewed)


def sample() -> None:
    """Skenario sekali jalan, seluruh data di memori dan tidak membuat file."""
    store = DemoStore()
    try:
        order = store.create_order(make_quote(QuoteRequest()), approved_by="operator-demo")
        print("\nSkenario: makalah 10 halaman, format standar.")
        show(order)
        ident = order.order_id
        store.accept_quote(ident, actor="pelanggan-demo")
        try:
            store.start_work(ident, actor="operator-demo")
        except ValueError as exc:
            print("\nPemeriksaan sebelum DP: " + str(exc))
        store.simulate_payment(ident, "DEMO-DP-001", order.required_before_work, status="pending")
        print("Notifikasi pending: uang tercatat = " + rupiah(store.get(ident).paid))
        store.simulate_payment(ident, "DEMO-DP-001", order.required_before_work)
        store.simulate_payment(ident, "DEMO-DP-001", order.required_before_work)
        print("Notifikasi sukses dikirim dua kali: uang tetap = " + rupiah(store.get(ident).paid))
        store.start_work(ident, actor="operator-demo")
        store.send_preview(ident, "DEMO-pratinjau-watermark.pdf", actor="operator-demo")
        store.approve_preview(ident, actor="pelanggan-demo")
        show(store.get(ident))
        try:
            store.release_final(ident, "DEMO-final.docx", actor="operator-demo")
        except ValueError as exc:
            print("\nPemeriksaan sebelum lunas: " + str(exc))
        balance = store.get(ident).remaining
        if balance:
            store.simulate_payment(ident, "DEMO-LUNAS-001", balance)
        show(store.release_final(ident, "DEMO-final.docx + DEMO-final.pdf", actor="operator-demo"))
        print("\nDemo selesai. Tidak ada uang, pesan, atau file makalah sungguhan yang dikirim.")
    finally:
        store.close()


def interactive() -> None:
    cfg = load_config()
    print("Konfigurasi: " + cfg["version"] + " (bisa diubah di config_harga.json)")
    db_path = ROOT / "runtime" / "demo.sqlite3"
    store = DemoStore(db_path)
    print(f"Data demo: {db_path}")
    current: str | None = None
    try:
        while True:
            if current:
                show(store.get(current))
            print("\n1 Buat penawaran  | 2 Pilih/lihat pesanan | 3 Setujui harga")
            print("4 Simulasi bayar  | 5 Mulai pengerjaan  | 6 Catat pratinjau")
            print("7 Minta revisi    | 8 Setujui pratinjau | 9 Serahkan final")
            print("10 Riwayat        | 11 Batalkan belum dibayar | 0 Keluar")
            choice = input("Pilih: ").strip()
            try:
                if choice == "0":
                    break
                if choice == "1":
                    current = new_order(store).order_id
                    continue
                if choice == "2":
                    orders = store.list_orders()
                    for index, order in enumerate(orders, 1):
                        print(f"{index}. {order.order_id} | {LABELS[order.status]} | {rupiah(order.total)}")
                    if orders:
                        index = number("Nomor pesanan", 1)
                        if not 1 <= index <= len(orders):
                            raise ValueError("Nomor pesanan tidak tersedia.")
                        current = orders[index - 1].order_id
                    else:
                        print("Belum ada pesanan demo.")
                    continue
                if not current:
                    raise ValueError("Buat atau pilih pesanan terlebih dahulu.")
                if choice == "3":
                    store.accept_quote(current, actor="pelanggan-demo")
                elif choice == "4":
                    order = store.get(current)
                    suggested = max(0, order.required_before_work - order.paid) or order.remaining
                    amount = number("Nominal simulasi", suggested)
                    default_ref = "DEMO-" + uuid.uuid4().hex[:10]
                    ref = input(f"Referensi transaksi [{default_ref}]: ").strip() or default_ref
                    status = input("Status pending/settlement/expire/deny [settlement]: ").strip() or "settlement"
                    source = input("Sumber midtrans/qris/tunai [midtrans]: ").strip() or "midtrans"
                    store.simulate_payment(current, ref, amount, source="simulasi_" + source, status=status)
                elif choice == "5":
                    store.start_work(current, actor="operator-demo")
                elif choice == "6":
                    store.send_preview(current, "DEMO-pratinjau-watermark.pdf", actor="operator-demo")
                    print("Hanya mencatat tahap pratinjau; tidak membuat PDF atau watermark.")
                elif choice == "7":
                    correction = yes("Perbaikan kesalahan pihak penyedia (gratis, tidak memakai jatah)?")
                    note = input("Catatan revisi: ").strip()
                    store.request_revision(current, note, actor="operator-demo", correction=correction)
                elif choice == "8":
                    store.approve_preview(current, actor="pelanggan-demo")
                elif choice == "9":
                    store.release_final(current, "DEMO-final.docx + DEMO-final.pdf", actor="operator-demo")
                    print("Hanya mencatat izin penyerahan; tidak mengirim dokumen sungguhan.")
                elif choice == "10":
                    for event in store.events(current):
                        print(f"{event['created']} | {event['action']} | {event['detail']}")
                elif choice == "11":
                    store.cancel_unpaid(current, input("Alasan: "), actor="operator-demo")
                else:
                    print("Pilihan tidak dikenal.")
            except (ValueError, sqlite3.Error) as exc:
                print("\nTidak diproses: " + str(exc))
    finally:
        store.close()


def telegram_demo() -> None:
    """Mengetik pesan seolah chat owner; tidak membuka polling atau mengirim ke Telegram."""
    store = DemoStore(ROOT / "runtime" / "demo.sqlite3")
    try:
        order = store.create_order(make_quote(QuoteRequest()), approved_by="operator-demo")
        store.accept_quote(order.order_id, actor="pelanggan-demo")
        controller = DemoTelegramAdmin(store, admin_user_id=1, admin_chat_id=1)
        print("\nSIMULASI CHAT TELEGRAM - ini berjalan di terminal, bukan bot sungguhan.")
        print("Contoh pesanan dibuat; dalam skenario ini pelanggan sudah menyetujui harga.")
        show(store.get(order.order_id))
        print("\nCoba salin perintah berikut satu per satu:")
        print("/dp")
        print(f"/dp_konfirmasi {order.order_id} {order.required_before_work} DP-TEST-001-{order.order_id}")
        print(f"/pembayaran {order.order_id}")
        print("\nKetik /bantuan_pembayaran untuk perintah lain; 0 untuk keluar.")
        while True:
            text = input("\nAnda: ").strip()
            if text == "0":
                break
            reply = controller.handle(text, user_id=1, chat_id=1)
            print("Bot demo: " + (reply.text if reply else "Perintah tidak ditangani modul pembayaran."))
            if reply and reply.ready_order_id:
                print("[Pengait agen] Pesanan siap dikerjakan; Nara belum dijalankan dalam demo.")
    finally:
        store.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prototipe harga dan pembayaran Taqi - SIMULASI")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--sample", action="store_true", help="Skenario contoh otomatis tanpa menyimpan data")
    mode.add_argument("--telegram-demo", action="store_true", help="Simulasi chat admin Telegram di terminal")
    args = parser.parse_args(argv)
    print("=== DEMO TERPISAH: TIDAK MENERIMA PEMBAYARAN ASLI ===")
    try:
        if args.sample:
            sample()
        elif args.telegram_demo:
            telegram_demo()
        else:
            interactive()
    except (EOFError, KeyboardInterrupt):
        print("\nDemo ditutup. Data interaktif yang sudah tersimpan tetap tersedia.")
    except (ValueError, OSError, sqlite3.Error) as exc:
        print("Tidak dapat menjalankan demo: " + str(exc))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
