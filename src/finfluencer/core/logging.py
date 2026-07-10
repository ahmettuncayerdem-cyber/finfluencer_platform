"""
finfluencer.core.logging
=========================

Structured logging via ``structlog``.

Design decisions
----------------
* JSON output by default (machine-parseable, ingested by provenance).
* Human-readable output only when ``verbose=True`` is passed at setup
  (developer convenience, never in reproducible runs).
* Log records carry structured fields, not formatted strings — this is
  what lets us later inspect e.g. ``quota_used`` as a numeric field
  instead of parsing a message string.
* Setup is idempotent: calling :func:`configure` twice does not stack
  handlers. Safe for interactive notebook use.
* Log records are dual-emitted to (a) rotating file under
  ``output.paths.logs`` and (b) stderr. Both use the same JSON format
  for consistency.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Any

import structlog


_CONFIGURED: bool = False


def configure(
    *,
    log_dir: Path | None = None,
    level: str = "INFO",
    verbose: bool = False,
    include_stderr: bool = True,
) -> None:
    """Configure structlog for the platform.

    Parameters
    ----------
    log_dir
        Directory to write rotating log files. If ``None``, only stderr
        is used.
    level
        Standard-logging level name.
    verbose
        If ``True``, use human-readable console output; if ``False``,
        emit JSON records (production default).
    include_stderr
        If ``False``, disable stderr output (rare — used when only file
        logging is desired).
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    # Common processors both for structlog-native and stdlib-wrapped calls.
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if verbose:
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer(
            colors=sys.stderr.isatty(),
        )
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Stdlib configuration for interop with libraries that log via stdlib.
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper()))
    # Remove previous handlers to keep setup idempotent.
    for h in list(root.handlers):
        root.removeHandler(h)

    if include_stderr:
        stderr_h = logging.StreamHandler(sys.stderr)
        stderr_h.setFormatter(formatter)
        root.addHandler(stderr_h)

    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_h = logging.handlers.RotatingFileHandler(
            log_dir / "finfluencer.log",
            maxBytes=25 * 1024 * 1024,  # 25 MiB per file
            backupCount=5,
            encoding="utf-8",
        )
        file_h.setFormatter(formatter)
        root.addHandler(file_h)

    _CONFIGURED = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound logger for ``name`` (typically ``__name__``).

    Idempotent: if :func:`configure` has not yet been called, a default
    JSON-to-stderr configuration is applied. Explicit :func:`configure`
    call is still recommended in pipeline entry points.
    """
    if not _CONFIGURED:
        configure()
    return structlog.get_logger(name)


def bind_context(**kwargs: Any) -> None:
    """Bind key/value pairs to all subsequent log records in this context.

    Uses :mod:`structlog.contextvars` so bindings survive across
    function boundaries within the same asyncio task or thread.

    Example
    -------
    ``bind_context(analyst_key="satiroglu")`` — every subsequent log
    call in this task adds ``analyst_key="satiroglu"`` to its record.
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """Clear all bindings previously set via :func:`bind_context`."""
    structlog.contextvars.clear_contextvars()


def _reset_for_testing() -> None:
    """Reset the ``configured`` flag. Test-only escape hatch."""
    global _CONFIGURED
    _CONFIGURED = False


__all__ = [
    "configure",
    "get_logger",
    "bind_context",
    "clear_context",
]
