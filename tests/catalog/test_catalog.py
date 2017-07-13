from __future__ import unicode_literals, print_function
import os
import shutil
import tempfile
import copy
from unittest import TestCase
from d43_aws_tools import S3Handler
from tools.file_utils import load_json_object
from tools.consistency_checker import ConsistencyChecker
from tools.mocks import MockAPI

from functions.catalog.catalog_handler import CatalogHandler

class TestCatalog(TestCase):

    resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

    class MockLogger(object):

        @staticmethod
        def warning(message):
            print('WARNING: {}'.format(message))

    class MockS3Handler(object):
        temp_dir = ''

        def __init__(self, bucket_name):
            self.bucket_name = bucket_name

        @staticmethod
        def download_file(key, local_file):
            shutil.copy(key, local_file)

        @staticmethod
        def upload_file(path, key, cache_time=1):
            out_path = os.path.join(TestCatalog.MockS3Handler.temp_dir, key)
            parent_dir = os.path.dirname(out_path)
            if not os.path.isdir(parent_dir):
                os.makedirs(parent_dir)

            shutil.copy(path, out_path)

    class MockChecker(ConsistencyChecker):

        @staticmethod
        def url_exists(url):
            return True

    class MockDynamodbHandler(object):
        tables_file = 'valid_db.json'
        commit_id = ''

        def __init__(self, table_name):
            self.table_name = table_name
            self.table = self._get_table(table_name)

        def _get_table(self, table_name):
            tables = load_json_object(os.path.join(TestCatalog.resources_dir, self.tables_file))
            return tables[table_name]

        # noinspection PyUnusedLocal
        def insert_item(self, data):
            self.table.append(data)
            return len(self.table) - 1

        # noinspection PyUnusedLocal
        def get_item(self, record_keys):
            try:
                return copy.deepcopy(self.table[record_keys['id']])
            except Exception:
                return None

        # noinspection PyUnusedLocal
        def update_item(self, record_keys, row):
            try:
                self.table[record_keys['id']].update(row)
            except Exception:
                return False
            return True

        # noinspection PyUnusedLocal
        def query_items(self):
            return list(self.table)

    class MockSESHandler(object):
        pass

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix='unitTest_')
        self.MockS3Handler.temp_dir = self.temp_dir
        self.s3keys = []

    def tearDown(self):
        # clean up local temp files
        if os.path.isdir(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

        # clean up temp files on S3
        if len(self.s3keys) > 0:
            s3_handler = S3Handler('test-cdn.door43.org')
            for s3key in self.s3keys:
                s3_handler.delete_file(s3key)

    @staticmethod
    def create_event():

        event = {
            'Records': [],
            'api_url': 'my-api',
            'api_bucket': 'my-bucket',
            'to_email': 'me@example.com',
            'from_email': 'me@example.com',
            'cdn_bucket': 'cdn-bucket',
            'cdn_url': 'cdn-url'
        }

        return event

    @staticmethod
    def create_s3_record(bucket_name, object_key):

        record = {
            's3': {
                'bucket': {'name': bucket_name},
                'object': {'key': object_key}
            }
        }

        return record

    def test_catalog_valid_obs_content(self):
        # mockV3CDN = MockAPI(self.resources_dir, 'https://cdn.door43.org')
        self.MockDynamodbHandler.tables_file = 'valid_db.json'
        event = self.create_event()
        # urls = [
        #     'https://cdn.door43.org/en/obs/v4/obs_obs.zip',
        #     'https://cdn.door43.org/en/obs/v4/obs_obs.zip.sig'
        # ]
        # mock_get_url = lambda url, catch_exception: mockV3CDN.get_url(url, catch_exception)
        # mock_url_exists = lambda url: url in urls
        catalog = CatalogHandler(event, self.MockS3Handler, self.MockDynamodbHandler, self.MockSESHandler)
        response = catalog.handle_catalog()

        self.assertTrue(response['success'])
        self.assertFalse(response['incomplete'])
        self.assertIn('Uploaded new catalog', response['message'])
        self.assertEqual(1, len(response['catalog']['languages']))
        self.assertEqual(1, len(response['catalog']['languages'][0]['resources']))
        self.assertNotIn('formats', response['catalog']['languages'][0]['resources'][0])
        self.assertEqual(1, len(response['catalog']['languages'][0]['resources'][0]['projects']))
        self.assertEqual(1, len(response['catalog']['languages'][0]['resources'][0]['projects'][0]['formats']))
        self.assertIn('checking', response['catalog']['languages'][0]['resources'][0])
        self.assertIn('comment', response['catalog']['languages'][0]['resources'][0])

    def test_catalog_no_sig_content(self):
        self.MockDynamodbHandler.tables_file = 'no_sig_db.json'
        event = self.create_event()
        catalog = CatalogHandler(event, self.MockS3Handler, self.MockDynamodbHandler, self.MockSESHandler)
        response = catalog.handle_catalog()

        self.assertFalse(response['success'])
        self.assertIn('has not been signed yet', response['message'])

    def test_catalog_mixed_content(self):
        """
        Tests what happens when some content is valid and some is not
        :return: 
        """
        self.MockDynamodbHandler.tables_file = 'mixed_db.json'
        event = self.create_event()
        catalog = CatalogHandler(event, self.MockS3Handler, self.MockDynamodbHandler, self.MockSESHandler)
        response = catalog.handle_catalog()

        self.assertTrue(response['success'])
        self.assertIn('Uploaded new catalog', response['message'])
        self.assertTrue(response['incomplete'])
        self.assertEqual(1, len(response['catalog']['languages']))
        self.assertEqual(1, len(response['catalog']['languages'][0]['resources']))

    def test_catalog_invalid_format(self):
        self.MockDynamodbHandler.tables_file = 'invalid_format_db.json'
        event = self.create_event()
        catalog = CatalogHandler(event, self.MockS3Handler, self.MockDynamodbHandler, self.MockSESHandler)
        response = catalog.handle_catalog()

        # we expect the invalid resource to be skipped
        self.assertTrue(response['success'])
        self.assertIn('Uploaded new catalog', response['message'])
        self.assertTrue(response['incomplete'])
        self.assertEqual(1, len(response['catalog']['languages']))
        self.assertEqual(1, len(response['catalog']['languages'][0]['resources']))


    def test_catalog_invalid_manifest(self):
        self.MockDynamodbHandler.tables_file = 'invalid_manifest_db.json'
        event = self.create_event()
        catalog = CatalogHandler(event, self.MockS3Handler, self.MockDynamodbHandler, self.MockSESHandler)
        response = catalog.handle_catalog()

        self.assertFalse(response['success'])
        self.assertIn('manifest missing key', response['message'])
        self.assertIsNone(response['catalog'])

    def test_catalog_empty_formats(self):
        # tests missing status and empty formats
        self.MockDynamodbHandler.tables_file = 'empty_formats_db.json'
        event = self.create_event()
        catalog = CatalogHandler(event, self.MockS3Handler, self.MockDynamodbHandler, self.MockSESHandler)
        response = catalog.handle_catalog()

        self.assertFalse(response['success'])
        self.assertIn('There were no formats to process', response['message'])
        self.assertFalse(response['incomplete'])

    def test_catalog_ulb_versification(self):
        self.MockDynamodbHandler.tables_file = 'ulb_versification_db.json'
        event = self.create_event()
        handler = CatalogHandler(event, self.MockS3Handler, self.MockDynamodbHandler, self.MockSESHandler, self.MockChecker)
        response = handler.handle_catalog()
        catalog = response['catalog']

        self.assertIsNotNone(catalog)
        self.assertIn('projects', catalog['languages'][0]['resources'][0])
        self.assertTrue(len(catalog['languages'][0]['resources'][0]['projects']) > 0)
        self.assertIn('chunks_url', catalog['languages'][0]['resources'][0]['projects'][0])

    def test_catalog_versification_ulb(self):
        self.MockDynamodbHandler.tables_file = 'versification_ulb_db.json'
        event = self.create_event()
        handler = CatalogHandler(event, self.MockS3Handler, self.MockDynamodbHandler, self.MockSESHandler, self.MockChecker)
        response = handler.handle_catalog()
        catalog = response['catalog']

        self.assertIsNotNone(catalog)
        self.assertIn('projects', catalog['languages'][0]['resources'][0])
        self.assertTrue(len(catalog['languages'][0]['resources'][0]['projects']) > 0)
        self.assertIn('chunks_url', catalog['languages'][0]['resources'][0]['projects'][0])

    def test_catalog_versification_tq(self):
        self.MockDynamodbHandler.tables_file = 'versification_tq_db.json'
        event = self.create_event()
        handler = CatalogHandler(event, self.MockS3Handler, self.MockDynamodbHandler, self.MockSESHandler, self.MockChecker)
        response = handler.handle_catalog()
        catalog = response['catalog']

        self.assertIsNotNone(catalog)
        self.assertIn('projects', catalog['languages'][0]['resources'][0])
        self.assertTrue(len(catalog['languages'][0]['resources'][0]['projects']) > 0)
        self.assertNotIn('chunks_url', catalog['languages'][0]['resources'][0]['projects'][0])

    def test_catalog_localization(self):
        self.MockDynamodbHandler.tables_file = 'localization_db.json'
        event = self.create_event()
        handler = CatalogHandler(event, self.MockS3Handler, self.MockDynamodbHandler, self.MockSESHandler,
                                 self.MockChecker)
        response = handler.handle_catalog()
        catalog = response['catalog']

        self.assertIn('category_labels', catalog['languages'][0])
        self.assertIn('versification_labels', catalog['languages'][0])
        self.assertIn('check_labels', catalog['languages'][0])
        self.assertNotIn('language', catalog['languages'][0])

    def test_catalog_complex(self):
        """
        Tests multiple repositories sharing a single resource
        and other complex situations
        :return: 
        """
        self.MockDynamodbHandler.tables_file = 'complex_db.json'
        event = self.create_event()
        handler = CatalogHandler(event, self.MockS3Handler, self.MockDynamodbHandler, self.MockSESHandler)
        response = handler.handle_catalog()
        catalog = response['catalog']

        # TODO: we need to run tests to ensure complex data is handled correctly.
        # e.g. one repo provides resource formats and another provide a project format for that resource
        # two repos with the same resource provide formats at the same level (conflict resource formats, conflicting projects formats)
        #
