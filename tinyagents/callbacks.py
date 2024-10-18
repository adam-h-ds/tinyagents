from abc import ABC
from typing import Any
import json
from inspect import iscoroutine
from ray.serve.handle import DeploymentResponse

from tinyagents.utils import create_colored_text
from tinyagents.types import NodeOutput

class BaseCallback(ABC):
    """ A base class for callbacks """

    def flow_start(self, inputs: Any, run_id: str):
        # runs when a graph is executed
        pass

    def flow_end(self, outputs: Any, run_id: str):
        # runs when a graph execution has finished
        pass
    
    def node_start(self, inputs: Any, node_name: str, run_id: str):
        # runs when a node has started
        pass

    def node_finish(self, outputs: Any, node_name: str, run_id: str):
        # runs when a node has finished
        pass

class StdoutCallback(BaseCallback):
    """ Print the inputs and outputs of nodes """
    def node_start(self, inputs: Any, node_name: str, run_id: str):
        print(create_colored_text(f"\n > Running node: {node_name}\n", "blue"))
        print(create_colored_text(f"\tInput: {inputs}\n", "yellow"))

    def node_finish(self, outputs: Any, node_name: str, run_id: str):
        print(create_colored_text(f"\tOutput ({node_name}): {self.output_to_str(outputs)}", "green"))

    @staticmethod
    def output_to_str(outputs) -> str:
        if iscoroutine(outputs) or isinstance(outputs, DeploymentResponse):
            return "[Future]"
        
        if isinstance(outputs, NodeOutput):
            outputs = outputs.to_dict()
        elif isinstance(outputs, list):
            outputs = [output.to_dict() for output in outputs]

        return json.dumps(outputs, indent=2)
        

