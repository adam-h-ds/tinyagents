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
        self.assertIs(isinstance(node, nodes.Parallel), True)

    def test_node_execution(self):
        action1 = Action1()
        action2 = Action2()

        node = action1 & action2
        print(node.invoke("."))
        self.assertEqual(
            {
                action1.name: action1.invoke("."),
                action2.name: action2.invoke(".")
            },
            node.invoke(".")
        )
