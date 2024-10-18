import unittest
from unittest.mock import patch, MagicMock

from opentelemetry.trace import Tracer

from tinyagents import chainable
from tinyagents.tracing import init_all_tracers
from tinyagents.nodes import NodeMeta

class TestTracing(unittest.TestCase):
    @patch('tinyagents.tracing.utils._init_node_tracer')
    def test_init_all_tracers(self, mock_init_node_tracer):
        node1 = MagicMock(spec=NodeMeta)
        node2 = MagicMock(spec=NodeMeta)
        nodes = [node1, node2]

        init_all_tracers(nodes)

        mock_init_node_tracer.assert_any_call(node1)
        mock_init_node_tracer.assert_any_call(node2)

    @patch('tinyagents.tracing.utils.create_tracer')
    def test_node_invoke_tracing(self, mock_create_tracer):
        mock_create_tracer.return_value = MagicMock(spec=Tracer)

        @chainable
        def single_node(x):
            return "output"
        
        graph = single_node.as_graph()
        graph._state[0]._tracer = mock_create_tracer.return_value
        runner = graph.compile()

        output = runner.invoke("input")
        self.assertEqual(output, "output")
        # ensure that the tracer started a new span
        graph._state[0]._tracer.start_as_current_span.assert_called_once()

if __name__ == '__main__':
    unittest.main()