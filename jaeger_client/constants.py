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

from __future__ import absolute_import, unicode_literals, print_function

from . import __version__


# Max number of bits to use when generating random ID
MAX_ID_BITS = 64

# How often remotely controller sampler polls for sampling strategy
DEFAULT_SAMPLING_INTERVAL = 60

# How often remote reporter does a preemptive flush of its buffers
DEFAULT_FLUSH_INTERVAL = 1

# Name of the HTTP header used to encode trace ID
TRACE_ID_HEADER = b'uber-trace-id'

# Prefix for HTTP headers used to record baggage items
BAGGAGE_HEADER_PREFIX = b'uberctx-'

# The name of HTTP header or a TextMap carrier key which, if found in the
# carrier, forces the trace to be sampled as "debug" trace. The value of the
# header is recorded as the tag on the # root span, so that the trace can
# be found in the UI using this value as a correlation ID.
DEBUG_ID_HEADER_KEY = 'jaeger-debug-id'

JAEGER_CLIENT_VERSION = 'Python-%s' % __version__

# Tracer-scoped tag that tells the version of Jaeger client library
JAEGER_VERSION_TAG_KEY = 'jaeger.version'

# Tracer-scoped tag that contains the hostname
JAEGER_HOSTNAME_TAG_KEY = 'jaeger.hostname'

# the type of sampler that always makes the same decision.
SAMPLER_TYPE_CONST = 'const'

# the type of sampler that samples traces with a certain fixed probability.
SAMPLER_TYPE_PROBABILISTIC = 'probabilistic'

# the type of sampler that samples only up to a fixed number
# of traces per second.
# noinspection SpellCheckingInspection
SAMPLER_TYPE_RATE_LIMITING = 'ratelimiting'
