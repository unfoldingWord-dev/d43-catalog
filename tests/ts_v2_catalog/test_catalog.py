import os
from general_tools.file_utils import load_json_object
from unittest import TestCase

from functions.ts_v2_catalog.ts_v2_catalog_handler import TsV2CatalogHandler

class TestTsV2Catalog(TestCase):

    resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

    def setUp(self):
        self.latest_catalog = load_json_object(os.path.join(TestTsV2Catalog.resources_dir, "catalog.json"))
        self.v2_catalog = load_json_object(os.path.join(TestTsV2Catalog.resources_dir, "v2_catalog.json"))

    def test_convert_catalog(self):
        converter = TsV2CatalogHandler(self.latest_catalog)
        catalog = converter.convert_catalog()

        # TODO: validate catalog matches expected form