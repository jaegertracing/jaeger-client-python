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

import socket
import struct

import jaeger_client.thrift_gen.zipkincore.ZipkinCollector as zipkin_collector
import jaeger_client.thrift_gen.sampling.SamplingManager as sampling_manager
from .thrift_gen.zipkincore.constants import SERVER_SEND, SERVER_RECV
from .thrift_gen.zipkincore.constants import CLIENT_SEND, CLIENT_RECV
from .thrift_gen.zipkincore.constants import SERVER_ADDR, CLIENT_ADDR
from .thrift_gen.zipkincore.constants import LOCAL_COMPONENT

_max_signed_port = (1 << 15) - 1
_max_unsigned_port = (1 << 16)
_max_signed_id = (1L << 63) - 1
_max_unsigned_id = (1L << 64)


def ipv4_to_int(ipv4):
    if ipv4 == 'localhost':
        ipv4 = '127.0.0.1'
    elif ipv4 == '::1':
        ipv4 = '127.0.0.1'
    try:
        return struct.unpack('!i', socket.inet_aton(ipv4))[0]
    except:
        return 0


def port_to_int(port):
    if type(port) is str:
        if port.isdigit():
            port = int(port)
    if type(port) is int:
        # zipkincore.thrift defines port as i16, which is signed,
        # therefore we convert ephemeral ports as negative ints
        if port > _max_signed_port:
            port -= _max_unsigned_port
        return port
    return None


def id_to_int(big_id):
    # zipkincore.thrift defines ID fields as i64, which is signed,
    # therefore we convert large IDs (> 2^63) to negative longs
    if big_id > _max_signed_id:
        big_id -= _max_unsigned_id
    return big_id


def make_endpoint(ipv4, port, service_name):
    if isinstance(ipv4, basestring):
        ipv4 = ipv4_to_int(ipv4)
    port = port_to_int(port)
    if port is None:
        port = 0
    return zipkin_collector.Endpoint(ipv4, port, service_name.lower())


def make_string_tag(key, value):
    if len(value) > 256:
        value = value[:256]
    return zipkin_collector.BinaryAnnotation(
        key, value, zipkin_collector.AnnotationType.STRING)


def make_peer_address_tag(key, host):
    """
    Used for Zipkin binary annotations like CA/SA (client/server address).
    They are modeled as Boolean type with '0x01' as the value.
    :param key:
    :param host:
    """
    return zipkin_collector.BinaryAnnotation(
        key, '0x01', zipkin_collector.AnnotationType.BOOL, host)


def make_local_component_tag(component_name, endpoint):
    """
    Used for Zipkin binary annotation LOCAL_COMPONENT.
    :param component_name:
    :param endpoint:
    """
    return zipkin_collector.BinaryAnnotation(
        key=LOCAL_COMPONENT, value=component_name,
        annotation_type=zipkin_collector.AnnotationType.STRING,
        host=endpoint)


def make_event(timestamp, name):
    return zipkin_collector.Annotation(
        timestamp=timestamp_micros(timestamp), value=name, host=None)


def timestamp_micros(ts):
    """
    Convert a float Unix timestamp from time.time() into a long value
    in microseconds, as required by Zipkin protocol.
    :param ts:
    :return:
    """
    return long(ts * 1000000)


def make_zipkin_spans(spans):
    zipkin_spans = []
    for span in spans:
        endpoint = make_endpoint(ipv4=span.tracer.ip_address,
                                 port=0,  # span.port,
                                 service_name=span.tracer.service_name)
        # TODO extend Zipkin Thrift and pass endpoint once only
        for event in span.logs:
            event.host = endpoint
        with span.update_lock:
            add_zipkin_annotations(span=span, endpoint=endpoint)
            zipkin_span = zipkin_collector.Span(
                trace_id=id_to_int(span.trace_id),
                name=span.operation_name,
                id=id_to_int(span.span_id),
                parent_id=id_to_int(span.parent_id) or None,
                annotations=span.logs,
                binary_annotations=span.tags,
                debug=span.is_debug(),
                timestamp=timestamp_micros(span.start_time),
                duration=timestamp_micros(span.end_time - span.start_time)
            )
        zipkin_spans.append(zipkin_span)
    return zipkin_spans


def add_zipkin_annotations(span, endpoint):
    if span.is_rpc():
        is_client = span.is_rpc_client()

        end_event = CLIENT_RECV if is_client else SERVER_SEND
        end_event = make_event(timestamp=span.end_time, name=end_event)
        end_event.host = endpoint
        span.logs.append(end_event)

        start_event = CLIENT_SEND if is_client else SERVER_RECV
        start_event = make_event(timestamp=span.start_time, name=start_event)
        start_event.host = endpoint
        span.logs.append(start_event)

        if span.peer:
            host = make_endpoint(
                ipv4=span.peer.get('ipv4', 0),
                port=span.peer.get('port', 0),
                service_name=span.peer.get('service_name', ''))
            key = SERVER_ADDR if is_client else CLIENT_ADDR
            peer = make_peer_address_tag(key=key, host=host)
            span.tags.append(peer)
    else:
        lc = make_local_component_tag(
            component_name=span.component or span.tracer.service_name,
            endpoint=endpoint)
        span.tags.append(lc)


def parse_sampling_strategy(response):
    """
    Parse SamplingStrategyResponse and converts to a Sampler.

    :param response:
    :return: Returns Go-style (value, error) pair
    """
    s_type = response.strategyType
    if s_type == sampling_manager.SamplingStrategyType.PROBABILISTIC:
        if response.probabilisticSampling is None:
            return None, 'probabilisticSampling field is None'
        sampling_rate = response.probabilisticSampling.samplingRate
        if 0 <= sampling_rate <= 1.0:
            from jaeger_client.sampler import ProbabilisticSampler
            return ProbabilisticSampler(rate=sampling_rate), None
        return None, (
            'Probabilistic sampling rate not in [0, 1] range: %s' %
            sampling_rate
        )
    elif s_type == sampling_manager.SamplingStrategyType.RATE_LIMITING:
        if response.rateLimitingSampling is None:
            return None, 'rateLimitingSampling field is None'
        mtps = response.rateLimitingSampling.maxTracesPerSecond
        if 0 <= mtps < 500:
            from jaeger_client.sampler import RateLimitingSampler
            return RateLimitingSampler(max_traces_per_second=mtps), None
        return None, (
            'Rate limiting parameter not in [0, 500] range: %s' % mtps
        )
    return None, (
        'Unsupported sampling strategy type: %s' % s_type
    )
