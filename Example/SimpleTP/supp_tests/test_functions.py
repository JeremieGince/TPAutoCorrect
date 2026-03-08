"""
Supplementary tests for SimpleTP - student-written tests for their own code.
These are run with coverage to measure how well students test their code.
"""

from functions import add, mul, sub


def test_add():
    assert add(1, 2) == 3
    assert add(0, 0) == 0
    assert add(-1, 1) == 0


def test_sub():
    assert sub(5, 2) == 3
    assert sub(0, 0) == 0


def test_mul():
    assert mul(3, 3) == 9
    assert mul(0, 100) == 0
