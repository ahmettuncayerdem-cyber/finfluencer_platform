# Contributing

This is currently a single-maintainer research project. Issues and pull
requests are welcome, but please open an issue to discuss significant
changes before submitting a pull request.

## Development setup
## Code style

- Ruff handles linting and formatting (`poetry run ruff check .`, `poetry run ruff format .`).
- MyPy runs in strict mode (`poetry run mypy src`).
- New code should include tests; the project enforces a minimum coverage
  threshold in CI (see `pyproject.toml`'s `[tool.pytest.ini_options]`).

## Commit discipline

This project favors small, independently buildable commits with a single
logical purpose per commit, each verified in isolation before landing.
