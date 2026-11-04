"""SEC EDGAR filings. No API key.

The SEC requires a User-Agent with a name and email (``SEC_USER_AGENT``).
"""

from datafeed.edgar.feed import Edgar
from datafeed.edgar.filings import EdgarFilings

__all__ = ["Edgar", "EdgarFilings"]
