# Copyright (c) 2016 Uber Technologies, Inc.
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

import pytest
import tornado.testing
import tornado.web
from urllib.parse import urlparse
from jaeger_client.local_agent_net import LocalAgentSender
from jaeger_client.config import DEFAULT_REPORTING_PORT

test_strategy = """
    {
        "strategyType":0,
        "probabilisticSampling":
        {
            "samplingRate":0.002
        }
    }
"""

test_credits = """
    {
        \"balances\": [
            {
                \"operation\": \"test-operation\",
                \"balance\": 2.0
            }
        ]
    }
"""

test_client_id = 12345678

class AgentHandler(tornado.web.RequestHandler):
    def get(self):
        self.write(test_strategy)

class CreditHandler(tornado.web.RequestHandler):
    def get(self):
        self.write(test_credits)


class Test(tornado.testing.AsyncHTTPTestCase):
    application = tornado.web.Application([
        (r"/sampling", AgentHandler),
        (r"/credits", CreditHandler),
    ])

    def get_app(self):
        return Test.application

    def test_request_sampling_strategy(self):
        sender = LocalAgentSender(
            host='127.0.0.1',
            sampling_port=self.get_http_port(),
            reporting_port=DEFAULT_REPORTING_PORT
        )
        response = self.io_loop.run_sync(lambda: sender.request_sampling_strategy(service_name='svc', timeout=15), timeout=15)
        assert response.body == test_strategy.encode('utf-8')

    def test_request_throttling_credits(self):
        sender = LocalAgentSender(
            host='127.0.0.1',
            sampling_port=self.get_http_port(),
            reporting_port=DEFAULT_REPORTING_PORT,
            throttling_port=self.get_http_port(),
        )
        response = self.io_loop.run_sync(lambda: sender.request_throttling_credits(
                                    service_name='svc',
                                    client_id=test_client_id,
                                    operations=['test-operation'],
                                    timeout=15),
                                    timeout=15)
        assert response.body == test_credits.encode('utf-8')
