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

import six
import socket
import struct

import jaeger_client.thrift_gen.jaeger.ttypes as ttypes
import jaeger_client.thrift_gen.sampling.SamplingManager as sampling_manager

_max_signed_port = (1 << 15) - 1
_max_unsigned_port = (1 << 16)
_max_signed_id = (1 << 63) - 1
_max_unsigned_id = (1 << 64)

if six.PY3:
    long = int


def ipv4_to_int(ipv4):
    if ipv4 == 'localhost':
        ipv4 = '127.0.0.1'
    elif ipv4 == '::1':
        ipv4 = '127.0.0.1'
    try:
        return struct.unpack('!i', socket.inet_aton(ipv4))[0]
    except:
        return 0


def id_to_int(big_id):
    if big_id is None:
        return None
    # thrift defines ID fields as i64, which is signed,
    # therefore we convert large IDs (> 2^63) to negative longs
    if big_id > _max_signed_id:
        big_id -= _max_unsigned_id
    return big_id


def _to_string(s):
    try:
        if isinstance(s, six.text_type):  # This is unicode() in Python 2 and str in Python 3.
            return s.encode('utf-8')
        else:
            return str(s)
    except Exception as e:
        return str(e)


def make_string_tag(key, value, max_length):
    key = _to_string(key)
    value = _to_string(value)
    if len(value) > max_length:
        value = value[:max_length]
    return ttypes.Tag(
        key=key,
        vStr=value,
        vType=ttypes.TagType.STRING,
    )


def timestamp_micros(ts):
    """
    Convert a float Unix timestamp from time.time() into a long value
    in microseconds, as required by Zipkin protocol.
    :param ts:
    :return:
    """
    return long(ts * 1000000)


def make_tags(tags, max_length):
    # TODO extend to support non-string tag values
    return [
        make_string_tag(key=k, value=v, max_length=max_length)
        for k, v in six.iteritems(tags or {})
    ]


def make_log(timestamp, fields, max_length):
    return ttypes.Log(
        timestamp=timestamp_micros(ts=timestamp),
        fields=make_tags(tags=fields, max_length=max_length),
    )


def make_process(service_name, tags, max_length):
    return ttypes.Process(
        serviceName=service_name,
        tags=make_tags(tags=tags, max_length=max_length),
    )


def make_jaeger_batch(spans, process):
    batch = ttypes.Batch(
        spans=[],
        process=process,
    )
    for span in spans:
        with span.update_lock:
            jaeger_span = ttypes.Span(
                traceIdLow=id_to_int(span.trace_id),
                traceIdHigh=0,
                spanId=id_to_int(span.span_id),
                parentSpanId=id_to_int(span.parent_id) or 0,
                operationName=span.operation_name,
                # references = references, # TODO
                flags=span.context.flags,
                startTime=timestamp_micros(span.start_time),
                duration=timestamp_micros(span.end_time - span.start_time),
                tags=span.tags,  # TODO
                logs=span.logs,  # TODO
            )
        batch.spans.append(jaeger_span)
    return batch


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
