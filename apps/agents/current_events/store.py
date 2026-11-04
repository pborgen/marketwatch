"""Write current-event documents to S3 under the UTC date of the run."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from documents import render_ndjson

DEFAULT_PREFIX = "current-events"
PREFIX_ENV = "EVENTS_PREFIX"


def events_key(when: datetime, prefix: str = DEFAULT_PREFIX) -> str:
    """``current-events/date=YYYY-MM-DD/events-YYYYMMDDTHHMMSSZ.ndjson``."""
    moment = _aware(when)
    day = moment.strftime("%Y-%m-%d")
    stamp = moment.strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}/date={day}/events-{stamp}.ndjson"


def store_events(
    documents: list[dict[str, Any]],
    *,
    bucket: str,
    client: Any,
    when: datetime | None = None,
    prefix: str | None = None,
) -> dict[str, Any]:
    """Put one newline-delimited object. The bucket must already exist."""
    moment = _aware(when or datetime.now(timezone.utc))
    key = events_key(moment, prefix_name(prefix))
    body = render_ndjson(documents)
    day = moment.strftime("%Y-%m-%d")
    try:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType="application/x-ndjson",
            Metadata={
                "collected-on": day,
                "document-count": str(len(documents)),
                "schema-version": "1",
            },
        )
    except Exception as exc:
        return {"error": f"Could not store events: {exc}", "count": len(documents)}
    return {
        "bucket": bucket,
        "key": key,
        "uri": f"s3://{bucket}/{key}",
        "count": len(documents),
        "collected_on": day,
    }


def bucket_name(value: str | None = None) -> str:
    """Bucket from the argument, or from ``DATA_BUCKET`` when the argument is omitted."""
    raw = value if value is not None else os.environ.get("DATA_BUCKET", "")
    name = raw.strip()
    if name.startswith("s3://"):
        name = name[5:]
    return name.split("/", 1)[0].strip()


def prefix_name(value: str | None = None) -> str:
    """Key prefix from the argument, or from ``EVENTS_PREFIX`` when omitted."""
    raw = value if value is not None else os.environ.get(PREFIX_ENV, "")
    parts: list[str] = []
    for part in raw.strip().strip("/").split("/"):
        if not part or part == ".":
            continue
        if part == "..":
            return DEFAULT_PREFIX
        parts.append(part)
    return "/".join(parts) if parts else DEFAULT_PREFIX


def s3_client() -> Any:
    import boto3

    return boto3.client("s3")


def _aware(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)
