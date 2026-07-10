"""Tests for :mod:`finfluencer.core.registry`."""

from __future__ import annotations

import pytest
from finfluencer.core.exceptions import (
    ProviderConfigurationError,
    ProviderNotFoundError,
)
from finfluencer.core.registry import (
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
