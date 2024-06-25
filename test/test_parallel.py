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

class TestParallelNode(unittest.TestCase):

    def test_construction(self):
        node = Action1() & Action2()
        self.assertIs(isinstance(node, nodes.Parralel), True)

    def test_node_execution(self):
        node = Action1() & Action2()

        self.assertEqual(
            [Action1().execute("."), Action2().execute(".")],
            node.execute(".")
        )
