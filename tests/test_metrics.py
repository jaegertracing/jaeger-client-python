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

from jaeger_client.metrics import MetricsFactory, Metrics,\
    LegacyMetricsFactory


def test_metrics_factory_noop():
    mf = MetricsFactory()
    mf.create_counter('foo')(1)
    mf.create_timer('foo')(1)
    mf.create_gauge('foo')(1)


def test_metrics_count_func_called():
    m = mock.MagicMock()
    metrics = Metrics(count=m)
    metrics.count('foo', 1)
    assert m.call_args == (('foo', 1),)


def test_metrics_timing_func_called():
    m = mock.MagicMock()
    metrics = Metrics(timing=m)
    metrics.timing('foo', 1)
    assert m.call_args == (('foo', 1),)


def test_metrics_gauge_func_called():
    m = mock.MagicMock()
    metrics = Metrics(gauge=m)
    metrics.gauge('foo', 1)
    assert m.call_args == (('foo', 1),)


def test_metrics_count_func_noops_if_given_uncallable_count_found():
    metrics = Metrics(count=123)
    metrics.count('foo', 1)


def test_metrics_timing_func_noops_if_given_uncallable_timing_found():
    metrics = Metrics(timing=123)
    metrics.timing('foo', 1)


def test_metrics_gauge_func_noops_if_given_uncallable_gauge_found():
    metrics = Metrics(gauge=123)
    metrics.gauge('foo', 1)


def test_legacy_metrics_factory():
    cm = mock.MagicMock()
    tm = mock.MagicMock()
    gm = mock.MagicMock()
    mf = LegacyMetricsFactory(Metrics(count=cm, timing=tm, gauge=gm))
    counter = mf.create_counter(name='foo', tags={'k':'v','a':'counter'})
    counter(1)
    assert cm.call_args == (('foo.a_counter.k_v', 1),)

    gauge = mf.create_gauge(name='bar', tags={'k':'v', 'a':'gauge'})
    gauge(2)
    assert gm.call_args == (('bar.a_gauge.k_v', 2),)

    timing = mf.create_timer(name='rawr', tags={'k':'v', 'a':'timer'})
    timing(3)
    assert tm.call_args == (('rawr.a_timer.k_v', 0.003),)

    mf = LegacyMetricsFactory(Metrics(timing=tm))
    timing = mf.create_timer(name='wow')
    timing(4)
    assert tm.call_args == (('wow', 0.004),), \
        'building a timer with no tags should work'


def test_legacy_metrics_factory_noop():
    mf = LegacyMetricsFactory(Metrics())
    counter = mf.create_counter(name='foo', tags={'a':'counter'})
    counter(1)

    gauge = mf.create_gauge(name='bar', tags={'a':'gauge'})
    gauge(2)

    timing = mf.create_timer(name='rawr', tags={'a':'timer'})
    timing(3)
