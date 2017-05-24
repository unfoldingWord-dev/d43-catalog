import os
from general_tools.file_utils import load_json_object
from unittest import TestCase

from functions.uw_v2_catalog.uw_v2_catalog_handler import UwV2CatalogHandler

class TestV2Catalog(TestCase):

    resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

    def setUp(self):
        self.latest_catalog = load_json_object(os.path.join(TestV2Catalog.resources_dir, "catalog.json"))
        self.v2_catalog = load_json_object(os.path.join(TestV2Catalog.resources_dir, "v2_catalog.json"))

    def test_convert_catalog(self):
        converter = UwV2CatalogHandler(self.latest_catalog)
        catalog = converter.convert_catalog()

        # TODO: validate catalog matches expected form