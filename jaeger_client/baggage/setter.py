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


class BaggageSetter(object):
    """
    BaggageSetter is a class that sets a baggage key:value and the associated
    logs on a Span.
    """

    def __init__(self, restriction_manager, metrics_factory):
        self._restriction_manager = restriction_manager
        self._baggage_update_success = \
            metrics_factory.create_counter(name='jaeger.baggage-update', tags={'result': 'ok'})
        self._baggage_update_failure = \
            metrics_factory.create_counter(name='jaeger.baggage-update', tags={'result': 'err'})
        self._baggage_truncate = \
            metrics_factory.create_counter(name='jaeger.baggage-truncate')

    def set_baggage(self, span, key, value):
        """
        Sets the baggage key:value on the span and the corresponding logs.
        Whether the baggage is set on the span depens on if the key is
        allowed to be set by this service.
        A SpanContext is returned with the new baggage key:value set.

        :param span: The span to set the baggage on.
        :param key: The baggage key to set.
        :param value: The baggage value to set.
        :return: The SpanContext with the baggage set if applicable.
        """
        truncated = False
        prev_item = ''
        restriction = self._restriction_manager.get_restriction(service=span.tracer.service_name,
                                                                baggage_key=key)
        if not restriction.key_allowed:
            self._log_fields(span, key, value, prev_item, truncated, restriction.key_allowed)
            self._baggage_update_failure(1)
            return span.context
        if len(value) > restriction.max_value_length:
            value = value[:restriction.max_value_length]
            truncated = True
            self._baggage_truncate(1)
        prev_item = span.get_baggage_item(key=key)
        self._log_fields(span, key, value, prev_item, truncated, restriction.key_allowed)
        self._baggage_update_success(1)
        return span.context.with_baggage_item(key=key, value=value)

    def _log_fields(self, span, key, value, prev_item, truncated, valid):
        if not span.is_sampled():
            return

        logs = {
            'event': 'baggage',
            'key': key,
            'value': value,
        }
        if prev_item:
            logs['override'] = 'true'
        if truncated:
            logs['truncated'] = 'true'
        if not valid:
            logs['invalid'] = 'true'
        span.log_kv(key_values=logs)
