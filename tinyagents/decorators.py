from typing import Callable
from inspect import isclass

from tinyagents.nodes import NodeMeta

class Function:
    name: str
    run: Callable

def chainable(cls):
    if not isclass(cls):
        func_cls = Function
        func_cls.run = cls

    class ChainableNode(cls if isclass(cls) else func_cls, NodeMeta):
        name: str = cls.name if hasattr(cls, "name") else cls.__name__
        
        def __repr__(self):
            return self.name

    return ChainableNode