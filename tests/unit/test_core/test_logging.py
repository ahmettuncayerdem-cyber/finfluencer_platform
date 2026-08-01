"""Tests for :mod:`finfluencer.core.logging`.

Regression coverage for ADR-P2-003 (Phase 2 architecture audit): a real
CLI invocation's explicit ``configure(log_dir=..., verbose=...)`` call
used to be silently discarded whenever any earlier-imported module had
already triggered :func:`get_logger`'s lazy default configuration --
which, given this codebase's convention of module-level
``_log = get_logger(__name__)`` calls, happened on essentially every
run. See ``collect/main.py``/``reporting/main.py`` for the real entry
points this protects; this suite tests the root-cause layer directly
rather than driving a full CLI invocation, since the bug lives entirely
inside :func:`finfluencer.core.logging.configure`/:func:`get_logger`.
"""

from __future__ import annotations

import logging as stdlib_logging
from pathlib import Path

import pytest

from finfluencer.core import logging as flogging


@pytest.fixture(autouse=True)
def _clean_logging_state():
    """Isolate each test from global logging state.

    ``core.logging`` deliberately holds process-global state (the root
    logger's handlers, the ``_CONFIGURED`` flag) -- exactly the design
    this bug lived in. Tests must not leak that state to each other or
    to the rest of the suite.
    """
    root = stdlib_logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    flogging._reset_for_testing()
    yield
    for h in list(root.handlers):
        root.removeHandler(h)
    for h in saved_handlers:
        root.addHandler(h)
    root.setLevel(saved_level)
    flogging._reset_for_testing()


def _file_handlers(root: stdlib_logging.Logger) -> list[stdlib_logging.Handler]:
    return [
        h for h in root.handlers
        if isinstance(h, stdlib_logging.handlers.RotatingFileHandler)
    ]


class TestConfigureIsNotSilentlyDiscarded:
    """ADR-P2-003: configure() must take effect even if get_logger() ran first."""

    def test_get_logger_before_configure_does_not_block_configure(self, tmp_path):
        """Reproduces the exact real-world bug sequence.

        1. Some transitively-imported module calls ``get_logger(__name__)``
           at module scope (as ``providers/platform/youtube.py``,
           ``collect/channels.py``, etc. all do) -- this is what happened
           silently, at import time, before any entry point code ran.
        2. The entry point then makes its own explicit, intentional
           ``configure(log_dir=...)`` call.

        Before the fix, step 2 was a no-op because step 1 had already
        set ``_CONFIGURED = True``. After the fix, step 2 must win.
        """
        # Step 1: simulate a module-level `_log = get_logger(__name__)`
        # executing during import, before the entry point does anything.
        flogging.get_logger("finfluencer.providers.platform.youtube")

        root = stdlib_logging.getLogger()
        assert _file_handlers(root) == [], (
            "sanity check: the lazy default configure() must not itself "
            "attach file logging (log_dir=None by default)"
        )

        # Step 2: the entry point's own explicit call, e.g.
        # collect/main.py:543 or reporting/main.py:133.
        log_dir = tmp_path / "logs"
        flogging.configure(log_dir=log_dir, verbose=False)

        handlers = _file_handlers(root)
        assert len(handlers) == 1, (
            "configure(log_dir=...) must attach a RotatingFileHandler even "
            "when get_logger() already ran once before it"
        )
        assert Path(handlers[0].baseFilename).parent == log_dir.resolve()

    def test_second_explicit_configure_call_replaces_first(self, tmp_path):
        """A second explicit configure() (e.g. a test harness, or a
        notebook re-running a cell) must re-point logging, not no-op."""
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"

        flogging.configure(log_dir=dir_a)
        root = stdlib_logging.getLogger()
        assert Path(_file_handlers(root)[0].baseFilename).parent == dir_a.resolve()

        flogging.configure(log_dir=dir_b)
        handlers = _file_handlers(root)
        assert len(handlers) == 1, "must not accumulate duplicate handlers"
        assert Path(handlers[0].baseFilename).parent == dir_b.resolve()


class TestHandlerReplacementIsClean:
    def test_configure_without_log_dir_after_one_with_log_dir_removes_file_handler(
        self, tmp_path,
    ):
        flogging.configure(log_dir=tmp_path / "logs")
        root = stdlib_logging.getLogger()
        assert len(_file_handlers(root)) == 1

        flogging.configure(log_dir=None)
        assert _file_handlers(root) == [], (
            "re-configuring without log_dir must drop the previous "
            "file handler, not leave it attached alongside nothing new"
        )

    def test_stderr_handler_not_duplicated_across_repeated_configure_calls(self):
        flogging.configure()
        flogging.configure()
        flogging.configure()
        root = stdlib_logging.getLogger()
        stream_handlers = [
            h for h in root.handlers
            if isinstance(h, stdlib_logging.StreamHandler)
            and not isinstance(h, stdlib_logging.handlers.RotatingFileHandler)
        ]
        assert len(stream_handlers) == 1


class TestGetLoggerLazyDefaultStillWorks:
    """The pre-existing 'safe for interactive/notebook use' contract
    (get_logger() self-configuring with sane defaults when nothing has
    configured yet) must survive this fix unchanged."""

    def test_get_logger_with_no_prior_configure_does_not_raise(self):
        log = flogging.get_logger("some.module")
        log.info("smoke_test")  # must not raise

    def test_get_logger_after_configure_does_not_reconfigure(self, tmp_path):
        """get_logger() must remain a no-op once *anything* has configured
        -- only configure() itself should be able to reconfigure."""
        flogging.configure(log_dir=tmp_path / "logs")
        root = stdlib_logging.getLogger()
        before = list(root.handlers)

        flogging.get_logger("another.module")

        assert root.handlers == before, (
            "get_logger() must not re-run configure() once configured "
            "at least once -- only an explicit configure() call may change "
            "handlers"
        )
