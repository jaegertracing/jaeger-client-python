import tornado.web
import json

from jaeger_client.local_agent_net import LocalAgentSender
from jaeger_client.config import (
    Config,
    DEFAULT_SAMPLING_PORT,
    DEFAULT_REPORTING_PORT,
)
from jaeger_client.sampler import RemoteControlledSampler
from jaeger_client.reporter import Reporter
from jaeger_client.tracer import Tracer

config = {
    'service_name': 'crossdock-python',
    'enabled': True,
    'sampler': {
        'type': 'probabilistic',
        'param': 1,
    },
    'reporter_flush_interval': 1,
    'sampling_refresh_interval': 5,
}


class EndToEndHandler(object):
    """
    Handler that creates traces from a http request.

    json: {
        "operation": "operationName",
        "count": 2,
        "tags": {
            "key": "value"
        }
    }

    Given the above json payload, the handler will create 2 traces for the "operationName"
    operation with the tags: {"key":"value"}. These traces are reported to the agent with
    the hostname "test_driver".
    """

    def __init__(self):
        cfg = Config(config)
        init_sampler = cfg.sampler
        channel = self.local_agent_sender

        sampler = RemoteControlledSampler(
            channel=channel,
            service_name=cfg.service_name,
            sampling_refresh_interval=cfg.sampling_refresh_interval,
            init_sampler=init_sampler)

        reporter = Reporter(
            channel=channel,
            flush_interval=cfg.reporter_flush_interval)

        self._tracer = Tracer(
            service_name=cfg.service_name,
            reporter=reporter,
            sampler=sampler)

    @property
    def tracer(self):
        return self._tracer

    @tracer.setter
    def tracer(self, tracer):
        self._tracer = tracer

    @property
    def local_agent_sender(self):
        return LocalAgentSender(
            host='test_driver',
            sampling_port=DEFAULT_SAMPLING_PORT,
            reporting_port=DEFAULT_REPORTING_PORT,
        )

    @tornado.gen.coroutine
    def generate_traces(self, request, response_writer):
        req = json.loads(request.body)
        for _ in range(req.get('count', 0)):
            span = self.tracer.start_span(req['operation'])
            for k, v in req.get('tags', {}).iteritems():
                span.set_tag(k, v)
            span.finish()
        response_writer.finish()
