from typing import Optional

from tinyagents.nodes import NodeMeta
from tinyagents.graph import Graph
from tinyagents.callbacks import BaseCallback
from tinyagents.utils import check_for_break, get_content
from tinyagents.types import NodeOutput

class SubGraph(NodeMeta):
    """ A node which contains a graph """
    name: str
    _state: list

    def __init__(self, graph: Graph, name: str):
        self.name = name
        self._state = graph._state

    def __repr__(self):
        subgraph_nodes_repr = " | ".join([node.name for node in self._state])
        return f"SubGraph({subgraph_nodes_repr})"
    
    def invoke(self, x, callback: Optional[BaseCallback] = None, **kwargs) -> NodeOutput:
        for node in self._state:
            x = get_content(x)
            x = node.invoke(x=x, callback=callback, **kwargs)
            stop = check_for_break(x)
            if stop:
                break
        return x
    
    async def ainvoke(self, x, callback: Optional[BaseCallback] = None, **kwargs) -> NodeOutput:
        for node in self._state:
            x = get_content(x)
            if hasattr(node, "remote"):
                x = await node.ainvoke.remote(x=x, callback=callback, **kwargs)
            else:
                x = node.invoke(x=x, callback=callback, **kwargs)
            stop = check_for_break(x)
            if stop:
                break
        return x