"""Pengendali admin Telegram yang dapat diuji tanpa bot/token/jaringan.

Masukan identitas harus berasal dari update Telegram terautentikasi di runtime
sebenarnya. Kelas ini belum terpasang pada bot utama dan seluruh uang adalah demo.
"""
from __future__ import annotations

from dataclasses import dataclass

from .payment_flow import DemoStore, LABELS, OrderView
from .pricing import rupiah, whole

COMMANDS = {
    "/dp", "/pembayaran", "/dp_konfirmasi", "/lunas_konfirmasi",
    "/bantuan_pembayaran", "/simulasi_midtrans",
}


@dataclass(frozen=True)
class AdminReply:
    text: str
    # Sinyal untuk pengait Nara di integrasi mendatang; bukan eksekusi Nara.
    ready_order_id: str | None = None


def payment_summary(order: OrderView) -> str:
    initial_label = "Bayar penuh sebelum mulai" if order.required_before_work == order.total else "DP sebelum mulai"
    payment_state = "Lunas" if order.remaining == 0 else ("Belum dibayar" if order.paid == 0 else "Dibayar sebagian")
    return (
        f"[SIMULASI] {order.order_id}\n"
        f"Status: {LABELS[order.status]}\n"
        f"Status pembayaran: {payment_state}\n"
        f"Total tagihan: {rupiah(order.total)}\n"
        f"{initial_label}: {rupiah(order.required_before_work)}\n"
        f"Pembayaran tercatat: {rupiah(order.paid)}\n"
        f"Sisa tagihan: {rupiah(order.remaining)}\n"
        f"Syarat pembayaran awal: {'terpenuhi' if order.paid >= order.required_before_work else 'belum terpenuhi'}"
    )


class DemoTelegramAdmin:
    """Owner saja, chat pribadi saja; perintah lain dikembalikan ke router lama."""

    def __init__(self, store: DemoStore, *, admin_user_id: int, admin_chat_id: int):
        self.store = store
        self.admin_user_id = whole(admin_user_id, "ID Telegram owner", 1)
        self.admin_chat_id = whole(admin_chat_id, "ID chat pribadi owner", 1)

    def payment_notice(self, order_id: str) -> AdminReply:
        """Format notifikasi setelah penyimpanan pembayaran terverifikasi oleh adapter.

        Tidak mengubah uang/status. Dispatcher nyata harus mengirimnya hanya ke
        admin_chat_id yang dikonfigurasi, memakai antrean persisten dan retry.
        """
        return AdminReply("Pembaruan pembayaran\n" + payment_summary(self.store.get(order_id)))

    def handle(self, text: str, *, user_id: int, chat_id: int, chat_type: str = "private") -> AdminReply | None:
        if (type(user_id) is not int or type(chat_id) is not int
                or user_id != self.admin_user_id or chat_id != self.admin_chat_id or chat_type != "private"):
            return None
        if not isinstance(text, str) or not text.strip():
            return None
        parts = text.strip().split()
        command = parts[0].split("@", 1)[0].lower()
        if command not in COMMANDS:
            return None
        if len(text) > 2000:
            return AdminReply("Perintah pembayaran terlalu panjang.")
        try:
            if command == "/bantuan_pembayaran":
                return AdminReply(
                    "[SIMULASI ADMIN TELEGRAM]\n"
                    "/dp — pesanan yang masih menunggu pembayaran awal\n"
                    "/dp ID — cek DP satu pesanan\n"
                    "/pembayaran [ID] — cek total, pembayaran, dan sisa\n"
                    "/dp_konfirmasi ID NOMINAL REFERENSI\n"
                    "/lunas_konfirmasi ID NOMINAL REFERENSI\n"
                    "Konfirmasi manual digunakan setelah memeriksa uang masuk di aplikasi merchant.\n"
                    "/simulasi_midtrans ID NOMINAL REFERENSI [pending|settlement|expire|deny]\n"
                    "Perintah terakhir hanya alat demo, bukan konfirmasi Midtrans sungguhan."
                )
            if command in ("/dp", "/pembayaran"):
                if len(parts) > 2:
                    raise ValueError(f"Format: {command} [ID_PESANAN]")
                if len(parts) == 2:
                    return AdminReply(payment_summary(self.store.get(parts[1])))
                orders = self.store.list_orders()
                if command == "/dp":
                    orders = [order for order in orders if order.stage == "accepted" and not order.can_start]
                if not orders:
                    return AdminReply("[SIMULASI] Tidak ada pesanan yang sesuai. Gunakan /pembayaran ID untuk detail.")
                # Balasan ringkas agar jauh di bawah batas pesan Telegram.
                lines = ["[SIMULASI] " + ("Menunggu pembayaran awal:" if command == "/dp" else "Pembayaran terbaru:")]
                for order in orders[:10]:
                    lines.append(f"{order.order_id}: {LABELS[order.status]} | masuk {rupiah(order.paid)} | sisa {rupiah(order.remaining)}")
                if len(orders) > 10:
                    lines.append(f"Ditampilkan 10 dari {len(orders)}. Gunakan /pembayaran ID untuk pesanan lain.")
                return AdminReply("\n".join(lines))
            expected = (4, 5) if command == "/simulasi_midtrans" else (4,)
            if len(parts) not in expected:
                raise ValueError(f"Format: {command} ID_PESANAN NOMINAL REFERENSI" +
                                 (" [STATUS]" if command == "/simulasi_midtrans" else ""))
            if not parts[2].isascii() or not parts[2].isdigit():
                raise ValueError("Nominal harus angka rupiah utuh tanpa titik, contoh 18000.")
            amount = int(parts[2])
            status = parts[4] if len(parts) == 5 else "settlement"
            source = "simulasi_midtrans" if command == "/simulasi_midtrans" else "simulasi_qris"
            update = self.store.simulate_payment_update(parts[1], parts[3], amount, source=source,
                                                        status=status, actor=f"telegram-owner:{user_id}")
            order = update.order
            became_ready = update.ready_for_work
            message = ("Konfirmasi manual QRIS (SIMULASI)" if source == "simulasi_qris"
                       else f"Notifikasi Midtrans {status} (SIMULASI)")
            message += "\n" + payment_summary(order)
            if became_ready:
                message += "\nPembayaran awal cukup. Siap diteruskan ke Nara setelah integrasi."
            if not update.credited_amount:
                message += "\nTidak ada tambahan pemasukan (status belum sukses atau transaksi sudah tercatat)."
            return AdminReply(message, order.order_id if became_ready else None)
        except ValueError as exc:
            return AdminReply("Tidak diproses: " + str(exc))
