import os
from tools.file_utils import load_json_object
from tools.mocks import MockS3Handler, MockAPI
from unittest import TestCase
from tools.test_utils import assert_s3_equals_api_json

from functions.uw_v2_catalog.uw_v2_catalog_handler import UwV2CatalogHandler

class TestUwV2Catalog(TestCase):

    resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

    def setUp(self):
        self.latest_catalog = load_json_object(os.path.join(TestUwV2Catalog.resources_dir, "v3_catalog.json"))
        self.v2_catalog = load_json_object(os.path.join(TestUwV2Catalog.resources_dir, "v2_catalog.json"))


    # TODO: re-enable this once we get the timezone normalization working on travis.
    # def test_create_v2_catalog(self):
    #     mockV3Api = MockAPI(os.path.join(self.resources_dir, 'v3_api'), 'https://api.door43.org/')
    #     mockV2Api = MockAPI(os.path.join(self.resources_dir, 'v2_api'), 'https://test')
    #     mockS3 = MockS3Handler('uw_bucket')
    #     mock_get_url = lambda url, catch_exception: mockV3Api.get_url(url, catch_exception)
    #     mock_download = lambda url, dest: mockV3Api.download_file(url, dest)
    #     event = {
    #         'stage-variables': {
    #             'cdn_bucket': '',
    #             'cdn_url': 'https://cdn.door43.org/',
    #             'catalog_url': 'https://api.door43.org/v3/catalog.json'
    #         }
    #     }
    #     converter = UwV2CatalogHandler(event, mockS3, mock_get_url, mock_download)
    #     catalog = converter.convert_catalog()
    #
    #     assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/uw/catalog.json')