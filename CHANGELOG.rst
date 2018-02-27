.. :changelog:

History
-------

3.8.0 (unreleased)
------------------

- Replace zipkin.thrift out-of-band span format with jaeger.thrift (#111)
- Use only `six` for py2/py3 compatibility, drop `future` (#130)
- Add codec for B3 trace context headers (#112) - thanks @gravelg
- Increase max tag value length to 1024 and make it configurable (#110)
- A number of fixes for Python 3.x compatibility
  - Fix span and sampler tests to work under Py3 (#117)
  - Fix dependencies for Py3 compatibility (#116)
  - Fix xrange for Py3 in thrift generated files (#115)
  - Add python3 compat, hasattr iteritems->itemx (#113) - thanks @kbroughton


3.7.1 (2017-12-14)
------------------

- Encode unicode baggage keys/values to UTF-8 (#109)


3.7.0 (2017-12-12)
------------------

- Change default for one_span_per_rpc to False (#105)


3.6.1 (2017-09-26)
------------------

- Fix bug when creating tracer with tags. (#80)


3.6.0 (2017-09-26)
------------------

- Allow tracer constructor to accept optional tags argument.
- Support `JAEGER_TAGS` environment variable and config for tracer tags.


3.5.0 (2017-07-10)
------------------

- Add metrics factory and allow tags for metrics [#45]
- Save baggage in span [#54]
- Allow to override hostname for jaeger agent [#51]


3.4.0 (2017-03-20)
------------------

- Add adaptive sampler
- Allow overriding one-span-per-rpc behavior
- Allow overriding codecs in tracer initialization


3.3.1 (2016-10-14)
------------------

- Replace 0 parentID with None


3.3.0 (2016-10-04)
------------------

- Upgrade to opentracing 1.2 with KV logging.


3.2.0 (2016-09-20)
------------------

- Support debug traces via HTTP header jaeger-debug-id.


3.1.0 (2016-09-06)
------------------

- Report sampling strategy as root span tags `sampler.type` and `sampler.param`. In case of probabilistic sampling (most frequently used strategy), the values would be `probabilistic` and the sampling probability [0 .. 1], respectively.
- Record host name as `jaeger.hostname` tag on the first-in-process spans (i.e. root spans and rpc-server spans)
- Record the version of the Jaeger library as `jaeger.version` tag


3.0.2 (2016-08-18)
------------------

- Do not create SpanContext from Zipkin span if trace_id is empty/zero


3.0.1 (2016-08-09)
------------------

- Do not publish crossdock module


3.0.0 (2016-08-07)
------------------

- Upgrade to OpenTracing 1.1


2.2.0 (2016-08-02)
------------------

- Implement Zipkin codec for interop with TChannel


2.1.0 (2016-07-19)
------------------

- Allow passing external IOLoop


2.0.0 (2016-07-19)
------------------

- Remove TChannel dependency
- Remove dependency on opentracing_instrumentation


1.0.1 (2016-07-11)
------------------

- Downgrade TChannel dependency to >= 0.24


1.0.0 (2016-07-10)
------------------

- Initial open source release.
