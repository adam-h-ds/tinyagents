import functools
from typing import TYPE_CHECKING

from opentelemetry import baggage
from openinference.semconv.trace import SpanAttributes
from openinference.semconv.trace import OpenInferenceSpanKindValues

from tinyagents.utils import convert_to_string, create_run_id

if TYPE_CHECKING:
    from tinyagents.nodes import NodeMeta

def trace_flow(func):
    """ Decorator for tracing the execution of a flow """
    @functools.wraps(func)
    def wrap(cls, inputs, **kwargs):

        if cls._tracer is None:
            return func(cls, inputs, **kwargs)
        
        run_id = create_run_id()
        
        with cls._tracer.start_as_current_span("flow", attributes={"run_id": run_id}) as flow:
            parent_ctx = baggage.set_baggage("context", "flow")
            flow.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "CHAIN")
            flow.set_attribute(SpanAttributes.INPUT_VALUE, convert_to_string(inputs))
            flow.set_attribute(SpanAttributes.INPUT_MIME_TYPE, "application/json" if type(inputs) in [list, dict] else "text/plain")

            outputs = func(cls, inputs, parent_context=parent_ctx, run_id=run_id, **kwargs)

            flow.set_attribute(SpanAttributes.OUTPUT_VALUE, convert_to_string(outputs)) # The output value of an operation
            flow.set_attribute(SpanAttributes.OUTPUT_MIME_TYPE, "application/json" if type(outputs) in [list, dict] else "text/plain") # either text/plain or application/json

        return outputs
    return wrap

def trace_node(func):
    """ Decorator for tracing the execution of a node """
    @functools.wraps(func)
    def wrap(cls: "NodeMeta", inputs, **kwargs):
        if cls._tracer is None:
            return func(cls, inputs, **kwargs)
        
        run_id = kwargs.get("run_id")

        parent_ctx = kwargs.get("parent_context")

        with cls._tracer.start_as_current_span(cls.name, attributes={"run_id": run_id}, context=parent_ctx) as span:
            kind = cls._kind.upper() if cls._kind is not None else None
            
            span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, kind if hasattr(OpenInferenceSpanKindValues, kind) else "UNKNOWN")
            span.set_attribute(SpanAttributes.INPUT_VALUE, convert_to_string(inputs))
            span.set_attribute(SpanAttributes.INPUT_MIME_TYPE, "application/json" if type(inputs) in [list, dict] else "text/plain")
            span.set_attribute(SpanAttributes.METADATA, convert_to_string(cls._metadata) if cls._metadata else "")

            outputs = func(cls, inputs, **kwargs)

            # set attributes for documents
            if kind == "RETRIEVER":
                docs = outputs.content

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
                span.set_attribute(SpanAttributes.OUTPUT_VALUE, convert_to_string(outputs))
                span.set_attribute(SpanAttributes.OUTPUT_MIME_TYPE, "application/json" if type(outputs) in [list, dict] else "text/plain") # either text/plain or application/json 

        return outputs
    return wrap