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
import time

import opentracing
from opentracing.ext import tags as ext_tags
from . import thrift
from . import codecs

SAMPLED_FLAG = 0x01
DEBUG_FLAG = 0x02


class Span(opentracing.Span):
    """Implements opentracing.Span with Zipkin semantics."""
    def __init__(self, trace_id, span_id, parent_id, flags,
                 operation_name, tracer, tags=None, baggage=None,
                 start_time=None):
        super(Span, self).__init__(tracer=tracer)
        self.trace_id = trace_id
        self.span_id = span_id
        self.parent_id = parent_id
        self.flags = flags
        self.operation_name = operation_name
        self.start_time = start_time or time.time()
        self.end_time = None
        self.kind = None  # default to local span, unless RPC kind is set
        self.peer = None
        self.component = None
        self.update_lock = threading.Lock()
        # we store tags and logs as Zipkin native thrift BinaryAnnotation and
        # Annotation structures, to avoid creating intermediate objects
        self.tags = []
        self.logs = []
        self.baggage = baggage
        if tags:
            for k, v in tags.iteritems():
                self.set_tag(k, v)

    def set_operation_name(self, operation_name):
        """
        Set or change the operation name.

        :param operation_name: the new operation name
        :return: Returns the Span itself, for call chaining.
        """
        with self.update_lock:
            self.operation_name = operation_name
        return self

    def finish(self, finish_time=None):
        """Indicate that the work represented by this span has been completed
        or terminated, and is ready to be sent to the Reporter.

        If any tags / logs need to be added to the span, it should be done
        before calling finish(), otherwise they may be ignored.

        :param finish_time: an explicit Span finish timestamp as a unix
            timestamp per time.time()
        """
        if not self.is_sampled():
            return

        self.end_time = finish_time or time.time()  # no locking
        self.tracer.report_span(self)

    def set_tag(self, key, value):
        """
        :param key:
        :param value:
        """
        if key == ext_tags.SAMPLING_PRIORITY:
            _set_sampling_priority(self, value)
        elif self.is_sampled():
            special = SPECIAL_TAGS.get(key, None)
            handled = False
            if special is not None and callable(special):
                handled = special(self, value)
            if not handled:
                tag = thrift.make_string_tag(key, str(value))
                with self.update_lock:
                    self.tags.append(tag)
        return self

    def info(self, message, payload):
        self.log(event=message, is_error=False, payload=payload)
        return self

    def error(self, message, payload):
        self.log(event=message, is_error=True, payload=payload)
        return self

    def log_event(self, event, payload=None):
        self.log(event=event, is_error=False, payload=payload)
        return self

    def log(self, **kwargs):
        """
        Record a generic Log event at an arbitrary timestamp.

        :param timestamp: the log timestamp as a unix timestamp per time.time()
        :param event: an event name as a string
        :param payload: an arbitrary structured payload. Implementations may
            choose to ignore none, some, or all of the payload.
        :return: returns the span itself, for chaining the calls
        """
        if self.is_sampled():
            ts = kwargs.get('timestamp', time.time())
            event = kwargs.get('event', '')
            log = thrift.make_event(ts, event)
            # Since Zipkin format does not support logs with payloads,
            # we convert the payload to a tag with the same name as log.
            # Also, if the log was an error, we add error=true tag.
            payload = kwargs.get('payload', None)
            if payload:
                tag = thrift.make_string_tag(event, str(payload))
            else:
                tag = None
            if kwargs.get('is_error', False):
                err = thrift.make_string_tag('error', 'true')
            else:
                err = None
            with self.update_lock:
                self.logs.append(log)
                if tag:
                    self.tags.append(tag)
                if err:
                    self.tags.append(err)
        return self

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

    def is_sampled(self):
        return self.flags & SAMPLED_FLAG == SAMPLED_FLAG

    def is_debug(self):
        return self.flags & DEBUG_FLAG == DEBUG_FLAG

    def is_rpc(self):
        return self.kind == ext_tags.SPAN_KIND_RPC_CLIENT or \
            self.kind == ext_tags.SPAN_KIND_RPC_SERVER

    def is_rpc_client(self):
        return self.kind == ext_tags.SPAN_KIND_RPC_CLIENT

    def __repr__(self):
        c = codecs.trace_context_to_string(
            trace_id=self.trace_id, span_id=self.span_id,
            parent_id=self.parent_id, flags=self.flags)
        return "%s %s.%s" % (c, self.tracer.service_name, self.operation_name)


def _set_sampling_priority(span, value):
    with span.update_lock:
        if value > 0:
            span.flags |= SAMPLED_FLAG | DEBUG_FLAG
        else:
            span.flags &= ~SAMPLED_FLAG
    return True


def _set_peer_service(span, value):
    with span.update_lock:
        if span.peer is None:
            span.peer = {'service_name': value}
        else:
            span.peer['service_name'] = value
    return True


def _set_peer_host_ipv4(span, value):
    with span.update_lock:
        if span.peer is None:
            span.peer = {'ipv4': value}
        else:
            span.peer['ipv4'] = value
    return True


def _set_peer_port(span, value):
    with span.update_lock:
        if span.peer is None:
            span.peer = {'port': value}
        else:
            span.peer['port'] = value
    return True


def _set_span_kind(span, value):
    with span.update_lock:
        if value is None or value == ext_tags.SPAN_KIND_RPC_CLIENT or \
                value == ext_tags.SPAN_KIND_RPC_SERVER:
            span.kind = value
            return True
    return False


def _set_component(span, value):
    with span.update_lock:
        span.component = value
    return True


def _normalize_baggage_key(key):
    return str(key).lower().replace('_', '-')

# Register handlers for special tags.
# Handler returns True if special tag was processed.
# If handler returns False, the tag should still be added to the Span.
SPECIAL_TAGS = {
    ext_tags.PEER_SERVICE: _set_peer_service,
    ext_tags.PEER_HOST_IPV4: _set_peer_host_ipv4,
    ext_tags.PEER_PORT: _set_peer_port,
    ext_tags.SPAN_KIND: _set_span_kind,
    ext_tags.COMPONENT: _set_component,
}
