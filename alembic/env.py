"""Alembic environment (BACKLOG.md EPIC-07', ADR-0001-A).

`target_metadata` points at `persistence/models.py`'s `Base.metadata` -- the one place this
file needs to import real application code -- so `alembic revision --autogenerate` can diff a
live database against the actual ORM models rather than requiring every migration to be
hand-written from scratch.

Database URL resolution deliberately does NOT read `sqlalchemy.url` from `alembic.ini` (see
that file's own comment) -- it reads `FINFLUENCER_DB_URL` from the environment, falling back to
the same default `bootstrap.py`'s durable mode uses. This is what lets the exact same
`alembic.ini`/`env.py` pair run migrations against a future PostgreSQL URL later (ADR-0001-A's
forward-compatibility guarantee) by only ever changing an environment variable, never this file.
"""

import os
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context
from finfluencer.persistence.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_DB_URL = f"sqlite:///{_REPO_ROOT / 'data' / 'finfluencer.db'}"


def _resolve_db_url() -> str:
    return os.environ.get("FINFLUENCER_DB_URL", _DEFAULT_DB_URL)


def run_migrations_offline() -> None:
    url = _resolve_db_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _resolve_db_url()
    connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
