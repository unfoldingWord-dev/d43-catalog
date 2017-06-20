import os
import json
from tools.file_utils import load_json_object
from unittest import TestCase

from functions.uw_v2_catalog.uw_v2_catalog_handler import UwV2CatalogHandler

class TestUwV2Catalog(TestCase):

    resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

    def setUp(self):
        self.latest_catalog = load_json_object(os.path.join(TestUwV2Catalog.resources_dir, "v3_catalog.json"))
        self.v2_catalog = load_json_object(os.path.join(TestUwV2Catalog.resources_dir, "v2_catalog.json"))

    def assertObjectEqual(self, obj1, obj2):
        """
        Checks if two objects are equal after recursively sorting them
        :param obj1:
        :param obj2:
        :return:
        """
        self.assertEqual(TestUwV2Catalog.ordered(obj1), TestUwV2Catalog.ordered(obj2))

    @staticmethod
    def ordered(obj):
        """
        Orders the values in an object
        :param obj:
        :return:
        """
        if isinstance(obj, dict):
            return sorted((k, TestUwV2Catalog.ordered(v)) for k, v in obj.items())
        if isinstance(obj, list):
            return sorted(TestUwV2Catalog.ordered(x) for x in obj)
        else:
            return obj

    def test_create_v2_catalog(self):
        converter = UwV2CatalogHandler(self.latest_catalog)
        catalog = converter.convert_catalog()

        # makes reading differences in the logs easier
        catalog_str = json.dumps(catalog)

        self.assertIsNotNone(catalog)
        self.assertNotEqual(self.latest_catalog, catalog)
        self.assertObjectEqual(self.v2_catalog, json.loads(catalog_str))