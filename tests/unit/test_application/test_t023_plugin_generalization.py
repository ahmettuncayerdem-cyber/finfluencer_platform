"""T-023 -- verify the `IAnalysisEngine` plugin abstraction generalized to a second
`AnalysisType` (`SentimentAnalysisAdapter`, T-022) with zero orchestrator code changes.

Structural evidence only -- no new production code (same verification-only precedent as
T-021). `git diff <T-020-close>..HEAD -- src/finfluencer/application/ src/finfluencer/domain/`
already confirms zero lines changed since T-020's close; this file additionally proves the
orchestrator *works*, not just that its source file is unedited, when constructed with a
`SentimentAnalysisAdapter` instead of a `TopicsAnalysisAdapter` -- the identical,
unmodified `IAnalysisEngine` dependency-injection seam T-020 already established.
"""

from __future__ import annotations

import ast
import inspect
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd

from finfluencer.application.orchestrators import (
    StartAnalysisRunCommand,
    StartAnalysisRunOrchestrator,
)
from finfluencer.core.contracts import ModelReference, SentimentConfig, TargetOfAffectConfig
from finfluencer.domain.analysis_engine import IAnalysisEngine
from finfluencer.domain.entities._common import EntityId
from finfluencer.domain.entities.analysis_run import AnalysisRun, AnalysisRunStatus
from finfluencer.infrastructure.analysis import SentimentAnalysisAdapter, TopicsAnalysisAdapter
from finfluencer.utils.io import write_parquet


class _FakeAnalysisRunRepository:
    """Minimal in-memory `IAnalysisRunRepository` double -- self-contained, mirrors the
    equivalent fake already established in `test_start_analysis_run_orchestrator.py` (T-020)
    without importing across test modules (same self-containment convention every adapter test
    file in this repo already follows)."""

    def __init__(self) -> None:
        self._by_key: dict[tuple[EntityId, str], AnalysisRun] = {}

    def add(self, analysis_run: AnalysisRun, *, idempotency_key: str) -> None:
        self._by_key[(analysis_run.project_id, idempotency_key)] = analysis_run

    def get_by_idempotency_key(
        self, project_id: EntityId, idempotency_key: str,
    ) -> AnalysisRun | None:
        return self._by_key.get((project_id, idempotency_key))

    def save(self, analysis_run: AnalysisRun) -> None:
        # No-op (EPIC-07'): shared object reference already keeps `_by_key` correct --
        # StartAnalysisRunOrchestrator now calls this after complete()/fail().
        pass


class _FakeSentimentProvider:
    key: str = "fake"
    model_name: str = "fake-sentiment-model"
    revision: str = "main"
    device: str = "cpu"

    def predict(self, texts: list[str]) -> np.ndarray:
        return np.asarray(
            [0.9 if ("iyi" in t or "harika" in t) else 0.1 for t in texts], dtype=np.float32,
        )


def _fake_sentiment_settings() -> Any:
    cfg = SentimentConfig(
        primary_model=ModelReference(name="fake-sentiment-model", revision="main"),
        batch_size=8,
        pseudo_neutral_band=(0.45, 0.55),
        target_of_affect=TargetOfAffectConfig(
            enabled=False, base_model="unused", base_revision="main", heads=[], target_labels=[],
        ),
    )
    return SimpleNamespace(sentiment=cfg, study=SimpleNamespace(root_seed=1))


def _write_fixture_comments(*, base_root: Path, collection_run_id: str) -> None:
    rows = [
        ("satiroglu", "c1", "harika bir gelisme"),
        ("gecer", "c2", "kotu bir haber"),
    ]
    df = pd.DataFrame([dict(analyst_key=a, comment_id=cid, text_clean=t) for a, cid, t in rows])
    path = base_root / collection_run_id / "data_raw" / "comments.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_parquet(df, path)


def _project_id() -> EntityId:
    return EntityId(uuid.uuid4())


def test_orchestrator_dispatches_sentiment_adapter_through_the_unmodified_ianalysisengine_seam(
    tmp_path: Path,
) -> None:
    """The same `StartAnalysisRunOrchestrator` constructor, unmodified since T-020, accepts a
    `SentimentAnalysisAdapter` wherever it previously only ever saw a `TopicsAnalysisAdapter` --
    proving the plugin abstraction generalizes at runtime, not just that the source file
    happens to be unedited."""
    base_root = tmp_path / "runs"
    collection_run_id = str(uuid.uuid4())
    _write_fixture_comments(base_root=base_root, collection_run_id=collection_run_id)

    engine = SentimentAnalysisAdapter(
        settings=_fake_sentiment_settings(), base_root=base_root, provider=_FakeSentimentProvider(),
    )
    orchestrator = StartAnalysisRunOrchestrator(
        analysis_run_repository=_FakeAnalysisRunRepository(), analysis_engine=engine,
    )

    command = StartAnalysisRunCommand(
        project_id=_project_id(),
        collection_run_id=EntityId(uuid.UUID(collection_run_id)),
        analysis_type_id=EntityId(uuid.uuid4()),
        analysis_type_version="1.0.0",
        idempotency_key="key-1",
    )
    result = orchestrator.execute(command)

    assert result.status == AnalysisRunStatus.COMPLETED.value
    assert result.row_count == 2
    assert result.topic_count == 2  # distinct sentiment_class values: positive + negative


def test_topics_and_sentiment_adapters_expose_an_identical_run_signature() -> None:
    """Both concrete `IAnalysisEngine` implementations must be interchangeable at the
    orchestrator's call site -- verified structurally via their `run()` signatures, since
    `IAnalysisEngine` (a `Protocol`) is not declared `runtime_checkable` and so cannot be
    `isinstance`-checked directly."""
    topics_sig = inspect.signature(TopicsAnalysisAdapter.run)
    sentiment_sig = inspect.signature(SentimentAnalysisAdapter.run)
    protocol_sig = inspect.signature(IAnalysisEngine.run)

    def _params(sig: inspect.Signature) -> list[str]:
        return [p for p in sig.parameters if p != "self"]

    assert _params(topics_sig) == _params(sentiment_sig) == _params(protocol_sig)
    assert (
        topics_sig.return_annotation
        == sentiment_sig.return_annotation
        == protocol_sig.return_annotation
    )


def test_orchestrator_source_contains_no_analysistype_specific_branching() -> None:
    """The orchestrator must remain generic across `AnalysisType` implementations -- confirms
    it never *imports* `finfluencer.topics.*`/`finfluencer.sentiment.*` or any concrete
    Infrastructure adapter, and never branches its own logic (`if`/`elif`) on any
    `AnalysisType`-identifying value.

    Deliberately checks imports/control-flow via `ast`, not a raw substring scan of the whole
    source: the module's own docstring legitimately *names* `finfluencer.topics.*` as an
    example of a forbidden import (prose, not code), and `AnalysisOutcome.topic_count` (a field
    name, already tracked as TD-03/DI-01 in the Governance Register) legitimately contains
    "topic" without being AnalysisType-specific branching. A substring check would produce a
    false failure on both; an import/control-flow check measures the actual property this test
    exists to verify.
    """
    import finfluencer.application.orchestrators.start_analysis_run as module

    tree = ast.parse(inspect.getsource(module))

    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    forbidden_import_prefixes = (
        "finfluencer.topics", "finfluencer.sentiment",
        "finfluencer.infrastructure.analysis", "finfluencer.embeddings",
    )
    for imported in imported_modules:
        assert not imported.startswith(forbidden_import_prefixes), (
            f"orchestrator unexpectedly imports {imported!r} -- must depend on "
            "IAnalysisEngine abstractly, never a concrete AnalysisType implementation"
        )

    # No `if`/`elif` anywhere in the module -- StartAnalysisRunOrchestrator's only branching is
    # the create/replay/retry status dispatch (T-020's own design), never a per-AnalysisType
    # conditional. Confirms the plugin abstraction requires zero orchestrator-side special-casing
    # to support a second implementation, not merely that no one happened to add one.
    if_nodes = [n for n in ast.walk(tree) if isinstance(n, ast.If)]
    assert len(if_nodes) == 3, (
        f"expected exactly the 3 known status-dispatch branches (existing is None / COMPLETED / "
        f"FAILED), found {len(if_nodes)} -- investigate before assuming AnalysisType-specific "
        "branching was NOT introduced"
    )
