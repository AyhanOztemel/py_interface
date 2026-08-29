"""Ikinci ornek: odeme gecidi alani.

Ilk ornekle hicbir isim paylasmiyor. Amaci `strict_interface`in belirli bir
dosyaya degil, herhangi bir alana uygulanabildigini gostermek.

Bu dosya `strict_interface`i import eden tek dosyadir; `example2.py` yalnizca
buradan arayuz siniflarini alir.
"""

from strict_interface import Interface, default


# --------------------------------------------------------------------------- #
# Kucuk, bagimsiz sozlesmeler
# --------------------------------------------------------------------------- #
class IValidatable(Interface):
    """Kendini dogrulayabilen her sey."""
    def validate(self) -> bool: ...


class ISerializable(Interface):
    """Sozluge cevrilip geri okunabilen her sey."""
    def to_dict(self) -> dict: ...

    @classmethod
    def from_dict(cls, payload: dict): ...


class IDisposable(Interface, structural=True):
    """Yapisal sozlesme: miras almadan da `isinstance` ile eslesir."""
    def release(self) -> None: ...


# --------------------------------------------------------------------------- #
# Asil sozlesme zinciri
# --------------------------------------------------------------------------- #
class IPaymentGateway(IValidatable, Interface):
    """Bir odeme saglayicisinin karsilamasi gereken sozlesme."""

    def charge(self, amount: float, currency: str) -> str: ...
    def refund(self, transaction_id: str) -> bool: ...

    @property
    def provider(self) -> str: ...

    @property
    def timeout(self) -> int: ...

    @timeout.setter
    def timeout(self, seconds: int) -> None: ...

    @staticmethod
    def format_amount(value: float) -> str: ...

    async def health_check(self) -> bool: ...

    @default
    def describe_gateway(self) -> str:
        """Govdeli varsayilan metot: ezilmesi zorunlu degil."""
        return f"{self.provider} gecidi, {self.timeout} sn zaman asimi"


class IAuditablePaymentGateway(IPaymentGateway, ISerializable, Interface):
    """Odeme gecidine denetim izi zorunlulugu ekler."""

    def audit_trail(self) -> list[str]: ...
    def purge_trail(self, *, confirm: bool = False) -> int: ...
