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

import time
import mock
import pytest

from jaeger_client.sampler import ProbabilisticSampler, ConstSampler, RateLimitingSampler


def test_probabilistic_sampler_errors():
    with pytest.raises(AssertionError):
        ProbabilisticSampler(-0.1)
    with pytest.raises(AssertionError):
        ProbabilisticSampler(1.1)


def test_probabilistic_sampler():
    sampler = ProbabilisticSampler(0.5)
    # probabilistic sampler defines max ID as 64bit long.
    # we hardcode that value here to make sure test is independent.
    id1 = 1L << 63  # second most significant bit, dividing full range in half
    assert id1 == 0x8000000000000000L
    assert sampler.is_sampled(id1-10)
    assert not sampler.is_sampled(id1+10)
    sampler.close()


def test_const_sampler():
    sampler = ConstSampler(True)
    assert sampler.is_sampled(1)
    assert sampler.is_sampled(1 << 63)
    sampler = ConstSampler(False)
    assert not sampler.is_sampled(1)
    assert not sampler.is_sampled(1 << 63)


def test_rate_limiting_sampler():
    sampler = RateLimitingSampler(2)
    # stop time by overwriting timestamp() function to always return the same time
    ts = time.time()
    sampler.last_tick = ts
    with mock.patch('jaeger_client.sampler.RateLimitingSampler.timestamp') \
            as mock_time:
        mock_time.side_effect = lambda: ts  # always return same time
        assert sampler.timestamp() == ts
        assert sampler.is_sampled(0), 'initial balance allows first item'
        assert sampler.is_sampled(0), 'initial balance allows second item'
        assert not sampler.is_sampled(0), 'initial balance exhausted'

        # move time 250ms forward, not enough credits to pay for one sample
        mock_time.side_effect = lambda: ts + 0.25
        assert not sampler.is_sampled(0), 'not enough time passed for full item'

        # move time 500ms forward, now enough credits to pay for one sample
        mock_time.side_effect = lambda: ts + 0.5
        assert sampler.is_sampled(0), 'enough time for new item'
        assert not sampler.is_sampled(0), 'no more balance'

        # move time 5s forward, enough to accumulate credits for 10 samples,
        # but it should still be capped at 2
        sampler.last_tick = ts  # reset the timer
        mock_time.side_effect = lambda: ts + 5
        assert sampler.is_sampled(0), 'enough time for new item'
        assert sampler.is_sampled(0), 'enough time for second new item'
        assert not sampler.is_sampled(0), 'but no further, since time is stopped'
        assert not sampler.is_sampled(0), 'but no further, since time is stopped'
        assert not sampler.is_sampled(0), 'but no further, since time is stopped'
    sampler.close()

def test_sample_equality():
    const1 = ConstSampler(True)
    const2 = ConstSampler(True)
    const3 = ConstSampler(False)
    assert const1 == const2
    assert const1 != const3

    prob1 = ProbabilisticSampler(rate=0.01)
    prob2 = ProbabilisticSampler(rate=0.01)
    prob3 = ProbabilisticSampler(rate=0.02)
    assert prob1 == prob2
    assert prob1 != prob3
    assert const1 != prob1

    rate1 = RateLimitingSampler(max_traces_per_second=0.01)
    rate2 = RateLimitingSampler(max_traces_per_second=0.01)
    rate3 = RateLimitingSampler(max_traces_per_second=0.02)
    assert rate1 == rate2
    assert rate1 != rate3
    assert rate1 != const1
    assert rate1 != prob1
