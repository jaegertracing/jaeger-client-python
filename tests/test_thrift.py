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

from cStringIO import StringIO

import jaeger_client.thrift_gen.zipkincore.ZipkinCollector as zipkin_collector
import jaeger_client.thrift_gen.sampling.SamplingManager as sampling_manager
from opentracing import child_of
from jaeger_client import ProbabilisticSampler, RateLimitingSampler
from jaeger_client import thrift, Span, SpanContext
from jaeger_client.thrift_gen.agent import Agent as Agent
from thrift.protocol.TCompactProtocol import TCompactProtocol
from thrift.transport.TTransport import TMemoryBuffer


def test_ipv4_to_int():
    base = thrift.ipv4_to_int('127.0.0.1')
    assert thrift.ipv4_to_int('localhost') == base
    assert thrift.ipv4_to_int('::1') == base
    assert thrift.ipv4_to_int('a:b:1') == 0


def test_port_to_int():
    assert thrift.port_to_int('123') == 123
    assert thrift.port_to_int(32768) == -32768
    assert thrift.port_to_int((1 << 16) - 1) == -1
    assert thrift.port_to_int('bad') is None


def test_make_endpoint():
    endpoint1 = thrift.make_endpoint(ipv4='localhost', port='',
                                     service_name='XYZ')
    target = zipkin_collector.Endpoint(
        ipv4=127 << 24 | 1, port=0, service_name='xyz')
    assert endpoint1 == target

    endpoint2 = thrift.make_endpoint(ipv4='127.0.0.1', port='',
                                     service_name='XYZ')
    assert endpoint2 == target


def test_submit_batch(tracer):
    # peer = Endpoint(ipv4=thrift.ipv4_to_int('1.2.3.4'),
    #                 port=9000, service_name="my_peer")
    span = tracer.start_span("test-span")
    # add both types of annotations
    span.set_tag('bender', 'is great')
    span.set_tag('peer.ipv4', 123123)
    span.log_event('kiss-my-shiny-metal-...')
    span.finish()  # to get the duration defined
    # verify that we can serialize the span
    _marshall_span(span)


def _marshall_span(span):
    class TestTrans(TMemoryBuffer):
        def now_reading(self):
            """
            Thrift TMemoryBuffer is not read-able AND write-able,
            it's one or the other (really? yes.). This will convert
            us from write-able to read-able.
            """
            self._buffer = StringIO(self.getvalue())

    spans = thrift.make_zipkin_spans([span])

    # write and read them to test encoding
    args = Agent.emitZipkinBatch_args(spans)
    t = TestTrans()
    prot = TCompactProtocol(t)
    args.write(prot)
    t.now_reading()
    args.read(prot)


def test_large_ids(tracer):

    def serialize(span_id):
        parent_ctx = SpanContext(trace_id=span_id, span_id=span_id,
                                 parent_id=0, flags=1)
        parent = Span(context=parent_ctx, operation_name='x', tracer=tracer)
        span = tracer.start_span(operation_name='x',
                                 references=child_of(parent.context))
        span.finish()
        _marshall_span(span)

    trace_id = 0
    serialize(trace_id)
    assert thrift.id_to_int(trace_id) == 0

    trace_id = 0x77fd53dc6b437681
    serialize(trace_id)
    assert thrift.id_to_int(trace_id) == 0x77fd53dc6b437681

    trace_id = 0x7fffffffffffffff
    serialize(trace_id)
    assert thrift.id_to_int(trace_id) == 0x7fffffffffffffff

    trace_id = 0x8000000000000000
    serialize(trace_id)
    assert thrift.id_to_int(trace_id) == -0x8000000000000000

    trace_id = 0x97fd53dc6b437681
    serialize(trace_id)

    trace_id = (1L << 64) - 1
    assert trace_id == 0xffffffffffffffffL
    serialize(trace_id)
    assert thrift.id_to_int(trace_id) == -1


def test_large_tags():
    tag = thrift.make_string_tag('x', 'y' * 300)
    assert len(tag.value) <= 256


def test_parse_sampling_strategy():
    # probabilistic

    resp = sampling_manager.SamplingStrategyResponse(
        strategyType=sampling_manager.SamplingStrategyType.PROBABILISTIC)
    s, e = thrift.parse_sampling_strategy(response=resp)
    assert s is None and e is not None

    resp.probabilisticSampling = \
        sampling_manager.ProbabilisticSamplingStrategy(samplingRate=2)
    s, e = thrift.parse_sampling_strategy(response=resp)
    assert s is None and e is not None

    resp.probabilisticSampling = \
        sampling_manager.ProbabilisticSamplingStrategy(samplingRate=0.5)
    s, e = thrift.parse_sampling_strategy(response=resp)
    assert isinstance(s, ProbabilisticSampler) and e is None

    # rate limiting

    resp = sampling_manager.SamplingStrategyResponse(
        strategyType=sampling_manager.SamplingStrategyType.RATE_LIMITING)
    s, e = thrift.parse_sampling_strategy(response=resp)
    assert s is None and e is not None

    resp.rateLimitingSampling = \
        sampling_manager.RateLimitingSamplingStrategy(maxTracesPerSecond=-1)
    s, e = thrift.parse_sampling_strategy(response=resp)
    assert s is None and e is not None

    resp.rateLimitingSampling = \
        sampling_manager.RateLimitingSamplingStrategy(maxTracesPerSecond=1)
    s, e = thrift.parse_sampling_strategy(response=resp)
    assert isinstance(s, RateLimitingSampler) and e is None

    # wrong strategy type

    resp.strategyType = 'x'
    s, e = thrift.parse_sampling_strategy(response=resp)
    assert s is None and e is not None
