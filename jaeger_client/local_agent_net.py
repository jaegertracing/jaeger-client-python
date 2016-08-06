# Copyright (c) 2016 Uber Technologies, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

from __future__ import absolute_import
from threadloop import ThreadLoop
import tornado
import tornado.httpclient
from tornado.httputil import url_concat
import json
from .TUDPTransport import TUDPTransport
from jaeger_client.thrift_gen.sampling import (
    SamplingManager as sampling_manager  # TODO why need to rename
)
from concurrent.futures import Future
from thrift.transport.TTransport import TBufferedTransport


class LocalAgentHTTP(object):

    def __init__(self, host, port):
        self.agent_http_host = host
        self.agent_http_port = int(port)

    def request_sampling_strategy(self, service_name, timeout):
        http_client = tornado.httpclient.AsyncHTTPClient(
            defaults=dict(request_timeout=timeout))
        # Properly url encode the params
        url = url_concat(
            'http://%s:%d/' % (self.agent_http_host, self.agent_http_port),
            [('service', service_name)])
        return http_client.fetch(url)


class LocalAgentSender(TBufferedTransport):
    """
    LocalAgentSender implements a everything necessary to communicate with
    local jaeger-agent. This class is designed to work in tornado and
    non-tornado environments. If in torndado, pass in the ioloop, if not
    then LocalAgentSender will create one for itself.

    NOTE: LocalAgentSender derives from TBufferedTransport. This will buffer
    up all written data until flush() is called. Flush gets called at the
    end of the batch span submission call.
    """

    def __init__(self, host, sampling_port, reporting_port, io_loop=None):
        # IOLoop
        self._thread_loop = None
        self.io_loop = io_loop or self._create_new_thread_loop()

        # http sampling
        self.local_agent_http = LocalAgentHTTP(host, sampling_port)

        # udp reporting - this will only get written to after our flush() call.
        # We are buffering things up because we are a TBufferedTransport.
        udp = TUDPTransport(host, reporting_port)
        TBufferedTransport.__init__(self, udp)

    def _create_new_thread_loop(self):
        """
        Create a daemonized thread that will run Tornado IOLoop.
        :return: the IOLoop backed by the new thread.
        """
        self._thread_loop = ThreadLoop()
        if not self._thread_loop.is_ready():
            self._thread_loop.start()
        return self._thread_loop._io_loop

    def readFrame(self):
        """Empty read frame that is never ready"""
        return Future()

    # Pass-through for the http
    def request_sampling_strategy(self, service_name, timeout):
        return self.local_agent_http.request_sampling_strategy(
            service_name, timeout)


def parse_sampling_strategy(body):
    response = json.loads(body)
    s_type = response['strategyType']
    if s_type == sampling_manager.SamplingStrategyType.PROBABILISTIC:
        sampling_rate = response['probabilisticSampling']['samplingRate']
        if 0 <= sampling_rate <= 1.0:
            from jaeger_client.sampler import ProbabilisticSampler
            return ProbabilisticSampler(rate=sampling_rate)
        else:
            raise ValueError(
                'Probabilistic sampling rate not in [0, 1] range: %s' %
                sampling_rate)
    elif s_type == sampling_manager.SamplingStrategyType.RATE_LIMITING:
        mtps = response['rateLimitingSampling']['maxTracesPerSecond']
        if 0 <= mtps < 500:
            from jaeger_client.sampler import RateLimitingSampler
            return RateLimitingSampler(max_traces_per_second=mtps)
        else:
            raise ValueError(
                'Rate limiting parameter not in [0, 500] range: %s' % mtps)
    else:
        raise ValueError('Unsupported sampling strategy type: %s' % s_type)
