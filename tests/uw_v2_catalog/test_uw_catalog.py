# coding=utf-8

from __future__ import print_function, unicode_literals
import os
from unittest import TestCase

from libraries.tools.file_utils import load_json_object
from libraries.tools.mocks import MockS3Handler, MockAPI, MockDynamodbHandler, MockSigner, MockLogger
from mock import patch
from libraries.lambda_handlers.uw_v2_catalog_handler import UwV2CatalogHandler
from libraries.tools.test_utils import assert_s3_equals_api_json, assert_s3_equals_api_text


# This is here to test importing main

@patch('libraries.lambda_handlers.handler.ErrorReporter')
class TestUwV2Catalog(TestCase):

    resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

    def setUp(self):
        self.latest_catalog = load_json_object(os.path.join(TestUwV2Catalog.resources_dir, "v3_catalog.json"))
        self.v2_catalog = load_json_object(os.path.join(TestUwV2Catalog.resources_dir, "v2_catalog.json"))

    def _make_event(self):
        return {
            'stage-variables': {
                'cdn_bucket': 'cdn.door43.org',
                'cdn_url': 'https://cdn.door43.org/',
                'from_email': '',
                'to_email': ''
            }
        }

    def test_status_missing(self, mock_reporter):
        mockDB = MockDynamodbHandler()
        mockDB._load_db(os.path.join(TestUwV2Catalog.resources_dir, 'missing_db.json'))
        mockV3Api = MockAPI(os.path.join(self.resources_dir, 'v3_api'), 'https://api.door43.org/')
        mockS3 = MockS3Handler('uw_bucket')
        mockSigner = MockSigner()
        mockLogger = MockLogger()

        converter = UwV2CatalogHandler(event=self._make_event(),
                                       context=None,
                                       logger=mockLogger,
                                       s3_handler=mockS3,
                                       dynamodb_handler=mockDB,
                                       url_handler=mockV3Api.get_url,
                                       download_handler=mockV3Api.download_file,
                                       signing_handler=mockSigner)
        result = converter._get_status()
        self.assertFalse(result)

    def test_status_not_ready(self, mock_reporter):
        mockDB = MockDynamodbHandler()
        mockDB._load_db(os.path.join(TestUwV2Catalog.resources_dir, 'not_ready_db.json'))
        mockV3Api = MockAPI(os.path.join(self.resources_dir, 'v3_api'), 'https://api.door43.org/')
        mockS3 = MockS3Handler('uw_bucket')
        mockSigner = MockSigner()
        mockLogger = MockLogger()

        converter = UwV2CatalogHandler(event=self._make_event(),
                                       context=None,
                                       logger=mockLogger,
                                       s3_handler=mockS3,
                                       dynamodb_handler=mockDB,
                                       url_handler=mockV3Api.get_url,
                                       download_handler=mockV3Api.download_file,
                                       signing_handler=mockSigner)
        result = converter._get_status()
        self.assertFalse(result)

    def test_status_ready_complete(self, mock_reporter):
        mockDB = MockDynamodbHandler()
        mockDB._load_db(os.path.join(TestUwV2Catalog.resources_dir, 'ready_complete_db.json'))
        mockV3Api = MockAPI(os.path.join(self.resources_dir, 'v3_api'), 'https://api.door43.org/')
        mockS3 = MockS3Handler('uw_bucket')
        mockSigner = MockSigner()
        mockLogger = MockLogger()

        converter = UwV2CatalogHandler(event=self._make_event(),
                                       context=None,
                                       logger=mockLogger,
                                       s3_handler=mockS3,
                                       dynamodb_handler=mockDB,
                                       url_handler=mockV3Api.get_url,
                                       download_handler=mockV3Api.download_file,
                                       signing_handler=mockSigner)
        (status, source_status) = converter._get_status()
        self.assertEqual('complete', source_status['state'])
        self.assertEqual('complete', status['state'])

    def test_status_ready_inprogress(self, mock_reporter):
        mockDB = MockDynamodbHandler()
        mockDB._load_db(os.path.join(TestUwV2Catalog.resources_dir, 'ready_inprogress_db.json'))
        mockV3Api = MockAPI(os.path.join(self.resources_dir, 'v3_api'), 'https://api.door43.org/')
        mockS3 = MockS3Handler('uw_bucket')
        mockSigner = MockSigner()
        mockLogger = MockLogger()

        converter = UwV2CatalogHandler(event=self._make_event(),
                                       context=None,
                                       logger=mockLogger,
                                       s3_handler=mockS3,
                                       dynamodb_handler=mockDB,
                                       url_handler=mockV3Api.get_url,
                                       download_handler=mockV3Api.download_file,
                                       signing_handler=mockSigner)
        (status, source_status) = converter._get_status()
        self.assertEqual('complete', source_status['state'])
        self.assertEqual('in-progress', status['state'])
        self.assertEqual(1, len(status['processed']))

    def test_status_ready_new_db(self, mock_reporter):
        mockDB = MockDynamodbHandler()
        mockDB._load_db(os.path.join(TestUwV2Catalog.resources_dir, 'ready_new_db.json'))
        mockV3Api = MockAPI(os.path.join(self.resources_dir, 'v3_api'), 'https://api.door43.org/')
        mockS3 = MockS3Handler('uw_bucket')
        mockSigner = MockSigner()
        mockLogger = MockLogger()

        converter = UwV2CatalogHandler(event=self._make_event(),
                                       context=None,
                                       logger=mockLogger,
                                       s3_handler=mockS3,
                                       dynamodb_handler=mockDB,
                                       url_handler=mockV3Api.get_url,
                                       download_handler=mockV3Api.download_file,
                                       signing_handler=mockSigner)
        (status, source_status) = converter._get_status()
        self.assertEqual('complete', source_status['state'])
        self.assertEqual('in-progress', status['state'])
        self.assertEqual(0, len(status['processed']))

    def test_status_outdated_complete_db(self, mock_reporter):
        mockDB = MockDynamodbHandler()
        mockDB._load_db(os.path.join(TestUwV2Catalog.resources_dir, 'ready_outdated_complete_db.json'))
        mockV3Api = MockAPI(os.path.join(self.resources_dir, 'v3_api'), 'https://api.door43.org/')
        mockS3 = MockS3Handler('uw_bucket')
        mockSigner = MockSigner()
        mockLogger = MockLogger()

        converter = UwV2CatalogHandler(event=self._make_event(),
                                       context=None,
                                       logger=mockLogger,
                                       s3_handler=mockS3,
                                       dynamodb_handler=mockDB,
                                       url_handler=mockV3Api.get_url,
                                       download_handler=mockV3Api.download_file,
                                       signing_handler=mockSigner)
        (status, source_status) = converter._get_status()
        self.assertEqual('complete', source_status['state'])
        self.assertEqual('in-progress', status['state'])
        self.assertEqual(0, len(status['processed']))

    def test_status_outdated_inprogress_db(self, mock_reporter):
        mockDB = MockDynamodbHandler()
        mockDB._load_db(os.path.join(TestUwV2Catalog.resources_dir, 'ready_outdated_inprogress_db.json'))
        mockV3Api = MockAPI(os.path.join(self.resources_dir, 'v3_api'), 'https://api.door43.org/')
        mockS3 = MockS3Handler('uw_bucket')
        mockSigner = MockSigner()
        mockLogger = MockLogger()

        converter = UwV2CatalogHandler(event=self._make_event(),
                                       context=None,
                                       logger=mockLogger,
                                       s3_handler=mockS3,
                                       dynamodb_handler=mockDB,
                                       url_handler=mockV3Api.get_url,
                                       download_handler=mockV3Api.download_file,
                                       signing_handler=mockSigner)
        (status, source_status) = converter._get_status()
        self.assertEqual('complete', source_status['state'])
        self.assertEqual('in-progress', status['state'])
        self.assertEqual(0, len(status['processed']))

    def test_create_v2_catalog(self, mock_reporter):
        mockDB = MockDynamodbHandler()
        mockDB._load_db(os.path.join(TestUwV2Catalog.resources_dir, 'ready_new_db.json'))
        mockV3Api = MockAPI(os.path.join(self.resources_dir, 'v3_api'), 'https://api.door43.org/')
        mockV3Api.add_host(os.path.join(self.resources_dir, 'v3_cdn'), 'https://cdn.door43.org/')
        mockV2Api = MockAPI(os.path.join(self.resources_dir, 'v2_api'), 'https://test')
        mockS3 = MockS3Handler('uw_bucket')
        mockSigner = MockSigner()
        mockLogger = MockLogger()

        converter = UwV2CatalogHandler(event=self._make_event(),
                                       context=None,
                                       logger=mockLogger,
                                       s3_handler=mockS3,
                                       dynamodb_handler=mockDB,
                                       url_handler=mockV3Api.get_url,
                                       download_handler=mockV3Api.download_file,
                                       signing_handler=mockSigner)
        converter.run()

        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/uw/catalog.json')
        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/uw/obs/en/obs/v4/source.json')
        assert_s3_equals_api_text(self, mockS3, mockV2Api, 'v2/uw/gen/en/udb/v7/gen.usfm')
        assert_s3_equals_api_text(self, mockS3, mockV2Api, 'v2/uw/1ch/en/ulb/v7/1ch.usfm')
        self.assertIn('v2/uw/obs/en/obs/v4/source.json.sig', mockS3._recent_uploads)
        self.assertIn('uw/txt/2/catalog.json', mockS3._recent_uploads)
        self.assertIn(
            'en_udb_1ch: media format "https://cdn.door43.org/en/udb/v9/1ch.pdf" does not match source version "7" and will be excluded.',
            mockLogger._messages)
        self.assertIn(
            'en_obs_obs: media format "https://cdn.door43.org/en/obs/v999/129kbps/en_obs_129kbps.zip" does not match source version "4" and will be excluded.',
            mockLogger._messages)