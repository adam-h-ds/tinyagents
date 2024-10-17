from typing import Optional, Any, Callable, List, Dict

from tinyagents.nodes import NodeMeta
from tinyagents.callbacks import BaseCallback
from tinyagents.types import NodeOutput

class ConditionalBranch(NodeMeta):
    """ A node which represents a branch in the graph """
    name: str
    branches: Dict[str, NodeMeta]
    router: Optional[Callable[[Any], str]] = None

    def __init__(self, *args: NodeMeta, router: Optional[Callable[[Any], str]] = None, branches: Optional[Dict[str, NodeMeta]] = None, name: Optional[str] = None):
        self.branches = branches if branches else {node.name: node for node in args}
        self.set_name(name if name else f"conditional_branch_{'-'.join(self.branches.keys())}")
        self.router = router

    def __repr__(self) -> str:
        branches_str = ", ".join(str(node) for node in self.branches.values())
        return f"ConditionalBranch({branches_str})"
    
    def __truediv__(self, other_node: NodeMeta) -> "ConditionalBranch":
        self.branches[other_node.name] = other_node
        return self
    
    def bind_router(self, router: Callable[[Any], str]) -> "ConditionalBranch":
        self.router = router
        return self
    
    def invoke(self, inputs: Any, callbacks: Optional[List[BaseCallback]] = None, **kwargs) -> NodeOutput:
        run_id = kwargs.get("run_id")
        if callbacks: [callback.node_start(inputs=inputs, node_name=self.name, run_id=run_id) for callback in callbacks]
        route = self._get_route(inputs)
        node = self._get_node(route)
        output = node.invoke(inputs=inputs, callbacks=callbacks, **kwargs)
        if callbacks: [callback.node_finish(outputs=output, node_name=self.name, run_id=run_id) for callback in callbacks]
        return output
    
    async def ainvoke(self, inputs: Any, callbacks: Optional[List[BaseCallback]] = None, **kwargs) -> NodeOutput:
        print(inputs)
        run_id = kwargs.get("run_id")
        if callbacks: [callback.node_start(inputs=inputs, node_name=self.name, run_id=run_id) for callback in callbacks]
        route = self._get_route(inputs)
        node = self._get_node(route)

        if hasattr(node.ainvoke, "remote"):
            output = await node.ainvoke.remote(inputs=inputs, callbacks=callbacks, **kwargs)
        else:
            output = await node.ainvoke(inputs=inputs, callbacks=callbacks, **kwargs)

        if callbacks: [callback.node_finish(outputs=output, node_name=self.name, run_id=run_id) for callback in callbacks]

        return output
    
    def _get_route(self, inputs: Any) -> str:
        """ If a router is provided, use it to determine the appropriate route. Otherwise assume the given inputs are the route to take """
        return self.router(inputs) if self.router else inputs

    def _get_node(self, route: str) -> NodeMeta:
        if route not in self.branches:
            raise KeyError(f"The router gave route `{route}` but this is not one of the available routes `{list(self.branches.keys())}`.")
        return self.branches[route]