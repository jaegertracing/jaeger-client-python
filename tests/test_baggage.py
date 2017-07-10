import mock
import pytest
import tornado.web
from urlparse import urlparse
from jaeger_client.local_agent_net import LocalAgentSender
from jaeger_client.config import DEFAULT_REPORTING_PORT

from jaeger_client.baggage import (
    RemoteBaggageRestrictionManager
)

KEY = 'key'
MAX_VALUE_LENGTH = 10

baggage_restrictions = """
        [
            {
                "baggageKey":"key",
                "maxValueLength":10
            }
        ]
    """

class BaggageRestrictionsHandler(tornado.web.RequestHandler):
    def get(self):
        self.write(baggage_restrictions)

application = tornado.web.Application([
    (r"/baggageRestrictions", BaggageRestrictionsHandler),
])

@pytest.fixture
def app():
    return application

@pytest.mark.gen_test
def test_remote_baggage_restriction_manager(http_client, base_url):
    o = urlparse(base_url)
    sender = LocalAgentSender(
        host='localhost',
        config_port=o.port,
        reporting_port=DEFAULT_REPORTING_PORT
    )
    mgr = RemoteBaggageRestrictionManager(
        channel=sender,
        service_name='x',
        refresh_interval_seconds=0.001
    )
    while not mgr.initialized:
        yield tornado.gen.sleep(0.001) # Sleep 1 millisecond
    valid, max_value_length = mgr.is_valid_baggage_key(KEY)
    assert valid
    assert max_value_length == MAX_VALUE_LENGTH

    mgr.close()

def test_update_baggage_restrictions():
    mgr = RemoteBaggageRestrictionManager(
        channel=mock.MagicMock(),
        service_name='x'
    )

    # noinspection PyProtectedMember
    mgr._update_baggage_restrictions([{'baggageKey': KEY, 'maxValueLength': MAX_VALUE_LENGTH}])

    valid, max_value_length = mgr.is_valid_baggage_key(KEY)
    assert valid
    assert max_value_length == MAX_VALUE_LENGTH

    valid, max_value_length = mgr.is_valid_baggage_key('x')
    assert not valid

def test_request_callback():
    mgr = RemoteBaggageRestrictionManager(
        channel=mock.MagicMock(),
        service_name='x'
    )
    mgr.metrics = mock.MagicMock()

    return_value = mock.MagicMock()
    return_value.exception = lambda *args: False

    return_value.result = lambda *args: \
        type('obj', (object,), {'body': baggage_restrictions})()
    # noinspection PyProtectedMember
    mgr._request_callback(return_value)
    mgr.metrics.baggage_restrictions_update_success.assert_called_with(1)

    valid, max_value_length = mgr.is_valid_baggage_key(KEY)
    assert valid
    assert max_value_length == 10

    return_value.result = lambda *args: \
        type('obj', (object,), {'body': 'bad_json'})()
    # noinspection PyProtectedMember
    mgr._request_callback(return_value)
    mgr.metrics.baggage_restrictions_update_success.assert_called_with(1)

    return_value.exception = lambda *args: True
    # noinspection PyProtectedMember
    mgr._request_callback(return_value)
    mgr.metrics.baggage_restrictions_update_failure.assert_called_with(1)

def test_allow_baggage_on_initialization_failure():
    mgr = RemoteBaggageRestrictionManager(
        channel=mock.MagicMock(),
        service_name='x'
    )
    valid, max_value_length = mgr.is_valid_baggage_key(KEY)
    assert valid
    assert max_value_length == 2048

def test_deny_baggage_on_initialization_failure():
    mgr = RemoteBaggageRestrictionManager(
        channel=mock.MagicMock(),
        service_name='x',
        deny_baggage_on_initialization_failure=True
    )
    valid, max_value_length = mgr.is_valid_baggage_key(KEY)
    assert not valid
