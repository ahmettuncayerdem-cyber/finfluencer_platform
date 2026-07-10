"""Tests for :mod:`finfluencer.core.reproducibility`."""

from __future__ import annotations

import pytest
from finfluencer.core.reproducibility import (
    capture_environment,
    derive_seed,
    get_git_state,
)


class TestDeriveSeed:
    def test_deterministic(self):
        assert derive_seed(42, "sentiment") == derive_seed(42, "sentiment")

    def test_stage_variance(self):
        assert derive_seed(42, "sentiment") != derive_seed(42, "topics")

    def test_root_variance(self):
        assert derive_seed(42, "sentiment") != derive_seed(43, "sentiment")

    def test_in_uint31_range(self):
        s = derive_seed(42, "sentiment")
        assert 0 <= s <= 2**31 - 1

    def test_negative_root_rejected(self):
        with pytest.raises(ValueError):
            derive_seed(-1, "sentiment")


class TestCaptureEnvironment:
    def test_has_python_and_packages(self):
        env = capture_environment()
        assert "python_version" in env
        assert "packages" in env
        # Core packages must be listed (they are installed as dependencies)
        assert "pydantic" in env["packages"]


def test_git_state_always_returns_dict():
    # In or out of a git repo, the function must not raise.
    st = get_git_state()
    assert "available" in st
