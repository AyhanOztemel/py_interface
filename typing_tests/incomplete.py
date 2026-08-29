from interface_contract import Interface


class IService(Interface):
    def execute(self, value: int) -> str: ...


class Incomplete(IService):
    pass


incomplete = Incomplete()
