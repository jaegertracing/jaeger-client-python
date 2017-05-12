# -*- coding: utf-8 -*-

from jaeger_client.rpcmetrics import NameNormalizer
import pytest

NAMES = [
    ['GET','GET'],
    ['über', '--ber'],
]

@pytest.mark.parametrize('actual,expected', NAMES)
@pytest.mark.gen_test
def test_normalize(actual, expected):
    nn = NameNormalizer()
    assert nn.normalize(actual) == expected
