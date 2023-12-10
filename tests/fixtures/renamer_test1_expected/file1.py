class NEW_CLASS:
    ...


def transform_class(SomeClass: list[NEW_CLASS]) -> NEW_CLASS:
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

class cls2(NEW_CLASS):
    ...


x = lambda SomeClass: SomeClass + 1
y = lambda _: NEW_CLASS


def fun1():
    class SomeClass:
        ...


class cls3:
    SomeClass = 3


def main():
    x = cls3.SomeClass
    a = [i for i in NEW_CLASS]
    b = [SomeClass for SomeClass in range(10)]
    c = {i: NEW_CLASS for i in range(10)}
    instance = NEW_CLASS()
    transform_class(SomeClass=NEW_CLASS)

