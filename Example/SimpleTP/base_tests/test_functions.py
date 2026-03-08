"""
Base tests for SimpleTP - run by the auto-corrector against student code.
"""

from functions import add, bad_func, mul, sub


def test_add_positive():
    assert add(2, 3) == 5


def test_add_negative():
    assert add(-1, -2) == -3


def test_add_mixed():
    assert add(5, -3) == 2


def test_sub_positive():
    assert sub(5, 3) == 2


def test_sub_negative():
    assert sub(-1, -2) == 1


def test_mul_positive():
    assert mul(3, 4) == 12


def test_mul_by_zero():
    assert mul(5, 0) == 0


def test_bad_func_returns_false():
    assert bad_func() is False
