from typing import Any, Optional
from json.decoder import JSONDecodeError
from contextlib import nullcontext

from ray.serve import deployment
import starlette
import starlette.requests
from opentelemetry.sdk.trace import Tracer

from tinyagents.callbacks import BaseCallback, StdoutCallback
from tinyagents.utils import check_for_break, get_content, create_run_id, convert_to_string
import tinyagents.deployment_utils as deploy_utils
from tinyagents.tracing import trace_flow, _bind_tracer_to_node

class Graph:
    _state: list
    _compiled: bool = False

    def __init__(self):
        self._state = []

    def compile(self, use_ray: bool = False, ray_options: dict = {}, callback: BaseCallback = StdoutCallback(), tracer: Tracer = None):
        if not use_ray:
            return GraphRunner(nodes=self._state, callback=callback, tracer=tracer)

        if self._compiled:
            raise Exception("Nodes in the graph have already been constructed as Ray deployments.")
        
        nodes = deploy_utils.nodes_to_deployments(graph_nodes=self._state, ray_options=ray_options)
        self._compiled = True
        return GraphDeployment.options(**ray_options.get("runner", {})).bind(nodes, callback=callback)

    def next(self, node: Any) -> None:
        self._state.append(node)

    def __str__(self) -> str:
        return "".join([f" {node.__repr__()} ->" for node in self._state])[:-3].strip()
    
    def __or__(self, node: Any):
        self.next(node)
        return self

class GraphRunner:
    """ A class for executing the graph """

    def __init__(self, nodes: list, callback: Optional[BaseCallback] = None, tracer: Tracer = None):
        self.nodes = nodes
        self.callback = callback
        self._tracer = tracer

        if self._tracer:
            for node in self.nodes:
                node = _bind_tracer_to_node(node=node, tracer=self._tracer)

    @trace_flow
    def invoke(self, x: Any):
        run_id = create_run_id()

        if self.callback: self.callback.flow_start(ref=run_id, inputs=x)

        for node in self.nodes:
            input = get_content(x)
            x = node.invoke(input, callback=self.callback) 
            stop = check_for_break(x)

            if stop:
                break
        
        if self.callback: self.callback.flow_end(ref=run_id, outputs=x)

        return x.content
    
    async def ainvoke(self, x: Any):
        run_id = create_run_id()

        if self.callback: self.callback.flow_start(ref=run_id, inputs=x)

        for node in self.nodes:
            input = get_content(x)

            if hasattr(node.invoke, "remote"):
                x = await node.ainvoke.remote(input, callback=self.callback)
            else:
                x = await node.ainvoke(input, callback=self.callback)

            stop = check_for_break(x)

            if stop:
                break
        
        if self.callback: self.callback.flow_end(ref=run_id, outputs=x)

        return x.content
    
@deployment(name="runner")
class GraphDeployment:
    def __init__(self, nodes: list, callback = None):
        self.runner = GraphRunner(nodes, callback=callback)
        self.callback = callback
    
    async def ainvoke(self, inputs: Any):
        return await self.runner.ainvoke(inputs)

    async def __call__(self, request: starlette.requests.Request):
        assert(isinstance(request, starlette.requests.Request)), "The `__call__` method is only used for handling REST requests. Use the `ainvoke()` method instead."
        
        try:
            request = await request.json()
        except JSONDecodeError:
            request = await request.body()
            request = request.decode("utf-8")

        return await self.runner.ainvoke(request)