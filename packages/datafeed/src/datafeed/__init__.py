"""External market-data clients.

Copied from pborgen/invest@68db3164b78746acc9031799c28c67f4f6431cb8.

Each vendor lives in its own folder and reports the kinds of data it can
return. See ``datafeed.kinds``. ``datafeed.quotes.QuoteService`` tries every
feed that can return a quote and keeps the first price.

The signed-in TradingView portfolio client stays in the invest repo.
"""
