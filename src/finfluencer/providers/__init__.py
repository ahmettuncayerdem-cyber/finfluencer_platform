"""
finfluencer.providers — Extension points for language, platform, and market data.

Each subpackage defines a Protocol base class and ships one concrete
implementation in-tree. Third parties may register additional
implementations via entry points under ``finfluencer.providers``
(see :mod:`finfluencer.core.registry`).
"""
