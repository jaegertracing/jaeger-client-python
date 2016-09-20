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

import urllib

from opentracing import (
    InvalidCarrierException,
    SpanContextCorruptedException,
)
from .constants import (
    TRACE_ID_HEADER,
    BAGGAGE_HEADER_PREFIX,
    DEBUG_ID_HEADER_KEY,
)
from .span_context import SpanContext


class Codec(object):
    def inject(self, span_context, carrier):
        raise NotImplementedError()

    def extract(self, carrier):
        raise NotImplementedError()


class TextCodec(Codec):
    def __init__(self,
                 url_encoding=False,
                 trace_id_header=TRACE_ID_HEADER,
                 baggage_header_prefix=BAGGAGE_HEADER_PREFIX,
                 debug_id_header=DEBUG_ID_HEADER_KEY):
        self.url_encoding = url_encoding
        self.trace_id_header = trace_id_header.lower().replace('_', '-')
        self.baggage_prefix = baggage_header_prefix.lower().replace('_', '-')
        self.debug_id_header = debug_id_header.lower().replace('_', '-')
        self.prefix_length = len(baggage_header_prefix)

    def inject(self, span_context, carrier):
        if not isinstance(carrier, dict):
            raise InvalidCarrierException('carrier not a collection')
        # Note: we do not url-encode the trace ID because the ':' separator
        # is not a problem for HTTP header values
        carrier[self.trace_id_header] = span_context_to_string(
            trace_id=span_context.trace_id, span_id=span_context.span_id,
            parent_id=span_context.parent_id, flags=span_context.flags)
        baggage = span_context.baggage
        if baggage:
            for key, value in baggage.iteritems():
                if self.url_encoding:
                    encoded_value = urllib.quote(value)
                else:
                    encoded_value = value
                carrier['%s%s' % (self.baggage_prefix, key)] = encoded_value

    def extract(self, carrier):
        if not hasattr(carrier, 'iteritems'):
            raise InvalidCarrierException('carrier not a collection')
        trace_id, span_id, parent_id, flags = None, None, None, None
        baggage = None
        debug_id = None
        for key, value in carrier.iteritems():
            uc_key = key.lower()
            if uc_key == self.trace_id_header:
                if self.url_encoding:
                    value = urllib.unquote(value)
                trace_id, span_id, parent_id, flags = \
                    span_context_from_string(value)
            elif uc_key.startswith(self.baggage_prefix):
                if self.url_encoding:
                    value = urllib.unquote(value)
                attr_key = key[self.prefix_length:]
                if baggage is None:
                    baggage = {attr_key.lower(): value}
                else:
                    baggage[attr_key.lower()] = value
            elif uc_key == self.debug_id_header:
                if self.url_encoding:
                    value = urllib.unquote(value)
                debug_id = value
        if not trace_id and baggage:
            raise SpanContextCorruptedException('baggage without trace ctx')
        if not trace_id:
            if debug_id is not None:
                return SpanContext.with_debug_id(debug_id=debug_id)
            return None
        return SpanContext(trace_id=trace_id, span_id=span_id,
                           parent_id=parent_id, flags=flags,
                           baggage=baggage)


class BinaryCodec(Codec):
    """
    BinaryCodec is a no-op.

    """
    def inject(self, span_context, carrier):
        if not isinstance(carrier, bytearray):
            raise InvalidCarrierException('carrier not a bytearray')
        pass  # TODO binary encoding not implemented

    def extract(self, carrier):
        if not isinstance(carrier, bytearray):
            raise InvalidCarrierException('carrier not a bytearray')
        # TODO binary encoding not implemented
        return None


def span_context_to_string(trace_id, span_id, parent_id, flags):
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
    return '{:x}:{:x}:{:x}:{:x}'.format(trace_id, span_id, parent_id, flags)


def span_context_from_string(value):
    """
    Decode span ID from a string into a TraceContext.
    Returns None if the string value is malformed.

    :param value: formatted {trace_id}:{span_id}:{parent_id}:{flags}
    """
    if type(value) is list and len(value) > 0:
        # sometimes headers are presented as arrays of values
        if len(value) > 1:
            raise SpanContextCorruptedException(
                'trace context must be a string or array of 1: "%s"' % value)
        value = value[0]
    if not isinstance(value, basestring):
        raise SpanContextCorruptedException(
            'trace context not a string "%s"' % value)
    parts = value.split(':')
    if len(parts) != 4:
        raise SpanContextCorruptedException(
            'malformed trace context "%s"' % value)
    try:
        trace_id = long(parts[0], 16)
        span_id = long(parts[1], 16)
        parent_id = long(parts[2], 16)
        flags = int(parts[3], 16)
        if trace_id < 1 or span_id < 1 or parent_id < 0 or flags < 0:
            raise SpanContextCorruptedException(
                'malformed trace context "%s"' % value)
        if parent_id == 0:
            parent_id = None
        return trace_id, span_id, parent_id, flags
    except ValueError as e:
        raise SpanContextCorruptedException(
            'malformed trace context "%s": %s' % (value, e))


# String constants identifying the interop format.
ZipkinSpanFormat = 'zipkin-span-format'


class ZipkinCodec(Codec):
    """
    ZipkinCodec handles ZipkinSpanFormat, which is an interop format
    used by TChannel.

    """
    def inject(self, span_context, carrier):
        if not isinstance(carrier, dict):
            raise InvalidCarrierException('carrier not a dictionary')
        carrier['trace_id'] = span_context.trace_id
        carrier['span_id'] = span_context.span_id
        carrier['parent_id'] = span_context.parent_id
        carrier['traceflags'] = span_context.flags

    def extract(self, carrier):
        if isinstance(carrier, dict):
            trace_id = carrier.get('trace_id')
            span_id = carrier.get('span_id')
            parent_id = carrier.get('parent_id')
            flags = carrier.get('traceflags')
        else:
            if hasattr(carrier, 'trace_id'):
                trace_id = getattr(carrier, 'trace_id')
            else:
                raise InvalidCarrierException('carrier has no trace_id')
            if hasattr(carrier, 'span_id'):
                span_id = getattr(carrier, 'span_id')
            else:
                raise InvalidCarrierException('carrier has no span_id')
            if hasattr(carrier, 'parent_id'):
                parent_id = getattr(carrier, 'parent_id')
            else:
                raise InvalidCarrierException('carrier has no parent_id')
            if hasattr(carrier, 'traceflags'):
                flags = getattr(carrier, 'traceflags')
            else:
                raise InvalidCarrierException('carrier has no traceflags')
        if not trace_id:
            return None
        return SpanContext(trace_id=trace_id, span_id=span_id,
                           parent_id=parent_id, flags=flags,
                           baggage=None)
