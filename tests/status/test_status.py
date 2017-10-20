from unittest import TestCase
from libraries.lambda_handlers.status_handler import StatusHandler
from libraries.tools.test_utils import assert_object_equals

class TestStatus(TestCase):

    def test_make_catalog_function_status(self):
        handler = StatusHandler(event={}, context=None)
        response = handler.make_function_status('3', {})
        self.assertEqual(response['status'], 'complete')
        self.assertEqual(response['name'], '3')
        self.assertEqual(response['lambda'], 'd43-catalog_catalog')

    def test_make_ts_catalog_function_status(self):
        handler = StatusHandler(event={}, context=None)
        response = handler.make_function_status('ts.2', {})
        self.assertEqual(response['status'], 'complete')
        self.assertEqual(response['name'], 'ts.2')
        self.assertEqual(response['lambda'], 'd43-catalog_ts_v2_catalog')

    def test_make_uw_catalog_function_status(self):
        handler = StatusHandler(event={}, context=None)
        response = handler.make_function_status('uw.2', {})
        self.assertEqual(response['status'], 'complete')
        self.assertEqual(response['name'], 'uw.2')
        self.assertEqual(response['lambda'], 'd43-catalog_uw_v2_catalog')

    def test_make_signing_function_status(self):
        handler = StatusHandler(event={}, context=None)
        response = handler.make_function_status('signing', {})
        self.assertEqual(response['status'], 'complete')
        self.assertEqual(response['name'], 'signing')
        self.assertEqual(response['lambda'], 'd43-catalog_signing')

    def test_make_signing_function_status_with_errors(self):
        handler = StatusHandler(event={}, context=None)
        errors = {
            'd43-catalog_signing': [
                {
                    'message': 'first error',
                    'timestamp': '2017-10-20T18:37:23.059571+00:00'
                },
                {
                    'message': 'second error',
                    'timestamp': '2017-11-20T18:37:23.059571+00:00'
                }
            ]
        }
        response = handler.make_function_status('signing', errors)
        self.assertEqual(response['status'], 'complete')
        self.assertEqual(response['name'], 'signing')
        self.assertEqual(response['lambda'], 'd43-catalog_signing')
        assert_object_equals(self, response['errors'], errors['d43-catalog_signing'])