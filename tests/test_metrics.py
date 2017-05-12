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

from jaeger_client.metrics import MetricsFactory, Counter, Timer, Gauge


class MetricsTests(unittest.TestCase):

    def test_count_func_called(self):
        m = mock.MagicMock()
        counter = Counter(name='foo', tags=None, count=m)
        counter.increment(1)
        assert m.called_with('foo', 1, None)

    def test_gauge_func_called(self):
        m = mock.MagicMock()
        gauge = Gauge(name='foo', tags=None, gauge=m)
        gauge.update(1)
        assert m.called_with('foo', 1, None)

    def test_timing_func_called(self):
        m = mock.MagicMock()
        timer = Timer(name='foo', tags=None, timing=m)
        timer.record(1)
        assert m.called_with('foo', 1, None)

    def test_count_func_noops_if_given_uncallable_count_found(self):
        counter = Counter(name='foo', tags=None, count=123)
        counter.increment(1)

    def test_gauge_func_noops_if_given_uncallable_gauge_found(self):
        gauge = Gauge(name='foo', tags=None, gauge=123)
        gauge.update(1)

    def test_timing_func_noops_if_given_uncallable_timing_found(self):
        timer = Timer(name='foo', tags=None, timing=123)
        timer.record(1)

    def test_tags(self):
        m = mock.MagicMock()
        mf = MetricsFactory(count=m, tags={'k':'v', 'a':'b'})
        counter = mf.counter(name='foo', tags={'a':'c'})
        counter.increment(1)
        assert m.called_with('foo', 1, {'k':'v', 'a':'c'}), \
            'metric tag should overwrite global tag'

        mf = MetricsFactory(count=m)
        counter = mf.counter(name='foo', tags={'a':'c'})
        counter.increment(1)
        assert m.called_with('foo', 1, {'a':'c'})
