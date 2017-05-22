# -*- coding: utf-8 -*-

from jaeger_client.rpcmetrics import Operation
import pytest

NAMES = [
    ['GET', 'GET'],
    ['über', '--ber'],
]


@pytest.mark.parametrize('actual,expected', NAMES)
@pytest.mark.gen_test
def test_normalize(actual, expected):
    o = Operation()
    assert o.normalize(actual) == expected


def test_max_size():
    o = Operation(max_size=1)
    assert o.normalize('GET') == 'GET'
    assert o.normalize('POST') == '', 'Operation can only hold 1 normalized operation'
