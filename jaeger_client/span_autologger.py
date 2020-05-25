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
