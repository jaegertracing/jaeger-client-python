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

from jaeger_client import Span
from jaeger_client.codecs import TextCodec, Codec
from jaeger_client.codecs import trace_context_from_string
from jaeger_client.codecs import trace_context_to_string
from opentracing.propagation import InvalidCarrierException
from opentracing.propagation import TraceCorruptedException


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
            codec.inject(span={}, carrier=[])  # array is no good
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
                val = trace_context_from_string(test[0])
            except TraceCorruptedException:
                val = None
            self.assertEqual(val, None, test[1])

    def test_trace_context_from_to_string(self):
        to_string = trace_context_to_string
        from_string = trace_context_from_string

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

        with self.assertRaises(TraceCorruptedException):
            from_string(['100:7f:100:0', 'garbage'])

        ctx_rev = from_string(u'100:7f:100:0')
        assert ctx_rev == (256L, 127L, 256L, 0), 'Unicode is acceptable'

    def test_context_to_readable_headers(self):
        codec = TextCodec(trace_id_header='Trace_ID',
                          baggage_header_prefix='Trace-Attr-')
        span = Span(trace_id=256, span_id=127, parent_id=None, flags=1,
                    operation_name='x', tracer=None, start_time=1)
        carrier = {}
        codec.inject(span, carrier)
        assert carrier == {'trace-id': '100:7f:0:1'}

        span.set_baggage_item('Fry', 'Leela')
        span.set_baggage_item('Bender', 'Countess de la Roca')
        carrier = {}
        codec.inject(span, carrier)
        assert carrier == {
            'trace-id': '100:7f:0:1',
            'trace-attr-bender': 'Countess de la Roca',
            'trace-attr-fry': 'Leela'}

    def test_context_from_readable_headers(self):
        codec = TextCodec(trace_id_header='Trace_ID',
                          baggage_header_prefix='Trace-Attr-')

        ctx = codec.extract(dict())
        assert ctx[0] is None, 'No headers'

        bad_headers = {
            '_Trace_ID': '100:7f:0:1',
            '_trace-attr-Kiff': 'Amy'
        }
        ctx = codec.extract(bad_headers)
        assert ctx[0] is None, 'Bad header names'

        with self.assertRaises(InvalidCarrierException):
            codec.extract(carrier=[])  # not a dict

        good_headers_bad_values = {
            'Trace-ID': '100:7f:0:1xxx',
            'trace-attr-Kiff': 'Amy'
        }
        with self.assertRaises(TraceCorruptedException):
            codec.extract(good_headers_bad_values)

        headers = {
            'Trace-ID': '100:7f:0:1',
            'trace-attr-Kiff': 'Amy',
            'trace-atTR-HERMES': 'LaBarbara'
        }
        trace_id, span_id, parent_id, flags, baggage = codec.extract(headers)
        assert trace_id == 256
        assert span_id == 127
        assert parent_id is None
        assert flags == 1
        assert baggage == {'kiff': 'Amy', 'hermes': 'LaBarbara'}

    def test_context_from_large_ids(self):
        codec = TextCodec(trace_id_header='Trace_ID',
                          baggage_header_prefix='Trace-Attr-')
        headers = {
            'Trace-ID': 'FFFFFFFFFFFFFFFF:FFFFFFFFFFFFFFFF:FFFFFFFFFFFFFFFF:1',
        }
        trace_id, span_id, parent_id, flags, baggage = codec.extract(headers)
        assert trace_id == 0xFFFFFFFFFFFFFFFFL
        assert trace_id == (1L << 64) - 1
        assert trace_id > 0
        assert span_id == 0xFFFFFFFFFFFFFFFFL
        assert span_id == (1L << 64) - 1
        assert span_id > 0
        assert parent_id == 0xFFFFFFFFFFFFFFFFL
        assert parent_id == (1L << 64) - 1
        assert parent_id > 0
