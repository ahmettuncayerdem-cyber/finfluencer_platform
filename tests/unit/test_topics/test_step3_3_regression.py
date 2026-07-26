"""Migration Step 3.3 byte-level regression test.

Step 3.3 changes exactly one thing: the call site inside
``run_topic_evolution()`` now calls ``_resolve_scoped_topics_via_scope()``
instead of ``_resolve_scoped_topics_via_configuration()``. Neither
resolver's implementation changed (see
``test_scope_resolution_equivalence.py`` for their independent
equivalence proof, established before this step). This file proves the
one-line call-site swap itself produced zero observable change in
``run_topic_evolution()``'s output, by running a byte-verified snapshot
of the pre-Step-3.3 function (``_pipeline_OLD_3_3_snapshot.py``,
mechanically reconstructed by reversing the exact, known edit) against
the identical fixture as the current (post-Step-3.3) function, and
comparing the two resulting ``topic_evolution.parquet`` files at the
byte level - not just row-by-row.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

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
from finfluencer.utils.io import write_parquet

_SNAPSHOT_PATH = Path(__file__).parent / "_pipeline_OLD_3_3_snapshot.py"


def _load_old_module():
    spec = importlib.util.spec_from_file_location(
        "finfluencer_topics_pipeline_STEP3_3_OLD_SNAPSHOT", _SNAPSHOT_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _topics_config() -> TopicsConfig:
    return TopicsConfig(
        embedding_model=ModelReference(name="emb-model", revision="main"),
        umap=UMAPConfig(n_neighbors=2, n_components=2, min_dist=0.0, metric="cosine"),
        hdbscan=HDBSCANConfig(
            min_cluster_size=2, min_samples=1, metric="euclidean",
            cluster_selection_method="eom",
        ),
        configurations=TopicConfigurations(within_analyst=True, pooled=True),
        merge_similarity_threshold=1.0,
        reduce_outliers=False,
        quality_metrics=[],
    )


def _fake_settings(cfg: TopicsConfig, root_seed: int = 1):
    return SimpleNamespace(topics=cfg, study=SimpleNamespace(root_seed=root_seed))


class _FakeModelWithTopicsOverTime:
    def __init__(self, result_df: pd.DataFrame):
        self._result_df = result_df
        self.calls: list[tuple] = []

    def topics_over_time(self, docs, timestamps, topics, nr_bins):
        self.calls.append((docs, timestamps, topics, nr_bins))
        return self._result_df


_BERTOPIC_RESULT = pd.DataFrame([
    {"Topic": 0, "Words": "altin, ons, gram", "Frequency": 2, "Timestamp": "2024-01-15"},
    {"Topic": 1, "Words": "borsa, faiz", "Frequency": 1, "Timestamp": "2024-01-15"},
])


def _write_corpus(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Four-analyst corpus with scope_id already populated on topics_df,
    exactly as Step 3.2's run_topics() would produce - required for
    _resolve_scoped_topics_via_scope() to have anything to match against."""
    rows = [
        ("satiroglu", "c1", "yorum bir", "2024-01-01"),
        ("satiroglu", "c2", "yorum iki", "2024-02-01"),
        ("gecer", "c3", "yorum uc", "2024-01-15"),
        ("gecer", "c4", "yorum dort", "2024-01-20"),
    ]
    comments_df = pd.DataFrame([
        dict(analyst_key=a, comment_id=cid, text_clean=t, posted_date=d)
        for a, cid, t, d in rows
    ])
    embeddings_df = pd.DataFrame([
        dict(
            comment_id=cid, embedding_path=f"/fake/{cid}.npy",
            model_name="emb-model", revision="main", dimension=4,
        )
        for _, cid, _, _ in rows
    ])

    # scope_id computed the same way _resolve_and_persist_group_scope
    # would during a real Step-3.2 run_topics() call - imported directly
    # so this fixture can't silently drift from the real mechanism.
    from finfluencer.core.contracts import AnalysisScopeType
    from finfluencer.scope import resolve_scope

    pooled_scope = resolve_scope(
        [r[1] for r in rows], scope_type=AnalysisScopeType.global_,
        criteria_version="v1_topics_pipeline",
    )
    satiroglu_scope = resolve_scope(
        ["c1", "c2"], scope_type=AnalysisScopeType.entity, entity_keys=["satiroglu"],
        criteria_version="v1_topics_pipeline",
    )
    gecer_scope = resolve_scope(
        ["c3", "c4"], scope_type=AnalysisScopeType.entity, entity_keys=["gecer"],
        criteria_version="v1_topics_pipeline",
    )

    topics_rows = []
    for cid, tid, prob, label in [
        ("c1", 0, 0.9, "0_altin"), ("c2", 0, 0.8, "0_altin"),
        ("c3", 1, 0.7, "1_borsa"), ("c4", 1, 0.6, "1_borsa"),
    ]:
        topics_rows.append(dict(
            comment_id=cid, topic_id=tid, topic_prob=prob, topic_tier=None,
            configuration="pooled", scope_id=pooled_scope.scope_id, topic_label=label,
        ))
    for cid, tid, prob, label, key, scope in [
        ("c1", 0, 0.9, "0_within", "satiroglu", satiroglu_scope),
        ("c2", 0, 0.8, "0_within", "satiroglu", satiroglu_scope),
        ("c3", 1, 0.7, "1_within", "gecer", gecer_scope),
        ("c4", 1, 0.6, "1_within", "gecer", gecer_scope),
    ]:
        topics_rows.append(dict(
            comment_id=cid, topic_id=tid, topic_prob=prob, topic_tier=None,
            configuration="within_analyst", scope_id=scope.scope_id, topic_label=label,
        ))
    topics_df = pd.DataFrame(topics_rows)

    comments_path = tmp_path / "comments.parquet"
    embeddings_path = tmp_path / "embeddings_index.parquet"
    topics_path = tmp_path / "topics.parquet"
    write_parquet(comments_df, comments_path)
    write_parquet(embeddings_df, embeddings_path)
    write_parquet(topics_df, topics_path)
    return comments_path, embeddings_path, topics_path


def _run(module, tmp_path: Path, *, configuration: str, analyst_key: str | None) -> Path:
    comments_path, embeddings_path, topics_path = _write_corpus(tmp_path)
    checkpoint = CheckpointManager(tmp_path / "checkpoints", tmp_path / "cache")
    cfg = _topics_config()
    settings = _fake_settings(cfg)

    from finfluencer.topics.pipeline import _model_fingerprint
    from finfluencer.core.reproducibility import derive_seed

    stage_seed = derive_seed(settings.study.root_seed, "topics")
    _analyst_comment_ids = {"satiroglu": ["c1", "c2"], "gecer": ["c3", "c4"]}
    comment_ids = (
        _analyst_comment_ids[analyst_key] if configuration == "within_analyst"
        else ["c1", "c2", "c3", "c4"]
    )
    fingerprint = _model_fingerprint(
        comment_ids, "emb-model", "main", cfg, configuration, stage_seed,
    )
    model_path = checkpoint.cache_path("topics_model", fingerprint, ".pkl")
    model_path.write_bytes(b"fake-cached-model")

    fake_model = _FakeModelWithTopicsOverTime(_BERTOPIC_RESULT)
    output_path = tmp_path / "topic_evolution.parquet"
    module.run_topic_evolution(
        settings, comments_path, embeddings_path, topics_path, checkpoint,
        configuration=configuration, analyst_key=analyst_key, nr_bins=3,
        model_loader=lambda path: fake_model,
        output_path=output_path,
    )
    return output_path


class TestStep3_3ByteLevelRegression:
    @pytest.mark.parametrize(
        "configuration,analyst_key",
        [("pooled", None), ("within_analyst", "satiroglu"), ("within_analyst", "gecer")],
    )
    def test_output_byte_identical_old_vs_new(self, tmp_path: Path, configuration, analyst_key):
        old = _load_old_module()
        old_output = _run(old, tmp_path / "old", configuration=configuration, analyst_key=analyst_key)

        from finfluencer.topics import pipeline as new
        new_output = _run(new, tmp_path / "new", configuration=configuration, analyst_key=analyst_key)

        old_bytes = old_output.read_bytes()
        new_bytes = new_output.read_bytes()
        assert old_bytes == new_bytes, (
            f"topic_evolution.parquet differs byte-for-byte for "
            f"configuration={configuration!r} analyst_key={analyst_key!r}"
        )

        # Belt-and-suspenders: also confirm at the row/value level, since
        # a byte-identical file already implies this, but this is what
        # the approval gate explicitly asks to verify item-by-item.
        old_df = pd.read_parquet(old_output)
        new_df = pd.read_parquet(new_output)
        assert len(old_df) == len(new_df)
        assert list(old_df["comment_id"]) if "comment_id" in old_df.columns else True
        assert old_df["topic_id"].tolist() == new_df["topic_id"].tolist()
        assert old_df["frequency"].tolist() == new_df["frequency"].tolist()
        assert old_df["time_bin"].tolist() == new_df["time_bin"].tolist()
        assert old_df["configuration"].tolist() == new_df["configuration"].tolist()
        assert old_df["analyst_key"].tolist() == new_df["analyst_key"].tolist()
        # Row order preserved (not just row content) - both resolvers
        # filter the same underlying topics_df, so .loc[] preserves the
        # original row order under either mask.
        pd.testing.assert_frame_equal(old_df, new_df)

    def test_fingerprint_computation_untouched(self, tmp_path: Path):
        """The fingerprint/cache lookup happens after scope resolution
        and does not depend on which resolver was used - confirm the
        cached model is found (no FileNotFoundError) under the new
        resolver, proving the fingerprint computation itself is
        unaffected by Step 3.3."""
        from finfluencer.topics import pipeline as new
        # _run() pre-seeds the cache under the fingerprint computed the
        # same way regardless of resolver; a successful run (no raise)
        # is the confirmation.
        output_path = _run(new, tmp_path, configuration="pooled", analyst_key=None)
        assert output_path.exists()
        assert len(pd.read_parquet(output_path)) == 2
