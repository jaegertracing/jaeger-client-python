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
import logging
import time
import collections

import mock
import pytest
import tornado.gen
import jaeger_client.reporter

from concurrent.futures import Future
from jaeger_client import Span, SpanContext
from jaeger_client.metrics import Metrics
from jaeger_client.utils import ErrorReporter
from tornado.ioloop import IOLoop
from tornado.testing import AsyncTestCase, gen_test
from jaeger_client.reporter import Reporter
from jaeger_client.ioloop_util import future_result


def test_null_reporter():
    reporter = jaeger_client.reporter.NullReporter()
    reporter.report_span({})
    f = reporter.close()
    f.result()


def test_in_memory_reporter():
    reporter = jaeger_client.reporter.InMemoryReporter()
    reporter.report_span({})
    f = reporter.close()
    f.result()
    spans = reporter.get_spans()
    assert [{}] == spans


def test_logging_reporter():
    log_mock = mock.MagicMock()
    reporter = jaeger_client.reporter.LoggingReporter(logger=log_mock)
    reporter.report_span({})
    log_mock.info.assert_called_with('Reporting span %s', {})
    reporter.close().result()


def test_composite_reporter():
    reporter = jaeger_client.reporter.CompositeReporter(
        jaeger_client.reporter.NullReporter(),
        jaeger_client.reporter.LoggingReporter())
    with mock.patch('jaeger_client.reporter.NullReporter.report_span') \
            as null_mock:
        with mock.patch('jaeger_client.reporter.LoggingReporter.report_span') \
                as log_mock:
            reporter.report_span({})
            null_mock.assert_called_with({})
            log_mock.assert_called_with({})
    with mock.patch('jaeger_client.reporter.NullReporter.close') \
            as null_mock:
        with mock.patch('jaeger_client.reporter.LoggingReporter.close') \
                as log_mock:
            from concurrent.futures import Future

            f1 = Future()
            f2 = Future()
            null_mock.return_value = f1
            log_mock.return_value = f2
            f = reporter.close()
            null_mock.assert_called_once()
            log_mock.assert_called_once()
            assert not f.done()
            f1.set_result(True)
            f2.set_result(True)
            assert f.done()


class FakeSender(object):
    """
    Mock the _send() method of the reporter by capturing requests
    and returning incomplete futures that can be completed from
    inside the test.
    """
    def __init__(self):
        self.requests = []
        self.futures = []

    def __call__(self, spans):
        # print('ManualSender called', request)
        self.requests.append(spans)
        fut = Future()
        self.futures.append(fut)
        return fut


class HardErrorReporter(object):
    def error(self, name, count, *args):
        raise ValueError(*args)


FakeTrace = collections.namedtuple(
    'FakeTracer', ['ip_address', 'service_name'])


class FakeMetrics(Metrics):
    def __init__(self):
        super(FakeMetrics, self).__init__(
            count=self._incr_count
        )
        self.counters = {}
        self.gauges = {}

    def _incr_count(self, key, value):
        self.counters[key] = value + self.counters.get(key, 0)


class ReporterTest(AsyncTestCase):
    @pytest.yield_fixture
    def thread_loop(self):
        yield

    def _new_span(self, name):
        tracer = FakeTrace(ip_address='127.0.0.1',
                           service_name='reporter_test')
        ctx = SpanContext(trace_id=1, span_id=1, parent_id=None, flags=1)
        span = Span(context=ctx, tracer=tracer, operation_name=name)
        span.start_time = time.time()
        span.end_time = span.start_time + 0.001  # 1ms
        return span

    def _new_reporter(self, batch_size, flush=None, queue_cap=100):
        reporter = Reporter(channel=mock.MagicMock(),
                            io_loop=IOLoop.current(),
                            batch_size=batch_size,
                            flush_interval=flush,
                            metrics=FakeMetrics(),
                            error_reporter=HardErrorReporter(),
                            queue_capacity=queue_cap)
        sender = FakeSender()
        reporter._send = sender
        return reporter, sender

    @tornado.gen.coroutine
    def _wait_for(self, fn):
        """Wait until fn() returns truth, but not longer than 1 second."""
        start = time.time()
        for i in range(1000):
            if fn():
                return
            yield tornado.gen.sleep(0.001)
        print 'waited for condition %f' % (time.time() - start)

    @gen_test
    def test_submit_batch_size_1(self):
        reporter, sender = self._new_reporter(batch_size=1)
        reporter.report_span(self._new_span('1'))

        yield self._wait_for(lambda: len(sender.futures) > 0)
        assert 1 == len(sender.futures)

        sender.futures[0].set_result(1)
        yield reporter.close()
        assert 1 == len(sender.futures)

        # send after close
        assert Metrics.REPORTER_DROPPED not in reporter.metrics.counters
        reporter.report_span(self._new_span('1'))
        assert 1 == reporter.metrics.counters[Metrics.REPORTER_DROPPED]

    @gen_test
    def test_submit_failure(self):
        reporter, sender = self._new_reporter(batch_size=1)
        reporter.error_reporter = ErrorReporter(
            metrics=reporter.metrics, logger=logging.getLogger())

        assert Metrics.REPORTER_FAILURE not in reporter.metrics.counters

        # simulate exception in send
        reporter._send = mock.MagicMock(side_effect=ValueError())
        reporter.report_span(self._new_span('1'))

        yield self._wait_for(
            lambda: Metrics.REPORTER_FAILURE in reporter.metrics.counters)
        assert 1 == reporter.metrics.counters.get(Metrics.REPORTER_FAILURE)

        # silly test, for code coverage only
        yield reporter._submit([])

    @gen_test
    def test_submit_queue_full_batch_size_1(self):
        reporter, sender = self._new_reporter(batch_size=1, queue_cap=1)
        reporter.report_span(self._new_span('1'))

        yield self._wait_for(lambda: len(sender.futures) > 0)
        assert 1 == len(sender.futures)
        # the consumer is blocked on a future, so won't drain the queue
        reporter.report_span(self._new_span('2'))
        assert Metrics.REPORTER_DROPPED not in reporter.metrics.counters
        reporter.report_span(self._new_span('3'))
        yield self._wait_for(
            lambda: Metrics.REPORTER_DROPPED in reporter.metrics.counters
        )
        assert 1 == reporter.metrics.counters.get(Metrics.REPORTER_DROPPED)
        # let it drain the queue
        sender.futures[0].set_result(1)
        yield self._wait_for(lambda: len(sender.futures) > 1)
        assert 2 == len(sender.futures)

        sender.futures[1].set_result(1)
        yield reporter.close()

    @gen_test
    def test_submit_batch_size_2(self):
        reporter, sender = self._new_reporter(batch_size=2, flush=0.005)
        reporter.report_span(self._new_span('1'))
        yield tornado.gen.sleep(0.001)
        assert 0 == len(sender.futures)

        reporter.report_span(self._new_span('2'))
        yield self._wait_for(lambda: len(sender.futures) > 0)
        assert 1 == len(sender.futures)
        assert 2 == len(sender.requests[0])
        sender.futures[0].set_result(1)

        # 3rd span will not be submitted right away, but after `flush` interval
        reporter.report_span(self._new_span('3'))
        yield tornado.gen.sleep(0.001)
        assert 1 == len(sender.futures)
        yield tornado.gen.sleep(0.001)
        assert 1 == len(sender.futures)
        yield tornado.gen.sleep(0.005)
        assert 2 == len(sender.futures)
        sender.futures[1].set_result(1)

        yield reporter.close()


    @gen_test
    def test_close_drains_queue(self):
        reporter, sender = self._new_reporter(batch_size=1, flush=0.050)
        reporter.report_span(self._new_span('0'))

        yield self._wait_for(lambda: len(sender.futures) > 0)
        assert 1 == len(sender.futures)

        # now that the consumer is blocked on the first future.
        # let's reset Send to actually respond right away
        # and flood the queue with messages
        count = [0]

        def send(_):
            count[0] += 1
            return future_result(True)

        reporter._send = send
        reporter.batch_size = 3
        for i in range(10):
            reporter.report_span(self._new_span('%s' % i))
        assert reporter.queue.qsize() == 10, 'queued 10 spans'

        # now unblock consumer
        sender.futures[0].set_result(1)
        yield self._wait_for(lambda: count[0] > 2)

        assert count[0] == 3, '9 out of 10 spans submitted in 3 batches'
        assert reporter.queue._unfinished_tasks == 1, 'one span still pending'

        yield reporter.close()
        assert reporter.queue.qsize() == 0, 'all spans drained'
        assert count[0] == 4, 'last span submitted in one extrac batch'
