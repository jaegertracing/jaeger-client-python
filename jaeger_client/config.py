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

import logging
import threading

import opentracing
from . import Tracer
from .local_agent_net import LocalAgentSender
from .reporter import (
    Reporter,
    CompositeReporter,
    LoggingReporter,
)
from .sampler import (
    ConstSampler,
    ProbabilisticSampler,
    RateLimitingSampler,
    RemoteControlledSampler,
)
from .constants import (
    DEFAULT_SAMPLING_INTERVAL,
    DEFAULT_FLUSH_INTERVAL,
    SAMPLER_TYPE_CONST,
    SAMPLER_TYPE_PROBABILISTIC,
    SAMPLER_TYPE_RATE_LIMITING,
    TRACE_ID_HEADER,
    BAGGAGE_HEADER_PREFIX,
    DEBUG_ID_HEADER_KEY,
)
from .metrics import Metrics
from .utils import get_boolean, ErrorReporter

DEFAULT_REPORTING_PORT = 5775
DEFAULT_SAMPLING_PORT = 5778
LOCAL_AGENT_DEFAULT_ENABLED = True

logger = logging.getLogger('jaeger_tracing')


class Config(object):
    """
    Wraps a YAML configuration section for configuring Jaeger Tracer.

    service_name is required, but can be passed either as constructor
    parameter, or as config property.

    Example:

    .. code-block:: yaml

        enabled: true
        reporter_batch_size: 10
        logging: true
        metrics: true
        sampler:
            type: const
            param: true

    """

    _initialized = False
    _initialized_lock = threading.Lock()

    def __init__(self, config, metrics=None, service_name=None):
        """
        :param metrics: an instance of Metrics class, or None
        :param service_name: default service name.
            Can be overwritten by config['service_name'].
        """
        self.config = config
        if get_boolean(self.config.get('metrics', True), True):
            self._metrics = metrics or Metrics()
        else:
            # if metrics are explicitly disabled, use a dummy
            self._metrics = Metrics()
        self._service_name = config.get('service_name', service_name)
        if self._service_name is None:
            raise ValueError('service_name required in the config or param')

        self._error_reporter = ErrorReporter(
            metrics=self.metrics,
            logger=logger if self.logging else None,
        )

    @property
    def service_name(self):
        return self._service_name

    @property
    def metrics(self):
        return self._metrics

    @property
    def error_reporter(self):
        return self._error_reporter

    @property
    def enabled(self):
        return get_boolean(self.config.get('enabled', True), True)

    @property
    def reporter_batch_size(self):
        return int(self.config.get('reporter_batch_size', 10))

    @property
    def reporter_queue_size(self):
        return int(self.config.get('reporter_queue_size', 100))

    @property
    def logging(self):
        return get_boolean(self.config.get('logging', False), False)

    @property
    def trace_id_header(self):
        """
        :return: Returns the name of the HTTP header used to encode trace ID
        """
        return self.config.get('trace_id_header', TRACE_ID_HEADER)

    @property
    def baggage_header_prefix(self):
        """
        :return: Returns the prefix for HTTP headers used to record baggage
        items
        """
        return self.config.get('baggage_header_prefix', BAGGAGE_HEADER_PREFIX)

    @property
    def debug_id_header(self):
        """
        :return: Returns the name of HTTP header or a TextMap carrier key
        which, if found in the carrier, forces the trace to be sampled as
        "debug" trace. The value of the header is recorded as the tag on the
        root span, so that the trace can be found in the UI using this value
        as a correlation ID.
        """
        return self.config.get('debug_id_header', DEBUG_ID_HEADER_KEY)

    @property
    def sampler(self):
        sampler_config = self.config.get('sampler', {})
        sampler_type = sampler_config.get('type', None)
        sampler_param = sampler_config.get('param', None)
        if not sampler_type:
            return None
        elif sampler_type == SAMPLER_TYPE_CONST:
            return ConstSampler(decision=get_boolean(sampler_param, False))
        elif sampler_type == SAMPLER_TYPE_PROBABILISTIC:
            return ProbabilisticSampler(rate=float(sampler_param))
        elif sampler_type in [SAMPLER_TYPE_RATE_LIMITING, 'rate_limiting']:
            return RateLimitingSampler(
                max_traces_per_second=float(sampler_param))

        raise ValueError('Unknown sampler type %s' % sampler_type)

    @property
    def sampling_refresh_interval(self):
        return self.config.get('sampling_refresh_interval',
                               DEFAULT_SAMPLING_INTERVAL)

    @property
    def reporter_flush_interval(self):
        return self.config.get('reporter_flush_interval',
                               DEFAULT_FLUSH_INTERVAL)

    def local_agent_group(self):
        return self.config.get('local_agent', None)

    @property
    def local_agent_enabled(self):
        # noinspection PyBroadException
        try:
            return get_boolean(self.local_agent_group().get('enabled',
                               LOCAL_AGENT_DEFAULT_ENABLED),
                               LOCAL_AGENT_DEFAULT_ENABLED)
        except:
            return LOCAL_AGENT_DEFAULT_ENABLED

    @property
    def local_agent_sampling_port(self):
        # noinspection PyBroadException
        try:
            return int(self.local_agent_group()['sampling_port'])
        except:
            return DEFAULT_SAMPLING_PORT

    @property
    def local_agent_reporting_port(self):
        # noinspection PyBroadException
        try:
            return int(self.local_agent_group()['reporting_port'])
        except:
            return DEFAULT_REPORTING_PORT

    @staticmethod
    def initialized():
        with Config._initialized_lock:
            return Config._initialized

    def initialize_tracer(self, io_loop=None):
        """
        Initialize Jaeger Tracer based on the passed `jaeger_client.Config`.
        Save it to `opentracing.tracer` global variable.
        Only the first call to this method has any effect.
        """

        with Config._initialized_lock:
            if Config._initialized:
                logger.warn('Jaeger tracer already initialized, skipping')
                return
            Config._initialized = True

        channel = self._create_local_agent_channel(io_loop=io_loop)
        sampler = self.sampler
        if sampler is None:
            sampler = RemoteControlledSampler(
                channel=channel,
                service_name=self.service_name,
                logger=logger,
                metrics=self.metrics,
                error_reporter=self.error_reporter,
                sampling_refresh_interval=self.sampling_refresh_interval)
        logger.info('Using sampler %s', sampler)

        reporter = Reporter(
            channel=channel,
            queue_capacity=self.reporter_queue_size,
            batch_size=self.reporter_batch_size,
            flush_interval=self.reporter_flush_interval,
            logger=logger,
            metrics=self.metrics,
            error_reporter=self.error_reporter)

        if self.logging:
            reporter = CompositeReporter(reporter, LoggingReporter(logger))

        tracer = self.create_tracer(
            reporter=reporter,
            sampler=sampler,
        )

        self._initialize_global_tracer(tracer=tracer)
        return tracer

    def create_tracer(self, reporter, sampler):
        return Tracer(
            service_name=self.service_name,
            reporter=reporter,
            sampler=sampler,
            metrics=self.metrics,
            trace_id_header=self.trace_id_header,
            baggage_header_prefix=self.baggage_header_prefix,
            debug_id_header=self.debug_id_header,
        )

    def _initialize_global_tracer(self, tracer):
        opentracing.tracer = tracer
        logger.info('opentracing.tracer initialized to %s[app_name=%s]',
                    tracer, self.service_name)

    def _create_local_agent_channel(self, io_loop):
        """
        Create an out-of-process channel communicating to local jaeger-agent.
        Spans are submitted as SOCK_DGRAM Thrift, sampling strategy is polled
        via JSON HTTP.

        :param self: instance of Config
        """
        logger.info('Initializing Jaeger Tracer with UDP reporter')
        return LocalAgentSender(
            host='localhost',
            sampling_port=self.local_agent_sampling_port,
            reporting_port=self.local_agent_reporting_port,
            io_loop=io_loop
        )
