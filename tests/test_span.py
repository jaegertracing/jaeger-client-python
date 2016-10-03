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

import collections
import json

from opentracing.ext import tags as ext_tags
from jaeger_client import Span, SpanContext, ConstSampler
from jaeger_client.thrift import add_zipkin_annotations


def test_baggage():
    ctx = SpanContext(trace_id=1, span_id=2, parent_id=None, flags=1)
    span = Span(context=ctx, operation_name='x', tracer=None)
    assert span.get_baggage_item('x') is None
    span.set_baggage_item('x', 'y').\
        set_baggage_item('z', 'why')
    assert span.get_baggage_item('x') == 'y'
    assert span.get_baggage_item('z') == 'why'
    assert span.get_baggage_item('tt') is None
    assert len(span.context.baggage) == 2
    span.set_baggage_item('x', 'b')  # override
    assert span.get_baggage_item('x') == 'b'
    assert len(span.context.baggage) == 2
    span.set_baggage_item('X_y', '123')
    assert span.get_baggage_item('X_y') == '123'
    assert span.get_baggage_item('x-Y') is None


def test_sampling_priority(tracer):
    tracer.sampler = ConstSampler(False)
    span = tracer.start_span(operation_name='x')
    assert span.is_sampled() is False
    span.set_tag(ext_tags.SAMPLING_PRIORITY, 1)
    assert span.is_sampled()
    assert span.is_debug()
    span.set_tag(ext_tags.SAMPLING_PRIORITY, 0)
    assert span.is_sampled() is False


def test_span_logging(tracer):
    tpl = collections.namedtuple(
        'Test',
        ['method', 'args', 'kwargs', 'expected', 'error', 'timestamp'])

    def test(method, expected,
             args=None, kwargs=None, error=False, timestamp=None):
        return tpl(
            method=method,
            args=args if args else [],
            expected=expected,
            kwargs=kwargs if kwargs else {},
            error=error,
            timestamp=timestamp,
        )

    def event_payload(event, payload):
        return {'event': event, 'payload': payload}

    def from_json(val):
        return json.loads(val)

    tests = [
        # deprecated info() method
        test(method='info',
             args=['msg'],
             expected='msg'),
        test(method='info',
             args=['msg', 'data'],
             expected=event_payload('msg', 'data')),
        # deprecated error() method
        test(method='error',
             args=['msg'],
             expected='msg', error=True),
        test(method='error',
             args=['msg', 'data'],
             expected=event_payload('msg', 'data'), error=True),
        # deprecated log_event() method
        test(method='log_event',
             args=['msg'],
             expected='msg'),
        test(method='log_event',
             args=['msg', 'data'],
             expected=event_payload('msg', 'data')),
        # deprecated log() method
        test(method='log',
             kwargs={'event': 'msg'},
             expected='msg'),
        test(method='log',
             kwargs={'event': 'msg', 'payload': 'data'},
             expected=event_payload('msg', 'data')),
        test(method='log',
             kwargs={'event': 'msg', 'payload': 'data', 'ignored': 'blah'},
             expected=event_payload('msg', 'data')),
        test(method='log',
             kwargs={'event': 'msg', 'payload': 'data', 'timestamp': 123},
             expected=event_payload('msg', 'data'),
             timestamp=123 * 1000 * 1000),  # in microseconds
        # log_kv()
        test(method='log_kv',
             args=[{'event': 'msg'}],
             expected='msg'),
        test(method='log_kv',
             args=[{'event': 'msg', 'x': 'y'}],
             expected={'event': 'msg', 'x': 'y'}),
        test(method='log_kv',
             args=[{'event': 'msg', 'x': 'y'}, 123],  # all args positional
             expected={'event': 'msg', 'x': 'y'},
             timestamp=123 * 1000 * 1000),
        test(method='log_kv',
             args=[{'event': 'msg', 'x': 'y'}],  # positional and kwargs
             kwargs={'timestamp': 123},
             expected={'event': 'msg', 'x': 'y'},
             timestamp=123 * 1000 * 1000),
        test(method='log_kv',
             args=[],  # kwargs only
             kwargs={
                 'key_values': {'event': 'msg', 'x': 'y'},
                 'timestamp': 123,
             },
             expected={'event': 'msg', 'x': 'y'},
             timestamp=123 * 1000 * 1000),  # to microseconds
    ]

    for test in tests:
        name = '%s' % (test,)
        span = tracer.start_span(operation_name='x')
        span.logs = []
        span.tags = []

        if test.method == 'info':
            span.info(*test.args, **test.kwargs)
        elif test.method == 'error':
            span.error(*test.args, **test.kwargs)
        elif test.method == 'log':
            span.log(*test.args, **test.kwargs)
        elif test.method == 'log_event':
            span.log_event(*test.args, **test.kwargs)
        elif test.method == 'log_kv':
            span.log_kv(*test.args, **test.kwargs)
        else:
            raise ValueError('Unknown method %s' % test.method)

        assert len(span.logs) == 1, name
        log = span.logs[0]
        if isinstance(test.expected, dict):
            log.value = from_json(log.value)
        assert log.value == test.expected

        if test.timestamp:
            assert log.timestamp == test.timestamp

        if test.error:
            assert len(span.tags) == 1, name
            assert span.tags[0].key == 'error'
        else:
            assert len(span.tags) == 0, name


def test_span_to_string(tracer):
    tracer.service_name = 'unittest'
    ctx = SpanContext(trace_id=1, span_id=1, parent_id=1, flags=1)
    span = Span(context=ctx, operation_name='crypt', tracer=tracer)
    assert '%s' % span == '1:1:1:1 unittest.crypt'


def test_span_peer_tags(tracer):
    for test in [[1, 2, 3], [2, 1, 3], [3, 2, 1]]:
        span = tracer.start_span(operation_name='x')
        span.set_tag(ext_tags.SPAN_KIND, ext_tags.SPAN_KIND_RPC_SERVER)
        for t in test:
            # either of peer tags can initialize span.peer dictionary, so
            # we try permutations such that each gets a change to be first.
            if t == 1:
                span.set_tag(ext_tags.PEER_SERVICE, 'downstream')
            elif t == 2:
                span.set_tag(ext_tags.PEER_HOST_IPV4, 127 << 24 | 1)
            elif t == 3:
                span.set_tag(ext_tags.PEER_PORT, 12345)
        span.finish()
        add_zipkin_annotations(span, None)
        ca = [e for e in span.tags if e.key == 'ca'][0]
        assert ca.host.service_name == 'downstream'
        assert ca.host.ipv4 == 127 << 24 | 1
        assert ca.host.port == 12345


def test_span_kind(tracer):
    span = tracer.start_span(operation_name='x')

    span.set_tag(ext_tags.SPAN_KIND, ext_tags.SPAN_KIND_RPC_SERVER)
    assert span.kind == ext_tags.SPAN_KIND_RPC_SERVER
    assert len([e for e in span.tags if e.key == 'span.kind']) == 0

    span.set_tag(ext_tags.SPAN_KIND, ext_tags.SPAN_KIND_RPC_CLIENT)
    assert span.kind == ext_tags.SPAN_KIND_RPC_CLIENT
    assert len([e for e in span.tags if e.key == 'span.kind']) == 0

    span.set_tag(ext_tags.SPAN_KIND, 'garbage')
    assert len([e for e in span.tags if e.key == 'span.kind']) == 1


def test_span_component(tracer):
    span = tracer.start_span(operation_name='x')
    assert span.component is None

    span.set_tag(ext_tags.COMPONENT, 'crypt')
    assert span.component == 'crypt'
