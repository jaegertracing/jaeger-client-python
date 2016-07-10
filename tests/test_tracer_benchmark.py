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

import time
from opentracing import Tracer as NoopTracer
from jaeger_client.tracer import Tracer
from jaeger_client.reporter import NullReporter
from jaeger_client.sampler import ConstSampler


def _generate_spans(tracer, iterations=1000, sleep=None):
    for i in range(0, iterations):
        span = tracer.start_trace(operation_name='root-span')
        span.finish()
        if sleep is not None:
            t = time.time() + sleep
            while time.time() < t:
                pass


def test_noop_tracer(benchmark):
    tracer = NoopTracer()
    benchmark(_generate_spans, tracer)


def test_no_sampling(benchmark):
    tracer = Tracer.default_tracer(
        channel=None, service_name='benchmark',
        reporter=NullReporter(), sampler=ConstSampler(False))
    benchmark(_generate_spans, tracer)


def test_100pct_sampling(benchmark):
    tracer = Tracer.default_tracer(
        channel=None, service_name='benchmark',
        reporter=NullReporter(), sampler=ConstSampler(True))
    benchmark(_generate_spans, tracer)


def test_100pct_sampling_250mcs(benchmark):
    tracer = Tracer.default_tracer(
        channel=None, service_name='benchmark',
        reporter=NullReporter(), sampler=ConstSampler(True))
    # 250 micros for request execution
    benchmark(_generate_spans, tracer, sleep=0.00025)


def test_all_batched_size10(benchmark):
    from tchannel.sync import TChannel
    ch = TChannel(name='foo')
    f = ch.advertise(routers=["127.0.0.1:21300", "127.0.0.1:21301"])
    f.result()
    tracer = Tracer.default_tracer(ch, service_name='benchmark',
                                   sampler=ConstSampler(True))
    tracer.reporter.batch_size = 10
    # 250 micros for request execution
    benchmark(_generate_spans, tracer, sleep=0.00025)


def test_all_batched_size5(benchmark):
    from tchannel.sync import TChannel
    ch = TChannel(name='foo')
    f = ch.advertise(routers=["127.0.0.1:21300", "127.0.0.1:21301"])
    f.result()
    tracer = Tracer.default_tracer(ch, service_name='benchmark',
                                   sampler=ConstSampler(True))
    tracer.reporter.batch_size = 5
    # 250 micros for request execution
    benchmark(_generate_spans, tracer, sleep=0.00025)


def test_all_not_batched(benchmark):
    from tchannel.sync import TChannel
    ch = TChannel(name='foo')
    f = ch.advertise(routers=["127.0.0.1:21300", "127.0.0.1:21301"])
    f.result()
    tracer = Tracer.default_tracer(ch, service_name='benchmark', sampler=ConstSampler(True))
    tracer.reporter.batch_size = 1
    # 250 micros for request execution
    benchmark(_generate_spans, tracer, sleep=0.00025)
