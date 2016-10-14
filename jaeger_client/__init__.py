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

import sys

# This is because thrift for python doesn't have 'package_prefix'.
# The thrift compiled libraries refer to each other relative to their subdir.
import jaeger_client.thrift_gen as modpath
sys.path.append(modpath.__path__[0])

__version__ = '3.3.1'

from .tracer import Tracer  # noqa
from .config import Config  # noqa
from .span import Span  # noqa
from .span_context import SpanContext  # noqa
from .sampler import ConstSampler  # noqa
from .sampler import ProbabilisticSampler  # noqa
from .sampler import RateLimitingSampler  # noqa
from .sampler import RemoteControlledSampler  # noqa
