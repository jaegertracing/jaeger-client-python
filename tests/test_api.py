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

import unittest

from jaeger_client import ConstSampler, Tracer
from jaeger_client.reporter import NullReporter
from opentracing.harness.api_check import APICompatibilityCheckMixin


class APITest(unittest.TestCase, APICompatibilityCheckMixin):

    reporter = NullReporter()
    sampler = ConstSampler(True)
    _tracer = Tracer(
        service_name='test_service_1', reporter=reporter, sampler=sampler)

    def tracer(self):
        return APITest._tracer

    def test_binary_propagation(self):
        # TODO binary codecs are not implemented at the moment
        pass

    def is_parent(self, parent, span):
        return span.parent_id == getattr(parent, 'span_id', None)

    # NOTE: this overrides a method defined in ApiComaptibilityCheckMixin in
    # order to add the scope.close() call, which prevents the tracer from
    # leaving an active scope in thread local storage
    # TODO: remove after switching to opentracing-python 2.1.0, issue for
    # tracking the release:
    # https://github.com/opentracing/opentracing-python/issues/119
    def test_start_active_span(self):
        # the first usage returns a `Scope` that wraps a root `Span`
        tracer = self.tracer()
        scope = tracer.start_active_span('Fry')

        assert scope.span is not None
        if self.check_scope_manager():
            assert self.is_parent(None, scope.span)

        scope.close()
