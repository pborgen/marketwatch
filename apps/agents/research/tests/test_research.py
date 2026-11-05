from __future__ import annotations

from pathlib import Path

from agent import filings, quote, summarize_prices
from prompt_management.prompt import local_system_prompt

_TEXT = Path(__file__).resolve().parents[1] / "system_prompt.txt"


def test_system_prompt_lives_in_the_text_file() -> None:
    text = local_system_prompt(_TEXT)
    assert "Do not give a buy or sell rating." in text
    assert not text.startswith("\n")


def test_quote_rejects_a_sentence() -> None:
    assert quote("not a ticker")["error"]


def test_filings_report_a_missing_sec_user_agent(monkeypatch) -> None:
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    result = filings("AAPL")
    assert result["symbol"] == "AAPL"
    assert "SEC_USER_AGENT" in result["error"]


def test_summarize_prices_uses_the_first_and_last_close() -> None:
    summary = summarize_prices(
        [
            {"date": "2025-01-02", "price": 100},
            {"date": "2025-06-02", "price": 80},
            {"date": "2026-01-02", "price": 150},
        ]
    )
    assert summary["start_price"] == 100
    assert summary["end_price"] == 150
    assert summary["change"] == 50
    assert summary["change_pct"] == 50
    assert summary["high"] == 150
    assert summary["low"] == 80
    assert summary["sessions"] == 3


def test_summarize_prices_needs_two_closes() -> None:
    assert summarize_prices([{"date": "2026-01-02", "price": 10}]) == {}
