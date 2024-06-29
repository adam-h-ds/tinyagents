from typing import Union, List

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
    if not isinstance(outputs, list):
        outputs = [outputs]

    for output in outputs:
        if output.action in ["respond", "end_loop"]:
            return output.content

    return None