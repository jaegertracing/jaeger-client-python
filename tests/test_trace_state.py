import base64
from collections import OrderedDict

import six

from jaeger_client.trace_state import TraceState
from six.moves import urllib_parse


def test_basic_init():
    trace_state = TraceState()
    assert isinstance(trace_state, TraceState)
    assert isinstance(trace_state._trace_state, OrderedDict)
    assert trace_state._encoder is None


def test_add_trace():
    trace_state = TraceState(operation_name="foo", trace_id="0123456789abcdef")
    trace_state.add("bar", "testing")
    trace_state.add("novalue")
    trace_state.add(None)
    assert trace_state._trace_state == OrderedDict([("bar", "testing"), ("foo", "0123456789abcdef")])
    trace_state.add("foo")
    assert trace_state._trace_state == OrderedDict([("foo", "0123456789abcdef"), ("bar", "testing")])


def test_add_trace_with_encoder():
    def encoder(value):
        return six.ensure_str(base64.urlsafe_b64encode(value.encode('utf-8'))).rstrip("=")

    encoded = encoder("0123456789abcdef"), encoder("testing")

    trace_state = TraceState(operation_name="foo", trace_id="0123456789abcdef", encoder=encoder)
    trace_state.add("bar", "testing")
    assert trace_state._trace_state["foo"] == encoded[0]
    assert trace_state._trace_state["bar"] == encoded[1]


def test_set_encoder():
    def encoder(v):
        return v

    trace_state = TraceState()
    assert trace_state._encoder is None
    trace_state.set_encoder(encoder)
    assert trace_state._encoder == encoder


def test_parse_from_header():
    trace_state = TraceState()
    header_data = "foo=0123456789abcdef,bar=testing,test=qwerty,garbage"
    trace_state.parse_from_header(header_data)
    assert trace_state._trace_state == OrderedDict(
        [("foo", "0123456789abcdef"), ("bar", "testing"), ("test", "qwerty")])


def test_get_formatted_header():
    trace_state = TraceState()
    assert trace_state.get_formatted_header() == ""
    trace_state.add("foo", "0123456789abcdef")
    trace_state.add("bar", "testing")
    trace_state.add("test", "qwerty")
    headers = trace_state.get_formatted_header(url_parse=False)
    formatted_headers = urllib_parse.quote(headers)
    assert headers == "test=qwerty,bar=testing,foo=0123456789abcdef"
    headers = trace_state.get_formatted_header()
    assert headers == formatted_headers


def test_init_with_data():
    trace_state = TraceState(
        operation_name="foo",
        trace_id="0123456789abcdef",
        header_values="bar=testing,test=qwerty,garbage"
    )
    assert len(trace_state._trace_state) == 3
    assert trace_state._trace_state == OrderedDict(
        [("foo", "0123456789abcdef"), ("bar", "testing"), ("test", "qwerty")])
