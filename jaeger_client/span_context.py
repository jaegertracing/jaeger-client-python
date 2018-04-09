# Copyright (c) 2016 Uber Technologies, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import absolute_import

import opentracing


class SpanContext(opentracing.SpanContext):
    __slots__ = ['trace_id', 'span_id', 'parent_id', 'flags',
                 '_baggage', '_debug_id', '_sampling_finalized']

    """Implements opentracing.SpanContext"""
    def __init__(self, trace_id, span_id, parent_id, flags, baggage=None, sampling_finalized=False):
        self.trace_id = trace_id
        self.span_id = span_id
        self.parent_id = parent_id or None
        self.flags = flags
        self._baggage = baggage or opentracing.SpanContext.EMPTY_BAGGAGE
        self._debug_id = None

        # This field exists to help distinguish between when a span can have a properly
        # correlated operation name -> sampling rate mapping, and when it cannot.
        # Adaptive sampling uses the operation name of a span to correlate it with
        # a sampling rate.  If an operation name is set on a span after the span's creation
        # then adaptive sampling cannot associate the operation name with the proper sampling rate.
        # In order to correct this we allow a span to be written to, so that we can re-sample
        # it in the case that an operation name is set after span creation. Situations
        # where a span context's sampling decision is finalized include:
        #  - it has inherited the sampling decision from its parent
        #  - its debug flag is set via the sampling.priority tag
        #  - it is finish()-ed
        #  - setOperationName is called
        #  - it is used as a parent for another span
        #  - its context is serialized using injectors
        self._sampling_finalized = sampling_finalized

    @property
    def baggage(self):
        return self._baggage or opentracing.SpanContext.EMPTY_BAGGAGE

    def with_baggage_item(self, key, value):
        baggage = dict(self._baggage)
        baggage[key] = value
        return SpanContext(
            trace_id=self.trace_id,
            span_id=self.span_id,
            parent_id=self.parent_id,
            flags=self.flags,
            baggage=baggage,
            sampling_finalized=self.sampling_finalized
        )

    @property
    def is_debug_id_container_only(self):
        return not self.trace_id and self._debug_id is not None

    @property
    def debug_id(self):
        return self._debug_id

    @staticmethod
    def with_debug_id(debug_id):
        ctx = SpanContext(
            trace_id=None, span_id=None, parent_id=None, flags=None
        )
        ctx._debug_id = debug_id
        return ctx

    @property
    def sampling_finalized(self):
        return self._sampling_finalized

    def finalize_sampling(self):
        self._sampling_finalized = True
