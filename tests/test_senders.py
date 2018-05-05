# Copyright (c) 2018 Uber Technologies, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import print_function


import mock
from tornado import ioloop

from jaeger_client import senders
from jaeger_client.local_agent_net import LocalAgentSender
from jaeger_client.thrift_gen.agent import Agent
from thrift.protocol import TCompactProtocol


def test_base_sender_create_io_loop_if_not_provided():

    sender = senders.Sender(host='mock', port=4242)

    assert sender.io_loop is not None
    assert isinstance(sender.io_loop, ioloop.IOLoop)

def test_udp_sender_instantiate_thrift_agent():

    sender = senders.UDPSender(host='mock', port=4242)

    assert sender.agent is not None
    assert isinstance(sender.agent, Agent.Client)


def test_udp_sender_intantiate_local_agent_channel():

    sender = senders.UDPSender(host='mock', port=4242)

    assert sender.channel is not None
    assert sender.channel.io_loop == sender.io_loop
    assert isinstance(sender.channel, LocalAgentSender)

def test_udp_sender_calls_agent_emitBatch_on_sending():

    test_data = {'foo': 'bar'}
    sender = senders.UDPSender(host='mock', port=4242)
    sender.agent = mock.Mock()

    sender.send(test_data)

    sender.agent.emitBatch.assert_called_once_with(test_data)


def test_udp_sender_implements_thrift_protocol_factory():

    sender = senders.UDPSender(host='mock', port=4242)

    assert callable(sender.getProtocol)
    protocol = sender.getProtocol(mock.MagicMock())
    assert isinstance(protocol, TCompactProtocol.TCompactProtocol)
