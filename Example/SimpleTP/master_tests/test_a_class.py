import sys
import os
import pytest

try:
    from ..src.a_class import AClass
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))
    from a_class import AClass


@pytest.mark.parametrize(
    "a, expected",
    [
        (AClass("", 1, 1), 2),
        (AClass("", 2, 2), 4),
        (AClass("", 3, 3), 6),
    ]
)
def test_add(a, expected):
    assert a.add() == expected


@pytest.mark.parametrize(
    "a, expected",
    [
        (AClass("", 1, 1), 0),
        (AClass("", 2, 2), 0),
        (AClass("", 3, 3), 0),
    ]
)
def test_sub(a, expected):
    assert a.sub() == expected


@pytest.mark.parametrize(
    "a, expected",
    [
        (AClass("", 1, 1), 1),
        (AClass("", 2, 2), 4),
        (AClass("", 3, 3), 9),
    ]
)
def test_mul(a, expected):
    assert a.mul() == expected


@pytest.mark.parametrize(
    "a, expected",
    [
        (AClass("a", 1, 1), "a"),
        (AClass("b", 2, 2), "b"),
        (AClass("c", 3, 3), "c"),
    ]
)
def test_name(a, expected):
    assert a.name == expected
