import inspect

from ray import serve

import tinyagents.nodes as nodes

def nodes_to_deployments(graph_nodes: list, ray_options: dict = {}) -> list[serve.Deployment]:
    deployments = []
    for node in graph_nodes:
        if isinstance(node, nodes.Parralel):
            ray_node = parralel_node_to_deployment(node, ray_options)

        elif isinstance(node, nodes.ConditionalBranch):
            ray_node = conditional_node_to_deployment(node, ray_options)

        elif isinstance(node, nodes.Recursive):
            ray_node = recursive_node_to_deployment(node, ray_options)

        else:
            ray_node = node_to_deployment(node, ray_options)
        
        deployments.append(ray_node)

    return deployments
    
def parralel_node_to_deployment(node, ray_options: dict = {}) -> serve.Deployment:
    node.nodes = {name: node_to_deployment(node_, ray_options) for name, node_ in node.nodes.items()}
    return node

def conditional_node_to_deployment(node, ray_options: dict = {}) -> serve.Deployment:
    node.branches = {name: node_to_deployment(node_, ray_options) for name, node_ in node.branches.items()}
    return node

def recursive_node_to_deployment(node, ray_options: dict = {}) -> serve.Deployment:
    node.node1 = node_to_deployment(node.node1, ray_options)
    node.node2 = node_to_deployment(node.node2, ray_options)
    return node

def node_to_deployment(node, ray_options: dict = {}):
    options = ray_options.get(node.name, {})
    argnames = [arg for arg in list(inspect.signature(node.__init__).parameters.keys()) if arg not in ["args", "kwargs", "self"]]
    try:
        args = {anno: getattr(node, anno) for anno in argnames}
    except AttributeError:
        raise Exception(f"In order to compile the graph using Ray, arguments that are passed to the constructor must be stored as attributes of the class `{node.name}`.")
    
    return serve.deployment(node.__class__, name=node.name).options(**options).bind(**args)