"""Tests for :mod:`finfluencer.migration.backfill_entity_model`."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from finfluencer.migration.backfill_entity_model import backfill_entity_model
from finfluencer.utils.io import write_parquet


def _video_row(
    *, analyst_key: str, video_id: str, title: str = "Video Title",
    eligible: bool = True, selected: bool = True, exclusion_reason: str = "",
) -> dict:
    return dict(
        analyst_key=analyst_key, video_id=video_id,
        published_at="2024-01-01T00:00:00Z", title=title,
        description="desc", duration_sec=120, views=100, likes=10,
        comment_count=5, made_for_kids=False, category_id="25",
        eligible=eligible, exclusion_reason=exclusion_reason, selected=selected,
    )


def _comment_row(
    *, analyst_key: str, video_id: str, comment_id: str, text_clean: str = "clean text",
) -> dict:
    return dict(
        analyst_key=analyst_key, video_id=video_id, comment_id=comment_id,
        commenter_hash="hash1", posted_date="2024-01-02", text_raw="raw text",
        text_clean=text_clean, tokens=["clean", "text"], n_tokens=2,
        emojis=[], likes=3,
    )


def _write_inputs(
    tmp_path: Path, videos_rows: list[dict], comments_rows: list[dict],
    channels_rows: list[dict] | None = None,
) -> tuple[Path, Path, Path | None]:
    videos_path = tmp_path / "videos.parquet"
    comments_path = tmp_path / "comments.parquet"
    write_parquet(pd.DataFrame(videos_rows), videos_path)
    write_parquet(pd.DataFrame(comments_rows), comments_path)
    channels_path = None
    if channels_rows is not None:
        channels_path = tmp_path / "channels.parquet"
        write_parquet(pd.DataFrame(channels_rows), channels_path)
    return videos_path, comments_path, channels_path


class TestBackfillEntityModel:
    def test_single_entity_no_duplication(self, tmp_path):
        videos_path, comments_path, _ = _write_inputs(
            tmp_path,
            [_video_row(analyst_key="satiroglu", video_id="v1")],
            [_comment_row(analyst_key="satiroglu", video_id="v1", comment_id="c1")],
        )
        result = backfill_entity_model(
            videos_path, comments_path, output_dir=tmp_path / "out",
        )
        assert len(result["entities"]) == 1
        assert result["entities"].iloc[0]["entity_key"] == "satiroglu"
        assert len(result["videos_canonical"]) == 1
        assert len(result["comments_canonical"]) == 1
        assert len(result["entity_video_link"]) == 1
        assert result["report"]["n_multi_entity_videos"] == 0
        assert result["report"]["n_duplicate_comment_rows_collapsed"] == 0

    def test_multi_entity_video_deduplicates_to_one_canonical_row(self, tmp_path):
        videos_path, comments_path, _ = _write_inputs(
            tmp_path,
            [
                _video_row(analyst_key="satiroglu", video_id="v_shared"),
                _video_row(analyst_key="gecer", video_id="v_shared"),
            ],
            [
                _comment_row(analyst_key="satiroglu", video_id="v_shared", comment_id="c1"),
                _comment_row(analyst_key="gecer", video_id="v_shared", comment_id="c1"),
            ],
        )
        result = backfill_entity_model(
            videos_path, comments_path, output_dir=tmp_path / "out",
        )
        # Exactly one physical video, two entity links.
        assert len(result["videos_canonical"]) == 1
        assert len(result["entity_video_link"]) == 2
        assert set(result["entity_video_link"]["entity_key"]) == {"satiroglu", "gecer"}
        assert result["report"]["n_multi_entity_videos"] == 1
        # Exactly one physical comment, no duplication in the canonical table.
        assert len(result["comments_canonical"]) == 1
        assert result["report"]["n_comments_raw_rows"] == 2
        assert result["report"]["n_duplicate_comment_rows_collapsed"] == 1

    def test_entity_video_link_preserves_per_entity_selection(self, tmp_path):
        videos_path, comments_path, _ = _write_inputs(
            tmp_path,
            [
                _video_row(analyst_key="satiroglu", video_id="v_shared", selected=True),
                _video_row(
                    analyst_key="gecer", video_id="v_shared",
                    selected=False, eligible=False, exclusion_reason="shorts",
                ),
            ],
            [],
        )
        result = backfill_entity_model(
            videos_path, comments_path, output_dir=tmp_path / "out",
        )
        link = result["entity_video_link"].set_index("entity_key")
        assert bool(link.loc["satiroglu", "selected"]) is True
        assert bool(link.loc["gecer", "selected"]) is False
        assert bool(link.loc["gecer", "eligible"]) is False
        assert link.loc["gecer", "exclusion_reason"] == "shorts"

    def test_volatile_metrics_take_max_instead_of_raising(self, tmp_path):
        """views/likes/comment_count legitimately drift across collection
        times for the same video re-collected under a second entity -
        this must resolve via max(), not raise (confirmed against real
        production data: 7 multi-entity videos differ only in views)."""
        videos_path, comments_path, _ = _write_inputs(
            tmp_path,
            [
                dict(
                    analyst_key="satiroglu", video_id="v_drift",
                    published_at="2024-01-01T00:00:00Z", title="Same Title",
                    description="desc", duration_sec=120, views=1000, likes=10,
                    comment_count=5, made_for_kids=False, category_id="25",
                    eligible=True, exclusion_reason="", selected=True,
                ),
                dict(
                    analyst_key="gecer", video_id="v_drift",
                    published_at="2024-01-01T00:00:00Z", title="Same Title",
                    description="desc", duration_sec=120, views=1250, likes=14,
                    comment_count=8, made_for_kids=False, category_id="25",
                    eligible=True, exclusion_reason="", selected=True,
                ),
            ],
            [],
        )
        result = backfill_entity_model(
            videos_path, comments_path, output_dir=tmp_path / "out",
        )
        row = result["videos_canonical"].iloc[0]
        assert row["views"] == 1250
        assert row["likes"] == 14
        assert row["comment_count"] == 8
        assert row["title"] == "Same Title"

    def test_inconsistent_video_title_raises(self, tmp_path):
        videos_path, comments_path, _ = _write_inputs(
            tmp_path,
            [
                _video_row(analyst_key="satiroglu", video_id="v_bad", title="Title A"),
                _video_row(analyst_key="gecer", video_id="v_bad", title="Title B"),
            ],
            [],
        )
        with pytest.raises(ValueError, match="videos_canonical"):
            backfill_entity_model(videos_path, comments_path, output_dir=tmp_path / "out")

    def test_inconsistent_comment_text_raises(self, tmp_path):
        videos_path, comments_path, _ = _write_inputs(
            tmp_path,
            [_video_row(analyst_key="satiroglu", video_id="v1")],
            [
                _comment_row(
                    analyst_key="satiroglu", video_id="v1", comment_id="c_bad",
                    text_clean="version A",
                ),
                _comment_row(
                    analyst_key="gecer", video_id="v1", comment_id="c_bad",
                    text_clean="version B",
                ),
            ],
        )
        with pytest.raises(ValueError, match="comments_canonical"):
            backfill_entity_model(videos_path, comments_path, output_dir=tmp_path / "out")

    def test_entities_pick_up_channel_ids(self, tmp_path):
        videos_path, comments_path, channels_path = _write_inputs(
            tmp_path,
            [_video_row(analyst_key="satiroglu", video_id="v1")],
            [],
            channels_rows=[dict(analyst_key="satiroglu", channel_id="UC123")],
        )
        result = backfill_entity_model(
            videos_path, comments_path, channels_path=channels_path,
            output_dir=tmp_path / "out",
        )
        row = result["entities"].iloc[0]
        assert row["membership_params"]["channel_ids"] == ["UC123"]
        assert row["entity_type"] == "creator"

    def test_output_files_written_to_disk(self, tmp_path):
        videos_path, comments_path, _ = _write_inputs(
            tmp_path,
            [_video_row(analyst_key="satiroglu", video_id="v1")],
            [_comment_row(analyst_key="satiroglu", video_id="v1", comment_id="c1")],
        )
        out_dir = tmp_path / "out"
        backfill_entity_model(videos_path, comments_path, output_dir=out_dir)
        for fname in (
            "entities.parquet", "entity_video_link.parquet",
            "videos_canonical.parquet", "comments_canonical.parquet",
        ):
            assert (out_dir / fname).exists()

    def test_idempotent_rerun_produces_same_counts(self, tmp_path):
        videos_path, comments_path, _ = _write_inputs(
            tmp_path,
            [
                _video_row(analyst_key="satiroglu", video_id="v1"),
                _video_row(analyst_key="gecer", video_id="v2"),
            ],
            [_comment_row(analyst_key="satiroglu", video_id="v1", comment_id="c1")],
        )
        out_dir = tmp_path / "out"
        first = backfill_entity_model(videos_path, comments_path, output_dir=out_dir)
        second = backfill_entity_model(videos_path, comments_path, output_dir=out_dir)
        assert first["report"] == second["report"]
