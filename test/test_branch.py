import unittest

from tinyagents import chainable
import tinyagents.nodes as nodes

@chainable
class Action1:
    def run(self, x):
        return "action_1_output"

@chainable
class Action2:
    def run(self, x):
        return "action_2_output"

class TestBranchNode(unittest.TestCase):

    def test_construction(self):
        node = Action1() / Action2()
        self.assertIs(isinstance(node, nodes.ConditionalBranch), True)

    def test_router(self):
        node = Action1() / Action2()

        def router(x: str) -> str:
            if x == "trigger_action_1":
                return "Action1"
            
            return "Action2"
        
        node.bind_router(router)

        self.assertEqual(node.execute("trigger_action_1").content, "action_1_output")
        self.assertEqual(node.execute("trigger_action_2").content, "action_2_output")
