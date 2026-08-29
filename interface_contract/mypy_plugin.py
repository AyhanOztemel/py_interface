"""Optional mypy integration for Interface subclasses.

Enable with ``plugins = interface_contract.mypy_plugin`` in mypy configuration.
The plugin marks non-default interface methods as abstract so mypy can reject
instantiation of incomplete implementations before the program runs.
"""

from __future__ import annotations

from collections.abc import Callable

from mypy.nodes import IS_ABSTRACT, Decorator, FuncDef, OverloadedFuncDef, Statement
from mypy.plugin import ClassDefContext, Plugin

_INTERFACE_BASES = {
    "interface_contract.Interface",
    "interface_contract._core.Interface",
    "strict_interface.Interface",
    "strict_interface._core.Interface",
}
_DEFAULT_DECORATORS = {
    "interface_contract.default",
    "interface_contract._core.default",
    "strict_interface.default",
    "strict_interface._core.default",
}


def _decorator_fullname(value: object) -> str | None:
    fullname = getattr(value, "fullname", None)
    return fullname if isinstance(fullname, str) else None


def _is_default(item: Decorator) -> bool:
    return any(_decorator_fullname(value) in _DEFAULT_DECORATORS for value in item.decorators)


def _mark_abstract(item: Statement) -> None:
    if isinstance(item, FuncDef):
        if not item.name.startswith("__"):
            item.abstract_status = IS_ABSTRACT
        return
    if isinstance(item, Decorator):
        if not item.name.startswith("__") and not _is_default(item):
            item.func.abstract_status = IS_ABSTRACT
        return
    if isinstance(item, OverloadedFuncDef):
        for overload in item.items:
            _mark_abstract(overload)


def _interface_class(ctx: ClassDefContext) -> None:
    for item in ctx.cls.defs.body:
        _mark_abstract(item)


class InterfaceContractPlugin(Plugin):
    """Teach mypy that direct Interface subclasses declare abstract methods."""

    def get_base_class_hook(
        self, fullname: str
    ) -> Callable[[ClassDefContext], None] | None:
        return _interface_class if fullname in _INTERFACE_BASES else None


def plugin(version: str) -> type[Plugin]:
    """Mypy plugin entry point."""
    return InterfaceContractPlugin
