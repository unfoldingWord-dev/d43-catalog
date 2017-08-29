from __future__ import unicode_literals, print_function

import json
import os
import shutil
import tempfile
import unittest
import mock
from mock import Mock, patch, MagicMock
from unittest import TestCase

from libraries.tools.file_utils import load_json_object
from libraries.tools.mocks import MockDynamodbHandler, MockS3Handler, MockLogger, MockSigner, MockAPI
from libraries.tools.signer import Signer
from libraries.tools.url_utils import HeaderReader

from libraries.lambda_handlers.signing_handler import SigningHandler
from libraries.tools.test_utils import assert_object_not_equals, is_travis, assert_object_equals_file


# This is here to test importing main

@patch('libraries.lambda_handlers.handler.ErrorReporter')
class TestSigningHandler(TestCase):

    def setUp(self):
        self.mock_signer = MockSigner()
        self.resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')
        self.temp_dir = tempfile.mkdtemp(prefix='signing_tests_')
        self.s3keys = []

    def tearDown(self):
        # clean up local temp files
        if os.path.isdir(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_db_item(self, commit_id=None):
        item = load_json_object(os.path.join(self.resources_dir, 'dynamodb_record.json'))[0]
        if commit_id:
            item['commit_id'] = commit_id
        return item

    def create_event(self):

        event = {
            'stage-variables': {
                'cdn_bucket': 'cdn.door43.org',
                'cdn_url': 'https://cdn.door43.org',
                'from_email': '',
                'to_email': ''
            }
        }

        return event

    def test_signing_handler_text_no_records(self, mock_reporter):
        event = self.create_event()
        mock_db = MockDynamodbHandler()
        mock_s3 = MockS3Handler()

        mock_api = MockAPI(os.path.join(self.resources_dir, 'cdn'), 'https://cdn.door43.org')

        handler = SigningHandler(event,
                                 None,
                                 logger=MockLogger(),
                                 signer=self.mock_signer,
                                 s3_handler=mock_s3,
                                 dynamodb_handler=mock_db,
                                 url_exists_handler=mock_api.url_exists,
                                 download_handler=mock_api.download_file)
        result = handler.run()
        self.assertFalse(result)

    def test_signing_handler_invalid_manifest(self, mock_reporter):
        mock_instance = MagicMock()
        mock_instance.add_error = MagicMock()
        mock_reporter.return_value = mock_instance

        event = self.create_event()
        mock_db = MockDynamodbHandler()
        mock_db._load_db(os.path.join(self.resources_dir, 'db/invalid.json'))

        mock_s3 = MockS3Handler()
        mock_s3._load_path(os.path.join(self.resources_dir, 'cdn'))

        mock_api = MockAPI(os.path.join(self.resources_dir, 'cdn'), 'https://cdn.door43.org')

        mock_logger = MockLogger()

        signer = SigningHandler(event,
                                None,
                                logger=mock_logger,
                                signer=self.mock_signer,
                                s3_handler=mock_s3,
                                dynamodb_handler=mock_db,
                                url_exists_handler=mock_api.url_exists,
                                download_handler=mock_api.download_file)
        result = signer.run()

        self.assertTrue(result)
        for f in mock_s3._recent_uploads:
            # assert nothing was uploaded to production
            self.assertTrue(f.startswith('temp/'))
            self.assertFalse(f.endswith('.sig'))
        # self.assertIn('Skipping unit-test. Bad Manifest: No JSON object could be decoded', mock_logger._messages)
        mock_instance.add_error.assert_called_once_with('Skipping unit-test. Bad Manifest: No JSON object could be decoded')

    def test_signing_handler_text_missing_file(self, mock_reporter):
        """
        Signing will continue to run even if a file is missing.
        The missing file will just be ignored.
        :return:
        """

        event = self.create_event()

        mock_db = MockDynamodbHandler()
        mock_db._load_db(os.path.join(self.resources_dir, 'db/valid_unsigned.json'))

        mock_api = MockAPI(os.path.join(self.resources_dir, 'cdn'), 'https://cdn.door43.org')

        mock_logger = MockLogger()
        mock_s3 = MockS3Handler()

        signer = SigningHandler(event,
                                None,
                                logger=mock_logger,
                                signer=self.mock_signer,
                                s3_handler=mock_s3,
                                dynamodb_handler=mock_db,
                                url_exists_handler=mock_api.url_exists,
                                download_handler=mock_api.download_file)
        result = signer.run()
        self.assertTrue(result)
        self.assertIn('The file "obs.zip" could not be downloaded: File not found for key: temp/en_obs/f8a8d8d757/en/obs/v4/obs.zip', mock_logger._messages)

    def test_signing_handler_text_wrong_key(self, mock_reporter):
        event = self.create_event()

        mock_db = MockDynamodbHandler()
        mock_db._load_db(os.path.join(self.resources_dir, 'db/valid_unsigned.json'))

        mock_s3 = MockS3Handler()
        mock_s3._load_path(os.path.join(self.resources_dir, 'cdn'))

        mock_api = MockAPI(os.path.join(self.resources_dir, 'cdn'), 'https://cdn.door43.org')

        mock_logger = MockLogger()

        # TRICKY: a wrong signing key will result in failed verification
        self.mock_signer._fail_verification()
        signer = SigningHandler(event,
                                None,
                                logger=mock_logger,
                                signer=self.mock_signer,
                                s3_handler=mock_s3,
                                dynamodb_handler=mock_db,
                                url_exists_handler=mock_api.url_exists,
                                download_handler=mock_api.download_file)
        result = signer.run()

        self.assertTrue(result)
        for f in mock_s3._recent_uploads:
            # assert nothing was uploaded to production
            self.assertTrue(f.startswith('temp/'))
            self.assertFalse(f.endswith('.sig'))
        self.assertIn('The signature was not successfully verified.', mock_logger._messages)

    def test_signing_handler_s3(self, mock_reporter):
        mock_s3 = MockS3Handler()
        mock_s3._load_path(os.path.join(self.resources_dir, 'cdn'))

        mock_db = MockDynamodbHandler()
        mock_db._load_db(os.path.join(self.resources_dir, 'db/valid_unsigned.json'))

        mock_logger = MockLogger()

        mock_api = MockAPI(os.path.join(self.resources_dir, 'cdn'), 'https://cdn.door43.org/')

        event = self.create_event()

        original_item = mock_db.get_item({'repo_name': 'en_obs'}).copy()
        self.assertIn('signed', original_item)
        self.assertFalse(original_item['signed'])

        global_headers = HeaderReader([
            ('last-modified', 'Fri, 03 Jun 2017 20:23:12 GMT'),
            ('content-length', 12345)
        ])

        signer = SigningHandler(event,
                                None,
                                logger=mock_logger,
                                signer=self.mock_signer,
                                s3_handler=mock_s3,
                                dynamodb_handler=mock_db,
                                url_exists_handler=mock_api.url_exists,
                                download_handler=mock_api.download_file,
                                url_headers_handler=lambda url: global_headers)
        result = signer.run()
        self.assertTrue(result)

        self.assertTrue(len(mock_s3._recent_uploads) > 0)
        has_prod_uploads = False
        for key in mock_s3._recent_uploads:
            # assert prod uploads have signatures
            if not key.startswith('temp/') and not key.endswith('.sig'):
                has_prod_uploads = True
                self.assertIn('{}.sig'.format(key), mock_s3._recent_uploads)
        self.assertTrue(has_prod_uploads)

        updated_item = mock_db.get_item({'repo_name': 'en_obs'}).copy()
        assert_object_not_equals(self, updated_item, original_item)
        assert_object_equals_file(self, json.loads(updated_item['package']), os.path.join(self.resources_dir, 'db/expected_signed_package.json'))

        self.assertIn('Skipping chapter obs:01 missing url https://cdn.door43.org/en/obs/v4/32kbps/en_obs_01_32kbps.mp3', mock_logger._messages)
        self.assertTrue(updated_item['signed'])

    def test_signing_handler_no_records(self, mock_reporter):
        event = self.create_event()

        mock_logger = MockLogger()
        mock_db = MockDynamodbHandler()
        mock_s3 = MockS3Handler()

        mock_api = MockAPI(os.path.join(self.resources_dir, 'cdn'), 'https://cdn.door43.org')

        signer = SigningHandler(event,
                                None,
                                logger=mock_logger,
                                signer=self.mock_signer,
                                s3_handler=mock_s3,
                                dynamodb_handler=mock_db,
                                url_exists_handler=mock_api.url_exists,
                                download_handler=mock_api.download_file)
        result = signer.run()

        self.assertFalse(result)
        self.assertIn('No items found for signing', mock_logger._messages)

    def test_signing_handler_already_signed(self, mock_reporter):
        event = self.create_event()
        mock_s3 = MockS3Handler()
        mock_db = MockDynamodbHandler()
        mock_db._load_db(os.path.join(self.resources_dir, 'db/valid_signed.json'))
        mock_logger = MockLogger()
        original_record = mock_db.get_item({'repo_name':'en_obs'}).copy()
        self.assertFalse(original_record['signed'])

        mock_api = MockAPI(os.path.join(self.resources_dir, 'cdn'), 'https://cdn.door43.org')

        signer = SigningHandler(event,
                                None,
                                logger=mock_logger,
                                signer=self.mock_signer,
                                s3_handler=mock_s3,
                                dynamodb_handler=mock_db,
                                url_exists_handler=mock_api.url_exists,
                                download_handler=mock_api.download_file)

        result = signer.run()
        self.assertTrue(result)

        updated_record = mock_db.get_item({'repo_name': 'en_obs'}).copy()
        self.assertTrue(updated_record['signed'])

    def test_skip_signing_large_file(self, mock_reporter):
        """
        Ensure that large files are not signed.
        Because lambda functions have limited disk space.
        :return:
        """
        mock_s3 = MockS3Handler()
        mock_db = MockDynamodbHandler()
        mock_logger = MockLogger()
        mock_api = MockAPI(os.path.join(self.resources_dir, 'cdn'), 'https://cdn.door43.org/')
        event = self.create_event()
        item = {
            'repo_name': 'repo_name',
            'commit_id': 'commitid'
        }
        format = {
          "build_rules": [
            "signing.sign_given_url"
          ],
          "chapters": [],
          "contributor": [
            "Narrator: Steve Lossing",
            "Checker: Brad Harrington",
            "Engineer: Brad Harrington"
          ],
          "format": "",
          "modified": "",
          "quality": "64kbps",
          "signature": "",
          "size": 0,
          "url": "https://cdn.door43.org/en/obs/v4/64kbps/en_obs_64kbps.zip"
        }
        mockHeaders = HeaderReader([
            ('content-length', SigningHandler.max_file_size + 1)
        ])

        signer = SigningHandler(event=event,
                                context=None,
                                logger=mock_logger,
                                signer=self.mock_signer,
                                s3_handler=mock_s3,
                                dynamodb_handler=mock_db,
                                url_exists_handler=mock_api.url_exists,
                                download_handler=mock_api.download_file,
                                url_headers_handler=lambda url: mockHeaders)
        (already_signed, newly_signed) = signer.process_format(item, format)
        self.assertIn('File is too large to sign https://cdn.door43.org/en/obs/v4/64kbps/en_obs_64kbps.zip', mock_logger._messages)
        self.assertFalse(already_signed)
        # TRICKY: for now we are faking the signature so the catalog can build.
        self.assertEqual('https://cdn.door43.org/en/obs/v4/64kbps/en_obs_64kbps.zip.sig', format['signature'])
        self.assertTrue(newly_signed)

    def test_signing_small_file(self, mock_reporter):
        """
        Ensure that small files are signed properly
        :return:
        """
        mock_s3 = MockS3Handler()
        mock_db = MockDynamodbHandler()
        mock_logger = MockLogger()
        mock_api = MockAPI(os.path.join(self.resources_dir, 'cdn'), 'https://cdn.door43.org/')
        event = self.create_event()
        item = {
            'repo_name': 'repo_name',
            'commit_id': 'commitid'
        }
        format = {
          "build_rules": [
            "signing.sign_given_url"
          ],
          "chapters": [],
          "contributor": [
            "Narrator: Steve Lossing",
            "Checker: Brad Harrington",
            "Engineer: Brad Harrington"
          ],
          "format": "",
          "modified": "",
          "quality": "64kbps",
          "signature": "",
          "size": 0,
          "url": "https://cdn.door43.org/en/obs/v4/64kbps/en_obs_64kbps.zip"
        }
        mockHeaders = HeaderReader([
            ('content-length', 123)
        ])
        signer = SigningHandler(event,
                                None,
                                logger=mock_logger,
                                signer=self.mock_signer,
                                s3_handler=mock_s3,
                                dynamodb_handler=mock_db,
                                url_exists_handler=mock_api.url_exists,
                                download_handler=mock_api.download_file,
                                url_headers_handler=lambda url: mockHeaders)
        (already_signed, newly_signed) = signer.process_format(item, format)
        self.assertEqual('https://cdn.door43.org/en/obs/v4/64kbps/en_obs_64kbps.zip.sig', format['signature'])
        self.assertNotIn('File is too large to sign https://cdn.door43.org/en/obs/v4/64kbps/en_obs_64kbps.zip', mock_logger._messages)
        self.assertFalse(already_signed)
        self.assertTrue(newly_signed)

    @unittest.skipIf(is_travis(), 'Skipping test_everything on Travis CI.')
    def test_manually_sign(self, mock_reporter):
        """
        This is used to manually sign large media files.
        You shouldn't actually run this test unless you want to use the signature
        :return:
        """
        return # This takes a long time so you don't usually want to do this
        mock_s3 = MockS3Handler()
        mock_db = MockDynamodbHandler()
        mock_logger = MockLogger()
        event = self.create_event()
        item = {
            'repo_name': 'repo_name',
            'commit_id': 'commitid'
        }
        quality = '720p'
        key = 'en/obs/v4/{0}/en_obs_{0}.zip'.format(quality)
        format = {
            "build_rules": [
                "signing.sign_given_url"
            ],
            "format": "",
            "modified": "",
            "signature": "",
            "size": 0,
            "url": "https://cdn.door43.org/{}".format(key)
        }

        pem_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), '../../functions/signing/uW-sk.enc')
        signer = Signer(pem_file)

        signing_handler = SigningHandler(event,
                                None,
                                logger=mock_logger,
                                s3_handler=mock_s3,
                                signer=signer,
                                dynamodb_handler=mock_db,
                                url_size_handler=lambda url: 1)
        (already_signed, newly_signed) = signing_handler.process_format(item, format)
        self.assertTrue(newly_signed)
        mock_s3.download_file('{}.sig'.format(key), os.path.expanduser('~/{}.sig'.format(os.path.basename(key))))