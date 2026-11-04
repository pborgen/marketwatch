"""Bureau of Labor Statistics releases. No API key.

Employment Situation and CPI only.
"""

from datafeed.bls.feed import Bls
from datafeed.bls.releases import BlsReleases

__all__ = ["Bls", "BlsReleases"]
