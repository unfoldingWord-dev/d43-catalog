from unittest import TestCase
from libraries.lambda_handlers.handler import Handler
from mock import MagicMock, Mock, patch

import mock

class MockHandler(Handler):
    """
    This is just a light wrapper so we can test our abstract Handler class
    """
    def _run(self, **kwargs):
        pass

class TestHandler(TestCase):

    @patch('libraries.lambda_handlers.handler.ErrorReporter.add_error')
    def test_report_error(self, mock_add_error):
        mock_add_error.return_value=None
        event = {
            'stage': 'dev'
        }
        context = Mock()
        context.function_name = 'test_lambda'
        context.aws_request_id = 'request-id'
        handler = MockHandler(event, context)

        handler.report_error('first error')
        mock_add_error.assert_called_once_with('first error')

    @patch('libraries.lambda_handlers.handler.ErrorReporter.add_error')
    @patch('libraries.lambda_handlers.handler.ErrorReporter.commit')
    def test_commit_errors(self, mock_commit, mock_add_error):
        event = {
            'stage': 'dev'
        }
        context = Mock()
        context.function_name = 'test_lambda'
        context.aws_request_id = 'request-id'
        handler = MockHandler(event, context)
        handler.report_error('first error')
        handler.run()
        mock_add_error.assert_called_once_with('first error')
        mock_commit.assert_called_once()