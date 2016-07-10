[![Build Status][ci-img]][ci] [![Coverage Status][cov-img]][cov] [![PyPI version][pypi-img]][pypi]

# Jaeger Bindings for Python OpenTracing API 

This is a client-side library that can be used to instrument Python apps 
for distributed trace collection, and to send those traces to Jaeger.
See the [OpenTracing Python API](https://github.com/opentracing/opentracing-python)
for additional detail.

## Installation

```bash
apt-get install python-dev
pip install jaeger-client
```

## Getting Started

(under construction)

If your python code is already instrumented for OpenTracing,
you can simply switch to Jaeger's implementation with:

```python
from jaeger_client import Config, initializer

if __name__ == "__main__":
  config = Config(config={},  # usually read from some yaml config
                  service_name='your-app-name')
  initializer.initialize_with_local_agent(config=config)

  with opentracing.tracer.start_span('TestSpan') as span:
    span.log_event('test message', payload={'life': 42})

  opentracing.tracer.close()  # flush any buffered spans
```

## Configuration

(under construction)

See [Config class](jaeger_client/config.py).

## License

[The MIT License](LICENSE).

[ci-img]: https://travis-ci.org/uber/jaeger-client-python.svg?branch=master
[ci]: https://travis-ci.org/uber/jaeger-client-python
[cov-img]: https://coveralls.io/repos/uber/jaeger-client-python/badge.svg?branch=master
[cov]: https://coveralls.io/github/uber/jaeger-client-python?branch=master
[pypi-img]: https://badge.fury.io/py/jaeger-client.svg
[pypi]: https://badge.fury.io/py/jaeger-client
