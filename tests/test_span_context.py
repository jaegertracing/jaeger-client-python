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

from jaeger_client import SpanContext


def test_parent_id_to_none():
    ctx1 = SpanContext(trace_id=1, span_id=2, parent_id=0, flags=1)
    assert ctx1.parent_id is None

def test_with_baggage_items():
    baggage1 = {'x': 'y'}
    ctx1 = SpanContext(trace_id=1, span_id=2, parent_id=3, flags=1,
                       baggage=baggage1)
    ctx2 = ctx1.with_baggage_item('a', 'b')
    assert ctx1.trace_id == ctx2.trace_id
    assert ctx1.span_id == ctx2.span_id
    assert ctx1.parent_id == ctx2.parent_id
    assert ctx1.flags == ctx2.flags
    assert ctx1.baggage != ctx2.baggage
    baggage1['a'] = 'b'
    assert ctx1.baggage == ctx2.baggage


def test_is_debug_id_container_only():
    ctx = SpanContext.with_debug_id('value1')
    assert ctx.is_debug_id_container_only
    assert ctx.debug_id == 'value1'
    ctx = SpanContext(trace_id=1, span_id=2, parent_id=3, flags=1)
    assert not ctx.is_debug_id_container_only
