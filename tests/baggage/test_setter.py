# Copyright (c) 2017 Uber Technologies, Inc.
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
import unittest
from jaeger_client.baggage.restriction_manager import BaggageRestrictionManager
from jaeger_client.baggage.setter import BaggageSetter
from jaeger_client.baggage.restriction import Restriction
from jaeger_client.metrics import LegacyMetricsFactory, Metrics
from jaeger_client.span import Span
from jaeger_client.span_context import SpanContext
from jaeger_client.tracer import Tracer
from jaeger_client.reporter import InMemoryReporter
from jaeger_client.sampler import ConstSampler


class BaggageSetterTests(unittest.TestCase):
    def setUp(self):
        self.service = 'test'
        self.tracer = Tracer(service_name=self.service, reporter=InMemoryReporter(), sampler=ConstSampler(True))
        self.span_ctx = SpanContext(trace_id=1, span_id=2, parent_id=None, flags=1)
        self.span = Span(context=self.span_ctx, operation_name='x', tracer=self.tracer)
        self.mgr = BaggageRestrictionManager()
        self.cm = mock.MagicMock()
        self.mf = LegacyMetricsFactory(Metrics(count=self.cm))
        self.setter = BaggageSetter(restriction_manager=self.mgr, metrics_factory=self.mf)

    def test_invalid_baggage(self):
        self.mgr.get_restriction = mock.MagicMock(return_value=Restriction(key_allowed=False, max_value_length=0))

        key = 'key'
        value = 'value'
        new_ctx = self.setter.set_baggage(self.span, key, value)
        assert len(self.span.logs) == 1
        assert self.span.logs[0].value == \
               '{{"value": "{}", "event": "baggage", "key": "{}", "invalid": "true"}}'.format(value, key)
        assert new_ctx.baggage.get(key) is None

        assert self.mgr.get_restriction.call_args == ({'baggage_key':'key', 'service':'test'},)
        assert self.cm.call_args == (('jaeger.baggage-update.result_err', 1),)

    def test_truncated_override_baggage(self):
        key = 'key'
        actual_value = '0123456789'
        expected_value = '01234'

        self.span = Span(context=self.span_ctx.with_baggage_item(key=key, value=actual_value), operation_name='x', tracer=self.tracer)
        self.mgr.get_restriction = mock.MagicMock(return_value=Restriction(key_allowed=True, max_value_length=5))

        new_ctx = self.setter.set_baggage(self.span, key, actual_value)
        assert len(self.span.logs) == 1
        assert self.span.logs[0].value == \
               '{{"override": "true", "value": "{}", "event": "baggage", "key": "{}", "truncated": "true"}}'.format(expected_value, key)
        assert new_ctx.baggage.get(key) == expected_value

        assert self.cm.call_args_list == [(('jaeger.baggage-truncate', 1),),(('jaeger.baggage-update.result_ok', 1),)]

    def test_unsampled_span(self):
        self.span = Span(context=SpanContext(trace_id=1, span_id=2, parent_id=None, flags=0), operation_name='x', tracer=self.tracer)
        self.mgr.get_restriction = mock.MagicMock(return_value=Restriction(key_allowed=True, max_value_length=10))

        key = 'key'
        value = 'value'
        new_ctx = self.setter.set_baggage(self.span, key, value)
        assert len(self.span.logs) == 0, 'if unsampled, baggage should be set but no logs'
        assert new_ctx.baggage.get(key) == value

        assert self.cm.call_args == (('jaeger.baggage-update.result_ok', 1),)
