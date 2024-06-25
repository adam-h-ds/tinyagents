from abc import abstractmethod, ABC
from typing import Any, Union
import json

from tinyagents.utils import create_colored_text
from tinyagents.types import NodeOutput

class BaseCallback(ABC):
    """ A base class for callbacks """

    def flow_start(self, ref: str, inputs: Any):
        # runs when a graph is executed
        pass

    def flow_end(self, ref: str, outputs: Any):
        # runs when a graph execution has finished
        pass
    
    def node_start(self, ref: str, inputs: Any):
        # runs when a node has started
        pass

    def node_finish(self, ref: str, outputs: Any):
        # runs when a node has finished
        pass

class StdoutCallback(BaseCallback):
    """ Print the inputs and outputs of nodes """
    def node_start(self, ref: str, inputs: Any):
        print(create_colored_text(f"\n > Running node: {ref}\n", "blue"))
        print(create_colored_text(f"\tInput: {inputs}\n", "yellow"))

    def node_finish(self, ref: str, outputs: Any):
        print(create_colored_text(f"\tOutput: {json.dumps(outputs.to_dict() if isinstance(outputs, NodeOutput) else [output.to_dict() for output in outputs], indent=2)}", "green"))