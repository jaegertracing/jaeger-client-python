# Copyright (c) 2018, The Jaeger Authors
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

from jaeger_client.metrics import MetricsFactory
from collections import defaultdict
from prometheus_client import Counter, Gauge


class PrometheusMetricsFactory(MetricsFactory):
    """
    Provides metrics backed by Prometheus
    """
    def __init__(self, namespace=''):
        self._cache = defaultdict(object)
        self._namespace = namespace

    def _get_tag_names(self, label):
        if label is None:
            return []
        tag_name_list = []
        for key in label.keys():
            tag_name_list.append(key)
        return tag_name_list

    def _get_metric(self, metric, cache, name, label_name_list):
        cache_key = name + ''.join(label_name_list)
        cached_gauge = cache.get(cache_key)
        if cached_gauge is None:
            cache[cache_key] = metric(name, name, label_name_list, self._namespace)
        return cache[cache_key]

    def create_counter(self, name, tags=None):
        label_name_list = self._get_tag_names(tags)
        counter = self._get_metric(Counter, self._cache, name, label_name_list)
        if tags is not None and len(tags) > 0:
            counter = counter.labels(**tags)

        def increment(value):
            counter.inc(value)
        return increment

    def create_gauge(self, name, tags=None):
        label_name_list = self._get_tag_names(tags)
        gauge = self._get_metric(Gauge, self._cache, name, label_name_list)
        if tags is not None and len(tags) > 0:
            gauge = gauge.labels(**tags)

        def update(value):
            gauge.set(value)
        return update
