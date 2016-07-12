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
import threading

import opentracing


class SpanContext(opentracing.SpanContext):
    __slots__ = ['trace_id', 'span_id', 'parent_id', 'flags',
                 'baggage', 'update_lock']

    """Implements opentracing.SpanContext"""
    def __init__(self, trace_id, span_id, parent_id, flags, baggage=None):
        self.trace_id = trace_id
        self.span_id = span_id
        self.parent_id = parent_id
        self.flags = flags
        self.baggage = baggage
        self.update_lock = threading.Lock()

    def set_baggage_item(self, key, value):
        with self.update_lock:
            if self.baggage is None:
                self.baggage = {}
            self.baggage[_normalize_baggage_key(key)] = str(value)
        return self

    def get_baggage_item(self, key):
        with self.update_lock:
            if self.baggage:
                return self.baggage.get(_normalize_baggage_key(key), None)
            else:
                return None


def _normalize_baggage_key(key):
    return str(key).lower().replace('_', '-')
