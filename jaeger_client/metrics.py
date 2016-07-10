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


class Metrics(object):
    """Provides an abstraction of metrics reporting framework."""

    # TODO do we want to automatically include host name?
    prefix = 'jaeger'

    TRACES_STARTED_SAMPLED = '%s.traces-started.sampled' % prefix
    """Number of traces started by this tracer as sampled"""

    TRACES_STARTED_NOT_SAMPLED = '%s.traces-started.not-sampled' % prefix
    """Number of traces started by this tracer as not sampled"""

    TRACES_JOINED_SAMPLED = '%s.traces-joined.sampled' % prefix
    """Number of externally started sampled traces this tracer joined"""

    TRACES_JOINED_NOT_SAMPLED = '%s.traces-joined.not-sampled' % prefix
    """Number of externally started non-sampled traces this tracer joined"""

    SPANS_SAMPLED = '%s.spans.sampled' % prefix
    """Number of sampled spans started/finished by this tracer"""

    SPANS_NOT_SAMPLED = '%s.spans.not-sampled' % prefix
    """Number of not-sampled spans started/finished by this tracer"""

    TRACER_DECODING_ERRORS = '%s.decoding.errors' % prefix
    """Number of errors decoding tracing context"""

    REPORTER_SUCCESS = '%s.spans.reported' % prefix
    """Number of spans successfully reported"""

    REPORTER_FAILURE = '%s.spans.failed' % prefix
    """Number of spans in failed attempts to report"""

    REPORTER_DROPPED = '%s.spans.dropped' % prefix
    """Number of spans dropped from the reporter"""

    REPORTER_SOCKET = '%s.spans.socket_error' % prefix
    """Number of spans dropped due to socket error"""

    REPORTER_QUEUE_LENGTH = '%s.queue_length' % prefix
    """Current number of spans in the reporter queue"""

    SAMPLER_ERRORS = '%s.sampler.errors' % prefix
    """Number of times the Sampler failed to retrieve sampling strategy"""

    def __init__(self, count=None, gauge=None):
        """
        :param count: function (key, value) to emit counters
        :param gauge: function (key, value) to emit gauges
        """
        self._count = count
        self._gauge = gauge
        if not callable(self._count):
            self._count = None
        if not callable(self._gauge):
            self._gauge = None

    def count(self, key, value):
        if self._count:
            self._count(key, value)
        # print('count', key, value)

    def gauge(self, key, value):
        if self._gauge:
            self._gauge(key, value)
        # print('gauge', key, value)
