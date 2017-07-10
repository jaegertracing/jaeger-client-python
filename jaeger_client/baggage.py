import logging
import json

from threading import Lock

from .metrics import Metrics, LegacyMetricsFactory
from .local_agent_net import LocalAgentPoller

DEFAULT_MAX_VALUE_LENGTH = 2048
DEFAULT_REFRESH_INTERVAL_SECONDS = 60

BAGGAGE_KEY = 'baggageKey'
MAX_VALUE_LENGTH = 'maxValueLength'

default_logger = logging.getLogger('jaeger_tracing')


class BaggageRestrictionManager(object):
    """
    BaggageRestrictionManager keeps track of valid baggage keys and their
    size restrictions.
    """
    def is_valid_baggage_key(self, baggage_key):
        raise NotImplementedError()


class DefaultBaggageRestrictionManager(BaggageRestrictionManager):
    """
    DefaultBaggageRestrictionManager allows any baggage key.
    """
    def is_valid_baggage_key(self, baggage_key):
        return True, DEFAULT_MAX_VALUE_LENGTH


class RemoteBaggageRestrictionManager(BaggageRestrictionManager):
    """
    RemoteRestrictionManager manages baggage restrictions by retrieving
    baggage restrictions from agent.
    """
    def __init__(self, channel, service_name, **kwargs):
        """
        :param channel: channel for communicating with jaeger-agent
        :param service_name: name of this application
        :param kwargs: optional parameters
            - refresh_interval_seconds: interval in seconds for polling
              for new baggage restrictions
            - logger:
            - metrics_factory: used to generate metrics for errors
            - deny_baggage_on_initialization_failure:
        :param init:
        :return:
        """
        self._channel = channel
        self.service_name = service_name
        self.logger = kwargs.get('logger', default_logger)
        self.refresh_interval_seconds = \
            kwargs.get('refresh_interval_seconds', DEFAULT_REFRESH_INTERVAL_SECONDS)
        self.metrics_factory = kwargs.get('metrics_factory',
                                          LegacyMetricsFactory(Metrics()))
        self.metrics = BaggageRestrictionManagerMetrics(self.metrics_factory)

        self.lock = Lock()
        self.restrictions = {}
        self.deny_baggage_on_initialization_failure = \
            kwargs.get('deny_baggage_on_initialization_failure', False)
        self.initialized = False

        self.io_loop = channel.io_loop
        if not self.io_loop:
            self.logger.error(
                'Cannot acquire IOLoop, baggage restrictions will not be updated')
        else:
            # Initialize baggage restrictions
            self._poll_baggage_restriction_proxy()
            # according to IOLoop docs, it's not safe to use timeout methods
            # unless already running in the loop, so we use `add_callback`
            self.poller = LocalAgentPoller(self.io_loop, self.lock, self.refresh_interval_seconds,
                                           self._poll_baggage_restriction_proxy)
            self.io_loop.add_callback(self.poller.init_polling)

    def _poll_baggage_restriction_proxy(self):
        self.logger.debug('Requesting baggage restrictions from agent')
        fut = self._channel.request_baggage_restrictions(
            self.service_name, timeout=15)
        fut.add_done_callback(self._request_callback)

    def _request_callback(self, future):
        exception = future.exception()
        if exception:
            self.metrics.baggage_restrictions_update_failure(1)
            return

        response = future.result()
        try:
            baggage_restrictions_response = json.loads(response.body)
        except Exception as e:
            self.metrics.baggage_restrictions_update_failure(1)
            self.logger.error(
                'Fail to parse baggage restrictions '
                'from jaeger-agent: %s [%s]', e, response.body)
            return

        self._update_baggage_restrictions(baggage_restrictions_response)
        self.metrics.baggage_restrictions_update_success(1)
        self.logger.debug('Baggage restrictions set to %s', self.restrictions)

    def _update_baggage_restrictions(self, response):
        restrictions = {}
        for restriction in response:
            if restriction.get(BAGGAGE_KEY) and restriction.get(MAX_VALUE_LENGTH):
                restrictions[restriction.get(BAGGAGE_KEY)] = restriction.get(MAX_VALUE_LENGTH)
        with self.lock:
            self.initialized = True
            self.restrictions = restrictions

    def close(self):
        if self.poller:
            self.poller.close()

    def is_valid_baggage_key(self, baggage_key):
        with self.lock:
            if not self.initialized:
                if self.deny_baggage_on_initialization_failure:
                    return False, 0
                else:
                    return True, DEFAULT_MAX_VALUE_LENGTH
            if baggage_key in self.restrictions:
                return True, self.restrictions[baggage_key]
            return False, 0


class BaggageRestrictionManagerMetrics:
    def __init__(self, metrics_factory):
        self.baggage_restrictions_update_success = \
            metrics_factory.create_counter(name='jaeger.baggage-restrictions-update',
                                           tags={'result': 'ok'})
        self.baggage_restrictions_update_failure = \
            metrics_factory.create_counter(name='jaeger.baggage-restrictions-update',
                                           tags={'result': 'err'})
