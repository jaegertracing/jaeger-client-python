# Copyright (c) 2016 Uber Technologies, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import absolute_import

import socket

import logging
import os
import random
import time
import six
import opentracing
from opentracing import Format, UnsupportedFormatException
from opentracing.ext import tags as ext_tags

from . import constants
from .codecs import TextCodec, ZipkinCodec, ZipkinSpanFormat, BinaryCodec
from .span import Span, SAMPLED_FLAG, DEBUG_FLAG
from .span_context import SpanContext
from .thrift import ipv4_to_int
from .metrics import Metrics, LegacyMetricsFactory
from .utils import local_ip

logger = logging.getLogger('jaeger_tracing')


class Tracer(opentracing.Tracer):
    """
    N.B. metrics has been deprecated, use metrics_factory instead.
    """
    def __init__(
        self, service_name, reporter, sampler, metrics=None,
        metrics_factory=None,
        trace_id_header=constants.TRACE_ID_HEADER,
        baggage_header_prefix=constants.BAGGAGE_HEADER_PREFIX,
        debug_id_header=constants.DEBUG_ID_HEADER_KEY,
        one_span_per_rpc=False, extra_codecs=None,
        tags=None,
        max_tag_value_length=constants.MAX_TAG_VALUE_LENGTH,
    ):
        self.service_name = service_name
        self.reporter = reporter
        self.sampler = sampler
        self.ip_address = ipv4_to_int(local_ip())
        self.metrics_factory = metrics_factory or LegacyMetricsFactory(metrics or Metrics())
        self.metrics = TracerMetrics(self.metrics_factory)
        self.random = random.Random(time.time() * (os.getpid() or 1))
        self.debug_id_header = debug_id_header
        self.one_span_per_rpc = one_span_per_rpc
        self.max_tag_value_length = max_tag_value_length
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
        if extra_codecs:
            self.codecs.update(extra_codecs)
        self.tags = {
            constants.JAEGER_VERSION_TAG_KEY: constants.JAEGER_CLIENT_VERSION,
            constants.JAEGER_IP_TAG_KEY: self.ip_address,
        }
        if tags:
            self.tags.update(tags)
        # noinspection PyBroadException
        try:
            hostname = socket.gethostname()
            self.tags[constants.JAEGER_HOSTNAME_TAG_KEY] = hostname
        except:
            logger.exception('Unable to determine host name')

        self.reporter.set_process(
            service_name=self.service_name,
            tags=self.tags,
            max_length=self.max_tag_value_length,
        )

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
                sampled, sampler_tags = \
                    self.sampler.is_sampled(trace_id, operation_name)
                if sampled:
                    flags = SAMPLED_FLAG
                    tags = tags or {}
                    for k, v in six.iteritems(sampler_tags):
                        tags[k] = v
            else:  # have debug id
                flags = SAMPLED_FLAG | DEBUG_FLAG
                tags = tags or {}
                tags[self.debug_id_header] = parent.debug_id
        else:
            trace_id = parent.trace_id
            if rpc_server and self.one_span_per_rpc:
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

        :return: Returns a tornado.concurrent.Future that indicates if the
            flush has been completed.
        """
        self.sampler.close()
        return self.reporter.close()

    def _emit_span_metrics(self, span, join=False):
        if span.is_sampled():
            self.metrics.spans_started_sampled(1)
        else:
            self.metrics.spans_started_not_sampled(1)
        if not span.context.parent_id:
            if span.is_sampled():
                if join:
                    self.metrics.traces_joined_sampled(1)
                else:
                    self.metrics.traces_started_sampled(1)
            else:
                if join:
                    self.metrics.traces_joined_not_sampled(1)
                else:
                    self.metrics.traces_started_not_sampled(1)
        return span

    def report_span(self, span):
        self.reporter.report_span(span)
        self.metrics.spans_finished(1)

    def random_id(self):
        return self.random.getrandbits(constants.MAX_ID_BITS)


class TracerMetrics(object):
    """Tracer specific metrics."""

    def __init__(self, metrics_factory):
        self.traces_started_sampled = \
            metrics_factory.create_counter(name='jaeger:traces',
                                           tags={'state': 'started', 'sampled': 'y'})
        self.traces_started_not_sampled = \
            metrics_factory.create_counter(name='jaeger:traces',
                                           tags={'state': 'started', 'sampled': 'n'})
        self.traces_joined_sampled = \
            metrics_factory.create_counter(name='jaeger:traces',
                                           tags={'state': 'joined', 'sampled': 'y'})
        self.traces_joined_not_sampled = \
            metrics_factory.create_counter(name='jaeger:traces',
                                           tags={'state': 'joined', 'sampled': 'n'})
        self.spans_started_sampled = \
            metrics_factory.create_counter(name='jaeger:started_spans', tags={'sampled': 'y'})
        self.spans_started_not_sampled = \
            metrics_factory.create_counter(name='jaeger:started_spans', tags={'sampled': 'n'})
        self.spans_finished = \
            metrics_factory.create_counter(name='jaeger:finished_spans')
