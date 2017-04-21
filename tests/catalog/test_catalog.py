from __future__ import unicode_literals, print_function
import codecs
import json
import os
import shutil
import tempfile
import unittest
import uuid
from unittest import TestCase
from datetime import datetime
from aws_tools.dynamodb_handler import DynamoDBHandler
from aws_tools.s3_handler import S3Handler
from general_tools.file_utils import load_json_object

from functions.catalog.catalog_handler import CatalogHandler
from functions.signing.aws_decrypt import decrypt_file
from functions.signing.signing import Signing

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

    class MockDynamodbHandler(object):

        commit_id = ''

        def __init__(self, table_name):
            self.table_name = table_name

        def _get_table(self, table_name):
            tables = load_json_object(os.path.join(TestCatalog.resources_dir, 'dynamodb_tables.json'))
            return tables[table_name]

        # noinspection PyUnusedLocal
        def insert_item(self, data):
            pass

        # noinspection PyUnusedLocal
        def get_item(self, record_keys):
            table = self._get_table(self.table_name)
            return_val = {}#load_json_object(os.path.join(TestCatalog.resources_dir, 'dynamodb_tables.json'))
            if TestCatalog.MockDynamodbHandler.commit_id:
                return_val['commit_id'] = TestCatalog.MockDynamodbHandler.commit_id
            return return_val

        # noinspection PyUnusedLocal
        @staticmethod
        def update_item(record_keys, row):
            return True

        # noinspection PyUnusedLocal
        def query_items(self):
            return self._get_table(self.table_name)

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
            'api_bucket': 'my-bucket',
            'to_email': 'me@example.com',
            'from_email': 'me@example.com',

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

    def test_catalog_valid_content(self):

        event = self.create_event()
        catalog = CatalogHandler(event, self.MockS3Handler, self.MockDynamodbHandler, self.MockSESHandler)
        response = catalog.handle_catalog()

        self.assertTrue(response['success'])
        # TODO: validate complete catalog is built

    def test_catalog_invalid_format(self):

        event = self.create_event()
        catalog = CatalogHandler(event, self.MockS3Handler, self.MockDynamodbHandler, self.MockSESHandler)
        response = catalog.handle_catalog()

        self.assertTrue(response['success'])

        # TODO: validate everything but invalid format is built

    def test_catalog_invalid_resource(self):
        event = self.create_event()
        catalog = CatalogHandler(event, self.MockS3Handler, self.MockDynamodbHandler, self.MockSESHandler)
        response = catalog.handle_catalog()

        self.assertTrue(response['success'])

        # TODO: validate everything but invalid resource is built

    def test_catalog_invalid_language(self):

        event = self.create_event()
        catalog = CatalogHandler(event, self.MockS3Handler, self.MockDynamodbHandler, self.MockSESHandler)
        response = catalog.handle_catalog()

        self.assertTrue(response['success'])

        # TODO: validate everything but invalid language is built

    def test_catalog_empty_resource(self):

        event = self.create_event()
        catalog = CatalogHandler(event, self.MockS3Handler, self.MockDynamodbHandler, self.MockSESHandler)
        response = catalog.handle_catalog()

        self.assertTrue(response['success'])
        # we'll need another db file for this

        # TODO: validate everything but empty resource is built

    def test_catalog_empty_language(self):

        event = self.create_event()
        catalog = CatalogHandler(event, self.MockS3Handler, self.MockDynamodbHandler, self.MockSESHandler)
        response = catalog.handle_catalog()

        self.assertTrue(response['success'])

        # TODO: validate everything but empty language is built
        # we'll need another db file for this