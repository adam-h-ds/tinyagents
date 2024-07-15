from typing import Union, List
from uuid import uuid4

import ray

from tinyagents.types import NodeOutput

COLOUR_MAP = {
    "blue": "36;1",
    "yellow": "33;1",
    "pink": "38;5;200",
    "green": "32;1",
    "red": "31;1",
}

def create_colored_text(text: str, colour: str) -> str:
    colour_code = COLOUR_MAP[colour]
    return f"\u001b[{colour_code}m\033[1;3m{text}\u001b[0m"

def check_for_break(outputs: Union[NodeOutput, List[NodeOutput]]):
    if isinstance(outputs, dict):
        outputs = list(outputs.values())

    if not isinstance(outputs, list):
        outputs = [outputs]

    for output in outputs:
        if output.action in ["respond", "end_loop"]:
            return True

    return False

def get_content(x):
    """ Extract the content from the inputs """
    if isinstance(x, list):
        return [output.content if isinstance(output, NodeOutput) else output for output in x]
            
    elif isinstance(x, dict):
        for key in x:
            if isinstance(x[key], NodeOutput):
                x[key] = x[key].content
        
    elif isinstance(x, NodeOutput):
        return x.content
    
    return x

def create_run_id():
    return str(uuid4())