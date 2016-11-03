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

from jaeger_client.sampler import (
    Sampler,
    ConstSampler,
    ProbabilisticSampler,
    RateLimitingSampler,
    RemoteControlledSampler,
    GuaranteedThroughputProbabilisticSampler,
    AdaptiveSampler,
    DEFAULT_SAMPLING_PROBABILITY,
)

MAX_INT = 1L << 63

def get_tags(type, param):
    return {
        'sampler.type': type,
        'sampler.param': param,
    }

def test_abstract_sampler_errors():
    sampler = Sampler()
    with pytest.raises(NotImplementedError):
        sampler.is_sampled(trace_id=123)
    with pytest.raises(NotImplementedError):
        sampler.close()


def test_probabilistic_sampler_errors():
    with pytest.raises(AssertionError):
        ProbabilisticSampler(-0.1)
    with pytest.raises(AssertionError):
        ProbabilisticSampler(1.1)


def test_probabilistic_sampler():
    sampler = ProbabilisticSampler(0.5)
    assert MAX_INT == 0x8000000000000000L
    sampled, tags = sampler.is_sampled(MAX_INT-10)
    assert sampled
    assert tags == get_tags('probabilistic', 0.5)
    sampled, _ = sampler.is_sampled(MAX_INT+10)
    assert not sampled
    sampler.close()
    assert '%s' % sampler == 'ProbabilisticSampler(0.5)'


def test_const_sampler():
    sampler = ConstSampler(True)
    assert sampler.is_sampled(1)
    assert sampler.is_sampled(MAX_INT)
    sampler = ConstSampler(False)
    sampled, tags = sampler.is_sampled(1)
    assert not sampled
    sampled, tags = sampler.is_sampled(MAX_INT)
    assert not sampled
    assert tags == get_tags('const', False)
    assert '%s' % sampler == 'ConstSampler(False)'


def test_rate_limiting_sampler():
    sampler = RateLimitingSampler(2)
    # stop time by overwriting timestamp() function to always return
    # the same time
    ts = time.time()
    sampler.last_tick = ts
    with mock.patch('jaeger_client.sampler.RateLimitingSampler.timestamp') \
            as mock_time:
        mock_time.side_effect = lambda: ts  # always return same time
        assert sampler.timestamp() == ts
        assert sampler.is_sampled(0), 'initial balance allows first item'
        assert sampler.is_sampled(0), 'initial balance allows second item'
        sampled, _ = sampler.is_sampled(0)
        assert not sampled, 'initial balance exhausted'

        # move time 250ms forward, not enough credits to pay for one sample
        mock_time.side_effect = lambda: ts + 0.25
        sampled, _ = sampler.is_sampled(0)
        assert not sampled, 'not enough time passed for full item'

        # move time 500ms forward, now enough credits to pay for one sample
        mock_time.side_effect = lambda: ts + 0.5
        assert sampler.is_sampled(0), 'enough time for new item'
        sampled, _ = sampler.is_sampled(0)
        assert not sampled, 'no more balance'

        # move time 5s forward, enough to accumulate credits for 10 samples,
        # but it should still be capped at 2
        sampler.last_tick = ts  # reset the timer
        mock_time.side_effect = lambda: ts + 5
        assert sampler.is_sampled(0), 'enough time for new item'
        assert sampler.is_sampled(0), 'enough time for second new item'
        for i in range(0, 3):
            sampled, tags = sampler.is_sampled(0)
            assert not sampled, 'but no further, since time is stopped'
        assert tags == get_tags('ratelimiting', 2)
    sampler.close()
    assert '%s' % sampler == 'RateLimitingSampler(2)'

    # Test with rate limit of less than 1 second
    sampler = RateLimitingSampler(0.1)
    ts = time.time()
    sampler.last_tick = ts
    with mock.patch('jaeger_client.sampler.RateLimitingSampler.timestamp') \
            as mock_time:
        mock_time.side_effect = lambda: ts  # always return same time
        assert sampler.timestamp() == ts
        sampled, _ = sampler.is_sampled(0)
        assert not sampled

        # move time 110ms forward, enough credits to pay for one sample
        mock_time.side_effect = lambda: ts + 0.11
        assert sampler.is_sampled(0)
    sampler.close()
    assert '%s' % sampler == 'RateLimitingSampler(0.1)'


def test_guaranteed_throughput_probabilistic_sampler():
    sampler = GuaranteedThroughputProbabilisticSampler('op', 2, 0.5)
    sampled, tags = sampler.is_sampled(MAX_INT-10)
    assert sampled
    assert tags == get_tags('probabilistic', 0.5)
    sampled, tags = sampler.is_sampled(MAX_INT+10)
    assert sampled
    assert tags == get_tags('lowerbound', 0.5)
    sampled, _ = sampler.is_sampled(MAX_INT+10)
    assert not sampled
    assert '%s' % sampler == 'GuaranteedThroughputProbabilisticSampler(op, 0.5, 2)'

    sampler.update(3, 0.51)
    sampled, tags = sampler.is_sampled(MAX_INT-10)
    assert sampled
    assert tags == get_tags('probabilistic', 0.51)
    sampled, tags = sampler.is_sampled(MAX_INT+(MAX_INT/4))
    assert sampled
    assert tags == get_tags('lowerbound', 0.51)

    assert '%s' % sampler == 'GuaranteedThroughputProbabilisticSampler(op, 0.51, 3)'
    sampler.close()


def test_adaptive_sampler():
    strategies = {
        "defaultSamplingProbability":0.51,
        "defaultLowerBoundTracesPerSecond":3,
        "perOperationStrategies":
        [
            {
                "operation":"op",
                "probabilisticSampling":{
                    "samplingRate":0.5
                }
            }
        ]
    }
    sampler = AdaptiveSampler(strategies, 2)
    sampled, tags = sampler.is_sampled(MAX_INT-10, 'op')
    assert sampled
    assert tags == get_tags('probabilistic', 0.5)

    # This operation is seen for the first time by the sampler
    sampled, tags = sampler.is_sampled(MAX_INT-10, "new_op")
    assert sampled
    assert tags == get_tags('probabilistic', 0.51)
    sampled, tags = sampler.is_sampled(MAX_INT+(MAX_INT/4), "new_op")
    assert sampled
    assert tags == get_tags('lowerbound', 0.51)

    # This operation is seen for the first time by the sampler but surpasses
    # max_operations of 2. The default probabilistic sampler will be used
    sampled, tags = sampler.is_sampled(MAX_INT-10, "new_op_2")
    assert sampled
    assert tags == get_tags('probabilistic', 0.51)
    sampled, _ = sampler.is_sampled(MAX_INT+(MAX_INT/4), "new_op_2")
    assert not sampled
    assert '%s' % sampler == 'AdaptiveSampler(0.51, 3, 2)'

    # Update the strategies
    strategies = {
        "defaultSamplingProbability":0.52,
        "defaultLowerBoundTracesPerSecond":4,
        "perOperationStrategies":
        [
            {
                "operation":"op",
                "probabilisticSampling":{
                    "samplingRate":0.52
                }
            },
            {
                "operation":"new_op_3",
                "probabilisticSampling":{
                    "samplingRate":0.53
                }
            }
        ]
    }
    sampler.update(strategies)

    # The probability for op has been updated
    sampled, tags = sampler.is_sampled(MAX_INT-10, 'op')
    assert sampled
    assert tags == get_tags('probabilistic', 0.52)

    # A new operation has been added
    sampled, tags = sampler.is_sampled(MAX_INT-10, 'new_op_3')
    assert sampled
    assert tags == get_tags('probabilistic', 0.53)
    assert '%s' % sampler == 'AdaptiveSampler(0.52, 4, 2)'

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


def test_remotely_controlled_sampler():
    sampler = RemoteControlledSampler(
        channel=mock.MagicMock(),
        service_name='x'
    )
    sampled, tags = sampler.is_sampled(1)
    assert sampled
    assert tags == get_tags('probabilistic', DEFAULT_SAMPLING_PROBABILITY)

    init_sampler = mock.MagicMock()
    init_sampler.is_sampled = mock.MagicMock()
    channel = mock.MagicMock()
    channel.io_loop = None
    sampler = RemoteControlledSampler(
        channel=channel,
        service_name='x',
        init_sampler=init_sampler,
        logger=mock.MagicMock(),
    )
    assert init_sampler.is_sampled.call_count == 1

    sampler.is_sampled(1)
    assert init_sampler.is_sampled.call_count == 2

    sampler.io_loop = mock.MagicMock()
    # noinspection PyProtectedMember
    sampler._init_polling()
    # noinspection PyProtectedMember
    sampler._delayed_polling()
    sampler.close()


def test_parse_sampling_strategy():
    sampler = RemoteControlledSampler(
        channel=mock.MagicMock(),
        service_name='x',
        max_operations=10
    )
    s, strategies = sampler.parse_sampling_strategy(None, '{"strategyType":0,"probabilisticSampling":{"samplingRate":0.001}}')
    assert '%s' % s == 'ProbabilisticSampler(0.001)'
    assert not strategies

    with pytest.raises(ValueError):
        sampler.parse_sampling_strategy(None,'{"strategyType":0,"probabilisticSampling":{"samplingRate":2}}')

    s, strategies = sampler.parse_sampling_strategy(None, '{"strategyType":1,"rateLimitingSampling":{"maxTracesPerSecond":10}}')
    assert '%s' % s == 'RateLimitingSampler(10)'
    assert not strategies

    with pytest.raises(ValueError):
        sampler.parse_sampling_strategy(None, '{"strategyType":1,"rateLimitingSampling":{"maxTracesPerSecond":-10}}')

    with pytest.raises(ValueError):
        sampler.parse_sampling_strategy(None, '{"strategyType":2}')

    response = """
    {
        "strategyType":1,
        "operationSampling":
        {
            "defaultSamplingProbability":0.001,
            "defaultLowerBoundTracesPerSecond":2,
            "perOperationStrategies":
            [
                {
                    "operation":"op",
                    "probabilisticSampling":{
                        "samplingRate":0.002
                    }
                }
            ]
        }
    }
    """
    s, strategies = sampler.parse_sampling_strategy(None, response)
    assert '%s' % s == 'AdaptiveSampler(0.001, 2, 10)'
    assert strategies

    existing_strategies = {
        "defaultSamplingProbability":0.51,
        "defaultLowerBoundTracesPerSecond":3,
        "perOperationStrategies":
            [
                {
                    "operation":"op",
                    "probabilisticSampling":{
                        "samplingRate":0.5
                    }
                }
            ]
    }
    existing_sampler = AdaptiveSampler(existing_strategies, 2)
    assert '%s' % existing_sampler == 'AdaptiveSampler(0.51, 3, 2)'

    s, strategies = sampler.parse_sampling_strategy(existing_sampler, response)
    assert '%s' % existing_sampler == 'AdaptiveSampler(0.51, 3, 2)'
    assert strategies
