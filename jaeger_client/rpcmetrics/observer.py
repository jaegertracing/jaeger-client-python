from opentracing.ext import tags as ext_tags
import time

class Observer(object):

    def __init__(self):
        self.observers = None

    def on_start_span(self, operation_name):
        pass


# type Observer interface {
#     OnStartSpan(operationName string, options opentracing.StartSpanOptions) SpanObserver
# }

OUTBOUND_SPAN_KIND = 0x01
INBOUND_SPAN_KIND = 0x02

class SpanObserver(object):

    def __init__(self, operation_name, metrics_by_endpoint, start_time=None, tags={}):
        from threading import Lock
        self.lock = Lock()
        self.operation_name = operation_name
        self.metrics_by_endpoint = metrics_by_endpoint
        self.start_time = start_time or time.time()
        self.observers = None
        self.kind = None
        self.http_status_code = None
        self.error = None

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

            metric = self.metrics_by_endpoint.get(self.operation_name)
            latency = time.time() - self.start_time
            if self.error:
                metric.request_count_failures()
                metric.request_latency_failures(latency)
            else:
                metric.request_count_success()
                metric.request_latency_success(latency)
            metric.record_http_status_code(self.http_status_code)
