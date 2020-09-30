# Copyright (c) 2020, The Jaeger Authors
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except
# in compliance with the License. You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the License
# is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
# or implied. See the License for the specific language governing permissions and limitations under
# the License.

from __future__ import absolute_import

from collections import OrderedDict

import six
import sys
from six.moves import urllib_parse


class TraceState(object):
    __slots__ = ['_trace_state', '_encoder']

    def __init__(self, operation_name=None, trace_id=None,
                 header_values=None, encoder=None):
        self._trace_state = OrderedDict()
        self._encoder = encoder
        if header_values:
            self.parse_from_header(header_values)
        if operation_name and trace_id:
            self.add(operation_name, trace_id)

    def set_encoder(self, encoder=None):
        self._encoder = encoder

    def parse_from_header(self, value):
        states = six.ensure_str(urllib_parse.unquote(value)).split(',')
        states.reverse()
        for state in states:
            if '=' in state:
                key, value = state.split('=', 1)
                self.add(key, value, skip_encode=True)

    def add(self, key, value=None, skip_encode=False):
        if not key:
            return
        if not value:
            value = self._trace_state.get(key, None)
            skip_encode = True
            if not value:
                return

        if self._encoder and skip_encode is False:
            value = self._encoder(value)

        key = six.ensure_str(str(key))
        value = six.ensure_str(str(value))

        if sys.version_info >= (3, 2, 0):
            self._trace_state[key] = value
            self._trace_state.move_to_end(key, last=False)
        else:
            # Not so graceful in older versions
            root = self._trace_state._OrderedDict__root  # noqa
            first = root[1]

            if key in self._trace_state:
                link = self._trace_state._OrderedDict__map[key]  # noqa
                link_prev, link_next, _ = link
                link_prev[1] = link_next
                link_next[0] = link_prev
                link[0] = root
                link[1] = first
                root[1] = first[0] = link
            else:
                root[1] = first[0] = self._trace_state._OrderedDict__map[key] = [root, first, key]
                dict.__setitem__(self._trace_state, key, value)

    def get_formatted_header(self, url_parse=True):
        traces = []
        if not self._trace_state:
            return ''
        for key, value in six.iteritems(
                self._trace_state
        ):
            traces.append('{}={}'.format(key, value))

        header_traces = ','.join(traces)
        if url_parse is True:
            if six.PY2:
                header_traces = urllib_parse.quote(
                    header_traces.encode('utf-8'))
            else:
                header_traces = urllib_parse.quote(
                    header_traces)

        return header_traces
