"""Tests for StartAnalysisRunOrchestrator (BACKLOG.md T-020).

Exercises Application -> Domain -> (Domain-owned `IAnalysisEngine`/`IAnalysisRunRepository`
interfaces) -> a real T-019 `TopicsAnalysisAdapter` -> the real, unmodified `topics/` pipeline,
end to end -- not mocks standing in for the whole chain. Only the repository is a fake
(Persistence remains abstract). Same discipline as
`test_start_collection_run_orchestrator.py` (T-011).
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
import pytest

from finfluencer.application.orchestrators import (
    StartAnalysisRunCommand,
    StartAnalysisRunOrchestrator,
    StartAnalysisRunResult,
)
from finfluencer.core.contracts import (
    HDBSCANConfig,
    ModelReference,
    TopicConfigurations,
    TopicsConfig,
    UMAPConfig,
)
from finfluencer.domain.entities._common import EntityId
from finfluencer.domain.entities.analysis_run import AnalysisRun, AnalysisRunStatus
from finfluencer.infrastructure.analysis import TopicsAnalysisAdapter
from finfluencer.topics.bertopic_runner import TopicFitResult
from finfluencer.utils.io import write_parquet

_DIM = 4


class FakeAnalysisRunRepository:
    """In-memory test double for `IAnalysisRunRepository` -- not a Persistence Layer
    implementation. Deliberately allows a second `add()` for an already-used key to overwrite
    the mapping (per this Protocol's own docstring -- a genuine behavioral difference from
    `FakeCollectionRunRepository`, not an oversight).
    """

    def __init__(self) -> None:
        self._by_key: dict[tuple[EntityId, str], AnalysisRun] = {}
        self.add_calls = 0

    def add(self, analysis_run: AnalysisRun, *, idempotency_key: str) -> None:
        self.add_calls += 1
        self._by_key[(analysis_run.project_id, idempotency_key)] = analysis_run

    def get_by_idempotency_key(
        self, project_id: EntityId, idempotency_key: str,
    ) -> AnalysisRun | None:
        return self._by_key.get((project_id, idempotency_key))


def _topics_config() -> TopicsConfig:
    return TopicsConfig(
        embedding_model=ModelReference(name="emb-model", revision="main"),
        umap=UMAPConfig(n_neighbors=2, n_components=2, min_dist=0.0, metric="cosine"),
        hdbscan=HDBSCANConfig(
            min_cluster_size=2, min_samples=1, metric="euclidean",
            cluster_selection_method="eom",
        ),
        configurations=TopicConfigurations(within_analyst=False, pooled=True),
        merge_similarity_threshold=1.0,
        reduce_outliers=False,
        quality_metrics=[],
    )


def _fake_settings() -> Any:
    return SimpleNamespace(topics=_topics_config(), study=SimpleNamespace(root_seed=1))


class _FakeRunner:
    def __init__(self, model: Any, *, raise_on_fit: bool = False) -> None:
        self.model = model
        self._raise_on_fit = raise_on_fit

    def fit_transform(self, texts: list[str], embeddings: np.ndarray) -> TopicFitResult:
        if self._raise_on_fit:
            raise RuntimeError("simulated BERTopic fit crash")
        n = len(texts)
        return TopicFitResult(
            topic_ids=[i % 2 for i in range(n)], topic_probs=[0.9] * n, model="FITTED_SENTINEL",
        )

    def transform(self, texts: list[str], embeddings: np.ndarray) -> TopicFitResult:
        n = len(texts)
        return TopicFitResult(
            topic_ids=[i % 2 for i in range(n)], topic_probs=[0.9] * n, model=self.model,
        )

    def save(self, path: Path) -> None:
        Path(path).write_bytes(b"fake-model")


def _make_runner_factory(*, raise_on_fit: bool = False):
    def factory(model: Any = None) -> _FakeRunner:
        return _FakeRunner(model=model, raise_on_fit=raise_on_fit)
    return factory


def _fake_model_loader(path: Path) -> str:
    return "LOADED_SENTINEL"


def _write_embedding(tmp_path: Path, comment_id: str) -> str:
    vec_path = tmp_path / "vectors" / f"{comment_id}.npy"
    vec_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(vec_path, np.random.default_rng(abs(hash(comment_id)) % (2**32)).random(_DIM))
    return str(vec_path)


def _write_fixture_dataset(tmp_path: Path, *, base_root: Path, collection_run_id: str) -> Path:
    rows = [
        ("satiroglu", "c1", "harika bir gelisme"),
        ("satiroglu", "c2", "kotu bir haber"),
        ("gecer", "c3", "notr bir yorum"),
        ("gecer", "c4", "cok iyi gitti"),
    ]
    comments_df = pd.DataFrame(
        [dict(analyst_key=a, comment_id=cid, text_clean=t) for a, cid, t in rows],
    )
    embeddings_df = pd.DataFrame(
        [
            dict(
                comment_id=cid,
                embedding_path=_write_embedding(tmp_path, cid),
                model_name="emb-model", revision="main", dimension=_DIM,
            )
            for _, cid, _ in rows
        ],
    )
    comments_path = base_root / collection_run_id / "data_raw" / "comments.parquet"
    comments_path.parent.mkdir(parents=True, exist_ok=True)
    write_parquet(comments_df, comments_path)

    embeddings_path = tmp_path / "embeddings_index.parquet"
    write_parquet(embeddings_df, embeddings_path)
    return embeddings_path


def _make_engine(
    base_root: Path, embeddings_index_path: Path, *, raise_on_fit: bool = False,
) -> TopicsAnalysisAdapter:
    return TopicsAnalysisAdapter(
        settings=_fake_settings(),
        base_root=base_root,
        embeddings_index_path=embeddings_index_path,
        runner_factory=_make_runner_factory(raise_on_fit=raise_on_fit),
        model_loader=_fake_model_loader,
    )


def _project_id() -> EntityId:
    return EntityId(uuid.uuid4())


def _command(
    *, project_id: EntityId, collection_run_id: str, idempotency_key: str,
) -> StartAnalysisRunCommand:
    # collection_run_id is always a `str(uuid.uuid4())` from _write_fixture_dataset's own
    # caller -- round-tripping through uuid.UUID() gives AnalysisRun a real EntityId while
    # str(EntityId(...)) still matches the directory name _write_fixture_dataset already wrote.
    return StartAnalysisRunCommand(
        project_id=project_id,
        collection_run_id=EntityId(uuid.UUID(collection_run_id)),
        analysis_type_id=EntityId(uuid.uuid4()),
        analysis_type_version="1.0.0",
        idempotency_key=idempotency_key,
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_execute_runs_analysis_end_to_end_and_completes(tmp_path: Path) -> None:
    base_root = tmp_path / "runs"
    collection_run_id = str(uuid.uuid4())
    embeddings_path = _write_fixture_dataset(
        tmp_path, base_root=base_root, collection_run_id=collection_run_id,
    )
    repo = FakeAnalysisRunRepository()
    orchestrator = StartAnalysisRunOrchestrator(
        analysis_run_repository=repo,
        analysis_engine=_make_engine(base_root, embeddings_path),
    )
    project_id = _project_id()

    result = orchestrator.execute(
        _command(project_id=project_id, collection_run_id=collection_run_id, idempotency_key="key-1"),
    )

    assert isinstance(result, StartAnalysisRunResult)
    assert result.project_id == project_id
    assert result.status == "completed"
    assert result.row_count == 4
    assert result.topic_count == 2
    assert repo.add_calls == 1


# ---------------------------------------------------------------------------
# Idempotency / duplicate dispatch
# ---------------------------------------------------------------------------


def test_duplicate_dispatch_with_same_key_does_not_create_a_second_run(tmp_path: Path) -> None:
    base_root = tmp_path / "runs"
    collection_run_id = str(uuid.uuid4())
    embeddings_path = _write_fixture_dataset(
        tmp_path, base_root=base_root, collection_run_id=collection_run_id,
    )
    repo = FakeAnalysisRunRepository()
    orchestrator = StartAnalysisRunOrchestrator(
        analysis_run_repository=repo,
        analysis_engine=_make_engine(base_root, embeddings_path),
    )
    command = _command(
        project_id=_project_id(), collection_run_id=collection_run_id, idempotency_key="dup-key",
    )

    first = orchestrator.execute(command)
    second = orchestrator.execute(command)

    assert first.id == second.id
    assert repo.add_calls == 1
    assert second.status == "completed"
    # Idempotent replay does not re-derive row/topic counts.
    assert second.row_count is None
    assert second.topic_count is None


def test_duplicate_dispatch_with_different_keys_creates_two_distinct_runs(tmp_path: Path) -> None:
    base_root = tmp_path / "runs"
    collection_run_id = str(uuid.uuid4())
    embeddings_path = _write_fixture_dataset(
        tmp_path, base_root=base_root, collection_run_id=collection_run_id,
    )
    repo = FakeAnalysisRunRepository()
    orchestrator = StartAnalysisRunOrchestrator(
        analysis_run_repository=repo,
        analysis_engine=_make_engine(base_root, embeddings_path),
    )
    project_id = _project_id()

    a = orchestrator.execute(
        _command(project_id=project_id, collection_run_id=collection_run_id, idempotency_key="key-a"),
    )
    b = orchestrator.execute(
        _command(project_id=project_id, collection_run_id=collection_run_id, idempotency_key="key-b"),
    )

    assert a.id != b.id
    assert repo.add_calls == 2


def test_same_idempotency_key_different_projects_do_not_collide(tmp_path: Path) -> None:
    base_root = tmp_path / "runs"
    collection_run_id = str(uuid.uuid4())
    embeddings_path = _write_fixture_dataset(
        tmp_path, base_root=base_root, collection_run_id=collection_run_id,
    )
    repo = FakeAnalysisRunRepository()
    orchestrator = StartAnalysisRunOrchestrator(
        analysis_run_repository=repo,
        analysis_engine=_make_engine(base_root, embeddings_path),
    )

    a = orchestrator.execute(
        _command(
            project_id=_project_id(), collection_run_id=collection_run_id,
            idempotency_key="shared-key",
        ),
    )
    b = orchestrator.execute(
        _command(
            project_id=_project_id(), collection_run_id=collection_run_id,
            idempotency_key="shared-key",
        ),
    )

    assert a.id != b.id
    assert repo.add_calls == 2


# ---------------------------------------------------------------------------
# Failure propagation and retry (NOT resume -- section 10.1 line 577)
# ---------------------------------------------------------------------------


def test_execute_marks_the_run_failed_and_reraises_on_a_fit_crash(tmp_path: Path) -> None:
    base_root = tmp_path / "runs"
    collection_run_id = str(uuid.uuid4())
    embeddings_path = _write_fixture_dataset(
        tmp_path, base_root=base_root, collection_run_id=collection_run_id,
    )
    repo = FakeAnalysisRunRepository()
    orchestrator = StartAnalysisRunOrchestrator(
        analysis_run_repository=repo,
        analysis_engine=_make_engine(base_root, embeddings_path, raise_on_fit=True),
    )
    project_id = _project_id()
    command = _command(
        project_id=project_id, collection_run_id=collection_run_id, idempotency_key="will-fail",
    )

    with pytest.raises(RuntimeError, match="simulated BERTopic fit crash"):
        orchestrator.execute(command)

    stored = repo.get_by_idempotency_key(project_id, "will-fail")
    assert stored is not None
    assert stored.status is AnalysisRunStatus.FAILED


def test_duplicate_dispatch_of_a_failed_run_creates_a_new_analysis_run_not_a_resume(
    tmp_path: Path,
) -> None:
    # The T-011 equivalent test proves CollectionRun.resume() is called. AnalysisRun has no
    # resume() (section 10.1 line 577) -- this test proves the orchestrator does NOT try to
    # call one, and instead persists a brand-new AnalysisRun for the retry.
    base_root = tmp_path / "runs"
    collection_run_id = str(uuid.uuid4())
    embeddings_path = _write_fixture_dataset(
        tmp_path, base_root=base_root, collection_run_id=collection_run_id,
    )
    repo = FakeAnalysisRunRepository()
    project_id = _project_id()
    command = _command(
        project_id=project_id, collection_run_id=collection_run_id, idempotency_key="resume-key",
    )

    orchestrator_one = StartAnalysisRunOrchestrator(
        analysis_run_repository=repo,
        analysis_engine=_make_engine(base_root, embeddings_path, raise_on_fit=True),
    )
    with pytest.raises(RuntimeError, match="simulated BERTopic fit crash"):
        orchestrator_one.execute(command)

    failed_run = repo.get_by_idempotency_key(project_id, "resume-key")
    assert failed_run is not None
    assert failed_run.status is AnalysisRunStatus.FAILED
    assert not hasattr(failed_run, "resume")

    # A fresh orchestrator instance, same repository, a working engine this time.
    orchestrator_two = StartAnalysisRunOrchestrator(
        analysis_run_repository=repo,
        analysis_engine=_make_engine(base_root, embeddings_path, raise_on_fit=False),
    )
    result = orchestrator_two.execute(command)

    assert result.id != failed_run.id  # a NEW AnalysisRun, not the failed one resumed
    assert result.status == "completed"
    assert result.row_count == 4
    assert result.topic_count == 2
    assert repo.add_calls == 2  # the failed run, then the retry run
    # The failed run's own status is untouched by the retry (immutability of the old instance).
    assert failed_run.status is AnalysisRunStatus.FAILED


# ---------------------------------------------------------------------------
# Architectural conformance
# ---------------------------------------------------------------------------


def test_orchestrator_module_does_not_import_presentation_api_or_infrastructure() -> None:
    import finfluencer.application.orchestrators.start_analysis_run as module

    tree = ast.parse(inspect.getsource(module))
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    assert not any(m.startswith("finfluencer.presentation") for m in imported_modules)
    assert not any(m.startswith("finfluencer.api") for m in imported_modules)
    assert not any(m.startswith("finfluencer.infrastructure") for m in imported_modules)
    assert not any(m.startswith("finfluencer.topics") for m in imported_modules)
