from builtins import range
# Copyright (c) 2017 Uber Technologies, Inc.
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

from jaeger_client.rate_limiter import RateLimiter

def test_rate_limiting_sampler():
    rate_limiter = RateLimiter(2, 2)
    # stop time by overwriting timestamp() function to always return
    # the same time
    ts = time.time()
    rate_limiter.last_tick = ts
    with mock.patch('jaeger_client.rate_limiter.RateLimiter.timestamp') \
            as mock_time:
        mock_time.side_effect = lambda: ts  # always return same time
        assert rate_limiter.timestamp() == ts
        assert rate_limiter.check_credit(1), 'initial balance allows first item'
        assert rate_limiter.check_credit(1), 'initial balance allows second item'
        assert not rate_limiter.check_credit(1), 'initial balance exhausted'

        # move time 250ms forward, not enough credits to pay for one sample
        mock_time.side_effect = lambda: ts + 0.25
        assert not rate_limiter.check_credit(1), 'not enough time passed for full item'

        # move time 500ms forward, now enough credits to pay for one sample
        mock_time.side_effect = lambda: ts + 0.5
        assert rate_limiter.check_credit(1), 'enough time for new item'
        assert not rate_limiter.check_credit(1), 'no more balance'

        # move time 5s forward, enough to accumulate credits for 10 samples,
        # but it should still be capped at 2
        rate_limiter.last_tick = ts  # reset the timer
        mock_time.side_effect = lambda: ts + 5
        assert rate_limiter.check_credit(1), 'enough time for new item'
        assert rate_limiter.check_credit(1), 'enough time for second new item'
        for i in range(0, 8):
            assert not rate_limiter.check_credit(1), 'but no further, since time is stopped'

    # Test with rate limit of greater than 1 second
    rate_limiter = RateLimiter(0.1, 1.0)
    ts = time.time()
    rate_limiter.last_tick = ts
    with mock.patch('jaeger_client.rate_limiter.RateLimiter.timestamp') \
            as mock_time:
        mock_time.side_effect = lambda: ts  # always return same time
        assert rate_limiter.timestamp() == ts
        assert rate_limiter.check_credit(1), 'initial balance allows first item'
        assert not rate_limiter.check_credit(1), 'initial balance exhausted'

        # move time 11s forward, enough credits to pay for one sample
        mock_time.side_effect = lambda: ts + 11
        assert rate_limiter.check_credit(1)
