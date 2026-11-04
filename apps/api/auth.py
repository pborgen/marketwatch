"""Shared password for the monitor.

One password, one cookie. Set ``MONITOR_PASSWORD`` to change it. When that
variable is unset, the password is ``demo``.
"""

from __future__ import annotations

import hashlib
import hmac
import os

COOKIE = "monitor"
_PURPOSE = b"marketwatch-monitor"


def expected_password() -> str | None:
    """The demo password, or None when it was set to a blank value."""
    if "MONITOR_PASSWORD" not in os.environ:
        return "demo"
    value = os.environ["MONITOR_PASSWORD"].strip()
    return value or None


def password_matches(given: str) -> bool:
    expected = expected_password()
    if not expected or not given:
        return False
    return hmac.compare_digest(given.encode(), expected.encode())


def session_token() -> str | None:
    expected = expected_password()
    if expected is None:
        return None
    return hmac.new(expected.encode(), _PURPOSE, hashlib.sha256).hexdigest()


def cookie_header(headers: object) -> str:
    raw = ""
    getter = getattr(headers, "get", None)
    if getter is not None:
        raw = getter("Cookie") or ""
    return raw


def session_ok(headers: object) -> bool:
    expected = session_token()
    if expected is None:
        return False
    presented = ""
    for part in cookie_header(headers).split(";"):
        name, separator, value = part.strip().partition("=")
        if separator and name == COOKIE:
            presented = value.strip()
            break
    if not presented:
        return False
    return hmac.compare_digest(presented.encode(), expected.encode())


def set_cookie(secure: bool) -> str:
    token = session_token() or ""
    parts = [
        f"{COOKIE}={token}",
        "HttpOnly",
        "Path=/",
        "SameSite=Lax",
        "Max-Age=43200",
    ]
    if secure:
        parts.append("Secure")
    return "; ".join(parts)


def clear_cookie(secure: bool) -> str:
    parts = [f"{COOKIE}=", "HttpOnly", "Path=/", "SameSite=Lax", "Max-Age=0"]
    if secure:
        parts.append("Secure")
    return "; ".join(parts)
