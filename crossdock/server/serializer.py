import json
from crossdock.thrift_gen.tracetest.ttypes import JoinTraceRequest, StartTraceRequest, \
    Downstream, Transport, TraceResponse, ObservedSpan


#
# Serializers for the downstream calls
#
def set_downstream_object_values(obj, i):
    return set_object_values(obj, i, downstream_from_struct)


def join_trace_request_from_json(j):
    jtr = JoinTraceRequest()
    set_downstream_object_values(jtr, json.loads(j))
    return jtr


def start_trace_request_from_json(j):
    sstr = StartTraceRequest()
    set_downstream_object_values(sstr, json.loads(j))
    return sstr


def downstream_from_struct(i):
    d = Downstream()
    set_downstream_object_values(d, i)
    return d


def downstream_to_json(d):
    s = {}
    if d is not None:
        s["downstream"] = obj_to_json(d)
    return json.dumps(s)

#
# Serializers for the upstream responses
#


def set_upstream_object_values(obj, i):
    return set_object_values(obj, i, traceresponse_from_struct)


def observed_span_from_struct(i):
    os = ObservedSpan()
    set_upstream_object_values(os, i)
    return os


def traceresponse_from_struct(i):
    tr = TraceResponse()
    set_upstream_object_values(tr, i)
    return tr


def traceresponse_from_json(j):
    return traceresponse_from_struct(json.loads(j))

# Generic


def class_keys(obj):
    return [a for a in dir(obj) if not a.startswith('__') and not
            callable(getattr(obj, a)) and not
            a == 'type_spec']


def obj_to_json(obj):
    s = {}
    for k in class_keys(obj):
        if k == "downstream":
            if obj.downstream is not None:
                s["downstream"] = obj_to_json(obj.downstream)
        elif k == "transport":
            if obj.transport is not None:
                s["transport"] = Transport._VALUES_TO_NAMES[obj.transport]
        elif k == "span":
            if obj.span is not None:
                s["span"] = obj_to_json(obj.span)
        else:
            s[k] = getattr(obj, k)
    return s


def set_object_values(obj, i, dsf):
    for k in i.iterkeys():
        if hasattr(obj, k):
            if k == "downstream":
                obj.downstream = dsf(i[k])
            elif k == "transport":
                obj.transport = Transport._NAMES_TO_VALUES[i[k]]
            elif k == "span":
                obj.span = observed_span_from_struct(i[k])
            else:
                setattr(obj, k, i[k])
