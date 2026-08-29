"""Ikinci kullanim ornegi: odeme gecitleri.

`strict_interface` burada da import edilmiyor, dekoratör de yok.
Sozlesme dogrulamasi sinif tanimlandigi anda arka planda calisiyor.
"""

import asyncio

from typeguard import typechecked

from interfaceClass2 import (
    IAuditablePaymentGateway, IDisposable, IPaymentGateway, ISerializable,
    IValidatable,
)


# --------------------------------------------------------------------------- #
# Tam implementasyon
# --------------------------------------------------------------------------- #
class StripeGateway(IAuditablePaymentGateway):
    def __init__(self, api_key: str, timeout: int = 30) -> None:
        self.api_key = api_key                 # kendi constructor'i korunuyor
        self._timeout = timeout
        self._trail: list[str] = []

    def validate(self) -> bool:
        return self.api_key.startswith("sk_")

    def charge(self, amount: float, currency: str) -> str:
        self._trail.append(f"charge {amount} {currency}")
        return f"txn_{int(amount * 100)}_{currency.lower()}"

    def refund(self, transaction_id: str) -> bool:
        self._trail.append(f"refund {transaction_id}")
        return transaction_id.startswith("txn_")

    @property
    def provider(self) -> str:
        return "stripe"

    @property
    def timeout(self) -> int:
        return self._timeout

    @timeout.setter
    def timeout(self, seconds: int) -> None:
        self._timeout = seconds

    @staticmethod
    def format_amount(value: float) -> str:
        return f"{value:,.2f}"

    async def health_check(self) -> bool:
        await asyncio.sleep(0)
        return True

    def to_dict(self) -> dict:
        return {"provider": self.provider, "timeout": self._timeout}

    @classmethod
    def from_dict(cls, payload: dict):
        return cls("sk_restored", payload.get("timeout", 30))

    def audit_trail(self) -> list[str]:
        return list(self._trail)

    def purge_trail(self, *, confirm: bool = False) -> int:
        if not confirm:
            return 0
        count = len(self._trail)
        self._trail.clear()
        return count


# --------------------------------------------------------------------------- #
# Soyut ara sinif + somut alt sinif
# --------------------------------------------------------------------------- #
class BaseSandboxGateway(IPaymentGateway, abstract=True):
    """Ortak davranisi toplar, sozlesmeyi kasten yarim birakir."""

    def validate(self) -> bool:
        return True

    @property
    def timeout(self) -> int:
        return 5

    @timeout.setter
    def timeout(self, seconds: int) -> None:
        raise RuntimeError("sandbox timeout sabittir")

    @staticmethod
    def format_amount(value: float) -> str:
        return f"~{value:.0f}"

    async def health_check(self) -> bool:
        return True


class SandboxGateway(BaseSandboxGateway):
    """Eksikleri tamamlar; burada tam olmak zorunda."""

    def charge(self, amount: float, currency: str) -> str:
        return "txn_sandbox"

    def refund(self, transaction_id: str) -> bool:
        return True

    @property
    def provider(self) -> str:
        return "sandbox"


# --------------------------------------------------------------------------- #
# typeguard ile nominal tip kontrolu
# --------------------------------------------------------------------------- #
@typechecked
def process(gateway: IAuditablePaymentGateway) -> str:
    return gateway.charge(19.9, "TRY")


@typechecked
def ping(gateway: IPaymentGateway) -> str:
    return gateway.provider


def show(label, fn):
    try:
        result = fn()
        print(f"[OK ] {label}" + (f" -> {result}" if result is not None else ""))
    except Exception as exc:
        head, *rest = str(exc).splitlines()
        print(f"[ERR] {label} -> {type(exc).__name__}: {head}")
        for line in rest:
            if line.strip():
                print(f"       {line.strip()}")


# --------------------------------------------------------------------------- #
print("--- tam implementasyon ---")
stripe = StripeGateway("sk_live_123", timeout=45)
show("charge", lambda: stripe.charge(250.0, "USD"))
show("refund", lambda: stripe.refund("txn_25000_usd"))
show("property okuma", lambda: stripe.provider)
show("staticmethod", lambda: StripeGateway.format_amount(1234567.891))
show("classmethod", lambda: StripeGateway.from_dict({"timeout": 10}).timeout)
show("async metot", lambda: asyncio.run(stripe.health_check()))
show("default metot", lambda: stripe.describe_gateway())
show("kendi constructor'i", lambda: stripe.api_key)


def property_setter():
    stripe.timeout = 90
    return stripe.timeout


show("property setter", property_setter)
show("keyword-only parametre", lambda: stripe.purge_trail(confirm=True))

print("\n--- soyut ara sinif ---")
show("BaseSandboxGateway orneklenemez", BaseSandboxGateway)
show("SandboxGateway calisir", lambda: SandboxGateway().charge(1.0, "EUR"))
show("soyut sinifin default metodu miras alindi",
     lambda: SandboxGateway().describe_gateway())

print("\n--- arayuzler orneklenemez ---")
for contract in (IValidatable, ISerializable, IDisposable,
                 IPaymentGateway, IAuditablePaymentGateway):
    show(contract.__name__, contract)

print("\n--- nominal tip kontrolu (typeguard) ---")
show("dogru sinif", lambda: process(stripe))
show("yanlis sinif", lambda: process(SandboxGateway()))
show("ust arayuz kabul ediyor", lambda: ping(SandboxGateway()))

print("\n--- sozlesme ihlalleri tanim aninda yakalaniyor ---")


def eksik_uyeler():
    class YarimGecit(IAuditablePaymentGateway):
        def charge(self, amount, currency): return "txn"


show("eksik uyeler", eksik_uyeler)


def yanlis_parametre_adi():
    class HataliImza(IValidatable):
        def validate(self, gereksiz): return True


show("fazladan zorunlu parametre", yanlis_parametre_adi)


def property_yerine_metot():
    class MetotOlarak(BaseSandboxGateway):
        def charge(self, amount, currency): return "txn"
        def refund(self, transaction_id): return True
        def provider(self): return "yanlis"        # property olmaliydi


show("property yerine metot", property_yerine_metot)


def eksik_setter():
    class SaltOkunur(BaseSandboxGateway):
        def charge(self, amount, currency): return "txn"
        def refund(self, transaction_id): return True
        @property
        def provider(self): return "salt-okunur"
        @property
        def timeout(self): return 1                # setter'i yok


show("property setter eksik", eksik_setter)


def async_uyumsuz():
    class SenkronSaglik(BaseSandboxGateway):
        def charge(self, amount, currency): return "txn"
        def refund(self, transaction_id): return True
        @property
        def provider(self): return "senkron"
        def health_check(self): return True        # async olmaliydi


show("async uyumsuzlugu", async_uyumsuz)


def govdeli_arayuz():
    class IBozuk(IValidatable, interface=True):
        def compute(self) -> int:
            return 42                              # arayuz govdesi bos olmali


show("arayuzde govdeli metot", govdeli_arayuz)

print("\n--- yapisal tipleme (miras yok) ---")


class TempFile:
    """IDisposable'dan turemiyor ama imzasi uyuyor."""
    def release(self) -> None:
        print("gecici dosya silindi")


class Connection:
    """Imzasi uymuyor: fazladan zorunlu parametre."""
    def release(self, force) -> None: ...


show("isinstance(TempFile(), IDisposable)", lambda: isinstance(TempFile(), IDisposable))
show("isinstance(Connection(), IDisposable)", lambda: isinstance(Connection(), IDisposable))
show("issubclass(TempFile, IDisposable)", lambda: issubclass(TempFile, IDisposable))
