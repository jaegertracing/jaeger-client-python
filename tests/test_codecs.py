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

import unittest
from collections import namedtuple

import mock
import pytest
from jaeger_client import Span, SpanContext, Tracer, ConstSampler
from jaeger_client.codecs import (
    Codec, TextCodec, BinaryCodec, ZipkinCodec, ZipkinSpanFormat,
    span_context_from_string,
    span_context_to_string,
)
from jaeger_client.config import Config
from jaeger_client.reporter import InMemoryReporter
from opentracing import Format
from opentracing.propagation import (
    InvalidCarrierException,
    SpanContextCorruptedException,
)


class TestCodecs(unittest.TestCase):
    def test_abstract_codec(self):
        codec = Codec()
        with self.assertRaises(NotImplementedError):
            codec.inject({}, {})
        with self.assertRaises(NotImplementedError):
            codec.extract({})

    def test_wrong_carrier(self):
        codec = TextCodec()
        with self.assertRaises(InvalidCarrierException):
            codec.inject(span_context={}, carrier=[])  # array is no good
        with self.assertRaises(InvalidCarrierException):
            codec.extract(carrier=[])

    def test_trace_context_from_bad_string(self):
        tests = [
            (123.321, 'not a string'),
            ('bad value', 'bad string'),
            ('1:1:1:1:1', 'Too many colons'),
            ('1:1:1', 'Too few colons'),
            ('x:1:1:1', 'Not all numbers'),
            ('1:x:1:1', 'Not all numbers'),
            ('1:1:x:1', 'Not all numbers'),
            ('1:1:1:x', 'Not all numbers'),
            ('0:1:1:1', 'Trace ID cannot be zero'),
            ('1:0:1:1', 'Span ID cannot be zero'),
            ('1:1:-1:1', 'Parent ID cannot be negative'),
            ('1:1::1', 'Parent ID is missing'),
            ('1:1:1:-1', 'Flags cannot be negative'),
        ]

        for test in tests:
            try:
                val = span_context_from_string(test[0])
            except SpanContextCorruptedException:
                val = None
            self.assertEqual(val, None, test[1])

    def test_trace_context_from_to_string(self):
        to_string = span_context_to_string
        from_string = span_context_from_string

        tests = [
            [(256L, 127L, None, 1), '100:7f:0:1'],
            [(256L, 127L, 256L, 0), '100:7f:100:0'],
        ]
        for test in tests:
            ctx = test[0]
            value = to_string(*ctx)
            self.assertEqual(value, test[1])
            ctx_rev = from_string(value)
            self.assertEqual(ctx_rev, ctx)

        ctx_rev = from_string(['100:7f:100:0'])
        assert ctx_rev == (256L, 127L, 256L, 0), 'Array is acceptable'

        with self.assertRaises(SpanContextCorruptedException):
            from_string(['100:7f:100:0', 'garbage'])

        ctx_rev = from_string(u'100:7f:100:0')
        assert ctx_rev == (256L, 127L, 256L, 0), 'Unicode is acceptable'

    def test_context_to_readable_headers(self):
        for url_encoding in [False, True]:
            codec = TextCodec(
                url_encoding=url_encoding,
                trace_id_header='Trace_ID',
                baggage_header_prefix='Trace-Attr-')
            ctx = SpanContext(
                trace_id=256, span_id=127, parent_id=None, flags=1
            )
            carrier = {}
            codec.inject(ctx, carrier)
            assert carrier == {'trace-id': '100:7f:0:1'}

            ctx._baggage = {
                'fry': 'Leela',
                'bender': 'Countess de la Roca',
            }
            carrier = {}
            codec.inject(ctx, carrier)
            if url_encoding:
                assert carrier == {
                    'trace-id': '100:7f:0:1',
                    'trace-attr-bender': 'Countess%20de%20la%20Roca',
                    'trace-attr-fry': 'Leela'}
            else:
                assert carrier == {
                    'trace-id': '100:7f:0:1',
                    'trace-attr-bender': 'Countess de la Roca',
                    'trace-attr-fry': 'Leela'}

    def test_context_from_bad_readable_headers(self):
        codec = TextCodec(trace_id_header='Trace_ID',
                          baggage_header_prefix='Trace-Attr-')

        ctx = codec.extract(dict())
        assert ctx is None, 'No headers'

        bad_headers = {
            '_Trace_ID': '100:7f:0:1',
            '_trace-attr-Kiff': 'Amy'
        }
        ctx = codec.extract(bad_headers)
        assert ctx is None, 'Bad header names'

        with self.assertRaises(InvalidCarrierException):
            codec.extract(carrier=[])  # not a dict

        good_headers_bad_values = {
            'Trace-ID': '100:7f:0:1xxx',
            'trace-attr-Kiff': 'Amy'
        }
        with self.assertRaises(SpanContextCorruptedException):
            codec.extract(good_headers_bad_values)

    def test_context_from_readable_headers(self):
        # provide headers all the way through Config object
        config = Config(
            service_name='test',
            config={
                'trace_id_header': 'Trace_ID',
                'baggage_header_prefix': 'Trace-Attr-',
            })
        tracer = config.create_tracer(
            reporter=InMemoryReporter(),
            sampler=ConstSampler(True),
        )
        for url_encoding in [False, True]:
            if url_encoding:
                codec = tracer.codecs[Format.HTTP_HEADERS]
                headers = {
                    'Trace-ID': '100%3A7f:0:1',
                    'trace-attr-Kiff': 'Amy%20Wang',
                    'trace-atTR-HERMES': 'LaBarbara%20Hermes'
                }
            else:
                codec = tracer.codecs[Format.HTTP_HEADERS]
                headers = {
                    'Trace-ID': '100:7f:0:1',
                    'trace-attr-Kiff': 'Amy Wang',
                    'trace-atTR-HERMES': 'LaBarbara Hermes'
                }
            ctx = codec.extract(headers)
            assert ctx.trace_id == 256
            assert ctx.span_id == 127
            assert ctx.parent_id is None
            assert ctx.flags == 1
            assert ctx.baggage == {
                'kiff': 'Amy Wang',
                'hermes': 'LaBarbara Hermes',
            }

    def test_baggage_without_trace_id(self):
        codec = TextCodec(trace_id_header='Trace_ID',
                          baggage_header_prefix='Trace-Attr-')
        headers = {
            'Trace-ID': '0:7f:0:1',  # trace_id = 0 is invalid
            'trace-attr-Kiff': 'Amy',
            'trace-atTR-HERMES': 'LaBarbara'
        }
        with mock.patch('jaeger_client.codecs.span_context_from_string') as \
                from_str:
            from_str.return_value = (0, 1, 1, 1)
            with self.assertRaises(SpanContextCorruptedException):
                codec.extract(headers)

    def test_context_from_large_ids(self):
        codec = TextCodec(trace_id_header='Trace_ID',
                          baggage_header_prefix='Trace-Attr-')
        headers = {
            'Trace-ID': 'FFFFFFFFFFFFFFFF:FFFFFFFFFFFFFFFF:FFFFFFFFFFFFFFFF:1',
        }
        context = codec.extract(headers)
        assert context.trace_id == 0xFFFFFFFFFFFFFFFFL
        assert context.trace_id == (1L << 64) - 1
        assert context.trace_id > 0
        assert context.span_id == 0xFFFFFFFFFFFFFFFFL
        assert context.span_id == (1L << 64) - 1
        assert context.span_id > 0
        assert context.parent_id == 0xFFFFFFFFFFFFFFFFL
        assert context.parent_id == (1L << 64) - 1
        assert context.parent_id > 0

    def test_zipkin_codec_extract(self):
        codec = ZipkinCodec()

        t = namedtuple('Tracing', 'span_id parent_id trace_id traceflags')
        carrier = t(span_id=1, parent_id=2, trace_id=3, traceflags=1)
        context = codec.extract(carrier)
        assert 3 == context.trace_id
        assert 2 == context.parent_id
        assert 1 == context.span_id
        assert 1 == context.flags
        assert context.baggage == {}

        t = namedtuple('Tracing', 'something')
        carrier = t(something=1)
        with self.assertRaises(InvalidCarrierException):
            codec.extract(carrier)

        t = namedtuple('Tracing', 'trace_id')
        carrier = t(trace_id=1)
        with self.assertRaises(InvalidCarrierException):
            codec.extract(carrier)

        t = namedtuple('Tracing', 'trace_id span_id')
        carrier = t(trace_id=1, span_id=1)
        with self.assertRaises(InvalidCarrierException):
            codec.extract(carrier)

        t = namedtuple('Tracing', 'trace_id span_id parent_id')
        carrier = t(trace_id=1, span_id=1, parent_id=1)
        with self.assertRaises(InvalidCarrierException):
            codec.extract(carrier)

        carrier = {'span_id': 1, 'parent_id': 2, 'trace_id': 3,
                   'traceflags': 1}
        context = codec.extract(carrier)
        assert 3 == context.trace_id
        assert 2 == context.parent_id
        assert 1 == context.span_id
        assert 1 == context.flags
        assert context.baggage == {}

        carrier['trace_id'] = 0
        assert codec.extract(carrier) is None

    def test_zipkin_codec_inject(self):
        codec = ZipkinCodec()

        with self.assertRaises(InvalidCarrierException):
            codec.inject(span_context=None, carrier=[])

        ctx = SpanContext(trace_id=256, span_id=127, parent_id=None, flags=1)
        span = Span(context=ctx, operation_name='x', tracer=None, start_time=1)
        carrier = {}
        codec.inject(span_context=span, carrier=carrier)
        assert carrier == {'span_id': 127, 'parent_id': None,
                           'trace_id': 256, 'traceflags': 1}

    def test_binary_codec(self):
        codec = BinaryCodec()
        with self.assertRaises(InvalidCarrierException):
            codec.inject({}, {})
        with self.assertRaises(InvalidCarrierException):
            codec.extract({})


@pytest.mark.parametrize('fmt,carrier', [
    (Format.TEXT_MAP, {}),
    (Format.HTTP_HEADERS, {}),
    (ZipkinSpanFormat, {}),
])
def test_round_trip(tracer, fmt, carrier):
    span = tracer.start_span('test-%s' % fmt)
    tracer.inject(span, fmt, carrier)
    context = tracer.extract(fmt, carrier)
    span2 = tracer.start_span('test-%s' % fmt, child_of=context)
    assert span.trace_id == span2.trace_id


def test_debug_id():
    debug_header = 'correlation-id'
    tracer = Tracer(
        service_name='test',
        reporter=InMemoryReporter(),
        sampler=ConstSampler(True),
        debug_id_header=debug_header,
    )
    tracer.codecs[Format.TEXT_MAP] = TextCodec(
        url_encoding=False,
        debug_id_header=debug_header,
    )
    carrier = {debug_header: 'Coraline'}
    context = tracer.extract(Format.TEXT_MAP, carrier)
    assert context.is_debug_id_container_only
    assert context.debug_id == 'Coraline'
    span = tracer.start_span('test', child_of=context)
    assert span.is_debug()
    assert span.is_sampled()
    tags = filter(lambda t: t.key == debug_header, span.tags)
    assert len(tags) == 1
    assert tags[0].value == 'Coraline'
