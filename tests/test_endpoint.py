# -*- coding: utf-8 -*-

from jaeger_client.rpcmetrics import Endpoint
import pytest

NAMES = [
    ['GET','GET'],
    ['über', '--ber'],
]

@pytest.mark.parametrize('actual,expected', NAMES)
@pytest.mark.gen_test
def test_normalize(actual, expected):
    e = Endpoint()
    assert e.normalize(actual) == expected

def test_max_size():
    e = Endpoint(max_size=1)
    assert e.normalize('GET') == 'GET'
    assert e.normalize('POST') == '', 'Endpoint can only hold 1 normalized endpoint'
