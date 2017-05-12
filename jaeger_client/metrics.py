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
        self.count = count
        self.gauge = gauge
        self.timing = timing
        self.tags = tags

    def counter(self, name, tags=None):
        return Counter(name, self.merge_tags(tags), self.count)

    def timer(self, name, tags=None):
        return Timer(name, self.merge_tags(tags), self.timing)

    def gauge(self, name, tags=None):
        return Gauge(name, self.merge_tags(tags), self.gauge)

    def merge_tags(self, tags=None):
        if not self.tags:
            return tags
        tags_cpy = self.tags.copy()
        tags_cpy.update(tags)
        return tags_cpy


class Counter(object):
    def __init__(self, name, tags=None, count=None):
        self.name = name
        self.tags = tags

        self._count = count
        if not callable(self._count):
            self._count = None

    def increment(self, value):
        if self._count:
            self._count(self.name, value, self.tags)


class Timer(object):
    def __init__(self, name, tags=None, timing=None):
        self.name = name
        self.tags = tags

        self._timing = timing
        if not callable(self._timing):
            self._timing = None

    def record(self, value):
        if self._timing:
            self._timing(self.name, value, self.tags)


class Gauge(object):
    def __init__(self, name, tags=None, gauge=None):
        self.name = name
        self.tags = tags

        self._gauge = gauge
        if not callable(self._gauge):
            self._gauge = None

    def update(self, value):
        if self._gauge:
            self._gauge(self.name, value, self.tags)
