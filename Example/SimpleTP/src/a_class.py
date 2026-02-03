from functions import add, sub, mul


class AClass:
    def __init__(self, name, a, b):
        self.name = name
        self.a = a
        self.b = b

    def add(self):
        return add(self.a, self.b)

    def sub(self):
        return sub(self.a, self.b)

    def mul(self):
        return mul(self.a, self.b)
