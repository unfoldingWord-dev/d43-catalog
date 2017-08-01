import os
from tools.file_utils import load_json_object
from tools.mocks import MockS3Handler, MockAPI, MockDynamodbHandler, MockSigner
from unittest import TestCase
from tools.test_utils import assert_s3_equals_api_json
from functions.uw_v2_catalog import UwV2CatalogHandler

# This is here to test importing main
from functions.uw_v2_catalog import main


class TestUwV2Catalog(TestCase):

    resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

    def setUp(self):
        self.latest_catalog = load_json_object(os.path.join(TestUwV2Catalog.resources_dir, "v3_catalog.json"))
        self.v2_catalog = load_json_object(os.path.join(TestUwV2Catalog.resources_dir, "v2_catalog.json"))

    def _make_event(self):
        return {
            'cdn_bucket': 'cdn.door43.org',
            'cdn_url': 'https://cdn.door43.org/'
        }

    def test_status_missing(self):
        mockDB = MockDynamodbHandler()
        mockDB._load_db(os.path.join(TestUwV2Catalog.resources_dir, 'missing_db.json'))
        mockV3Api = MockAPI(os.path.join(self.resources_dir, 'v3_api'), 'https://api.door43.org/')
        mockS3 = MockS3Handler('uw_bucket')
        mockSigner = MockSigner()

        converter = UwV2CatalogHandler(event=self._make_event(),
                                       s3_handler=mockS3,
                                       dynamodb_handler=mockDB,
                                       url_handler=mockV3Api.get_url,
                                       download_handler=mockV3Api.download_file,
                                       signing_handler=mockSigner)
        result = converter._get_status()
        self.assertFalse(result)

    def test_status_not_ready(self):
        mockDB = MockDynamodbHandler()
        mockDB._load_db(os.path.join(TestUwV2Catalog.resources_dir, 'not_ready_db.json'))
        mockV3Api = MockAPI(os.path.join(self.resources_dir, 'v3_api'), 'https://api.door43.org/')
        mockS3 = MockS3Handler('uw_bucket')
        mockSigner = MockSigner()

        converter = UwV2CatalogHandler(event=self._make_event(),
                                       s3_handler=mockS3,
                                       dynamodb_handler=mockDB,
                                       url_handler=mockV3Api.get_url,
                                       download_handler=mockV3Api.download_file,
                                       signing_handler=mockSigner)
        result = converter._get_status()
        self.assertFalse(result)

    def test_status_ready_complete(self):
        mockDB = MockDynamodbHandler()
        mockDB._load_db(os.path.join(TestUwV2Catalog.resources_dir, 'ready_complete_db.json'))
        mockV3Api = MockAPI(os.path.join(self.resources_dir, 'v3_api'), 'https://api.door43.org/')
        mockS3 = MockS3Handler('uw_bucket')
        mockSigner = MockSigner()

        converter = UwV2CatalogHandler(event=self._make_event(),
                                       s3_handler=mockS3,
                                       dynamodb_handler=mockDB,
                                       url_handler=mockV3Api.get_url,
                                       download_handler=mockV3Api.download_file,
                                       signing_handler=mockSigner)
        (status, source_status) = converter._get_status()
        self.assertEqual('complete', source_status['state'])
        self.assertEqual('complete', status['state'])

    def test_status_ready_inprogress(self):
        mockDB = MockDynamodbHandler()
        mockDB._load_db(os.path.join(TestUwV2Catalog.resources_dir, 'ready_inprogress_db.json'))
        mockV3Api = MockAPI(os.path.join(self.resources_dir, 'v3_api'), 'https://api.door43.org/')
        mockS3 = MockS3Handler('uw_bucket')
        mockSigner = MockSigner()

        converter = UwV2CatalogHandler(event=self._make_event(),
                                       s3_handler=mockS3,
                                       dynamodb_handler=mockDB,
                                       url_handler=mockV3Api.get_url,
                                       download_handler=mockV3Api.download_file,
                                       signing_handler=mockSigner)
        (status, source_status) = converter._get_status()
        self.assertEqual('complete', source_status['state'])
        self.assertEqual('in-progress', status['state'])
        self.assertEqual(1, len(status['processed']))

    def test_status_ready_new_db(self):
        mockDB = MockDynamodbHandler()
        mockDB._load_db(os.path.join(TestUwV2Catalog.resources_dir, 'ready_new_db.json'))
        mockV3Api = MockAPI(os.path.join(self.resources_dir, 'v3_api'), 'https://api.door43.org/')
        mockS3 = MockS3Handler('uw_bucket')
        mockSigner = MockSigner()

        converter = UwV2CatalogHandler(event=self._make_event(),
                                       s3_handler=mockS3,
                                       dynamodb_handler=mockDB,
                                       url_handler=mockV3Api.get_url,
                                       download_handler=mockV3Api.download_file,
                                       signing_handler=mockSigner)
        (status, source_status) = converter._get_status()
        self.assertEqual('complete', source_status['state'])
        self.assertEqual('in-progress', status['state'])
        self.assertEqual(0, len(status['processed']))

    def test_status_outdated_complete_db(self):
        mockDB = MockDynamodbHandler()
        mockDB._load_db(os.path.join(TestUwV2Catalog.resources_dir, 'ready_outdated_complete_db.json'))
        mockV3Api = MockAPI(os.path.join(self.resources_dir, 'v3_api'), 'https://api.door43.org/')
        mockS3 = MockS3Handler('uw_bucket')
        mockSigner = MockSigner()

        converter = UwV2CatalogHandler(event=self._make_event(),
                                       s3_handler=mockS3,
                                       dynamodb_handler=mockDB,
                                       url_handler=mockV3Api.get_url,
                                       download_handler=mockV3Api.download_file,
                                       signing_handler=mockSigner)
        (status, source_status) = converter._get_status()
        self.assertEqual('complete', source_status['state'])
        self.assertEqual('in-progress', status['state'])
        self.assertEqual(0, len(status['processed']))

    def test_status_outdated_inprogress_db(self):
        mockDB = MockDynamodbHandler()
        mockDB._load_db(os.path.join(TestUwV2Catalog.resources_dir, 'ready_outdated_inprogress_db.json'))
        mockV3Api = MockAPI(os.path.join(self.resources_dir, 'v3_api'), 'https://api.door43.org/')
        mockS3 = MockS3Handler('uw_bucket')
        mockSigner = MockSigner()

        converter = UwV2CatalogHandler(event=self._make_event(),
                                       s3_handler=mockS3,
                                       dynamodb_handler=mockDB,
                                       url_handler=mockV3Api.get_url,
                                       download_handler=mockV3Api.download_file,
                                       signing_handler=mockSigner)
        (status, source_status) = converter._get_status()
        self.assertEqual('complete', source_status['state'])
        self.assertEqual('in-progress', status['state'])
        self.assertEqual(0, len(status['processed']))

    def test_create_v2_catalog(self):
        mockDB = MockDynamodbHandler()
        mockDB._load_db(os.path.join(TestUwV2Catalog.resources_dir, 'ready_new_db.json'))
        mockV3Api = MockAPI(os.path.join(self.resources_dir, 'v3_api'), 'https://api.door43.org/')
        mockV3Api.add_host(os.path.join(self.resources_dir, 'v3_cdn'), 'https://cdn.door43.org/')
        mockV2Api = MockAPI(os.path.join(self.resources_dir, 'v2_api'), 'https://test')
        mockS3 = MockS3Handler('uw_bucket')
        mockSigner = MockSigner()
        converter = UwV2CatalogHandler(event=self._make_event(),
                                       s3_handler=mockS3,
                                       dynamodb_handler=mockDB,
                                       url_handler=mockV3Api.get_url,
                                       download_handler=mockV3Api.download_file,
                                       signing_handler=mockSigner)
        converter.run()

        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/uw/catalog.json')
        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/uw/obs/en/obs/v4/source.json')
        self.assertIn('v2/uw/obs/en/obs/v4/source.json.sig', mockS3._recent_uploads)
        self.assertIn('uw/txt/2/catalog.json', mockS3._recent_uploads)