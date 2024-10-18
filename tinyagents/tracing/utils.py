import os

from ray.serve.handle import DeploymentHandle 

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import Tracer
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from openinference.semconv.resource import ResourceAttributes

def create_tracer() -> Tracer:
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

def check_tracing_enabled():
    return os.environ.get("TINYAGENTS_ENABLE_TRACING", "false") == "true"

def init_all_tracers(nodes):
    """ Trigger the initialisation of tracers for all nodes """
    for node in nodes:
        node_type = type(node).__name__

        if node_type == "SubGraph":
            init_all_tracers(node._state)
        else:
            _init_node_tracer(node)

def _handle_remote_node(node):
    """ Initialise tracer for local or remote nodes"""
    # if the node is remote
    if isinstance(node, DeploymentHandle):
        node._init_tracer.remote()
        return

    node._init_tracer()

def _init_node_tracer(node):
    node_type = type(node).__name__

    if node_type == "ChainableNode":
        _handle_remote_node(node)

    elif node_type == "Recursive":
        init_all_tracers([node.node1, node.node2])

    elif node_type == "ConditionalBranch":
        init_all_tracers(list(node.branches.values()))

    elif node_type == "Parallel":
        init_all_tracers(list(node.nodes.values()))


