"""Pricing / Quote Engine — kalkulator harga otomatis untuk paket makalah,
jasa rapikan dokumen pelanggan, dan tambahan (footnote/rush), diadaptasi dari
prototipe billing ChatGPT (`chatgpt_billing/pricing.py`, lihat catatan
keputusan di project doc "riset-provider-lead-agent-personal-assistant.md")
supaya harga TIDAK PERNAH dihitung/dikarang AI — murni kode deterministik.

Beda dengan prototipe aslinya yang memakai file `config_harga.json` statis,
konfigurasi di sini disimpan di SQLite lewat `PricingConfigStore`, supaya bisa
diubah admin langsung lewat command Telegram/Web Admin (`/paket_set`,
`/paket_hapus`, `/tarif_set` di `app/lead.py`) tanpa akses server sama sekali —
konsisten dengan pola `PriceListStore`/`KillSwitch` yang sudah ada di paket ini.
Nilai bawaan (seed) memakai angka usulan yang sama seperti prototipe ChatGPT
(lihat `README.md` folder prototipe), tapi statusnya di sini BUKAN "usulan
tetap" — admin bisa mengubahnya kapan pun lewat command, dan perubahan hanya
berlaku untuk penawaran BARU dihitung setelahnya. Belum ada objek "order" yang
menyimpan snapshot penawaran per pesanan pada tahap ini — itu jadi pekerjaan
lanjutan tersendiri kalau/ketika modul ini disambungkan ke alur order sungguhan
(lihat catatan integrasi di `app/dp_policy.py`).

CATATAN PENYEDERHANAAN dari prototipe asli: bundle footnote di sini memakai
SATU struktur tarif (bundle + tarif lanjutan) untuk mode makalah MAUPUN mode
rapikan dokumen pelanggan, sedangkan prototipe ChatGPT membedakan keduanya
(tarif bundle untuk makalah, tarif per-catatan terpisah untuk rapikan). Ini
penyederhanaan sadar supaya modul tetap ringkas di tahap ini — bisa dipisah
lagi nanti kalau memang dibutuhkan.

`make_quote()` murni fungsi kode: menerima `QuoteRequest` + `PricingConfig`
lalu mengembalikan `Quote` immutable berisi rincian harga integer rupiah
(tidak ada float sama sekali, sama seperti prototipe aslinya). DP (uang muka)
yang dihitung di sini HANYA angka referensi (`Quote.dp_amount`/`Quote.sisa`)
— apakah DP itu benar-benar WAJIB dibayar sebelum pekerjaan dimulai diatur
terpisah lewat `app/dp_policy.py` (`DpPolicyStore`), supaya modul harga dan
kebijakan "wajib/opsional"-nya tidak saling mengunci satu sama lain.
"""

from __future__ import annotations

import math
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator

TIDY_LEVELS = ("dasar", "struktur", "khusus")

# Kunci setting skalar yang dikenal, dengan nilai bawaan (seed) — angka yang
# sama seperti "usulan" di prototipe ChatGPT (lihat README.md folder
# prototipe), supaya hasil hitung tetap masuk akal sebelum admin sempat
# menyesuaikan. `/tarif_set` di app/lead.py HANYA menerima key dari daftar ini.
_DEFAULT_SETTINGS: dict[str, int] = {
    "halaman_tambahan": 6000,
    "rapikan_dasar_per_halaman": 2000,
    "rapikan_dasar_minimum": 15000,
    "rapikan_struktur_per_halaman": 3500,
    "rapikan_struktur_minimum": 25000,
    "rapikan_khusus_per_halaman": 5000,
    "rapikan_khusus_minimum": 40000,
    "footnote_bundle_harga": 15000,
    "footnote_bundle_batas": 10,
    "footnote_lanjutan_per_catatan": 1000,
    "rush_persen": 30,
    "dp_ambang": 35000,
    "dp_persen": 30,
}

PRICING_SETTING_KEYS: frozenset[str] = frozenset(_DEFAULT_SETTINGS)

_DEFAULT_PACKAGES: tuple[tuple[str, int, int], ...] = (
    ("Ringkas", 5, 35000),
    ("Standar", 10, 60000),
    ("Lengkap", 15, 90000),
)

_PERCENT_KEYS = {"rush_persen", "dp_persen"}


def _round_up_rupiah(value: float) -> int:
    """Bulatkan ke atas ke rupiah utuh, dengan epsilon kecil supaya noise
    floating-point (mis. 18000.000000000002 dari perkalian persen) tidak
    salah kebulet jadi 18001."""
    return int(math.ceil(value - 1e-9))


@dataclass(frozen=True)
class PackageTier:
    name: str
    page_limit: int
    price: int


@dataclass(frozen=True)
class PricingConfig:
    packages: tuple[PackageTier, ...]
    settings: dict[str, int]


@dataclass(frozen=True)
class QuoteRequest:
    """Salah satu dari `pages` (mode makalah) atau `tidy_level`+`tidy_pages`
    (mode rapikan dokumen pelanggan) wajib diisi — keduanya alternatif, tidak
    ditumpuk, sama seperti aturan asli di README.md prototipe ChatGPT."""

    pages: int = 0
    package_name: str | None = None  # None = pilih paket terkecil yang cukup otomatis
    tidy_level: str | None = None
    tidy_pages: int = 0
    footnote_count: int = 0
    rush: bool = False


@dataclass(frozen=True)
class Quote:
    mode: str  # "makalah" | "rapikan"
    label: str
    base_price: int
    footnote_fee: int
    rush_fee: int
    total: int
    dp_amount: int  # jumlah yang perlu ditagih di depan (referensi, lihat app/dp_policy.py)
    sisa: int  # 0 kalau total <= ambang DP (bayar penuh di depan)
    review_reasons: tuple[str, ...] = ()


def make_quote(request: QuoteRequest, config: PricingConfig) -> Quote:
    makalah_mode = request.pages > 0
    rapikan_mode = bool(request.tidy_level)
    if makalah_mode == rapikan_mode:
        raise ValueError(
            "Isi salah satu saja: `pages` (mode makalah) atau `tidy_level`+`tidy_pages` "
            "(mode rapikan dokumen pelanggan) — keduanya tidak bisa ditumpuk."
        )

    review_reasons: list[str] = []
    if makalah_mode:
        base_price, label = _quote_makalah(request, config, review_reasons)
    else:
        base_price, label = _quote_rapikan(request, config, review_reasons)

    footnote_fee = _footnote_fee(request.footnote_count, config.settings)
    subtotal = base_price + footnote_fee

    rush_fee = 0
    if request.rush:
        rush_fee = _round_up_rupiah(subtotal * config.settings["rush_persen"] / 100)

    total = subtotal + rush_fee
    dp_amount, sisa = _split_dp(total, config.settings)

    return Quote(
        mode="makalah" if makalah_mode else "rapikan",
        label=label,
        base_price=base_price,
        footnote_fee=footnote_fee,
        rush_fee=rush_fee,
        total=total,
        dp_amount=dp_amount,
        sisa=sisa,
        review_reasons=tuple(review_reasons),
    )


def _quote_makalah(request: QuoteRequest, config: PricingConfig, review_reasons: list[str]) -> tuple[int, str]:
    pages = request.pages
    if pages <= 0:
        raise ValueError("Jumlah halaman isi wajib lebih dari 0.")
    packages_sorted = sorted(config.packages, key=lambda tier: tier.page_limit)
    if not packages_sorted:
        raise ValueError("Belum ada paket harga tersimpan. Tambah dulu dengan /paket_set.")

    if request.package_name:
        tier = next(
            (t for t in packages_sorted if t.name.casefold() == request.package_name.casefold()), None
        )
        if tier is None:
            raise ValueError(f"Paket '{request.package_name}' tidak ditemukan.")
    else:
        tier = next((t for t in packages_sorted if pages <= t.page_limit), packages_sorted[-1])
        if pages > packages_sorted[-1].page_limit:
            review_reasons.append(
                f"Halaman ({pages}) melebihi paket terbesar ('{packages_sorted[-1].name}', "
                f"{packages_sorted[-1].page_limit} halaman) — pertimbangkan penawaran khusus."
            )

    extra_pages = max(0, pages - tier.page_limit)
    base_price = tier.price + extra_pages * config.settings["halaman_tambahan"]
    label = f"Makalah {pages} halaman isi (paket {tier.name}" + (
        f" + {extra_pages} halaman tambahan)" if extra_pages else ")"
    )
    return base_price, label


def _quote_rapikan(request: QuoteRequest, config: PricingConfig, review_reasons: list[str]) -> tuple[int, str]:
    level = (request.tidy_level or "").casefold()
    if level not in TIDY_LEVELS:
        raise ValueError(f"tidy_level harus salah satu dari: {', '.join(TIDY_LEVELS)}.")
    if request.tidy_pages <= 0:
        raise ValueError("Jumlah halaman dokumen yang dirapikan wajib lebih dari 0.")
    per_page = config.settings[f"rapikan_{level}_per_halaman"]
    minimum = config.settings[f"rapikan_{level}_minimum"]
    base_price = max(request.tidy_pages * per_page, minimum)
    if level == "khusus":
        review_reasons.append(
            "Tarif rapikan 'khusus' memerlukan pemeriksaan operator sebelum ditawarkan ke pelanggan."
        )
    label = f"Rapikan dokumen ({level}), {request.tidy_pages} halaman"
    return base_price, label


def _footnote_fee(footnote_count: int, settings: dict[str, int]) -> int:
    if footnote_count <= 0:
        return 0
    bundle_limit = settings["footnote_bundle_batas"]
    if footnote_count <= bundle_limit:
        return settings["footnote_bundle_harga"]
    extra = footnote_count - bundle_limit
    return settings["footnote_bundle_harga"] + extra * settings["footnote_lanjutan_per_catatan"]


def _split_dp(total: int, settings: dict[str, int]) -> tuple[int, int]:
    if total <= settings["dp_ambang"]:
        return total, 0
    dp_amount = _round_up_rupiah(total * settings["dp_persen"] / 100)
    return dp_amount, total - dp_amount


class PricingConfigStore:
    """Konfigurasi kalkulator harga, tersimpan SQLite, diedit admin lewat
    command Telegram/Web Admin (`/paket_set`, `/paket_hapus`, `/tarif_set` di
    `app/lead.py`) — bukan file JSON statis yang perlu akses server."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS pricing_package (
                    name TEXT PRIMARY KEY,
                    page_limit INTEGER NOT NULL,
                    price INTEGER NOT NULL,
                    updated_by TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS pricing_setting (
                    key TEXT PRIMARY KEY,
                    value INTEGER NOT NULL,
                    updated_by TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                )"""
            )
            self._seed_defaults(db)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Buka transaksi SQLite dan selalu tutup handle file setelah dipakai.

        sqlite3.Connection sebagai context manager hanya commit/rollback; ia tidak
        menutup koneksi. Pada Windows hal itu membuat file database sementara tetap
        terkunci sehingga TemporaryDirectory gagal dibersihkan (WinError 32) — lihat
        pola yang sama di app/document_preferences.py.
        """
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _seed_defaults(self, db: sqlite3.Connection) -> None:
        """Isi nilai bawaan HANYA sekali, kalau tabelnya masih benar-benar
        kosong (instalasi baru) — supaya kalkulator langsung bisa dipakai
        tanpa admin harus setting semua angka dari nol dulu. Tidak pernah
        menimpa nilai yang sudah pernah diubah admin (dicek per-tabel, bukan
        cuma sekali saat __init__ pertama, supaya aman dipanggil berkali-kali
        dari proses berbeda yang share database yang sama)."""
        now = datetime.now().isoformat(timespec="seconds")
        package_count = db.execute("SELECT COUNT(*) AS n FROM pricing_package").fetchone()["n"]
        if package_count == 0:
            for name, page_limit, price in _DEFAULT_PACKAGES:
                db.execute(
                    "INSERT INTO pricing_package (name, page_limit, price, updated_by, updated_at) VALUES (?,?,?,?,?)",
                    (name, page_limit, price, "system:seed", now),
                )
        setting_count = db.execute("SELECT COUNT(*) AS n FROM pricing_setting").fetchone()["n"]
        if setting_count == 0:
            for key, value in _DEFAULT_SETTINGS.items():
                db.execute(
                    "INSERT INTO pricing_setting (key, value, updated_by, updated_at) VALUES (?,?,?,?)",
                    (key, value, "system:seed", now),
                )

    # -- Paket (mode makalah) ------------------------------------------------

    def set_package(self, name: str, page_limit: int, price: int, *, updated_by: str) -> PackageTier:
        name = (name or "").strip()
        if not name:
            raise ValueError("Nama paket wajib diisi.")
        if page_limit <= 0:
            raise ValueError("Batas halaman paket wajib lebih dari 0.")
        if price <= 0:
            raise ValueError("Harga paket wajib lebih dari 0.")
        updated_by = (updated_by or "").strip()
        if not updated_by:
            raise ValueError("updated_by wajib diisi agar audit trail jelas.")
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as db:
            db.execute(
                """INSERT INTO pricing_package (name, page_limit, price, updated_by, updated_at)
                   VALUES (?,?,?,?,?)
                   ON CONFLICT(name) DO UPDATE SET
                       page_limit=excluded.page_limit, price=excluded.price,
                       updated_by=excluded.updated_by, updated_at=excluded.updated_at""",
                (name, page_limit, price, updated_by, now),
            )
        return PackageTier(name, page_limit, price)

    def remove_package(self, name: str) -> bool:
        with self._connect() as db:
            cursor = db.execute("DELETE FROM pricing_package WHERE name = ?", ((name or "").strip(),))
            return cursor.rowcount > 0

    def list_packages(self) -> list[PackageTier]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT name, page_limit, price FROM pricing_package ORDER BY page_limit"
            ).fetchall()
        return [PackageTier(row["name"], row["page_limit"], row["price"]) for row in rows]

    # -- Setting skalar (tarif tambahan, rush, ambang/persen DP) -------------

    def set_setting(self, key: str, value: int, *, updated_by: str) -> int:
        key = (key or "").strip()
        if key not in _DEFAULT_SETTINGS:
            raise ValueError(f"Kunci tarif '{key}' tidak dikenal. Pilihan: {', '.join(sorted(_DEFAULT_SETTINGS))}.")
        if value < 0:
            raise ValueError("Nilai tarif tidak boleh negatif.")
        if key in _PERCENT_KEYS and value > 100:
            raise ValueError(f"'{key}' adalah persentase, maksimal 100.")
        updated_by = (updated_by or "").strip()
        if not updated_by:
            raise ValueError("updated_by wajib diisi agar audit trail jelas.")
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as db:
            db.execute(
                """INSERT INTO pricing_setting (key, value, updated_by, updated_at)
                   VALUES (?,?,?,?)
                   ON CONFLICT(key) DO UPDATE SET
                       value=excluded.value, updated_by=excluded.updated_by, updated_at=excluded.updated_at""",
                (key, value, updated_by, now),
            )
        return value

    def all_settings(self) -> dict[str, int]:
        with self._connect() as db:
            rows = db.execute("SELECT key, value FROM pricing_setting").fetchall()
        return {row["key"]: row["value"] for row in rows}

    def load_config(self) -> PricingConfig:
        return PricingConfig(packages=tuple(self.list_packages()), settings=self.all_settings())
