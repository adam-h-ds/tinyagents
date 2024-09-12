import logging
from typing import Any, Callable, Optional, Dict, Union, Literal
from abc import abstractmethod
from inspect import iscoroutinefunction
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from opentelemetry.sdk.trace import Tracer

from tinyagents.graph import Graph
from tinyagents.handlers import passthrough
from tinyagents.utils import check_for_break, get_content
from tinyagents.types import NodeOutput
from tinyagents.callbacks import BaseCallback
from tinyagents.tracing import trace_node, create_tracer

logger = logging.getLogger(__name__)

class NodeMeta:
    name: str
    _kind: Optional[Literal["tool", "llm", "retriever", "agent", "other"]]
    _ray_options: Optional[Dict[str, Any]]
    _metadata: Dict[str, Any]
    _tracer: Tracer

    def __truediv__(self, *args) -> "ConditionalBranch":
        return ConditionalBranch(self, *args)
        
    def __and__(self, *args) -> "Parralel":
        return Parralel(self, *args)
    
    def __or__(self, node: Any) -> Graph:
        if isinstance(node, Graph):
            node.next(self)
            return node
        
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
    def invoke(self, x: Any, callback: Optional[BaseCallback] = None) -> Union[NodeOutput, Dict[str, NodeOutput]]:
        if callback: callback.node_start(self.name, x)
        inputs = self.prepare_input(x)
        output = self.run(inputs)
        output = self.output_handler(output)
        if callback: callback.node_finish(self.name, output)
        return output
    
    @trace_node
    async def ainvoke(self, x: Any, callback: Optional[BaseCallback] = None) -> Union[NodeOutput, Dict[str, NodeOutput]]:
        if callback: callback.node_start(self.name, x)
        inputs = await self._async_run(self.prepare_input, x)
        output = await self._async_run(self.run, inputs)
        output = await self._async_run(self.output_handler, output)
        if callback: callback.node_finish(self.name, output)
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
    
class Parralel(NodeMeta):
    """ A node which parallelises a set of subnodes """
    name: str
    nodes: dict
    num_workers: int

    def __init__(self, *args, nodes: Optional[dict] = None, name: Optional[str] = None, num_workers: Optional[int] = None):
        if not nodes:
            self.nodes = {arg.name: arg for arg in args}
        else:
            self.nodes = nodes

        self.num_workers = num_workers
            
        if name == None:
            self.set_name("parallel_" + "_".join(self.nodes.keys()))
        else:
            self.set_name(name)

    def __repr__(self) -> str:
        nodes_str = " ∧ ".join(list(self.nodes.keys()))
        return f"Parallel({nodes_str})"
    
    def __and__(self, other_node) -> "Parralel":
        self.nodes[other_node.name] = other_node
        return self
    
    def invoke(self, x, callback: Optional[BaseCallback] = None) -> Dict[str, NodeOutput]:
        refs = {}
        outputs = {}
        with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            for name, node in self.nodes.items():
                if callback: callback.node_start(name, x)
                refs[name] = executor.submit(partial(node.invoke, x=x))

            for node_name in refs:
                output = refs[node_name].result()
                if callback: callback.node_finish(node_name, output)
                outputs[node_name] = output

        return outputs
    
    async def ainvoke(self, x, callback: Optional[BaseCallback] = None) -> Dict[str, NodeOutput]:
        refs = {}
        outputs = {}
        for name, node in self.nodes.items():
            if callback: callback.node_start(name, x)

            if hasattr(node, "remote"):
                refs[name] = node.invoke.remote(x=x, callback=callback)
            else:
                refs[name] = node.ainvoke(x=x, callback=callback)

        for node_name in refs:
            output = await refs[node_name]
            if callback: callback.node_finish(node_name, output)
            outputs[node_name] = output

        return outputs
    
    def set_max_workers(self, max_workers: int) -> None:
        self.max_workers = max_workers

class ConditionalBranch(NodeMeta):
    """ A node which represents a branch in the graph, """
    name: str
    branches: dict
    router: Optional[Callable] = None

    def __init__(self, *args, router: Optional[Callable] = None, branches: Optional[dict] = None, name: Optional[str] = None):
        if not branches:
            self.branches = {
                node.name: node for node in args
            }
        else:
            self.branches = branches

        if name == None:
            self.set_name("conditional_branch_" + "-".join(list(self.branches.keys())))
        else:
            self.set_name(name)

        self.router = router

    def __repr__(self) -> str:
        branches_str = " | ".join(list(self.branches.keys()))
        return f"ConditionalBranch({branches_str})"
    
    def __truediv__(self, other_node):
        self.branches[other_node.name] = other_node
        return self
    
    def bind_router(self, router: Callable) -> "ConditionalBranch":
        self.router = router
        return self
    
    def invoke(self, x: Any, callback: Optional[BaseCallback] = None) -> NodeOutput:
        if callback: callback.node_start(self.name, x)
        route = self._get_route(x)
        node = self._get_node(route)
        if callback: callback.node_finish(self.name, route)
        output = node.invoke(x=x, callback=callback)
        return output
    
    async def ainvoke(self, x: Any, callback: Optional[BaseCallback] = None):
        if callback: callback.node_start(self.name, x)
        route = self._get_route(x)
        node = self._get_node(route)
        if callback: callback.node_finish(self.name, route)

        if hasattr(node.invoke, "remote"):
            output = await node.invoke.remote(x=x, callback=callback)
        else:
            output = node.invoke(x=x, callback=callback)

        return output
    
    def _get_route(self, x: Any) -> str:
        """ If a router is provided, use it to determine the appropriate route. Otherwise assume the given inputs are the route to take """
        if not self.router:
            return x
     
        return self.router(x)

    def _get_node(self, route: str):
        try:
            return self.branches[route]
        except KeyError:
            raise Exception(f"The router gave route `{str(route)}` but this is not one of the available routes `{list(self.branches.keys())}`.")
    
class Recursive(NodeMeta):
    """ A node for looping the execution of two subnodes (e.g. a conversation between two agents)"""
    name: str
    node1: NodeMeta
    node2: NodeMeta
    max_iter: int

    def __init__(self, node1, node2, max_iter: int = 3, name: Optional[str] = None):
        self.node1 = node1
        self.node2 = node2
        self.max_iter = max_iter

        if name == None:
            self.set_name(f"recursive_{node1.name}_{node2.name}")
        else:
            self.set_name(name)

    def __repr__(self):
        return f"Recursive({self.node1.name}, {self.node2.name})"
    
    def invoke(self, x, callback: Optional[BaseCallback] = None):
        response = None
        n = 0
        while not response and n <= self.max_iter:
            for node in [self.node1, self.node2]:
                x = get_content(x)

                if callback: callback.node_start(node.name, x)
                x = node.invoke(x=x, callback=callback)
                if callback: callback.node_finish(node.name, x)

                stop = check_for_break(x)
                if stop:
                    response = x
                    break

            n += 1

        return x
    
    async def ainvoke(self, x, callback: Optional[BaseCallback] = None):
        response = None
        n = 0
        while not response and n <= self.max_iter:
            for node in [self.node1, self.node2]:
                x = get_content(x)

                if callback: callback.node_start(node.name, input)
                if hasattr(node.invoke, "remote"):
                    x = await node.ainvoke.remote(x=x, callback=callback)
                else:
                    x = await node.ainvoke(x=x, callback=callback)
                if callback: callback.node_finish(node.name, x)

                stop = check_for_break(x)
                if stop:
                    response = x
                    break
                
            n += 1

        return x