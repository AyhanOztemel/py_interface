"""Small, explicit adapter registry for interface contracts."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from ._core import InterfaceError, is_interface, satisfies

_T = TypeVar("_T")
_MISSING = object()


class AdaptationError(InterfaceError):
    """Raised when no adapter exists or an adapter returns an invalid object."""


class AdapterRegistry:
    """Map ``(source type, target interface)`` pairs to adapter factories."""

    def __init__(self) -> None:
        self._factories: dict[tuple[type, type], Callable[[Any], Any]] = {}

    def register(
        self,
        source: type,
        target: type,
        factory: Callable[[Any], Any] | None = None,
    ) -> Callable[[Any], Any]:
        """Register a factory directly or use the method as a decorator."""
        if not isinstance(source, type):
            raise TypeError("source bir sinif olmali")
        if not is_interface(target):
            raise TypeError("target bir Interface olmali")

        def store(candidate: Callable[[Any], Any]) -> Callable[[Any], Any]:
            if not callable(candidate):
                raise TypeError("adapter factory cagrilabilir olmali")
            self._factories[(source, target)] = candidate
            return candidate

        return store if factory is None else store(factory)

    def unregister(self, source: type, target: type) -> bool:
        """Remove one registration and report whether it existed."""
        return self._factories.pop((source, target), None) is not None

    def _factory_for(self, source: type, target: type) -> Callable[[Any], Any] | None:
        for candidate in source.__mro__:
            factory = self._factories.get((candidate, target))
            if factory is not None:
                return factory
        return None

    def can_adapt(self, obj: Any, target: type) -> bool:
        """Return whether ``obj`` already satisfies or has an adapter to ``target``."""
        if not is_interface(target):
            raise TypeError("target bir Interface olmali")
        return satisfies(obj, target) or self._factory_for(type(obj), target) is not None

    def adapt(self, obj: Any, target: type, *, default: Any = _MISSING) -> Any:
        """Adapt ``obj`` to ``target`` and validate the produced object."""
        if not is_interface(target):
            raise TypeError("target bir Interface olmali")
        if satisfies(obj, target):
            return obj

        factory = self._factory_for(type(obj), target)
        if factory is None:
            if default is not _MISSING:
                return default
            raise AdaptationError(
                f"{type(obj).__name__} -> {target.__name__} adapter'i kayitli degil."
            )

        result = factory(obj)
        if not satisfies(result, target):
            raise AdaptationError(
                f"{type(obj).__name__} -> {target.__name__} adapter'i "
                f"gecersiz {type(result).__name__} dondurdu."
            )
        return result


default_registry = AdapterRegistry()


def register_adapter(
    source: type,
    target: type,
    factory: Callable[[Any], Any] | None = None,
) -> Callable[[Any], Any]:
    """Register an adapter in the process-wide default registry."""
    return default_registry.register(source, target, factory)


def unregister_adapter(source: type, target: type) -> bool:
    """Remove an adapter from the process-wide default registry."""
    return default_registry.unregister(source, target)


def adapt(obj: _T, target: type, *, default: Any = _MISSING) -> Any:
    """Adapt through the process-wide default registry."""
    return default_registry.adapt(obj, target, default=default)


def can_adapt(obj: Any, target: type) -> bool:
    """Check the process-wide default registry."""
    return default_registry.can_adapt(obj, target)
