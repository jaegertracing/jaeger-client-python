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

import socket

import os
import time
import logging
import random
import opentracing
from opentracing import Format, UnsupportedFormatException
from opentracing.ext import tags as ext_tags

from . import constants
from .codecs import TextCodec, ZipkinCodec, ZipkinSpanFormat, BinaryCodec
from .span import Span, SAMPLED_FLAG, DEBUG_FLAG
from .span_context import SpanContext
from .thrift import ipv4_to_int
from .metrics import Metrics
from .utils import local_ip

logger = logging.getLogger('jaeger_tracing')


class Tracer(opentracing.Tracer):
    def __init__(self, service_name, reporter, sampler, metrics=None,
                 trace_id_header=constants.TRACE_ID_HEADER,
                 baggage_header_prefix=constants.BAGGAGE_HEADER_PREFIX,
                 debug_id_header=constants.DEBUG_ID_HEADER_KEY):
        self.service_name = service_name
        self.reporter = reporter
        self.sampler = sampler
        self.ip_address = ipv4_to_int(local_ip())
        self.metrics = metrics or Metrics()
        self.random = random.Random(time.time() * (os.getpid() or 1))
        self.debug_id_header = debug_id_header
        self.codecs = {
            Format.TEXT_MAP: TextCodec(
                url_encoding=False,
                trace_id_header=trace_id_header,
                baggage_header_prefix=baggage_header_prefix,
                debug_id_header=debug_id_header,
            ),
            Format.HTTP_HEADERS: TextCodec(
                url_encoding=True,
                trace_id_header=trace_id_header,
                baggage_header_prefix=baggage_header_prefix,
                debug_id_header=debug_id_header,
            ),
            Format.BINARY: BinaryCodec(),
            ZipkinSpanFormat: ZipkinCodec(),
        }
        self.tags = {
            constants.JAEGER_VERSION_TAG_KEY: constants.JAEGER_CLIENT_VERSION,
        }
        # noinspection PyBroadException
        try:
            hostname = socket.gethostname()
            self.tags[constants.JAEGER_HOSTNAME_TAG_KEY] = hostname
        except:
            logger.exception('Unable to determine host name')

    def start_span(self,
                   operation_name=None,
                   child_of=None,
                   references=None,
                   tags=None,
                   start_time=None):
        """
        Start and return a new Span representing a unit of work.

        :param operation_name: name of the operation represented by the new
            span from the perspective of the current service.
        :param child_of: shortcut for 'child_of' reference
        :param references: (optional) either a single Reference object or a
            list of Reference objects that identify one or more parent
            SpanContexts. (See the Reference documentation for detail)
        :param tags: optional dictionary of Span Tags. The caller gives up
            ownership of that dictionary, because the Tracer may use it as-is
            to avoid extra data copying.
        :param start_time: an explicit Span start time as a unix timestamp per
            time.time()

        :return: Returns an already-started Span instance.
        """
        parent = child_of
        if references:
            if isinstance(references, list):
                # TODO only the first reference is currently used
                references = references[0]
            parent = references.referenced_context

        # allow Span to be passed as reference, not just SpanContext
        if isinstance(parent, Span):
            parent = parent.context

        rpc_server = tags and \
            tags.get(ext_tags.SPAN_KIND) == ext_tags.SPAN_KIND_RPC_SERVER

        if parent is None or parent.is_debug_id_container_only:
            trace_id = self.random_id()
            span_id = trace_id
            parent_id = None
            flags = 0
            baggage = None
            if parent is None:
                if self.sampler.is_sampled(trace_id):
                    flags = SAMPLED_FLAG
                    tags = tags or {}
                    for k, v in self.sampler.tags.iteritems():
                        tags[k] = v
            else:  # have debug id
                flags = SAMPLED_FLAG | DEBUG_FLAG
                tags = tags or {}
                tags[self.debug_id_header] = parent.debug_id
        else:
            trace_id = parent.trace_id
            if rpc_server:
                # Zipkin-style one-span-per-RPC
                span_id = parent.span_id
                parent_id = parent.parent_id
            else:
                span_id = self.random_id()
                parent_id = parent.span_id
            flags = parent.flags
            baggage = dict(parent.baggage)

        span_ctx = SpanContext(trace_id=trace_id, span_id=span_id,
                               parent_id=parent_id, flags=flags,
                               baggage=baggage)
        span = Span(context=span_ctx, tracer=self,
                    operation_name=operation_name,
                    tags=tags, start_time=start_time)

        if (rpc_server or not parent_id) and (flags & SAMPLED_FLAG):
            # this is a first-in-process span, and is sampled
            for k, v in self.tags.iteritems():
                span.set_tag(k, v)

        self._emit_span_metrics(span=span, join=rpc_server)

        return span

    def inject(self, span_context, format, carrier):
        codec = self.codecs.get(format, None)
        if codec is None:
            raise UnsupportedFormatException(format)
        if isinstance(span_context, Span):
            # be flexible and allow Span as argument, not only SpanContext
            span_context = span_context.context
        if not isinstance(span_context, SpanContext):
            raise ValueError(
                'Expecting Jaeger SpanContext, not %s', type(span_context))
        codec.inject(span_context=span_context, carrier=carrier)

    def extract(self, format, carrier):
        codec = self.codecs.get(format, None)
        if codec is None:
            raise UnsupportedFormatException(format)
        return codec.extract(carrier)

    def close(self):
        """
        Perform a clean shutdown of the tracer, flushing any traces that
        may be buffered in memory.

        :return: Returns a concurrent.futures.Future that indicates if the
            flush has been completed.
        """
        self.sampler.close()
        return self.reporter.close()

    def _emit_span_metrics(self, span, join=False):
        if span.is_sampled():
            self.metrics.count(Metrics.SPANS_SAMPLED, 1)
        else:
            self.metrics.count(Metrics.SPANS_NOT_SAMPLED, 1)
        if not span.context.parent_id:
            if span.is_sampled():
                if join:
                    self.metrics.count(Metrics.TRACES_JOINED_SAMPLED, 1)
                else:
                    self.metrics.count(Metrics.TRACES_STARTED_SAMPLED, 1)
            else:
                if join:
                    self.metrics.count(Metrics.TRACES_JOINED_NOT_SAMPLED, 1)
                else:
                    self.metrics.count(Metrics.TRACES_STARTED_NOT_SAMPLED, 1)
        return span

    def report_span(self, span):
        self.reporter.report_span(span)

    def random_id(self):
        return self.random.getrandbits(constants.MAX_ID_BITS)
