import logging
from typing import Any, Callable
from abc import abstractmethod
from hashlib import md5

from tinyagents.graph import Graph
from tinyagents.handlers import passthrough
from tinyagents.utils import check_for_break
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
    
    abstractmethod
    def execute(self, inputs: Any) -> Any:
        output = self.run(inputs)
        return self.output_handler(output)
    
    def as_graph(self):
        graph = Graph()
        graph.next(self)
        return graph   
    
class Parralel(NodeMeta):
    """ A node which parallelises a set of subnodes """
    name: str
    nodes: list = []

    def __init__(self, *args, name: str = None):
        self.nodes = [arg for arg in args]
        if not name:
            self.set_name(self._get_hash())

    def __repr__(self):
        nodes_str = " ∧ ".join([branch.name for branch in self.nodes])
        return f"Parallel({nodes_str})"
    
    def __and__(self, other_node):
        self.nodes.append(other_node)
        return self
    
    def _get_hash(self):
        return md5(str(self.nodes).encode("utf-8")).hexdigest()
    
    def execute(self, inputs, callback: BaseCallback = None):
        outputs = []
        # TODO: add parallelisation here
        for node in self.nodes:
            if callback: callback.node_start(self.name, inputs)
            output = node.execute(inputs)
            if callback: callback.node_finish(self.name, output)
            outputs.append(output)
        return outputs
        
    
class ConditionalBranch(NodeMeta):
    """ A node which represents a branch in the graph, """
    name: str = None
    branches: dict = {}
    router: Callable = None

    def __init__(self, *args):
        self.branches = {
            node.name: node for node in args
        }

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
    
    def execute(self, inputs: Any, callback: BaseCallback = None):
        if callback: callback.node_start(self.name, inputs)

        # if no router has been set, assune the inputs to the node is the name of the node to execute
        if not self.router:
            route = inputs
        else:
            route = self.router(inputs)

        x = self.branches[route].execute(inputs)

        if callback: callback.node_finish(self.name, x)
        return x
    
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
    
    def execute(self, x, callback: BaseCallback = None):
        response = None
        n = 0
        while not response and n <= self.max_iter:
            for node in [self.node1, self.node2]:
                input = x.content if isinstance(x, NodeOutput) else x

                if callback: callback.node_start(node.name, input)
                x = node.execute(input)
                if callback: callback.node_finish(node.name, x)

                response = check_for_break(x)
                if response:
                    break

            n += 1

        return x