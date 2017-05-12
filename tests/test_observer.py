from jaeger_client.rpcmetrics import SpanObserver
from jaeger_client.rpcmetrics import MetricsByEndpoint
import pytest
import mock

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
    so = SpanObserver(operation_name='operation', metrics_by_endpoint=None, start_time=None, tags=tags)

    assert so.kind == kind
    assert so.http_status_code == http_status_code
    assert so.error == error

@pytest.mark.parametrize('tags,kind,http_status_code,error', TAGS)
@pytest.mark.gen_test
def test_handle_tag_in_lock(tags, kind, http_status_code, error):
    mock_metrics = mock.MagicMock()
    me = MetricsByEndpoint(mock_metrics, 1)
    so = SpanObserver(operation_name='operation', metrics_by_endpoint=me, start_time=None)

    so.on_set_operation_name()

