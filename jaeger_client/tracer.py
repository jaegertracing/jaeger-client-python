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

import copy
import os
import time
import logging
import random
import opentracing
from opentracing import Format, UnsupportedFormatException
from tchannel.net import local_ip

from .constants import MAX_ID_BITS
from .codecs import TextCodec
from .span import Span, SAMPLED_FLAG
from .reporter import LocalAgentReporter
from .sampler import LocalAgentControlledSampler
from .version import __version__
from .thrift import ipv4_to_int
from .metrics import Metrics

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
        }

    @staticmethod
    def default_tracer(channel, service_name, reporter=None, sampler=None,
                       metrics=None):
        """Instantiate Tracer with default reporter and sampler, unless
        alternatives are provided.

        Default reporter submits traces over UDP to local agent.
        Default sampler polls local agent for sampling strategy.

        Normal clients (i.e. production code) should not be overriding reporter
        and sampler.

        :param channel: either TChannel or LocalAgentSender
        :param service_name: canonical name of this service, unique but low
            cardinality, i.e. do not include PID or host name or port
            number, just the string name.
        :param reporter: Jaeger Reporter, normally should be left to default
        :param sampler: Jaeger Reporter, normally should be left to default
        :param metrics:
        :return: Jaeger Tracer
        """
        if reporter is None:
            reporter = LocalAgentReporter(channel=channel)
        if sampler is None:
            sampler = LocalAgentControlledSampler(channel=channel,
                                                  service_name=service_name)
        return Tracer(service_name=service_name, reporter=reporter,
                      sampler=sampler, metrics=metrics)

    def start_span(self,
                   operation_name=None,
                   parent=None,
                   tags=None,
                   start_time=None):
        """
        Start and return a new Span representing a unit of work.

        :param operation_name: name of the operation represented by the new
            span from the perspective of the current service.
        :param parent: an optional parent Span. If specified, the returned Span
            will be a child of `parent` in `parent`'s trace. If unspecified,
            the returned Span will be the root of its own trace.
        :param tags: optional dictionary of Span Tags. The caller gives up
            ownership of that dictionary, because the Tracer may use it as-is
            to avoid extra data copying.
        :param start_time: an explicit Span start time as a unix timestamp per
            time.time()

        :return: Returns an already-started Span instance.
        """
        if parent is None:
            trace_id = self.random_id()
            span_id = trace_id
            parent_id = None
            flags = SAMPLED_FLAG if self.sampler.is_sampled(trace_id) else 0
            baggage = {}
        else:
            with parent.update_lock:
                trace_id = parent.trace_id
                span_id = self.random_id()
                parent_id = parent.span_id
                flags = parent.flags
                baggage = copy.deepcopy(parent.baggage)

        span = Span(trace_id=trace_id, span_id=span_id,
                    parent_id=parent_id, flags=flags,
                    tracer=self, operation_name=operation_name,
                    tags=tags, baggage=baggage, start_time=start_time)

        return self.start_span_internal(span=span, join=False)

    def inject(self, span, format, carrier):
        codec = self.codecs.get(format, None)
        if codec is None:
            raise UnsupportedFormatException(format)
        codec.inject(span=span, carrier=carrier)

    def join(self, operation_name, format, carrier):
        codec = self.codecs.get(format, None)
        if codec is None:
            raise UnsupportedFormatException(format)
        trace_id, span_id, parent_id, flags, baggage = codec.extract(carrier)
        if trace_id is None:
            return None
        span = Span(trace_id=trace_id, span_id=span_id,
                    parent_id=parent_id, flags=flags,
                    tracer=self, operation_name=operation_name,
                    baggage=baggage)
        return self.start_span_internal(span=span, join=True)

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
        span.set_tag(key='jaegerClient', value='Python-%s' % __version__)
        if not span.parent_id:
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
