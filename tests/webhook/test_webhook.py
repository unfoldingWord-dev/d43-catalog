import codecs
import os
import json
from unittest import TestCase
from functions.webhook.repo_handler import RepoHandler


class TestWebhook(TestCase):
    resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_webook_with_valid_data(self):
        request_file = os.path.join(self.resources_dir, 'valid-request.json')

        with codecs.open(request_file, 'r', encoding='utf-8') as in_file:
            request_text = in_file.read()
            # convert Windows line endings to Linux line endings
            content = request_text.replace('\r\n', '\n')

            # deserialized object
            request_json = json.loads(content)

        handler = RepoHandler(request_json)
        with self.assertRaises(Exception) as error_context:
            handler.run()

        self.assertIn('Bad Manifest', str(error_context.exception))