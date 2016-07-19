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
import unittest
from jaeger_client import Config, ConstSampler, ProbabilisticSampler, RateLimitingSampler


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
        assert c.sampler.credits_per_second == 1234

    def test_bad_sampler(self):
        c = Config({'sampler': {'type': 'bad-sampler'}}, service_name='x')
        with self.assertRaises(ValueError):
            c.sampler.is_sampled(0)
