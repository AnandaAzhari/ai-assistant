"""Research Manager v0.1.

Mencari sumber akademik nyata tanpa memakai token model AI.
Tahap awal memakai OpenAlex + Crossref, lalu menggabungkan dan menghapus duplikat
berdasarkan DOI/judul. Google Scholar tidak discrape otomatis.
"""

from __future__ import annotations

import json
import math
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchSource:
    provider: str
    title: str
    authors: tuple[str, ...] = ()
    year: int | None = None
    venue: str = ""
    doi: str = ""
    url: str = ""
    work_type: str = ""
    cited_by_count: int = 0
    is_open_access: bool = False
    score: float = 0.0


@dataclass(frozen=True)
class ResearchResult:
    status: str
    query: str
    sources: tuple[ResearchSource, ...] = ()
    warning: str = ""


class ResearchManager:
    OPENALEX_URL = "https://api.openalex.org/works"
    CROSSREF_URL = "https://api.crossref.org/works"

    def __init__(
        self,
        *,
        openalex_api_key: str = "",
        crossref_mailto: str = "",
        timeout: int = 15,
    ):
        self.openalex_api_key = (openalex_api_key or "").strip()
        self.crossref_mailto = (crossref_mailto or "").strip()
        self.timeout = max(5, int(timeout))

    @classmethod
    def from_env(cls) -> "ResearchManager":
        return cls(
            openalex_api_key=os.environ.get("OPENALEX_API_KEY", ""),
            crossref_mailto=os.environ.get("CROSSREF_MAILTO", ""),
            timeout=int(os.environ.get("RESEARCH_HTTP_TIMEOUT", "15") or 15),
        )

    @property
    def status_text(self) -> str:
        oa = "OpenAlex siap"
        if self.openalex_api_key:
            oa += " (API key aktif)"
        cr = "Crossref siap"
        if self.crossref_mailto:
            cr += " (polite pool)"
        return f"Research Manager siap. {oa}; {cr}."

    @staticmethod
    def _clean_text(value: object) -> str:
        text = str(value or "")
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _normalize_doi(value: str) -> str:
        doi = (value or "").strip().lower()
        doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi)
        doi = re.sub(r"^doi:\s*", "", doi)
        return doi.strip()

    @classmethod
    def _normalize_title(cls, value: str) -> str:
        text = cls._clean_text(value).casefold()
        text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _query_tokens(query: str) -> set[str]:
        return {
            token for token in re.findall(r"[a-z0-9à-ÿ]+", query.casefold())
            if len(token) >= 3
        }

    @classmethod
    def _relevance_score(cls, source: ResearchSource, query: str) -> float:
        q = cls._query_tokens(query)
        title_tokens = cls._query_tokens(source.title)
        overlap = len(q & title_tokens) / max(1, len(q))
        score = overlap * 70.0

        type_lower = source.work_type.casefold()
        if any(token in type_lower for token in ("journal", "article", "book", "proceedings")):
            score += 8.0
        if source.doi:
            score += 7.0
        if source.venue:
            score += 3.0
        if source.is_open_access:
            score += 3.0
        if source.cited_by_count > 0:
            score += min(9.0, math.log10(source.cited_by_count + 1) * 4.0)
        return round(score, 3)

    def _get_json(self, url: str) -> dict:
        headers = {
            "Accept": "application/json",
            "User-Agent": "TaqiAI-ResearchManager/0.1",
        }
        if self.crossref_mailto:
            headers["User-Agent"] += f" (mailto:{self.crossref_mailto})"
        request = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            payload = response.read()
        return json.loads(payload.decode("utf-8"))

    @staticmethod
    def _openalex_authors(item: dict) -> tuple[str, ...]:
        authors: list[str] = []
        for authorship in item.get("authorships") or []:
            name = ((authorship.get("author") or {}).get("display_name") or "").strip()
            if name and name not in authors:
                authors.append(name)
        return tuple(authors[:12])

    def _search_openalex(self, query: str, rows: int) -> list[ResearchSource]:
        params = {
            "search": query,
            "per_page": str(max(1, min(rows, 25))),
        }
        if self.openalex_api_key:
            params["api_key"] = self.openalex_api_key
        url = self.OPENALEX_URL + "?" + urllib.parse.urlencode(params)
        data = self._get_json(url)
        results: list[ResearchSource] = []
        for item in data.get("results") or []:
            title = self._clean_text(item.get("display_name") or item.get("title"))
            if not title:
                continue
            primary_location = item.get("primary_location") or {}
            source_meta = primary_location.get("source") or {}
            venue = self._clean_text(source_meta.get("display_name"))
            doi = self._normalize_doi(item.get("doi") or "")
            open_access = item.get("open_access") or {}
            url_value = ""
            if doi:
                url_value = f"https://doi.org/{doi}"
            elif primary_location.get("landing_page_url"):
                url_value = self._clean_text(primary_location.get("landing_page_url"))
            else:
                url_value = self._clean_text(item.get("id"))
            source = ResearchSource(
                provider="OpenAlex",
                title=title,
                authors=self._openalex_authors(item),
                year=item.get("publication_year") if isinstance(item.get("publication_year"), int) else None,
                venue=venue,
                doi=doi,
                url=url_value,
                work_type=self._clean_text(item.get("type")),
                cited_by_count=int(item.get("cited_by_count") or 0),
                is_open_access=bool(open_access.get("is_oa")),
            )
            results.append(source)
        return results

    @staticmethod
    def _crossref_year(item: dict) -> int | None:
        for key in ("published-print", "published-online", "published", "issued", "created"):
            value = item.get(key) or {}
            parts = value.get("date-parts") or []
            if parts and parts[0] and isinstance(parts[0][0], int):
                return parts[0][0]
        return None

    @staticmethod
    def _crossref_authors(item: dict) -> tuple[str, ...]:
        authors: list[str] = []
        for author in item.get("author") or []:
            literal = (author.get("name") or "").strip()
            if not literal:
                given = (author.get("given") or "").strip()
                family = (author.get("family") or "").strip()
                literal = " ".join(part for part in (given, family) if part)
            if literal and literal not in authors:
                authors.append(literal)
        return tuple(authors[:12])

    def _search_crossref(self, query: str, rows: int) -> list[ResearchSource]:
        params = {
            "query.bibliographic": query,
            "rows": str(max(1, min(rows, 20))),
        }
        if self.crossref_mailto:
            params["mailto"] = self.crossref_mailto
        url = self.CROSSREF_URL + "?" + urllib.parse.urlencode(params)
        data = self._get_json(url)
        items = ((data.get("message") or {}).get("items") or [])
        results: list[ResearchSource] = []
        for item in items:
            title_values = item.get("title") or []
            title = self._clean_text(title_values[0] if title_values else "")
            if not title:
                continue
            doi = self._normalize_doi(item.get("DOI") or "")
            container = item.get("container-title") or []
            venue = self._clean_text(container[0] if container else "")
            url_value = f"https://doi.org/{doi}" if doi else self._clean_text(item.get("URL"))
            source = ResearchSource(
                provider="Crossref",
                title=title,
                authors=self._crossref_authors(item),
                year=self._crossref_year(item),
                venue=venue,
                doi=doi,
                url=url_value,
                work_type=self._clean_text(item.get("type")),
                cited_by_count=int(item.get("is-referenced-by-count") or 0),
                is_open_access=False,
            )
            results.append(source)
        return results

    @classmethod
    def _dedupe(cls, sources: list[ResearchSource]) -> list[ResearchSource]:
        output: list[ResearchSource] = []
        seen_doi: set[str] = set()
        seen_title: set[str] = set()
        for source in sources:
            doi = cls._normalize_doi(source.doi)
            title = cls._normalize_title(source.title)
            if doi and doi in seen_doi:
                continue
            if title and title in seen_title:
                continue
            if doi:
                seen_doi.add(doi)
            if title:
                seen_title.add(title)
            output.append(source)
        return output

    def search(self, query: str, *, limit: int = 10) -> ResearchResult:
        clean_query = self._clean_text(query)
        if len(clean_query) < 3:
            return ResearchResult("membutuhkan_bantuan", clean_query, warning="Topik riset terlalu pendek.")

        per_provider = max(5, min(12, int(limit) + 2))
        found: list[ResearchSource] = []
        warnings: list[str] = []

        try:
            found.extend(self._search_openalex(clean_query, per_provider))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            warnings.append(f"OpenAlex belum berhasil: {exc}")

        try:
            found.extend(self._search_crossref(clean_query, per_provider))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            warnings.append(f"Crossref belum berhasil: {exc}")

        unique = self._dedupe(found)
        scored = [
            ResearchSource(**{**source.__dict__, "score": self._relevance_score(source, clean_query)})
            for source in unique
        ]
        scored.sort(key=lambda item: (item.score, item.cited_by_count, item.year or 0), reverse=True)
        selected = tuple(scored[: max(1, min(int(limit), 20))])

        if not selected:
            return ResearchResult(
                "gagal",
                clean_query,
                warning="; ".join(warnings) or "Tidak ada sumber yang ditemukan.",
            )
        return ResearchResult("berhasil", clean_query, selected, "; ".join(warnings))

    @staticmethod
    def format_result(result: ResearchResult) -> str:
        if result.status != "berhasil":
            return result.warning or "Research Manager belum menemukan sumber."
        lines = [f"Ditemukan {len(result.sources)} kandidat sumber untuk: **{result.query}**"]
        for index, source in enumerate(result.sources, start=1):
            authors = ", ".join(source.authors[:3]) or "Penulis tidak tercantum"
            if len(source.authors) > 3:
                authors += " dkk."
            year = str(source.year) if source.year else "tanpa tahun"
            venue = f" — {source.venue}" if source.venue else ""
            doi = f" | DOI: {source.doi}" if source.doi else ""
            lines.append(f"{index}. **{source.title}** — {authors} ({year}){venue}{doi}")
        if result.warning:
            lines.append(f"\nCatatan: {result.warning}")
        lines.append("\nDaftar ini berasal dari metadata akademik nyata dan belum otomatis dimasukkan ke makalah sebelum tahap verifikasi/source registry.")
        return "\n".join(lines)
