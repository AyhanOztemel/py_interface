"""strict_interface — Java/C# tarzi, imza dogrulayan arayuzler.

    from strict_interface import Interface

    class IRepository(Interface):
        def find(self, id: int) -> str: ...
        def save(self, item: str) -> None: ...

    class SqlRepository(IRepository):        # dekoratör gerekmez
        def __init__(self, dsn: str) -> None:
            self.dsn = dsn
        def find(self, id: int) -> str: return f"row {id}"
        def save(self, item: str) -> None: ...

Sozlesme, sinif tanimlandigi anda dogrulanir. Sozlesmeyi kasten kismen
dolduran ara siniflar icin `abstract=True` verin:

    class BaseRepo(IRepository, abstract=True):
        def save(self, item: str) -> None: ...
"""

from ._core import (
    Interface,
    InterfaceError,
    InterfaceMeta,
    Member,
    default,
    implements,
    interface,
    interface_implement,
    is_abstract,
    is_interface,
    is_stub,
    members_of,
    missing_members,
    signature_problem,
    structurally_implements,
    verify,
)

__all__ = [
    "Interface", "InterfaceError", "InterfaceMeta", "Member",
    "default", "implements", "interface", "interface_implement",
    "is_abstract", "is_interface", "is_stub", "members_of",
    "missing_members", "signature_problem", "structurally_implements",
    "verify",
]
__version__ = "0.3.0"
