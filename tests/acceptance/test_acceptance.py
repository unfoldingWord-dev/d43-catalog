import os
from unittest import TestCase
from tools.file_utils import load_json_object
from functions.acceptance.acceptance_test import AcceptanceTest
import json

class TestAcceptance(TestCase):
    resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

    class MockSESHandler(object):
        email = None
        def __init__(self):
            TestAcceptance.MockSESHandler.email = None

        def send_email(self, Source, Destination, Message):
            TestAcceptance.MockSESHandler.email = Message

    class MockResponse(object):
        status = None

        def __init__(self, status):
            TestAcceptance.MockResponse.status = status

    class MockHttpConnection(object):
        response = None

        def __init__(self, stuff):
            pass

        def request(self, method, path):
            pass

        def getresponse(self):
            return TestAcceptance.MockHttpConnection.response

    class MockURLHandler(object):
        response = ''

        def get_url(self, url, catch_exception):
            return TestAcceptance.MockURLHandler.response.encode('ascii')

    def _load_catalog(self, name):
        data = load_json_object(os.path.join(TestAcceptance.resources_dir, name))
        return json.dumps(data)

    def test_good_catalog(self):
        self.MockSESHandler.email = None
        self.MockURLHandler.response =  self._load_catalog('good_catalog.json')
        self.MockHttpConnection.response = self.MockResponse(200)
        acceptance = AcceptanceTest('http://example.com', self.MockURLHandler, self.MockHttpConnection, self.MockSESHandler,
                                    to_email='me@example.com',
                                    from_email='me@example.com')
        errors = acceptance.run()

        self.assertEqual(0, len(errors))
        self.assertIn('was generated', self.MockSESHandler.email['Body']['Text']['Data'])

    def test_bad_catalog(self):
        self.MockSESHandler.email = None
        self.MockURLHandler.response =  self._load_catalog('bad_catalog.json')
        self.MockHttpConnection.response = self.MockResponse(200)
        acceptance = AcceptanceTest('http://example.com', self.MockURLHandler, self.MockHttpConnection, self.MockSESHandler,
                                    to_email='me@example.com',
                                    from_email='me@example.com')
        errors = acceptance.run()

        self.assertTrue(len(errors) > 0)
        self.assertIn('Errors in', self.MockSESHandler.email['Body']['Text']['Data'])