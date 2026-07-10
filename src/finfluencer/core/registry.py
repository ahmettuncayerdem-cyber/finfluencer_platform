"""
finfluencer.core.registry
==========================

Plugin registry for providers (language, platform, market, sentiment
backend, LLM backend).

Two registration paths
----------------------
1. **In-tree registration** — subpackages call :func:`register` at
   import time (or via a metaclass hook) to advertise providers that
   ship with the platform (e.g. ``TurkishLanguageProvider``).

2. **Out-of-tree registration** — third-party plugins declare entry
   points under the group ``finfluencer.providers``; :func:`discover`
   loads and registers them lazily on first lookup.

Lookup ignores registration path — callers ask for a provider by
``(kind, key)`` and receive whichever implementation is registered
first-wins.
"""

from __future__ import annotations

import importlib
import importlib.metadata
from typing import Any, Callable, TypeVar

from finfluencer.core.exceptions import (
    ProviderConfigurationError,
    ProviderNotFoundError,
)


T = TypeVar("T")

#: The entry-point group name that third parties use to advertise plugins.
ENTRY_POINT_GROUP: str = "finfluencer.providers"


# =============================================================================
# In-memory registry
# =============================================================================


#: Map of ``(kind, key) → provider class``.
_REGISTRY: dict[tuple[str, str], type] = {}

#: Kinds discovered via entry points (populated by :func:`discover`).
_DISCOVERED_KINDS: set[str] = set()


def register(kind: str, key: str) -> Callable[[type[T]], type[T]]:
    """Decorator to register a provider under ``(kind, key)``.

    Example
    -------
    ``@register("language", "turkish")`` on a class body registers that
    class as the ``LanguageProvider`` for the ``turkish`` key.
    """
    def decorator(cls: type[T]) -> type[T]:
        _register_class(kind, key, cls)
        return cls

    return decorator


def _register_class(kind: str, key: str, cls: type) -> None:
    if not kind or not key:
        raise ValueError("register: kind and key must be non-empty")
    identifier = (kind, key)
    _REGISTRY[identifier] = cls


def unregister(kind: str, key: str) -> None:
    """Remove a registration. Primarily for testing."""
    _REGISTRY.pop((kind, key), None)


def clear_registry() -> None:
    """Empty the registry. Testing utility."""
    _REGISTRY.clear()
    _DISCOVERED_KINDS.clear()


# =============================================================================
# Entry-point discovery
# =============================================================================


def discover(kind: str) -> None:
    """Discover and register third-party providers of ``kind`` via entry
    points under the group :data:`ENTRY_POINT_GROUP`.

    Idempotent per kind. Import failures on individual plugins are
    collected but do not stop discovery of other plugins.
    """
    if kind in _DISCOVERED_KINDS:
        return
    _DISCOVERED_KINDS.add(kind)

    try:
        eps = importlib.metadata.entry_points(group=ENTRY_POINT_GROUP)
    except TypeError:
        # Older importlib.metadata; entry_points() returns dict-like
        eps = importlib.metadata.entry_points().get(ENTRY_POINT_GROUP, [])  # type: ignore

    errors: list[tuple[str, str]] = []
    for ep in eps:
        # Naming convention: entry-point name is "kind:key"
        if ":" not in ep.name:
            continue
        ep_kind, ep_key = ep.name.split(":", 1)
        if ep_kind != kind:
            continue
        try:
            cls = ep.load()
            _register_class(ep_kind, ep_key, cls)
        except Exception as exc:  # noqa: BLE001
            errors.append((ep.name, f"{type(exc).__name__}: {exc}"))

    if errors:
        # Log via structlog when logging is available; do not raise.
        try:
            from finfluencer.core.logging import get_logger

            get_logger(__name__).warning(
                "provider_discovery_partial_failure",
                kind=kind,
                errors=errors,
            )
        except Exception:  # noqa: BLE001
            pass


# =============================================================================
# Lookup
# =============================================================================


def get(kind: str, key: str) -> type:
    """Return the provider class registered under ``(kind, key)``.

    Attempts entry-point discovery once per kind if the initial lookup
    misses; raises :class:`ProviderNotFoundError` if still not found.
    """
    cls = _REGISTRY.get((kind, key))
    if cls is None:
        discover(kind)
        cls = _REGISTRY.get((kind, key))
    if cls is None:
        available = sorted(k for (kd, k) in _REGISTRY if kd == kind)
        raise ProviderNotFoundError(
            f"No provider registered for kind={kind!r} key={key!r}",
            kind=kind,
            key=key,
            available_keys=available,
        )
    return cls


def instantiate(kind: str, key: str, **kwargs: Any) -> Any:
    """Look up and instantiate a provider.

    Kwargs are forwarded to the provider's constructor. Configuration
    errors during construction are re-raised as
    :class:`ProviderConfigurationError`.
    """
    cls = get(kind, key)
    try:
        return cls(**kwargs)
    except Exception as exc:  # noqa: BLE001
        raise ProviderConfigurationError(
            f"Failed to instantiate provider {kind}:{key}: {exc}",
            kind=kind,
            key=key,
            reason=type(exc).__name__,
        ) from exc


def list_registered(kind: str | None = None) -> list[tuple[str, str]]:
    """Return the list of ``(kind, key)`` pairs currently registered.

    If ``kind`` is given, restrict to that kind.
    """
    if kind is None:
        return sorted(_REGISTRY.keys())
    return sorted((kd, k) for (kd, k) in _REGISTRY if kd == kind)


__all__ = [
    "ENTRY_POINT_GROUP",
    "register",
    "unregister",
    "clear_registry",
    "discover",
    "get",
    "instantiate",
    "list_registered",
]
