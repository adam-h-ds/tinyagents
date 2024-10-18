from typing import Optional, List, Any

from tinyagents.nodes import NodeMeta
from tinyagents.callbacks import BaseCallback
from tinyagents.utils import check_for_break, get_content

class Recursive(NodeMeta):
    """ A node for looping between two nodes (e.g. a conversation between two agents) """
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
    
    def invoke(self, inputs: Any, callbacks: Optional[List[BaseCallback]] = None, **kwargs):
        response = None
        n = 0
        x = inputs
        while not response and n <= self.max_iter:
            for node in [self.node1, self.node2]:
                x = get_content(x)

                if callbacks: [callback.node_start(node.name, x) for callback in callbacks]
                x = node.invoke(inputs=x, callbacks=callbacks, **kwargs)
                if callbacks: [callback.node_finish(node.name, x) for callback in callbacks]

                stop = check_for_break(x)
                if stop:
                    response = x
                    break
            n += 1

        return x
    
    async def ainvoke(self, inputs: Any, callbacks: Optional[List[BaseCallback]] = None, **kwargs):
        response = None
        n = 0
        x = inputs
        while not response and n <= self.max_iter:
            for node in [self.node1, self.node2]:
                x = get_content(x)

                if callbacks: [callback.node_start(node.name, input) for callback in callbacks]
                
                if hasattr(node.invoke, "remote"):
                    x = await node.ainvoke.remote(inputs=x, callbacks=callbacks, **kwargs)
                else:
                    x = await node.ainvoke(inputs=x, callbacks=callbacks, **kwargs)

                if callbacks: [callback.node_finish(node.name, x) for callback in callbacks]

                stop = check_for_break(x)
                if stop:
                    response = x
                    break
            n += 1

        return x
    