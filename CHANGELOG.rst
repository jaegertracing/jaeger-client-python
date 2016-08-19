.. :changelog:

History
-------

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
