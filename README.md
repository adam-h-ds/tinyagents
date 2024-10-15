# TinyAgents 
<img src="docs/assets/logo.png" alt="drawing" width="100"/>

[![LICENSE](https://img.shields.io/github/license/adam-h-ds/tinyagents?label=license&style=for-the-badge)](https://github.com/adam-h-ds/tinyagents/blob/main/LICENSE)
[![BUILD](https://img.shields.io/github/actions/workflow/status/adam-h-ds/tinyagents/publish.yml?style=for-the-badge)](https://github.com/adam-h-ds/tinyagents/blob/main/.github/workflows/publish.yml)
[![VERSION](https://img.shields.io/pypi/v/tinyagents?style=for-the-badge&label=PYPI+VERSION)](https://github.com/adam-h-ds/tinyagents)

A tiny, lightweight and unintrusive library for orchestrating agentic applications. 

**Here's the big idea:**

1. 😶‍🌫️ **Less than 1000 lines of code.**
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
from typing import TypedDict

class State(TypedDict):
    approved: bool
    findings: List[str]

@chainable
class Supervisor:
    def __init__(self):
        ...

    def run(self, state: dict) ->:
        # get findings from the state and determine if the research is sufficient
        if len(state.findings) > 3:
            state.approved = True

        return state

    def output_handler(self, state: dict):
        # override the default output handler which returns `passthrough(..)` 
        # to move to the next node in the graph.
        if state.approved == True:
            return end_loop(...final output...)
        
        return passthrough(state)

@chainable
class Researcher:
    def __init__(self):
        ...

    def __run__(self, state: State) -> State:
        # do research and add findings to the state
        state.findings.append("...new finding...")
        return state

graph = loop(Researcher(), Supervisor(), max_iter=8).as_graph()

print(graph)
## Recursive(researcher, supervisor)
```

#### Subgraphs

You can use `Graph` objects as if they were nodes, which creates `SubGraph` nodes.

```python
from tinyagents import chainable, loop
from pydantic import BaseModel

class State(BaseModel):
    messages: List[Dict[str, str]]

@chainable
def tool1(inputs: str):
    return ...

@chainable
def tool2(inputs: str):
    return ...

@chainable
def tool3(inputs: str):
    return ...

@chainable
def tool4(inputs: str):
    return ...

@chainable
class Agent:
    def __init__(self):
        ...

    def run(self, inputs: State):
        # use tools and generate a response
        return ...

# parallelise all toolkits
toolkit1 = tool1 & tool2
toolkit2 = tool3 & tool4
agent = Agent()

# define Graph 1
graph1 = loop(toolkit1, agent, max_iter=2).as_graph()
# define Graph 2
graph2 = toolkit2 | agent

graph1_runner = graph1.compile()
graph2_runner = graph2.compile()

state = State(messages=[{"role": "user", "content": "Hello!"}])

# invoke Graph 1 
result1 = graph1.invoke(state)
# invoke Graph 2
result2 = graph2.invoke(state)

# invoke a combined and parallelised graph
combined_graph_runner = (graph1 & graph2).compile()
combined_result = combined_graph_runner.invoke(state)
print(combined_result)
# [result1, result2]
```
