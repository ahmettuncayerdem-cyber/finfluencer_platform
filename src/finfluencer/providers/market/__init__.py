"""Market-data providers. Import concrete providers here so their @register decorators run."""
from finfluencer.providers.market import base as base  # noqa: F401
from finfluencer.providers.market import yfinance_provider as yfinance_provider  # noqa: F401
from finfluencer.providers.market import tcmb_evds_provider as tcmb_evds_provider  # noqa: F401
