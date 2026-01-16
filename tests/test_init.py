import pytest

import tac as pkg


@pytest.mark.parametrize(
    "attr",
    [
        "__author__",
        "__email__",
        "__copyright__",
        "__license__",
        "__url__",
        "__package__",
        "__version__",
    ],
)
def test_attributes(attr):
    assert hasattr(pkg, attr), f"Module does not have attribute {attr}"
    assert getattr(pkg, attr) is not None, f"Attribute {attr} is None"
    assert isinstance(getattr(pkg, attr), str), f"Attribute {attr} is not a string"
