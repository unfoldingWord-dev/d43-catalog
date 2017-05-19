import codecs
import os
import json
from unittest import TestCase
from functions.webhook.webhook_handler import WebhookHandler

class TestWebhook(TestCase):
    resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

    class MockDynamodbHandler(object):
        data = None

        @staticmethod
        def insert_item(data):
            TestWebhook.MockDynamodbHandler.data = data

    class MockS3Handler:
        uploads = []

        @staticmethod
        def reset():
            TestWebhook.MockS3Handler.uploads = []

        @staticmethod
        def upload_file(path, key):
            TestWebhook.MockS3Handler.uploads.append({
                'key': key,
                'path': path
            })

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_webook_with_invalid_data(self):
        request_file = os.path.join(self.resources_dir, 'missing-manifest.json')

        with codecs.open(request_file, 'r', encoding='utf-8') as in_file:
            request_text = in_file.read()
            # convert Windows line endings to Linux line endings
            content = request_text.replace('\r\n', '\n')

            # deserialized object
            request_json = json.loads(content)

        self.MockDynamodbHandler.data = None
        self.MockS3Handler.reset()
        handler = WebhookHandler(request_json, self.MockS3Handler, self.MockDynamodbHandler)
        with self.assertRaises(Exception) as error_context:
            handler.run()

        self.assertIn('does not have a manifest.yaml file', str(error_context.exception))

        self.assertFalse(os.path.isdir(handler.temp_dir))

    def test_webhook_with_obs_data(self):
        request_file = os.path.join(self.resources_dir, 'obs-request.json')

        with codecs.open(request_file, 'r', encoding='utf-8') as in_file:
            request_text = in_file.read()
            # convert Windows line endings to Linux line endings
            content = request_text.replace('\r\n', '\n')

            # deserialized object
            request_json = json.loads(content)

        self.MockDynamodbHandler.data = None
        self.MockS3Handler.reset()
        handler = WebhookHandler(request_json, self.MockS3Handler, self.MockDynamodbHandler)
        handler.run()

        entry = self.MockDynamodbHandler.data
        self.assertEqual(1, len(self.MockS3Handler.uploads))
        self.assertIn('/en-obs.zip', self.MockS3Handler.uploads[0]['path'])
        self.assertIn('temp/en-obs/{}/obs.zip'.format(entry['commit_id']), self.MockS3Handler.uploads[0]['key'])

    def test_webhook_ulb(self):
        request_file = os.path.join(self.resources_dir, 'ulb-request.json')

        with codecs.open(request_file, 'r', encoding='utf-8') as in_file:
            request_text = in_file.read()
            # convert Windows line endings to Linux line endings
            content = request_text.replace('\r\n', '\n')

            # deserialized object
            request_json = json.loads(content)

        self.MockDynamodbHandler.data = None
        self.MockS3Handler.reset()
        handler = WebhookHandler(request_json, self.MockS3Handler, self.MockDynamodbHandler)
        handler.run()

        entry = self.MockDynamodbHandler.data
        self.assertEqual(1, len(self.MockS3Handler.uploads))
        self.assertIn('/en-ulb.zip', self.MockS3Handler.uploads[0]['path'])
        self.assertIn('temp/en-ulb/{}/ulb.zip'.format(entry['commit_id']), self.MockS3Handler.uploads[0]['key'])

    def test_webhook_versification(self):
        request_file = os.path.join(self.resources_dir, 'versification-request.json')
        with codecs.open(request_file, 'r', encoding='utf-8') as in_file:
            request_text = in_file.read()
            # convert Windows line endings to Linux line endings
            content = request_text.replace('\r\n', '\n')

            # deserialized object
            request_json = json.loads(content)

        self.MockDynamodbHandler.data = None
        self.MockS3Handler.reset()
        handler = WebhookHandler(request_json, self.MockS3Handler, self.MockDynamodbHandler)
        handler.run()

        self.assertEqual(66, len(self.MockS3Handler.uploads))
        data = self.MockDynamodbHandler.data
        self.assertTrue(len(data['package']) > 0)
        package = json.loads(data['package'])
        self.assertIn('chunks_url', package[0])
        self.assertIn('https://cdn.door43.org/bible/', package[0]['chunks_url'])
        self.assertIn('identifier', package[0])
        self.assertNotIn('chunks', package[0])
        for upload in self.MockS3Handler.uploads:
            # for now we are bypassing signing and uploading directly
            self.assertIn('bible/'.format(data['commit_id']), upload['key'])
            #self.assertIn('temp/versification/{}/'.format(data['commit_id']), upload['key'])

    def test_webhook_localization(self):
        request_file = os.path.join(self.resources_dir, 'localization-request.json')
        with codecs.open(request_file, 'r', encoding='utf-8') as in_file:
            request_text = in_file.read()
            # convert Windows line endings to Linux line endings
            content = request_text.replace('\r\n', '\n')

            # deserialized object
            request_json = json.loads(content)

        self.MockDynamodbHandler.data = None
        self.MockS3Handler.reset()
        handler = WebhookHandler(request_json, self.MockS3Handler, self.MockDynamodbHandler)
        handler.run()
