"""Tests for `SentimentAnalysisAdapter` (BACKLOG.md T-022).

Same injection technique already established in `test_topics_adapter.py` (T-019): a fake
`SentimentProvider` stands in for `TransformerSentimentClassifier`, so these tests never require
`transformers`/`torch` to be installed -- confirmed consistent with the pre-existing
`tests/unit/test_sentiment` suite (20 passed, no heavy ML deps installed in this sandbox).
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from finfluencer.core.contracts import ModelReference, SentimentConfig, TargetOfAffectConfig
from finfluencer.domain.analysis_engine import AnalysisOutcome
from finfluencer.infrastructure.analysis import SentimentAnalysisAdapter
from finfluencer.sentiment.base import SentimentProvider
from finfluencer.utils.io import read_parquet, write_parquet


def _sentiment_config() -> SentimentConfig:
    return SentimentConfig(
        primary_model=ModelReference(name="fake-sentiment-model", revision="main"),
        batch_size=8,
        pseudo_neutral_band=(0.45, 0.55),
        target_of_affect=TargetOfAffectConfig(
            enabled=False, base_model="unused", base_revision="main",
            heads=[], target_labels=[],
        ),
    )


class _FakeSettings:
    def __init__(self, cfg: SentimentConfig, root_seed: int = 1) -> None:
        self.sentiment = cfg
        self.study = _FakeStudy(root_seed)


class _FakeStudy:
    def __init__(self, root_seed: int) -> None:
        self.root_seed = root_seed


def _fake_settings(cfg: SentimentConfig, root_seed: int = 1) -> _FakeSettings:
    return _FakeSettings(cfg, root_seed)


class _FakeProvider:
    """Deterministic, known polarity: positive if the text contains "iyi"/"harika",
    negative otherwise -- the "fixture dataset with known expected sentiment scores" T-022's own
    Verification line requires."""

    key: str = "fake"
    model_name: str = "fake-sentiment-model"
    revision: str = "main"
    device: str = "cpu"

    def __init__(self) -> None:
        self.calls: list[int] = []

    def predict(self, texts: list[str]) -> np.ndarray:
        self.calls.append(len(texts))
        positive_markers = ("iyi", "harika")
        return np.asarray(
            [0.9 if any(m in t for m in positive_markers) else 0.1 for t in texts],
            dtype=np.float32,
        )


def _write_fixture_dataset(*, base_root: Path, collection_run_id: str) -> None:
    """Writes comments.parquet at the T-010-convention path this adapter resolves
    (`base_root/collection_run_id/data_raw/comments.parquet`)."""
    rows = [
        ("satiroglu", "c1", "harika bir gelisme"),
        ("satiroglu", "c2", "kotu bir haber"),
        ("gecer", "c3", "cok iyi gitti"),
        ("gecer", "c4", "berbat bir durum"),
    ]
    comments_df = pd.DataFrame(
        [dict(analyst_key=a, comment_id=cid, text_clean=t) for a, cid, t in rows],
    )
    comments_path = base_root / collection_run_id / "data_raw" / "comments.parquet"
    comments_path.parent.mkdir(parents=True, exist_ok=True)
    write_parquet(comments_df, comments_path)


def test_adapter_produces_known_expected_sentiment_classes(tmp_path: Path) -> None:
    base_root = tmp_path / "runs"
    collection_run_id = "cr-fixture-1"
    _write_fixture_dataset(base_root=base_root, collection_run_id=collection_run_id)

    provider = _FakeProvider()
    adapter = SentimentAnalysisAdapter(
        settings=_fake_settings(_sentiment_config()),
        base_root=base_root,
        provider=provider,
    )

    outcome = adapter.run(analysis_run_id="ar-1", collection_run_id=collection_run_id)

    assert isinstance(outcome, AnalysisOutcome)
    assert outcome.analysis_run_id == "ar-1"
    assert outcome.row_count == 4
    # 2 distinct sentiment_class values produced (positive + negative) -- known, deterministic.
    assert outcome.topic_count == 2

    sentiment_path = base_root / "ar-1" / "data_processed" / "sentiment.parquet"
    sentiment_df = read_parquet(sentiment_path)
    by_id = sentiment_df.set_index("comment_id")["sentiment_class"].to_dict()
    assert by_id["c1"] == "positive"
    assert by_id["c2"] == "negative"
    assert by_id["c3"] == "positive"
    assert by_id["c4"] == "negative"


def test_adapter_isolates_checkpoint_and_cache_per_analysis_run_id(tmp_path: Path) -> None:
    base_root = tmp_path / "runs"
    collection_run_id = "cr-fixture-2"
    _write_fixture_dataset(base_root=base_root, collection_run_id=collection_run_id)

    adapter = SentimentAnalysisAdapter(
        settings=_fake_settings(_sentiment_config()),
        base_root=base_root,
        provider=_FakeProvider(),
    )

    adapter.run(analysis_run_id="ar-a", collection_run_id=collection_run_id)
    adapter.run(analysis_run_id="ar-b", collection_run_id=collection_run_id)

    assert (base_root / "ar-a" / "checkpoints").exists()
    assert (base_root / "ar-b" / "checkpoints").exists()
    assert (base_root / "ar-a" / "checkpoints") != (base_root / "ar-b" / "checkpoints")
    assert (base_root / "ar-a" / "data_processed" / "sentiment.parquet").exists()
    assert (base_root / "ar-b" / "data_processed" / "sentiment.parquet").exists()


def test_provider_is_not_constructed_until_run_is_called(tmp_path: Path) -> None:
    # Lazy-resolution discipline (mirrors TopicsAnalysisAdapter's model_loader/runner_factory):
    # constructing the adapter must not invoke the provider factory.
    factory_calls: list[int] = []

    def factory() -> SentimentProvider:
        factory_calls.append(1)
        return _FakeProvider()

    adapter = SentimentAnalysisAdapter(
        settings=_fake_settings(_sentiment_config()),
        base_root=tmp_path,
        provider_factory=factory,
    )
    assert factory_calls == []  # not called at construction time

    base_root = tmp_path / "runs"
    collection_run_id = "cr-fixture-3"
    _write_fixture_dataset(base_root=base_root, collection_run_id=collection_run_id)
    adapter2 = SentimentAnalysisAdapter(
        settings=_fake_settings(_sentiment_config()), base_root=base_root, provider_factory=factory,
    )
    adapter2.run(analysis_run_id="ar-1", collection_run_id=collection_run_id)
    assert factory_calls == [1]  # invoked exactly once, only once run() executes


def test_run_rejects_empty_analysis_run_id(tmp_path: Path) -> None:
    adapter = SentimentAnalysisAdapter(
        settings=_fake_settings(_sentiment_config()), base_root=tmp_path, provider=_FakeProvider(),
    )
    with pytest.raises(ValueError):
        adapter.run(analysis_run_id="", collection_run_id="cr-1")


def test_run_rejects_empty_collection_run_id(tmp_path: Path) -> None:
    adapter = SentimentAnalysisAdapter(
        settings=_fake_settings(_sentiment_config()), base_root=tmp_path, provider=_FakeProvider(),
    )
    with pytest.raises(ValueError):
        adapter.run(analysis_run_id="ar-1", collection_run_id="")


def test_adapter_module_does_not_import_presentation_or_api() -> None:
    # PRODUCT_ARCHITECTURE.md section 12.1: Infrastructure's forbidden dependencies include
    # Presentation and API -- same ast-based check T-010/T-019's own adapter tests use.
    import finfluencer.infrastructure.analysis.sentiment_adapter as module

    tree = ast.parse(inspect.getsource(module))
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    assert not any(m.startswith("finfluencer.presentation") for m in imported_modules)
    assert not any(m.startswith("finfluencer.api") for m in imported_modules)


def test_adapter_never_modifies_wrapped_legacy_modules() -> None:
    import finfluencer.infrastructure.analysis.sentiment_adapter as module

    source = inspect.getsource(module)
    for forbidden in ("setattr(", "monkeypatch", "importlib.reload"):
        assert forbidden not in source
