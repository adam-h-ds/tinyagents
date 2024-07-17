# TinyAgents 
<img src="docs/assets/logo.png" alt="drawing" width="100"/>

[![LICENSE](https://img.shields.io/github/license/adam-h-ds/tinyagents?label=license&style=for-the-badge)](https://github.com/adam-h-ds/tinyagents/blob/main/LICENSE)
[![BUILD](https://img.shields.io/github/actions/workflow/status/adam-h-ds/tinyagents/publish.yml?style=for-the-badge)](https://github.com/adam-h-ds/tinyagents/blob/main/.github/workflows/publish.yml)
[![VERSION](https://img.shields.io/pypi/v/tinyagents?style=for-the-badge&label=PYPI+VERSION)](https://github.com/adam-h-ds/tinyagents)

A tiny, lightweight and unintrusive library for orchestrating agentic applications. 

**Here's the big idea:**

1. 😶‍🌫️ **Less than 600 lines of code.**
2. 😨 **Lightweight - "Ray Is All You Need"**
3. 🚀 **No need to change your code, just decorate!** 

**Recent updates**:
1. (17/07) As of version 1.1, you can now run and deploy TinyAgents graphs using **Ray Serve** 🎉 see this [notebook](examples/deploy_with_ray.ipynb) for an example. More information can also be found here [Run and deploy using Ray Serve](docs/using_ray.md).

## Installation

```bash
pip install tinyagents
```

## How it works!

### Define your graph using standard operators

#### Parallelisation

Use the `&` operator to create a `Parallel` node.

> Note: when using Ray you can configure resource allocation by passing `ray_options` when compiling your graph (more information provided [here](docs/assets/using_ray.md)). When you are not using Ray, you can set the maximum number of workers used by the `ThreadPoolExecutor` by using the `node.set_max_workers()` method.

```python
from tinyagents import chainable

@chainable
def tool1(inputs: dict):
    return ...

@chaianble
def tool2(inputs: dict):
    return ...

@chainable
class Agent:
    def __init__(self):
        ...

    def run(self, inputs: list):
        return ...

# run `tool1` and `tool2` in parallel, then pass outputs to `Agent`
graph = (tool1 & tool2) | Agent()
runner = graph.compile()

runner.invoke("Hello!")
```

#### Branching

Use `/` operator to create a `ConditionalBranch` node. 

> Note: If a (callable) *router* is bound to the node, it will be used to determine which of the subnodes should be executed (by returning the name of the selected node). If no router is provided, the input to the ConditionalBranch node must be the name of the node to execute.

```python
jailbreak_check = ...
agent1 = ...
agent2 = ...
guardrail = ...

def my_router(inputs: str):
    if inputs == "jailbreak_attempt":
        return agent2.name

    return agent1.name

# check for a jailbreak attempt, then run either `agent1` or `agent2`, then finally run `guardrail`
graph = jailbreak_check | (agent1 / agent2).bind_router(my_router) | guardrail

print(graph)
## jailbreak_check -> ConditionalBranch(agent1, agent2) -> guardrail
```

#### Looping

Use the `loop` function to define a `Recursive` node.

> Note: loops can be exited early by overriding the `output_handler` method for a node and using the `end_loop` function instead of the default `passthrough`.

```python
from tinyagents import chainable, loop, end_loop, passthrough

@chainable
class Supervisor:
    def __init__(self):
        ...

    def run(self, state: dict) ->:
        # get findings from the state and assess
        return state

    def output_handler(self, state: dict):
        if state["last_message"] == "Approved":
            return end_loop(supervisor_output)
        
        return passthrough(supervisor_output)

class Researcher:
    def __init__(self):
        ...

    def __run__(self, state: str) -> str:
        # add findings to the state
        return state

graph = loop(Researcher(), Supervisor(), max_iter=8).as_graph()

print(graph)
## Recursive(researcher, supervisor)
```