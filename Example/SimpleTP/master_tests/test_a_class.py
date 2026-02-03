import sys
import os
import pytest

try:
    import tac
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
    import tac

try:
    from ..src.a_class import AClass
except ImportError:
    AClass = tac.utils.import_obj_from_file(
        "AClass", tac.utils.find_filepath("a_class.py", root=os.path.join(os.path.dirname(__file__), "..", "src"))
    )


@pytest.mark.parametrize(
    "a, expected",
    [
        (AClass("", 1, 1), 2),
        (AClass("", 2, 2), 4),
        (AClass("", 3, 3), 6),
    ],
)
def test_add(a, expected):
    assert a.add() == expected


@pytest.mark.parametrize(
    "a, expected",
    [
        (AClass("", 1, 1), 0),
        (AClass("", 2, 2), 0),
        (AClass("", 3, 3), 0),
    ],
)
def test_sub(a, expected):
    assert a.sub() == expected


@pytest.mark.parametrize(
    "a, expected",
    [
        (AClass("", 1, 1), 1),
        (AClass("", 2, 2), 4),
        (AClass("", 3, 3), 9),
    ],
)
def test_mul(a, expected):
    assert a.mul() == expected


@pytest.mark.parametrize(
    "a, expected",
    [
        (AClass("a", 1, 1), "a"),
        (AClass("b", 2, 2), "b"),
        (AClass("c", 3, 3), "c"),
    ],
)
def test_name(a, expected):
    assert a.name == expected
