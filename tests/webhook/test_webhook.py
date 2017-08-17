import codecs
import json
import os
from unittest import TestCase

from libraries.tools.mocks import MockAPI, MockDynamodbHandler, MockS3Handler, MockLogger

from functions.webhook import WebhookHandler
from libraries.tools.test_utils import assert_object_equals_file


# This is here to test importing main


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
        mockLogger = MockLogger()
        handler = WebhookHandler(event=request_json,
                                 logger=mockLogger,
                                 s3_handler=self.MockS3Handler,
                                 dynamodb_handler=self.MockDynamodbHandler)
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

        mockLogger = MockLogger()
        mockDCS = MockAPI(self.resources_dir, 'https://git.door43.org/')
        self.MockDynamodbHandler.data = None
        self.MockS3Handler.reset()
        urls = {
            'https://git.door43.org/Door43-Catalog/en_obs/archive/f8a8d8d757e7ea287cf91b266963f8523bdbd5ad.zip': 'en_obs.zip'
        }
        mock_download = lambda url, dest: mockDCS.download_file(urls[url], dest)
        handler = WebhookHandler(event=request_json,
                                 logger=mockLogger,
                                 s3_handler=self.MockS3Handler,
                                 dynamodb_handler=self.MockDynamodbHandler,
                                 download_handler=mock_download)
        handler.run()

        entry = self.MockDynamodbHandler.data
        self.assertEqual(1, len(self.MockS3Handler.uploads))
        self.assertIn('/en_obs.zip', self.MockS3Handler.uploads[0]['path'])
        self.assertIn('temp/en_obs/{}/en/obs/v4/obs.zip'.format(entry['commit_id']), self.MockS3Handler.uploads[0]['key'])

        self.assertEqual('f8a8d8d757', entry['commit_id'])
        self.assertEqual(False, entry['dirty'])
        self.assertEqual('en', entry['language'])
        self.assertEqual('2017-04-25T21:46:30+00:00', entry['timestamp'])
        self.assertEqual(False, entry['signed'])
        self.assertEqual('en_obs', entry['repo_name'])
        assert_object_equals_file(self, json.loads(entry['package']), os.path.join(self.resources_dir, 'expected_obs_package.json'))

    def test_webhook_ulb_merged_pull_request(self):
        request_file = os.path.join(self.resources_dir, 'ulb-merged-pull-request.json')
        with codecs.open(request_file, 'r', encoding='utf-8') as in_file:
            request_text = in_file.read()
            # convert Windows line endings to Linux line endings
            content = request_text.replace('\r\n', '\n')

            # deserialized object
            request_json = json.loads(content)

        mockLogger = MockLogger()
        mockDCS = MockAPI(self.resources_dir, 'https://git.door43.org/')
        urls = {
            'https://git.door43.org/Door43-Catalog/ta_ulb/archive/0a7e25cd939f00086262fe94b9d25afc3b5dabd3.zip': 'ta_ulb.zip'
        }
        mock_download = lambda url, dest: mockDCS.download_file(urls[url], dest)
        self.MockDynamodbHandler.data = None
        self.MockS3Handler.reset()
        handler = WebhookHandler(event=request_json,
                                 logger=mockLogger,
                                 s3_handler=self.MockS3Handler,
                                 dynamodb_handler=self.MockDynamodbHandler,
                                 download_handler=mock_download)
        handler.run()
        entry = self.MockDynamodbHandler.data
        self.assertEqual(4, len(self.MockS3Handler.uploads))  # books and bundle
        self.assertIn('/ta_ulb.zip', self.MockS3Handler.uploads[0]['path'])

        self.assertEqual('0a7e25cd93', entry['commit_id'])
        self.assertEqual(False, entry['dirty'])
        self.assertEqual('ta', entry['language'])
        self.assertEqual('2017-08-17T18:56:52.884140+00:00', entry['timestamp'])
        self.assertEqual(False, entry['signed'])
        self.assertEqual('ta_ulb', entry['repo_name'])
        self.assertIn('temp/ta_ulb/{}/ta/ulb/v3/ulb.zip'.format(entry['commit_id']),
                      self.MockS3Handler.uploads[0]['key'])

    def test_webhook_ulb_pull_request(self):
        request_file = os.path.join(self.resources_dir, 'ulb-pull-request.json')
        with codecs.open(request_file, 'r', encoding='utf-8') as in_file:
            request_text = in_file.read()
            # convert Windows line endings to Linux line endings
            content = request_text.replace('\r\n', '\n')

            # deserialized object
            request_json = json.loads(content)

        mockLogger = MockLogger()
        mockDCS = MockAPI(self.resources_dir, 'https://git.door43.org/')
        urls = {
            'https://git.door43.org/Door43-Catalog/en_ulb/archive/2fbfd081f46487e48e49090a95c48d45e04e6bed.zip': 'en_ulb.zip'
        }
        mock_download = lambda url, dest: mockDCS.download_file(urls[url], dest)
        self.MockDynamodbHandler.data = None
        self.MockS3Handler.reset()
        handler = WebhookHandler(event=request_json,
                                 logger=mockLogger,
                                 s3_handler=self.MockS3Handler,
                                 dynamodb_handler=self.MockDynamodbHandler,
                                 download_handler=mock_download)

        with self.assertRaises(Exception) as error_context:
            handler.run()
        self.assertIn('Skipping un-merged pull request', str(error_context.exception))
        entry = self.MockDynamodbHandler.data
        self.assertEqual(0, len(self.MockS3Handler.uploads))
        self.assertIsNone(entry)

    def test_webhook_ulb(self):
        request_file = os.path.join(self.resources_dir, 'ulb-request.json')

        with codecs.open(request_file, 'r', encoding='utf-8') as in_file:
            request_text = in_file.read()
            # convert Windows line endings to Linux line endings
            content = request_text.replace('\r\n', '\n')

            # deserialized object
            request_json = json.loads(content)

        mockLogger = MockLogger()
        mockDCS = MockAPI(self.resources_dir, 'https://git.door43.org/')
        urls = {
            'https://git.door43.org/Door43-Catalog/en_ulb/archive/2fbfd081f46487e48e49090a95c48d45e04e6bed.zip': 'en_ulb.zip'
        }
        mock_download = lambda url, dest: mockDCS.download_file(urls[url], dest)
        self.MockDynamodbHandler.data = None
        self.MockS3Handler.reset()
        handler = WebhookHandler(event=request_json,
                                 logger=mockLogger,
                                 s3_handler=self.MockS3Handler,
                                 dynamodb_handler=self.MockDynamodbHandler,
                                 download_handler=mock_download)
        handler.run()

        entry = self.MockDynamodbHandler.data
        self.assertEqual(4, len(self.MockS3Handler.uploads)) # books and bundle
        self.assertIn('/en_ulb.zip', self.MockS3Handler.uploads[0]['path'])

        self.assertEqual('2fbfd081f4', entry['commit_id'])
        self.assertEqual(False, entry['dirty'])
        self.assertEqual('en', entry['language'])
        self.assertEqual('2017-05-02T22:52:04+00:00', entry['timestamp'])
        self.assertEqual(False, entry['signed'])
        self.assertEqual('en_ulb', entry['repo_name'])
        self.assertIn('temp/en_ulb/{}/en/ulb/v7/ulb.zip'.format(entry['commit_id']), self.MockS3Handler.uploads[0]['key'])

        assert_object_equals_file(self, json.loads(entry['package']), os.path.join(self.resources_dir, 'expected_ulb_package.json'))

    def test_webhook_versification(self):
        request_file = os.path.join(self.resources_dir, 'versification-request.json')
        with codecs.open(request_file, 'r', encoding='utf-8') as in_file:
            request_text = in_file.read()
            # convert Windows line endings to Linux line endings
            content = request_text.replace('\r\n', '\n')
            request_json = json.loads(content)

        urls = {
            'https://git.door43.org/Door43-Catalog/versification/archive/c7e936e4dcc103560987c8475db69e292aa66dca.zip': 'versification.zip'
        }

        mockLogger = MockLogger()
        mock_api = MockAPI(self.resources_dir, 'https://git.door43.org')
        mock_db = MockDynamodbHandler()
        mock_s3 = MockS3Handler()
        handler = WebhookHandler(request_json,
                    s3_handler=mock_s3,
                    logger=mockLogger,
                    dynamodb_handler=mock_db,
                    download_handler=lambda url, dest: mock_api.download_file(urls[url], dest))
        handler.run()

        self.assertEqual(66, len(mock_s3._recent_uploads))
        data = mock_db._last_inserted_item
        self.assertTrue(len(data['package']) > 0)
        package = json.loads(data['package'])
        self.assertIn('chunks_url', package[0])
        self.assertIn('https://cdn.door43.org/bible/', package[0]['chunks_url'])
        self.assertIn('identifier', package[0])
        self.assertNotIn('chunks', package[0])
        for key in mock_s3._recent_uploads:
            dest = mock_s3._recent_uploads[key]
            # for now we are bypassing signing and uploading directly
            self.assertIn('bible/'.format(data['commit_id']), dest)
            #self.assertIn('temp/versification/{}/'.format(data['commit_id']), upload['key'])

    def test_webhook_localization(self):
        request_file = os.path.join(self.resources_dir, 'localization-request.json')
        with codecs.open(request_file, 'r', encoding='utf-8') as in_file:
            request_text = in_file.read()
            # convert Windows line endings to Linux line endings
            content = request_text.replace('\r\n', '\n')

            # deserialized object
            request_json = json.loads(content)

        mockLogger = MockLogger()
        self.MockDynamodbHandler.data = None
        self.MockS3Handler.reset()
        handler = WebhookHandler(event=request_json,
                                 logger=mockLogger,
                                 s3_handler=self.MockS3Handler,
                                 dynamodb_handler=self.MockDynamodbHandler)
        handler.run()
