# Copyright (c) 2016-2018 Uber Technologies, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import absolute_import

import six
import mock
import json
import os
import pytest
import opentracing
from mock import MagicMock
from tornado.httpclient import HTTPRequest
from jaeger_client import Tracer, ConstSampler
from jaeger_client.reporter import InMemoryReporter
from crossdock.server.endtoend import EndToEndHandler, _determine_host_port, _parse_host_port

tchannel_port = '9999'


# noinspection PyShadowingNames
@pytest.yield_fixture
def tracer():
    tracer = Tracer(
        service_name='test-tracer',
        sampler=ConstSampler(True),
        reporter=InMemoryReporter(),
    )
    try:
        yield tracer
    finally:
        tracer.close()


PERMUTATIONS = []
for s2 in ['HTTP', 'TCHANNEL']:
    for s3 in ['HTTP', 'TCHANNEL']:
        for sampled in [True, False]:
            PERMUTATIONS.append((s2, s3, sampled))


def test_determine_host_port():
    original_value = os.environ.get('AGENT_HOST_PORT', None)
    os.environ['AGENT_HOST_PORT'] = 'localhost:1234'
    host, port = _determine_host_port()

    # Before any assertions, restore original environment variable.
    if original_value:
        os.environ['AGENT_HOST_PORT'] = original_value

    assert host == 'localhost'
    assert port == 1234


def test_parse_host_port():
    test_cases = [
        [('', 'localhost', 5678), ('localhost', 5678)],
        [('test:1234', 'localhost', 5678), ('test', 1234)],
    ]
    for test_case in test_cases:
        args, result = test_case
        host, port = _parse_host_port(*args)
        assert (host, port) == result
