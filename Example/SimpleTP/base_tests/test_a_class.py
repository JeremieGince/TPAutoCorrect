"""
Base tests for AClass in SimpleTP - run by the auto-corrector.
"""

import pytest
from a_class import AClass


@pytest.fixture
def instance():
    return AClass("test", 6, 3)


def test_aclass_add(instance):
    assert instance.add() == 9


def test_aclass_sub(instance):
    assert instance.sub() == 3


def test_aclass_mul(instance):
    assert instance.mul() == 18


def test_aclass_name(instance):
    assert instance.name == "test"
