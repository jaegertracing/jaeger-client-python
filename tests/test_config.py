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
import os
import unittest
from jaeger_client import Config, ConstSampler, ProbabilisticSampler, RateLimitingSampler
from jaeger_client.reporter import NullReporter
from jaeger_client import constants


class ConfigTests(unittest.TestCase):

    def test_enabled(self):
        c = Config({'enabled': True}, service_name='x')
        assert c.enabled
        c = Config({'enabled': False}, service_name='x')
        assert not c.enabled

    def test_reporter_batch_size(self):
        c = Config({'reporter_batch_size': 12345}, service_name='x')
        assert c.reporter_batch_size == 12345
        c = Config({}, service_name='x')
        assert c.reporter_batch_size == 10

    def test_tags(self):
        os.environ['JAEGER_TAGS'] = 'a=b,c=d'
        c = Config({'tags': {'e': 'f'}}, service_name='x')
        assert c.tags == {'a': 'b', 'c': 'd', 'e': 'f'}
        c.create_tracer(NullReporter(), ConstSampler(True))

    def test_no_sampler(self):
        c = Config({}, service_name='x')
        assert c.sampler is None

    def test_const_sampler(self):
        c = Config({'sampler': {'type': 'const', 'param': True}},
                   service_name='x')
        assert type(c.sampler) is ConstSampler
        assert c.sampler.decision
        c = Config({'sampler': {'type': 'const', 'param': False}},
                   service_name='x')
        assert type(c.sampler) is ConstSampler
        assert not c.sampler.decision

    def test_probabilistic_sampler(self):
        with self.assertRaises(Exception):
            cfg = {'sampler': {'type': 'probabilistic', 'param': 'xx'}}
            _ = Config(cfg, service_name='x').sampler
        c = Config({'sampler': {'type': 'probabilistic', 'param': 0.5}},
                   service_name='x')
        assert type(c.sampler) is ProbabilisticSampler
        assert c.sampler.rate == 0.5

    def test_rate_limiting_sampler(self):
        with self.assertRaises(Exception):
            cfg = {'sampler': {'type': 'rate_limiting', 'param': 'xx'}}
            _ = Config(cfg, service_name='x').sampler
        c = Config({'sampler': {'type': 'rate_limiting', 'param': 1234}},
                   service_name='x')
        assert type(c.sampler) is RateLimitingSampler
        assert c.sampler.traces_per_second == 1234

    def test_bad_sampler(self):
        c = Config({'sampler': {'type': 'bad-sampler'}}, service_name='x')
        with self.assertRaises(ValueError):
            c.sampler.is_sampled(0)

    def test_agent_reporting_host(self):
        c = Config({}, service_name='x')
        assert c.local_agent_reporting_host == 'localhost'

        c = Config({'local_agent': {'reporting_host': 'jaeger.local'}}, service_name='x')
        assert c.local_agent_reporting_host == 'jaeger.local'

    def test_max_tag_value_length(self):
        c = Config({}, service_name='x')
        assert c.max_tag_value_length == constants.MAX_TAG_VALUE_LENGTH

        c = Config({'max_tag_value_length': 333}, service_name='x')
        assert c.max_tag_value_length == 333

        t = c.create_tracer(NullReporter(), ConstSampler(True))
        assert t.max_tag_value_length == 333

    def test_propagation(self):
        c = Config({}, service_name='x')
        assert c.propagation == {}

        c = Config({'propagation': 'b3'}, service_name='x')
        assert len(c.propagation) == 1
