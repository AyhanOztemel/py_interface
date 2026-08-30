# interface-contract

Python için sınıf tanımlandığı anda hata veren, metot imzalarını çalışma
zamanında doğrulayan katı arayüz sözleşmeleri.

```bash
pip install interface-contract
```

Yeni projelerde önerilen import:

```python
from interface_contract import Interface, default


class Repository(Interface):
    def find(self, item_id: int) -> str: ...
    def save(self, item: str) -> None: ...

    @default
    def kind(self) -> str:
        return "repository"


class MemoryRepository(Repository):
    def find(self, item_id: int) -> str:
        return f"row {item_id}"

    def save(self, item: str) -> None:
        pass
```

Eksik metot, yanlış imza veya yanlış üye türü varsa `MemoryRepository` sınıfı
tanımlanırken `InterfaceError` oluşur. Nesne yaratılmasını veya metodun
çağrılmasını beklemez.

## Geriye dönük uyumluluk

Eski import yolu aynen çalışır:

```python
from strict_interface import Interface
```

İki paketteki `Interface` aynı nesnedir. Mevcut kodların importlarını değiştirmek
zorunda değilsiniz. PyPI dağıtım adı `interface-contract`, yeni ana import adı
`interface_contract` şeklindedir.

0.4.0 değişiklikleri eklemelidir. Önceki sürümlerde anotasyonlar alan sözleşmesi
sayılmadığı için bu davranış korunur; alan denetimi yalnızca açıkça
`check_attributes=True` verilince etkinleşir.

## Soyut ara sınıflar

Sözleşmeyi bilinçli olarak kısmen tamamlayan ara sınıflarda `abstract=True`
kullanın:

```python
class BaseRepository(Repository, abstract=True):
    def save(self, item: str) -> None:
        pass
```

Bu sınıf örneklenemez; tam doğrulama ilk somut alt sınıfta yapılır.

## Yapısal kullanım

Miras alamadığınız sınıfları isim ve imza birlikte kontrol ederek kullanmak için:

```python
class Closable(Interface, structural=True):
    def close(self) -> None: ...


class Resource:
    def close(self) -> None:
        pass


assert isinstance(Resource(), Closable)
```

## Alan sözleşmeleri

```python
class UserRecord(Interface, check_attributes=True):
    name: str
    age: int


class User(UserRecord):
    def __init__(self, name: str, age: int) -> None:
        self.name = name
        self.age = age
```

Alanlar `__init__` tamamlandıktan hemen sonra kontrol edilir. Tip denetimi bilinçli
olarak yüzeyseldir; örneğin `list[str]` için nesnenin liste olması kontrol edilir,
listenin bütün elemanları dolaşılmaz. Dataclass implementasyonları desteklenir.

Miras kullanmayan nesneler için `verify_instance(nesne, Arayuz)` hata verir veya
nesneyi döndürür; `satisfies(nesne, Arayuz)` ise `bool` döndürür.

## Adaptörler

```python
from interface_contract import AdapterRegistry

registry = AdapterRegistry()


@registry.register(dict, UserRecord)
def dict_to_user(data: dict[str, object]) -> User:
    return User(str(data["name"]), int(data["age"]))


user = registry.adapt({"name": "Ada", "age": 37}, UserRecord)
```

Adaptör sonucu hedef arayüze karşı doğrulanır. Ayrı kayıt defteri istemiyorsanız
global `adapt`, `can_adapt`, `register_adapter` ve `unregister_adapter`
fonksiyonlarını kullanabilirsiniz.

## Mypy desteği

İsteğe bağlı eklenti, eksik implementasyonların örneklenmesini statik analizde de
yakalar:

```toml
[tool.mypy]
plugins = ["interface_contract.mypy_plugin"]
```

Eklenti ek bir çalışma zamanı bağımlılığı getirmez. Mypy eklenti API'si deneysel
olduğu için çalışma zamanı doğrulaması esas güvence olmaya devam eder.

## Başlıca destekler

- normal ve async metotlar
- getter/setter/deleter parçaları ayrı doğrulanan property'ler
- staticmethod ve classmethod
- `@default` ile hazır implementasyonlar
- generic, çoklu ve türetilmiş arayüzler
- opsiyonel anotasyon denetimi (`check_annotations=True`)
- kaynak kodu bulunmayan REPL, notebook, `exec`, frozen ve yalnız bytecode
  ortamları

Ayrıntılı İngilizce belge ve API örnekleri için
[README.md](https://github.com/AyhanOztemel/py_interface/blob/main/README.md),
sürüm değişiklikleri için
[CHANGELOG.md](https://github.com/AyhanOztemel/py_interface/blob/main/CHANGELOG.md)
dosyasına bakın.

## Lisans

MIT
