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

import collections
import json
import mock

from opentracing.ext import tags as ext_tags
from jaeger_client import Span, SpanContext, ConstSampler, Tracer, ProbabilisticSampler


def test_baggage():
    mock_tracer = mock.MagicMock()
    mock_tracer.max_tag_value_length = 100
    ctx = SpanContext(trace_id=1, span_id=2, parent_id=None, flags=1)
    span = Span(context=ctx, operation_name='x', tracer=mock_tracer)
    assert span.get_baggage_item('x') is None
    span.set_baggage_item('x', 'y').\
        set_baggage_item('z', 'why')
    assert span.get_baggage_item('x') == 'y'
    assert span.get_baggage_item('z') == 'why'
    assert span.get_baggage_item('tt') is None
    assert len(span.context.baggage) == 2
    span.set_baggage_item('x', 'b')  # override
    assert span.get_baggage_item('x') == 'b'
    assert len(span.context.baggage) == 2
    span.set_baggage_item('X_y', '123')
    assert span.get_baggage_item('X_y') == '123'
    assert span.get_baggage_item('x-Y') is None


def _tags_to_dict(tags):
    return {f.key: f.vStr for f in tags}


def test_baggage_logs():
    mock_tracer = mock.MagicMock()
    mock_tracer.max_tag_value_length = 100
    ctx = SpanContext(trace_id=1, span_id=2, parent_id=None, flags=1)
    span = Span(context=ctx, operation_name='x', tracer=mock_tracer)
    span.set_baggage_item('x', 'a')
    assert span.get_baggage_item('x') == 'a'
    assert len(span.logs) == 1
    assert _tags_to_dict(span.logs[0].fields) == {
        "event": "baggage", "key": "x", "value": "a",
    }
    span.set_baggage_item('x', 'b')  # override
    assert span.get_baggage_item('x') == 'b'
    assert len(span.logs) == 2
    assert _tags_to_dict(span.logs[1].fields) == {
        "event": "baggage", "key": "x", "value": "b", "override": "true",
    }


def test_is_rpc():
    mock_tracer = mock.MagicMock()
    mock_tracer.max_tag_value_length = 100
    ctx = SpanContext(trace_id=1, span_id=2, parent_id=None, flags=1)

    span = Span(context=ctx, operation_name='x', tracer=mock_tracer)
    assert span.is_rpc() is False
    assert span.is_rpc_client() is False

    span = Span(context=ctx, operation_name='x', tracer=mock_tracer)
    span.set_tag(ext_tags.SPAN_KIND, ext_tags.SPAN_KIND_RPC_SERVER)
    assert span.is_rpc() is True
    assert span.is_rpc_client() is False

    span = Span(context=ctx, operation_name='x', tracer=mock_tracer)
    span.set_tag(ext_tags.SPAN_KIND, ext_tags.SPAN_KIND_RPC_CLIENT)
    assert span.is_rpc() is True
    assert span.is_rpc_client() is True


def test_sampling_priority(tracer):
    tracer.sampler = ConstSampler(False)
    span = tracer.start_span(operation_name='x')
    assert span.is_sampled() is False
    span.set_tag(ext_tags.SAMPLING_PRIORITY, 1)
    assert span.is_sampled()
    assert span.is_debug()
    span.set_tag(ext_tags.SAMPLING_PRIORITY, 0)
    assert span.is_sampled() is False


def test_span_logging(tracer):
    tpl = collections.namedtuple(
        'Test',
        ['method', 'args', 'kwargs', 'expected', 'error', 'timestamp'])

    def test(method, expected,
             args=None, kwargs=None, error=False, timestamp=None):
        if isinstance(expected, str):
            expected = {'event': expected}
        return tpl(
            method=method,
            args=args if args else [],
            expected=expected,
            kwargs=kwargs if kwargs else {},
            error=error,
            timestamp=timestamp,
        )

    def event_payload(event, payload):
        return {'event': event, 'payload': payload}

    def from_json(val):
        return json.loads(val)

    tests = [
        # deprecated info() method
        test(method='info',
             args=['msg'],
             expected='msg'),
        test(method='info',
             args=['msg', 'data'],
             expected=event_payload('msg', 'data')),
        # deprecated error() method
        test(method='error',
             args=['msg'],
             expected='msg', error=True),
        test(method='error',
             args=['msg', 'data'],
             expected=event_payload('msg', 'data'), error=True),
        # deprecated log_event() method
        test(method='log_event',
             args=['msg'],
             expected='msg'),
        test(method='log_event',
             args=['msg', 'data'],
             expected=event_payload('msg', 'data')),
        # deprecated log() method
        test(method='log',
             kwargs={'event': 'msg'},
             expected='msg'),
        test(method='log',
             kwargs={'event': 'msg', 'payload': 'data'},
             expected=event_payload('msg', 'data')),
        test(method='log',
             kwargs={'event': 'msg', 'payload': 'data', 'ignored': 'blah'},
             expected=event_payload('msg', 'data')),
        test(method='log',
             kwargs={'event': 'msg', 'payload': 'data', 'timestamp': 123},
             expected=event_payload('msg', 'data'),
             timestamp=123 * 1000 * 1000),  # in microseconds
        # log_kv()
        test(method='log_kv',
             args=[{'event': 'msg'}],
             expected='msg'),
        test(method='log_kv',
             args=[{'event': 'msg', 'x': 'y'}],
             expected={'event': 'msg', 'x': 'y'}),
        test(method='log_kv',
             args=[{'event': 'msg', 'x': 'y'}, 123],  # all args positional
             expected={'event': 'msg', 'x': 'y'},
             timestamp=123 * 1000 * 1000),
        test(method='log_kv',
             args=[{'event': 'msg', 'x': 'y'}],  # positional and kwargs
             kwargs={'timestamp': 123},
             expected={'event': 'msg', 'x': 'y'},
             timestamp=123 * 1000 * 1000),
        test(method='log_kv',
             args=[],  # kwargs only
             kwargs={
                 'key_values': {'event': 'msg', 'x': 'y'},
                 'timestamp': 123,
             },
             expected={'event': 'msg', 'x': 'y'},
             timestamp=123 * 1000 * 1000),  # to microseconds
    ]

    for test in tests:
        name = '%s' % (test,)
        span = tracer.start_span(operation_name='x')
        span.logs = []
        span.tags = []

        if test.method == 'info':
            span.info(*test.args, **test.kwargs)
        elif test.method == 'error':
            span.error(*test.args, **test.kwargs)
        elif test.method == 'log':
            span.log(*test.args, **test.kwargs)
        elif test.method == 'log_event':
            span.log_event(*test.args, **test.kwargs)
        elif test.method == 'log_kv':
            span.log_kv(*test.args, **test.kwargs)
        else:
            raise ValueError('Unknown method %s' % test.method)

        assert len(span.logs) == 1, name
        log = span.logs[0]
        log_fields = _tags_to_dict(log.fields)
        assert log_fields == test.expected

        if test.timestamp:
            assert log.timestamp == test.timestamp


def test_span_to_string(tracer):
    tracer.service_name = 'unittest'
    ctx = SpanContext(trace_id=1, span_id=1, parent_id=1, flags=1)
    span = Span(context=ctx, operation_name='crypt', tracer=tracer)
    assert '%s' % span == '1:1:1:1 unittest.crypt'


def test_span_tag_value_max_length(tracer):
    tracer.max_tag_value_length = 42
    span = tracer.start_span(operation_name='x')
    span.set_tag('x', 'x' * 50)
    tag_n = len(span.tags) - 1
    assert span.tags[tag_n].key == 'x'
    assert span.tags[tag_n].vStr == 'x' * 42


def test_sampling_finalized_on_setting_sampling_priority_tag(tracer):
    span = tracer.start_span(operation_name='x')
    assert not span.context.sampling_finalized

    span.set_tag(ext_tags.SAMPLING_PRIORITY, 1)
    assert span.context.sampling_finalized

    unsampled_span = tracer.start_span(operation_name='unsampled_span')
    unsampled_span.set_tag(ext_tags.SAMPLING_PRIORITY, 0)
    assert unsampled_span.context.sampling_finalized


def test_sampling_finalized_on_finished_span(tracer):
    span = tracer.start_span(operation_name='x')
    assert not span.context.sampling_finalized

    span.finish()
    assert span.context.sampling_finalized


def test_sampling_finalized_on_set_operation_name(tracer):
    span = tracer.start_span(operation_name='x')
    assert not span.context.sampling_finalized

    span.set_operation_name('y')
    assert span.context.sampling_finalized


def test_is_writeable_returns_true_if_no_finalized_or_the_span_is_sampled():
    reporter = mock.MagicMock()
    sampler = ConstSampler(False)
    tracer = Tracer(
        service_name='test_service_1', reporter=reporter, sampler=sampler)

    unfinalized_span = tracer.start_span(operation_name='unfinalized_span')
    assert not unfinalized_span.context.sampling_finalized
    assert unfinalized_span._is_writeable()

    unfinalized_span.finish()
    assert not unfinalized_span._is_writeable()

    tracer.sampler = ConstSampler(True)
    sampled_span = tracer.start_span(operation_name='sampled_span')
    assert sampled_span._is_writeable()


def test_set_operation_name_should_add_sampler_tags_to_span_and_change_operation_name(tracer):
    span = tracer.start_span(operation_name='x')
    assert span.operation_name is 'x'
    assert _tags_to_dict(span.tags) == {
        "sampler.type": "const", "sampler.param": 'True'
    }

    tracer.sampler = ProbabilisticSampler(1.0)
    span.set_operation_name(operation_name='y')
    assert span.operation_name is 'y'
    assert _tags_to_dict(span.tags) == {
        "sampler.type": "probabilistic", "sampler.param": '1.0'
    }


def test_set_operation_name_should_not_change_sampler_tags_but_change_operation_name(tracer):
    span = tracer.start_span(operation_name='x')
    span.set_operation_name(operation_name='y')
    assert span.operation_name is 'y'

    # update sampler to something that will always sample
    tracer.sampler = ProbabilisticSampler(1.0)

    # The second call should rename the operation name, but
    # not re-sample the span.  This is because finalize was set
    # in the first 'setOperationName' call.
    span.set_operation_name(operation_name='z')
    assert span.operation_name is 'z'
    assert _tags_to_dict(span.tags) == {
        "sampler.type": "const", "sampler.param": 'True'
    }
