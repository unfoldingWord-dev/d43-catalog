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

    @patch('libraries.lambda_handlers.handler.DynamoDBHandler.get_item')
    @patch('libraries.lambda_handlers.handler.DynamoDBHandler.update_item')
    def test_report_error(self, mock_update_item, mock_get_item):
        """

        :param MagicMock mock_db:
        :return:
        """
        mock_get_item.return_value=None
        event = {
            'stage': 'dev'
        }
        context = Mock()
        context.function_name = 'test_lambda'
        context.aws_request_id = 'request-id'
        handler = MockHandler(event, context)

        handler.report_error('first error')
        mock_get_item.assert_called_once_with({'lambda':'test_lambda'})
        mock_update_item.assert_called_once_with({'lambda': 'test_lambda'},
                                                 {'reporters': ['request-id'],
                                                  'errors':[{"timestamp": mock.ANY, "message": "first error"}],
                                                  'lambda': 'test_lambda'
                                                 }
                                                )
