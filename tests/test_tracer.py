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

import mock
import random
import tornado.httputil

from opentracing import Format
from opentracing.ext import tags as ext_tags
from jaeger_client import ConstSampler, Tracer
from jaeger_client.thrift_gen.zipkincore import constants as g
from jaeger_client.thrift import add_zipkin_annotations


def log_exists(span, value):
    return filter(lambda (x): x.value == value, span.logs) != []


def test_start_trace(tracer):
    assert type(tracer) is Tracer
    with mock.patch.object(random.Random, 'getrandbits') as mock_random, \
            mock.patch('time.time') as mock_timestamp:
        mock_random.return_value = 12345L
        mock_timestamp.return_value = 54321L

        span = tracer.start_span('test')
        span.set_tag(ext_tags.SPAN_KIND, ext_tags.SPAN_KIND_RPC_SERVER)
        assert span, "Span must not be nil"
        assert span.tracer == tracer, "Tracer must be referenced from span"
        assert span.kind == ext_tags.SPAN_KIND_RPC_SERVER, \
            'Span must be server-side'
        assert span.trace_id == 12345L, "Must match trace_id"
        assert span.is_sampled(), "Must be sampled"
        assert span.parent_id is None, "Must not have parent_id (root span)"
        assert span.start_time == 54321L, "Must match timestamp"

        span.finish()
        assert span.end_time is not None, "Must have end_time defined"
        add_zipkin_annotations(span, None)
        assert len(span.logs) == 2, "Must have two events"
        assert log_exists(span, g.SERVER_RECV), 'Must have sr event'
        assert log_exists(span, g.SERVER_SEND), 'Must have ss event'
        tracer.reporter.assert_called_once()

        # TODO restore below once debug Trace Attribute is supported
        # tracer.sampler = ConstSampler(False)
        # span = tracer.start_span("test2", debug=True)
        # assert span.is_sampled(), \
        #     'Debug span must be sampled even if sampler said no'
    tracer.close()


def test_start_child(tracer):
    root = tracer.start_span("test")
    span = tracer.start_span("test", parent=root)
    span.set_tag(ext_tags.SPAN_KIND, ext_tags.SPAN_KIND_RPC_SERVER)
    assert span.is_sampled(), "Must be sampled"
    assert span.trace_id == root.trace_id, "Must have the same trace id"
    assert span.parent_id == root.span_id, "Must inherit parent id"
    span.finish()
    assert span.end_time is not None, "Must have end_time set"
    add_zipkin_annotations(span, None)
    assert len(span.logs) == 2, "Must have two events"
    assert log_exists(span, g.SERVER_SEND), 'Must have ss event'
    assert log_exists(span, g.SERVER_RECV), 'Must have sr event'
    tracer.reporter.assert_called_once()
    tracer.close()


def test_child_span(tracer):
    span = tracer.start_span("test")
    child = tracer.start_span("child", parent=span)
    child.set_tag(ext_tags.SPAN_KIND, ext_tags.SPAN_KIND_RPC_CLIENT)
    child.set_tag('bender', 'is great')
    child.log_event('kiss-my-shiny-metal-...')
    child.finish()
    span.finish()
    tracer.reporter.report_span.assert_called_once()
    assert len(span.logs) == 0, 'Parent span is Local, must not have events'
    assert len(child.logs) == 1, 'Child must have one events'
    add_zipkin_annotations(span=span, endpoint=None)
    add_zipkin_annotations(span=child, endpoint=None)
    assert len([t for t in span.tags if t.key == g.LOCAL_COMPONENT]) == 1
    assert len(child.logs) == 3, 'Child must have three events'
    assert log_exists(child, g.CLIENT_SEND), 'Must have cs event'
    assert log_exists(child, g.CLIENT_RECV), 'Must have cr event'

    tracer.sampler = ConstSampler(False)
    span = tracer.start_span("test")
    child = tracer.start_span("child", parent=span)
    child.set_tag('bender', 'is great')
    child.log_event('kiss-my-shiny-metal-...')
    child.finish()
    span.finish()
    assert len(child.logs) == 0, "Must have no events, not sampled"
    assert len(child.tags) == 0, "Must have no attributes, not sampled"
    tracer.close()


def test_sampler_effects(tracer):
    tracer.sampler = ConstSampler(True)
    span = tracer.start_span("test")
    assert span.is_sampled(), "Must be sampled"

    tracer.sampler = ConstSampler(False)
    span = tracer.start_span("test")
    assert not span.is_sampled(), "Must not be sampled"
    tracer.close()


def test_default_tracer():
    class Sender(object):
        def __init__(self):
            self._channel = mock.MagicMock()
            self.io_loop = mock.MagicMock()

    channel = Sender()
    sampler = ConstSampler(False)
    tracer = Tracer.default_tracer(channel=channel, service_name='service')
    assert tracer.reporter._channel == channel

    reporter = 'reporter'
    tracer = Tracer.default_tracer(channel=channel, service_name='service',
                                   reporter=reporter)
    assert tracer.reporter == reporter

    tracer = Tracer.default_tracer(channel=channel, service_name='service',
                                   sampler=sampler)
    assert tracer.sampler == sampler


def test_serialization(tracer):
    span = tracer.start_span('help')
    carrier = {}
    tracer.inject(span=span, format=Format.TEXT_MAP, carrier=carrier)
    assert len(carrier) > 0
    h_ctx = tornado.httputil.HTTPHeaders(carrier)
    assert 'UBER-TRACE-ID' in h_ctx
    span2 = tracer.join('x', Format.TEXT_MAP, carrier)
    assert span2 is not None
    assert span2.trace_id == span.trace_id
    assert span2.span_id == span.span_id
    assert span2.parent_id == span.parent_id
    assert span2.flags == span.flags
