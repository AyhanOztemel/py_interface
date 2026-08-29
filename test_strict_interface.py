import abc
import inspect

import pytest

from strict_interface import (
    Interface,
    InterfaceError,
    InterfaceMeta,
    default,
    implements,
    interface,
    is_abstract,
    is_interface,
    is_stub,
    members_of,
    missing_members,
    structurally_implements,
    verify,
)
from strict_interface._core import _STUB_FORMS, _bytecode_is_stub


# --------------------------------------------------------------------------- #
# Ortak fikstur arayuzleri
# --------------------------------------------------------------------------- #
class IRepository(Interface):
    def find(self, id: int) -> str: ...
    def save(self, item: str) -> None: ...
    @property
    def name(self) -> str: ...
    @staticmethod
    def helper(x): ...
    @classmethod
    def build(cls, dsn): ...
    async def fetch(self, url: str): ...


class IAudited(IRepository, interface=True):
    def log(self, msg: str) -> None: ...


# --------------------------------------------------------------------------- #
# Temel davranis
# --------------------------------------------------------------------------- #
class TestBasics:
    def test_interface_cannot_be_instantiated(self):
        with pytest.raises(InterfaceError, match="arayuzdur"):
            IRepository()

    def test_is_interface(self):
        assert is_interface(IRepository) and is_interface(IAudited)

    def test_implementation_is_not_an_interface(self):
        class Repo(IRepository):
            def find(self, id): return "r"
            def save(self, item): ...
            @property
            def name(self): return "n"
            @staticmethod
            def helper(x): return x
            @classmethod
            def build(cls, dsn): return cls()
            async def fetch(self, url): return url
        assert not is_interface(Repo)
        assert Repo().find(1) == "r"

    def test_own_init_is_preserved(self):
        class Repo(IRepository):
            def __init__(self, dsn, *, echo=False):
                self.dsn, self.echo = dsn, echo
            def find(self, id): return self.dsn
            def save(self, item): ...
            @property
            def name(self): return "n"
            @staticmethod
            def helper(x): return x
            @classmethod
            def build(cls, dsn): return cls(dsn)
            async def fetch(self, url): return url
        assert Repo("pg://x", echo=True).find(1) == "pg://x"
        assert Repo.build("pg://y").dsn == "pg://y"

    def test_missing_members_reported_together(self):
        with pytest.raises(InterfaceError) as excinfo:
            class Partial(IAudited):
                def find(self, id): ...
        message = str(excinfo.value)
        for name in ("save", "name", "helper", "build", "fetch", "log"):
            assert f"'{name}' implement edilmemis" in message

    def test_plain_subclass_is_checked_at_definition(self):
        """Dekoratör olmadan da tanim aninda yakalanir."""
        with pytest.raises(InterfaceError, match="implement edilmemis"):
            class Sneaky(IRepository):
                pass

    def test_implements_decorator_is_still_accepted(self):
        @implements
        class Repo(IRepository):
            def find(self, id): return "r"
            def save(self, item): ...
            @property
            def name(self): return "n"
            @staticmethod
            def helper(x): return x
            @classmethod
            def build(cls, dsn): return cls()
            async def fetch(self, url): return url
        assert Repo().find(1) == "r"

    def test_members_of_and_missing_members(self):
        class Empty(IRepository, abstract=True):
            pass
        assert set(members_of(IAudited)) >= {"find", "save", "name", "log"}
        assert "find" in missing_members(Empty)


# --------------------------------------------------------------------------- #
# Soyut ara siniflar
# --------------------------------------------------------------------------- #
class TestAbstract:
    def test_abstract_class_may_be_incomplete(self):
        class BaseRepo(IRepository, abstract=True):
            def save(self, item): ...
            @property
            def name(self): return "base"
        assert is_abstract(BaseRepo)

    def test_abstract_class_cannot_be_instantiated(self):
        class BaseRepo(IRepository, abstract=True):
            def save(self, item): ...
        with pytest.raises(InterfaceError, match="soyut bir sinif"):
            BaseRepo()

    def test_concrete_subclass_of_abstract_is_checked(self):
        class BaseRepo(IRepository, abstract=True):
            def save(self, item): ...
            @property
            def name(self): return "base"

        with pytest.raises(InterfaceError, match="'find' implement edilmemis"):
            class Child(BaseRepo):
                @staticmethod
                def helper(x): return x
                @classmethod
                def build(cls, dsn): return None
                async def fetch(self, url): ...

        class Complete(BaseRepo):
            def find(self, id): return "r"
            @staticmethod
            def helper(x): return x
            @classmethod
            def build(cls, dsn): return None
            async def fetch(self, url): ...
        assert Complete().find(1) == "r"


# --------------------------------------------------------------------------- #
# Imza dogrulama
# --------------------------------------------------------------------------- #
class TestSignatures:
    def test_wrong_parameter_name_rejected(self):
        with pytest.raises(InterfaceError, match="parametre adi 'id' olmali"):
            class Bad(IRepository):
                def find(self, key): ...
                def save(self, item): ...
                @property
                def name(self): return ""
                @staticmethod
                def helper(x): return x
                @classmethod
                def build(cls, dsn): return None
                async def fetch(self, url): ...

    def test_missing_parameter_rejected(self):
        with pytest.raises(InterfaceError, match="eksik parametre"):
            class Bad(IRepository):
                def find(self): ...
                def save(self, item): ...
                @property
                def name(self): return ""
                @staticmethod
                def helper(x): return x
                @classmethod
                def build(cls, dsn): return None
                async def fetch(self, url): ...

    def test_extra_required_parameter_rejected(self):
        with pytest.raises(InterfaceError, match="fazladan zorunlu parametre"):
            class Bad(IRepository):
                def find(self, id, extra): ...
                def save(self, item): ...
                @property
                def name(self): return ""
                @staticmethod
                def helper(x): return x
                @classmethod
                def build(cls, dsn): return None
                async def fetch(self, url): ...

    def test_extra_optional_parameter_allowed(self):
        class Ok(IRepository):
            def find(self, id, timeout=5): return "r"
            def save(self, item): ...
            @property
            def name(self): return ""
            @staticmethod
            def helper(x): return x
            @classmethod
            def build(cls, dsn): return None
            async def fetch(self, url): ...
        assert Ok().find(1) == "r"

    def test_catch_all_signature_allowed(self):
        class Ok(IRepository):
            def find(self, *a, **k): return "r"
            def save(self, *a, **k): ...
            @property
            def name(self): return ""
            @staticmethod
            def helper(*a, **k): return None
            @classmethod
            def build(cls, *a, **k): return None
            async def fetch(self, *a, **k): ...
        assert Ok().find(1) == "r"

    def test_async_mismatch_rejected(self):
        with pytest.raises(InterfaceError, match="async def"):
            class Bad(IRepository):
                def find(self, id): ...
                def save(self, item): ...
                @property
                def name(self): return ""
                @staticmethod
                def helper(x): return x
                @classmethod
                def build(cls, dsn): return None
                def fetch(self, url): ...

    def test_kind_mismatch_rejected(self):
        with pytest.raises(InterfaceError, match="property olmali"):
            class Bad(IRepository):
                def find(self, id): ...
                def save(self, item): ...
                def name(self): return ""
                @staticmethod
                def helper(x): return x
                @classmethod
                def build(cls, dsn): return None
                async def fetch(self, url): ...

    def test_annotations_checked_when_requested(self):
        class IStrict(Interface, check_annotations=True):
            def run(self, count: int) -> bool: ...
        with pytest.raises(InterfaceError, match="anotasyonu"):
            class Bad(IStrict):
                def run(self, count: str) -> bool: ...

        class Good(IStrict):
            def run(self, count: int) -> bool: return True
        assert Good().run(1)

    def test_signature_metadata_is_preserved(self):
        assert str(inspect.signature(IRepository.find)) == "(self, id: int) -> str"


# --------------------------------------------------------------------------- #
# Property setter / deleter
# --------------------------------------------------------------------------- #
class TestProperties:
    def test_writable_property_requires_setter(self):
        class IConfig(Interface):
            @property
            def level(self) -> int: ...
            @level.setter
            def level(self, value: int) -> None: ...

        with pytest.raises(InterfaceError, match="setter'si eksik"):
            class ReadOnly(IConfig):
                @property
                def level(self): return 1

        class Writable(IConfig):
            @property
            def level(self): return self._v
            @level.setter
            def level(self, value): self._v = value
        obj = Writable()
        obj.level = 7
        assert obj.level == 7

    def test_deleter_contract(self):
        class ICache(Interface):
            @property
            def entry(self): ...
            @entry.deleter
            def entry(self): ...
        with pytest.raises(InterfaceError, match="deleter'si eksik"):
            class NoDeleter(ICache):
                @property
                def entry(self): return None


# --------------------------------------------------------------------------- #
# Default metotlar
# --------------------------------------------------------------------------- #
class TestDefaults:
    def test_default_method_is_optional_and_inherited(self):
        class IGreeter(Interface):
            def name(self) -> str: ...
            @default
            def greet(self) -> str:
                return f"merhaba {self.name()}"

        class Tr(IGreeter):
            def name(self): return "dunya"
        assert Tr().greet() == "merhaba dunya"

    def test_default_method_can_be_overridden_but_signature_checked(self):
        class IGreeter(Interface):
            @default
            def greet(self, loud: bool = False) -> str: return "hi"

        class Ok(IGreeter):
            def greet(self, loud=False): return "HI" if loud else "hi"
        assert Ok().greet(True) == "HI"

        with pytest.raises(InterfaceError, match="imzasi uyusmuyor"):
            class Bad(IGreeter):
                def greet(self, volume=False): return "x"

    def test_non_default_body_rejected(self):
        with pytest.raises(InterfaceError, match="govdesi bos olmali"):
            class IBad(Interface):
                def go(self): return 42


# --------------------------------------------------------------------------- #
# Miras, mixin ve isimlendirme
# --------------------------------------------------------------------------- #
class TestInheritance:
    def test_mixin_implementation_accepted(self):
        class LogMixin:
            def log(self, msg): return f"log:{msg}"

        class Repo(LogMixin, IAudited):
            def find(self, id): return "r"
            def save(self, item): ...
            @property
            def name(self): return ""
            @staticmethod
            def helper(x): return x
            @classmethod
            def build(cls, dsn): return None
            async def fetch(self, url): ...
        assert Repo().log("x") == "log:x"

    def test_class_named_with_i_prefix_is_not_an_interface(self):
        class Item:                      # arayuz degil, sadece adi I ile basliyor
            def price(self): return 5

        class Product(Item, IRepository):
            def find(self, id): return "r"
            def save(self, item): ...
            @property
            def name(self): return ""
            @staticmethod
            def helper(x): return x
            @classmethod
            def build(cls, dsn): return None
            async def fetch(self, url): ...
        assert Product().price() == 5

    def test_interface_cannot_inherit_concrete_class(self):
        class Concrete:
            def go(self): return 1
        with pytest.raises(InterfaceError, match="arayuz degil"):
            class IBad(Concrete, Interface):
                def other(self): ...

    def test_optional_name_prefix_rule(self):
        with pytest.raises(InterfaceError, match="'I' ile baslamali"):
            class Repository(Interface, name_prefix="I"):
                def go(self): ...

    def test_subclass_of_implementation_is_rechecked(self):
        class Repo(IRepository):
            def find(self, id): return "r"
            def save(self, item): ...
            @property
            def name(self): return ""
            @staticmethod
            def helper(x): return x
            @classmethod
            def build(cls, dsn): return None
            async def fetch(self, url): ...

        with pytest.raises(InterfaceError, match="parametre adi"):
            class BadChild(Repo):
                def find(self, wrong_name): return "r"


# --------------------------------------------------------------------------- #
# Onbellek gecersizleme
# --------------------------------------------------------------------------- #
class TestCacheInvalidation:
    def test_monkeypatch_after_verification_is_caught(self):
        class Repo(IRepository):
            def find(self, id): return "r"
            def save(self, item): ...
            @property
            def name(self): return ""
            @staticmethod
            def helper(x): return x
            @classmethod
            def build(cls, dsn): return None
            async def fetch(self, url): ...
        assert Repo().find(1) == "r"

        Repo.find = lambda self, wrong: "r"      # sonradan bozuldu
        with pytest.raises(InterfaceError, match="parametre adi 'id' olmali"):
            Repo()

    def test_patching_parent_invalidates_child(self):
        class IUnit(Interface):
            def run(self) -> None: ...

        class Parent(IUnit):
            def run(self): ...
        class Child(Parent):
            pass
        Child()
        del Parent.run
        with pytest.raises(InterfaceError, match="implement edilmemis"):
            Child()


# --------------------------------------------------------------------------- #
# Yapisal tipleme (Protocol benzeri)
# --------------------------------------------------------------------------- #
class TestStructural:
    def test_structural_isinstance_without_inheritance(self):
        class IClosable(Interface, structural=True):
            def close(self) -> None: ...

        class Duck:                     # IClosable'dan turemiyor
            def close(self) -> None: ...

        class Wrong:
            def close(self, force): ...

        assert isinstance(Duck(), IClosable)
        assert issubclass(Duck, IClosable)
        assert not isinstance(Wrong(), IClosable)
        assert structurally_implements(Duck, IClosable)

    def test_structural_is_opt_in(self):
        class ISealed(Interface):
            def close(self) -> None: ...
        class Duck:
            def close(self) -> None: ...
        assert not isinstance(Duck(), ISealed)


# --------------------------------------------------------------------------- #
# Jenerik arayuzler
# --------------------------------------------------------------------------- #
class TestGenerics:
    def test_generic_interface(self):
        from typing import Generic, TypeVar
        T = TypeVar("T")

        class IStore(Interface, Generic[T]):
            def get(self, key: str) -> T: ...

        class UserStore(IStore[str]):
            def get(self, key): return key.upper()
        assert UserStore().get("ali") == "ALI"
        assert IStore[str] is not None


# --------------------------------------------------------------------------- #
# Kaynak koda bagimli olmama
# --------------------------------------------------------------------------- #
class TestSourceIndependence:
    def test_definition_inside_exec(self):
        namespace = {"Interface": Interface}
        exec("class IDyn(Interface):\n"
             "    def go(self, a): ...\n"
             "class Impl(IDyn):\n"
             "    def go(self, a): return a\n", namespace)
        assert namespace["Impl"]().go(3) == 3

    def test_stub_detection(self):
        def a(self): pass
        def b(self): ...
        def c(self): "dokuman"
        def d(self): raise NotImplementedError
        def e(self): raise NotImplementedError("henuz yok")
        async def f(self, x): ...
        def g(self): return 42
        def h(self): print("yan etki")
        def i(self): raise ValueError("baska hata")
        assert all(map(is_stub, (a, b, c, d, e, f)))
        assert not any(map(is_stub, (g, h, i)))

    def test_stub_detection_without_source(self):
        namespace: dict = {}
        exec("def hidden(self): ...\ndef busy(self): return 1\n", namespace)
        assert is_stub(namespace["hidden"])
        assert not is_stub(namespace["busy"])

    @pytest.mark.parametrize("source", _STUB_FORMS)
    def test_every_accepted_stub_form_survives_the_bytecode_path(self, source):
        """Surumler arasi asil guvence.

        Kalibrasyon sozlugu, kabul ettigimizi soyledigimiz her bos govde
        bicimini kaynak kodu olmadan da tanimak zorunda. Bir CPython surumu
        opcode degistirirse bu test o surumde kirmizi yanar.
        """
        namespace: dict = {}
        exec(compile(source, "<test>", "exec"), namespace)
        assert _bytecode_is_stub(namespace["_s"])

    def test_bytecode_fallback_recognises_every_stub_form(self):
        namespace: dict = {}
        exec("def a(self): pass\n"
             "def b(self): ...\n"
             "def c(self): 'dokuman'\n"
             "def d(self): raise NotImplementedError\n"
             "def e(self): raise NotImplementedError('henuz yok')\n"
             "async def f(self, x): ...\n"
             "async def g(self): raise NotImplementedError\n", namespace)
        for name in "abcdefg":
            assert _bytecode_is_stub(namespace[name]), f"{name} stub sayilmaliydi"

    def test_bytecode_fallback_rejects_real_bodies(self):
        namespace: dict = {}
        exec("def g(self): return 42\n"
             "def h(self): print('yan etki')\n"
             "def i(self): raise ValueError('baska hata')\n"
             "def j(self): x = 1; return x\n"
             "def k(self): return []\n"
             "def m(self): self.sayac += 1\n", namespace)
        for name in "ghijkm":
            assert not _bytecode_is_stub(namespace[name]), f"{name} dolu sayilmaliydi"

    def test_bytecode_fallback_rejects_mixed_stub_instructions(self):
        namespace: dict = {}
        exec(
            "def a(self): return 'deger'\n"
            "def b(self): return NotImplementedError\n"
            "def c(self): return NotImplementedError()\n",
            namespace,
        )
        assert not any(_bytecode_is_stub(namespace[name]) for name in "abc")

    def test_callable_without_code_fails_closed(self):
        assert not _bytecode_is_stub(len)

    def test_unknown_code_shape_counts_as_a_real_body(self):
        namespace: dict = {}
        exec("def weird(self): return {*(1, 2)}\n", namespace)
        assert not _bytecode_is_stub(namespace["weird"])

    def test_contract_still_enforced_without_source(self):
        with pytest.raises(InterfaceError, match="govdesi bos olmali"):
            exec("class IBad(Interface):\n"
                 "    def calc(self): return 99\n", {"Interface": Interface})

        with pytest.raises(InterfaceError, match="govdesi bos olmali"):
            exec("class IBadText(Interface):\n"
                 "    def calc(self): return 'uygulama'\n", {"Interface": Interface})


# --------------------------------------------------------------------------- #
# Baska metaclass'larla birlikte kullanim
# --------------------------------------------------------------------------- #
class TestMetaclassInterop:
    def test_combined_metaclass_with_abcmeta(self):
        class Meta(InterfaceMeta, abc.ABCMeta):
            pass

        class ICloser(Interface, metaclass=Meta):
            def close(self) -> None: ...

        class Impl(ICloser, abc.ABC):
            def close(self) -> None: ...

        assert issubclass(Impl, ICloser)
        assert isinstance(Impl(), ICloser)

    def test_combined_metaclass_still_enforces_the_contract(self):
        class Meta(InterfaceMeta, abc.ABCMeta):
            pass

        class ICloser(Interface, metaclass=Meta):
            def close(self) -> None: ...

        with pytest.raises(InterfaceError, match="implement edilmemis"):
            class Broken(ICloser, abc.ABC):
                pass

    def test_abc_register_is_honoured(self):
        # super() zincirlemesi sayesinde ABCMeta.register semantigi yasiyor.
        class Meta(InterfaceMeta, abc.ABCMeta):
            pass

        class ICloser(Interface, metaclass=Meta):
            def close(self) -> None: ...

        class Foreign:
            def close(self) -> None: ...

        ICloser.register(Foreign)
        assert issubclass(Foreign, ICloser)


# --------------------------------------------------------------------------- #
# Dekorator stili (geriye donuk uyumluluk)
# --------------------------------------------------------------------------- #
class TestDecoratorStyle:
    def test_decorator_interface(self):
        @interface
        class ILegacy:
            def go(self, a): ...

        class Impl(ILegacy):
            def go(self, a): return a
        assert Impl().go(1) == 1
        with pytest.raises(InterfaceError):
            ILegacy()

    def test_decorator_inheritance_chain(self):
        """Turetilmis arayuz: dekoratör yerine `interface=True` kullanilir.

        Otomatik dogrulama tanim aninda calistigi icin `@interface`
        dekoratörü zincirin ikinci halkasinda kullanilamaz — dekoratör
        calismadan once sinif ifadesi zaten dogrulanmis olur.
        """
        @interface
        class IA:
            def a(self): ...

        class IB(IA, interface=True):
            def b(self): ...

        with pytest.raises(InterfaceError, match="'a' implement edilmemis"):
            class Impl(IB):
                def b(self): ...

    def test_hint_when_stub_only_class_is_not_marked_as_interface(self):
        @interface
        class IA:
            def a(self): ...

        with pytest.raises(InterfaceError, match="interface=True"):
            class IB(IA):            # arayuz olmasi isteniyordu ama isaretlenmedi
                def b(self): ...

    def test_verify_is_public(self):
        class IUnit(Interface):
            def run(self) -> None: ...
        class Impl(IUnit):
            def run(self): ...
        assert verify(Impl) is Impl
