# strict-interface

Python'da **imzayi da dogrulayan**, hatayi **sinif tanimlanir tanimlanmaz**
veren ve kaynak koduna erisim gerektirmeyen arayuzler.

## Kurulum

```bash
pip install strict-interface
```

```python
from strict_interface import Interface, default

class IRepository(Interface):
    def find(self, id: int) -> str: ...
    def save(self, item: str) -> None: ...

    @property
    def name(self) -> str: ...

    @default
    def describe(self) -> str:          # Alt siniflara hazir miras kalan metot
        return f"repository<{self.name}>"

class SqlRepository(IRepository):       # dekoratör gerekmez
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn                  # kendi constructor'iniz korunur

    def find(self, id: int) -> str: return f"row {id}"
    def save(self, item: str) -> None: ...

    @property
    def name(self) -> str: return "sql"
```

### Interface icinde govdeli metot

Interface icinde somut/govdeli bir metot yazacaksaniz `@default` kullanin.
Bu dekorator, govdenin bilerek yazildigini belirtir. Alt sinif metodu hazir
olarak miras alir; isterse kendi metodunu yazarak degistirebilir. `@default`
olmadan yazilan govdeli interface metodu sozlesme hatasi kabul edilir.

## 0.3.0'da ne degisti

**Python 3.14 destegi.** 3.14 sabit yuklemeleri icin `LOAD_SMALL_INT` opcode'unu
getirdi. Kaynak koda erisilemeyen ortamlardaki bytecode yedegi bu komutu
tanimadigi icin `def m(self): return 1` gibi **dolu bir govdeyi bos saniyordu** —
yani sozlesme sessizce gevsiyordu.

Bununla birlikte yedek yolun yonu tersine cevrildi: artik tanimadigimiz her
opcode bir hesaplama kabul edilir ve govde **dolu** raporlanir. Onceki davranis
"emin degilsem gecir" idi; yenisi "emin degilsem reddet". Yeni bir CPython
surumu artik kutuphaneyi sessizce gevsetemez, en fazla yuksek sesle hata verir.

Ayri olarak `issubclass`/`isinstance` artik `super()` ile zincirleniyor; boylece
`InterfaceMeta` baska bir metaclass ile birlestirilebiliyor (asagiya bakin).

## 0.2.0'da ne degisti

Dogrulama artik **otomatik**. Bir arayuzden turetilen her sinif, `class`
ifadesi calistigi anda dogrulanir; `@implements` yazmak zorunda degilsiniz.
Dekoratör geriye donuk uyumluluk icin duruyor ve artik bir sey degistirmiyor.

Bunun bir sonucu var: sozlesmeyi **kasten** kismen dolduran ara siniflar icin
`abstract=True` vermelisiniz.

```python
class BaseRepo(IRepository, abstract=True):   # eksik olmasi serbest
    def save(self, item: str) -> None: ...

class SqlRepo(BaseRepo):                      # burada tam olmak zorunda
    def find(self, id: int) -> str: return "row"
    @property
    def name(self) -> str: return "sql"
```

`abstract=True` siniflar orneklenemez; dogrulama ilk somut alt sinifa ertelenir.

## `abc` ve `Protocol` yerine neden?

| | `abc.ABC` | `typing.Protocol` | `strict_interface` |
|---|---|---|---|
| Eksik metot yakalanir | ornekleme aninda | statik (calisma aninda hayir) | **tanim aninda** |
| **Imza uyumu dogrulanir** | hayir | statik olarak evet | **calisma aninda evet** |
| Govde bosluk zorunlulugu | hayir | hayir | **evet** (`@default` haric) |
| Arayuz orneklenemez | evet | — | evet |
| Yapisal (mirassiz) `isinstance` | hayir | `@runtime_checkable` ile, sadece isim | **isim + imza** |

Asil katki ucuncu ve son satir: ABC "metot var mi" diye bakar, imzaya bakmaz;
`runtime_checkable` Protocol de yalnizca ismin varligini kontrol eder.

## Ozellikler

- Metot, `@property` (getter/setter/deleter ayri ayri), `@staticmethod`,
  `@classmethod`, `async def`
- `@default` ile govdeli varsayilan metotlar
- `abstract=True` ile kismen dolduran ara siniflar
- Jenerik arayuzler: `class IStore(Interface, Generic[T])`
- Yapisal tipleme: `class IClosable(Interface, structural=True)` → `isinstance`
  miras olmadan calisir, imza da kontrol edilir
- Opsiyonel anotasyon kontrolu: `class IX(Interface, check_annotations=True)`
- Opsiyonel isim kurali: `class IX(Interface, name_prefix="I")` — varsayilan
  kapali, cunku Macarca notasyon PEP 8'e aykiridir
- Eksikler tek hatada **toplu** raporlanir
- Sinifa sonradan atama yapilirsa dogrulama onbellegi gecersizlenir
- Govde kontrolu once AST ile, kaynak yoksa bytecode ile → REPL, `exec`,
  notebook, frozen app ve yalniz `.pyc` dagitiminda da calisir

## Turetilmis arayuz yazimi

Bir sinif, **dogrudan** `Interface` listeliyorsa (veya `interface=True` aliyorsa)
arayuzdur; aksi halde implementasyondur.

```python
class IAudited(IRepository, Interface): ...      # arayuz
class IAudited(IRepository, interface=True): ... # ayni sey
class SqlRepository(IRepository): ...            # implementasyon
```

Isaretlemeyi unutup govdesi tamamen bos bir sinif yazarsaniz hata mesaji size
bunu hatirlatir.

## Statik tip denetleyiciler

`mypy`/`pyright` arayuzu normal bir sinif olarak gorur; `IRepository.find`
cagrilarindaki tip hatalarini yakalar. Bos govdeler icin `empty-body` hata kodunu
kapatmaniz gerekir (`pyproject.toml`de ayarlidir). Ozel bir mypy eklentisi
yazilmadikca sozlesme kontrolleri **calisma aninda** kalir.

## Baska metaclass'larla birlikte kullanim

Arayuzler `InterfaceMeta` uzerine kuruludur. Kendi metaclass'i olan bir taban
(`abc.ABC`, `enum.Enum`, Django `Model`, Pydantic `BaseModel`) ile dogrudan
birlestirirseniz Python `metaclass conflict` hatasi verir. Bu Python'un genel
kurali; cozumu iki metaclass'i birlestiren kucuk bir sinif yazmaktir:

```python
import abc
from strict_interface import Interface, InterfaceMeta

class Meta(InterfaceMeta, abc.ABCMeta):
    pass

class ICloser(Interface, metaclass=Meta):
    def close(self) -> None: ...

class Impl(ICloser, abc.ABC):
    def close(self) -> None: ...
```

`issubclass`/`isinstance` kontrolleri `super()` ile zincirlendigi icin diger
metaclass'in semantigi korunur — ornegin `ICloser.register(...)` calismaya
devam eder.

## Bilinen sinirlar

- `interface` dekoratörü artik yalnizca **zincirin ilk halkasinda** kullanilabilir.
  `@interface class IB(IA)` yazarsaniz, dekoratör calismadan once `IB` bir
  implementasyon olarak dogrulanir ve hata alirsiniz. Turetilmis arayuzler icin
  `class IB(IA, interface=True)` yazin.
- Kaynak koduna ulasilamayan ortamlarda govde kontrolu bytecode'a duser. Bu yol
  AST kadar hassas degildir: `return None` ve `return "sabit"` gibi govdeler bos
  sayilabilir. Kaynak erisilebilir oldugunda (normal durum) AST kullanilir ve bu
  belirsizlik olusmaz.
- Kendi metaclass'i olan taban siniflarla birlesim icin yukaridaki bolume bakin.

## Testler

```bash
pip install -e ".[dev]"
pytest -q          # 59 test
ruff check .
mypy strict_interface
```

## CI

`.github/workflows/ci.yml` her push ve pull request'te uc is calistirir:

| Is | Kapsam |
|---|---|
| `test` | Linux ve Windows uzerinde CPython **3.10 – 3.14** (10 kombinasyon) |
| `lint` | `ruff check` ve `mypy --strict` |
| `build` | wheel/sdist uretimi, `twine check`, `py.typed`in pakete girdigi dogrulanir |

`fail-fast: false` bilincli: bos govde tespiti bytecode'a dustugu icin hatalar
surume ozgu olabiliyor, bir surumun kirilmasi digerlerinin sonucunu gizlememeli.
`test` isi ayrica her surumde kalibre edilen opcode sozlugunu log'a yazar; bir
CPython surumu opcode degistirdiginde ne oldugu dogrudan gorunur.
