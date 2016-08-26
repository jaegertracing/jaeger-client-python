# Copyright (c) 2016 Uber Technologies, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

from __future__ import absolute_import

import mock
import json
import pytest
import opentracing
from crossdock.server import server
from tornado.httpclient import HTTPRequest
from jaeger_client import Tracer, ConstSampler
from jaeger_client.reporter import InMemoryReporter

tchannel_port = "9999"


@pytest.fixture
def app():
    """Required by pytest-tornado's http_server fixture"""
    s = server.Server(int(tchannel_port))
    s.tchannel.listen()
    return server.make_app(s)


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
for s2 in ["HTTP", "TCHANNEL"]:
    for s3 in ["HTTP", "TCHANNEL"]:
        for sampled in [True, False]:
            PERMUTATIONS.append((s2, s3, sampled))


@pytest.mark.parametrize('s2_transport,s3_transport,sampled', PERMUTATIONS)
@pytest.mark.gen_test
def test_trace_propagation(
        s2_transport, s3_transport, sampled, tracer,
        base_url, http_port, http_client):

    # verify that server is ready
    yield http_client.fetch(
        request=HTTPRequest(
            url=base_url,
            method='HEAD',
        )
    )

    level3 = dict()
    level3["serviceName"] = "python"
    level3["serverRole"] = "s3"
    level3["transport"] = s3_transport
    level3["host"] = "localhost"
    level3["port"] = str(http_port) if s3_transport == "HTTP" else tchannel_port

    level2 = dict()
    level2["serviceName"] = "python"
    level2["serverRole"] = "s2"
    level2["transport"] = s2_transport
    level2["host"] = "localhost"
    level2["port"] = str(http_port) if s2_transport == "HTTP" else tchannel_port
    level2["downstream"] = level3

    level1 = dict()
    level1["baggage"] = "Zoidberg"
    level1["serverRole"] = "s1"
    level1["sampled"] = sampled
    level1["downstream"] = level2
    body = json.dumps(level1)

    with mock.patch('opentracing.tracer', tracer):
        assert opentracing.tracer == tracer # sanity check that patch worked

        req = HTTPRequest(url="%s/start_trace" % base_url, method="POST",
                          headers={"Content-Type": "application/json"},
                          body=body,
                          request_timeout=2)

        response = yield http_client.fetch(req)
        assert response.code == 200
        tr = server.serializer.traceresponse_from_json(response.body)
        assert tr is not None
        assert tr.span is not None
        assert tr.span.baggage == level1.get("baggage")
        assert tr.span.sampled == sampled
        assert tr.span.traceId is not None
        assert tr.downstream is not None
        assert tr.downstream.span.baggage == level1.get("baggage")
        assert tr.downstream.span.sampled == sampled
        assert tr.downstream.span.traceId == tr.span.traceId
        assert tr.downstream.downstream is not None
        assert tr.downstream.downstream.span.baggage == level1.get("baggage")
        assert tr.downstream.downstream.span.sampled == sampled
        assert tr.downstream.downstream.span.traceId == tr.span.traceId
