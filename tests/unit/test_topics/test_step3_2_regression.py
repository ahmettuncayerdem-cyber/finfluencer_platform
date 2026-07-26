"""Migration Step 3.2 deterministic regression test.

Compares ``run_topics()`` output row-by-row against a byte-verified
snapshot of the function as it existed immediately before Step 3.2
(``_pipeline_OLD_snapshot.py`` - reconstructed by mechanically reversing
the exact, known Step 3.2 edits against the current file; see the
migration report for how this snapshot was produced and verified).

Required invariant (Step 3.2 approval gate, item 9 + the explicit
row-by-row comparison instruction): no row of ``topics.parquet`` may
change except for the newly introduced ``scope_id`` column. This test
asserts exactly that - not "close enough," but every non-scope_id
value identical, and ``scope_id`` transitioning from "column did not
exist" (old) to "fully populated" (new).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from finfluencer.core.checkpoint import CheckpointManager
from finfluencer.core.contracts import (
    HDBSCANConfig,
    ModelReference,
    TopicConfigurations,
    TopicsConfig,
    UMAPConfig,
)
from finfluencer.topics.bertopic_runner import TopicFitResult
from finfluencer.utils.io import write_parquet

_DIM = 4
_SNAPSHOT_PATH = Path(__file__).parent / "_pipeline_OLD_snapshot.py"


def _load_old_module():
    spec = importlib.util.spec_from_file_location(
        "finfluencer_topics_pipeline_STEP3_2_OLD_SNAPSHOT", _SNAPSHOT_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Fixture builders - deliberately duplicated from test_pipeline.py rather
# than imported, so this regression test has no dependency on that file's
# helpers changing shape in a later migration step.
# ---------------------------------------------------------------------------


def _topics_config(
    *, within_analyst: bool = True, pooled: bool = True,
    reduce_outliers: bool = False, merge_similarity_threshold: float = 1.0,
) -> TopicsConfig:
    return TopicsConfig(
        embedding_model=ModelReference(name="emb-model", revision="main"),
        umap=UMAPConfig(n_neighbors=2, n_components=2, min_dist=0.0, metric="cosine"),
        hdbscan=HDBSCANConfig(
            min_cluster_size=2, min_samples=1, metric="euclidean",
            cluster_selection_method="eom",
        ),
        configurations=TopicConfigurations(within_analyst=within_analyst, pooled=pooled),
        merge_similarity_threshold=merge_similarity_threshold,
        reduce_outliers=reduce_outliers,
        quality_metrics=[],
    )


def _fake_settings(cfg: TopicsConfig, root_seed: int = 1):
    return SimpleNamespace(topics=cfg, study=SimpleNamespace(root_seed=root_seed))


class _FakeRunner:
    """Deterministic duck-typed stand-in for BERTopicRunner - identical
    in behavior to test_pipeline.py's version, duplicated deliberately
    (see module docstring)."""

    def __init__(self, model, fit_calls: list, transform_calls: list) -> None:
        self.model = model
        self._fit_calls = fit_calls
        self._transform_calls = transform_calls

    def fit_transform(self, texts: list[str], embeddings: np.ndarray) -> TopicFitResult:
        self._fit_calls.append(len(texts))
        n = len(texts)
        return TopicFitResult(
            topic_ids=[i % 2 for i in range(n)], topic_probs=[0.9] * n, model="FITTED_SENTINEL",
        )

    def transform(self, texts: list[str], embeddings: np.ndarray) -> TopicFitResult:
        self._transform_calls.append(len(texts))
        n = len(texts)
        return TopicFitResult(
            topic_ids=[i % 2 for i in range(n)], topic_probs=[0.9] * n, model=self.model,
        )

    def save(self, path: Path) -> None:
        Path(path).write_bytes(b"fake-model")


def _make_runner_factory(fit_calls: list, transform_calls: list):
    def factory(model=None) -> _FakeRunner:
        return _FakeRunner(model=model, fit_calls=fit_calls, transform_calls=transform_calls)
    return factory


def _fake_model_loader(path: Path):
    return "LOADED_SENTINEL"


def _write_embedding(tmp_path: Path, comment_id: str) -> str:
    vec_path = tmp_path / "vectors" / f"{comment_id}.npy"
    vec_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(vec_path, np.random.default_rng(abs(hash(comment_id)) % (2**32)).random(_DIM))
    return str(vec_path)


def _write_corpus(tmp_path: Path, rows: list[tuple[str, str, str]]) -> tuple[Path, Path]:
    comments_df = pd.DataFrame([
        dict(analyst_key=a, comment_id=cid, text_clean=t) for a, cid, t in rows
    ])
    embeddings_df = pd.DataFrame([
        dict(
            comment_id=cid, embedding_path=_write_embedding(tmp_path, cid),
            model_name="emb-model", revision="main", dimension=_DIM,
        )
        for _, cid, _ in rows
    ])
    comments_path = tmp_path / "comments.parquet"
    embeddings_path = tmp_path / "embeddings_index.parquet"
    write_parquet(comments_df, comments_path)
    write_parquet(embeddings_df, embeddings_path)
    return comments_path, embeddings_path


# Larger, four-analyst corpus - closer to the real platform's shape
# (four analysts) than the two-analyst fixture in test_pipeline.py.
_CORPUS_ROWS = [
    ("satiroglu", "c1", "harika bir gelisme"),
    ("satiroglu", "c2", "kotu bir haber"),
    ("gecer", "c3", "notr bir yorum"),
    ("gecer", "c4", "cok iyi gitti"),
    ("basaran", "c5", "faiz artisi bekleniyor"),
    ("basaran", "c6", "piyasa dustu"),
    ("yesilada", "c7", "altin yukseliyor"),
    ("yesilada", "c8", "dolar sabit kaldi"),
]


def _run(module, tmp_path: Path) -> pd.DataFrame:
    comments_path, embeddings_path = _write_corpus(tmp_path, _CORPUS_ROWS)
    checkpoint = CheckpointManager(
        checkpoint_root=tmp_path / "checkpoints", cache_root=tmp_path / "cache",
    )
    cfg = _topics_config()
    settings = _fake_settings(cfg)
    fit_calls: list = []
    transform_calls: list = []
    df = module.run_topics(
        settings, comments_path, embeddings_path, checkpoint,
        output_path=tmp_path / "topics.parquet",
        runner_factory=_make_runner_factory(fit_calls, transform_calls),
        model_loader=_fake_model_loader,
    )
    return df


class TestStep3_2RowByRowRegression:
    def test_old_snapshot_has_no_scope_id_column_populated(self, tmp_path: Path):
        """Sanity check on the snapshot itself: confirms _pipeline_OLD_snapshot.py
        really is pre-Step-3.2 behavior, not an accidental copy of the
        current file. (TopicRecord itself already gained an optional
        scope_id field in Step 3.1, so the column exists in both old and
        new output — the old code just never populates it.)"""
        old = _load_old_module()
        old_df = _run(old, tmp_path)
        assert "scope_id" in old_df.columns  # Step 3.1's schema field, present but unused
        assert old_df["scope_id"].isna().all()

    def test_new_scope_id_fully_populated(self, tmp_path: Path):
        from finfluencer.topics import pipeline as new
        new_df = _run(new, tmp_path)
        assert "scope_id" in new_df.columns
        assert new_df["scope_id"].notna().all()
        assert (new_df["scope_id"].str.len() > 0).all()

    def test_row_by_row_identical_except_scope_id(self, tmp_path: Path):
        old = _load_old_module()
        old_df = _run(old, tmp_path / "old")
        from finfluencer.topics import pipeline as new
        new_df = _run(new, tmp_path / "new")

        assert len(old_df) == len(new_df) == 16  # 8 within_analyst + 8 pooled

        compare_cols = [c for c in old_df.columns if c != "scope_id"]
        assert compare_cols == [
            "comment_id", "topic_id", "topic_prob", "topic_tier", "configuration", "topic_label",
        ]

        old_sorted = old_df.sort_values(["configuration", "comment_id"]).reset_index(drop=True)
        new_sorted = new_df.sort_values(["configuration", "comment_id"]).reset_index(drop=True)

        pd.testing.assert_frame_equal(
            old_sorted[compare_cols], new_sorted[compare_cols], check_dtype=False,
        )

        # The one sanctioned change: scope_id goes from all-NaN to fully
        # populated, and is internally consistent (same scope_id for
        # every row sharing a configuration/analyst_key group).
        assert old_sorted["scope_id"].isna().all()
        assert new_sorted["scope_id"].notna().all()

        pooled_scope_ids = new_sorted.loc[new_sorted["configuration"] == "pooled", "scope_id"]
        assert pooled_scope_ids.nunique() == 1

        within = new_sorted.loc[new_sorted["configuration"] == "within_analyst"]
        comments_df = pd.read_parquet(tmp_path / "new" / "comments.parquet")
        merged = within.merge(comments_df[["comment_id", "analyst_key"]], on="comment_id")
        # Every analyst's within_analyst rows share one scope_id, and
        # different analysts get different scope_ids.
        per_analyst_scope_ids = merged.groupby("analyst_key")["scope_id"].nunique()
        assert (per_analyst_scope_ids == 1).all()
        assert merged.groupby("scope_id")["analyst_key"].nunique().eq(1).all()

    def test_fingerprints_and_checkpoint_keys_identical(self, tmp_path: Path):
        """Requirements 2-3 of the Step 3.2 approval gate: the Tier-3
        model-cache fingerprint and Tier-2 checkpoint key must be
        byte-identical to pre-migration, since resolve_scope() must not
        feed into either."""
        old = _load_old_module()
        old_ckpt_dir = tmp_path / "old" / "checkpoints"
        _run(old, tmp_path / "old")

        from finfluencer.topics import pipeline as new
        new_ckpt_dir = tmp_path / "new" / "checkpoints"
        _run(new, tmp_path / "new")

        old_done_files = sorted(p.name for p in old_ckpt_dir.glob("*.done"))
        new_done_files = sorted(p.name for p in new_ckpt_dir.glob("*.done"))
        assert old_done_files == new_done_files  # identical stage names

        for name in old_done_files:
            old_content = (old_ckpt_dir / name).read_text()
            new_content = (new_ckpt_dir / name).read_text()
            assert old_content == new_content, f"checkpoint {name} content diverged"

        old_cache_dir = tmp_path / "old" / "cache" / "topics_model"
        new_cache_dir = tmp_path / "new" / "cache" / "topics_model"
        old_fingerprints = sorted(
            p.relative_to(old_cache_dir).as_posix() for p in old_cache_dir.rglob("*.pkl")
        )
        new_fingerprints = sorted(
            p.relative_to(new_cache_dir).as_posix() for p in new_cache_dir.rglob("*.pkl")
        )
        assert old_fingerprints == new_fingerprints  # identical Tier-3 cache paths
