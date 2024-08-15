from typing import Any, Optional, Union
from json.decoder import JSONDecodeError

from ray.serve import deployment
import starlette
import starlette.requests
from opentelemetry.sdk.trace import Tracer

from tinyagents.callbacks import BaseCallback, StdoutCallback
from tinyagents.utils import check_for_break, get_content, create_run_id
import tinyagents.deployment_utils as deploy_utils
from tinyagents.tracing import trace_flow, _init_node_tracers, create_tracer, _check_tracing_enabled

class GraphRunner:
    """ A runner for executing the graph """

    def __init__(self, nodes: list, callback: Optional[BaseCallback] = None):
        self.nodes = nodes
        self.callback = callback
        self._tracer = None

        if _check_tracing_enabled():
            self._tracer = create_tracer() 
            _init_node_tracers(nodes)

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
    
    @trace_flow
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
    
class Graph:
    _state: list
    _compiled: bool = False

    def __init__(self):
        self._state = []

    def compile(self, use_ray: bool = False, ray_options: dict = {}, callback: BaseCallback = StdoutCallback()) -> Union["GraphRunner", "GraphDeployment"]:
        """Create a GraphRunner that can be used to execute the graph.
        
        Args:
            use_ray: whether to convert nodes to Ray Deployments (including the GraphRunner), which can be deployed using `serve.run`.
            ray_options: the Ray Actor options for the GraphRunner deployment - this is only used if `use_ray=True`.
            callback: a callback that should be used - see `tinyagents.callbacks` to create your own or see when each of the methods are called.
            enable_tracing: whether to use trace the graph using OpenTelemetry and OpenInference attributes (see https://github.com/Arize-ai/openinference). Traces can be visualised using Phoenix.
        """
        if not use_ray:
            return GraphRunner(nodes=self._state, callback=callback)

        if not self._compiled:
            nodes = deploy_utils.nodes_to_deployments(graph_nodes=self._state, ray_options=ray_options)
            self._compiled = True

        return GraphDeployment.options(**ray_options).bind(nodes, callback=callback)

    def next(self, node: Any) -> None:
        self._state.append(node)

    def __str__(self) -> str:
        return "".join([f" {node.__repr__()} ->" for node in self._state])[:-3].strip()
    
    def __or__(self, node: Any):
        self.next(node)
        return self