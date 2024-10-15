from typing import Optional, Any, Callable

from tinyagents.nodes import NodeMeta
from tinyagents.callbacks import BaseCallback
from tinyagents.types import NodeOutput

class ConditionalBranch(NodeMeta):
    """ A node which represents a branch in the graph """
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
        branches_str = ", ".join([str(node) for node in self.branches.values()])
        return f"ConditionalBranch({branches_str})"
    
    def __truediv__(self, other_node):
        self.branches[other_node.name] = other_node
        return self
    
    def bind_router(self, router: Callable) -> "ConditionalBranch":
        self.router = router
        return self
    
    def invoke(self, x: Any, callback: Optional[BaseCallback] = None, **kwargs) -> NodeOutput:
        run_id = kwargs.get("run_id")
        if callback: callback.node_start(inputs=x, node_name=self.name, run_id=run_id)
        route = self._get_route(x)
        node = self._get_node(route)
        output = node.invoke(x=x, callback=callback, **kwargs)
        if callback: callback.node_finish(outputs=output, node_name=self.name, run_id=run_id)
        return output
    
    async def ainvoke(self, x: Any, callback: Optional[BaseCallback] = None, **kwargs):
        run_id = kwargs.get("run_id")
        if callback: callback.node_start(inputs=x, node_name=self.name, run_id=run_id)
        route = self._get_route(x)
        node = self._get_node(route)

        if hasattr(node.invoke, "remote"):
            output = await node.invoke.remote(x=x, callback=callback, **kwargs)
        else:
            output = node.invoke(x=x, callback=callback, **kwargs)

        if callback: callback.node_finish(outputs=output, node_name=self.name, run_id=run_id)

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
    