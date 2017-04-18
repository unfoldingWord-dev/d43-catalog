import codecs
import os
import json
from unittest import TestCase
from functions.webhook.repo_handler import RepoHandler

class TestWebhook(TestCase):
    resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

    class MockDynamodbHandler(object):
        def __init__(self):
            pass

        @staticmethod
        def insert_item(data):
            pass

    class MockS3Handler:
        def __init__(self):
            pass

        @staticmethod
        def upload_file(path, key):
            pass

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_webook_with_invalid_data(self):
        request_file = os.path.join(self.resources_dir, 'invalid-request.json')

        with codecs.open(request_file, 'r', encoding='utf-8') as in_file:
            request_text = in_file.read()
            # convert Windows line endings to Linux line endings
            content = request_text.replace('\r\n', '\n')

            # deserialized object
            request_json = json.loads(content)

        handler = RepoHandler(request_json, self.MockS3Handler, self.MockDynamodbHandler)
        with self.assertRaises(Exception) as error_context:
            handler.run()

        self.assertIn('Bad Manifest', str(error_context.exception))

        self.assertFalse(os.path.isdir(handler.temp_dir))

    def test_webook_with_valid_data(self):
        request_file = os.path.join(self.resources_dir, 'valid-request.json')

        with codecs.open(request_file, 'r', encoding='utf-8') as in_file:
            request_text = in_file.read()
            # convert Windows line endings to Linux line endings
            content = request_text.replace('\r\n', '\n')

            # deserialized object
            request_json = json.loads(content)

        handler = RepoHandler(request_json, self.MockS3Handler, self.MockDynamodbHandler)
        handler.run()