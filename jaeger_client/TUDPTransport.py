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
import logging

from thrift.transport.TTransport import TTransportBase
import socket

logger = logging.getLogger('jaeger_tracing')


class TUDPTransport(TTransportBase, object):
    """
    TUDPTransport implements just enough of the tornado transport interface
    to work for blindly sending UDP packets.
    """
    def __init__(self, host, port, blocking=False):
        self.transport_host = host
        self.transport_port = port
        self.transport_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if blocking:
            blocking = 1
        else:
            blocking = 0
        self.transport_sock.setblocking(blocking)

    def write(self, buf):
        """Raw write to the UDP socket."""
        return self.transport_sock.sendto(
            buf,
            (self.transport_host, self.transport_port)
        )

    def isOpen(self):
        """
        isOpen for UDP is always true (there is no connection) as long
        as we have a sock
        """
        return self.transport_sock is not None

    def close(self):
        self.transport_sock.close()
        self.transport_sock = None
