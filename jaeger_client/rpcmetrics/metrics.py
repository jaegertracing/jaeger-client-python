from .operation import Operation
from jaeger_client.metrics import MetricsFactory

OPERATION_PLACEHOLDER = 'other'
OPERATION_METRIC_TAG = 'operation'
OPERATION_COUNT = 'jaeger.operation-count'
OPERATION_LATENCY = 'jaeger.operation-latency'


class OperationMetric(object):
    def __init__(self, operation, metrics_factory):
        self.metrics_factory = metrics_factory or MetricsFactory()
        self.operation = operation
        self.operation_count_success = self.metrics_factory.create_counter(
            name=OPERATION_COUNT,
            tags={'status': 'ok', OPERATION_METRIC_TAG: self.operation})
        self.operation_count_failures = self.metrics_factory.create_counter(
            name=OPERATION_COUNT,
            tags={'status': 'err', OPERATION_METRIC_TAG: self.operation})
        self.operation_latency_success = self.metrics_factory.create_timer(
            name=OPERATION_LATENCY,
            tags={'status': 'ok', OPERATION_METRIC_TAG: self.operation})
        self.operation_latency_failures = self.metrics_factory.create_timer(
            name=OPERATION_LATENCY,
            tags={'status': 'err', OPERATION_METRIC_TAG: self.operation})
        self.http_status_code_2xx = self.metrics_factory.create_counter(
            name=OPERATION_COUNT,
            tags={'status': 'ok', 'proto': 'http', 'status_code': '2xx',
                  OPERATION_METRIC_TAG: self.operation})
        self.http_status_code_3xx = self.metrics_factory.create_counter(
            name=OPERATION_COUNT,
            tags={'status': 'ok', 'proto': 'http', 'status_code': '3xx',
                  OPERATION_METRIC_TAG: self.operation})
        self.http_status_code_4xx = self.metrics_factory.create_counter(
            name=OPERATION_COUNT,
            tags={'status': 'err', 'proto': 'http', 'status_code': '4xx',
                  OPERATION_METRIC_TAG: self.operation})
        self.http_status_code_5xx = self.metrics_factory.create_counter(
            name=OPERATION_COUNT,
            tags={'status': 'err', 'proto': 'http', 'status_code': '5xx',
                  OPERATION_METRIC_TAG: self.operation})

    def record_http_status_code(self, status_code):
        if 200 <= status_code < 300:
            self.http_status_code_2xx(1)
        elif 300 <= status_code < 400:
            self.http_status_code_3xx(1)
        elif 400 <= status_code < 500:
            self.http_status_code_4xx(1)
        elif 500 <= status_code < 600:
            self.http_status_code_5xx(1)


class MetricsByOperation(object):
    def __init__(self, metrics_factory, max_operations=200):
        from threading import Lock
        self.lock = Lock()
        self.metrics_factory = metrics_factory
        self.operations = Operation(max_operations)
        self.metrics_by_operation = {}

    def get(self, operation):
        safe_name = self.operations.normalize(operation)
        if not safe_name:
            safe_name = OPERATION_PLACEHOLDER
        with self.lock:
            if safe_name in self.metrics_by_operation:
                return self.metrics_by_operation[safe_name]
            return self.get_in_lock(safe_name)

    def get_in_lock(self, safe_name):
        self.metrics_by_operation[safe_name] = OperationMetric(safe_name, self.metrics_factory)
        return self.metrics_by_operation[safe_name]
