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

from opentracing import InvalidCarrierException
from opentracing import TraceCorruptedException
from .constants import TRACE_ID_HEADER, BAGGAGE_HEADER_PREFIX


class Codec(object):
    def inject(self, span, carrier):
        raise NotImplementedError()

    def extract(self, carrier):
        raise NotImplementedError()


class TextCodec(Codec):
    def __init__(self,
                 trace_id_header=TRACE_ID_HEADER,
                 baggage_header_prefix=BAGGAGE_HEADER_PREFIX):
        self.trace_id_header = trace_id_header.lower().replace('_', '-')
        self.baggage_prefix = baggage_header_prefix.lower().replace('_', '-')
        self.prefix_length = len(baggage_header_prefix)

    def inject(self, span, carrier):
        if not isinstance(carrier, dict):
            raise InvalidCarrierException('carrier not a collection')
        with span.update_lock:
            carrier[self.trace_id_header] = trace_context_to_string(
                trace_id=span.trace_id, span_id=span.span_id,
                parent_id=span.parent_id, flags=span.flags)
            baggage = span.baggage
            if baggage is not None:
                for key, value in baggage.iteritems():
                    carrier['%s%s' % (self.baggage_prefix, key)] = value

    def extract(self, carrier):
        if not hasattr(carrier, 'iteritems'):
            raise InvalidCarrierException('carrier not a collection')
        trace_id, span_id, parent_id, flags = None, None, None, None
        baggage = None
        for key, value in carrier.iteritems():
            uc_key = key.lower()
            if uc_key == self.trace_id_header:
                trace_id, span_id, parent_id, flags = \
                    trace_context_from_string(value)
            elif uc_key.startswith(self.baggage_prefix):
                attr_key = key[self.prefix_length:]
                if baggage is None:
                    baggage = {attr_key.lower(): value}
                else:
                    baggage[attr_key.lower()] = value
        return trace_id, span_id, parent_id, flags, baggage


def trace_context_to_string(trace_id, span_id, parent_id, flags):
    """
    Serialize span ID to a string
        {trace_id}:{span_id}:{parent_id}:{flags}

    Numbers are encoded as variable-length lower-case hex strings.
    If parent_id is None, it is written as 0.

    :param trace_id:
    :param span_id:
    :param parent_id:
    :param flags:
    """
    parent_id = parent_id or 0L
    return "{:x}:{:x}:{:x}:{:x}".format(trace_id, span_id, parent_id, flags)


def trace_context_from_string(value):
    """
    Decode span ID from a string into a TraceContext.
    Returns None if the string value is malformed.

    :param value: formatted {trace_id}:{span_id}:{parent_id}:{flags}
    """
    if type(value) is list and len(value) > 0:
        # sometimes headers are presented as arrays of values
        if len(value) > 1:
            raise TraceCorruptedException(
                'trace context must be a string or array of 1: "%s"' % value)
        value = value[0]
    if not isinstance(value, basestring):
        raise TraceCorruptedException(
            'trace context not a string "%s"' % value)
    parts = value.split(':')
    if len(parts) != 4:
        raise TraceCorruptedException(
            'malformed trace context "%s"' % value)
    try:
        trace_id = long(parts[0], 16)
        span_id = long(parts[1], 16)
        parent_id = long(parts[2], 16)
        flags = int(parts[3], 16)
        if trace_id < 1 or span_id < 1 or parent_id < 0 or flags < 0:
            raise TraceCorruptedException(
                'malformed trace context "%s"' % value)
        if parent_id == 0:
            parent_id = None
        return trace_id, span_id, parent_id, flags
    except ValueError as e:
        raise TraceCorruptedException(
            'malformed trace context "%s": %s' % (value, e))
