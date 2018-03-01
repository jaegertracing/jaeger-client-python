# Copyright (c) 2016 Uber Technologies, Inc.
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

import unittest
from collections import namedtuple
import six

import mock
import pytest
from jaeger_client import Span, SpanContext, Tracer, ConstSampler
from jaeger_client.codecs import (
    Codec, TextCodec, BinaryCodec, ZipkinCodec, ZipkinSpanFormat, B3Codec,
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


byte255 = bytes(chr(255)) if six.PY2 else bytes([255])


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
            [(256, 127, None, 1), '100:7f:0:1'],
            [(256, 127, 256, 0), '100:7f:100:0'],
        ]
        for test in tests:
            ctx = test[0]
            value = to_string(*ctx)
            self.assertEqual(value, test[1])
            ctx_rev = from_string(value)
            self.assertEqual(ctx_rev, ctx)

        ctx_rev = from_string(['100:7f:100:0'])
        assert ctx_rev == (256, 127, 256, 0), 'Array is acceptable'

        with self.assertRaises(SpanContextCorruptedException):
            from_string(['100:7f:100:0', 'garbage'])

        ctx_rev = from_string(u'100:7f:100:0')
        assert ctx_rev == (256, 127, 256, 0), 'Unicode is acceptable'

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
                'fry': u'Leela',
                'bender': 'Countess de la Roca',
                b'key1': byte255,
                u'key2-caf\xe9': 'caf\xc3\xa9',
                u'key3': u'caf\xe9',
                'key4-caf\xc3\xa9': 'value',
            }
            carrier = {}
            codec.inject(ctx, carrier)
            # NB: the reverse transformation is not exact, e.g. this fails:
            #   assert ctx._baggage == codec.extract(carrier)._baggage
            # But fully supporting lossless Unicode baggage is not the goal.
            if url_encoding:
                assert carrier == {
                    'trace-id': '100:7f:0:1',
                    'trace-attr-bender': 'Countess%20de%20la%20Roca',
                    'trace-attr-fry': 'Leela',
                    'trace-attr-key1': '%FF',
                    'trace-attr-key2-caf\xc3\xa9': 'caf%C3%A9',
                    'trace-attr-key3': 'caf%C3%A9',
                    'trace-attr-key4-caf\xc3\xa9': 'value',
                }, 'with url_encoding = %s' % url_encoding
                for key, val in six.iteritems(carrier):
                    assert isinstance(key, str)
                    assert isinstance(val, str), '%s' % type(val)
            else:
                assert carrier == {
                    'trace-id': '100:7f:0:1',
                    'trace-attr-bender': 'Countess de la Roca',
                    'trace-attr-fry': 'Leela',
                    'trace-attr-key1': '\xff',
                    u'trace-attr-key2-caf\xe9': 'caf\xc3\xa9',
                    u'trace-attr-key3': u'caf\xe9',
                    'trace-attr-key4-caf\xc3\xa9': 'value',
                }, 'with url_encoding = %s' % url_encoding

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
        assert context.trace_id == 0xFFFFFFFFFFFFFFFF
        assert context.trace_id == (1 << 64) - 1
        assert context.trace_id > 0
        assert context.span_id == 0xFFFFFFFFFFFFFFFF
        assert context.span_id == (1 << 64) - 1
        assert context.span_id > 0
        assert context.parent_id == 0xFFFFFFFFFFFFFFFF
        assert context.parent_id == (1 << 64) - 1
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

    def test_zipkin_b3_codec_inject(self):
        codec = B3Codec()

        with self.assertRaises(InvalidCarrierException):
            codec.inject(span_context=None, carrier=[])

        ctx = SpanContext(trace_id=256, span_id=127, parent_id=None, flags=1)
        span = Span(context=ctx, operation_name='x', tracer=None, start_time=1)
        carrier = {}
        codec.inject(span_context=span, carrier=carrier)
        assert carrier == {'X-B3-SpanId': format(127, 'x').zfill(16),
                           'X-B3-TraceId': format(256, 'x').zfill(16), 'X-B3-Flags': '1'}

    def test_b3_codec_inject_parent(self):
        codec = B3Codec()

        with self.assertRaises(InvalidCarrierException):
            codec.inject(span_context=None, carrier=[])

        ctx = SpanContext(trace_id=256, span_id=127, parent_id=32, flags=1)
        span = Span(context=ctx, operation_name='x', tracer=None, start_time=1)
        carrier = {}
        codec.inject(span_context=span, carrier=carrier)
        assert carrier == {'X-B3-SpanId': format(127, 'x').zfill(16), 'X-B3-ParentSpanId': format(32, 'x').zfill(16),
                           'X-B3-TraceId': format(256, 'x').zfill(16), 'X-B3-Flags': '1'}

    def test_b3_extract(self):
        codec = B3Codec()

        with self.assertRaises(InvalidCarrierException):
            codec.extract([])

        carrier = {'x-b3-spanid': 'a2fb4a1d1a96d312', 'x-b3-parentspanid': '0020000000000001',
                   'x-b3-traceid': '463ac35c9f6413ad48485a3953bb6124', 'x-b3-flags': '1'}

        span_context = codec.extract(carrier)
        assert span_context.span_id == int('a2fb4a1d1a96d312', 16)
        assert span_context.trace_id == int('463ac35c9f6413ad48485a3953bb6124', 16)
        assert span_context.parent_id == int('0020000000000001', 16)
        assert span_context.flags == 0x02

        carrier.update({'x-b3-sampled': '1'})

        span_context = codec.extract(carrier)
        assert span_context.flags == 0x03

        # validate invalid hex string
        with self.assertRaises(SpanContextCorruptedException):
            codec.extract({'x-b3-traceid': 'a2fb4a1d1a96d312z'})

        # validate non-string header
        with self.assertRaises(SpanContextCorruptedException):
            codec.extract({'x-b3-traceid': 123})

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
    tags = [t for t in span.tags if t.key == debug_header]
    assert len(tags) == 1
    assert tags[0].vStr == 'Coraline'


def test_non_ascii_baggage_with_httplib(httpserver):
    # TODO this test requires `futurize`. Unfortunately, that also changes
    # how the test works under Py2.
    # Some observation:
    # - In Py2, the httplib does not like unicode strings, maybe we need to convert everything to bytes.
    # - Not sure yet what's the story with httplib in Py3, it seems not to like raw bytes.
    if six.PY3:
        raise ValueError('this test does not work with Py3')
    # httpserver is provided by pytest-localserver
    httpserver.serve_content(content='Hello', code=200, headers=None)

    tracer = Tracer(
        service_name='test',
        reporter=InMemoryReporter(),
        # don't sample to avoid logging baggage to the span
        sampler=ConstSampler(False),
    )
    tracer.codecs[Format.TEXT_MAP] = TextCodec(url_encoding=True)

    baggage = [
        (b'key', b'value'),
        (u'key', b'value'),
        (b'key', byte255),
        (u'caf\xe9', 'caf\xc3\xa9'),
        ('caf\xc3\xa9', 'value'),
    ]
    for b in baggage:
        span = tracer.start_span('test')
        span.set_baggage_item(b[0], b[1])

        headers = {}
        tracer.inject(
            span_context=span.context, format=Format.TEXT_MAP, carrier=headers
        )
        # make sure httplib doesn't blow up
        import urllib2
        request = urllib2.Request(httpserver.url, None, headers)
        response = urllib2.urlopen(request)
        assert response.read() == b'Hello'
        response.close()
