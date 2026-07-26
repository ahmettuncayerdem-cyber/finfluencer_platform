"""Tests for :mod:`finfluencer.core.registry`."""

from __future__ import annotations

import importlib.metadata

import pytest
from finfluencer.core.exceptions import (
    ProviderConfigurationError,
    ProviderNotFoundError,
)
from finfluencer.core.registry import (
    ENTRY_POINT_GROUP,
    discover,
    get,
    instantiate,
    list_registered,
    register,
    unregister,
)


class TestRegistration:
    def test_register_and_get(self):
        @register("test_kind", "test_key")
        class P: ...

        assert get("test_kind", "test_key") is P
        unregister("test_kind", "test_key")

    def test_missing_key_raises(self):
        with pytest.raises(ProviderNotFoundError):
            get("test_kind", "nonexistent")

    def test_missing_key_lists_available(self):
        @register("test_kind", "available_key")
        class P: ...
        try:
            get("test_kind", "other")
        except ProviderNotFoundError as exc:
            assert "available_key" in exc.context.get("available_keys", [])
        unregister("test_kind", "available_key")


class TestInstantiate:
    def test_instantiate_with_kwargs(self):
        @register("test_kind", "with_kwargs")
        class P:
            def __init__(self, name: str) -> None:
                self.name = name

        inst = instantiate("test_kind", "with_kwargs", name="x")
        assert inst.name == "x"
        unregister("test_kind", "with_kwargs")

    def test_constructor_failure_wrapped(self):
        @register("test_kind", "will_fail")
        class P:
            def __init__(self) -> None:
                raise RuntimeError("boom")

        with pytest.raises(ProviderConfigurationError):
            instantiate("test_kind", "will_fail")
        unregister("test_kind", "will_fail")


def test_list_registered_by_kind():
    @register("k1", "a")
    class A: ...
    @register("k1", "b")
    class B: ...
    @register("k2", "c")
    class C: ...

    ks = list_registered("k1")
    assert ("k1", "a") in ks and ("k1", "b") in ks
    assert ("k2", "c") not in ks
    for k, v in [("k1", "a"), ("k1", "b"), ("k2", "c")]:
        unregister(k, v)


def test_list_registered_all_kinds_when_kind_is_none():
    @register("kx", "a")
    class A: ...
    @register("ky", "b")
    class B: ...

    result = list_registered()
    assert ("kx", "a") in result
    assert ("ky", "b") in result
    unregister("kx", "a")
    unregister("ky", "b")


class TestRegisterValidation:
    def test_empty_kind_raises(self):
        with pytest.raises(ValueError, match="kind and key"):
            @register("", "somekey")
            class P: ...

    def test_empty_key_raises(self):
        with pytest.raises(ValueError, match="kind and key"):
            @register("somekind", "")
            class P: ...


# =============================================================================
# discover() — entry-point-based plugin loading.
#
# Fake EntryPoint objects and a monkeypatched importlib.metadata.entry_points
# are used throughout: this is the same "inject a controllable fake for an
# optional/external dependency surface" technique used for get_git_state() in
# test_reproducibility.py, applied here to the plugin-discovery entry-point
# API rather than GitPython.
# =============================================================================


class _FakeEntryPoint:
    def __init__(self, name: str, *, loader=None, obj=None) -> None:
        self.name = name
        self._loader = loader
        self._obj = obj

    def load(self):
        if self._loader is not None:
            return self._loader()
        return self._obj


class TestDiscover:
    def test_idempotent_per_kind_entry_points_queried_once(self, monkeypatch):
        calls = []

        def fake_entry_points(*, group):
            calls.append(group)
            return []

        monkeypatch.setattr(importlib.metadata, "entry_points", fake_entry_points)

        discover("idempotent_kind")
        discover("idempotent_kind")  # second call must hit the early return

        assert calls == [ENTRY_POINT_GROUP]

    def test_typeerror_triggers_older_importlib_metadata_fallback(self, monkeypatch):
        def fake_entry_points(*args, **kwargs):
            if kwargs:
                raise TypeError("entry_points() got an unexpected keyword argument 'group'")
            return {ENTRY_POINT_GROUP: []}

        monkeypatch.setattr(importlib.metadata, "entry_points", fake_entry_points)

        discover("legacy_kind")  # must not raise

    def test_entry_point_without_colon_is_skipped(self, monkeypatch):
        ep = _FakeEntryPoint(name="no_colon_name", obj=object)
        monkeypatch.setattr(importlib.metadata, "entry_points", lambda *, group: [ep])

        discover("no_colon_kind")

        assert list_registered("no_colon_kind") == []

    def test_entry_point_kind_mismatch_is_skipped(self, monkeypatch):
        ep = _FakeEntryPoint(name="other_kind:some_key", obj=object)
        monkeypatch.setattr(importlib.metadata, "entry_points", lambda *, group: [ep])

        discover("mismatch_kind")

        assert list_registered("mismatch_kind") == []

    def test_entry_point_successfully_loaded_and_registered(self, monkeypatch):
        class Provider: ...

        ep = _FakeEntryPoint(name="ep_kind:ep_key", obj=Provider)
        monkeypatch.setattr(importlib.metadata, "entry_points", lambda *, group: [ep])

        discover("ep_kind")

        assert get("ep_kind", "ep_key") is Provider

    def test_entry_point_load_failure_is_collected_not_raised(self, monkeypatch):
        def _broken_loader():
            raise RuntimeError("plugin import exploded")

        ep = _FakeEntryPoint(name="broken_kind:broken_key", loader=_broken_loader)
        monkeypatch.setattr(importlib.metadata, "entry_points", lambda *, group: [ep])

        discover("broken_kind")  # must not raise despite the failing plugin

        with pytest.raises(ProviderNotFoundError):
            get("broken_kind", "broken_key")

    def test_logging_failure_during_partial_failure_report_is_swallowed(self, monkeypatch):
        # Both the plugin load AND the subsequent warning-log call fail;
        # discover() must still not raise (the log call is best-effort).
        def _broken_loader():
            raise RuntimeError("boom")

        ep = _FakeEntryPoint(name="noisy_kind:noisy_key", loader=_broken_loader)
        monkeypatch.setattr(importlib.metadata, "entry_points", lambda *, group: [ep])

        def _broken_get_logger(*args, **kwargs):
            raise RuntimeError("logging unavailable")

        monkeypatch.setattr("finfluencer.core.logging.get_logger", _broken_get_logger)

        discover("noisy_kind")  # must not raise
