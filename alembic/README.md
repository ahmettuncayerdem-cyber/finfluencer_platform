# Alembic Migrations (EPIC-07', ADR-0001-A)

Standard single-database Alembic setup targeting `src/finfluencer/persistence/models.py`'s
`Base.metadata`.

## Usage

```bash
# Generate a new migration from the current models (autogenerate diffs against the target DB):
poetry run alembic revision --autogenerate -m "describe the change"

# Apply all migrations up to the latest:
poetry run alembic upgrade head

# Roll back one migration:
poetry run alembic downgrade -1
```

## Which database?

Set `FINFLUENCER_DB_URL` before running any `alembic` command to target a specific database.
Without it, `alembic/env.py` defaults to `sqlite:///<repo_root>/data/finfluencer.db` -- the same
default `bootstrap.py`'s durable persistence mode uses, so `alembic upgrade head` with no
environment override prepares exactly the database the running application will actually use.

```bash
FINFLUENCER_DB_URL="postgresql+psycopg://user:pass@host/dbname" poetry run alembic upgrade head
```

Per ADR-0001-A's forward-compatibility guarantee, this is the *only* thing that needs to change
to run these same migrations against PostgreSQL later.
