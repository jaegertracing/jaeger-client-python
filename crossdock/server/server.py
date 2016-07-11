import tornado.web
import opentracing
import tornado.ioloop
import tornado.escape
import tornado.httpclient
from tornado.web import asynchronous
from jaeger_client.tracer import Tracer
from jaeger_client.sampler import ConstSampler
import crossdock.server.constants as constants
import crossdock.server.serializer as serializer
from opentracing_instrumentation import http_client, http_server
from opentracing_instrumentation.client_hooks import tornado_http
import opentracing.ext.tags as ext_tags
from crossdock.thrift_gen.tracetest.ttypes import ObservedSpan, TraceResponse, Transport, \
    JoinTraceRequest

from tchannel import TChannel, thrift, context, event
from crossdock.server.thriftrw_serializer import trace_response_to_thriftrw, \
    join_trace_request_to_thriftrw

DefaultClientPortHTTP = 8080
DefaultServerPortHTTP = 8081
DefaultServerPortTChannel = 8082
tchannel_supported = False

# Tchannel initialization.


class OpenTracingHook(event.EventHook):
    def before_send_request(self, request):
        print 'before_send_request: trace_id: %x, span_id: %x' % \
            (request.tracing.trace_id, request.tracing.span_id)

idl_path = 'idl/thrift/crossdock/tracetest.thrift'
service = thrift.load(path=idl_path, service='python')
tchannel = TChannel('python', hostport="0:%d" % DefaultServerPortTChannel, trace=True)
tchannel.hooks.register(OpenTracingHook())


def serve():
    '''main entry point'''
    print "Python Tornado Crossdock Server Running ..."
    tchannel.listen()
    app = make_app(Server())
    app.listen(DefaultClientPortHTTP)
    app.listen(DefaultServerPortHTTP)
    tornado.ioloop.IOLoop.current().start()


# Tornado Stuff
class MainHandler(tornado.web.RequestHandler):
    def initialize(self, server=None, method=None):
        self.server = server
        self.method = method

    @asynchronous
    def get(self):
        if self.server and self.method:
            self.method(self.server, self.request, self)
        else:
            self.finish()

    @asynchronous
    def post(self):
        if self.server and self.method:
            self.method(self.server, self.request, self)
        else:
            self.finish()

    def head(self):
        pass


def make_app(server):
    return tornado.web.Application(
        [
            (r"/", MainHandler),
            (r"/start_trace", MainHandler, (dict(server=server, method=Server.start_trace))),
            (r"/join_trace", MainHandler, (dict(server=server, method=Server.join_trace))),
        ], debug=True)


# TChannel handlers
def tchannelNotImplResponse():
    return TraceResponse(notImplementedError="python <=> tchannel not implemented")


@tchannel.thrift.register(service.TracedService)
def startTrace(request):
    return trace_response_to_thriftrw(service, tchannelNotImplResponse())


@tchannel.thrift.register(service.TracedService)
def joinTrace(request):
    return trace_response_to_thriftrw(service, tchannelNotImplResponse())


# HTTP Tracing Stuff
class UnknownTransportException(Exception):
    pass


class Server(object):
    def __init__(self):
        self.tracer = Tracer("python", None, ConstSampler(decision=True))
        opentracing.tracer = self.tracer

    def start_trace(self, request, response_writer):
        sstr = serializer.start_trace_request_from_json(request.body)

        def update_span(span):
            span.set_baggage_item(constants.baggage_key, sstr.baggage)
            span.set_tag(ext_tags.SAMPLING_PRIORITY, sstr.sampled)

        self.handle_trace_request(request, sstr, update_span, response_writer)

    def join_trace(self, request, response_writer):

        jtr = serializer.join_trace_request_from_json(request.body) if request.body else None

        self.handle_trace_request(request, jtr, None, response_writer)

    def handle_trace_request(self, http_request, trace_request, span_handler, response_writer):

        span = http_server.before_request(http_server.TornadoRequestWrapper(request=http_request),
                                          self.tracer)
        if span_handler:
            span_handler(span)

        traceId = "%x" % span.trace_id
        observed_span = ObservedSpan(traceId, span.is_sampled(),
                                     span.get_baggage_item(constants.baggage_key))

        tr = TraceResponse(span=observed_span)

        if trace_request and trace_request.downstream is not None:
            self.call_downstream(span, trace_request, tr, response_writer)
        else:
            response_writer.write(serializer.obj_to_json(tr))
            response_writer.finish()

    def call_downstream(self, span, trace_request, trace_response, response_writer):
        if trace_request.downstream.transport == Transport.HTTP:
            self.call_downstream_http(span, trace_request, trace_response, response_writer)
        elif trace_request.downstream.transport == Transport.TCHANNEL:
            if tchannel_supported:
                self.real_call_downstream_tchannel(span, trace_request, trace_response,
                                                   response_writer)
            else:
                self.call_downstream_tchannel(span, trace_request, trace_response,
                                              response_writer)
        else:
            response_writer.finish()
            raise UnknownTransportException("%s" % trace_request.downstream.transport)

    def call_downstream_http(self, span, trace_request, trace_response, response_writer):

        def handle_response(response):
            tr = serializer.traceresponse_from_json(response.body)
            if tr.notImplementedError:
                response_writer.write(serializer.obj_to_json(tr))
            else:
                trace_response.downstream = tr
                response_writer.write(serializer.obj_to_json(trace_response))
            response_writer.finish()

        downstream = trace_request.downstream
        url = "http://%s:%s/join_trace" % (downstream.host, downstream.port)
        body = serializer.downstream_to_json(downstream.downstream)

        req = tornado.httpclient.HTTPRequest(url=url, method="POST",
                                             headers={"Content-Type": "application/json"},
                                             body=body)
        http_client.before_http_request(tornado_http.TornadoRequestWrapper(request=req),
                                        lambda: span)
        client = tornado.httpclient.AsyncHTTPClient()
        client.fetch(req, handle_response)

    def call_downstream_tchannel(self, span, trace_request, trace_response, response_writer):

        tr = tchannelNotImplResponse()
        response_writer.write(serializer.obj_to_json(tr))
        response_writer.finish()

    def real_call_downstream_tchannel(self, span, trace_request, trace_response, response_writer):

        def handle_response(f):
            response = f.result()
            trace_response.downstream = response.body

            response_writer.write(serializer.obj_to_json(trace_response))
            response_writer.finish()

        downstream = trace_request.downstream
        # XXX cache these
        service = thrift.load(idl_path, service=downstream.serviceName)

        jtr = JoinTraceRequest(trace_request.serverRole, downstream.downstream)
        jtr = join_trace_request_to_thriftrw(service, jtr)
        # with context.RequestContext(span):
        with context.request_context(span):
            f = tchannel.thrift(service.TracedService.joinTrace(jtr),
                                hostport="%s:%s" % (downstream.host, downstream.port))
        tornado.ioloop.IOLoop.current().add_future(f, handle_response)
