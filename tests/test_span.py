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

from opentracing.ext import tags as ext_tags
from jaeger_client import Span, ConstSampler
from jaeger_client.thrift import add_zipkin_annotations


def test_baggage():
    span = Span(trace_id=1, span_id=2, parent_id=None, flags=1,
                operation_name='x', tracer=None)
    assert span.get_baggage_item('x') is None
    span.set_baggage_item('x', 'y').\
        set_baggage_item('z', 'why')
    assert span.get_baggage_item('x') == 'y'
    assert span.get_baggage_item('z') == 'why'
    assert span.get_baggage_item('tt') is None
    assert len(span.baggage) == 2
    span.set_baggage_item('x', 'b')  # override
    assert span.get_baggage_item('x') == 'b'
    assert len(span.baggage) == 2
    span.set_baggage_item('X_y', '123')
    assert span.get_baggage_item('x-Y') == '123'


def test_sampling_priority(tracer):
    tracer.sampler = ConstSampler(False)
    span = tracer.start_span(operation_name='x')
    assert span.is_sampled() is False
    span.set_tag(ext_tags.SAMPLING_PRIORITY, 1)
    assert span.is_sampled()
    assert span.is_debug()
    span.set_tag(ext_tags.SAMPLING_PRIORITY, 0)
    assert span.is_sampled() is False


def test_info_error(tracer):
    span = tracer.start_span(operation_name='x')
    span.info('event1', 'data1')
    span.error('event2', 'data2')
    assert len([e for e in span.logs if e.value == 'event1']) == 1, 'event1'
    assert len([e for e in span.logs if e.value == 'event2']) == 1, 'event2'
    assert len([e for e in span.tags if e.value == 'data1']) == 1, 'data1'
    assert len([e for e in span.tags if e.value == 'data2']) == 1, 'data2'
    assert len([e for e in span.tags if e.key == 'error']) == 1, 'error'


def test_span_to_string(tracer):
    tracer.service_name = 'unittest'
    span = Span(trace_id=1, span_id=1, parent_id=1, flags=1,
                operation_name='crypt', tracer=tracer)
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
