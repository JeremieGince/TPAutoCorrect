import sys
import os
import pytest

try:
    from ..src.functions import add, sub, mul
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))
    from functions import add, sub, mul, bad_func


@pytest.mark.parametrize(
    "a, b, expected",
    [
        (1, 2, 3),
        (2, 3, 5),
        (3, 4, 7),
    ],
)
def test_add(a, b, expected):
    assert add(a, b) == expected


@pytest.mark.parametrize(
    "a, b, expected",
    [
        (1, 2, -1),
        (2, 3, -1),
        (3, 4, -1),
    ],
)
def test_sub(a, b, expected):
    assert sub(a, b) == expected


@pytest.mark.parametrize(
    "a, b, expected",
    [
        (1, 2, 2),
        (2, 3, 6),
        (3, 4, 12),
    ],
)
def test_mul(a, b, expected):
    assert mul(a, b) == expected


def test_bad_func():
    assert bad_func() == (not bad_func())
