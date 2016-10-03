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

import json
import threading
import time

import opentracing
from opentracing.ext import tags as ext_tags
from . import codecs, thrift

SAMPLED_FLAG = 0x01
DEBUG_FLAG = 0x02


class Span(opentracing.Span):
    """Implements opentracing.Span with Zipkin semantics."""

    __slots__ = ['_tracer', '_context',
                 'operation_name', 'start_time', 'end_time', 'kind',
                 'peer', 'component', 'logs', 'tags', 'update_lock']

    def __init__(self, context, tracer, operation_name,
                 tags=None, start_time=None):
        super(Span, self).__init__(context=context, tracer=tracer)
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

    def info(self, message, payload=None):
        """DEPRECATED"""
        if payload:
            self.log(event=message, payload=payload)
        else:
            self.log(event=message)
        return self

    def error(self, message, payload=None):
        """DEPRECATED"""
        self.set_tag('error', True)
        if payload:
            self.log(event=message, payload=payload)
        else:
            self.log(event=message)
        return self

    def log_kv(self, key_values, timestamp=None):
        if self.is_sampled():
            timestamp = timestamp if timestamp else time.time()
            event = key_values.get('event', None)
            if event and len(key_values) == 1:
                log = thrift.make_event(timestamp=timestamp, name=event)
            else:
                # Since Zipkin format does not support kv-logs,
                # we convert key_values to JSON.
                # TODO handle exception logging, 'python.exception.type' etc.
                value = json.dumps(
                    key_values,
                    default=lambda x: '%s' % (x,)  # avoid exceptions
                )
                log = thrift.make_event(timestamp=timestamp, name=value)
            with self.update_lock:
                self.logs.append(log)
        return self

    def set_baggage_item(self, key, value):
        new_context = self.context.with_baggage_item(key=key, value=value)
        with self.update_lock:
            self._context = new_context
        return self

    def get_baggage_item(self, key):
        return self.context.baggage.get(key)

    def is_sampled(self):
        return self.context.flags & SAMPLED_FLAG == SAMPLED_FLAG

    def is_debug(self):
        return self.context.flags & DEBUG_FLAG == DEBUG_FLAG

    def is_rpc(self):
        return self.kind == ext_tags.SPAN_KIND_RPC_CLIENT or \
            self.kind == ext_tags.SPAN_KIND_RPC_SERVER

    def is_rpc_client(self):
        return self.kind == ext_tags.SPAN_KIND_RPC_CLIENT

    @property
    def trace_id(self):
        return self.context.trace_id

    @property
    def span_id(self):
        return self.context.span_id

    @property
    def parent_id(self):
        return self.context.parent_id

    @property
    def flags(self):
        return self.context.flags

    def __repr__(self):
        c = codecs.span_context_to_string(
            trace_id=self.context.trace_id, span_id=self.context.span_id,
            parent_id=self.context.parent_id, flags=self.context.flags)
        return '%s %s.%s' % (c, self.tracer.service_name, self.operation_name)


def _set_sampling_priority(span, value):
    with span.update_lock:
        if value > 0:
            span.context.flags |= SAMPLED_FLAG | DEBUG_FLAG
        else:
            span.context.flags &= ~SAMPLED_FLAG
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
