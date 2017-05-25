import os
import codecs
import json
from general_tools.file_utils import load_json_object
from unittest import TestCase

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

    def assertObjectEqual(self, obj1, obj2):
        """
        Checks if two objects are equal after recursively sorting them
        :param obj1: 
        :param obj2: 
        :return: 
        """
        self.assertEqual(TestTsV2Catalog.ordered(obj1), TestTsV2Catalog.ordered(obj2))

    def test_convert_catalog(self):
        converter = TsV2CatalogHandler(self.latest_catalog)
        catalog = converter.convert_catalog()
        expected_catalog = json.loads(TestTsV2Catalog.readMockApi('/ts/txt/2/catalog.json'))

        self.assertObjectEqual(catalog, expected_catalog)

        #TODO: test paths in catalog