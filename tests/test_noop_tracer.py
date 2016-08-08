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

import opentracing
from opentracing import Tracer, Format


def test_new_trace():
    tracer = Tracer()

    span = tracer.start_span(operation_name='test')
    span.set_baggage_item('Fry', 'Leela')
    span.set_tag('x', 'y')
    span.log_event('z')

    child = tracer.start_span(operation_name='child',
                              references=opentracing.child_of(span.context))
    child.log_event('w')
    assert child.get_baggage_item('Fry') is None
    carrier = {}
    tracer.inject(
        span_context=child.context, format=Format.TEXT_MAP, carrier=carrier)
    assert carrier == dict()
    child.finish()

    span.finish()


def test_join_trace():
    tracer = Tracer()

    span_ctx = tracer.extract(format=Format.TEXT_MAP, carrier={})
    span = tracer.start_span(operation_name='test',
                             references=opentracing.child_of(span_ctx))
    span.set_tag('x', 'y')
    span.set_baggage_item('a', 'b')
    span.log_event('z')

    child = tracer.start_span(operation_name='child',
                              references=opentracing.child_of(span.context))
    child.log_event('w')
    child.finish()

    span.finish()
