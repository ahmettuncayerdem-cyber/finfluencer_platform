"""UI integration test for the Sprint 0 dev page (BACKLOG.md T-012).

BACKLOG.md's own Verification line for T-012 is "manual click-through + IG-001 CI check" --
"manual" is a human verification step (Role: "Claude or Copilot... human-approved"), not
something this sandbox can perform itself (no display, no real browser; standing up Playwright/
Selenium here would be a disproportionate new dependency for one Sprint 0 smoke check, and
neither is declared in pyproject.toml). This test is the automated equivalent available in this
environment: it proves the page is served correctly, contains the expected form elements and
fetch() calls, and that those calls target routes that actually exist and work (proven
separately in test_routes_identity.py/test_routes_collection.py) -- genuine manual click-through
in a real browser remains an outstanding human verification step, not claimed as satisfied here.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from finfluencer.bootstrap import create_app


def test_dev_ui_page_is_served_and_contains_expected_forms() -> None:
    client = TestClient(create_app())
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    html = response.text

    assert 'id="create-project-form"' in html
    assert 'id="start-run-form"' in html
    assert 'id="status-table"' in html
    # The two fetch() calls target the exact routes this task registered.
    assert 'fetch("/projects"' in html or "postJson(\"/projects\"" in html
    assert "/datasets/${datasetId}/collection-runs" in html
