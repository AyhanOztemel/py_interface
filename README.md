# interface-contract

Strict runtime interface contracts for Python, with definition-time failures and
signature-aware structural checks.

```bash
pip install interface-contract
```

```python
from interface_contract import Interface, default


class Repository(Interface):
    def find(self, item_id: int) -> str: ...
    def save(self, item: str) -> None: ...

    @property
    def name(self) -> str: ...

    @default
    def describe(self) -> str:
        return f"repository<{self.name}>"


class SqlRepository(Repository):
    def find(self, item_id: int) -> str:
        return f"row {item_id}"

    def save(self, item: str) -> None:
        pass

    @property
    def name(self) -> str:
        return "sql"
```

If `SqlRepository` misses a required member, changes its descriptor kind, or has
an incompatible signature, class creation raises `InterfaceError`. You do not
need to wait until an instance is created or a method is called.

## Why interface-contract?

Python already has `abc.ABC` and `typing.Protocol`; this package targets a
different boundary: strict runtime validation for plugin systems, application
architecture, dependency injection, and dynamically loaded code.

| Capability | `abc.ABC` | runtime `Protocol` | `interface-contract` |
|---|---:|---:|---:|
| Missing method detected at runtime | instantiation | `isinstance` | class definition |
| Runtime signature validation | no | no | yes |
| Property/static/class method kind validation | no | no | yes |
| Signature-aware structural `isinstance` | no | no | yes |
| Explicit default implementations | concrete method | concrete method | `@default` |
| Optional instance-field contracts | annotations only | presence only | presence + shallow type check |
| Runtime adapter registry | no | no | yes |

This is not a replacement for static typing. Use mypy or another type checker for
whole-program analysis, and use interface-contract where runtime boundaries must
fail loudly and predictably.

## Core behavior

### Definition-time validation

Concrete subclasses are checked as soon as their `class` statement executes.
Intermediate implementations can opt out until a concrete subclass is ready:

```python
class BaseRepository(Repository, abstract=True):
    def save(self, item: str) -> None:
        pass


class MemoryRepository(BaseRepository):
    def find(self, item_id: int) -> str:
        return "row"

    @property
    def name(self) -> str:
        return "memory"
```

Abstract implementations cannot be instantiated.

### Default methods

Interface methods normally declare requirements and therefore must have an empty
body (`...`, `pass`, or a docstring-only body). Mark intentional implementations
with `@default`:

```python
from interface_contract import Interface, default


class Named(Interface):
    @property
    def name(self) -> str: ...

    @default
    def display_name(self) -> str:
        return self.name.title()
```

### Structural interfaces

Set `structural=True` when inheritance is not under your control:

```python
class Closable(Interface, structural=True):
    def close(self) -> None: ...


class FileLike:
    def close(self) -> None:
        pass


assert isinstance(FileLike(), Closable)
assert issubclass(FileLike, Closable)
```

Unlike runtime-checkable protocols, the structural check also validates callable
signatures and descriptor kinds.

### Instance-field contracts

Field checking is opt-in, preserving compatibility with versions that ignored
class annotations:

```python
class UserRecord(Interface, check_attributes=True):
    name: str
    age: int


class User(UserRecord):
    def __init__(self, name: str, age: int) -> None:
        self.name = name
        self.age = age
```

Fields are checked immediately after `__init__`. Standard annotations receive a
best-effort shallow runtime check; parameter contents such as every item inside
`list[str]` are intentionally not traversed. `ClassVar` does not declare an
instance field. Dataclass implementations are supported.

For objects that cannot inherit from an interface, use `verify_instance` or
`satisfies`:

```python
from interface_contract import satisfies, verify_instance

verify_instance(User("Ada", 37), UserRecord)  # returns the object or raises
assert satisfies(User("Ada", 37), UserRecord)
```

### Adapters

The registry converts an existing type to a target interface and validates the
result:

```python
from interface_contract import AdapterRegistry

registry = AdapterRegistry()


@registry.register(dict, UserRecord)
def dict_to_user(data: dict[str, object]) -> User:
    return User(name=str(data["name"]), age=int(data["age"]))


user = registry.adapt({"name": "Ada", "age": 37}, UserRecord)
```

`adapt`, `can_adapt`, `register_adapter`, and `unregister_adapter` expose a
process-wide default registry when a dedicated registry is unnecessary.

## Optional annotation checks

Call signatures are always checked for parameter shape. To also compare available
parameter and return annotations, enable `check_annotations=True`:

```python
class Parser(Interface, check_annotations=True):
    def parse(self, value: str) -> int: ...
```

Runtime annotation comparison is deliberately conservative. It does not try to
replace a static type checker.

## Mypy integration

The package is typed and ships an optional mypy plugin. It lets mypy reject the
instantiation of incomplete implementations before execution. No extra runtime
dependency is installed.

```toml
[tool.mypy]
plugins = ["interface_contract.mypy_plugin"]
```

```python
class Job(Interface):
    def execute(self, payload: str) -> int: ...


class Incomplete(Job):
    pass


Incomplete()  # mypy: Cannot instantiate abstract class "Incomplete"
```

The mypy plugin API is itself experimental; runtime validation remains the source
of truth.

## Supported members

- regular and async methods
- properties, including independent getter/setter/deleter requirements
- static methods and class methods
- generic interfaces
- multiple and derived interfaces
- custom metaclass composition
- source-less environments such as REPL, `exec`, notebooks, frozen apps, and
  bytecode-only distributions

Useful inspection functions include `members_of`, `attributes_of`,
`missing_members`, `missing_attributes`, `signature_problem`, `verify`, and
`structurally_implements`.

## Backward compatibility

The former import path remains fully supported:

```python
from strict_interface import Interface
```

`strict_interface.Interface` and `interface_contract.Interface` are the same
object. Existing source code does not need an import migration. The PyPI
distribution name is `interface-contract`; the preferred new import is
`interface_contract`.

Version 0.4.0 is additive except for the distribution rename. Runtime field
checking only activates when `check_attributes=True` is explicitly selected.

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
python -m mypy strict_interface interface_contract typing_tests/valid.py
python -m build
python -m twine check dist/*
```

See [README.tr.md](https://github.com/AyhanOztemel/py_interface/blob/main/README.tr.md)
for Turkish documentation and
[CHANGELOG.md](https://github.com/AyhanOztemel/py_interface/blob/main/CHANGELOG.md)
for release notes.

## License

MIT
