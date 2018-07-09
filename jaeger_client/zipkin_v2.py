# Copyright (c) 2018 Uber Technologies, Inc.
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
from binascii import hexlify
from struct import pack
import json

from opentracing.ext import tags as ext_tags

from jaeger_client.thrift_gen.jaeger.ttypes import TagType
from .thrift import timestamp_micros
from . import constants


def make_zipkin_v2_batch(spans=None, process=None):
    batched_spans = []
    for span in spans:
        with span.update_lock:
            v2_span = to_zipkin_v2_span(span, process)
        batched_spans.append(v2_span)
    return batched_spans


def to_zipkin_v2_span(span, process):
    """Converts jaeger thrift span and process information to Zipkin's API v2 span format"""
    v2_span = dict(
        traceId=to_encoded_id(span.trace_id),
        id=to_encoded_id(span.span_id),
        timestamp=timestamp_micros(span.start_time),
        debug=span.is_debug(),
    )

    if span.end_time:
        v2_span['duration'] = timestamp_micros(span.end_time - span.start_time)

    name = getattr(span, 'operation_name', '')
    if name:
        v2_span['name'] = name

    parent_id = getattr(span, 'parent_id', 0)
    if parent_id:
        v2_span['parentId'] = to_encoded_id(parent_id)

    kind = get_span_kind(span)
    if kind:
        v2_span['kind'] = kind

    local_endpoint = get_local_endpoint(process)
    if local_endpoint:
        v2_span['localEndpoint'] = local_endpoint

    remote_endpoint = get_remote_endpoint(process)
    if remote_endpoint:
        v2_span['remoteEndpoint'] = remote_endpoint

    tags = format_span_tags(span)
    if tags:
        v2_span['tags'] = tags

    annotations = [log_to_annotation(l) for l in span.logs]
    if annotations:
        v2_span['annotations'] = annotations

    return v2_span


def to_encoded_id(jaeger_id):
    return hexlify(pack('>Q', jaeger_id)).decode('ascii')


def get_span_kind(span):
    kind = None
    for tag in span.tags:
        if tag.key == ext_tags.SPAN_KIND:
            kind = {ext_tags.SPAN_KIND_RPC_CLIENT: 'CLIENT',
                    ext_tags.SPAN_KIND_RPC_SERVER: 'SERVER'}[tag.vStr]
    return kind


ttype_attr_map = {TagType.BINARY: 'vBinary', TagType.BOOL: 'vBool', TagType.DOUBLE: 'vDouble',
                  TagType.LONG: 'vLong', TagType.STRING: 'vStr'}


def get_tag_value(tag):
    attr = ttype_attr_map[tag.vType]
    return getattr(tag, attr, None)


def get_local_endpoint(process):
    local_endpoint = {}
    service_name = getattr(process, 'serviceName', '')
    if service_name:
        local_endpoint['serviceName'] = service_name
    if process.tags:
        for tag in process.tags:
            if tag.key == constants.JAEGER_IP_TAG_KEY:
                ipv4 = get_tag_value(tag)
                if ipv4:
                    local_endpoint['ipv4'] = ipv4
                break
    return local_endpoint


def get_remote_endpoint(process):
    tag_key_map = [(ext_tags.PEER_SERVICE, 'serviceName'), (ext_tags.PEER_HOST_IPV4, 'ipv4'),
                   (ext_tags.PEER_HOST_IPV6, 'ipv6'), (ext_tags.PEER_PORT, 'port')]

    remote_endpoint = {}
    if process.tags:
        for tag in process.tags:
            for tag_key, endpoint_key in list(tag_key_map):
                if tag.key == tag_key:
                    tag_key_map.remove((tag_key, endpoint_key))
                    value = get_tag_value(tag)
                    if value:
                        if tag.key == ext_tags.PEER_PORT:
                            value = int(value)
                        remote_endpoint[endpoint_key] = value
                    continue
            if not tag_key_map:
                break

    return remote_endpoint


redundant_tags = (ext_tags.PEER_HOST_IPV4, ext_tags.PEER_HOST_IPV6, ext_tags.PEER_PORT,
                  ext_tags.PEER_SERVICE, ext_tags.SPAN_KIND, ext_tags.SPAN_KIND_RPC_CLIENT,
                  ext_tags.SPAN_KIND_RPC_SERVER)


def format_span_tags(span):
    formatted = {}
    for tag in span.tags:
        if tag.key not in redundant_tags:
            k, v = format_span_tag(tag)
            if v:
                formatted[k] = v
    return formatted


def format_span_tag(tag):
    key = tag.key
    value = get_tag_value(tag)
    return key, value


def log_to_annotation(log):
    annotation = dict(timestamp=log.timestamp)
    tags = dict([format_span_tag(t) for t in log.fields])
    annotation['value'] = json.dumps(tags)
    return annotation
