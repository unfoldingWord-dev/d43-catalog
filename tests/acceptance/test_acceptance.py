import json
import os

from mock import patch
from unittest import TestCase
from libraries.lambda_handlers.acceptance_handler import AcceptanceHandler
from libraries.tools.file_utils import load_json_object


@patch('libraries.lambda_handlers.handler.ErrorReporter')
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
            if TestAcceptance.MockHttpConnection.response is None:
                print('WARNING: did you forget to initialize MockHttpConnection?')
            return TestAcceptance.MockHttpConnection.response

    class MockURLHandler(object):
        response = ''

        def get_url(self, url, catch_exception):
            return TestAcceptance.MockURLHandler.response.encode('ascii')

    def _load_catalog(self, name):
        data = load_json_object(os.path.join(TestAcceptance.resources_dir, name))
        return json.dumps(data)

    def test_good_catalog(self, mock_reporter):
        self.MockSESHandler.email = None
        self.MockURLHandler.response =  self._load_catalog('good_catalog.json')
        self.MockHttpConnection.response = self.MockResponse(200)
        acceptance = AcceptanceHandler(self.make_event(), None,'http://example.com', self.MockURLHandler, self.MockHttpConnection, self.MockSESHandler,
                                    to_email='me@example.com',
                                    from_email='me@example.com')
        errors = acceptance.run()

        self.assertEqual(0, len(errors))
        self.assertIn('was generated', self.MockSESHandler.email['Body']['Text']['Data'])

    def test_complex_good_catalog(self, mock_reporter):
        self.MockSESHandler.email = None
        self.MockURLHandler.response =  self._load_catalog('complex_good_catalog.json')
        self.MockHttpConnection.response = self.MockResponse(200)
        acceptance = AcceptanceHandler(self.make_event(), None,'http://example.com', self.MockURLHandler, self.MockHttpConnection, self.MockSESHandler,
                                    to_email='me@example.com',
                                    from_email='me@example.com')
        errors = acceptance.run()

        self.assertEqual(0, len(errors))
        self.assertIn('was generated', self.MockSESHandler.email['Body']['Text']['Data'])

    def test_bad_catalog(self, mock_reporter):
        self.MockSESHandler.email = None
        self.MockURLHandler.response =  self._load_catalog('bad_catalog.json')
        self.MockHttpConnection.response = self.MockResponse(200)
        acceptance = AcceptanceHandler(self.make_event(), None,'http://example.com', self.MockURLHandler, self.MockHttpConnection, self.MockSESHandler,
                                    to_email='me@example.com',
                                    from_email='me@example.com')
        errors = acceptance.run()

        self.assertTrue(len(errors) > 0)
        self.assertIn('Errors in', self.MockSESHandler.email['Body']['Text']['Data'])

    def test_missing_catalog(self, mock_reporter):
        self.MockSESHandler.email = None
        self.MockURLHandler.response = ''
        self.MockHttpConnection.response = self.MockResponse(200)
        acceptance = AcceptanceHandler(self.make_event(), None,'http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler,
                                    to_email='me@example.com',
                                    from_email='me@example.com')
        success = acceptance.test_catalog_structure()
        self.assertFalse(success)
        self.assertIn('http://example.com does not exist', acceptance.errors)

    def test_invalid_catalog_json(self, mock_reporter):
        self.MockSESHandler.email = None
        self.MockURLHandler.response = '{'
        self.MockHttpConnection.response = self.MockResponse(200)
        acceptance = AcceptanceHandler(self.make_event(), None,'http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler,
                                    to_email='me@example.com',
                                    from_email='me@example.com')
        result = acceptance.test_catalog_structure()
        self.assertFalse(result)
        self.assertIn('Expecting object: line 1 column 1 (char 0)', acceptance.errors)

    def test_missing_languages(self, mock_reporter):
        self.MockURLHandler.response = '{"catalogs":[]}'
        self.MockHttpConnection.response = self.MockResponse(200)
        acceptance = AcceptanceHandler(self.make_event(), None,'http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler)
        result = acceptance.test_catalog_structure()
        self.assertFalse(result)
        self.assertIn("http://example.com doesn't have 'languages'", acceptance.errors)

    def test_empty_languages(self, mock_reporter):
        acceptance = AcceptanceHandler(self.make_event(), None,'http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler)
        result = acceptance._test_languages([])
        self.assertFalse(result)
        self.assertIn("There needs to be at least one language in the catalog", acceptance.errors)

    def test_languages_not_array(self, mock_reporter):
        acceptance = AcceptanceHandler(self.make_event(), None,'http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler)
        result = acceptance._test_languages(9)
        self.assertFalse(result)
        self.assertIn("'languages' is not an array", acceptance.errors)

    def test_language_not_dict(self, mock_reporter):
        acceptance = AcceptanceHandler(self.make_event(), None,'http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler)
        result = acceptance._test_languages([{}, []])
        self.assertFalse(result)
        self.assertIn("languages: Found a language container that doesn't have 'identifier'", acceptance.errors)
        self.assertIn("languages: Found a language container that is not an associative array", acceptance.errors)

    def test_language_missing_keys(self, mock_reporter):
        acceptance = AcceptanceHandler(self.make_event(), None,'http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler)
        result = acceptance._test_languages([{"identifier":"en"}])
        self.assertFalse(result)
        self.assertIn("en: 'title' does not exist", acceptance.errors)
        self.assertIn("en: 'direction' does not exist", acceptance.errors)

    def test_resources_not_array(self, mock_reporter):
        acceptance = AcceptanceHandler(self.make_event(), None,'http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler)
        result = acceptance._test_resources("en", 9)
        self.assertFalse(result)
        self.assertIn("en: 'resources' is not an array", acceptance.errors)

    def test_resource_not_dict(self, mock_reporter):
        acceptance = AcceptanceHandler(self.make_event(), None,'http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler)
        result = acceptance._test_resources("en", [{}, 9])
        self.assertFalse(result)
        self.assertIn("en resources: A resource container exists without an 'identifier'", acceptance.errors)
        self.assertIn("en: Found a resource container that is not an associative array", acceptance.errors)

    def test_resource_missing_keys(self, mock_reporter):
        acceptance = AcceptanceHandler(self.make_event(), None,'http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler)

        result = acceptance._test_resources("en", [{"identifier":"id"}])
        self.assertFalse(result)
        self.assertIn("en_id: resource is missing 'title'", acceptance.errors)
        self.assertIn("en_id: resource is missing 'source'", acceptance.errors)
        self.assertIn("en_id: resource is missing 'rights'", acceptance.errors)
        self.assertIn("en_id: resource is missing 'creator'", acceptance.errors)
        self.assertIn("en_id: resource is missing 'contributor'", acceptance.errors)
        self.assertIn("en_id: resource is missing 'relation'", acceptance.errors)
        self.assertIn("en_id: resource is missing 'publisher'", acceptance.errors)
        self.assertIn("en_id: resource is missing 'issued'", acceptance.errors)
        self.assertIn("en_id: resource is missing 'modified'", acceptance.errors)
        self.assertIn("en_id: resource is missing 'version'", acceptance.errors)
        self.assertIn("en_id: resource is missing 'checking'", acceptance.errors)
        self.assertIn("en_id: resource is missing 'projects'", acceptance.errors)

    def test_projects_not_array(self, mock_reporter):
        acceptance = AcceptanceHandler(self.make_event(), None,'http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler)

        result = acceptance._test_projects("en", "id", 9, {})
        self.assertFalse(result)
        self.assertIn("en_id: 'projects' is not an array", acceptance.errors)

    def test_project_not_dictionary(self, mock_reporter):
        acceptance = AcceptanceHandler(self.make_event(), None,'http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler)

        result = acceptance._test_projects("en", "id", [9], {})
        self.assertFalse(result)
        self.assertIn("en_id: project is not a dictionary", acceptance.errors)

    def test_project_missing_keys(self, mock_reporter):
        acceptance = AcceptanceHandler(self.make_event(), None,'http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler)

        result = acceptance._test_projects("en", "id", [{}], {})
        self.assertFalse(result)
        self.assertIn("en_id: project missing 'categories'", acceptance.errors)
        self.assertIn("en_id: project missing 'identifier'", acceptance.errors)
        self.assertIn("en_id: project missing 'sort'", acceptance.errors)
        self.assertIn("en_id: project missing 'title'", acceptance.errors)
        self.assertIn("en_id: project missing 'versification'", acceptance.errors)

    def test_formats_missing_in_multi_project_resource(self, mock_reporter):
        acceptance = AcceptanceHandler(self.make_event(), None,'http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler)

        result = acceptance._test_projects("en", "id", [{},{}], {})
        self.assertFalse(result)
        self.assertIn("en_id: 'formats' does not exist in multi-project resource", acceptance.errors)

    def test_formats_in_single_project_resource(self, mock_reporter):
        acceptance = AcceptanceHandler(self.make_event(), None,'http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler)

        result = acceptance._test_projects("en", "id", [{}], {"formats":[]})
        self.assertFalse(result)
        self.assertIn("en_id: 'formats' found in single-project resource", acceptance.errors)

    def test_formats_not_array(self, mock_reporter):
        acceptance = AcceptanceHandler(self.make_event(), None,'http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler)

        result = acceptance._test_formats(6, "en", "id")
        self.assertFalse(result)
        self.assertIn("en_id: 'formats' is not an array", acceptance.errors)

    def test_format_missing_key(self, mock_reporter):
        acceptance = AcceptanceHandler(self.make_event(), None,'http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler)

        result = acceptance._test_formats([{}], "en", "id")
        self.assertFalse(result)
        self.assertIn("Format container for 'en_id' doesn't have 'format'", acceptance.errors)
        self.assertIn("Format container for 'en_id' doesn't have 'modified'", acceptance.errors)
        self.assertIn("Format container for 'en_id' doesn't have 'size'", acceptance.errors)
        self.assertIn("Format container for 'en_id' doesn't have 'url'", acceptance.errors)
        self.assertIn("Format container for 'en_id' doesn't have 'signature'", acceptance.errors)

    def test_video_format_has_quality(self, mock_reporter):
        TestAcceptance.MockHttpConnection.response = TestAcceptance.MockResponse(200)
        acceptance = AcceptanceHandler(self.make_event(), None,'http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler)
        format = {
            "identifier":"obs",
            "modified":"",
            "size":0,
            "url":"",
            "signature":"example.com/file.sig",
            "format": "content=video/mp4"
        }

        result = acceptance._test_formats([format], "en", "obs", "obs")
        self.assertFalse(result)
        self.assertIn("en_obs: Missing 'quality' key in media format", acceptance.errors)

    def test_audio_format_has_quality(self, mock_reporter):
        TestAcceptance.MockHttpConnection.response = TestAcceptance.MockResponse(200)
        acceptance = AcceptanceHandler(self.make_event(), None,'http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler)
        format = {
            "identifier": "obs",
            "modified": "",
            "size": 0,
            "url": "",
            "signature": "example.com/file.sig",
            "format": "content=video/mp3"
        }
        result = acceptance._test_formats([format], "en", "obs", "obs")
        self.assertFalse(result)
        self.assertIn("en_obs: Missing 'quality' key in media format", acceptance.errors)

    def test_resource_cannot_have_chapters(self, mock_reporter):
        TestAcceptance.MockHttpConnection.response = TestAcceptance.MockResponse(200)
        acceptance = AcceptanceHandler(self.make_event(), None,'http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler)
        format = {
            "identifier": "obs",
            "modified": "",
            "size": 0,
            "url": "",
            "signature": "example.com/file.sig",
            "format": "content=video/mp3",
            "chapters":[]
        }
        result = acceptance._test_formats([format], "en", "obs")
        self.assertFalse(result)
        self.assertIn("en_obs: chapters can only be in project formats", acceptance.errors)

    def test_chapter_missing_keys(self, mock_reporter):
        TestAcceptance.MockHttpConnection.response = TestAcceptance.MockResponse(200)
        acceptance = AcceptanceHandler(self.make_event(), None,'http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler)
        chapter = {
        }
        result = acceptance._test_chapters("en", "obs", "obs", [chapter])
        self.assertFalse(result)
        self.assertIn('en_obs_obs: chapter format is missing "identifier"', acceptance.errors)
        self.assertIn('en_obs_obs: chapter format is missing "modified"', acceptance.errors)
        self.assertIn('en_obs_obs: chapter format is missing "signature"', acceptance.errors)
        self.assertIn('en_obs_obs: chapter format is missing "size"', acceptance.errors)
        self.assertIn('en_obs_obs: chapter format is missing "url"', acceptance.errors)

    def test_chapter_missing_length(self, mock_reporter):
        TestAcceptance.MockHttpConnection.response = TestAcceptance.MockResponse(200)
        acceptance = AcceptanceHandler(self.make_event(), None,'http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler)
        chapter = {
            "format": "audio/mp3",
            "identifier": "29",
            "modified": "2017-07-28T20:05:58.052139",
            "signature": "https://cdn.door43.org/en/obs/v4/64kbps/en_obs_29_64kbps.mp3.sig",
            "size": 1037295,
            "url": "https://cdn.door43.org/en/obs/v4/64kbps/en_obs_29_64kbps.mp3"
        }
        result = acceptance._test_chapters("en", "obs", "obs", [chapter])
        self.assertFalse(result)
        self.assertEqual(1, len(acceptance.errors))
        self.assertIn('en_obs_obs: chapter media format is missing "length"', acceptance.errors)

    def test_chapter_missing_urls(self, mock_reporter):
        TestAcceptance.MockHttpConnection.response = TestAcceptance.MockResponse(404)
        acceptance = AcceptanceHandler(self.make_event(), None,'http://example.com', self.MockURLHandler, self.MockHttpConnection,
                                    self.MockSESHandler)
        chapter = {
            "format": "audio/mp3",
            "identifier": "29",
            "modified": "2017-07-28T20:05:58.052139",
            "signature": "http://exampe.com.sig",
            "size": 1037295,
            "length":0,
            "url": "http://exampe.com"
        }
        result = acceptance._test_chapters("en", "obs", "obs", [chapter])
        self.assertFalse(result)
        self.assertIn("en_obs_obs: 'http://exampe.com' does not exist", acceptance.errors)
        self.assertIn("en_obs_obs: 'http://exampe.com.sig' does not exist", acceptance.errors)

    def make_event(self):
        return {
            'stage-variables':{
                'from_email': 'me@example.com',
                'to_email':'me@example.com'
            }
        }