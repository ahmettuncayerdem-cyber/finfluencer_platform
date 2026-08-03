"""Tests for `bootstrap.create_app`'s Release Blocker #6 dispatch wiring.

Proves two things `bootstrap.py`'s own docstring commits to, without either running a full
BERTopic model over the tiny fixture dataset (heavy, not what these tests isolate -- the real
composite engines' own sequencing is already covered by
`tests/unit/test_infrastructure/test_analysis/test_real_topics_engine.py`/
`test_real_sentiment_engine.py`) or duplicating `test_routes_analysis.py`'s own coverage of the
always-permissive default path (already green, unmodified, 4/4 passing -- proof this delta broke
nothing there):

1. The wiring itself is structurally correct: the two well-known ids resolve to orchestrators
   backed by the real composite engines, and the original single orchestrator/demo engine is
   untouched.
2. Dispatch is genuinely permissive end-to-end over HTTP: swapping in a fake orchestrator at
   exactly one well-known id and POSTing with that id invokes only that fake, never the other one
   or the default; POSTing with an unrecognized id invokes only the default, never either fake.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

from finfluencer.application.orchestrators.start_analysis_run import (
    StartAnalysisRunCommand,
    StartAnalysisRunOrchestrator,
    StartAnalysisRunResult,
)
from finfluencer.bootstrap import (
    SENTIMENT_ANALYSIS_TYPE_ID,
    TOPIC_MODELING_ANALYSIS_TYPE_ID,
    create_app,
)
from finfluencer.infrastructure.analysis import (
    RealSentimentAnalysisEngine,
    RealTopicsAnalysisEngine,
)


def test_well_known_ids_resolve_to_real_engines() -> None:
    app = create_app()
    by_type = app.state.analysis_run_orchestrators_by_type

    assert set(by_type) == {TOPIC_MODELING_ANALYSIS_TYPE_ID, SENTIMENT_ANALYSIS_TYPE_ID}
    assert isinstance(
        by_type[TOPIC_MODELING_ANALYSIS_TYPE_ID]._analysis_engine, RealTopicsAnalysisEngine,
    )
    assert isinstance(
        by_type[SENTIMENT_ANALYSIS_TYPE_ID]._analysis_engine, RealSentimentAnalysisEngine,
    )


def test_default_orchestrator_is_unchanged_from_before_release_blocker_6() -> None:
    from finfluencer.bootstrap import _DemoTopicAssignmentEngine

    app = create_app()
    default = app.state.start_analysis_run_orchestrator

    assert isinstance(default, StartAnalysisRunOrchestrator)
    assert isinstance(default._analysis_engine, _DemoTopicAssignmentEngine)
    # The dict only ever holds the two real orchestrators -- the default is never in it.
    assert default not in app.state.analysis_run_orchestrators_by_type.values()


class _FakeOrchestrator:
    """Duck-typed `StartAnalysisRunOrchestrator` stand-in, swapped into `app.state` after
    `create_app()` -- same seam-substitution style this session's other adapter tests already use
    (e.g. `_FakePreprocessEngine`), not `unittest.mock`/monkeypatch.
    """

    def __init__(self) -> None:
        self.calls: list[Any] = []

    def execute(self, command: StartAnalysisRunCommand) -> StartAnalysisRunResult:
        self.calls.append(command.analysis_type_id)
        return StartAnalysisRunResult(
            id=uuid.uuid4(),  # type: ignore[arg-type]
            project_id=command.project_id,
            status="completed",
            row_count=0,
            topic_count=0,
        )


def _start_collection_run(client: TestClient) -> str:
    dataset_id = str(uuid.uuid4())
    response = client.post(
        f"/datasets/{dataset_id}/collection-runs",
        json={"dataset_id": dataset_id, "idempotency_key": str(uuid.uuid4())},
    )
    assert response.status_code == 200
    return response.json()["id"]  # type: ignore[no-any-return]


def _wire_fakes(app: Any) -> tuple[_FakeOrchestrator, _FakeOrchestrator]:
    fake_topics = _FakeOrchestrator()
    fake_sentiment = _FakeOrchestrator()
    app.state.analysis_run_orchestrators_by_type[TOPIC_MODELING_ANALYSIS_TYPE_ID] = fake_topics
    app.state.analysis_run_orchestrators_by_type[SENTIMENT_ANALYSIS_TYPE_ID] = fake_sentiment
    return fake_topics, fake_sentiment


def test_well_known_id_dispatches_to_its_own_orchestrator_only() -> None:
    app = create_app()
    fake_topics, fake_sentiment = _wire_fakes(app)
    client = TestClient(app)
    collection_run_id = _start_collection_run(client)

    response = client.post(
        f"/collection-runs/{collection_run_id}/analysis-runs",
        json={
            "project_id": str(uuid.uuid4()), "collection_run_id": collection_run_id,
            "analysis_type_id": str(TOPIC_MODELING_ANALYSIS_TYPE_ID),
            "analysis_type_version": "1.0.0", "idempotency_key": "wired-1",
        },
    )

    assert response.status_code == 200
    assert len(fake_topics.calls) == 1
    assert fake_sentiment.calls == []


def test_unrecognized_id_still_dispatches_to_the_default_demo_orchestrator() -> None:
    app = create_app()
    fake_topics, fake_sentiment = _wire_fakes(app)
    client = TestClient(app)
    collection_run_id = _start_collection_run(client)

    response = client.post(
        f"/collection-runs/{collection_run_id}/analysis-runs",
        json={
            "project_id": str(uuid.uuid4()), "collection_run_id": collection_run_id,
            "analysis_type_id": str(uuid.uuid4()), "analysis_type_version": "1.0.0",
            "idempotency_key": "wired-2",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["row_count"] == 8  # the real demo engine actually ran, matching T-028's own value
    assert fake_topics.calls == []
    assert fake_sentiment.calls == []
