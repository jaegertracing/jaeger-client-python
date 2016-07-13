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

from jaeger_client import utils


class ConfigTests(unittest.TestCase):

    def check_boolean(self, string, default, correct):
        assert utils.get_boolean(string, default) == correct

    def test_get_false_boolean(self):
        self.check_boolean('false', 'asdf', False)

    def test_get_0_boolean(self):
        self.check_boolean('0', 'asdf', False)

    def test_get_true_boolean(self):
        self.check_boolean('true', 'qwer', True)

    def test_get_1_boolean(self):
        self.check_boolean('1', 'qwer', True)

    def test_get_unknown_boolean(self):
        self.check_boolean('zxcv', 'qwer', 'qwer')

    def test_get_None_boolean(self):
        self.check_boolean(None, 'qwer', False)

#    def test_error_reporter_doesnt_send_metrics_if_not_configured(self):
#        er = utils.ErrorReporter(False)
#        er.error('foo', 1)
#        assert not mock_metrics.count.called

    def test_error_reporter_sends_metrics_if_configured(self):
        mock_metrics = mock.MagicMock()
        er = utils.ErrorReporter(mock_metrics)
        er.error('foo', 1)
        assert mock_metrics.count.called_with('foo', 1)

    def test_error_reporter_doesnt_send_log_messages_if_before_deadline(self):
        mock_logger = mock.MagicMock()
        er = utils.ErrorReporter(None, logger=mock_logger, log_interval_minutes=1000)
        er.error('foo', 1)
        assert not mock_logger.error.called

    def test_error_reporter_sends_log_messages_if_after_deadline(self):
        mock_logger = mock.MagicMock()
        # 0 log interval means we're always after the deadline, so always log
        er = utils.ErrorReporter(None, logger=mock_logger, log_interval_minutes=0)
        er._last_error_reported_at=0
        er.error('foo', 1, 'error args')
        assert mock_logger.error.call_args == (('error args',),)


def test_local_ip_does_not_blow_up():
    import socket
    import jaeger_client.utils
    socket.gethostname()
    with mock.patch('socket.gethostbyname',
                    side_effect=[IOError(), '127.0.0.1']):
        jaeger_client.utils.local_ip()
