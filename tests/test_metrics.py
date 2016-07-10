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

from jaeger_client.metrics import Metrics


class MetricsTests(unittest.TestCase):

    def test_count_func_called(self):
        m = mock.MagicMock()
        metrics = Metrics(count=m)
        metrics.count('foo', 1)
        assert m.called_with('foo', 1)

    def test_gauge_func_called(self):
        m = mock.MagicMock()
        metrics = Metrics(gauge=m)
        metrics.gauge('foo', 1)
        assert m.call_args == (('foo', 1),)

    def test_count_func_noops_if_given_uncallable_count_found(self):
        metrics = Metrics(count=123)
        metrics.count('foo', 1)

    def test_gauge_func_noops_if_given_uncallable_gauge_found(self):
        metrics = Metrics(gauge=123)
        metrics.gauge('foo', 1)
