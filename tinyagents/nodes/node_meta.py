from typing import Any, Callable, Optional, Dict, Union, Literal, List
from inspect import iscoroutinefunction

from opentelemetry.sdk.trace import Tracer

from tinyagents.graph import Graph
from tinyagents.handlers import passthrough
from tinyagents.utils import get_content
from tinyagents.types import NodeOutput
from tinyagents.callbacks import BaseCallback
from tinyagents.tracing import trace_node, create_tracer

class NodeMeta:
    name: str
    _kind: Optional[Literal["tool", "llm", "retriever", "agent", "other"]]
    _ray_options: Optional[Dict[str, Any]]
    _metadata: Dict[str, Any]
    _tracer: Tracer

    def __truediv__(self, *args) -> "ConditionalBranch":
        from tinyagents.nodes import ConditionalBranch
        return ConditionalBranch(self, *args)
        
    def __and__(self, *args) -> "Parallel":
        from tinyagents.nodes import Parallel
        return Parallel(self, *args)
    
    def __or__(self, node: Any) -> Graph:
        graph = Graph()
        graph.next(self)
        graph.next(node)
        return graph

    def set_name(self, name: str) -> None:
        self.name = name

    def run(self, inputs: Any) -> Any:
        raise NotImplementedError()

    def output_handler(self, outputs: Any) -> NodeOutput:
        return passthrough(outputs)
    
    def prepare_input(self, inputs: Any) -> Any:
        return get_content(inputs)
    
    @trace_node
    def invoke(self, inputs: Any, callbacks: Optional[List[BaseCallback]] = None, **kwargs) -> Union[NodeOutput, Dict[str, NodeOutput]]:
        run_id = kwargs.get("run_id")
        if callbacks: [callback.node_start(inputs=inputs, node_name=self.name, run_id=run_id) for callback in callbacks]
        inputs = self.prepare_input(inputs)
        output = self.run(inputs)
        output = self.output_handler(output)
        if callbacks: [callback.node_finish(outputs=output, node_name=self.name, run_id=run_id) for callback in callbacks]
        return output
    
    @trace_node
    async def ainvoke(self, inputs: Any, callbacks: Optional[List[BaseCallback]] = None, **kwargs) -> Union[NodeOutput, Dict[str, NodeOutput]]:
        run_id = kwargs.get("run_id")
        if callbacks: [callback.node_start(inputs=inputs, node_name=self.name, run_id=run_id) for callback in callbacks]
        inputs = await self._async_run(self.prepare_input, inputs)
        output = await self._async_run(self.run, inputs)
        output = await self._async_run(self.output_handler, output)
        if callbacks: [callback.node_finish(outputs=output, node_name=self.name, run_id=run_id) for callback in callbacks]
        return output
    
    @staticmethod
    async def _async_run(func: Callable, inputs: Any) -> Any:
        if iscoroutinefunction(func):
            return await func(inputs)
        return func(inputs)
    
    def as_graph(self) -> Graph:
        graph = Graph()
        graph.next(self)
        return graph   
    
    def _init_tracer(self):
        self._tracer = create_tracer()

    def _get_meta(self):
        return self._metadata