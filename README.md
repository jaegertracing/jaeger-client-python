[![Build Status][ci-img]][ci] [![Coverage Status][cov-img]][cov] [![PyPI version][pypi-img]][pypi]

# Jaeger Bindings for Python OpenTracing API 

This is a client-side library that can be used to instrument Python apps 
for distributed trace collection, and to send those traces to Jaeger.
See the [OpenTracing Python API](https://github.com/opentracing/opentracing-python)
for additional detail.

## Contributing and Developing

Please see [CONTRIBUTING.md](./CONTRIBUTING.md).

## Installation

```bash
apt-get install python-dev
pip install jaeger-client
```

## Getting Started

```python
import opentracing
import logging
import time
from jaeger_client import Config

if __name__ == "__main__":
    log_level = logging.DEBUG
    logging.getLogger('').handlers = []
    logging.basicConfig(format='%(asctime)s %(message)s', level=log_level)

    config = Config(
        config={ # usually read from some yaml config
            'sampler': {
                'type': 'const',
                'param': 1,
            },
            'logging': True,
        },  
        service_name='your-app-name',
    )
    # this call also sets opentracing.tracer
    tracer = config.initialize_tracer()

    with tracer.start_span('TestSpan') as span:
        span.log_event('test message', payload={'life': 42})

        with tracer.start_span('ChildSpan', child_of=span) as child_span:
            span.log_event('down below')

    time.sleep(2)   # yield to IOLoop to flush the spans - https://github.com/jaegertracing/jaeger-client-python/issues/50
    tracer.close()  # flush any buffered spans
```

### Other Instrumentation

The [opentracing-contrib](https://github.com/opentracing-contrib) project has a few modules that provide explicit instrumentation support for popular frameworks like Django and Flask.

At Uber we are mostly using the [opentracing_instrumentation](https://github.com/uber-common/opentracing-python-instrumentation) module that provides:
  * explicit instrumentation for HTTP servers, and
  * implicit (monkey-patched) instrumentation for several popular libraries like `urllib2`, `redis`, `requests`, some SQL clients, etc.

## Initialization & Configuration

### Production

The recommended way to initialize the tracer for production use:

```python
from jaeger_client import Config

config = Config(config={}, service_name='your-app-name')
tracer = config.initialize_tracer()
```

Note that the last line also sets the `opentracing.tracer` global variable.

### Development

For development, some parameters can be passed via `config` dictionary, as in the Getting Started example above. For more details please see the [Config class](jaeger_client/config.py).

### WSGI

Applications running under WSGI usually fork multiple sub-processes to handle individual requests.
When Jaeger tracer is initialized, it may start a new background thread. If the process later forks,
it might cause issues or hang the application (due to exclusive lock on the interpreter).
Therefore, it is recommended that the tracer is not initialized until after the child processes
are forked. Depending on the WSGI framework you might be able to use `@postfork` decorator
to delay tracer initialization.

## Debug Traces (Forced Sampling)

### Programmatically

The OpenTracing API defines a `sampling.priority` standard tag that
can be used to affect the sampling of a span and its children:

```python
from opentracing.ext import tags as ext_tags

span.set_tag(ext_tags.SAMPLING_PRIORITY, 1)
```

### Via HTTP Headers

Jaeger Tracer also understands a special HTTP Header `jaeger-debug-id`,
which can be set in the incoming request, e.g.

```sh
curl -H "jaeger-debug-id: some-correlation-id" http://myhost.com
```

When Jaeger sees this header in the request that otherwise has no
tracing context, it ensures that the new trace started for this
request will be sampled in the "debug" mode (meaning it should survive
all downsampling that might happen in the collection pipeline), and
the root span will have a tag as if this statement was executed:

```python
span.set_tag('jaeger-debug-id', 'some-correlation-id')
```

This allows using Jaeger UI to find the trace by this tag.

## Zipkin Compatibility

This library internally uses Zipkin Thrift data model and conventions, 
but if you want to use it directly with other Zipkin libraries & backend, 
it needs:
  1. different [wire codecs](./jaeger_client/codecs.py) to transmit 
     trace context as `X-B3-*` headers
  2. a reporter that will submit traces to Zipkin backend over Zipkin-supported 
     transports like Kafka or HTTP

Both of these things are easy to add (e.g. it was done in https://github.com/jaegertracing/jaeger-client-java/pull/34), 
but it is not a priority for the Uber team since we are using a different backend.
We will welcome PRs that provide that functionality.

## License

[Apache 2.0 License](./LICENSE).

[ci-img]: https://travis-ci.org/jaegertracing/jaeger-client-python.svg?branch=master
[ci]: https://travis-ci.org/jaegertracing/jaeger-client-python
[cov-img]: https://coveralls.io/repos/jaegertracing/jaeger-client-python/badge.svg?branch=master
[cov]: https://coveralls.io/github/jaegertracing/jaeger-client-python?branch=master
[pypi-img]: https://badge.fury.io/py/jaeger-client.svg
[pypi]: https://badge.fury.io/py/jaeger-client
