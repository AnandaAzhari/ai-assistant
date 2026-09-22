"""Harga usulan dalam rupiah bulat. Tidak memanggil AI atau layanan pembayaran."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config_harga.json"
MAX_AMOUNT = 1_000_000_000_000


def whole(value: object, label: str, minimum: int = 0, maximum: int = MAX_AMOUNT) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{label} harus bilangan bulat {minimum} sampai {maximum}.")
    return value


def percent_up(amount: int, percent: int) -> int:
    """Bulatkan pecahan rupiah ke atas tanpa floating point."""
    return (amount * percent + 99) // 100


def rupiah(amount: int) -> str:
    return "Rp" + f"{amount:,}".replace(",", ".")


@dataclass(frozen=True)
class QuoteRequest:
    service: str = "makalah"
    pages: int = 10
    package: str = "otomatis"
    formatting: str = "dasar"
    footnote_mode: str = "tidak"
    footnote_count: int = 0
    sources_to_verify: int = 0
    extra_revision_rounds: int = 0
    rush: bool = False


@dataclass(frozen=True)
class QuoteLine:
    description: str
    amount: int


@dataclass(frozen=True)
class Quote:
    config_version: str
    service: str
    pages: int
    lines: tuple[QuoteLine, ...]
    total: int
    required_before_work: int
    revision_rounds: int
    review_reasons: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)

    def validate(self) -> None:
        whole(self.total, "Total", 1)
        whole(self.required_before_work, "Pembayaran awal", 1, self.total)
        whole(self.revision_rounds, "Jatah revisi", 0, 100)
        if not self.lines or sum(whole(line.amount, "Rincian harga") for line in self.lines) != self.total:
            raise ValueError("Total tidak cocok dengan rincian penawaran.")


def _keys(data: object, expected: set[str], label: str) -> dict:
    if not isinstance(data, dict) or set(data) != expected:
        raise ValueError(f"Struktur {label} tidak sesuai template konfigurasi.")
    return data


def validate_config(data: object) -> dict:
    cfg = _keys(data, {
        "version", "status", "packages", "extra_page", "formatting", "footnotes",
        "source_verification_each", "extra_revision_round", "included_revision_rounds",
        "rush_percent", "payment",
    }, "konfigurasi")
    if not isinstance(cfg["version"], str) or not cfg["version"].strip():
        raise ValueError("Versi konfigurasi wajib diisi.")
    if cfg["status"] != "USULAN_UNTUK_UJI":
        raise ValueError("Prototipe ini hanya menerima konfigurasi USULAN_UNTUK_UJI.")
    packs = _keys(cfg["packages"], {"ringkas", "standar", "lengkap"}, "packages")
    previous_pages = previous_price = 0
    for name in ("ringkas", "standar", "lengkap"):
        pack = _keys(packs[name], {"pages", "price"}, f"paket {name}")
        pages = whole(pack["pages"], "Kapasitas paket", 1, 1000)
        price = whole(pack["price"], "Harga paket", 1)
        if pages <= previous_pages or price < previous_price:
            raise ValueError("Kapasitas paket harus meningkat dan harga tidak boleh menurun.")
        previous_pages, previous_price = pages, price
    levels = _keys(cfg["formatting"], {"dasar", "struktur", "khusus"}, "formatting")
    for level in levels.values():
        _keys(level, {"per_page", "minimum"}, "tingkat perapian")
        whole(level["per_page"], "Tarif per halaman", 1)
        whole(level["minimum"], "Minimum perapian", 1)
    notes = _keys(cfg["footnotes"], {
        "existing_each", "existing_minimum", "bundle_price", "bundle_count", "bundle_extra_each",
    }, "footnotes")
    for key, value in notes.items():
        whole(value, key, 1, 1000 if key == "bundle_count" else MAX_AMOUNT)
    for key in ("extra_page", "source_verification_each", "extra_revision_round"):
        whole(cfg[key], key, 1)
    whole(cfg["included_revision_rounds"], "Jatah revisi", 0, 50)
    whole(cfg["rush_percent"], "Persen layanan cepat", 0, 100)
    payment = _keys(cfg["payment"], {"full_payment_threshold", "deposit_percent"}, "payment")
    whole(payment["full_payment_threshold"], "Batas bayar penuh")
    whole(payment["deposit_percent"], "Persen DP", 1, 100)
    return cfg


def load_config(path: Path | str = DEFAULT_CONFIG) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Konfigurasi harga tidak dapat dibaca: {exc}") from exc
    return validate_config(data)


def make_quote(request: QuoteRequest, config: dict | None = None) -> Quote:
    cfg = load_config() if config is None else validate_config(config)
    whole(request.pages, "Jumlah halaman", 1, 1000)
    whole(request.footnote_count, "Jumlah footnote", 0, 1000)
    whole(request.sources_to_verify, "Jumlah sumber", 0, 1000)
    whole(request.extra_revision_rounds, "Tambahan revisi", 0, 50)
    if type(request.rush) is not bool:
        raise ValueError("Pilihan cepat harus true atau false.")
    if request.service not in ("makalah", "rapikan"):
        raise ValueError("Layanan harus makalah atau rapikan.")
    if request.package not in ("otomatis", "ringkas", "standar", "lengkap"):
        raise ValueError("Paket tidak dikenal.")
    if request.formatting not in ("dasar", "struktur", "khusus"):
        raise ValueError("Tingkat perapian tidak dikenal.")
    if request.footnote_mode not in ("tidak", "bundle", "rapikan"):
        raise ValueError("Pilihan footnote tidak dikenal.")
    if (request.footnote_mode == "tidak") != (request.footnote_count == 0):
        raise ValueError("Isi jumlah footnote jika memilih layanan footnote; selain itu gunakan nol.")
    lines: list[QuoteLine] = []
    reviews: list[str] = []
    if request.service == "makalah":
        if request.formatting != "dasar":
            raise ValueError("Makalah sudah termasuk format standar. Format khusus perlu penawaran manual.")
        if request.footnote_mode == "rapikan":
            raise ValueError("Untuk makalah baru pilih bundle footnote; tarif rapikan untuk dokumen pelanggan.")
        name = request.package
        if name == "otomatis":
            name = next((n for n in ("ringkas", "standar", "lengkap")
                         if request.pages <= cfg["packages"][n]["pages"]), "lengkap")
        pack = cfg["packages"][name]
        lines.append(QuoteLine(f"Makalah {name} (hingga {pack['pages']} halaman isi; format standar termasuk)", pack["price"]))
        extra = max(0, request.pages - pack["pages"])
        if extra:
            lines.append(QuoteLine(f"Tambahan {extra} halaman isi", extra * cfg["extra_page"]))
    else:
        if request.package != "otomatis":
            raise ValueError("Jasa rapikan tidak menggunakan paket makalah.")
        if request.footnote_mode == "bundle":
            raise ValueError("Bundle footnote hanya untuk paket makalah.")
        rate = cfg["formatting"][request.formatting]
        lines.append(QuoteLine(
            f"Rapikan {request.formatting}, {request.pages} halaman (minimum {rupiah(rate['minimum'])})",
            max(rate["minimum"], request.pages * rate["per_page"]),
        ))
        if request.formatting == "khusus":
            reviews.append("Periksa pedoman dan kerumitan dokumen; tarif khusus adalah harga mulai.")
    notes = cfg["footnotes"]
    if request.footnote_mode == "bundle":
        lines.append(QuoteLine(f"Bundle footnote, hingga {notes['bundle_count']} catatan dari sumber lengkap", notes["bundle_price"]))
        extra = max(0, request.footnote_count - notes["bundle_count"])
        if extra:
            lines.append(QuoteLine(f"Tambahan {extra} footnote di luar bundle", extra * notes["bundle_extra_each"]))
    elif request.footnote_mode == "rapikan":
        lines.append(QuoteLine(f"Rapikan {request.footnote_count} footnote dari data sumber lengkap",
                               max(notes["existing_minimum"], request.footnote_count * notes["existing_each"])))
    if request.sources_to_verify:
        lines.append(QuoteLine(f"Verifikasi {request.sources_to_verify} sumber (harga mulai)",
                               request.sources_to_verify * cfg["source_verification_each"]))
        reviews.append("Pastikan sumber dapat diperoleh dan sepakati lingkup verifikasi sebelum menetapkan harga.")
    if request.extra_revision_rounds:
        lines.append(QuoteLine(f"Tambahan {request.extra_revision_rounds} putaran revisi kecil (harga mulai)",
                               request.extra_revision_rounds * cfg["extra_revision_round"]))
        reviews.append("Sepakati lingkup revisi kecil tambahan; perubahan topik perlu penawaran baru.")
    if request.rush:
        lines.append(QuoteLine(f"Layanan cepat {cfg['rush_percent']}% dari subtotal jasa",
                               percent_up(sum(line.amount for line in lines), cfg["rush_percent"])))
        reviews.append("Operator harus menyetujui deadline dan memastikan kapasitas antrean.")
    total = sum(line.amount for line in lines)
    terms = cfg["payment"]
    initial = total if total <= terms["full_payment_threshold"] else percent_up(total, terms["deposit_percent"])
    quote = Quote(cfg["version"], request.service, request.pages, tuple(lines), total, initial,
                  cfg["included_revision_rounds"] + request.extra_revision_rounds, tuple(reviews))
    quote.validate()
    return quote
