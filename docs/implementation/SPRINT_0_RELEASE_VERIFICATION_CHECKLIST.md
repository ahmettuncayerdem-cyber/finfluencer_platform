# Sprint 0 Release Verification Checklist — T-014

**Purpose:** the human half of T-014 ("Deploy Walking Skeleton to one real minimal environment").
Role: Human + Claude. Verification: manual access to the deployed environment. Claude cannot
complete this task alone — the items below are what the operator checks personally, in an
environment Claude does not control. Nothing here should require judgment calls; every item is
an observable pass/fail, not an opinion.

**Scope note:** this checklist governs T-014 only. It assumes T-001 through T-013 are already
closed (Sprint 0 implementation is complete, per operator instruction) — it does not re-verify
their own internal acceptance criteria, only that the assembled whole behaves correctly end to
end, once, in a real environment.

---

## 0. Setup (once, before checking anything below)

From the repository root, in a terminal with **Python 3.11–3.13** available (`pyproject.toml`'s
declared range — this is a real requirement, not the sandbox's own 3.10 workaround used during
development):

```
pip install -e .
pip install fastapi uvicorn
```

(or, if you use Poetry and it resolves cleanly on your machine: `poetry install`, then prefix
every command below with `poetry run`.)

Start the app as a real server process:

```
uvicorn finfluencer.bootstrap:create_app --factory --host 127.0.0.1 --port 8000
```

Leave this running in one terminal; run the checks below from a second terminal / your browser.

---

## 1. Checklist

- [ ] **Application starts successfully.**
  The `uvicorn` command above prints `Application startup complete.` and `Uvicorn running on
  http://127.0.0.1:8000` with no traceback. Leave it running.

- [ ] **HTTP server responds.**
  `curl -i http://127.0.0.1:8000/` (or open the URL in a browser) returns `HTTP/1.1 200 OK`.

- [ ] **Home page loads.**
  Open `http://127.0.0.1:8000/` in a browser. You should see "Finfluencer Research Platform —
  Walking Skeleton (Sprint 0)" with a **Create Project** form, a **Start Collection Run** form,
  and an empty **Status list** table.

- [ ] **Create Project succeeds.**
  Fill in the Create Project form (any Tenant ID UUID — e.g. generate one by running
  `python -c "import uuid; print(uuid.uuid4())"` — any project name, any idempotency key) and
  submit. A new row appears in the Status list: kind `Project`, a real UUID, status `active`.

- [ ] **Start Collection Run succeeds.**
  Fill in the Start Collection Run form (any Dataset ID UUID — same trick as above — any
  idempotency key) and submit. A new row appears in the Status list: kind `CollectionRun`, a
  real UUID, status `completed`. This is a real run against the fixture dataset — expect roughly
  a one-second pause before the row appears, not an instant response.

- [ ] **Duplicate request behaves correctly.**
  Submit the *exact same* Start Collection Run form again — same Dataset ID, same idempotency
  key, unchanged — without editing either field. The new row's ID must be **identical** to the
  previous one, and the response must return promptly (it does not re-run the collection).
  Submitting with a *different* idempotency key (same Dataset ID) must produce a **new**,
  different ID.

- [ ] **Crash/resume behavior already proven by T-013.**
  No manual action needed — T-013's automated test (`tests/integration/
  test_t013_interruption_and_resume.py`) already proves this with a real, uncatchable `SIGKILL`
  of a genuine subprocess, not a simulated failure. Optionally re-run it yourself to see it fire
  again: `pytest tests/integration -v` (see item below — this is the same command).

- [ ] **Walking Skeleton regression passes.**
  In the second terminal:
  ```
  pytest tests/unit/test_domain tests/unit/test_presentation tests/unit/test_application \
         tests/unit/test_infrastructure/test_collection tests/unit/test_api tests/integration -q
  ```
  Expect **126 passed**, 0 failed.

- [ ] **IG-001 passes.**
  ```
  python scripts/check_layer_dependencies.py
  ```
  Expect: `IG-001: clean -- no forbidden cross-layer imports found.`

- [ ] **No unexpected warnings in logs.**
  Check the terminal running `uvicorn` and the terminal that ran the pytest commands above.
  Expected, known-benign output: structured JSON log lines from `structlog` (`collect_channels`,
  `channel_resolved`, etc. — these are normal collection-stage logging, not warnings), and (only
  in the pytest run, not in the running server) a single `DeprecationWarning` about `httpx`'s
  `TestClient(app=...)` shortcut — a cosmetic, already-known test-tooling warning, not a defect.
  Anything else — a Python traceback, an `ERROR`-level log line, a `CollectionError`, an
  unhandled exception — fails this item.

- [ ] **Working tree clean.**
  Stop the server (Ctrl+C), then:
  ```
  git status --short
  ```
  Expect only the pre-existing untracked "T-033 pile" (research-track files at the repo root,
  documented in BACKLOG.md's T-001 entry, unrelated to this engagement) — no modified or new
  files from anything you did above (the app writes only to a temp directory, never to the repo).

- [ ] **Repository state matches latest commit.**
  ```
  git log -1 --oneline
  git diff --stat
  ```
  `git diff --stat` must be empty. `git log -1` should show the commit that added this checklist
  ("docs: add Sprint 0 Release Verification Checklist (T-014)") or a later one, if further
  commits have landed since — never an earlier commit, and never a dirty/uncommitted state.

---

## 2. When every box above is checked

Report back (pass/fail per item, and any deviation observed). On a full pass, per the operator's
own standing instruction, the next steps are: update `BACKLOG.md`'s T-014 entry to **CLOSED**,
update the Backlog Snapshot section, and produce the Sprint 0 Completion Report — all performed
by Claude once this checklist's results are confirmed, not before.
