from . import Endpoint
from jaeger_client import Metrics

ENDPOINT_PLACEHOLDER = "other"
ENDPOINT_METRIC_TAG = "endpoint"

class EndpointMetric(object):
    def __init__(self, endpoint, metrics):
        self.metrics = metrics
        self.endpoint = endpoint

    def request_count_success(self):
        self.metrics.count('requests|%s=%s|error=false' % (ENDPOINT_METRIC_TAG, self.endpoint), 1)

    def request_count_failures(self):
        self.metrics.count('requests|%s=%s|error=true' % (ENDPOINT_METRIC_TAG, self.endpoint), 1)

    def request_latency_success(self, latency):
        # TODO latency doesn't exist
        # self.metrics.timer('request_latency|%s=%s|error=false' % (ENDPOINT_METRIC_TAG, self.endpoint), 1)
        pass

    def request_latency_failures(self, latency):
        # TODO latency doesn't exist
        # self.metrics.timer('request_latency|%s=%s|error=true' % (ENDPOINT_METRIC_TAG, self.endpoint), 1)
        pass

    def record_http_status_code(self, status_code):
        key = None
        if 200 <= status_code < 300:
            key = 'http_requests|%s=%s|status_code=2xx' % (ENDPOINT_METRIC_TAG, self.endpoint)
        elif 300 <= status_code < 400:
            key = 'http_requests|%s=%s|status_code=3xx' % (ENDPOINT_METRIC_TAG, self.endpoint)
        elif 400 <= status_code < 500:
            key = 'http_requests|%s=%s|status_code=4xx' % (ENDPOINT_METRIC_TAG, self.endpoint)
        elif 500 <= status_code < 600:
            key = 'http_requests|%s=%s|status_code=5xx' % (ENDPOINT_METRIC_TAG, self.endpoint)
        if key:
            self.metrics.count(key, 1)

class MetricsByEndpoint(object):
    def __init__(self, metrics, max_endpoints=200):
        from threading import Lock
        self.lock = Lock()
        self.metrics = metrics or Metrics()
        self.endpoints = Endpoint(max_endpoints)
        self.metrics_by_endpoint = {}

    def get(self, endpoint):
        safe_name = self.endpoints.normalize(endpoint)
        if not safe_name:
            safe_name = ENDPOINT_PLACEHOLDER
        with self.lock:
            if safe_name in self.metrics_by_endpoint:
                return self.metrics_by_endpoint[safe_name]
            return self.get_in_lock(safe_name)

    def get_in_lock(self, safe_name):
        self.metrics_by_endpoint[safe_name] = EndpointMetric(safe_name, self.metrics)
        return self.metrics_by_endpoint[safe_name]
