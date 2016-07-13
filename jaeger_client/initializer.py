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

import opentracing_instrumentation.config as instrumentation
from . import Tracer, RemoteControlledSampler
from .reporter import Reporter, LoggingReporter, CompositeReporter
from .metrics import Metrics
from .utils import ErrorReporter
from .local_agent_net import LocalAgentSender

logger = logging.getLogger('jaeger_tracing')

_initialized = False
_initialized_lock = threading.RLock()


def initialized():
    global _initialized
    global _initialized_lock
    with _initialized_lock:
        return _initialized


# TODO move this to Uber internal repo
def _init_instrumentation_config(service_name):
    instrumentation.CONFIG.app_name = service_name
    instrumentation.CONFIG.caller_name_headers.append('X-Uber-Source')
    instrumentation.CONFIG.callee_endpoint_headers.append('X-Uber-Endpoint')


def _init_metrics_errors(config):
    metrics = config.metrics or Metrics()
    if config.logging:
        error_reporter = ErrorReporter(metrics=metrics, logger=logger)
    else:
        error_reporter = ErrorReporter(metrics=metrics)

    return metrics, error_reporter


# TODO move this to Config class
def initialize_tracer(config):
    """
    Initialize Jaeger Tracer based on the passed `jaeger_client.Config`.
    Save it to `opentracing.tracer` global variable.

    :param config: instance of Config
    """
    global _initialized
    global _initialized_lock

    with _initialized_lock:
        if _initialized:
            logger.warn('Jaeger tracer has been already initialized, skipping')
            return
        _initialized = True

        _init_instrumentation_config(config.service_name)
        metrics, error_reporter = _init_metrics_errors(config)

        channel = _create_local_agent_channel(config=config)
        sampler = config.sampler
        if sampler is None:
            sampler = RemoteControlledSampler(
                channel=channel,
                service_name=config.service_name,
                logger=logger,
                metrics=metrics,
                error_reporter=error_reporter,
                sampling_refresh_interval=config.sampling_refresh_interval)
        logger.info('Using sampler %s', sampler)

        reporter = Reporter(
            channel=channel,
            queue_capacity=config.reporter_queue_size,
            batch_size=config.reporter_batch_size,
            flush_interval=config.reporter_flush_interval,
            logger=logger,
            metrics=metrics,
            error_reporter=error_reporter)
    if config.logging:
        reporter = CompositeReporter(reporter, LoggingReporter(logger))

    tracer = Tracer(service_name=config.service_name,
                    sampler=sampler, reporter=reporter, metrics=metrics)

    opentracing.tracer = tracer
    logger.info('opentracing.tracer initialized to %s[app_name=%s]',
                tracer, config.service_name)

    config.install_client_hooks()


def _create_local_agent_channel(config):
    """
    Create an out-of-process channel communicating to local jaeger-agent.
    Spans are submitted as SOCK_DGRAM Thrift, sampling strategy is polled
    via JSON HTTP.

    :param config: instance of Config
    """
    logger.info('Initializing Jaeger Tracer with UDP reporter')
    return LocalAgentSender('localhost',
                            config.local_agent_sampling_port,
                            config.local_agent_reporting_port)
