import math

from leakwatch.scanner.entropy import shannon


def test_entropy_bounds():
    assert shannon("") == 0
    assert shannon("aaaaaaaa") == 0
    assert math.isclose(shannon("ab"), 1.0)
    assert math.isclose(shannon("abcd" * 4), 2.0)


def test_random_vs_word():
    import fakes
    assert shannon(fakes.generic_password()) >= 3.5
    assert shannon("changeme") < 3.5
    assert shannon("xxxxxxxxxxxx") < 1
