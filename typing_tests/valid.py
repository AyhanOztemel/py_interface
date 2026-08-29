from interface_contract import Interface, default


class IService(Interface):
    def execute(self, value: int) -> str: ...

    @default
    def label(self) -> str:
        return "service"


class Service(IService):
    def execute(self, value: int) -> str:
        return str(value)


service = Service()
result: str = service.execute(1)
