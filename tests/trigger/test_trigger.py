import unittest
from unittest import TestCase

from tools.mocks import MockLogger

from libraries.lambda_handlers.trigger_handler import TriggerHandler
from libraries.tools.test_utils import is_travis


class TestTrigger(TestCase):

    @unittest.skipIf(is_travis(), 'Skipping test_trigger on Travis CI')
    def test_trigger(self):
        mockLogger = MockLogger()

        event = {
            "api_url": "https://dev-api.door43.org/v3/lambda"
        }

        TriggerHandler().handle(event,
                                None,
                                logger=mockLogger)