"""Cekirdek uygulama. Genel API icin `strict_interface/__init__.py`ye bakin."""

from __future__ import annotations

import ast
import inspect
import textwrap
import types
from collections.abc import Callable
from typing import (
    Annotated,
    Any,
    ClassVar,
    Literal,
    TypeVar,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

_FLAG = "__is_interface__"
_MEMBERS = "__interface_members__"
_VERIFIED = "__interface_verified__"
_STRUCTURAL = "__interface_structural__"
_DEFAULT = "__interface_default__"
_ANNOTATED = "__interface_check_annotations__"
_ABSTRACT = "__interface_abstract__"
_ATTRIBUTES = "__interface_attributes__"
_CHECK_ATTRIBUTES = "__interface_check_attributes__"


class InterfaceError(TypeError):
    """Arayuz sozlesmesi ihlal edildiginde atilir."""


# --------------------------------------------------------------------------- #
# Govde bosluk kontrolu
#
# Birincil yontem AST: surumler arasi kararli ve okunabilir.
# Kaynak koda ulasilamadiginda (REPL, exec, notebook, frozen app, sadece .pyc)
# bytecode'a dusuluyor.
#
# Kaynak bulunamazsa kabul edilen bos govdeler calisan yorumlayicida derlenir.
# Aday govde, bunlardan uretilen tam kod imzalarindan biriyle eslesmelidir.
# Opcode adlari veya farkli govdelerden birlestirilmis bir izin listesi
# kullanilmaz. Boylece gercek bir govde parca parca stub komutlarindan olussa
# bile kabul edilmez; PyPy gibi yorumlayicilar da kendi imzalarini kalibre eder.
# --------------------------------------------------------------------------- #

# Kabul ettigimiz butun bos govde bicimleri. Kod imzalari bunlardan uretilir.
_STUB_FORMS = (
    "def _s(self): pass",
    "def _s(self): ...",
    "def _s(self): 'dokuman'",
    "def _s(self): raise NotImplementedError",
    "def _s(self): raise NotImplementedError('mesaj')",
    "async def _s(self): pass",
    "async def _s(self): ...",
    "async def _s(self): 'dokuman'",
    "async def _s(self): raise NotImplementedError",
    "async def _s(self): raise NotImplementedError('mesaj')",
)

# Senkron, coroutine ve generator govdeleri birbirinden ayiran davranis bitleri.
_CODE_FLAGS = inspect.CO_COROUTINE | inspect.CO_GENERATOR | inspect.CO_ASYNC_GENERATOR
_CodeShape = tuple[bytes, tuple[str, ...], tuple[str, ...], int]


def _code_shape(code: Any) -> _CodeShape | None:
    raw = getattr(code, "co_code", None)
    constants = getattr(code, "co_consts", None)
    names = getattr(code, "co_names", None)
    flags = getattr(code, "co_flags", None)
    if (
        not isinstance(raw, bytes)
        or not isinstance(constants, tuple)
        or not isinstance(names, tuple)
        or not isinstance(flags, int)
    ):
        return None
    const_shape = tuple(
        "none" if value is None else "ellipsis" if value is Ellipsis else "literal"
        for value in constants
    )
    return raw, const_shape, tuple(map(str, names)), flags & _CODE_FLAGS


def _calibrate_stub_shapes() -> frozenset[_CodeShape]:
    """Bos govde kod imzalarini calisan yorumlayicidan ogrenir."""
    shapes: set[_CodeShape] = set()
    for source in _STUB_FORMS:
        namespace: dict[str, Any] = {}
        # S102: derlenen kaynak _STUB_FORMS'tan geliyor, disaridan girdi almiyor.
        exec(compile(source, "<strict_interface>", "exec"), namespace)  # noqa: S102
        shape = _code_shape(namespace["_s"].__code__)
        if shape is not None:
            shapes.add(shape)
    return frozenset(shapes)


_STUB_SHAPES = _calibrate_stub_shapes()


def _ast_is_stub(func: Callable[..., Any]) -> bool | None:
    try:
        source = textwrap.dedent(inspect.getsource(func))
    except (OSError, TypeError):
        return None
    try:
        module = ast.parse(source)
    except SyntaxError:
        return None
    if not module.body:
        return None
    node = module.body[0]
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return None

    body = list(node.body)
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:]  # docstring
    if not body:
        return True

    for stmt in body:
        if isinstance(stmt, ast.Pass):
            continue
        if (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant)
                and stmt.value.value is Ellipsis):
            continue
        if isinstance(stmt, ast.Raise) and stmt.exc is not None:
            exc = stmt.exc
            target = exc.func if isinstance(exc, ast.Call) else exc
            if isinstance(target, ast.Name) and target.id == "NotImplementedError":
                continue
        return False
    return True


def _bytecode_is_stub(func: Callable[..., Any]) -> bool:
    code = getattr(func, "__code__", None)
    if code is None:
        return False
    shape = _code_shape(code)
    return shape is not None and shape in _STUB_SHAPES


def is_stub(func: Callable[..., Any]) -> bool:
    """Govde `pass`, `...`, sadece docstring veya `raise NotImplementedError` mi?"""
    verdict = _ast_is_stub(func)
    return _bytecode_is_stub(func) if verdict is None else verdict


# --------------------------------------------------------------------------- #
# Uyeler
# --------------------------------------------------------------------------- #
class Member:
    """Arayuzun bir uyesi: metot, property, staticmethod veya classmethod."""

    __slots__ = ("is_async", "is_default", "kind", "name", "owner", "parts")

    def __init__(self, name: str, kind: str, parts: dict[str, Callable[..., Any]],
                 is_async: bool, owner: str, is_default: bool = False) -> None:
        self.name = name
        self.kind = kind
        self.parts = parts          # property icin fget/fset/fdel, digerleri icin ""
        self.is_async = is_async
        self.owner = owner
        self.is_default = is_default

    @property
    def primary(self) -> Callable[..., Any] | None:
        return self.parts.get("") or self.parts.get("fget")

    def __repr__(self) -> str:
        flag = " (default)" if self.is_default else ""
        return f"<{self.kind} {self.owner}.{self.name}{flag}>"


class AttributeSpec:
    """An opt-in instance-attribute requirement declared by an interface."""

    __slots__ = ("annotation", "name", "owner")

    def __init__(self, name: str, annotation: Any, owner: str) -> None:
        self.name = name
        self.annotation = annotation
        self.owner = owner

    def __repr__(self) -> str:
        return f"<attribute {self.owner}.{self.name}: {self.annotation!r}>"


def _has_default(raw: Any) -> bool:
    target = raw.__func__ if isinstance(raw, (staticmethod, classmethod)) else raw
    if isinstance(raw, property):
        target = raw.fget
    return bool(getattr(target, _DEFAULT, False))


def classify(name: str, value: Any, owner: str) -> Member | None:
    """Sinif sozlugundeki bir girdiyi Member'a cevirir; sozlesme disi ise None."""
    is_default = _has_default(value)
    if isinstance(value, staticmethod):
        fn = value.__func__
        return Member(name, "staticmethod", {"": fn},
                      inspect.iscoroutinefunction(fn), owner, is_default)
    if isinstance(value, classmethod):
        fn = value.__func__
        return Member(name, "classmethod", {"": fn},
                      inspect.iscoroutinefunction(fn), owner, is_default)
    if isinstance(value, property):
        parts = {k: f for k, f in
                 (("fget", value.fget), ("fset", value.fset), ("fdel", value.fdel))
                 if f is not None}
        return Member(name, "property", parts, False, owner, is_default)
    if inspect.isfunction(value):
        return Member(name, "method", {"": value},
                      inspect.iscoroutinefunction(value), owner, is_default)
    return None  # sabitler ve sinif degiskenleri sozlesmeye dahil degil


# --------------------------------------------------------------------------- #
# Imza uyumu
# --------------------------------------------------------------------------- #
_P = inspect.Parameter


def _is_catch_all(params: list[_P]) -> bool:
    kinds = {p.kind for p in params}
    return _P.VAR_POSITIONAL in kinds and _P.VAR_KEYWORD in kinds


def signature_problem(declared: Callable[..., Any], impl: Callable[..., Any],
                      check_annotations: bool = False) -> str | None:
    """Imzalar uyumsuzsa aciklama, uyumluysa None dondurur."""
    try:
        dsig = inspect.signature(declared)
        isig = inspect.signature(impl)
    except (TypeError, ValueError):
        return None  # C seviyesinde cagrilabilir; imza okunamiyor

    d = list(dsig.parameters.values())
    i = list(isig.parameters.values())

    if _is_catch_all(i):
        return None  # (*args, **kwargs) esnek imzaya izin ver

    if len(i) < len(d):
        return (f"beklenen ({', '.join(p.name for p in d)}), "
                f"verilen ({', '.join(p.name for p in i)}) — eksik parametre")

    # strict=False bilincli: implementasyon fazladan opsiyonel parametre
    # tanimlayabilir, fazlaliklar asagida ayrica denetleniyor.
    for want, got in zip(d, i, strict=False):
        if want.name != got.name:
            return f"parametre adi '{want.name}' olmali, '{got.name}' verilmis"
        if want.kind is not got.kind:
            return f"parametre '{want.name}' turu {want.kind.description} olmali"
        if (check_annotations and want.annotation is not _P.empty
                and got.annotation is not _P.empty
                and want.annotation != got.annotation):
            return (f"parametre '{want.name}' anotasyonu {want.annotation!r} "
                    f"olmali, {got.annotation!r} verilmis")

    for extra in i[len(d):]:
        if extra.default is _P.empty and extra.kind not in (
                _P.VAR_POSITIONAL, _P.VAR_KEYWORD):
            return f"fazladan zorunlu parametre '{extra.name}' — varsayilan deger verin"

    if (check_annotations and dsig.return_annotation is not inspect.Signature.empty
            and isig.return_annotation is not inspect.Signature.empty
            and dsig.return_annotation != isig.return_annotation):
        return (f"donus anotasyonu {dsig.return_annotation!r} olmali, "
                f"{isig.return_annotation!r} verilmis")
    return None


def member_problem(declared: Member, impl: Member,
                   check_annotations: bool = False) -> str | None:
    if impl.kind != declared.kind:
        return f"{declared.kind} olmali, {impl.kind} olarak tanimlanmis"
    if impl.is_async != declared.is_async:
        return ("async def olarak tanimlanmali" if declared.is_async
                else "async olmayan def olarak tanimlanmali")
    for part, decl_fn in declared.parts.items():
        impl_fn = impl.parts.get(part)
        if impl_fn is None:
            label = {"fget": "okuyucu", "fset": "setter", "fdel": "deleter"}.get(part, part)
            return f"property {label}'si eksik"
        problem = signature_problem(decl_fn, impl_fn, check_annotations)
        if problem:
            prefix = f"{part} " if part else ""
            return f"{prefix}imzasi uyusmuyor: {problem}"
    return None


# --------------------------------------------------------------------------- #
# Metaclass
# --------------------------------------------------------------------------- #
def _is_allowed_base(base: type) -> bool:
    """Arayuzun turetilebilecegi taban mi? (arayuz, object, typing yardimcilari)"""
    if base is object:
        return True
    if getattr(base, "__module__", "") in ("typing", "typing_extensions"):
        return True
    return is_interface(base)


def _looks_like_interface(namespace: dict[str, Any]) -> bool:
    """Govdesi tamamen bos olan bir sinif — muhtemelen arayuz olmasi isteniyordu."""
    found = False
    for key, value in namespace.items():
        if key.startswith("__") and key.endswith("__"):
            continue
        member = classify(key, value, "?")
        if member is None:
            continue
        found = True
        if not all(is_stub(fn) for fn in member.parts.values()):
            return False
    return found


def _with_interface_hint(exc: InterfaceError, cls: type,
                         namespace: dict[str, Any]) -> InterfaceError:
    problems = [line for line in str(exc).splitlines() if line.startswith("  - ")]
    if not problems or not all("implement edilmemis" in p for p in problems):
        return exc          # imza/tur hatasi var; bu bir arayuz karisikligi degil
    if not _looks_like_interface(namespace):
        return exc
    return InterfaceError(
        f"{exc}\n\n"
        f"Ipucu: {cls.__name__} govdesi tamamen bos. Bunun bir arayuz olmasini "
        f"istiyorsaniz `Interface`i taban olarak listeleyin veya `interface=True` "
        f"verin:\n"
        f"    class {cls.__name__}(..., Interface): ...\n"
        f"    class {cls.__name__}(..., interface=True): ...\n"
        f"Sozlesmeyi kasten kismen dolduran bir ara sinif ise `abstract=True` verin.")


class InterfaceMeta(type):
    """Arayuz semantigini tasiyan metaclass.

    - arayuzler ornekleneemez, hata mesaji anlamlidir
    - bir arayuzden turetilen her sinif **tanim aninda** dogrulanir; kismen
      dolduran ara siniflar icin `abstract=True` verin
    - sinifa sonradan atama yapilirsa dogrulama onbellegi gecersizlenir
    - structural=True verilen arayuzlerde isinstance/issubclass mirassiz calisir
    """

    def __new__(mcls, name: str, bases: tuple[type, ...], namespace: dict[str, Any],
                *, interface: bool | None = None, structural: bool = False,
                name_prefix: str | None = None, strict_body: bool = True,
                check_annotations: bool = False, abstract: bool = False,
                check_attributes: bool | None = None,
                **kwargs: Any) -> InterfaceMeta:
        cls = super().__new__(mcls, name, bases, dict(namespace), **kwargs)

        root = globals().get("Interface")
        if interface is None:
            interface = bool(namespace.get(_FLAG)) or (root is not None and root in bases)

        type.__setattr__(cls, _FLAG, bool(interface))
        type.__setattr__(cls, _VERIFIED, False)

        # --- implementasyon yolu ------------------------------------------- #
        if not interface:
            if abstract:
                # sozlesmeyi kasten kismen dolduran ara sinif: dogrulama
                # somut alt sinifa ertelenir
                type.__setattr__(cls, _ABSTRACT, True)
                return cls
            if any(is_interface(base) for base in cls.__mro__[1:]):
                try:
                    verify(cls)
                except InterfaceError as exc:
                    raise _with_interface_hint(exc, cls, namespace) from None
            return cls

        # --- arayuz yolu ---------------------------------------------------- #
        if check_attributes is None:
            check_attributes = any(
                bool(base.__dict__.get(_CHECK_ATTRIBUTES, False))
                for base in cls.__mro__[1:] if is_interface(base)
            )
        type.__setattr__(cls, _STRUCTURAL, structural)
        type.__setattr__(cls, _ANNOTATED, check_annotations)
        type.__setattr__(cls, _CHECK_ATTRIBUTES, bool(check_attributes))

        problems: list[str] = []
        if name_prefix and not name.startswith(name_prefix):
            problems.append(f"arayuz adi '{name_prefix}' ile baslamali")

        members: dict[str, Member] = {}
        attributes: dict[str, AttributeSpec] = {}
        for base in reversed(cls.__mro__[1:]):
            if is_interface(base):
                members.update(base.__dict__.get(_MEMBERS, {}))
                attributes.update(base.__dict__.get(_ATTRIBUTES, {}))
            elif not _is_allowed_base(base):
                problems.append(f"arayuz yalnizca arayuzlerden turetilebilir; "
                                f"'{base.__name__}' bir arayuz degil")

        for key, value in namespace.items():
            if key.startswith("__") and key.endswith("__"):
                if key in ("__init__", "__new__"):
                    problems.append(f"arayuz '{key}' tanimlayamaz")
                continue
            member = classify(key, value, name)
            if member is None:
                continue
            if strict_body and not member.is_default:
                for part, fn in member.parts.items():
                    if not is_stub(fn):
                        where = f"{key}.{part}" if part and part != "fget" else key
                        problems.append(
                            f"'{where}' govdesi bos olmali (`...`, `pass`, docstring "
                            f"veya `raise NotImplementedError`); govdeli metot icin "
                            f"@default kullanin")
            members[key] = member

        if check_attributes:
            raw_annotations = namespace.get("__annotations__", {})
            try:
                resolved_annotations = get_type_hints(cls, include_extras=True)
            except (NameError, TypeError):
                resolved_annotations = {}
            for key, raw_annotation in raw_annotations.items():
                annotation = resolved_annotations.get(key, raw_annotation)
                if key.startswith("_") or get_origin(annotation) is ClassVar:
                    continue
                attributes[key] = AttributeSpec(key, annotation, name)

        if problems:
            raise InterfaceError(
                f"{name} arayuzu gecersiz:\n  - " + "\n  - ".join(problems))

        type.__setattr__(cls, _MEMBERS, members)
        type.__setattr__(cls, _ATTRIBUTES, attributes)
        return cls

    # --- ornekleme -------------------------------------------------------- #
    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        if cls.__dict__.get(_FLAG, False):
            raise InterfaceError(
                f"{cls.__name__} bir arayuzdur, ornegi olusturulamaz.")
        if cls.__dict__.get(_ABSTRACT, False):
            raise InterfaceError(
                f"{cls.__name__} soyut bir sinif (abstract=True), "
                f"ornegi olusturulamaz.")
        if not cls.__dict__.get(_VERIFIED, False):
            verify(cls)
        instance = super().__call__(*args, **kwargs)
        verify_instance(instance)
        return instance

    # --- onbellek gecersizleme -------------------------------------------- #
    def __setattr__(cls, key: str, value: Any) -> None:
        type.__setattr__(cls, key, value)
        if key not in (
            _VERIFIED, _MEMBERS, _FLAG, _STRUCTURAL, _ANNOTATED, _ABSTRACT,
            _ATTRIBUTES, _CHECK_ATTRIBUTES,
        ):
            _invalidate(cls)

    def __delattr__(cls, key: str) -> None:
        type.__delattr__(cls, key)
        _invalidate(cls)

    # --- yapisal tipleme --------------------------------------------------- #
    def __instancecheck__(cls, obj: Any) -> bool:
        if super().__instancecheck__(obj):
            return True
        if not (cls.__dict__.get(_FLAG) and cls.__dict__.get(_STRUCTURAL)):
            return False
        return satisfies(obj, cls)

    def __subclasscheck__(cls, sub: type) -> bool:
        # super() ile zincirleniyor ki InterfaceMeta baska bir metaclass ile
        # birlestirildiginde (ornegin ABCMeta) onun register() semantigi yasasin.
        if super().__subclasscheck__(sub):
            return True
        if not (cls.__dict__.get(_FLAG) and cls.__dict__.get(_STRUCTURAL)):
            return False
        return structurally_implements(sub, cls)


def _invalidate(cls: type) -> None:
    type.__setattr__(cls, _VERIFIED, False)
    for sub in cls.__subclasses__():
        _invalidate(sub)


# --------------------------------------------------------------------------- #
# Genel yardimcilar
# --------------------------------------------------------------------------- #
def is_interface(obj: Any) -> bool:
    """Sinifin *kendisi* arayuz mu? Implementasyonlar icin False."""
    return isinstance(obj, type) and obj.__dict__.get(_FLAG, False)


class Interface(metaclass=InterfaceMeta, interface=True):
    """Tum arayuzlerin kok sinifi.

    `class IFoo(Interface): ...` seklinde turetin. Dogrudan `Interface`
    listelemeyen alt siniflar implementasyon sayilir; turetilmis bir arayuz
    yaziyorsaniz `Interface`i tekrar listeleyin veya `interface=True` verin:

        class IAudited(IRepository, Interface): ...
        class IAudited(IRepository, interface=True): ...
    """

    __slots__ = ()

    def __init_subclass__(
        cls,
        *,
        interface: bool | None = None,
        structural: bool = False,
        name_prefix: str | None = None,
        strict_body: bool = True,
        check_annotations: bool = False,
        abstract: bool = False,
        check_attributes: bool | None = None,
        **kwargs: Any,
    ) -> None:
        """Document class keywords for type checkers; InterfaceMeta consumes them."""
        super().__init_subclass__(**kwargs)


def is_abstract(obj: Any) -> bool:
    """`abstract=True` ile tanimlanmis, sozlesmeyi kismen dolduran ara sinif mi?"""
    return isinstance(obj, type) and obj.__dict__.get(_ABSTRACT, False)


def members_of(cls: type) -> dict[str, Member]:
    """Sinifin uymasi gereken tum arayuz uyeleri (default'lar dahil)."""
    collected: dict[str, Member] = {}
    for base in reversed(getattr(cls, "__mro__", (cls,))):
        if is_interface(base):
            collected.update(base.__dict__.get(_MEMBERS, {}))
    return collected


def attributes_of(cls: type) -> dict[str, AttributeSpec]:
    """Return opt-in instance-attribute requirements inherited by ``cls``."""
    collected: dict[str, AttributeSpec] = {}
    for base in reversed(getattr(cls, "__mro__", (cls,))):
        if is_interface(base):
            collected.update(base.__dict__.get(_ATTRIBUTES, {}))
    return collected


def _required(cls: type) -> dict[str, Member]:
    return {n: m for n, m in members_of(cls).items() if not m.is_default}


def _find_implementation(cls: type, name: str) -> tuple[Any, type] | None:
    for base in cls.__mro__:
        if is_interface(base):
            continue
        if name in vars(base):
            return vars(base)[name], base
    return None


def missing_members(cls: type) -> list[str]:
    """Implement edilmemis zorunlu uyelerin adlari."""
    return [n for n in _required(cls) if _find_implementation(cls, n) is None]


def _concrete_attribute_owner(cls: type, name: str) -> type | None:
    for base in cls.__mro__:
        if is_interface(base):
            continue
        if name in vars(base):
            return base
    return None


def _annotation_matches(value: Any, annotation: Any) -> bool:
    """Best-effort, shallow runtime check for a standard type annotation."""
    if annotation is Any or annotation is inspect.Signature.empty:
        return True
    if annotation is None:
        return value is None
    if isinstance(annotation, str):
        return True  # Forward references need the defining module namespace.
    if isinstance(annotation, TypeVar):
        if annotation.__constraints__:
            return any(_annotation_matches(value, item) for item in annotation.__constraints__)
        return _annotation_matches(value, annotation.__bound__) if annotation.__bound__ else True

    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is Annotated:
        return _annotation_matches(value, args[0]) if args else True
    if origin in (Union, types.UnionType):
        return any(_annotation_matches(value, item) for item in args)
    if origin is Literal:
        return value in args
    if origin is ClassVar:
        return True
    if origin is not None:
        try:
            return isinstance(value, origin)
        except TypeError:
            return True
    try:
        return isinstance(value, annotation)
    except TypeError:
        return True


def _instance_attribute_value(obj: Any, name: str) -> tuple[bool, Any]:
    try:
        namespace = vars(obj)
    except TypeError:
        namespace = {}
    if name in namespace:
        return True, namespace[name]

    owner = _concrete_attribute_owner(type(obj), name)
    if owner is None:
        return False, None
    try:
        return True, getattr(obj, name)
    except AttributeError:
        return False, None


def _attribute_problems(obj: Any, iface_or_impl: type) -> list[str]:
    problems: list[str] = []
    for name, spec in attributes_of(iface_or_impl).items():
        exists, value = _instance_attribute_value(obj, name)
        if not exists:
            problems.append(f"'{name}' instance attribute eksik ({spec.owner} arayuzu)")
        elif not _annotation_matches(value, spec.annotation):
            problems.append(
                f"'{name}' degeri {spec.annotation!r} anotasyonuyla uyusmuyor; "
                f"{type(value).__name__} verildi"
            )
    return problems


def missing_attributes(obj: Any, iface_or_impl: type | None = None) -> list[str]:
    """Return missing opt-in instance attributes without raising."""
    contract = type(obj) if iface_or_impl is None else iface_or_impl
    return [
        name for name in attributes_of(contract)
        if not _instance_attribute_value(obj, name)[0]
    ]


def verify_instance(obj: Any, iface: type | None = None) -> Any:
    """Verify runtime attributes, and optionally structural methods, on ``obj``."""
    contract = type(obj) if iface is None else iface
    if iface is not None and not is_interface(iface):
        raise TypeError(f"{iface!r} bir arayuz degil")
    if iface is not None and not structurally_implements(type(obj), iface, check_attributes=False):
        raise InterfaceError(
            f"{type(obj).__name__} {iface.__name__} arayuzunun metotlarini karsilamiyor."
        )
    problems = _attribute_problems(obj, contract)
    if problems:
        raise InterfaceError(
            f"{type(obj).__name__} instance sozlesmesini karsilamiyor:\n  - "
            + "\n  - ".join(problems)
        )
    return obj


def satisfies(obj: Any, iface: type) -> bool:
    """Return whether an object structurally satisfies methods and attributes."""
    try:
        verify_instance(obj, iface)
    except (InterfaceError, TypeError, ValueError):
        return False
    return True


def verify(cls: type) -> type:
    """Sinifi arayuz sozlesmesine karsi dogrular; uyumsuzsa InterfaceError atar."""
    contract = members_of(cls)
    if not contract and not attributes_of(cls):
        raise InterfaceError(
            f"{cls.__name__} hicbir arayuzden turetilmemis.")

    check_annotations = any(
        b.__dict__.get(_ANNOTATED, False) for b in cls.__mro__ if is_interface(b))

    problems: list[str] = []
    for name, declared in contract.items():
        found = _find_implementation(cls, name)
        if found is None:
            if not declared.is_default:
                problems.append(
                    f"'{name}' implement edilmemis ({declared.owner} arayuzu)")
            continue
        value, owner = found
        impl = classify(name, value, owner.__name__)
        if impl is None:
            problems.append(f"'{name}' cagrilabilir bir uye degil")
            continue
        problem = member_problem(declared, impl, check_annotations)
        if problem:
            problems.append(f"'{name}' {problem}")

    if problems:
        raise InterfaceError(
            f"{cls.__name__} arayuz sozlesmesini karsilamiyor:\n  - "
            + "\n  - ".join(problems))

    type.__setattr__(cls, _VERIFIED, True)
    return cls


def structurally_implements(
    candidate: type,
    iface: type,
    *,
    check_attributes: bool = True,
) -> bool:
    """Miras olmaksizin, uye uye uyum kontrolu (Protocol benzeri)."""
    if not is_interface(iface):
        raise TypeError(f"{iface!r} bir arayuz degil")
    for name, declared in members_of(iface).items():
        raw = None
        for base in getattr(candidate, "__mro__", (candidate,)):
            if name in vars(base):
                raw = vars(base)[name]
                break
        if raw is None:
            return False
        impl = classify(name, raw, getattr(candidate, "__name__", "?"))
        if impl is None or member_problem(declared, impl) is not None:
            return False
    if check_attributes:
        for name, spec in attributes_of(iface).items():
            owner = _concrete_attribute_owner(candidate, name)
            if owner is None:
                return False
            raw = vars(owner)[name]
            if not isinstance(raw, property) and not _annotation_matches(raw, spec.annotation):
                return False
    return True


def implements(cls: type) -> type:
    """Geriye donuk uyumluluk.

    Dogrulama artik tanim aninda otomatik yapiliyor; bu dekoratör yalnizca
    niyeti belgelemek isteyenler icin duruyor ve sinifi degistirmeden dondurur.
    """
    if not cls.__dict__.get(_VERIFIED, False):
        verify(cls)
    return cls


def default(func: Any) -> Any:
    """Arayuzde govdeli 'default method' tanimlamaya izin verir (Java 8 benzeri)."""
    target = func
    if isinstance(func, (staticmethod, classmethod)):
        target = func.__func__
    elif isinstance(func, property):
        target = func.fget
    setattr(target, _DEFAULT, True)
    return func


def interface(cls: type | None = None, **options: Any) -> Any:
    """Dekoratör stili arayuz tanimi.

    `class IFoo(Interface)` yazimi tercih edilmelidir. Bu dekoratör sinifi
    InterfaceMeta ile yeniden olusturur; govdede sifir argumanli `super()`
    kullanan bir `@default` metot varsa o metot bozulur (`__class__` hucresi
    eski sinifi gosterir). Arayuzlerin govdesi normalde bos oldugu icin bu
    pratikte yalnizca default metotlari ilgilendirir.
    """
    def decorate(target: type) -> type:
        namespace = {k: v for k, v in vars(target).items()
                     if k not in ("__dict__", "__weakref__")}
        namespace[_FLAG] = True
        bases = tuple(b for b in target.__bases__ if b is not object)
        if not any(is_interface(b) for b in bases):
            bases = (*bases, Interface)
        return InterfaceMeta(target.__name__, bases, namespace,
                             interface=True, **options)

    return decorate(cls) if cls is not None else decorate


# Geriye donuk uyumluluk
interface_implement = implements
