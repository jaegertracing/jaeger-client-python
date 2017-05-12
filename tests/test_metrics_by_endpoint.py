from jaeger_client.rpcmetrics import MetricsByEndpoint
import mock

def test_metrics_by_endpoint():
    mock_metrics = mock.MagicMock()
    me = MetricsByEndpoint(mock_metrics, 1)

    metric = me.get('GET')
    metric.request_count_success()
    mock_metrics.count.assert_called_with('requests|endpoint=GET|error=false', 1)
    metric.request_count_failures()
    mock_metrics.count.assert_called_with('requests|endpoint=GET|error=true', 1)
    metric.record_http_status_code(200)
    mock_metrics.count.assert_called_with('http_requests|endpoint=GET|status_code=2xx', 1)
    metric.record_http_status_code(300)
    mock_metrics.count.assert_called_with('http_requests|endpoint=GET|status_code=3xx', 1)
    metric.record_http_status_code(400)
    mock_metrics.count.assert_called_with('http_requests|endpoint=GET|status_code=4xx', 1)
    metric.record_http_status_code(500)
    mock_metrics.count.assert_called_with('http_requests|endpoint=GET|status_code=5xx', 1)

    metric = me.get('POST')
    metric.request_count_success()
    mock_metrics.count.assert_called_with('requests|endpoint=other|error=false', 1)
