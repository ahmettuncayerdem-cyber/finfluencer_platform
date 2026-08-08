"""Engine/session construction for the Persistence Layer (BACKLOG.md EPIC-07', ADR-0001-A).

Deliberately small: one function to build a SQLAlchemy `Engine` from a connection URL, one
function to build the paired `sessionmaker`. Every repository in `sqlalchemy_repositories.py`
takes a `sessionmaker` at construction time (dependency-injected, same pattern
`bootstrap.py` already uses for every other adapter) rather than importing a module-level global
engine -- this is what keeps two `create_app()` calls with different `db_url` values fully
isolated from each other (see `t029_e2e_verification.py` check 10a), and what makes the
per-repository unit tests in `tests/unit/test_persistence/` able to point at an independent
in-memory or temp-file database without any process-global state to reset between tests.

SQLite-specific connection argument, explained rather than left as a magic flag:
`check_same_thread=False` is required because FastAPI runs synchronous path-operation functions
in a worker thread pool (`starlette.concurrency.run_in_threadpool`) -- a single request's
handler may run on a different OS thread than the one that created the `Engine`. SQLite's
default DBAPI driver refuses cross-thread use of the same connection unless this flag is set.
This is safe here specifically because every repository method opens and closes its own
short-lived `Session` per call (see `sqlalchemy_repositories.py`'s module docstring) rather than
holding one connection open across requests -- SQLAlchemy's own connection pool, not this flag,
is what actually serializes concurrent access to the underlying SQLite file.

ADR-0001-A's forward-compatibility guarantee lives here too: nothing in this module is
SQLite-specific beyond the one documented `connect_args` branch below. Pointing `db_url` at
`postgresql+psycopg://...` instead works with this exact same code path.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import sessionmaker

from finfluencer.persistence.models import Base


def build_engine(db_url: str) -> Engine:
    """Construct a SQLAlchemy `Engine` for `db_url`, creating the parent directory first if
    `db_url` is a file-based SQLite URL and that directory does not yet exist (a fresh
    `sqlite:///path/to/data/finfluencer.db` URL should not require the caller to `mkdir -p`
    by hand -- the equivalent convenience `tempfile.mkdtemp()` already provides for
    `collection_base_root` elsewhere in `bootstrap.py`).
    """
    if db_url.startswith("sqlite:///") and db_url != "sqlite:///:memory:":
        db_path = Path(db_url.removeprefix("sqlite:///"))
        db_path.parent.mkdir(parents=True, exist_ok=True)

    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite:") else {}
    return create_engine(db_url, connect_args=connect_args)


def build_session_factory(engine: Engine) -> sessionmaker:
    """One `sessionmaker` bound to `engine`, handed to every repository constructed against
    this same database -- see this module's own docstring for why that sharing is safe and
    why it is dependency-injected rather than a module-level global.
    """
    return sessionmaker(bind=engine, expire_on_commit=False)


def create_all_tables(engine: Engine) -> None:
    """Create every table `persistence/models.py` declares, if not already present.

    Used by `bootstrap.py`'s ephemeral (temp-file) default path, where there is no deployed
    Alembic migration history to run against -- a fresh temp file has no schema at all until
    this runs once. For a real, durable deployment, `alembic upgrade head` (see
    `alembic/README.md`) is the intended path instead; this function is intentionally *not*
    itself a substitute for Alembic (it has no migration history, no down-revision, no way to
    evolve a schema that already has rows in it) -- see this module's own tests for the explicit
    check that both paths produce the same schema.
    """
    Base.metadata.create_all(bind=engine)


__all__ = ["build_engine", "build_session_factory", "create_all_tables"]
