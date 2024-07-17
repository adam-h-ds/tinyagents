from typing import Any, Optional

from tinyagents.types import NodeOutput, Action
import tinyagents.nodes as nodes

def respond(response: str) -> NodeOutput:
    return NodeOutput(
        content=response,
        action=Action.Respond
    )

def passthrough(outputs: Any) -> NodeOutput:
    return NodeOutput(
        content=outputs
    )

def end_loop(outputs: Any):
    return NodeOutput(
        content=outputs,
        action=Action.EndLoop
    )

def loop(node1, node2, max_iter: int = 3, name: Optional[str] = None):
    return nodes.Recursive(node1, node2, max_iter, name)