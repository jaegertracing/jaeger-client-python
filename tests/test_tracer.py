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

import pytest
import tornado.httputil

from opentracing import Format, child_of
from opentracing.ext import tags as ext_tags
from jaeger_client import ConstSampler, Tracer
from jaeger_client import constants as c
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

    tracer.close()


def test_forced_sampling(tracer):
    tracer.sampler = ConstSampler(False)
    span = tracer.start_span("test2",
                             tags={ext_tags.SAMPLING_PRIORITY: 1})
    assert span.is_sampled()
    assert span.is_debug()


@pytest.mark.parametrize('mode', ['arg', 'ref'])
def test_start_child(tracer, mode):
    root = tracer.start_span("test")
    if mode == 'arg':
        span = tracer.start_span("test", child_of=root.context)
    elif mode == 'ref':
        span = tracer.start_span("test", references=child_of(root.context))
    else:
        raise ValueError('bad mode')
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
    child = tracer.start_span("child", references=child_of(span.context))
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
    child = tracer.start_span("child", references=child_of(span.context))
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


@pytest.mark.parametrize('inject_mode', ['span', 'context'])
def test_serialization(tracer, inject_mode):
    span = tracer.start_span('help')
    carrier = {}
    if inject_mode == 'span':
        injectable = span
    elif inject_mode == 'context':
        injectable = span.context
    else:
        raise ValueError('bad inject_mode')
    tracer.inject(
        span_context=injectable, format=Format.TEXT_MAP, carrier=carrier
    )
    assert len(carrier) > 0
    h_ctx = tornado.httputil.HTTPHeaders(carrier)
    assert 'UBER-TRACE-ID' in h_ctx
    ctx2 = tracer.extract(Format.TEXT_MAP, carrier)
    assert ctx2 is not None
    assert ctx2.trace_id == span.trace_id
    assert ctx2.span_id == span.span_id
    assert ctx2.parent_id == span.parent_id
    assert ctx2.flags == span.flags


def test_serialization_error(tracer):
    span = 'span'
    carrier = {}
    with pytest.raises(ValueError):
        tracer.inject(
            span_context=span, format=Format.TEXT_MAP, carrier=carrier
        )


def test_tracer_tags_hostname():
    reporter = mock.MagicMock()
    sampler = ConstSampler(True)

    with mock.patch('socket.gethostname', return_value='dream-host.com'):
        t = Tracer(service_name='x', reporter=reporter, sampler=sampler)
        assert t.tags.get(c.JAEGER_HOSTNAME_TAG_KEY) == 'dream-host.com'


def test_tracer_tags_no_hostname():
    reporter = mock.MagicMock()
    sampler = ConstSampler(True)

    from jaeger_client.tracer import logger
    with mock.patch.object(logger, 'exception') as mock_log:
        with mock.patch('socket.gethostname',
                        side_effect=['host', ValueError()]):
            Tracer(service_name='x', reporter=reporter, sampler=sampler)
        assert mock_log.call_count == 1


@pytest.mark.parametrize('span_type,expected_tags', [
    ('root', {
        'jaeger.version': c.JAEGER_CLIENT_VERSION,
        'jaeger.hostname': 'dream-host.com',
        'sampler.type': 'const',
        'sampler.param': 'True',
    }),
    ('child', {
        'jaeger.version': None,
        'jaeger.hostname': None,
        'sampler.type': None,
        'sampler.param': None,
    }),
    ('rpc-server', {
        'jaeger.version': c.JAEGER_CLIENT_VERSION,
        'jaeger.hostname': 'dream-host.com',
        'sampler.type': None,
        'sampler.param': None,
    }),
])
def test_tracer_tags_on_root_span(span_type, expected_tags):
    reporter = mock.MagicMock()
    sampler = ConstSampler(True)
    with mock.patch('socket.gethostname', return_value='dream-host.com'):
        tracer = Tracer(service_name='x', reporter=reporter, sampler=sampler)
        span = tracer.start_span(operation_name='root')
        if span_type == 'child':
            span = tracer.start_span('child', child_of=span)
        if span_type == 'rpc-server':
            span = tracer.start_span(
                'child', child_of=span.context,
                tags={ext_tags.SPAN_KIND: ext_tags.SPAN_KIND_RPC_SERVER}
            )
        for key, value in expected_tags.iteritems():
            found_tag = None
            for tag in span.tags:
                if tag.key == key:
                    found_tag = tag
            if value is None:
                assert found_tag is None, 'test (%s)' % span_type
                continue

            assert found_tag is not None, 'test (%s): expecting tag %s' % (
                span_type, key
            )
            assert found_tag.value == value, \
                'test (%s): expecting tag %s=%s' % (span_type, key, value)
