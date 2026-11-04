"""SEC EDGAR filings for one ticker, and the latest filings across companies.

Company history comes from ``data.sec.gov`` submissions. The latest list is
EDGAR's current-filings atom feed. Both are the filing itself, not a headline
about it. The SEC requires a User-Agent that includes a name and email.
"""

from __future__ import annotations

import os
import re
from collections.abc import Sequence
from typing import Any
from xml.etree import ElementTree

import httpx

from datafeed.http import QuoteLookupError, request_json, with_client
from datafeed.rss import cap_limit, child_text, clean_query, local_name, story_summary, ticker_from_query

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
CURRENT_URL = "https://www.sec.gov/cgi-bin/browse-edgar"
SOURCE = "edgar"
DEFAULT_FORMS = ("8-K", "10-Q", "10-K", "4", "SC 13D", "SC 13G")
_USER_AGENT_ERROR = "Set SEC_USER_AGENT to a name and email. EDGAR requires it."
_TITLE = re.compile(r"^(?P<form>.+?) - (?P<company>.+?) \((?P<cik>\d+)\)")
_ACCESSION = re.compile(r"accession-number=(\d{10}-\d{2}-\d{6})")
_FILED = re.compile(r"Filed:\s*(\d{4}-\d{2}-\d{2})")


def resolve_user_agent(explicit: str | None) -> str:
    """``None`` reads ``SEC_USER_AGENT``. A string, including blank, is used as given."""
    if explicit is not None:
        return " ".join(explicit.split())
    return " ".join(os.environ.get("SEC_USER_AGENT", "").split())


def filing_link(accession: str) -> str:
    """Index page for one accession. The path CIK is the accession prefix."""
    prefix = accession.split("-", 1)[0]
    cik = str(int(prefix))
    folder = accession.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{folder}/{accession}-index.html"


def parse_tickers(payload: dict[str, Any]) -> dict[str, tuple[str, str]]:
    """Ticker to ``(cik, company name)``. CIK is the integer text, not zero-padded."""
    found: dict[str, tuple[str, str]] = {}
    for row in payload.values():
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper()
        cik = row.get("cik_str")
        if not ticker or isinstance(cik, bool) or cik is None:
            continue
        try:
            number = str(int(cik))
        except (TypeError, ValueError):
            continue
        found[ticker] = (number, str(row.get("title") or "").strip())
    return found


def _forms(forms: Sequence[str] | None) -> set[str] | None:
    """``None`` uses the material-form default. An empty list keeps every form."""
    chosen = DEFAULT_FORMS if forms is None else forms
    wanted = {form.strip().upper() for form in chosen if form and form.strip()}
    return wanted or None


def _matches(form: str, wanted: set[str] | None) -> bool:
    if wanted is None:
        return True
    name = form.strip().upper()
    if name in wanted:
        return True
    return any(name.startswith(f"{item}/") for item in wanted)


def _column(recent: dict[str, Any], name: str, index: int) -> str:
    values = recent.get(name)
    if not isinstance(values, list) or index >= len(values) or values[index] is None:
        return ""
    return " ".join(str(values[index]).split())


def parse_submissions(
    payload: dict[str, Any],
    *,
    ticker: str,
    limit: int,
    forms: Sequence[str] | None = None,
) -> list[dict[str, str]]:
    """Newest filings from one company's submissions payload."""
    filings = payload.get("filings") if isinstance(payload.get("filings"), dict) else {}
    recent = filings.get("recent") if isinstance(filings.get("recent"), dict) else {}
    form_column = recent.get("form")
    if not isinstance(form_column, list):
        return []
    company = str(payload.get("name") or "").strip()
    wanted = _forms(forms)
    items: list[dict[str, str]] = []
    cap = cap_limit(limit)
    for index, form in enumerate(form_column):
        form_name = str(form or "").strip()
        if not form_name or not _matches(form_name, wanted):
            continue
        accession = _column(recent, "accessionNumber", index)
        if not accession:
            continue
        item = {
            "form": form_name,
            "company": company,
            "ticker": ticker,
            "filed": _column(recent, "filingDate", index),
            "accepted": _column(recent, "acceptanceDateTime", index),
            "accession": accession,
            "link": filing_link(accession),
            "source": SOURCE,
        }
        description = _column(recent, "primaryDocDescription", index)
        if description:
            item["description"] = description
        detail = _column(recent, "items", index)
        if detail:
            item["items"] = detail
        items.append(item)
        if len(items) >= cap:
            break
    return items


def _category(entry: ElementTree.Element) -> str:
    for child in entry:
        if local_name(child.tag) == "category" and child.get("term"):
            return child.get("term", "").strip()
    return ""


def parse_current_atom(xml_text: str, *, limit: int) -> list[dict[str, str]]:
    """Newest filings from the current-filings atom feed."""
    root = ElementTree.fromstring(xml_text)
    cap = cap_limit(limit)
    items: list[dict[str, str]] = []
    for entry in root.iter():
        if local_name(entry.tag) != "entry":
            continue
        title = child_text(entry, "title")
        link = child_text(entry, "link")
        if link.startswith("/"):
            link = f"https://www.sec.gov{link}"
        matched = _TITLE.match(title)
        form = _category(entry) or (matched.group("form") if matched else "")
        company = matched.group("company") if matched else title
        accession_match = _ACCESSION.search(child_text(entry, "id"))
        accession = accession_match.group(1) if accession_match else ""
        if not link and accession:
            link = filing_link(accession)
        if not form or not link.startswith(("http://", "https://")):
            continue
        summary = story_summary(child_text(entry, "summary"), title=title)
        filed_match = _FILED.search(summary)
        item = {
            "form": form,
            "company": company,
            "filed": filed_match.group(1) if filed_match else "",
            "accepted": child_text(entry, "updated"),
            "link": link,
            "source": SOURCE,
        }
        if accession:
            item["accession"] = accession
        if summary:
            item["description"] = summary
        items.append({key: value for key, value in item.items() if value})
        if len(items) >= cap:
            break
    return items


def _ticker_candidates(ticker: str) -> list[str]:
    keys = [ticker]
    if "." in ticker:
        keys.append(ticker.replace(".", "-"))
    if "-" in ticker:
        keys.append(ticker.replace("-", "."))
    return keys


class EdgarFilings:
    """Filings for a ticker, or the newest filings of one form."""

    def __init__(self, client: httpx.Client | None = None, *, user_agent: str | None = None) -> None:
        self._client = client
        self._user_agent = resolve_user_agent(user_agent)
        self._tickers: dict[str, tuple[str, str]] | None = None

    def filings(
        self,
        query: str,
        *,
        limit: int = 25,
        forms: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        """Recent 8-K, 10-Q, 10-K, Form 4, and 13D/13G filings for a ticker.

        Pass ``forms`` to choose others. An empty list keeps every form.
        """
        cleaned = clean_query(query)
        ticker = ticker_from_query(cleaned)
        if ticker is None:
            return _failed(cleaned, "Query must be a ticker, for example AAPL.")
        if not self._user_agent:
            return _failed(ticker, _USER_AGENT_ERROR)
        try:
            company = self._company(ticker)
            if company is None:
                return _failed(ticker, f"No EDGAR company for {ticker}.")
            cik, _name = company
            payload = self._json(SUBMISSIONS_URL.format(cik=f"{int(cik):010d}"))
        except QuoteLookupError as exc:
            return _failed(ticker, f"EDGAR filings failed: {exc}")
        items = parse_submissions(payload, ticker=ticker, limit=limit, forms=forms)
        return {"query": ticker, "count": len(items), "items": items}

    def latest(self, *, limit: int = 25, form: str = "") -> dict[str, Any]:
        """Newest filings on EDGAR. ``form`` limits the atom feed, for example ``8-K``."""
        chosen = " ".join((form or "").split()).upper()
        label = chosen or "latest"
        if not self._user_agent:
            return _failed(label, _USER_AGENT_ERROR)
        params = {
            "action": "getcurrent",
            "type": chosen,
            "owner": "include",
            "count": str(cap_limit(limit)),
            "output": "atom",
        }
        try:
            xml_text = self._text(CURRENT_URL, params, accept="application/atom+xml")
        except QuoteLookupError as exc:
            return _failed(label, f"EDGAR filings failed: {exc}")
        try:
            items = parse_current_atom(xml_text, limit=limit)
        except ElementTree.ParseError:
            return _failed(label, "EDGAR feed was not readable.")
        return {"query": label, "count": len(items), "items": items}

    def _company(self, ticker: str) -> tuple[str, str] | None:
        if self._tickers is None:
            self._tickers = parse_tickers(self._json(TICKERS_URL))
        for key in _ticker_candidates(ticker):
            company = self._tickers.get(key)
            if company is not None:
                return company
        return None

    def _json(self, url: str) -> dict[str, Any]:
        headers = self._headers("application/json")
        return with_client(self._client, lambda http: request_json(http, "GET", url, headers=headers))

    def _text(self, url: str, params: dict[str, str], *, accept: str) -> str:
        def fetch(http: httpx.Client) -> str:
            try:
                response = http.get(url, params=params, headers=self._headers(accept))
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise QuoteLookupError(f"HTTP {exc.response.status_code}") from exc
            except httpx.HTTPError as exc:
                raise QuoteLookupError("network error") from exc
            if "Undeclared Automated Tool" in response.text[:800]:
                raise QuoteLookupError(_USER_AGENT_ERROR)
            return response.text

        return with_client(self._client, fetch)

    def _headers(self, accept: str) -> dict[str, str]:
        return {"User-Agent": self._user_agent, "Accept": accept}


def _failed(query: str, message: str) -> dict[str, Any]:
    return {"query": query, "count": 0, "items": [], "error": message}
