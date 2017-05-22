from jaeger_client.rpcmetrics import MetricsByOperation
from .test_reporter import FakeMetricsFactory


def test_metrics_by_endpoint():
    mf = FakeMetricsFactory()
    mo = MetricsByOperation(mf, 1)

    metric = mo.get('GET')
    metric.operation_count_success(1)
    metric.operation_count_failures(1)
    metric.http_status_code_2xx(1)
    metric.http_status_code_3xx(1)
    metric.http_status_code_4xx(1)
    metric.http_status_code_5xx(1)

    assert mf.counters == {
        'jaeger.operation-count.operation_GET.status_ok': 1,
        'jaeger.operation-count.operation_GET.status_err': 1,
        'jaeger.operation-count.operation_GET.proto_http.status_ok.status_code_2xx': 1,
        'jaeger.operation-count.operation_GET.proto_http.status_ok.status_code_3xx': 1,
        'jaeger.operation-count.operation_GET.proto_http.status_err.status_code_4xx': 1,
        'jaeger.operation-count.operation_GET.proto_http.status_err.status_code_5xx': 1,
    }

    metric.operation_latency_success(1)
    assert 'jaeger.operation-latency.operation_GET.status_ok' in mf.timers
    metric.operation_latency_failures(1)
    assert 'jaeger.operation-latency.operation_GET.status_err' in mf.timers

    metric = mo.get('POST')
    metric.operation_count_success(1)
    assert 'jaeger.operation-count.operation_other.status_ok' in mf.counters
