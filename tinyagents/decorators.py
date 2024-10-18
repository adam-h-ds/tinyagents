from typing import Callable, Dict, Any, Union, Type, Optional, Literal, TYPE_CHECKING
from inspect import isclass

if TYPE_CHECKING:
    from opentelemetry.trace import Tracer

from tinyagents.nodes import NodeMeta

class Function:
    name: str
    run: Callable

def chainable(
        *args: Union[Type, Callable],
        node_name: Optional[str] = None,
        kind: Optional[Literal["tool", "llm", "retriever", "agent", "other"]] = "other",
        ray_options: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
    if ray_options is None:
        ray_options = {}
    if metadata is None:
        metadata = {}

    if kind not in ["tool", "llm", "retriever", "agent", "other"]:
        raise ValueError(f"`{kind}` is not a valid node type, must be one of ['tool', 'llm', 'retriever', 'agent', 'other']")

    def decorator(cls: Union[Type, Callable]) -> Type:
        func_cls = Function if not isclass(cls) else cls
        if not isclass(cls):
            func_cls.run = staticmethod(cls)

        class ChainableNode(func_cls, NodeMeta):
            name: str = node_name if node_name else getattr(cls, 'name', cls.__name__)
            _kind: str = kind
            _metadata: Dict[str, Any] = metadata
            _ray_options: Dict[str, Any] = ray_options
            _tracer: Union["Tracer", None] = None

            def __repr__(self) -> str:
                return self.name

        return ChainableNode if isclass(cls) else ChainableNode()

    return decorator(args[0]) if args else decorator
