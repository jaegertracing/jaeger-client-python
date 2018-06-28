# Copyright (c) 2018 Uber Technologies, Inc.
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

from time import time
import json

import mock

from jaeger_client.zipkin_v2 import make_zipkin_v2_batch, to_zipkin_v2_span
from jaeger_client import Span, SpanContext, ConstSampler
import jaeger_client.thrift_gen.jaeger.ttypes as ttypes
from jaeger_client.constants import JAEGER_IP_TAG_KEY
from jaeger_client.thrift import timestamp_micros
from opentracing.ext import tags as ext_tags
from jaeger_client import thrift


def to_tag(key, value):
    return thrift.make_string_tag(key=key, value=value, max_length=100)


def test_to_v2_span_no_parent_nor_duration_nor_tags_nor_annotations(tracer):
    start_time = time()
    ctx = SpanContext(trace_id=1, span_id=1, parent_id=None, flags=1)
    span = Span(context=ctx, operation_name='operation', start_time=start_time, tracer=tracer)
    process = ttypes.Process(serviceName='x')
    zip_span = to_zipkin_v2_span(span, process)
    expected = dict(debug=False, id='0000000000000001',
                    traceId='0000000000000001',
                    localEndpoint=dict(serviceName='x'),
                    name='operation', timestamp=timestamp_micros(start_time))
    assert zip_span == expected


def test_to_v2_span_with_parent_no_duration_nor_tags_nor_annotations(tracer):
    start_time = time()
    ctx = SpanContext(trace_id=1, span_id=2, parent_id=1, flags=1)
    span = Span(context=ctx, operation_name='operation', start_time=start_time, tracer=tracer)
    process = ttypes.Process(serviceName='x', tags=[to_tag(JAEGER_IP_TAG_KEY, '127.0.0.1')])
    zip_span = to_zipkin_v2_span(span, process)
    expected = dict(debug=False, id='0000000000000002',
                    parentId='0000000000000001', traceId='0000000000000001',
                    localEndpoint=dict(serviceName='x', ipv4='127.0.0.1'),
                    name='operation', timestamp=timestamp_micros(start_time))
    assert zip_span == expected


def test_to_v2_span_with_parent_and_duration_and_tags_no_annotations(tracer):
    start_time = time()
    ctx = SpanContext(trace_id=1, span_id=2, parent_id=1, flags=1)
    span = Span(context=ctx, operation_name='operation', start_time=start_time, tracer=tracer)
    span.set_tag('SomeKey', '123123')
    span.set_tag(ext_tags.SPAN_KIND, ext_tags.SPAN_KIND_RPC_CLIENT)
    end_time = start_time + 20
    span.end_time = end_time
    process = ttypes.Process(serviceName='x', tags=[to_tag(JAEGER_IP_TAG_KEY, '127.0.0.1')])
    zip_span = to_zipkin_v2_span(span, process)
    expected = dict(kind='CLIENT', debug=False, id='0000000000000002',
                    parentId='0000000000000001', traceId='0000000000000001',
                    localEndpoint=dict(serviceName='x', ipv4='127.0.0.1'),
                    name='operation', timestamp=timestamp_micros(start_time),
                    duration=20000000, tags=dict(SomeKey='123123'))
    assert zip_span == expected


def test_to_v2_span_with_parent_and_duration_and_tags_and_annotations(tracer):
    start_time = time()
    ctx = SpanContext(trace_id=18446744073709551614, span_id=18446744073709551615,
                      parent_id=18446744073709551614, flags=1)
    span = Span(context=ctx, operation_name='operation', start_time=start_time, tracer=tracer)
    span.set_tag('SomeKey', '123123')
    span.set_tag(ext_tags.SPAN_KIND, ext_tags.SPAN_KIND_RPC_SERVER)
    event_time = time() + 3
    span.log_kv({'SomeTagKey': 'SomeTagValue'}, timestamp=event_time)  
    end_time = start_time + 20
    span.end_time = end_time
    process = ttypes.Process(serviceName='x', tags=[to_tag(JAEGER_IP_TAG_KEY, '127.0.0.1')])
    zip_span = to_zipkin_v2_span(span, process)
    expected = dict(kind='SERVER', debug=False, id='ffffffffffffffff',
                    parentId='fffffffffffffffe', traceId='fffffffffffffffe',
                    localEndpoint=dict(serviceName='x', ipv4='127.0.0.1'),
                    name='operation', timestamp=timestamp_micros(start_time),
                    duration=20000000, tags=dict(SomeKey='123123'),
                    annotations=[dict(timestamp=timestamp_micros(event_time),
                                      value=json.dumps(dict(SomeTagKey='SomeTagValue')))])
    assert zip_span == expected


def test_to_v2_span_remote_with_parent_and_duration_and_tags_and_annotations(tracer):
    start_time = time()
    ctx = SpanContext(trace_id=9205364235243340812, span_id=9830726033745040073,
                      parent_id=9205364235243340812, flags=1)
    span = Span(context=ctx, operation_name='operation', start_time=start_time, tracer=tracer)
    span.set_tag('SomeKey', '123123')
    event_time = time() + 3
    span.log_kv({'SomeTagKey': 'SomeTagValue1'}, timestamp=event_time)  
    span.log_kv({'SomeOtherTagKey': 'SomeTagValue2'}, timestamp=event_time + 1)  
    span.log_kv({'SomeAdditionalTagKey': 'SomeTagValue3'}, timestamp=event_time + 2)  
    end_time = start_time + 20
    span.end_time = end_time
    process = ttypes.Process(serviceName='x', tags=[
        to_tag(JAEGER_IP_TAG_KEY, '127.0.0.1'),
        to_tag(ext_tags.PEER_HOST_IPV4, '192.168.34.1'),
        to_tag(ext_tags.PEER_HOST_IPV6, '::1'),
        to_tag(ext_tags.PEER_SERVICE, 'remote_operation'),
        to_tag(ext_tags.PEER_PORT, 99776),
        to_tag('SomeOtherTag', 'TagValue')
    ])

    def is_debug(*args):  # simultaneously sampled and debug
        return True

    span.is_debug = is_debug
    zip_span = to_zipkin_v2_span(span, process)

    expected = dict(debug=True, id='886dc13e058ed2c9',
                    parentId='7fc005fff5c3c40c', traceId='7fc005fff5c3c40c',
                    localEndpoint=dict(serviceName='x', ipv4='127.0.0.1'),
                    remoteEndpoint=dict(serviceName='remote_operation',
                                        ipv4='192.168.34.1', ipv6='::1',
                                        port=99776),
                    name='operation', timestamp=timestamp_micros(start_time),
                    duration=20000000, tags=dict(SomeKey='123123'),
                    annotations=[
                        dict(timestamp=timestamp_micros(event_time),
                             value=json.dumps(dict(SomeTagKey='SomeTagValue1'))),
                        dict(timestamp=timestamp_micros(event_time + 1),
                             value=json.dumps(dict(SomeOtherTagKey='SomeTagValue2'))),
                        dict(timestamp=timestamp_micros(event_time + 2),
                             value=json.dumps(dict(SomeAdditionalTagKey='SomeTagValue3'))),
                    ])
    assert zip_span == expected


def test_make_zipkin_v2_batch(tracer):
    ctx_one = SpanContext(trace_id=1, span_id=1, parent_id=None, flags=1)
    span_one = Span(context=ctx_one, operation_name='operation', start_time=time(), tracer=tracer)
    ctx_two = SpanContext(trace_id=1, span_id=2, parent_id=1, flags=1)
    span_two = Span(context=ctx_two, operation_name='operation', start_time=time(), tracer=tracer)
    ctx_three = SpanContext(trace_id=1, span_id=3, parent_id=2, flags=1)
    span_three = Span(context=ctx_three, operation_name='operation', start_time=time(), tracer=tracer)
    process = ttypes.Process(serviceName='x', tags=[to_tag(JAEGER_IP_TAG_KEY, '127.0.0.1')])
    batch = make_zipkin_v2_batch([span_one, span_two, span_three], process)
    assert len(batch) == 3
    assert batch[0]['id'] == '0000000000000001'
    assert batch[1]['id'] == '0000000000000002'
    assert batch[2]['id'] == '0000000000000003'
