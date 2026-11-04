"""OpenSearch documents for one current event.

Each document is one retrieval passage. A RAG pipeline embeds ``text`` and
uses ``id`` as the OpenSearch document id, so collecting the same story
again updates that hit instead of inserting a second one.

S3 keeps these as newline-delimited JSON (one document per line) under
``current-events/date=YYYY-MM-DD/``. OpenSearch Ingestion can read that
prefix with the newline codec and send ``id`` through as ``document_id``.
The index mapping and ingest pipeline live in ``opensearch/``.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from datafeed.rss import published_at as parse_published

INDEX_NAME = "current-events"
SCHEMA_VERSION = 1
TEXT_FIELD = "text"
ID_FIELD = "id"


def to_document(
    item: dict[str, Any],
    *,
    feed: str,
    category: str,
    symbols: list[str],
    collected_at: datetime,
) -> dict[str, Any] | None:
    """One headline or release, or None when it has no title and link."""
    title = _text(item.get("title"))
    url = _text(item.get("link") or item.get("url"))
    if not title or not url.startswith(("http://", "https://")):
        return None
    source = _text(item.get("source")) or feed
    summary = _text(item.get("summary"))
    moment = _aware(collected_at)
    document: dict[str, Any] = {
        "id": document_id(url=url, title=title, source=source),
        "schema_version": SCHEMA_VERSION,
        "text": passage(title=title, summary=summary, source=source),
        "title": title,
        "source": source,
        "feed": feed,
        "url": url,
        "collected_at": _iso(moment),
        "collected_on": moment.strftime("%Y-%m-%d"),
        "category": _category(category),
        "symbols": _symbols(symbols),
    }
    if summary and summary.casefold() != title.casefold():
        document["summary"] = summary
    published = event_timestamp(_text(item.get("published")))
    if published is not None:
        document["published_at"] = published
    return document


def document_id(*, url: str, title: str, source: str) -> str:
    """Stable id from the link, so the same story keeps one OpenSearch id."""
    identity = url.strip() or f"{source.strip()}\n{title.strip()}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def passage(*, title: str, summary: str, source: str) -> str:
    """The field a neural ingest pipeline embeds and a RAG query retrieves."""
    blocks = [title.strip()]
    body = summary.strip()
    if body and body.casefold() != title.strip().casefold():
        blocks.append(body)
    outlet = source.strip()
    if outlet:
        blocks.append(f"Source: {outlet}")
    return "\n\n".join(blocks)


def dedupe(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One document per id. The longer passage wins, and symbols are combined."""
    chosen: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for document in documents:
        current = chosen.get(document["id"])
        if current is None:
            chosen[document["id"]] = document
            order.append(document["id"])
            continue
        chosen[document["id"]] = _prefer(current, document)
    return [chosen[ident] for ident in order]


def render_ndjson(documents: list[dict[str, Any]]) -> bytes:
    """One JSON object per line, UTF-8, with a trailing newline."""
    lines = [json.dumps(document, ensure_ascii=False, separators=(",", ":")) for document in documents]
    return ("\n".join(lines) + "\n").encode("utf-8")


def event_timestamp(value: str) -> str | None:
    """RSS or ISO timestamp as UTC ``YYYY-MM-DDTHH:MM:SSZ``, or None."""
    text = value.strip()
    if not text:
        return None
    parsed = parse_published(text)
    if parsed is None:
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    return _iso(_aware(parsed))


def _prefer(current: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    kept = incoming if len(incoming["text"]) > len(current["text"]) else current
    other = current if kept is incoming else incoming
    symbols = _symbols([*kept["symbols"], *other["symbols"]])
    if symbols == list(kept["symbols"]):
        return kept
    merged = dict(kept)
    merged["symbols"] = symbols
    return merged


def _iso(moment: datetime) -> str:
    return _aware(moment).strftime("%Y-%m-%dT%H:%M:%SZ")


def _aware(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def _category(value: str) -> str:
    text = " ".join(value.casefold().split())
    return text[:80] or "general"


def _symbols(values: list[str]) -> list[str]:
    seen: list[str] = []
    for value in values:
        symbol = str(value).strip().upper()
        if symbol and symbol not in seen:
            seen.append(symbol)
    return seen


def _text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())
