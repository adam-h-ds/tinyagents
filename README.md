# TinyAgents 
<img src="docs/assets/logo.png" alt="drawing" width="100"/>

[![LICENSE](https://img.shields.io/github/license/adam-h-ds/tinyagents?label=license&style=for-the-badge)](https://github.com/adam-h-ds/tinyagents/blob/main/LICENSE)
[![BUILD](https://img.shields.io/github/actions/workflow/status/adam-h-ds/tinyagents/publish.yml?style=for-the-badge)](https://github.com/adam-h-ds/tinyagents/blob/main/.github/workflows/publish.yml)
[![VERSION](https://img.shields.io/pypi/v/tinyagents?style=for-the-badge&label=PYPI+VERSION)](https://github.com/adam-h-ds/tinyagents)

A tiny, lightweight and unintrusive library for orchestrating agentic applications. 

**Here's the big idea:**

1. 😶‍🌫️ **Less than 500 lines of code.** *"I have absolutely no idea what this library is doing under the hood"*
2. 😨 **Avoid including the entirety of PyPi in the requirements.txt**
3. 🚀 **Minimise the need for code changes.** *"The library is no longer being maintained - so let's retire our application with it."*

*Upcoming:*
1. Support for deployment and execution using Ray.
    - easily deploy and scale nodes in your graph as Ray Serve deployments.
2. A set of callbacks for storing traces to Redis, Pub/Sub or disk.
3. A tool for visualising what is happening within your graphs

## Installation

```bash
pip install tinyagents
```

## How it works!

### Define your graph using standard operators

#### Parallelisation
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
```python
jailbreak_check = ...
agent1 = ...
agent2 = ...
guardrail = ...

def my_router(inputs: str):
    if inputs == "jailbreak_attempt":
        return agent2.name

    return agent1.name

# check for jailbreaks, then run either `agent1` or `agent2`, then finally run `guardrail`
graph = jailbreak_check | (agent1 / agent2).bind_router(my_router) | guardrail

print(graph)

## jailbreak_check -> ConditionalBranch(agent1, agent2) -> guardrail
```

#### Looping
```python
from tinyagents import loop

agent1 = ...
agent2 = ...
agent3 = ...
guardrail = ...

# run at most 3 iterations between `agent1` and `agent2`, then pass to `agent3` and finally `guardrail`.
graph = loop(agent1, agent2, max_iter=3) | agent3 | guardrail

print(graph)

## Recursive(agent1, agent2) -> agent3 -> guardrail
```