from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import pytest

import interface_contract as contract
import strict_interface as legacy
from interface_contract import (
    AdaptationError,
    AdapterRegistry,
    Interface,
    InterfaceError,
    attributes_of,
    missing_attributes,
    satisfies,
    verify_instance,
)


def test_new_and_legacy_imports_are_identical() -> None:
    assert contract.Interface is legacy.Interface
    assert contract.default is legacy.default
    assert contract.__version__ == legacy.__version__ == "0.4.0"


def test_annotations_remain_ignored_by_default() -> None:
    class ILegacy(Interface):
        value: int

        def run(self) -> None: ...

    class Legacy(ILegacy):
        def run(self) -> None: ...

    assert isinstance(Legacy(), ILegacy)


def test_opt_in_instance_attributes_are_checked_after_init() -> None:
    class IUser(Interface, check_attributes=True):
        name: str
        age: int

        def label(self) -> str: ...

    class User(IUser):
        def __init__(self, name: str, age: int) -> None:
            self.name = name
            self.age = age

        def label(self) -> str:
            return self.name

    user = User("Ada", 37)
    assert user.label() == "Ada"
    assert set(attributes_of(IUser)) == {"name", "age"}
    assert missing_attributes(user, IUser) == []


def test_missing_instance_attribute_is_reported() -> None:
    class IUser(Interface, check_attributes=True):
        name: str

    class User(IUser):
        pass

    with pytest.raises(InterfaceError, match=r"name.*instance attribute eksik"):
        User()


def test_wrong_instance_attribute_type_is_reported() -> None:
    class IUser(Interface, check_attributes=True):
        age: int

    class User(IUser):
        def __init__(self) -> None:
            self.age = "unknown"

    with pytest.raises(InterfaceError, match=r"age.*int.*str"):
        User()


def test_opt_in_attributes_work_with_dataclasses() -> None:
    class IPoint(Interface, check_attributes=True):
        x: int
        y: int

    @dataclass
    class Point(IPoint):
        x: int
        y: int

    assert Point(2, 3).x == 2


def test_classvar_is_not_an_instance_contract() -> None:
    class IConfigured(Interface, check_attributes=True):
        category: ClassVar[str]
        value: int

    assert set(attributes_of(IConfigured)) == {"value"}


def test_structural_instance_check_includes_instance_attributes_and_signatures() -> None:
    class INamedCloser(Interface, structural=True, check_attributes=True):
        name: str

        def close(self) -> None: ...

    class Resource:
        def __init__(self) -> None:
            self.name = "resource"

        def close(self) -> None:
            pass

    class BadResource:
        def __init__(self) -> None:
            self.name = "resource"

        def close(self, force: bool) -> None:
            pass

    assert isinstance(Resource(), INamedCloser)
    assert satisfies(Resource(), INamedCloser)
    assert not isinstance(BadResource(), INamedCloser)
    assert not issubclass(Resource, INamedCloser)  # name exists only after __init__


def test_verify_instance_can_check_a_non_inheriting_object() -> None:
    class IRecord(Interface, check_attributes=True):
        identifier: int

    class Record:
        identifier = 42

    record = Record()
    assert verify_instance(record, IRecord) is record


def test_adapter_registry_supports_decorators_and_source_subclasses() -> None:
    class IText(Interface, check_attributes=True):
        text: str

        def render(self) -> str: ...

    class Payload:
        def __init__(self, value: str) -> None:
            self.value = value

    class ChildPayload(Payload):
        pass

    class TextView:
        def __init__(self, payload: Payload) -> None:
            self.text = payload.value

        def render(self) -> str:
            return self.text

    registry = AdapterRegistry()

    @registry.register(Payload, IText)
    def payload_to_text(payload: Payload) -> TextView:
        return TextView(payload)

    assert registry.can_adapt(ChildPayload("hello"), IText)
    assert registry.adapt(ChildPayload("hello"), IText).render() == "hello"
    assert registry.unregister(Payload, IText)
    assert not registry.can_adapt(ChildPayload("hello"), IText)


def test_adapter_returns_existing_implementation_without_conversion() -> None:
    class IRunnable(Interface):
        def run(self) -> str: ...

    class Runner(IRunnable):
        def run(self) -> str:
            return "ok"

    runner = Runner()
    assert AdapterRegistry().adapt(runner, IRunnable) is runner


def test_adapter_missing_default_and_invalid_result() -> None:
    class IRunnable(Interface):
        def run(self) -> str: ...

    class Source:
        pass

    registry = AdapterRegistry()
    sentinel = object()
    assert registry.adapt(Source(), IRunnable, default=sentinel) is sentinel
    with pytest.raises(AdaptationError, match="kayitli degil"):
        registry.adapt(Source(), IRunnable)

    registry.register(Source, IRunnable, lambda value: object())
    with pytest.raises(AdaptationError, match="gecersiz"):
        registry.adapt(Source(), IRunnable)
