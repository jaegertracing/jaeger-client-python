from opentracing.ext import tags as ext_tags
from .metrics import MetricsByOperation
import time

DEFAULT_MAX_NUMBER_OF_OPERATIONS = 200
OUTBOUND_SPAN_KIND = 0x01
INBOUND_SPAN_KIND = 0x02


class Observer(object):

    def __init__(self, metrics_factory):
        self.metrics_by_operation = MetricsByOperation(
            metrics_factory, DEFAULT_MAX_NUMBER_OF_OPERATIONS)

    def on_start_span(self, operation_name, start_time=None, tags=None):
        return SpanObserver(
            operation_name=operation_name,
            metrics_by_operation=self.metrics_by_operation,
            start_time=start_time,
            tags=tags,
        )


class SpanObserver(object):

    def __init__(self, operation_name, metrics_by_operation, start_time=None, tags=None):
        from threading import Lock
        self.lock = Lock()
        self.operation_name = operation_name
        self.metrics_by_operation = metrics_by_operation
        self.start_time = start_time or time.time()
        self.observers = None
        self.kind = None
        self.http_status_code = None
        self.error = None

        if tags:
            for k, v in tags.iteritems():
                self.handle_tag_in_lock(k, v)

    def handle_tag_in_lock(self, key, value):
        if key == ext_tags.SPAN_KIND:
            if value == ext_tags.SPAN_KIND_RPC_CLIENT:
                self.kind = OUTBOUND_SPAN_KIND
            elif value == ext_tags.SPAN_KIND_RPC_SERVER:
                self.kind = INBOUND_SPAN_KIND
        elif key == ext_tags.HTTP_STATUS_CODE:
            if isinstance(value, (str, unicode)):
                self.http_status_code = int(value)
            elif isinstance(value, int):
                self.http_status_code = value
        elif key == 'error':
            # TODO ext_tags.ERROR has not been released yet in opentracing-python
            if isinstance(value, bool):
                self.error = value
            elif isinstance(value, (str, unicode)):
                self.error = value == 'True'

    def on_set_operation_name(self, operation_name):
        with self.lock:
            self.operation_name = operation_name

    def on_set_tag(self, key, value):
        with self.lock:
            self.handle_tag_in_lock(key, value)

    def on_finish(self):
        """
        Emits the RPC metrics. It only has an effect when operation_name
        is not blank, and the span kind is an RPC server.
        """
        with self.lock:
            if not self.operation_name or self.kind != INBOUND_SPAN_KIND:
                return

            metric = self.metrics_by_operation.get(self.operation_name)
            latency = time.time() - self.start_time
            if self.error:
                metric.operation_count_failures(1)
                metric.operation_latency_failures(latency)
            else:
                metric.operation_count_success(1)
                metric.operation_latency_success(latency)
            metric.record_http_status_code(self.http_status_code)
