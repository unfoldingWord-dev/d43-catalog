from unittest import TestCase
from mock import patch, MagicMock
from libraries.tools.mocks import MockLogger
from libraries.lambda_handlers.trigger_handler import TriggerHandler

@patch('libraries.lambda_handlers.handler.ErrorReporter')
@patch('libraries.lambda_handlers.trigger_handler.grequests')
class TestTrigger(TestCase):

    @staticmethod
    def mock_request_map_errors(requests, exception_handler=None):
        for r in requests:
            if exception_handler:
                exception_handler(r, Exception('An error'))

    class MockRequest(object):
        def __init__(self, method, url, callback=None):
            self.method = method
            self.url = url
            self.callback = callback

    def make_event(self):
        return {
            "api_url": "https://dev-api.door43.org",
            "api_version": "3",
            "stage": "dev"
        }

    def test_trigger(self, mock_grequests, mock_reporter):
        handler = TriggerHandler(self.make_event(), None)
        handler.logger = MagicMock()
        handler.run()
        handler.logger.info.assert_called()
        handler.logger.error.assert_not_called()

    def test_trigger_errors(self, mock_grequests, mock_reporter):
        mock_grequests.request = lambda method, url, callback=None: self.MockRequest(method, url, callback)
        mock_grequests.map = self.mock_request_map_errors

        handler = TriggerHandler(self.make_event(), None)
        handler.logger = MagicMock()
        handler.run()
        handler.logger.info.assert_called()
        handler.logger.error.assert_called()