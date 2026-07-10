"""
finfluencer.utils.dedup
========================

Near-duplicate detection via token-level Jaccard similarity.

Used by :mod:`finfluencer.preprocess.pipeline` to drop copy-paste spam
and bot-repetition artefacts (Methods §3.3). The design goal is
transparency and determinism, not minimum runtime — comparing all
pairs quadratically is acceptable at MVP-B scale (~3–4k comments per
analyst); if a future study reaches 10⁶ comments per analyst, replace
this with LSH/MinHash under the same interface.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence


def jaccard_similarity(a: Iterable[str], b: Iterable[str]) -> float:
    """Return the Jaccard similarity of two token collections.

    ``|A ∩ B| / |A ∪ B|``. Empty vs empty returns 1.0 (identical by
    definition); either-empty vs non-empty returns 0.0.
    """
    sa = set(a)
    sb = set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def find_near_duplicates(
    token_lists: Sequence[Sequence[str]],
    *,
    threshold: float = 0.90,
    length_tolerance: float = 0.20,
) -> set[int]:
    """Return indices of documents to *drop* as near-duplicates.

    Compares every document with previously-seen documents of similar
    length (±``length_tolerance``) and drops the current one if any
    pair exceeds ``threshold``. The first occurrence of a duplicate
    cluster is always retained; later ones are dropped.

    The length-tolerance filter reduces the quadratic comparisons in
    practice — comments of very different lengths cannot have high
    Jaccard similarity so we skip them.

    Parameters
    ----------
    token_lists
        Sequence of tokenised documents.
    threshold
        Jaccard threshold above which two documents are considered
        near-duplicates. Default 0.90 matches Methods §3.3.
    length_tolerance
        Relative length window for candidate comparison. Default 0.20
        (compare only against documents whose length is within ±20%).

    Returns
    -------
    set[int]
        Zero-based indices of documents to drop.
    """
    if not 0.0 <= threshold <= 1.0:
        raise ValueError(
            f"find_near_duplicates: threshold must be in [0, 1], got {threshold}",
        )
    if length_tolerance < 0.0:
        raise ValueError("find_near_duplicates: length_tolerance must be >= 0")

    to_drop: set[int] = set()
    # Bucket by exact set-length; candidates come from nearby buckets.
    signatures: dict[int, list[tuple[int, set[str]]]] = {}

    for i, tokens in enumerate(token_lists):
        s = set(tokens)
        L = len(s)
        if L == 0:
            continue

        lo = max(1, int(L * (1.0 - length_tolerance)))
        hi = int(L * (1.0 + length_tolerance)) + 1

        for length_bucket in range(lo, hi):
            for _j, sj in signatures.get(length_bucket, ()):
                if not sj:
                    continue
                intersection = len(s & sj)
                if intersection == 0:
                    continue
                union = len(s | sj)
                sim = intersection / union
                if sim >= threshold:
                    to_drop.add(i)
                    break
            if i in to_drop:
                break

        # Register this document even if it was dropped — later
        # duplicates should also be dropped against it.
        signatures.setdefault(L, []).append((i, s))

    return to_drop


__all__ = [
    "jaccard_similarity",
    "find_near_duplicates",
]
