# Copyright (c) 2016-2018 Uber Technologies, Inc.
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

import logging
from logging import StreamHandler
import datetime

import logging

logger = logging.getLogger('jaeger_tracing')

class SpanAutologger(StreamHandler):
    # Custom StreamHandler implementation to forward python logger records to Jaeger / OpenTracing
    __slots__ = ["_span", "span_logger"]
    def __init__(self, span_logger, span):
        StreamHandler.__init__(self)
        self._span = span
        self.span_logger = span_logger

    def emit(self, record):
        # See here https://docs.python.org/3/library/logging.html#logrecord-objects
        if hasattr(record, 'msg'):
            logger.debug("emitting log")
            message = self.format(record)
            self._span.log_kv({
                "asctime": getattr(record, 'asctime', datetime.datetime.now()),
                "created": record.created,
                "filename": record.filename,
                "funcName": record.funcName,
                "levelname": record.levelname,
                "lineno": record.lineno,
                "message": message,
                "msg": record.msg,
                "module": record.module,
                "msecs": record.msecs,
                "name": record.name,
                "pathname": record.pathname,
                "process": record.process,
                "processName": record.processName,
                "thread": record.thread,
                "threadName": record.threadName,
            })
    def __enter__(self):
        logger.debug("adding jaeger streamhandler to logger object to capture log")
        self.span_logger.addHandler(self)

    def __exit__(self, type=None, value=None, traceback=None):
        logger.debug("removing jaeger streamhandler from logger object")
        self.span_logger.removeHandler(self)
        if type:
            logger.debug("span exited with an exception, log the exception")
            self._span.log_kv({
                "exception": type,
                "value": value,
                "traceback": traceback
            })
