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


class RateLimiter(object):
    """
    RateLimiter is based on leaky bucket algorithm, formulated in terms
    of a credits balance that is replenished every time check_credit()
    method is called (tick) by the amount proportional to the time
    elapsed since the last tick, up to max of credits_per_second. A call
    to check_credit() takes a cost of an item we want to pay with the
    balance. If the balance exceeds the cost of the item, the item is
    "purchased" and the balance reduced, indicated by returned value of
    true. Otherwise the balance is unchanged and return false.

    This can be used to limit a rate of messages emitted by a service
    by instantiating the Rate Limiter with the max number of messages a
    service is allowed to emit per second, and calling check_credit(1.0)
    for each message to determine if the message is within the rate limit.

    It can also be used to limit the rate of traffic in bytes, by setting
    credits_per_second to desired throughput as bytes/second, and calling
    check_credit() with the actual message size.
    """

    def __init__(self, credits_per_second=10.0, max_balance=10.0):
        self.credits_per_second = credits_per_second
        self.max_balance = max_balance
        self.balance = self.max_balance
        self.last_tick = self.timestamp()

    @staticmethod
    def timestamp():
        return time.time()

    def check_credit(self, item_cost=1.0):
        current_time = self.timestamp()
        elapsed_time = current_time - self.last_tick
        self.last_tick = current_time
        self.balance += elapsed_time * self.credits_per_second
        if self.balance > self.max_balance:
            self.balance = self.max_balance
        if self.balance >= item_cost:
            self.balance -= item_cost
            return True
        return False
