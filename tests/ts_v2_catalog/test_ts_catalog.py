import os
import codecs
import json
from general_tools.file_utils import load_json_object
from unittest import TestCase
from tools.mocks import MockS3Handler, MockDynamodbHandler

from functions.ts_v2_catalog.ts_v2_catalog_handler import TsV2CatalogHandler

class TestTsV2Catalog(TestCase):

    resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

    def setUp(self):
        self.latest_catalog = load_json_object(os.path.join(TestTsV2Catalog.resources_dir, "v3_catalog.json"))
        self.assertIsNotNone(self.latest_catalog)

    @staticmethod
    def readMockApi(path):
        """
        Rest a file from the mock api
        :param path: 
        :return: 
        """
        if(path.startswith('/')): path = path[1:]
        file_path = os.path.join(TestTsV2Catalog.resources_dir, 'ts_api', path.split('?')[0])
        if os.path.exists(file_path):
            return TestTsV2Catalog.read_file(file_path)
        else:
            raise Exception('Mock API path does not exist: {}'.format(file_path))

    @staticmethod
    def read_file(file_name, encoding='utf-8-sig'):
        with codecs.open(file_name, 'r', encoding=encoding) as f:
            return f.read()

    @staticmethod
    def ordered(obj):
        """
        Orders the values in an object
        :param obj: 
        :return: 
        """
        if isinstance(obj, dict):
            return sorted((k, TestTsV2Catalog.ordered(v)) for k, v in obj.items())
        if isinstance(obj, list):
            return sorted(TestTsV2Catalog.ordered(x) for x in obj)
        else:
            return obj

    def make_event(self):
        return {
            'stage-variables': {
                'cdn_bucket': '',
                'cdn_url': 'https://api.unfoldingword.org/ts/txt/2'
            },
            'catalog': self.latest_catalog
        }

    def assertObjectEqual(self, obj1, obj2):
        """
        Checks if two objects are equal after recursively sorting them
        :param obj1: 
        :param obj2: 
        :return: 
        """
        self.assertEqual(TestTsV2Catalog.ordered(obj1), TestTsV2Catalog.ordered(obj2))

    def assertS3EqualsApiJSON(self, mockS3, key):
        """
        Checks if a generated s3 file matches a file in the mock api
        :param mockS3: 
        :param key: 
        :return: 
        """
        self.assertIn(key, mockS3._uploads)
        s3_obj = json.loads(TestTsV2Catalog.read_file(mockS3._uploads[key]))

        expected_obj = json.loads(TestTsV2Catalog.readMockApi('/ts/txt/2/{}'.format(key)))
        self.assertObjectEqual(s3_obj, expected_obj)

    def test_convert_catalog(self):
        mockS3 = MockS3Handler('/ts/txt/2/')
        zips = {
            'en_ulb': os.path.join(TestTsV2Catalog.resources_dir, "en_ulb.zip")
        }
        mockDb = MockDynamodbHandler()
        mockDb._load_db(os.path.join(TestTsV2Catalog.resources_dir, 'db.json'))
        download_handler = lambda url, path, bundle_name: zips[bundle_name] if bundle_name in zips else ''
        converter = TsV2CatalogHandler(self.make_event(), mockS3, download_handler, mockDb)
        converter.convert_catalog()

        self.assertS3EqualsApiJSON(mockS3, 'catalog.json')
        self.assertS3EqualsApiJSON(mockS3, 'obs/languages.json')
        self.assertS3EqualsApiJSON(mockS3, '1ch/languages.json')
        self.assertS3EqualsApiJSON(mockS3, 'obs/en/resources.json')
        self.assertS3EqualsApiJSON(mockS3, '1ch/en/resources.json')
        self.assertS3EqualsApiJSON(mockS3, '1ch/en/ulb/source.json')