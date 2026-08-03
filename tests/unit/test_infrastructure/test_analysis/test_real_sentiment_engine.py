"""Tests for `RealSentimentAnalysisEngine` (Release Blocker #6,
`docs/implementation/RB6_ANALYSIS_DISPATCH_READINESS_REVIEW.md` sections 5.2/5.3).

Tests the *composition* this class adds -- preprocess, then delegate to a real
`SentimentAnalysisAdapter` -- not the internals of either piece, each already covered by its own
test suite. `preprocess_engine` is faked (duck-typed, recording call order); the sentiment
`provider` reuses `test_sentiment_adapter.py`'s own established fake pattern for the same reason
that file fakes it (no `transformers`/`torch` required to run these tests).
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import pytest

from finfluencer.core.contracts import ModelReference, SentimentConfig, TargetOfAffectConfig
from finfluencer.domain.analysis_engine import AnalysisOutcome
from finfluencer.infrastructure.analysis import RealSentimentAnalysisEngine
from finfluencer.utils.io import write_parquet


def _sentiment_config() -> SentimentConfig:
    return SentimentConfig(
        primary_model=ModelReference(name="sent-model", revision="main"),
        batch_size=8,
        pseudo_neutral_band=(0.45, 0.55),
        target_of_affect=TargetOfAffectConfig(
            enabled=False, base_model="unused", base_revision="main",
            heads=[], target_labels=[],
        ),
    )


def _fake_settings() -> Any:
    return SimpleNamespace(sentiment=_sentiment_config(), study=SimpleNamespace(root_seed=1))


class _FakeProvider:
    """Same shape `test_sentiment_adapter.py`'s own fake already establishes: deterministic,
    known polarity -- positive if the text contains "iyi"/"harika", negative otherwise.
    """

    key: str = "fake"
    model_name: str = "fake-sentiment-model"
    revision: str = "main"
    device: str = "cpu"

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def predict(self, texts: list[str]) -> np.ndarray:
        self.calls.append(list(texts))
        positive_markers = ("iyi", "harika")
        return np.asarray(
            [0.9 if any(m in t for m in positive_markers) else 0.1 for t in texts],
            dtype=np.float32,
        )


class _FakePreprocessEngine:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def ensure_clean(self, collection_run_id: str) -> SimpleNamespace:
        self.calls.append(collection_run_id)
        return SimpleNamespace(comments_path=None, row_count=0)


_ROWS = [
    ("satiroglu", "c1", "harika bir gelisme"),
    ("satiroglu", "c2", "kotu bir haber"),
    ("gecer", "c3", "notr bir yorum"),
]


def _write_fixture(base_root: Path, collection_run_id: str) -> None:
    comments_path = base_root / collection_run_id / "data_raw" / "comments.parquet"
    comments_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(
        [dict(analyst_key=a, comment_id=cid, text_clean=t) for a, cid, t in _ROWS],
    )
    write_parquet(df, comments_path)


def test_run_sequences_preprocess_then_sentiment(tmp_path: Path) -> None:
    base_root = tmp_path / "runs"
    _write_fixture(base_root, "cr-1")

    preprocess = _FakePreprocessEngine()
    provider = _FakeProvider()
    engine = RealSentimentAnalysisEngine(
        settings=_fake_settings(),
        base_root=base_root,
        preprocess_engine=preprocess,
        provider=provider,
    )

    outcome = engine.run(analysis_run_id="ar-1", collection_run_id="cr-1")

    assert isinstance(outcome, AnalysisOutcome)
    assert outcome.row_count == 3
    # sentiment_class is binary (positive if prob >= 0.5 else negative); the fake's marker-based
    # scores (0.9 for "harika"/"iyi", 0.1 otherwise) produce both classes across these 3 rows.
    assert outcome.topic_count == 2
    assert preprocess.calls == ["cr-1"]
    assert provider.calls  # the sentiment provider was actually invoked


def test_shared_sentiment_engine_instance_serves_multiple_collection_runs(tmp_path: Path) -> None:
    """Unlike `RealTopicsAnalysisEngine`, `SentimentAnalysisAdapter` has no fixed-path bug --
    proves the one shared instance built in `__init__` correctly handles two different
    `collection_run_id`s without cross-contamination.
    """
    base_root = tmp_path / "runs"
    _write_fixture(base_root, "cr-a")
    _write_fixture(base_root, "cr-b")

    preprocess = _FakePreprocessEngine()
    engine = RealSentimentAnalysisEngine(
        settings=_fake_settings(), base_root=base_root,
        preprocess_engine=preprocess, provider=_FakeProvider(),
    )

    outcome_a = engine.run(analysis_run_id="ar-a", collection_run_id="cr-a")
    outcome_b = engine.run(analysis_run_id="ar-b", collection_run_id="cr-b")

    assert outcome_a.row_count == 3
    assert outcome_b.row_count == 3
    assert preprocess.calls == ["cr-a", "cr-b"]


def test_run_rejects_empty_analysis_run_id(tmp_path: Path) -> None:
    engine = RealSentimentAnalysisEngine(
        settings=_fake_settings(), base_root=tmp_path,
        preprocess_engine=_FakePreprocessEngine(), provider=_FakeProvider(),
    )
    with pytest.raises(ValueError):
        engine.run(analysis_run_id="", collection_run_id="cr-1")


def test_run_rejects_empty_collection_run_id(tmp_path: Path) -> None:
    engine = RealSentimentAnalysisEngine(
        settings=_fake_settings(), base_root=tmp_path,
        preprocess_engine=_FakePreprocessEngine(), provider=_FakeProvider(),
    )
    with pytest.raises(ValueError):
        engine.run(analysis_run_id="ar-1", collection_run_id="")


def test_default_preprocess_engine_is_real_when_not_injected(tmp_path: Path) -> None:
    from finfluencer.infrastructure.analysis import PreprocessEngineAdapter

    engine = RealSentimentAnalysisEngine(
        settings=_fake_settings(), base_root=tmp_path, provider=_FakeProvider(),
    )
    assert isinstance(engine._preprocess_engine, PreprocessEngineAdapter)


def test_module_does_not_import_presentation_or_api() -> None:
    import finfluencer.infrastructure.analysis.real_sentiment_engine as module

    tree = ast.parse(inspect.getsource(module))
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    assert not any(m.startswith("finfluencer.presentation") for m in imported_modules)
    assert not any(m.startswith("finfluencer.api") for m in imported_modules)
