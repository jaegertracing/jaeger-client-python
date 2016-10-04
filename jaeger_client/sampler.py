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
import random
import time

from threading import Lock
from tornado.ioloop import PeriodicCallback
from .constants import (
    MAX_ID_BITS,
    DEFAULT_SAMPLING_INTERVAL,
    SAMPLER_TYPE_CONST,
    SAMPLER_TYPE_PROBABILISTIC,
    SAMPLER_TYPE_RATE_LIMITING,
)
from .metrics import Metrics
from .utils import ErrorReporter
from .local_agent_net import parse_sampling_strategy

default_logger = logging.getLogger('jaeger_tracing')

SAMPLER_TYPE_TAG_KEY = 'sampler.type'
SAMPLER_PARAM_TAG_KEY = 'sampler.param'
DEFAULT_SAMPLING_PROBABILITY = 0.001


class Sampler(object):
    """
    Sampler is responsible for deciding if a particular span should be
    "sampled", i.e. recorded in permanent storage.
    """

    def __init__(self, tags=None):
        self._tags = tags

    def is_sampled(self, trace_id):
        raise NotImplementedError()

    def close(self):
        raise NotImplementedError()

    @property
    def tags(self):
        return self._tags

    def __eq__(self, other):
        return (isinstance(other, self.__class__) and
                self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not self.__eq__(other)


class ConstSampler(Sampler):
    """ConstSampler always returns the same decision."""

    def __init__(self, decision):
        super(ConstSampler, self).__init__(
            tags={
                SAMPLER_TYPE_TAG_KEY: SAMPLER_TYPE_CONST,
                SAMPLER_PARAM_TAG_KEY: decision,
            }
        )
        self.decision = decision

    def is_sampled(self, trace_id):
        return self.decision

    def close(self):
        pass

    def __str__(self):
        return 'ConstSampler(%s)' % self.decision


class ProbabilisticSampler(Sampler):
    """
    A sampler that randomly samples a certain percentage of traces specified
    by the samplingRate, in the range between 0.0 and 1.0.

    It relies on the fact that new trace IDs are 64bit random numbers
    themselves, thus making the sampling decision without generating a new
    random number, but simply calculating if traceID < (samplingRate * 2^64).
    Note that we actually ignore (zero out) the most significant bit.
    """

    def __init__(self, rate):
        super(ProbabilisticSampler, self).__init__(
            tags={
                SAMPLER_TYPE_TAG_KEY: SAMPLER_TYPE_PROBABILISTIC,
                SAMPLER_PARAM_TAG_KEY: rate,
            }
        )
        assert 0.0 <= rate <= 1.0, 'Sampling rate must be between 0.0 and 1.0'
        self.rate = rate
        self.max_number = 1 << MAX_ID_BITS
        self.boundary = rate * self.max_number

    def is_sampled(self, trace_id):
        return trace_id < self.boundary

    def close(self):
        pass

    def __str__(self):
        return 'ProbabilisticSampler(%s)' % self.rate


class RateLimitingSampler(Sampler):
    """
    Samples at most max_traces_per_second. The distribution of sampled
    traces follows burstiness of the service, i.e. a service with uniformly
    distributed requests will have those requests sampled uniformly as well,
    but if requests are bursty, especially sub-second, then a number of
    sequential requests can be sampled each second.
    """

    def __init__(self, max_traces_per_second=10):
        super(RateLimitingSampler, self).__init__(
            tags={
                SAMPLER_TYPE_TAG_KEY: SAMPLER_TYPE_RATE_LIMITING,
                SAMPLER_PARAM_TAG_KEY: max_traces_per_second,
            }
        )
        assert max_traces_per_second >= 0, \
            'max_traces_per_second must not be negative'
        self.credits_per_second = max_traces_per_second
        self.balance = max_traces_per_second
        self.last_tick = self.timestamp()
        self.item_cost = 1

    def is_sampled(self, trace_id):
        current_time = self.timestamp()
        elapsed_time = current_time - self.last_tick
        self.last_tick = current_time
        self.balance += elapsed_time * self.credits_per_second
        if self.balance > self.credits_per_second:
            self.balance = self.credits_per_second
        if self.balance >= self.item_cost:
            self.balance -= self.item_cost
            return True
        return False

    def close(self):
        pass

    @staticmethod
    def timestamp():
        return time.time()

    def __eq__(self, other):
        """The last_tick and balance fields can be different"""
        if not isinstance(other, self.__class__):
            return False
        d1 = dict(self.__dict__)
        d2 = dict(other.__dict__)
        d1['balance'] = d2['balance']
        d1['last_tick'] = d2['last_tick']
        return d1 == d2

    def __str__(self):
        return 'RateLimitingSampler(%s)' % self.credits_per_second


class RemoteControlledSampler(Sampler):
    """Periodically loads the sampling strategy from a remote server."""
    def __init__(self, channel, service_name, **kwargs):
        """
        :param channel: channel for communicating with jaeger-agent
        :param service_name: name of this application
        :param kwargs: optional parameters
            - init_sampler: initial value of the sampler,
                else ProbabilisticSampler(0.01)
            - sampling_refresh_interval: interval in seconds for polling
              for new strategy
            - logger:
            - metrics: metrics facade, used to emit metrics on errors
            - error_reporter: ErrorReporter instance
        :param init:
        :return:
        """
        super(RemoteControlledSampler, self).__init__()
        self._channel = channel
        self.service_name = service_name
        self.logger = kwargs.get('logger', default_logger)
        self.sampler = kwargs.get('init_sampler')
        self.sampling_refresh_interval = \
            kwargs.get('sampling_refresh_interval', DEFAULT_SAMPLING_INTERVAL)
        self.metrics = kwargs.get('metrics', None) or Metrics()
        self.error_reporter = kwargs.get('error_reporter') or \
            ErrorReporter(metrics=self.metrics)

        if self.sampler is None:
            self.sampler = ProbabilisticSampler(DEFAULT_SAMPLING_PROBABILITY)
        else:
            self.sampler.is_sampled(0)  # assert we got valid sampler API

        self.lock = Lock()
        self.running = True
        self.periodic = None

        self.io_loop = channel.io_loop
        if not self.io_loop:
            self.logger.error(
                'Cannot acquire IOLoop, sampler will not be updated')
        else:
            # according to IOLoop docs, it's not safe to use timeout methods
            # unless already running in the loop, so we use `add_callback`
            self.io_loop.add_callback(self._init_polling)

    def is_sampled(self, trace_id):
        with self.lock:
            return self.sampler.is_sampled(trace_id)

    @property
    def tags(self):
        with self.lock:
            return self.sampler.tags

    def _init_polling(self):
        """
        Bootstrap polling for sampling strategy.

        To avoid spiky traffic from the samplers, we use a random delay
        before the first poll.
        """
        with self.lock:
            if self.running:
                r = random.Random()
                delay = r.random() * self.sampling_refresh_interval
                self.io_loop.call_later(delay=delay,
                                        callback=self._delayed_polling)
                self.logger.info(
                    'Delaying sampling strategy polling by %d sec', delay)

    def _delayed_polling(self):
        periodic = PeriodicCallback(
            callback=self.poll_sampling_manager,
            # convert interval to milliseconds
            callback_time=self.sampling_refresh_interval * 1000,
            io_loop=self.io_loop)
        self.poll_sampling_manager()  # Initial sample now
        with self.lock:
            if self.running:
                self.periodic = periodic
                periodic.start()  # start the periodic cycle
                self.logger.info(
                    'Tracing sampler started with sampling refresh '
                    'interval %d sec', self.sampling_refresh_interval)

    def poll_sampling_manager(self):

        def submit_callback(future):
            exception = future.exception()
            if exception:
                self.error_reporter.error(
                    Metrics.SAMPLER_ERRORS, 1,
                    'Fail to get sampling strategy from jaeger-agent: %s',
                    exception)
                return

            response = future.result()
            try:
                sampler = parse_sampling_strategy(response.body)
            except Exception as e:
                self.error_reporter.error(
                    Metrics.SAMPLER_ERRORS, 1,
                    'Fail to parse sampling strategy '
                    'from jaeger-agent: %s [%s]', e, response.body)
                return

            with self.lock:
                if self.sampler == sampler:
                    return
                self.sampler = sampler
            self.logger.debug('Tracing sampler set to %s', sampler)

        self.logger.debug('Requesting tracing sampler refresh')
        fut = self._channel.request_sampling_strategy(
            self.service_name, timeout=15)
        fut.add_done_callback(submit_callback)

    def close(self):
        with self.lock:
            self.running = False
            if self.periodic is not None:
                self.periodic.stop()
