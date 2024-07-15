import logging
from typing import Any, Callable, Optional, Dict
from abc import abstractmethod
from hashlib import md5
from inspect import iscoroutinefunction
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from tinyagents.graph import Graph
from tinyagents.handlers import passthrough
from tinyagents.utils import check_for_break, get_content
from tinyagents.types import NodeOutput
from tinyagents.callbacks import BaseCallback

logger = logging.getLogger(__name__)

class NodeMeta:
    name: str

    @abstractmethod
    def __truediv__(self, *args):
        return ConditionalBranch(self, *args)
        
    @abstractmethod
    def __and__(self, *args):
        return Parralel(self, *args)
    
    @abstractmethod
    def __or__(self, node: Any):
        if isinstance(node, Graph):
            node.next(self)
            return node
        
        graph = Graph()
        graph.next(self)
        graph.next(node)
        return graph

    @abstractmethod
    def set_name(self, name: str):
        self.name = name

    @abstractmethod
    def run(self, inputs: Any):
        pass

    @abstractmethod
    def output_handler(self, outputs: Any):
        return passthrough(outputs)
    
    @abstractmethod
    def prepare_input(self, inputs: Any):
        return get_content(inputs)
    
    @abstractmethod
    def invoke(self, inputs: Any, callback: BaseCallback = None) -> Any:
        if callback: callback.node_start(self.name, inputs)
        inputs = self.prepare_input(inputs)
        output = self.run(inputs)
        output = self.output_handler(output)
        if callback: callback.node_finish(self.name, output)
        return output
    
    @abstractmethod
    async def ainvoke(self, inputs: Any, callback: BaseCallback = None):
        if callback: callback.node_start(self.name, inputs)
        inputs = await self._async_run(self.prepare_input, inputs)
        output = await self._async_run(self.run, inputs)
        output = await self._async_run(self.output_handler, output)
        if callback: callback.node_finish(self.name, output)
        return output
    
    @staticmethod
    async def _async_run(func: Callable, inputs: Any):
        if iscoroutinefunction(func):
            return await func(inputs)
        return func(inputs)
    
    def as_graph(self):
        graph = Graph()
        graph.next(self)
        return graph   
    
class Parralel(NodeMeta):
    """ A node which parallelises a set of subnodes """
    name: str
    nodes: dict
    num_workers: int

    def __init__(self, *args, nodes: Optional[dict] = None, name: str = None, num_workers: int = None):
        if not nodes:
            self.nodes = {arg.name: arg for arg in args}
        else:
            self.nodes = nodes

        self.num_workers = num_workers
            
        if not name:
            self.set_name("parallel_" + "_".join(self.nodes.keys()))

    def __repr__(self):
        nodes_str = " ∧ ".join(list(self.nodes.keys()))
        return f"Parallel({nodes_str})"
    
    def __and__(self, other_node):
        self.nodes[other_node.name] = other_node
        return self
    
    def invoke(self, inputs, callback: BaseCallback = None) -> Dict[str, NodeOutput]:
        refs = {}
        outputs = {}
        with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            for name, node in self.nodes.items():
                if callback: callback.node_start(name, inputs)
                refs[name] = executor.submit(partial(node.invoke, inputs))

            for node_name in refs:
                output = refs[node_name].result()
                if callback: callback.node_finish(node_name, output)
                outputs[node_name] = output

        return outputs
    
    async def ainvoke(self, inputs, callback: BaseCallback = None) -> Dict[str, NodeOutput]:
        refs = {}
        outputs = {}
        for name, node in self.nodes.items():
            if callback: callback.node_start(name, inputs)

            if hasattr(node, "remote"):
                refs[name] = node.invoke.remote(inputs)
            else:
                refs[name] = node.ainvoke(inputs)

        for node_name in refs:
            output = await refs[node_name]
            if callback: callback.node_finish(node_name, output)
            outputs[node_name] = output

        return outputs

class ConditionalBranch(NodeMeta):
    """ A node which represents a branch in the graph, """
    name: str = None
    branches: dict
    router: Callable = None

    def __init__(self, *args, router: Optional[Callable] = None, branches: Optional[dict] = None):
        if not branches:
            self.branches = {
                node.name: node for node in args
            }
        else:
            self.branches = branches

        self.router = router

    def __repr__(self):
        branches_str = " | ".join(list(self.branches.keys()))
        return f"ConditionalBranch({branches_str})"
    
    def __truediv__(self, other_node):
        self.branches[other_node.name] = other_node
        return self
    
    @property
    def name(self):
        return self.__repr__()
    
    def bind_router(self, router: Callable):
        self.router = router
        return self
    
    def invoke(self, inputs: Any, callback: BaseCallback = None):
        if callback: callback.node_start(self.name, inputs)
        route = self._get_route(inputs)
        node = self._get_node(route)
            
        output = node.invoke(inputs)
        
        if callback: callback.node_finish(self.name, output)
        return output
    
    async def ainvoke(self, inputs: Any, callback: BaseCallback = None):
        if callback: callback.node_start(self.name, inputs)
        route = self._get_route(inputs)
        node = self._get_node(route)

        if hasattr(node.invoke, "remote"):
            output = await node.invoke.remote(inputs)
        else:
            output = node.invoke(inputs)

        if callback: callback.node_finish(self.name, output)
        return output
    
    def _get_route(self, inputs) -> str:
        """ If a router is provided, use it to determine the appropriate route. Otherwise assume the given inputs are the route to take """
        if not self.router:
            return inputs
     
        return self.router(inputs)

    def _get_node(self, route: str):
        try:
            return self.branches[route]
        except KeyError:
            raise Exception(f"The router gave route `{str(route)}` but this is not one of the available routes `{list(self.branches.keys())}`.")
    
class Recursive(NodeMeta):
    """ A node for looping the execution of two subnodes (e.g. a conversation between two agents)"""
    name: str = None
    node1: NodeMeta = None
    node2: NodeMeta = None
    max_iter: int = None

    def __init__(self, node1, node2, max_iter: int = 3, name: str = None):
        self.node1 = node1
        self.node2 = node2
        self.max_iter = max_iter
        self.name = name

    def __repr__(self):
        return f"Recursive({self.node1.name}, {self.node2.name})"
    
    def invoke(self, x, callback: BaseCallback = None):
        response = None
        n = 0
        while not response and n <= self.max_iter:
            for node in [self.node1, self.node2]:
                input = get_content(x)

                if callback: callback.node_start(node.name, input)
                x = node.invoke(x)
                if callback: callback.node_finish(node.name, x)

                stop = check_for_break(x)
                if stop:
                    response = x
                    break

            n += 1

        return x
    
    async def ainvoke(self, x, callback: BaseCallback = None):
        n = 0
        while not response and n <= self.max_iter:
            for node in [self.node1, self.node2]:
                input = get_content(x)

                if callback: callback.node_start(node.name, input)
                x = await node.ainvoke(x)
                if callback: callback.node_finish(node.name, x)

                stop = check_for_break(x)
                if stop:
                    response = x
                    break
                
            n += 1

        return x