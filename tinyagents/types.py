from enum import Enum
from dataclasses import dataclass
from typing import Any, Optional

class Action(Enum):
    Respond = "respond"
    EndLoop = "end_loop"

@dataclass
class NodeOutput:
    content: Any
    action: Optional[Action] = None
    ref: Optional[str] = None

    def to_dict(self):
        dict_ = self.__dict__
        if isinstance(self.action, Action):
            dict_["action"] = self.action.value

        return dict_
