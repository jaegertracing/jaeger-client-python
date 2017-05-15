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


class MetricsFactory(object):
    """Generates new metrics."""

    def __init__(self, count=None, gauge=None, timing=None, tags=None):
        """
        :param count: function (key, value) to emit counters
        :param gauge: function (key, value) to emit gauges
        :param timing: function (key, value) to emit timings
        :param tags: {k:v} dictionary
        """
        self._count = count
        self._gauge = gauge
        self._timing = timing
        self._tags = tags
        if not callable(self._count):
            self._count = None
        if not callable(self._gauge):
            self._gauge = None
        if not callable(self._timing):
            self._timing = None

    def counter(self, name, tags=None):
        """
        Generates a new counter from the given name and tags.
        :param name: name of the counter
        :param tags: tags for the counter
        :return: a callable function which takes the value to increase
        the counter by ie. def increment(value)
        """
        raise NotImplementedError

    def timer(self, name, tags=None):
        """
        Generates a new timer from the given name and tags.
        :param name: name of the timer
        :param tags: tags for the timer
        :return: a callable function which takes the duration to
        record ie. def record(duration)
        """
        raise NotImplementedError

    def gauge(self, name, tags=None):
        """
        Generates a new gauge from the given name and tags.
        :param name: name of the gauge
        :param tags: tags for the gauge
        :return: a callable function which takes the value to update
        the gauge with ie. def update(value)
        """
        raise NotImplementedError

    def _merge_tags(self, tags=None):
        if not self._tags:
            return tags
        tags_cpy = self._tags.copy()
        tags_cpy.update(tags)
        return tags_cpy


class NoopMetricsFactory(MetricsFactory):
    """Metrics factory that returns Metrics with Noop"""

    def __init__(self, tags=None):
        super(NoopMetricsFactory, self).__init__(
            tags=tags
        )

    def counter(self, name, tags=None):
        def increment(value):
            pass
        return increment

    def timer(self, name, tags=None):
        def record(value):
            pass
        return record

    def gauge(self, name, tags=None):
        def update(value):
            pass
        return update


class LegacyMetricsFactory(MetricsFactory):
    """A MetricsFactory wrapper around Metrics."""

    def __init__(self, metrics, tags=None):
        super(LegacyMetricsFactory, self).__init__(
            count=metrics.count,
            gauge=metrics.gauge,
            timing=metrics.timing,
            tags=tags
        )

    def counter(self, name, tags=None):
        key = self._get_key(name, self._merge_tags(tags))

        def increment(value):
            return self._count(key, value)
        return increment

    def timer(self, name, tags=None):
        key = self._get_key(name, self._merge_tags(tags))

        def record(value):
            return self._timing(key, value)
        return record

    def gauge(self, name, tags=None):
        key = self._get_key(name, self._merge_tags(tags))

        def update(value):
            return self._gauge(key, value)
        return update

    def _get_key(self, name, tags=None):
        key = name
        for k in sorted(tags.iterkeys()):
            key = key + '|' + str(k) + '=' + str(tags[k])
        return key


class Metrics(object):
    """Provides an abstraction of metrics reporting framework."""

    def __init__(self, count=None, gauge=None, timing=None):
        """
        :param count: function (key, value) to emit counters
        :param gauge: function (key, value) to emit gauges
        :param timing: function (key, value) to emit timings
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
