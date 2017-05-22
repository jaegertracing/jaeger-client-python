from jaeger_client.rpcmetrics import SpanObserver, MetricsByOperation
from .test_reporter import FakeMetricsFactory
import pytest

TAGS = [
    [
        {
            'span.kind': 'client',
            'http.status_code': 200,
            'error': True,
        },
        0x01,
        200,
        True,
    ],
    [
        {
            'span.kind': 'server',
            'http.status_code': '200',
            'error': 'True',
        },
        0x02,
        200,
        True,
    ],
    [
        {
            'span.kind': 'what?',
            'error': 'error',
        },
        None,
        None,
        False,
    ],
]

@pytest.mark.parametrize('tags,kind,http_status_code,error', TAGS)
@pytest.mark.gen_test
def test_handle_tag_in_lock(tags, kind, http_status_code, error):
    so = SpanObserver(operation_name='operation', metrics_by_operation=None, start_time=None, tags=tags)

    assert so.kind == kind
    assert so.http_status_code == http_status_code
    assert so.error == error

def test_span_observer_metrics():
    mf = FakeMetricsFactory()
    mo = MetricsByOperation(mf, 1)
    so = SpanObserver(operation_name='operation', metrics_by_operation=mo, start_time=0, tags={
        'span.kind': 'client',
        'http.status_code': '400',
        'error': 'True',
    },)

    so.on_set_operation_name('hello')
    so.on_set_tag('span.kind', 'server')
    so.on_finish()

    # Error metrics
    assert mf.counters['jaeger.operation-count.operation_hello.status_err'] == 1
    assert mf.counters['jaeger.operation-count.operation_hello.proto_http.status_err.status_code_4xx'] == 1
    assert mf.timers['jaeger.operation-latency.operation_hello.status_err'] > 0

    so = SpanObserver(operation_name='hello', metrics_by_operation=mo, start_time=0, tags={
        'span.kind': 'server',
        'http.status_code': '200',
    },)
    so.on_finish()

    # Success metrics
    assert mf.counters['jaeger.operation-count.operation_hello.status_ok'] == 1
    assert mf.counters['jaeger.operation-count.operation_hello.proto_http.status_ok.status_code_2xx'] == 1
    assert mf.timers['jaeger.operation-latency.operation_hello.status_ok'] > 0

    so = SpanObserver(operation_name='hello', metrics_by_operation=mo, start_time=0, tags={
        'span.kind': 'client',
    },)
    old_counters = mf.counters
    so.on_finish()

    # Client side metrics are not emitted, the metrics should not change
    assert mf.counters == old_counters

    so = SpanObserver(operation_name='world', metrics_by_operation=mo, start_time=0, tags={
        'span.kind': 'server',
    },)
    so.on_finish()

    # metrics_by_operation can hold at most 1 operation, the 'world' operation should use
    # the 'other' operation name
    assert mf.counters['jaeger.operation-count.operation_other.status_ok'] == 1
    assert mf.timers['jaeger.operation-latency.operation_other.status_ok'] > 0
