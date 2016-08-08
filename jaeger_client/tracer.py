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

import os
import time
import logging
import random
import opentracing
from opentracing import Format, UnsupportedFormatException
from opentracing.ext import tags as ext_tags

from .constants import MAX_ID_BITS, JAEGER_CLIENT_VERSION
from .codecs import TextCodec, ZipkinCodec, ZipkinSpanFormat, BinaryCodec
from .span import Span, SAMPLED_FLAG
from .span_context import SpanContext
from .thrift import ipv4_to_int
from .metrics import Metrics
from .utils import local_ip

logger = logging.getLogger('jaeger_tracing')


class Tracer(opentracing.Tracer):
    def __init__(self, service_name, reporter, sampler, metrics=None):
        self.service_name = service_name
        self.reporter = reporter
        self.sampler = sampler
        self.ip_address = ipv4_to_int(local_ip())
        self.metrics = metrics or Metrics()
        self.random = random.Random(time.time() * (os.getpid() or 1))
        self.codecs = {
            Format.TEXT_MAP: TextCodec(),
            Format.HTTP_HEADERS: TextCodec(),  # TODO use some encoding
            Format.BINARY: BinaryCodec(),
            ZipkinSpanFormat: ZipkinCodec(),
        }

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

        if parent is None:
            trace_id = self.random_id()
            span_id = trace_id
            parent_id = None
            flags = SAMPLED_FLAG if self.sampler.is_sampled(trace_id) else 0
            baggage = None
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

        return self.start_span_internal(span=span, join=rpc_server)

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

    def start_span_internal(self, span, join=False):
        span.set_tag(key='jaegerClient', value=JAEGER_CLIENT_VERSION)
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
        if span.is_sampled():
            self.metrics.count(Metrics.SPANS_SAMPLED, 1)
        else:
            self.metrics.count(Metrics.SPANS_NOT_SAMPLED, 1)
        self.reporter.report_span(span)

    def random_id(self):
        return self.random.getrandbits(MAX_ID_BITS)
