"""Tests for :mod:`finfluencer.preprocess.pipeline`."""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from finfluencer.core.checkpoint import CheckpointManager
from finfluencer.preprocess.base import TextPreprocessor
from finfluencer.preprocess.pipeline import (
    build_default_preprocessor,
    run_preprocessing,
)
from finfluencer.providers.language.turkish import TurkishLanguageProvider
from finfluencer.utils.io import write_parquet


def _fake_settings(*, min_tokens: int = 2, jaccard: float = 0.9, root_seed: int = 42):
    """Duck-typed stand-in for core.contracts.Settings (only the fields
    run_preprocessing actually reads)."""
    return SimpleNamespace(
        preprocessing=SimpleNamespace(
            min_tokens=min_tokens, jaccard_dup_threshold=jaccard,
        ),
        study=SimpleNamespace(root_seed=root_seed),
    )


_COMMENT_DEFAULTS = dict(
    commenter_hash="h", posted_date="2026-01-01",
    text_clean="", tokens=[], n_tokens=0, emojis=[], likes=0,
)


def _row(analyst_key: str, video_id: str, comment_id: str, text_raw: str) -> dict:
    row = dict(_COMMENT_DEFAULTS)
    row.update(
        analyst_key=analyst_key, video_id=video_id,
        comment_id=comment_id, text_raw=text_raw,
    )
    return row


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame([
        _row("satiroglu", "v1", "c1", "Bu ay THYAO yüzde 10 arttı harika"),
        _row("satiroglu", "v1", "c2", "Bu ay THYAO yüzde 10 arttı harika"),  # near-dup of c1
        _row("satiroglu", "v1", "c3", "ok"),  # below min_tokens=2
        _row("gecer", "v2", "c4", "100 TL kazandım bugün"),
    ])


@pytest.fixture
def preprocessor() -> TextPreprocessor:
    return build_default_preprocessor(TurkishLanguageProvider())


class TestTurkishFinancialPreprocessor:
    def test_structural_type(self, preprocessor):
        assert isinstance(preprocessor, TextPreprocessor)

    def test_preserves_financial_semantics(self, preprocessor):
        out = preprocessor.process("Bu ay $THYAO %10 arttı, 100 TL kar ettim")
        assert "cashtag_thyao" in out.tokens
        assert "percent_10" in out.tokens
        assert "money_try" in out.tokens
        assert out.n_tokens == len(out.tokens)

    def test_extracts_emoji_before_stripping(self, preprocessor):
        out = preprocessor.process("harika 😊")
        assert out.emojis == ["😊"]
        assert "😊" not in out.text_clean


class TestRunPreprocessing:
    def test_fills_columns_and_filters(
        self, tmp_checkpoint_root, tmp_cache_root, tmp_path, preprocessor,
    ):
        comments_path = tmp_path / "comments.parquet"
        write_parquet(_sample_df(), comments_path)
        out_path = tmp_path / "out.parquet"
        checkpoint = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)

        result = run_preprocessing(
            _fake_settings(), comments_path, checkpoint,
            preprocessor=preprocessor, output_path=out_path,
        )

        assert set(result["comment_id"]) == {"c1", "c4"}  # c2 dup, c3 too short
        row = result.loc[result["comment_id"] == "c1"].iloc[0]
        assert row["n_tokens"] == len(row["tokens"])
        assert row["n_tokens"] > 0

    def test_in_place_default_output(
        self, tmp_checkpoint_root, tmp_cache_root, tmp_path, preprocessor,
    ):
        comments_path = tmp_path / "comments.parquet"
        write_parquet(_sample_df(), comments_path)
        checkpoint = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)

        result = run_preprocessing(
            _fake_settings(), comments_path, checkpoint, preprocessor=preprocessor,
        )
        reloaded = pd.read_parquet(comments_path)
        assert set(result["comment_id"]) == set(reloaded["comment_id"])
        assert list(result.columns) == list(_sample_df().columns)

    def test_analyst_key_filter_leaves_others_untouched(
        self, tmp_checkpoint_root, tmp_cache_root, tmp_path, preprocessor,
    ):
        comments_path = tmp_path / "comments.parquet"
        write_parquet(_sample_df(), comments_path)
        out_path = tmp_path / "out.parquet"
        checkpoint = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)

        result = run_preprocessing(
            _fake_settings(), comments_path, checkpoint,
            preprocessor=preprocessor, output_path=out_path,
            analyst_key="satiroglu",
        )

        gecer_row = result.loc[result["comment_id"] == "c4"].iloc[0]
        assert gecer_row["text_clean"] == ""
        assert gecer_row["n_tokens"] == 0
        assert "c1" in set(result["comment_id"])

    def test_checkpoint_skips_second_run(
        self, tmp_checkpoint_root, tmp_cache_root, tmp_path, preprocessor,
    ):
        comments_path = tmp_path / "comments.parquet"
        write_parquet(_sample_df(), comments_path)
        out_path = tmp_path / "out.parquet"
        checkpoint = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)
        settings = _fake_settings()

        first = run_preprocessing(
            settings, comments_path, checkpoint,
            preprocessor=preprocessor, output_path=out_path,
        )
        second = run_preprocessing(
            settings, comments_path, checkpoint,
            preprocessor=preprocessor, output_path=out_path,
        )
        assert set(first["comment_id"]) == set(second["comment_id"]) == {"c1", "c4"}

    def test_config_change_forces_reprocessing(
        self, tmp_checkpoint_root, tmp_cache_root, tmp_path, preprocessor,
    ):
        comments_path = tmp_path / "comments.parquet"
        write_parquet(_sample_df(), comments_path)
        checkpoint = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)

        out1 = tmp_path / "out1.parquet"
        run_preprocessing(
            _fake_settings(min_tokens=2), comments_path, checkpoint,
            preprocessor=preprocessor, output_path=out1,
        )
        out2 = tmp_path / "out2.parquet"
        result2 = run_preprocessing(
            _fake_settings(min_tokens=1), comments_path, checkpoint,
            preprocessor=preprocessor, output_path=out2,
        )
        # min_tokens=1 keeps the previously-too-short "ok" comment.
        assert "c3" in set(result2["comment_id"])

    def test_empty_input_is_handled(
        self, tmp_checkpoint_root, tmp_cache_root, tmp_path, preprocessor,
    ):
        comments_path = tmp_path / "comments.parquet"
        write_parquet(pd.DataFrame(), comments_path)
        out_path = tmp_path / "out.parquet"
        checkpoint = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)

        result = run_preprocessing(
            _fake_settings(), comments_path, checkpoint,
            preprocessor=preprocessor, output_path=out_path,
        )
        assert result.empty
