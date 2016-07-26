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
import fcntl
import socket
import struct
import time

from .metrics import Metrics


class ErrorReporter(object):
    """
    Reports errors by emitting metrics, and if logger is provided,
    logging the error message once every log_interval_minutes
    """

    def __init__(self, metrics, logger=None, log_interval_minutes=15):
        self.logger = logger
        self.log_interval_minutes = log_interval_minutes
        self.metrics = metrics or Metrics()
        self._last_error_reported_at = time.time()

    def error(self, name, count, *args):
        if self.metrics:
            self.metrics.count(name, count)

        if self.logger is None:
            return

        next_logging_deadline = \
            self._last_error_reported_at + (self.log_interval_minutes * 60)
        current_time = time.time()
        if next_logging_deadline >= current_time:
            # If we aren't yet at the next logging deadline
            return

        self.logger.error(*args)
        self._last_error_reported_at = current_time


def get_boolean(string, default):
    string = str(string).lower()
    if string in ['false', '0', 'none']:
        return False
    elif string in ['true', '1']:
        return True
    else:
        return default


def local_ip():
    """Get the local network IP of this machine"""
    try:
        ip = socket.gethostbyname(socket.gethostname())
    except IOError:
        ip = socket.gethostbyname('localhost')
    if ip.startswith('127.'):
        # Check eth0, eth1, eth2, en0, ...
        interfaces = [
            i + str(n) for i in ('eth', 'en', 'wlan') for n in xrange(3)
        ]  # :(
        for interface in interfaces:
            try:
                ip = interface_ip(interface)
                break
            except IOError:
                pass
    return ip


def interface_ip(interface):
    """Determine the IP assigned to us by the given network interface."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(
        fcntl.ioctl(
            sock.fileno(), 0x8915, struct.pack('256s', interface[:15])
        )[20:24]
    )
    # Explanation:
    # http://stackoverflow.com/questions/11735821/python-get-localhost-ip
    # http://stackoverflow.com/questions/24196932/how-can-i-get-the-ip-address-of-eth0-in-python
