import pytest
import tornado.web
from urlparse import urlparse
from jaeger_client.local_agent_net import LocalAgentSender
from jaeger_client.config import DEFAULT_REPORTING_PORT

test_strategy = """
    {
        "strategyType":0,
        "probabilisticSampling":
        {
            "samplingRate":0.002
        }
    }
    """


class AgentHandler(tornado.web.RequestHandler):
    def get(self):
        self.write(test_strategy)

application = tornado.web.Application([
    (r"/sampling", AgentHandler),
])

@pytest.fixture
def app():
    return application


@pytest.mark.gen_test
def test_request_sampling_strategy(http_client, base_url):
    o = urlparse(base_url)
    sender = LocalAgentSender(
        host='localhost',
        sampling_port=o.port,
        reporting_port=DEFAULT_REPORTING_PORT
    )
    response = yield sender.request_sampling_strategy(service_name='svc', timeout=15)
    assert response.body == test_strategy
