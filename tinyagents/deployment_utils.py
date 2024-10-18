import inspect
from ray import serve
import tinyagents.nodes as nodes

def nodes_to_deployments(graph_nodes: list) -> list[serve.Deployment]:
    deployments = [convert_node_to_deployment(node) for node in graph_nodes]
    return deployments

def convert_node_to_deployment(node) -> serve.Deployment:
    if isinstance(node, nodes.Parallel):
        return parralel_node_to_deployment(node)
    elif isinstance(node, nodes.ConditionalBranch):
        return conditional_node_to_deployment(node)
    elif isinstance(node, nodes.Recursive):
        return recursive_node_to_deployment(node)
    else:
        return node_to_deployment(node)

def parralel_node_to_deployment(node) -> serve.Deployment:
    node.nodes = {name: node_to_deployment(node_) for name, node_ in node.nodes.items()}
    return node

def conditional_node_to_deployment(node) -> serve.Deployment:
    node.branches = {name: node_to_deployment(node_) for name, node_ in node.branches.items()}
    return node

def recursive_node_to_deployment(node) -> serve.Deployment:
    node.node1 = node_to_deployment(node.node1)
    node.node2 = node_to_deployment(node.node2)
    return node

def node_to_deployment(node):
    options = node._ray_options
    argnames = [arg for arg in inspect.signature(node.__init__).parameters if arg not in {"args", "kwargs", "self"}]
    try:
        args = {anno: getattr(node, anno) for anno in argnames}
    except AttributeError:
        raise Exception(f"In order to compile the graph using Ray, arguments that are passed to the constructor must be stored as attributes of the class `{node.name}`.")
    return serve.deployment(node.__class__, name=node.name).options(**options).bind(**args)