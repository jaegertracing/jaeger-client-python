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

import mock
import unittest

from jaeger_client.TUDPTransport import TUDPTransport


class TUDPTransportTests(unittest.TestCase):
    def setUp(self):
        self.t = TUDPTransport('127.0.0.1', 12345)

    def test_constructor_blocking(self):
        t = TUDPTransport('127.0.0.1', 12345, blocking=True)
        assert t.transport_sock.gettimeout() == None

    def test_constructor_nonblocking(self):
        t = TUDPTransport('127.0.0.1', 12345, blocking=False)
        assert t.transport_sock.gettimeout() == 0

    def test_write(self):
        self.t.write('hello')

    def test_isopen_when_open(self):
        assert self.t.isOpen() == True

    def test_isopen_when_closed(self):
        self.t.close()
        assert self.t.isOpen() == False

    def test_close(self):
        self.t.close()
        with self.assertRaises(Exception):
            # Something bad should happen if we send on a closed socket..
            self.t.write('hello')
