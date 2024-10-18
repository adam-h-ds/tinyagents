from typing import Any, Optional, Union, List
from json.decoder import JSONDecodeError

from ray.serve import deployment
import starlette
import starlette.requests

from tinyagents.callbacks import BaseCallback, StdoutCallback
from tinyagents.utils import check_for_break, get_content, create_run_id
import tinyagents.deployment_utils as deploy_utils
from tinyagents.tracing import trace_flow, init_all_tracers, create_tracer, check_tracing_enabled
from tinyagents.types import NodeOutput

class GraphRunner:
    """ A runner for executing the graph. """

    def __init__(self, nodes: list, callbacks: Optional[List[BaseCallback]] = None):
        """
        Initializes the GraphRunner with a list of nodes and an optional callback.

        Args:
            nodes (list): A list of nodes to be executed in the graph.
            callback (Optional[BaseCallback]): An optional callback for tracking execution.
        """
        self.nodes = nodes
        self.callbacks = callbacks
        self._tracer = None

        if check_tracing_enabled():
            self._tracer = create_tracer() 
            init_all_tracers(nodes)

    @trace_flow
    def invoke(self, inputs: Any, **kwargs):
        """
        Executes the graph synchronously with the given inputs.

        Args:
            inputs (Any): The input data for the graph execution.
            **kwargs: Additional keyword arguments.

        Returns:
            Any: The output of the graph execution.
        """
        run_id = create_run_id() if "run_id" not in kwargs else kwargs.pop("run_id")

        if self.callbacks: [callback.flow_start(inputs=inputs, run_id=run_id) for callback in self.callbacks]

        x = inputs
        for node in self.nodes:
            x = get_content(x)
            x = node.invoke(x, callbacks=self.callbacks, run_id=run_id, **kwargs) 
            stop = check_for_break(x)
            if stop:
                break

        if isinstance(x, NodeOutput):
            x = x.content

        if self.callbacks: [callback.flow_end(outputs=x, run_id=run_id) for callback in self.callbacks]

        return x
    
    @trace_flow
    async def ainvoke(self, inputs: Any, **kwargs):
        """
        Executes the graph asynchronously with the given inputs.

        Args:
            inputs (Any): The input data for the graph execution.
            **kwargs: Additional keyword arguments.

        Returns:
            Any: The output of the graph execution.
        """
        run_id = create_run_id() if "run_id" not in kwargs else kwargs.pop("run_id")
        if self.callbacks: [callback.flow_start(inputs=inputs, run_id=run_id) for callback in self.callbacks]

        x = inputs
        for node in self.nodes:
            x = get_content(x)

            if hasattr(node.ainvoke, "remote"):
                x = await node.ainvoke.remote(inputs=x, callbacks=self.callbacks, **kwargs)
            else:
                x = await node.ainvoke(inputs=x, callbacks=self.callbacks, **kwargs)

            stop = check_for_break(x)

            if stop:
                break

        if isinstance(x, NodeOutput):
            x = x.content
        
        if self.callbacks: [callback.flow_end(outputs=x, run_id=run_id) for callback in self.callbacks]

        return x
    
@deployment(name="runner")
class GraphDeployment:
    """ A deployment class for executing the graph in a deployment context. """

    def __init__(self, nodes: list, callbacks: Optional[List[BaseCallback]] = None):
        """
        Initializes the GraphDeployment with a list of nodes and an optional callback.

        Args:
            nodes (list): A list of nodes to be executed in the graph.
            callback: An optional callback for tracking execution.
        """
        self.runner = GraphRunner(nodes, callbacks=callbacks)
    
    async def ainvoke(self, inputs: Any):
        """
        Asynchronously invokes the graph with the given inputs.

        Args:
            inputs (Any): The input data for the graph execution.

        Returns:
            Any: The output of the graph execution.
        """
        return await self.runner.ainvoke(inputs)

    async def __call__(self, request: starlette.requests.Request):
        """
        Handles a REST request by invoking the graph.

        Args:
            request (starlette.requests.Request): The incoming HTTP request.

        Returns:
            Any: The output of the graph execution.
        """
        assert(isinstance(request, starlette.requests.Request)), "The `__call__` method is only used for handling REST requests. Use the `ainvoke()` method instead."
        
        try:
            request = await request.json()
        except JSONDecodeError:
            request = await request.body()
            request = request.decode("utf-8")

        return await self.runner.ainvoke(request)
    
    async def _get_meta(self):
        """
        Retrieves metadata for all nodes in the graph.

        Returns:
            list: A list of metadata for each node.
        """
        return [await node._get_meta.remote() for node in self.runner.nodes]
    
class Graph:
    """ A class representing a graph of nodes. """

    name: str
    _state: list
    _compiled: bool = False

    def __init__(self):
        """ Initializes the Graph with an empty state. """
        self._state = []

    def compile(
            self, 
            use_ray: bool = False,
            single_deployment: bool = False,
            runner_ray_options: dict = {}, 
            callbacks: Optional[List[BaseCallback]] = None, 
            verbose: bool = True
        ) -> Union["GraphRunner", "GraphDeployment"]:
        """
        Creates a GraphRunner or GraphDeployment that can be used to execute the graph.

        Args:
            use_ray (bool): Whether to convert nodes to Ray Deployments.
            single_deployment (bool): Whether to contain all nodes within a single Ray Deployment.
            runner_ray_options (dict): The Ray Actor options for the GraphRunner deployment.
            callbacks (List[BaseCallback]): A list of callbacks that should be used.
            verbose (bool): Whether to print the node outputs to the console.

        Returns:
            Union[GraphRunner, GraphDeployment]: The created GraphRunner or GraphDeployment.
        """
        if verbose and (not callbacks or not any(isinstance(callback, StdoutCallback) for callback in callbacks)):
            callbacks = [StdoutCallback()] + (callbacks if callbacks is not None else [])

        if not use_ray:
            return GraphRunner(nodes=self._state, callbacks=callbacks)

        # check if nodes have already been converted to deployments
        if not self._compiled and not single_deployment:
            self._state = deploy_utils.nodes_to_deployments(graph_nodes=self._state)
            self._compiled = True

        return GraphDeployment.options(**runner_ray_options).bind(self._state, callbacks=callbacks)

    def next(self, node: Any) -> None:
        """
        Adds a node to the graph.

        Args:
            node (Any): The node to be added to the graph.
        """
        if isinstance(node, Graph):
            print(self._state, node._state)
            self._state.extend(node._state)
            return
        
        self._state.append(node)

    def __str__(self) -> str:
        """ Returns a string representation of the graph. """
        return "".join([f" {node.__repr__()} ->" for node in self._state])[:-3].strip()
    
    def __or__(self, node: Any):
        """ Adds a node to the graph using the 'or' operator. """
        self.next(node)
        return self
    
    def __and__(self, other):
        """ Combines this graph with another using the 'and' operator. """
        from tinyagents.nodes import SubGraph, Parallel
        return Parallel(SubGraph(self, name=self.name), SubGraph(other, name=other.name))
    
    def __truediv__(self, other) -> "ConditionalBranch":
        """ Creates a conditional branch with another graph. """
        from tinyagents.nodes import SubGraph, ConditionalBranch
        return ConditionalBranch(SubGraph(self, name=self.name), SubGraph(other, name=other.name))

    @property
    def name(self):
        """ Returns the name of the graph based on its nodes. """
        return "graph_" + "_".join([node.name for node in self._state])