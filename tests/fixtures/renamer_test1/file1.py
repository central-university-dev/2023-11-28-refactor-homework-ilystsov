class SomeClass:
    ...


def transform_class(SomeClass: list[SomeClass]) -> SomeClass:
    tmp = SomeClass

    def simple_fun(*args) -> SomeClass:
        cls = SomeClass
        ...

    class cls1(SomeClass):
        def __init__(self):
            SomeClass().__init__()

        def method(self, SomeClass):
            ...

    return tmp

class cls2(SomeClass):
    ...


x = lambda SomeClass: SomeClass + 1
y = lambda _: SomeClass


def fun1():
    class SomeClass:
        ...


class cls3:
    SomeClass = 3


def main():
    x = cls3.SomeClass
    a = [i for i in SomeClass]
    b = [SomeClass for SomeClass in range(10)]
    c = {i: SomeClass for i in range(10)}
    instance = SomeClass()
    transform_class(SomeClass=SomeClass)

