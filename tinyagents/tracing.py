import functools
from typing import Optional

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from openinference.semconv.trace import SpanAttributes
from openinference.semconv.trace import OpenInferenceSpanKindValues
from openinference.semconv.resource import ResourceAttributes
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from tinyagents.utils import convert_to_string

def create_phoenix_tracer(
        project_name: Optional[str] = "tinyagents",
        tracer_name: Optional[str] = None
    ):
    """ Create a tracer for logging traces to Phoenix """
    from phoenix.config import get_env_host, get_env_port
    resource = Resource(attributes={
        ResourceAttributes.PROJECT_NAME: project_name
    })

    # checking if a global tracer already exists - avoids override issues
    _existing_provider = trace.get_tracer_provider()
    if isinstance(_existing_provider, trace.ProxyTracerProvider):
        tracer_provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(tracer_provider)
        tracer = trace.get_tracer(__name__ if not tracer_name else tracer_name)
        collector_endpoint = f"http://{get_env_host()}:{get_env_port()}/v1/traces"
        span_exporter = OTLPSpanExporter(endpoint=collector_endpoint)
        simple_span_processor = SimpleSpanProcessor(span_exporter=span_exporter)
        trace.get_tracer_provider().add_span_processor(simple_span_processor)
        return tracer
    return _existing_provider

def trace_flow(func):
    @functools.wraps(func)
    def wrap(cls, x, **kwargs):
        if cls._tracer is None:
            return func(cls, x)
        
        with cls._tracer.start_as_current_span("flow") as span:
            span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "CHAIN")
            #span.set_attribute(SpanAttributes.TAG_TAGS, str("['tag1','tag2']"))
            span.set_attribute(SpanAttributes.INPUT_VALUE, convert_to_string(x))
            span.set_attribute(SpanAttributes.INPUT_MIME_TYPE, "application/json" if type(x) in [list, dict] else "text/plain")
            #span.set_attribute(SpanAttributes.METADATA, "<ADDITIONAL_METADATA>")

            x = func(cls, x)

            span.set_attribute(SpanAttributes.OUTPUT_VALUE, convert_to_string(x)) # The output value of an operation
            span.set_attribute(SpanAttributes.OUTPUT_MIME_TYPE, "application/json" if type(x) in [list, dict] else "text/plain") # either text/plain or application/json

        return x
    return wrap

def trace_node(func):
    @functools.wraps(func)
    def wrap(cls, x, **kwargs):
        if cls._tracer is None:
            return func(cls, x)
        
        with cls._tracer.start_as_current_span(cls.name) as span:
            kind = cls._kind.upper() if cls._kind is not None else None
            span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, kind if hasattr(OpenInferenceSpanKindValues, kind) else "UNKNOWN")
            #span.set_attribute(SpanAttributes.TAG_TAGS, str("['tag1','tag2']"))
            span.set_attribute(SpanAttributes.INPUT_VALUE, convert_to_string(x))
            span.set_attribute(SpanAttributes.INPUT_MIME_TYPE, "application/json" if type(x) in [list, dict] else "text/plain")
            span.set_attribute(SpanAttributes.METADATA, convert_to_string(cls._metadata) if cls._metadata else "")

            x = func(cls, x)

            span.set_attribute(SpanAttributes.OUTPUT_VALUE, convert_to_string(x)) # The output value of an operation
            span.set_attribute(SpanAttributes.OUTPUT_MIME_TYPE, "application/json" if type(x) in [list, dict] else "text/plain") # either text/plain or application/json 

        return x
    return wrap

def _bind_tracer_to_node(node, tracer):
    node_type = type(node).__name__
    if node_type == "Recursive":
        node.node1._tracer = tracer
        node.node2._tracer = tracer

    elif node_type == "ConditionalBranch":
        for branch in node.branches:
            node.branches[branch]._tracer = tracer

    elif node_type == "Parralel":
        for node_name in node.nodes:
            node.nodes[node_name]._tracer = tracer

    else:
        node._tracer = tracer

    return node




