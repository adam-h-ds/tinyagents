from typing import Optional, Dict
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from tinyagents.types import NodeOutput
from tinyagents.callbacks import BaseCallback
from tinyagents.nodes.node_meta import NodeMeta

class Parallel(NodeMeta):
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
    
    def __and__(self, other_node) -> "Parallel":
        self.nodes[other_node.name] = other_node
        return self
    
    def invoke(self, x, callback: Optional[BaseCallback] = None, **kwargs) -> Dict[str, NodeOutput]:
        run_id = kwargs.get("run_id")
        refs = {}
        outputs = {}
        with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            for name, node in self.nodes.items():
                if callback: callback.node_start(inputs=x, node_name=name, run_id=run_id)
                refs[name] = executor.submit(partial(node.invoke, x=x, **kwargs))

            for node_name in refs:
                output = refs[node_name].result()
                if callback: callback.node_finish(outputs=output, node_name=node_name, run_id=run_id)
                outputs[node_name] = output

        return outputs
    
    async def ainvoke(self, x, callback: Optional[BaseCallback] = None, **kwargs) -> Dict[str, NodeOutput]:
        run_id = kwargs.get("run_id")
        refs = {}
        outputs = {}
        for name, node in self.nodes.items():
            if callback: callback.node_start(inputs=x, node_name=name, run_id=run_id)

            if hasattr(node, "remote"):
                refs[name] = node.invoke.remote(x=x, callback=callback, **kwargs)
            else:
                refs[name] = node.ainvoke(x=x, callback=callback, **kwargs)

        for node_name in refs:
            output = await refs[node_name]
            if callback: callback.node_finish(outputs=output, node_name=node_name, run_id=run_id)
            outputs[node_name] = output

        return outputs
    
    def set_max_workers(self, max_workers: int) -> None:
        self.max_workers = max_workers