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
import importlib
import logging
from .sampler import ConstSampler, ProbabilisticSampler, RateLimitingSampler
from .constants import DEFAULT_SAMPLING_INTERVAL
from .constants import DEFAULT_FLUSH_INTERVAL
from .metrics import Metrics
from .utils import get_boolean

DEFAULT_REPORTING_PORT = 5775
DEFAULT_SAMPLING_PORT = 5778
LOCAL_AGENT_DEFAULT_ENABLED = True

logger = logging.getLogger('jaeger_tracing')


class Config(object):
    """
    Wraps a YAML configuration section for configuring Jaeger Tracer.

    service_name is required, but can be passed either as constructor
    parameter, or as config property.

    Example:

    .. code-block:: yaml

        enabled: true
        reporter_batch_size: 1
        logging: true
        metrics: true
        tchannel_factory: jaeger.config.tchannel_singleton
        sampler:
            type: const
            param: true

    """
    def __init__(self, config, metrics=None, service_name=None):
        """
        :param metrics: an instance of Metrics class, or None
        :param service_name: default service name.
            Can be overwritten by config['service_name'].
        """
        self.config = config
        if get_boolean(self.config.get('metrics', True), True):
            self._metrics = metrics or Metrics()
        else:
            # if metrics are explicitly disabled, use a dummy
            self._metrics = Metrics()
        channel_factory = self.config.get('tchannel_factory', None)
        if channel_factory is None:
            self._channel_factory = lambda: None
        else:
            self._channel_factory = Config.load_symbol(channel_factory)
        self._service_name = config.get('service_name', service_name)
        if self._service_name is None:
            raise ValueError('service_name required in the config or param')

    @property
    def service_name(self):
        return self._service_name

    @property
    def metrics(self):
        return self._metrics

    @property
    def enabled(self):
        return get_boolean(self.config.get('enabled', True), True)

    @property
    def reporter_batch_size(self):
        return int(self.config.get('reporter_batch_size', 10))

    @property
    def reporter_queue_size(self):
        return int(self.config.get('reporter_queue_size', 100))

    @property
    def logging(self):
        return get_boolean(self.config.get('logging', False), False)

    @property
    def tchannel_factory(self):
        return self._channel_factory

    @property
    def sampler(self):
        sampler_config = self.config.get('sampler', {})
        sampler_type = sampler_config.get('type', None)
        sampler_param = sampler_config.get('param', None)
        if not sampler_type:
            return None
        elif sampler_type == 'const':
            return ConstSampler(decision=get_boolean(sampler_param, False))
        elif sampler_type == 'probabilistic':
            return ProbabilisticSampler(rate=float(sampler_param))
        elif sampler_type == 'rate_limiting':
            return RateLimitingSampler(
                max_traces_per_second=float(sampler_param))

        raise ValueError('Unknown sampler type %s' % sampler_type)

    @property
    def sampling_refresh_interval(self):
        return self.config.get('sampling_refresh_interval', DEFAULT_SAMPLING_INTERVAL)

    @property
    def reporter_flush_interval(self):
        return self.config.get('reporter_flush_interval', DEFAULT_FLUSH_INTERVAL)

    def local_agent_group(self):
        return self.config.get('local_agent', None)

    @property
    def local_agent_enabled(self):
        try:
            return get_boolean(self.local_agent_group().get('enabled',
                               LOCAL_AGENT_DEFAULT_ENABLED),
                               LOCAL_AGENT_DEFAULT_ENABLED)
        except:
            return LOCAL_AGENT_DEFAULT_ENABLED

    @property
    def local_agent_sampling_port(self):
        try:
            return int(self.local_agent_group()['sampling_port'])
        except:
            return DEFAULT_SAMPLING_PORT

    @property
    def local_agent_reporting_port(self):
        try:
            return int(self.local_agent_group()['reporting_port'])
        except:
            return DEFAULT_REPORTING_PORT

    def install_client_hooks(self):
        """
        Usually called from middleware to install client hooks
        specified in the client_hooks section of the configuration
        """
        hooks = self.config.get('client_hooks', None)
        if hooks is None or hooks == 'all':
            hooks = [
                'opentracing_instrumentation.client_hooks.install_all_patches'
            ]
        if hooks is not None and type(hooks) is list:
            for hook_name in hooks:
                logger.info('Loading client hook %s', hook_name)
                hook = Config.load_symbol(hook_name)
                logger.info('Applying client hook %s', hook_name)
                hook()

    @staticmethod
    def load_symbol(name):
        """Load a symbol by name.

        :param str name: The name to load, specified by `module.attr`.
        :returns: The attribute value. If the specified module does not contain
                  the requested attribute then `None` is returned.
        """
        module_name, key = name.rsplit('.', 1)
        try:
            module = importlib.import_module(module_name)
        except ImportError as err:
            # it's possible the symbol is a class method
            module_name, class_name = module_name.rsplit('.', 1)
            module = importlib.import_module(module_name)
            klass = getattr(module, class_name, None)
            if klass:
                attr = getattr(klass, key, None)
            else:
                raise err
        else:
            attr = getattr(module, key, None)
        if not callable(attr):
            raise ValueError('%s is not callable (was %r)' % (name, attr))
        return attr
