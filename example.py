"""Kullanim ornegi.

Dikkat: bu dosya `strict_interface`i hic import etmiyor. Yalnizca
`interfaceClass.py`den arayuz siniflarini aliyor; dekoratör de yok.
Sozlesme dogrulamasi sinif tanimlandigi anda arka planda calisiyor.
"""

from typeguard import typechecked

from interfaceClass import (
    I_IV_Example, I_V_Example, I_VI_Example, IClosable, IExample, IIExample,
    IIIExample,
)


@typechecked
def type_safe_checked(class_name: IIExample):
    print("gelen class referansi --->", class_name)


@typechecked
def type_safe_checked2(class_name: I_VI_Example):
    print("gelen class referansi --->", class_name)


class ExampleImplementation(IIIExample):
    def __init__(self, label: str = "varsayilan") -> None:
        self.label = label                      # kendi constructor'i korunuyor

    def method1(self): print("method1 implemented")
    def method2(self, value): return f"method2({value})"
    def method3(self): print("method3 implemented")
    def method4(self, *, verbose=False): print("method4 verbose =", verbose)
    def method5(self): print("method5 implemented")
    def method6(self): print("method6 implemented")
    def method7(self): print("method7 implemented")
    def method8(self): print("method8 implemented")
    def method9(self): print("method9 implemented")
    def method10(self): print("sozlesme disi ek metot")


class ExampleImplementation2(I_IV_Example, I_V_Example, I_VI_Example):
    def method1(self): print("method1 implemented")
    def method2(self, value): return f"method2({value})"
    def method3(self): print("method3 implemented")
    def method4(self, *, verbose=False): print("method4 verbose =", verbose)
    def method5(self): print("method5 implemented")
    def method6(self): print("method6 implemented")
    def method7(self): print("method7 implemented")
    def method8(self): print("method8 implemented")
    def method9(self): print("method9 implemented")


def show(label, fn):
    try:
        result = fn()
        print(f"[OK ] {label}" + (f" -> {result}" if result is not None else ""))
    except Exception as exc:
        print(f"[ERR] {label} -> {type(exc).__name__}: {exc}")


print("--- implementasyon calisiyor ---")
impl = ExampleImplementation("uretim")
impl.method1()
impl.method8()
impl.method4(verbose=True)                       # keyword-only imza korunuyor
show("method2 imzali cagri", lambda: impl.method2(42))
show("constructor korunuyor", lambda: impl.label)
show("govdeli hazir metot", lambda: impl.describe())

print("\n--- arayuzler orneklenemez ---")
for iface in (IExample, IIExample, IIIExample, I_IV_Example, I_V_Example, I_VI_Example):
    show(iface.__name__, iface)

print("\n--- nominal tip kontrolu (typeguard) ---")
show("dogru sinif", lambda: type_safe_checked(ExampleImplementation()))
show("yanlis sinif", lambda: type_safe_checked(ExampleImplementation2()))
show("dogru sinif 2", lambda: type_safe_checked2(ExampleImplementation2()))
show("yanlis sinif 2", lambda: type_safe_checked2(ExampleImplementation()))

print("\n--- eksik / hatali implementasyon tanim aninda yakalaniyor ---")


def eksik():
    class Eksik(IIIExample):                     # dekoratör yok, yine de yakalanir
        def method1(self): ...


show("eksik metotlar", eksik)


def yanlis_imza():
    class YanlisImza(I_V_Example):
        def method5(self, beklenmeyen): ...
        def method6(self): ...


show("yanlis imza", yanlis_imza)

print("\n--- soyut ara sinif (abstract=True) ---")


def soyut_tanim():
    class YarimRepo(IIIExample, abstract=True):  # kasten eksik: hata vermez
        def method1(self): ...
        def method2(self, value): return ""
    return "tanim gecti"


show("abstract=True tanimlanabiliyor", soyut_tanim)


def soyut_ornekleme():
    class YarimRepo(IIIExample, abstract=True):
        def method1(self): ...
    return YarimRepo()


show("abstract sinif orneklenemez", soyut_ornekleme)

print("\n--- yapisal tipleme (miras yok) ---")


class Dosya:
    def close(self) -> None: print("kapandi")


show("isinstance(Dosya(), IClosable)", lambda: isinstance(Dosya(), IClosable))
