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
from __future__ import absolute_import

import sys
import socket
import logging
import tornado.gen
from six import reraise
from threadloop import ThreadLoop

from . import thrift
from .local_agent_net import LocalAgentSender
from thrift.protocol import TCompactProtocol

from jaeger_client.thrift_gen.agent import Agent


logger = logging.getLogger('jaeger_tracing')


class Sender(object):
    def __init__(self, io_loop=None, batch_size=10):
        from threading import Lock
        self._io_loop = io_loop or self._create_new_thread_loop()
        self._process_lock = Lock()
        self._process = None
        self._batch_size = batch_size
        self.spans = []

    @tornado.gen.coroutine
    def append(self, span):
        """
        Queue a span for subsequent submission calls to flush().
        If number of appended spans is equal to batch size, initiate flush().
        """
        spans_flushed = 0
        self.spans.append(span)

        if len(self.spans) == self._batch_size:
            spans_flushed = yield self.flush()

        raise tornado.gen.Return(spans_flushed)

    @property
    def span_count(self):
        return len(self.spans)

    @tornado.gen.coroutine
    def flush(self):
        """
        Flush spans, if any, if process has been set. Returns number of spans successfully flushed.
        """
        spans_sent = 0
        if self.spans:
            with self._process_lock:
                process = self._process
            if process:
                try:
                    spans_sent = yield self._batch_and_send(self.spans, self._process)
                finally:
                    self.spans = []
        raise tornado.gen.Return(spans_sent)

    @tornado.gen.coroutine
    def _batch_and_send(self, spans, process):
        """
        Batch spans and invokes send(), returning number of spans sent.
        Override with specific batching logic, if desired.
        """
        batch = thrift.make_jaeger_batch(spans=spans, process=process)
        yield self.send(batch)
        raise tornado.gen.Return(len(spans))

    @tornado.gen.coroutine
    def send(self, batch):
        """Send batch of spans to collector via desired transport."""
        raise NotImplementedError('This method should be implemented by subclasses')

    def set_process(self, service_name, tags, max_length):
        with self._process_lock:
            self._process = thrift.make_process(
                service_name=service_name, tags=tags, max_length=max_length,
            )

    def _create_new_thread_loop(self):
        """
        Create a daemonized thread that will run Tornado IOLoop.
        :return: the IOLoop backed by the new thread.
        """
        self._thread_loop = ThreadLoop()
        if not self._thread_loop.is_ready():
            self._thread_loop.start()
        return self._thread_loop._io_loop

    def getProtocol(self, transport):
        raise NotImplementedError('This method should be implemented by subclasses')


class UDPSender(Sender):
    def __init__(self, host, port, io_loop=None, agent=None, batch_size=10):
        super(UDPSender, self).__init__(io_loop=io_loop, batch_size=batch_size)
        self._host = host
        self._port = port
        self._channel = self._create_local_agent_channel(self._io_loop)
        self._agent = agent or Agent.Client(self._channel, self)

    @tornado.gen.coroutine
    def send(self, batch):
        """
        Send batch of spans out via thrift transport.
        """
        try:
            yield self._agent.emitBatch(batch)
        except socket.error as e:
            reraise(type(e),
                    type(e)('Failed to submit traces to jaeger-agent socket: {}'.format(e)),
                    sys.exc_info()[2])
        except Exception as e:
            reraise(type(e), type(e)('Failed to submit traces to jaeger-agent: {}'.format(e)),
                    sys.exc_info()[2])

    def _create_local_agent_channel(self, io_loop):
        """
        Create an out-of-process channel communicating to local jaeger-agent.
        Spans are submitted as SOCK_DGRAM Thrift, sampling strategy is polled
        via JSON HTTP.

        :param self: instance of Config
        """
        logger.info('Initializing Jaeger Tracer with UDP reporter')
        return LocalAgentSender(
            host=self._host,
            sampling_port=5778,
            reporting_port=self._port,
            io_loop=io_loop
        )

    # method for protocol factory
    def getProtocol(self, transport):
        """
        Implements Thrift ProtocolFactory interface
        :param: transport:
        :return: Thrift compact protocol
        """
        return TCompactProtocol.TCompactProtocol(transport)
