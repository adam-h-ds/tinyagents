import functools
import os

from ray.serve.handle import DeploymentHandle 

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from openinference.semconv.trace import SpanAttributes
from openinference.semconv.trace import OpenInferenceSpanKindValues, DocumentAttributes
from openinference.semconv.resource import ResourceAttributes

from tinyagents.utils import convert_to_string

def create_tracer():
    """Create a tracer for logging traces using OpenTelemtry """
    resource = Resource(attributes={
        ResourceAttributes.PROJECT_NAME: os.environ.get("PHOENIX_PROJECT_NAME", "default")
    })
    collector_endpoint = os.environ.get("COLLECTOR_ENDPOINT")
    if not collector_endpoint:
        from phoenix.config import get_env_host, get_env_port
        collector_endpoint = f"http://{get_env_host()}:{get_env_port()}/v1/traces"

    # checking if a global tracer already exists - avoids override issues
    _existing_provider = trace.get_tracer_provider()
    if not isinstance(_existing_provider, trace.ProxyTracerProvider):
        return trace.get_tracer(__name__)
    
    tracer_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(tracer_provider)
    tracer = trace.get_tracer(__name__)
    span_exporter = OTLPSpanExporter(endpoint=collector_endpoint)
    simple_span_processor = SimpleSpanProcessor(span_exporter=span_exporter)
    trace.get_tracer_provider().add_span_processor(simple_span_processor)
    return tracer

def _check_tracing_enabled():
    return os.environ.get("TINYAGENTS_ENABLE_TRACING", "false") == "true"

def _init_node_tracers(nodes):
    """ Trigger the initialisation of tracers for all nodes """
    for node in nodes:
        node_type = type(node).__name__
        if node_type == "Recursive":
            _init_tracer(node.node1)
            _init_tracer(node.node2)

        elif node_type == "ConditionalBranch":
            for branch in node.branches:
                _init_tracer(node.branches[branch])

        elif node_type == "Parralel":
            for node_name in node.nodes:
                _init_tracer(node.nodes[node_name])

        else:
            _init_tracer(node)

def _init_tracer(node):
    """ Initialise tracer for local or remote nodes"""
    # if the node is remote
    if isinstance(node, DeploymentHandle):
        node._init_tracer.remote()

    node._init_tracer()

def trace_flow(func):
    """ Decorator for tracing the execution of a flow """
    @functools.wraps(func)
    def wrap(cls, x, **kwargs):
        if cls._tracer is None:
            return func(cls, x, **kwargs)
        
        with cls._tracer.start_as_current_span("flow") as span:
            span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "CHAIN")
            span.set_attribute(SpanAttributes.INPUT_VALUE, convert_to_string(x))
            span.set_attribute(SpanAttributes.INPUT_MIME_TYPE, "application/json" if type(x) in [list, dict] else "text/plain")

            x = func(cls, x, **kwargs)

            span.set_attribute(SpanAttributes.OUTPUT_VALUE, convert_to_string(x)) # The output value of an operation
            span.set_attribute(SpanAttributes.OUTPUT_MIME_TYPE, "application/json" if type(x) in [list, dict] else "text/plain") # either text/plain or application/json

        return x
    return wrap

def trace_node(func):
    """ Decorator for tracing the execution of a node """
    @functools.wraps(func)
    def wrap(cls, x, **kwargs):
        if cls._tracer is None:
            return func(cls, x, **kwargs)
        
        with cls._tracer.start_as_current_span(cls.name) as span:
            kind = cls._kind.upper() if cls._kind is not None else None

            span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, kind if hasattr(OpenInferenceSpanKindValues, kind) else "UNKNOWN")
            span.set_attribute(SpanAttributes.INPUT_VALUE, convert_to_string(x))
            span.set_attribute(SpanAttributes.INPUT_MIME_TYPE, "application/json" if type(x) in [list, dict] else "text/plain")
            span.set_attribute(SpanAttributes.METADATA, convert_to_string(cls._metadata) if cls._metadata else "")

            x = func(cls, x, **kwargs)

            # set attributes for documents
            if kind == "RETRIEVER":
                docs = x.content

                if isinstance(docs, str):
                    docs = [docs]

                if isinstance(docs, list) and len(docs) > 0:
                    if isinstance(docs[0], str):
                        docs = [dict(id=i, content=doc) for i, doc in enumerate(docs)]

                    if isinstance(docs[0], dict):
                        for i, doc in enumerate(docs):
                            for key, value in doc.items():
                                if key in ["id", "content", "score", "metadata"]:
                                    span.set_attribute(f"retrieval.documents.{i}.document.{key}", convert_to_string(value))
                    else:
                        span.set_attribute(SpanAttributes.OUTPUT_VALUE, convert_to_string(docs)) # The output value of an operation

            else:
                span.set_attribute(SpanAttributes.OUTPUT_VALUE, convert_to_string(x))
                span.set_attribute(SpanAttributes.OUTPUT_MIME_TYPE, "application/json" if type(x) in [list, dict] else "text/plain") # either text/plain or application/json 

        return x
    return wrap



