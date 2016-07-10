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
from opentracing_instrumentation import get_current_span
from tchannel import context
from . import Tracer, RemoteControlledSampler, LocalAgentControlledSampler
from .reporter import Reporter, LocalAgentReporter, LoggingReporter, \
    CompositeReporter
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


def instrumentation_config(service_name):
    instrumentation.CONFIG.app_name = service_name
    instrumentation.CONFIG.caller_name_headers.append('X-Uber-Source')
    instrumentation.CONFIG.callee_endpoint_headers.append('X-Uber-Endpoint')


def metrics_errors(config):
    metrics = config.metrics or Metrics()
    if config.logging:
        error_reporter = ErrorReporter(metrics=metrics, logger=logger)
    else:
        error_reporter = ErrorReporter(metrics=metrics)

    return metrics, error_reporter


# Factories for the different types of samplers
class RemoteControlledSamplerFactory(object):
    def __call__(self, *args, **kwargs):
        return RemoteControlledSampler(*args, **kwargs)


class LocalAgentControlledSamplerFactory(object):
    def __call__(self, *args, **kwargs):
        return LocalAgentControlledSampler(*args, **kwargs)


# Factories for the different types of reporters
class TChannelReporterFactory(object):
    def __call__(self, *args, **kwargs):
        return Reporter(*args, **kwargs)


class LocalAgentReporterFactory(object):
    def __call__(self, *args, **kwargs):
        return LocalAgentReporter(*args, **kwargs)


def initialize_tracer(config, channel,
                      sampler_factory=None, reporter_factory=None):
    """
    Initialize Jaeger Tracer based on the passed `jaeger_client.Config`.
    Save it to `opentracing.tracer` global variable.

    :param config: instance of Config
    :param channel: initialized instance of TChannel
    :param sampler_factory:
    :param reporter_factory:
    """
    global _initialized
    global _initialized_lock

    with _initialized_lock:
        if _initialized:
            logger.warn('Jaeger tracer has been already initialized, skipping')
            return

        instrumentation_config(config.service_name)
        metrics, error_reporter = metrics_errors(config)

        sampler = config.sampler
        if sampler is None and sampler_factory is not None:
            sampler = sampler_factory(
                channel=channel,
                service_name=config.service_name,
                logger=logger,
                metrics=metrics,
                error_reporter=error_reporter,
                sampling_refresh_interval=config.sampling_refresh_interval)
        logger.info('Using sampler %s', sampler)

        reporter = reporter_factory(
            channel=channel,
            queue_capacity=config.reporter_queue_size,
            batch_size=config.reporter_batch_size,
            flush_interval=config.reporter_flush_interval,
            logger=logger,
            metrics=metrics,
            error_reporter=error_reporter)
        if config.logging:
            reporter = CompositeReporter(reporter, LoggingReporter(logger))

        tracer = Tracer.default_tracer(channel=channel,
                                       service_name=config.service_name,
                                       sampler=sampler,
                                       reporter=reporter,
                                       metrics=metrics)

        opentracing.tracer = tracer
        logger.info('opentracing.tracer initialized to %s[app_name=%s]',
                    tracer, config.service_name)

        config.install_client_hooks()
        _patch_tchannel_call()

        _initialized = True


def _patch_tchannel_call():
    """
    Monkey-patch TChannel.call() method by extracting current OpenTracing Span
    and running the original method inside request_context(span).
    :return:
    """
    request_context_func = None
    try:
        request_context_func = context.request_context
    except:
        try:  # for tchannel >= 0.25
            provider = context.RequestContextProvider()
            request_context_func = provider.request_context
        except:
            logging.warn(
                'No request_context() function, not patching TChannel'
            )
            return

    import tchannel
    original_func = tchannel.TChannel.call

    def wrapped_call(*args, **kwargs):
        parent_span = get_current_span()
        if parent_span is None:
            return original_func(*args, **kwargs)

        # The reason this works is because TChannel is only looking at
        # trace_id and span_id fields in the object it retrieves from context
        with request_context_func(parent_span):
            return original_func(*args, **kwargs)

    tchannel.TChannel.call = wrapped_call


def initialize_with_local_agent(config, caller='middleware'):
    """
    Initialize with SOCK_DGRAM Thrift to push spans at local-agent

    :param config: instance of Config

    :param caller: name of the caller, used in the logs only.
        This is useful when used from uWSGI workers, to distinguish
        which worker is doing the work.
    """
    logger.info('Initializing Jaeger Tracer with UDP reporter')
    channel = LocalAgentSender('localhost',
                               config.local_agent_sampling_port,
                               config.local_agent_reporting_port)

    initialize_tracer(config=config, channel=channel,
                      sampler_factory=LocalAgentControlledSamplerFactory(),
                      reporter_factory=LocalAgentReporterFactory())
