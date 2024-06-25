import unittest

from tinyagents import chainable
import tinyagents.nodes as nodes
from tinyagents.graph import Graph

@chainable
class Action1:
    def run(self, x):
        return "action_1_output"

@chainable
class Action2:
    def run(self, x):
        return "action_2_output"
    
@chainable
class Action3:
    def run(self, x):
        return "action_3_output"

class TestGraph(unittest.TestCase):

    def test_construction(self):
        node1 = Action1() & Action2()
        node2 = Action3()

        graph1 = node1 | node2
        graph2 = node1 & node2

        self.assertIs(
            isinstance(graph1, Graph), 
            True
        )
        self.assertIs(
            isinstance(graph2, Graph), 
            False
        )

    def test_static_order(self):
        node1 = Action1() & Action2()
        node2 = Action3()

        graph = node1 | node2

        self.assertEqual(
            graph.get_order(),
            [node1, node2]
        )
