"""Tests for :mod:`finfluencer.sentiment.pipeline`."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from finfluencer.core.checkpoint import CheckpointManager
from finfluencer.sentiment.pipeline import run_sentiment
from finfluencer.utils.hashing import hash_string
from finfluencer.utils.io import write_parquet


def _fake_settings(
    root_seed: int = 42, pseudo_neutral_band: tuple[float, float] = (0.40, 0.60),
):
    return SimpleNamespace(
        study=SimpleNamespace(root_seed=root_seed),
        sentiment=SimpleNamespace(pseudo_neutral_band=pseudo_neutral_band),
    )


class _FakeProvider:
    """Minimal SentimentProvider — no model_name/revision/device attrs,
    so pipeline metadata fallback is exercised too.

    Maps text -> deterministic probability by length (mod 1.0), except
    special-cased keywords used to hit specific bands in tests.
    """

    key = "fake"

    def __init__(self) -> None:
        self.predict_calls: list[list[str]] = []

    def predict(self, texts: list[str]) -> np.ndarray:
        self.predict_calls.append(list(texts))
        probs = []
        for t in texts:
            if t == "NEUTRALISH":
                probs.append(0.50)
            elif t == "CLEARLY_NEGATIVE":
                probs.append(0.05)
            else:
                probs.append(0.90)
        return np.asarray(probs, dtype=np.float32)


def _row(analyst_key: str, comment_id: str, text_clean: str) -> dict:
    return dict(analyst_key=analyst_key, comment_id=comment_id, text_clean=text_clean)


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame([
        _row("satiroglu", "c1", "harika bir yatirim oldu"),
        _row("satiroglu", "c2", "harika bir yatirim oldu"),  # duplicate text of c1
        _row("satiroglu", "c3", "NEUTRALISH"),
        _row("gecer", "c4", "CLEARLY_NEGATIVE"),
    ])


@pytest.fixture
def provider() -> _FakeProvider:
    return _FakeProvider()


class TestRunSentiment:
    def test_cache_miss_then_hit(
        self, tmp_checkpoint_root, tmp_cache_root, tmp_path, provider,
    ):
        comments_path = tmp_path / "comments.parquet"
        write_parquet(_sample_df(), comments_path)
        out1 = tmp_path / "sent1.parquet"
        checkpoint = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)

        result = run_sentiment(
            _fake_settings(), comments_path, checkpoint,
            provider=provider, output_path=out1,
        )
        assert set(result["comment_id"]) == {"c1", "c2", "c3", "c4"}
        n_predict_first = sum(len(c) for c in provider.predict_calls)
        assert n_predict_first > 0

        # Fresh checkpoint stage (different checkpoint_root) but same
        # cache_root must hit the cache: no new predict() calls.
        checkpoint2 = CheckpointManager(tmp_checkpoint_root / "other", tmp_cache_root)
        out2 = tmp_path / "sent2.parquet"
        provider.predict_calls.clear()
        run_sentiment(
            _fake_settings(), comments_path, checkpoint2,
            provider=provider, output_path=out2,
        )
        assert sum(len(c) for c in provider.predict_calls) == 0

    def test_duplicate_text_scored_once(
        self, tmp_checkpoint_root, tmp_cache_root, tmp_path, provider,
    ):
        comments_path = tmp_path / "comments.parquet"
        write_parquet(_sample_df(), comments_path)
        out_path = tmp_path / "sent.parquet"
        checkpoint = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)

        result = run_sentiment(
            _fake_settings(), comments_path, checkpoint,
            provider=provider, output_path=out_path,
        )
        c1_prob = result.loc[result["comment_id"] == "c1", "sentiment_prob"].iloc[0]
        c2_prob = result.loc[result["comment_id"] == "c2", "sentiment_prob"].iloc[0]
        assert c1_prob == c2_prob
        all_texts = [t for call in provider.predict_calls for t in call]
        assert all_texts.count("harika bir yatirim oldu") == 1

    def test_polarity_and_pseudo_neutral_banding(
        self, tmp_checkpoint_root, tmp_cache_root, tmp_path, provider,
    ):
        comments_path = tmp_path / "comments.parquet"
        write_parquet(_sample_df(), comments_path)
        out_path = tmp_path / "sent.parquet"
        checkpoint = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)

        result = run_sentiment(
            _fake_settings(pseudo_neutral_band=(0.40, 0.60)), comments_path, checkpoint,
            provider=provider, output_path=out_path,
        )
        row = lambda cid: result.loc[result["comment_id"] == cid].iloc[0]  # noqa: E731

        c1 = row("c1")  # prob 0.90 -> positive, not pseudo-neutral
        assert c1["sentiment_class"] == "positive"
        assert c1["sentiment_pseudo_neutral"] == False  # noqa: E712

        c3 = row("c3")  # prob 0.50 -> inside [0.40, 0.60] -> pseudo-neutral
        assert c3["sentiment_pseudo_neutral"] == True  # noqa: E712

        c4 = row("c4")  # prob 0.05 -> negative, not pseudo-neutral
        assert c4["sentiment_class"] == "negative"
        assert c4["sentiment_pseudo_neutral"] == False  # noqa: E712

    def test_target_of_affect_fields_are_none(
        self, tmp_checkpoint_root, tmp_cache_root, tmp_path, provider,
    ):
        """Phase 2.2 scope: target-of-affect is deferred to Phase 2.3."""
        comments_path = tmp_path / "comments.parquet"
        write_parquet(_sample_df(), comments_path)
        out_path = tmp_path / "sent.parquet"
        checkpoint = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)

        result = run_sentiment(
            _fake_settings(), comments_path, checkpoint,
            provider=provider, output_path=out_path,
        )
        assert result["sentiment_target"].isna().all()
        assert result["sentiment_market_directed"].isna().all()

    def test_analyst_isolation(
        self, tmp_checkpoint_root, tmp_cache_root, tmp_path, provider,
    ):
        comments_path = tmp_path / "comments.parquet"
        write_parquet(_sample_df(), comments_path)
        out_path = tmp_path / "sent.parquet"
        checkpoint = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)

        result = run_sentiment(
            _fake_settings(), comments_path, checkpoint,
            provider=provider, output_path=out_path, analyst_key="satiroglu",
        )
        assert set(result["comment_id"]) == {"c1", "c2", "c3"}
        assert "c4" not in set(result["comment_id"])

    def test_checkpoint_skip_no_rescoring(
        self, tmp_checkpoint_root, tmp_cache_root, tmp_path, provider,
    ):
        comments_path = tmp_path / "comments.parquet"
        write_parquet(_sample_df(), comments_path)
        out_path = tmp_path / "sent.parquet"
        checkpoint = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)
        settings = _fake_settings()

        first = run_sentiment(
            settings, comments_path, checkpoint,
            provider=provider, output_path=out_path,
        )
        provider.predict_calls.clear()
        second = run_sentiment(
            settings, comments_path, checkpoint,
            provider=provider, output_path=out_path,
        )
        assert provider.predict_calls == []
        assert set(first["comment_id"]) == set(second["comment_id"])

    def test_config_change_invalidates_checkpoint_but_cache_still_hits(
        self, tmp_checkpoint_root, tmp_cache_root, tmp_path, provider,
    ):
        comments_path = tmp_path / "comments.parquet"
        write_parquet(_sample_df(), comments_path)
        checkpoint = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)

        run_sentiment(
            _fake_settings(root_seed=1), comments_path, checkpoint,
            provider=provider, output_path=tmp_path / "sent1.parquet",
        )
        provider.predict_calls.clear()
        run_sentiment(
            _fake_settings(root_seed=2), comments_path, checkpoint,
            provider=provider, output_path=tmp_path / "sent2.parquet",
        )
        # Different root_seed invalidates the Tier-2 checkpoint, forcing
        # reprocessing, but the Tier-3 score cache is keyed independently
        # of root_seed -> no new predict() calls.
        assert provider.predict_calls == []

    def test_empty_input_is_handled(
        self, tmp_checkpoint_root, tmp_cache_root, tmp_path, provider,
    ):
        comments_path = tmp_path / "comments.parquet"
        write_parquet(pd.DataFrame(), comments_path)
        out_path = tmp_path / "sent.parquet"
        checkpoint = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)

        result = run_sentiment(
            _fake_settings(), comments_path, checkpoint,
            provider=provider, output_path=out_path,
        )
        assert result.empty

    def test_deterministic_hashing(
        self, tmp_checkpoint_root, tmp_cache_root, tmp_path, provider,
    ):
        comments_path = tmp_path / "comments.parquet"
        write_parquet(_sample_df(), comments_path)
        out_path = tmp_path / "sent.parquet"
        checkpoint = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)

        run_sentiment(
            _fake_settings(), comments_path, checkpoint,
            provider=provider, output_path=out_path,
        )
        expected_hash = hash_string("harika bir yatirim oldu::fake::unknown::cpu")
        cached_path = checkpoint.cache_path("sentiment", expected_hash, ".npy")
        assert cached_path.exists()
