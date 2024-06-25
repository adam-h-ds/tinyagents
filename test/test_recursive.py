import unittest

from tinyagents import chainable, loop, respond, passthrough
import tinyagents.nodes as nodes

@chainable
class Action1:
    def run(self, x):
        return x + 1

@chainable
class Action2:
    def run(self, x):
        return x
    
    def output_handler(self, x):
        if x == 3:
            return respond(x)
        
        return passthrough(x)

class TestResursiveNode(unittest.TestCase):

    def test_construction(self):
        self.assertIs(isinstance(loop(Action1(), Action2()), nodes.Recursive), True)

    def test_max_iterations(self):
        node = loop(Action1(), Action2(), max_iter=3)
        self.assertEqual(node.execute(0).content, 4)