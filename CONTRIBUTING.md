# Contributing

This is currently a single-maintainer research project. Issues and pull
requests are welcome, but please open an issue to discuss significant
changes before submitting a pull request.

## Development setup

Install dependencies with `poetry install`, then run the test suite with
`poetry run pytest`.

## Code style

- Ruff handles linting and formatting (`poetry run ruff check .`, `poetry run ruff format .`).
- MyPy runs in strict mode (`poetry run mypy src`).
- New code should include tests; the project enforces a minimum coverage
  threshold in CI (see `pyproject.toml`'s `[tool.pytest.ini_options]`).

### CI quality gate scope (Sprint 2.7A policy)

CI's `lint` job does not run `ruff check .` / `mypy src` against the whole
repository. It is deliberately scoped to `src/finfluencer/reporting/`,
`src/finfluencer/cli.py`, and their test suites -- the Sprint 1/2
deliverables -- via the `run:` commands in
`.github/workflows/ci.yml`. The rest of the repository (in particular
pre-2.7A legacy modules) carries pre-existing lint/type findings that are
tracked separately and are out of scope for the Sprint 2.7A release
hardening effort; gating on them here would block releases on unrelated,
already-known debt rather than on the new code being shipped. As later
sprints bring more of the repository up to the same standard, this scope
should grow to match -- it is not meant to stay this narrow permanently.

Within that scope, two different kinds of findings are handled
differently, and this distinction is intentional:

- **Genuine correctness findings are fixed in code**, not suppressed --
  e.g. `B904` (raise-without-`from` inside an `except` clause), `B905`
  (`zip()` without an explicit `strict=`), stale `# noqa` comments, unused
  imports, and a bare `except Exception: pass` that swallowed callback
  failures without logging them.
- **Stylistic findings are suppressed via scoped
  `[tool.ruff.lint.per-file-ignores]` entries in `pyproject.toml`**,
  each with an inline comment explaining why. These are permanent policy
  decisions, not technical debt to "clean up later":
  - `E501` (long lines) -- the manuscript table/figure modules contain
    wide literal data rows (headers, formatted cell values); wrapping
    them would hurt readability for no benefit, and Sprint 2.7A's policy
    explicitly excludes reformatting working code.
  - `RUF001` (ambiguous unicode) -- Turkish-language literals (e.g. the
    dotless `ı`) and mathematical symbols (`ρ`, `−`) that are the
    scientifically correct characters for this content, not typos.
  - `UP035` / `UP037` (import-modernization suggestions) -- pre-existing,
    working patterns; modernizing them is a style pass, not a Sprint 2.7A
    release blocker.
  - `PLR2004` (magic value) / `RUF005` (list-concat-vs-unpack) -- minor
    style preferences in manuscript-generation code, not correctness
    issues.
  - `I001` (import sort order) -- fixing this reformats the import block;
    out of scope under the "no reformatting" policy.
  - `B008` (`typer.Option()` as an argument default, `main.py` only) --
    this is Typer's own required API pattern, not a bug.
  - `N806` (`test_manuscript_tables.py` only) -- an existing module-level
    constant naming convention used inside a test function.
  - `PLW1510` / `S603` (`test_cli.py` only) -- these are subprocess-based
    CLI smoke tests that invoke `sys.executable` with test-controlled
    arguments and assert on `.returncode` themselves; `check=True` would
    break that pattern, and the "untrusted input" warning does not apply
    to a trusted interpreter invoked with hardcoded test arguments.

The corresponding `mypy` overrides (`ignore_missing_imports` for
`openpyxl.*`, `scipy.*`, `pymannkendall.*`, `scikit_posthocs.*`) exist
because these libraries ship no type stubs and none are available to
install, unlike `pandas` and `PyYAML` (covered by the `pandas-stubs` and
`types-pyyaml` dev dependencies already declared in `pyproject.toml`).

## Commit discipline

This project favors small, independently buildable commits with a single
logical purpose per commit, each verified in isolation before landing.
