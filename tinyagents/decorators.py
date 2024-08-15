from typing import Callable, Dict, Any, Union, Type, Optional, Literal
from inspect import isclass

from tinyagents.nodes import NodeMeta

class Function:
    name: str
    run: Callable

def chainable(
        *args,
        kind: Optional[Literal["tool", "llm", "retriever", "agent, ""other"]] = "other",
        ray_options: Optional[Dict[str, Any]] = {},
        metadata: Dict[str, Any] = {}
    ):
    assert(kind in ["tool", "llm", "retriever", "agent", "other"]), f"`{kind}` is not a valid node type, must be one of ['tool', 'llm', 'retriever', 'agent', 'other']"
    def decorator(cls: Union[Type, Callable]) -> Type:
        if not isclass(cls):
            func_cls = Function
            func_cls.run = cls

        class ChainableNode(cls if isclass(cls) else func_cls, NodeMeta):
            name: str = getattr(cls, 'name', cls.__name__)
            _kind: str = kind
            _metadata: Dict[str, Any] = metadata
            _ray_actor_options: Dict[str, Any] = ray_options
            _tracer: "Tracer" = None

            def __repr__(self):
                return self.name

        return ChainableNode

    return decorator(cls=args[0]) if len(args) > 0 else decorator
