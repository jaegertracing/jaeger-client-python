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
from __future__ import division


from builtins import str
from past.utils import old_div
from builtins import object
class MetricsFactory(object):
    """Generates new metrics."""

    def _noop(self, *args):
        pass

    def create_counter(self, name, tags=None):
        """
        Generates a new counter from the given name and tags and returns
        a callable function used to increment the counter.
        :param name: name of the counter
        :param tags: tags for the counter
        :return: a callable function which takes the value to increase
        the counter by ie. def increment(value)
        """
        return self._noop

    def create_timer(self, name, tags=None):
        """
        Generates a new timer from the given name and tags and returns
        a callable function used to record a float duration in microseconds.
        :param name: name of the timer
        :param tags: tags for the timer
        :return: a callable function which takes the duration to
        record ie. def record(duration)
        """
        return self._noop

    def create_gauge(self, name, tags=None):
        """
        Generates a new gauge from the given name and tags and returns
        a callable function used to update the gauge.
        :param name: name of the gauge
        :param tags: tags for the gauge
        :return: a callable function which takes the value to update
        the gauge with ie. def update(value)
        """
        return self._noop


class LegacyMetricsFactory(MetricsFactory):
    """A MetricsFactory adapter for legacy Metrics class."""

    def __init__(self, metrics):
        self._metrics = metrics

    def create_counter(self, name, tags=None):
        key = self._get_key(name, tags)

        def increment(value):
            return self._metrics.count(key, value)
        return increment

    def create_timer(self, name, tags=None):
        key = self._get_key(name, tags)

        def record(value):
            # Convert microseconds to milliseconds for legacy
            return self._metrics.timing(key, old_div(value, 1000.0))
        return record

    def create_gauge(self, name, tags=None):
        key = self._get_key(name, tags)

        def update(value):
            return self._metrics.gauge(key, value)
        return update

    def _get_key(self, name, tags=None):
        if not tags:
            return name
        key = name
        for k in sorted(tags.keys()):
            key = key + '.' + str(k) + '_' + str(tags[k])
        return key


class Metrics(object):
    """
    Provides an abstraction of metrics reporting framework.
    This Class has been deprecated, please use MetricsFactory
    instead.
    """

    def __init__(self, count=None, gauge=None, timing=None):
        """
        :param count: function (key, value) to emit counters
        :param gauge: function (key, value) to emit gauges
        :param timing: function (key, value in milliseconds) to
            emit timings
        """
        self._count = count
        self._gauge = gauge
        self._timing = timing
        if not callable(self._count):
            self._count = None
        if not callable(self._gauge):
            self._gauge = None
        if not callable(self._timing):
            self._timing = None

    def count(self, key, value):
        if self._count:
            self._count(key, value)

    def timing(self, key, value):
        if self._timing:
            self._timing(key, value)

    def gauge(self, key, value):
        if self._gauge:
            self._gauge(key, value)
