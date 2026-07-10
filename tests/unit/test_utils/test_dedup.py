"""Tests for :mod:`finfluencer.utils.dedup`."""

from __future__ import annotations

import pytest
from finfluencer.utils.dedup import find_near_duplicates, jaccard_similarity


class TestJaccard:
    def test_both_empty_returns_one(self):
        assert jaccard_similarity([], []) == 1.0

    def test_one_empty_returns_zero(self):
        assert jaccard_similarity(["a"], []) == 0.0
        assert jaccard_similarity([], ["a"]) == 0.0

    def test_identical(self):
        assert jaccard_similarity(["a", "b"], ["a", "b"]) == 1.0

    def test_disjoint(self):
        assert jaccard_similarity(["a"], ["b"]) == 0.0

    def test_partial(self):
        # |{a,b} ∩ {a,c}| / |{a,b,c}| = 1/3
        assert abs(jaccard_similarity(["a", "b"], ["a", "c"]) - 1/3) < 1e-9


class TestFindNearDuplicates:
    def test_exact_duplicate_detected(self):
        docs = [
            ["hocam", "teşekkürler"],
            ["hocam", "teşekkürler"],  # dup of index 0
        ]
        assert find_near_duplicates(docs, threshold=0.9) == {1}

    def test_first_occurrence_retained(self):
        docs = [["a", "b", "c"], ["a", "b", "c"], ["a", "b", "c"]]
        drops = find_near_duplicates(docs, threshold=0.9)
        # Original always retained; later occurrences dropped
        assert 0 not in drops
        assert drops == {1, 2}

    def test_threshold_sensitivity(self):
        docs = [
            ["a", "b", "c", "d"],       # baseline
            ["a", "b", "c", "e"],       # jaccard = 3/5 = 0.6
        ]
        assert find_near_duplicates(docs, threshold=0.9) == set()  # below
        assert find_near_duplicates(docs, threshold=0.5) == {1}      # above

    def test_length_tolerance_skips_distant_lengths(self):
        docs = [["a"], list("abcdefghij")]
        # Tokens have zero overlap AND length ratio > tolerance ⇒ no dup.
        assert find_near_duplicates(docs, threshold=0.01) == set()

    def test_invalid_threshold_raises(self):
        with pytest.raises(ValueError):
            find_near_duplicates([["a"]], threshold=1.5)
