import os
from unittest import TestCase
from tools.file_utils import load_json_object
from functions.acceptance import AcceptanceTest
import json

# This is here to test importing main
from functions.acceptance import main

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

    def test_complex_good_catalog(self):
        self.MockSESHandler.email = None
        self.MockURLHandler.response =  self._load_catalog('complex_good_catalog.json')
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

    def test_missing_catalog(self):
        self.MockSESHandler.email = None
        self.MockURLHandler.response = ''
        self.MockHttpConnection.response = self.MockResponse(200)
        acceptance = AcceptanceTest('http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler,
                                    to_email='me@example.com',
                                    from_email='me@example.com')
        success = acceptance.test_catalog_structure()
        self.assertFalse(success)
        self.assertIn('http://example.com does not exist', acceptance.errors)

    def test_invalid_catalog_json(self):
        self.MockSESHandler.email = None
        self.MockURLHandler.response = '{'
        self.MockHttpConnection.response = self.MockResponse(200)
        acceptance = AcceptanceTest('http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler,
                                    to_email='me@example.com',
                                    from_email='me@example.com')
        result = acceptance.test_catalog_structure()
        self.assertFalse(result)
        self.assertIn('Expecting object: line 1 column 1 (char 0)', acceptance.errors)

    def test_missing_languages(self):
        self.MockURLHandler.response = '{"catalogs":[]}'
        self.MockHttpConnection.response = self.MockResponse(200)
        acceptance = AcceptanceTest('http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler)
        result = acceptance.test_catalog_structure()
        self.assertFalse(result)
        self.assertIn("http://example.com doesn't have 'languages'", acceptance.errors)

    def test_empty_languages(self):
        acceptance = AcceptanceTest('http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler)
        result = acceptance._test_languages([])
        self.assertFalse(result)
        self.assertIn("There needs to be at least one language in the catalog", acceptance.errors)

    def test_languages_not_array(self):
        acceptance = AcceptanceTest('http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler)
        result = acceptance._test_languages(9)
        self.assertFalse(result)
        self.assertIn("'languages' is not an array", acceptance.errors)

    def test_language_not_dict(self):
        acceptance = AcceptanceTest('http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler)
        result = acceptance._test_languages([{}, []])
        self.assertFalse(result)
        self.assertIn("languages: Found a language container that doesn't have 'identifier'", acceptance.errors)
        self.assertIn("languages: Found a language container that is not an associative array", acceptance.errors)

    def test_language_missing_keys(self):
        acceptance = AcceptanceTest('http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler)
        result = acceptance._test_languages([{"identifier":"en"}])
        self.assertFalse(result)
        self.assertIn("en: 'title' does not exist", acceptance.errors)
        self.assertIn("en: 'direction' does not exist", acceptance.errors)

    def test_resources_not_array(self):
        acceptance = AcceptanceTest('http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler)
        result = acceptance._test_resources("en", 9)
        self.assertFalse(result)
        self.assertIn("en: 'resources' is not an array", acceptance.errors)

    def test_resource_not_dict(self):
        acceptance = AcceptanceTest('http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler)
        result = acceptance._test_resources("en", [{}, 9])
        self.assertFalse(result)
        self.assertIn("en resources: A resource container exists without an 'identifier'", acceptance.errors)
        self.assertIn("en: Found a resource container that is not an associative array", acceptance.errors)

    def test_resource_missing_keys(self):
        acceptance = AcceptanceTest('http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler)

        result = acceptance._test_resources("en", [{"identifier":"id"}])
        self.assertFalse(result)
        self.assertIn("en_id: 'title' does not exist", acceptance.errors)
        self.assertIn("en_id: 'source' does not exist", acceptance.errors)
        self.assertIn("en_id: 'rights' does not exist", acceptance.errors)
        self.assertIn("en_id: 'creator' does not exist", acceptance.errors)
        self.assertIn("en_id: 'contributor' does not exist", acceptance.errors)
        self.assertIn("en_id: 'relation' does not exist", acceptance.errors)
        self.assertIn("en_id: 'publisher' does not exist", acceptance.errors)
        self.assertIn("en_id: 'issued' does not exist", acceptance.errors)
        self.assertIn("en_id: 'modified' does not exist", acceptance.errors)
        self.assertIn("en_id: 'version' does not exist", acceptance.errors)
        self.assertIn("en_id: 'checking' does not exist", acceptance.errors)
        self.assertIn("en_id: 'projects' does not exist", acceptance.errors)

    def test_projects_not_array(self):
        acceptance = AcceptanceTest('http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler)

        result = acceptance._test_projects("en", "id", {"projects": 9})
        self.assertFalse(result)
        self.assertIn("en_id: 'projects' is not an array", acceptance.errors)

    def test_formats_missing_in_multi_project_resource(self):
        acceptance = AcceptanceTest('http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler)

        result = acceptance._test_projects("en", "id", {"projects": [{},{}]})
        self.assertFalse(result)
        self.assertIn("en_id: 'formats' does not exist in multi-project resource", acceptance.errors)

    def test_formats_in_single_project_resource(self):
        acceptance = AcceptanceTest('http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler)

        result = acceptance._test_projects("en", "id", {"projects": [{}], "formats":[]})
        self.assertFalse(result)
        self.assertIn("en_id: 'formats' found in single-project resource", acceptance.errors)

    def test_formats_not_array(self):
        acceptance = AcceptanceTest('http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler)

        result = acceptance._test_formats("en", "id", 6)
        self.assertFalse(result)
        self.assertIn("en_id: 'formats' is not an array", acceptance.errors)

    def test_format_missing_key(self):
        acceptance = AcceptanceTest('http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler)

        result = acceptance._test_formats("en", "id", [{}])
        self.assertFalse(result)
        self.assertIn("Format container for 'en_id' doesn't have 'format'", acceptance.errors)
        self.assertIn("Format container for 'en_id' doesn't have 'modified'", acceptance.errors)
        self.assertIn("Format container for 'en_id' doesn't have 'size'", acceptance.errors)
        self.assertIn("Format container for 'en_id' doesn't have 'url'", acceptance.errors)
        self.assertIn("Format container for 'en_id' doesn't have 'signature'", acceptance.errors)