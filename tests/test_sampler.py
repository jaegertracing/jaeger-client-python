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
    sampled, _ = sampler.is_sampled(1)
    assert sampled
    sampled, _ = sampler.is_sampled(MAX_INT)
    assert sampled
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
        sampled, _ = sampler.is_sampled(0)
        assert sampled, 'initial balance allows first item'
        sampled, _ = sampler.is_sampled(0)
        assert sampled, 'initial balance allows second item'
        sampled, _ = sampler.is_sampled(0)
        assert not sampled, 'initial balance exhausted'

        # move time 250ms forward, not enough credits to pay for one sample
        mock_time.side_effect = lambda: ts + 0.25
        sampled, _ = sampler.is_sampled(0)
        assert not sampled, 'not enough time passed for full item'

        # move time 500ms forward, now enough credits to pay for one sample
        mock_time.side_effect = lambda: ts + 0.5
        sampled, _ = sampler.is_sampled(0)
        assert sampled, 'enough time for new item'
        sampled, _ = sampler.is_sampled(0)
        assert not sampled, 'no more balance'

        # move time 5s forward, enough to accumulate credits for 10 samples,
        # but it should still be capped at 2
        sampler.last_tick = ts  # reset the timer
        mock_time.side_effect = lambda: ts + 5
        sampled, _ = sampler.is_sampled(0)
        assert sampled, 'enough time for new item'
        sampled, _ = sampler.is_sampled(0)
        assert sampled, 'enough time for second new item'
        for i in range(0, 3):
            sampled, tags = sampler.is_sampled(0)
            assert not sampled, 'but no further, since time is stopped'
        assert tags == get_tags('ratelimiting', 2)
    sampler.close()
    assert '%s' % sampler == 'RateLimitingSampler(2)'

    # Test with rate limit of greater than 1 second
    sampler = RateLimitingSampler(0.1)
    ts = time.time()
    sampler.last_tick = ts
    with mock.patch('jaeger_client.sampler.RateLimitingSampler.timestamp') \
            as mock_time:
        mock_time.side_effect = lambda: ts  # always return same time
        assert sampler.timestamp() == ts
        sampled, _ = sampler.is_sampled(0)
        assert sampled, 'initial balance allows first item'
        sampled, _ = sampler.is_sampled(0)
        assert not sampled, 'initial balance exhausted'

        # move time 11s forward, enough credits to pay for one sample
        mock_time.side_effect = lambda: ts + 11
        sampled, _ = sampler.is_sampled(0)
        assert sampled
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


def test_sampler_equality():
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


# noinspection PyProtectedMember
def test_sampling_request_callback():
    channel = mock.MagicMock()
    channel.io_loop = mock.MagicMock()
    error_reporter = mock.MagicMock()
    error_reporter.error = mock.MagicMock()
    sampler = RemoteControlledSampler(
        channel=channel,
        service_name='x',
        error_reporter=error_reporter,
        max_operations=10,
    )

    return_value = mock.MagicMock()
    return_value.exception = lambda *args: False

    probabilistic_strategy = """
    {
        "strategyType":0,
        "probabilisticSampling":
        {
            "samplingRate":0.002
        }
    }
    """

    return_value.result = lambda *args: \
        type('obj', (object,), {'body': probabilistic_strategy})()
    sampler._sampling_request_callback(return_value)
    assert '%s' % sampler.sampler == 'ProbabilisticSampler(0.002)', 'sampler should have changed to probabilistic'
    prev_sampler = sampler.sampler

    sampler._sampling_request_callback(return_value)
    assert prev_sampler is sampler.sampler, "strategy hasn't changed so sampler should not change"

    adaptive_sampling_strategy = """
    {
        "strategyType":0,
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
    return_value.result = lambda *args: \
        type('obj', (object,), {'body': adaptive_sampling_strategy})()
    sampler._sampling_request_callback(return_value)
    assert '%s' % sampler.sampler == 'AdaptiveSampler(0.001, 2, 10)', 'sampler should have changed to adaptive'
    prev_sampler = sampler.sampler

    sampler._sampling_request_callback(return_value)
    assert prev_sampler is sampler.sampler, "strategy hasn't changed so sampler should not change"

    return_value.exception = lambda *args: True
    sampler._sampling_request_callback(return_value)
    assert error_reporter.error.call_count == 1
    assert prev_sampler is sampler.sampler, 'error fetching strategy should not update the sampler'

    return_value.exception = lambda *args: False
    return_value.result = lambda *args: type('obj', (object,), {'body': 'bad_json'})()

    sampler._sampling_request_callback(return_value)
    assert error_reporter.error.call_count == 2
    assert prev_sampler is sampler.sampler, 'error updating sampler should not update the sampler'

    return_value.result = lambda *args: \
        type('obj', (object,), {'body': probabilistic_strategy})()
    sampler._sampling_request_callback(return_value)
    assert '%s' % sampler.sampler == 'ProbabilisticSampler(0.002)', 'updating sampler from adaptive to probabilistic should work'

    sampler.close()


probabilistic_sampler = ProbabilisticSampler(0.002)
other_probabilistic_sampler = ProbabilisticSampler(0.003)
rate_limiting_sampler = RateLimitingSampler(10)
other_rate_limiting_sampler = RateLimitingSampler(20)

@pytest.mark.parametrize("response,init_sampler,expected_sampler,err_count,err_msg,reference_equivalence", [
    (
        {"strategyType":0,"probabilisticSampling":{"samplingRate":0.003}},
        probabilistic_sampler,
        other_probabilistic_sampler,
        0,
        'sampler should update to new probabilistic sampler',
        False,
    ),
    (
        {"strategyType":0,"probabilisticSampling":{"samplingRate":400}},
        probabilistic_sampler,
        probabilistic_sampler,
        1,
        'sampler should remain the same if strategy is invalid',
        True,
    ),
    (
        {"strategyType":0,"probabilisticSampling":{"samplingRate":0.002}},
        probabilistic_sampler,
        probabilistic_sampler,
        0,
        'sampler should remain the same with the same strategy',
        True,
    ),
    (
        {"strategyType":1,"rateLimitingSampling":{"maxTracesPerSecond":10}},
        probabilistic_sampler,
        rate_limiting_sampler,
        0,
        'sampler should update to new rate limiting sampler',
        False,
    ),
    (
        {"strategyType":1,"rateLimitingSampling":{"maxTracesPerSecond":10}},
        rate_limiting_sampler,
        rate_limiting_sampler,
        0,
        'sampler should remain the same with the same strategy',
        True,
    ),
    (
        {"strategyType":1,"rateLimitingSampling":{"maxTracesPerSecond":-10}},
        rate_limiting_sampler,
        rate_limiting_sampler,
        1,
        'sampler should remain the same if strategy is invalid',
        True,
    ),
    (
        {"strategyType":1,"rateLimitingSampling":{"maxTracesPerSecond":20}},
        rate_limiting_sampler,
        other_rate_limiting_sampler,
        0,
        'sampler should update to new rate limiting sampler',
        False,
    ),
    (
        {},
        rate_limiting_sampler,
        rate_limiting_sampler,
        1,
        'sampler should remain the same if strategy is empty',
        True,
    ),
    (
        {"strategyType":2},
        rate_limiting_sampler,
        rate_limiting_sampler,
        1,
        'sampler should remain the same if strategy is invalid',
        True,
    ),
])
def test_update_sampler(response, init_sampler, expected_sampler, err_count, err_msg, reference_equivalence):
    error_reporter = mock.MagicMock()
    error_reporter.error = mock.MagicMock()
    remote_sampler = RemoteControlledSampler(
        channel=mock.MagicMock(),
        service_name='x',
        error_reporter=error_reporter,
        max_operations=10,
        init_sampler=init_sampler,
    )

    # noinspection PyProtectedMember
    remote_sampler._update_sampler(response)
    assert error_reporter.error.call_count == err_count
    if reference_equivalence:
        assert remote_sampler.sampler is expected_sampler, err_msg
    else:
        assert remote_sampler.sampler == expected_sampler, err_msg

    remote_sampler.close()


# noinspection PyProtectedMember
def test_update_sampler_adaptive_sampler():
    error_reporter = mock.MagicMock()
    error_reporter.error = mock.MagicMock()
    remote_sampler = RemoteControlledSampler(
        channel=mock.MagicMock(),
        service_name='x',
        error_reporter=error_reporter,
        max_operations=10,
    )

    response = {
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

    remote_sampler._update_sampler(response)
    assert '%s' % remote_sampler.sampler == 'AdaptiveSampler(0.001, 2, 10)'

    new_response = {
        "strategyType":1,
        "operationSampling":
        {
            "defaultSamplingProbability":0.51,
            "defaultLowerBoundTracesPerSecond":3,
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

    remote_sampler._update_sampler(new_response)
    assert '%s' % remote_sampler.sampler == 'AdaptiveSampler(0.51, 3, 10)'

    remote_sampler._update_sampler({"strategyType":0,"probabilisticSampling":{"samplingRate":0.004}})
    assert '%s' % remote_sampler.sampler == 'ProbabilisticSampler(0.004)', \
        'should not fail going from adaptive sampler to probabilistic sampler'

    remote_sampler.close()
