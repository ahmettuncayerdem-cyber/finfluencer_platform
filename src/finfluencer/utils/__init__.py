"""
finfluencer.utils — Small pure utility functions used across the platform.

Modules
-------
    hashing : salted SHA-256 utilities (anonymisation, provenance)
    time    : timezone-aware datetime helpers            (added in a later file)
    io      : Parquet / Excel / CSV read/write helpers   (added in a later file)
    dedup   : near-duplicate detection                   (added in a later file)

Design invariant
----------------
Every function in this subpackage is a pure function of its arguments.
No global state, no external service calls, no filesystem writes except
those explicit in the function name (e.g. `hash_file` reads only).
This lets these utilities be imported freely from any subpackage without
introducing dependency cycles.
"""
