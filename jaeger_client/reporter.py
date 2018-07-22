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

import logging
import threading

import tornado.gen
import tornado.ioloop
import tornado.queues
from tornado.concurrent import Future
from .constants import DEFAULT_FLUSH_INTERVAL
from . import ioloop_util
from .metrics import Metrics, LegacyMetricsFactory
from .senders import UDPSender
from .utils import ErrorReporter


default_logger = logging.getLogger('jaeger_tracing')


class NullReporter(object):
    """Ignores all spans."""
    def report_span(self, span):
        pass

    def set_process(self, service_name, tags, max_length):
        pass

    def close(self):
        fut = Future()
        fut.set_result(True)
        return fut


class InMemoryReporter(NullReporter):
    """Stores spans in memory and returns them via get_spans()."""
    def __init__(self):
        super(InMemoryReporter, self).__init__()
        self.spans = []
        self.lock = threading.Lock()

    def report_span(self, span):
        with self.lock:
            self.spans.append(span)

    def get_spans(self):
        with self.lock:
            return self.spans[:]


class LoggingReporter(NullReporter):
    """Logs all spans."""
    def __init__(self, logger=None):
        self.logger = logger if logger else default_logger

    def report_span(self, span):
        self.logger.info('Reporting span %s', span)


class Reporter(NullReporter):
    """Receives completed spans from Tracer and submits them out of process."""
    def __init__(self, channel, queue_capacity=100, batch_size=10,
                 flush_interval=DEFAULT_FLUSH_INTERVAL, io_loop=None,
                 error_reporter=None, metrics=None, metrics_factory=None,
                 sender=None, **kwargs):
        """
        :param channel: a communication channel to jaeger-agent
        :param sender: senders.Sender subclass implementing send method,
            for sending batch of spans to jaeger.
        :param queue_capacity: how many spans we can hold in memory before
            starting to drop spans
        :param batch_size: how many spans we can submit at once to Collector
        :param flush_interval: how often the auto-flush is called (in seconds)
        :param io_loop: which IOLoop to use. If None, try to get it from
            channel (only works if channel is tchannel.sync)
        :param error_reporter:
        :param metrics: an instance of Metrics class, or None. This parameter
            has been deprecated, please use metrics_factory instead.
        :param metrics_factory: an instance of MetricsFactory class, or None.
        :param kwargs:
            'logger'
        :return:
        """
        from threading import Lock

        # TODO for next major rev: remove channel param in favor of sender
        self._sender = sender or self._create_default_sender(channel)
        self.queue_capacity = queue_capacity
        self.batch_size = batch_size
        self.metrics_factory = metrics_factory or LegacyMetricsFactory(metrics or Metrics())
        self.metrics = ReporterMetrics(self.metrics_factory)
        self.error_reporter = error_reporter or ErrorReporter(Metrics())
        self.logger = kwargs.get('logger', default_logger)

        if queue_capacity < batch_size:
            raise ValueError('Queue capacity cannot be less than batch size')

        self.io_loop = io_loop or self.fetch_io_loop(channel, self._sender)

        if self.io_loop is None:
            self.logger.error('Jaeger Reporter has no IOLoop')
        else:
            self.queue = tornado.queues.Queue(maxsize=queue_capacity)
            self.stop = object()
            self.stopped = False
            self.stop_lock = Lock()
            self.flush_interval = flush_interval or None
            self.io_loop.spawn_callback(self._consume_queue)

    @staticmethod
    def fetch_io_loop(channel, sender):
        if channel:
            return channel.io_loop
        elif sender:
            return sender.io_loop
        return None

    def _create_default_sender(self, channel):
        sender = UDPSender(
            port=channel.reporting_port,
            host=channel.host,
            io_loop=channel.io_loop
        )
        return sender

    def set_process(self, service_name, tags, max_length):
        self._sender.set_process(service_name, tags, max_length)

    def report_span(self, span):
        # We should not be calling `queue.put_nowait()` from random threads,
        # only from the same IOLoop where the queue is consumed (T333431).
        if tornado.ioloop.IOLoop.current(instance=False) == self.io_loop:
            self._report_span_from_ioloop(span)
        else:
            self.io_loop.add_callback(self._report_span_from_ioloop, span)

    def _report_span_from_ioloop(self, span):
        try:
            with self.stop_lock:
                stopped = self.stopped
            if stopped:
                self.metrics.reporter_dropped(1)
            else:
                self.queue.put_nowait(span)
        except tornado.queues.QueueFull:
            self.metrics.reporter_dropped(1)

    @tornado.gen.coroutine
    def _consume_queue(self):
        stopped = False

        while not stopped:
            while self._sender.span_count < self.batch_size:
                try:
                    # using timeout allows periodic flush with smaller packet
                    timeout = self.flush_interval + self.io_loop.time() \
                        if self.flush_interval and self._sender.span_count else None
                    span = yield self.queue.get(timeout=timeout)
                except tornado.gen.TimeoutError:
                    break
                else:
                    if span == self.stop:
                        stopped = True
                        self.queue.task_done()
                        # don't return yet, submit accumulated spans first
                        break
                    else:
                        self._sender.append(span)

            if self._sender.span_count:
                num_spans = self._sender.span_count
                try:
                    yield self._sender.flush()
                except Exception as exc:
                    self.metrics.reporter_failure(num_spans)
                    self.error_reporter.error(exc)
                else:
                    self.metrics.reporter_success(num_spans)

                for _ in range(num_spans):
                    self.queue.task_done()

            self.metrics.reporter_queue_length(self.queue.qsize())
        self.logger.info('Span publisher exited')

    def close(self):
        """
        Ensure that all spans from the queue are submitted.
        Returns Future that will be completed once the queue is empty.
        """
        with self.stop_lock:
            self.stopped = True

        return ioloop_util.submit(self._flush, io_loop=self.io_loop)

    @tornado.gen.coroutine
    def _flush(self):
        yield self.queue.put(self.stop)
        yield self.queue.join()


class ReporterMetrics(object):
    """Reporter specific metrics."""

    def __init__(self, metrics_factory):
        self.reporter_success = \
            metrics_factory.create_counter(name='jaeger:reporter_spans', tags={'result': 'ok'})
        self.reporter_failure = \
            metrics_factory.create_counter(name='jaeger:reporter_spans', tags={'result': 'err'})
        self.reporter_dropped = \
            metrics_factory.create_counter(name='jaeger:reporter_spans', tags={'result': 'dropped'})
        self.reporter_queue_length = \
            metrics_factory.create_gauge(name='jaeger:reporter_queue_length')


class CompositeReporter(NullReporter):
    """Delegates reporting to one or more underlying reporters."""
    def __init__(self, *reporters):
        self.reporters = reporters

    def set_process(self, service_name, tags, max_length):
        for reporter in self.reporters:
            reporter.set_process(service_name, tags, max_length)

    def report_span(self, span):
        for reporter in self.reporters:
            reporter.report_span(span)

    def close(self):
        from threading import Lock
        lock = Lock()
        count = [0]
        future = Future()

        def on_close(_):
            with lock:
                count[0] += 1
                if count[0] == len(self.reporters):
                    future.set_result(True)

        for reporter in self.reporters:
            f = reporter.close()
            f.add_done_callback(on_close)

        return future
