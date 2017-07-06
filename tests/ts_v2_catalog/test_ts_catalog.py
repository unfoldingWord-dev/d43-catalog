import os
import json
from tools.file_utils import load_json_object, read_file
from unittest import TestCase
from tools.mocks import MockS3Handler, MockAPI, MockDynamodbHandler
from tools.test_utils import assert_s3_equals_api_json

from functions.ts_v2_catalog.ts_v2_catalog_handler import TsV2CatalogHandler

class TestTsV2Catalog(TestCase):

    resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

    def setUp(self):
        self.latest_catalog = load_json_object(os.path.join(TestTsV2Catalog.resources_dir, "v3_catalog.json"))
        self.assertIsNotNone(self.latest_catalog)

    def make_event(self):
        return {
            'stage-variables': {
                'cdn_bucket': '',
                'cdn_url': 'https://api.unfoldingword.org/',
                'catalog_url': 'https://api.door43.org/v3/catalog.json'
            }
        }

    def test_convert_catalog(self):
        mockV3Api = MockAPI(self.resources_dir, 'https://cdn.door43.org/')
        mockV2Api = MockAPI(os.path.join(self.resources_dir, 'ts_api'), 'https://test')
        mockS3 = MockS3Handler('ts_bucket')
        mockDb = MockDynamodbHandler()
        mockDb._load_db(os.path.join(TestTsV2Catalog.resources_dir, 'ready_new_db.json'))
        # TRICKY: map the v3 test files to urls so we can have a flat list of test files
        urls = {
            'https://test-cdn.door43.org/en/ulb/v7/ulb.zip': "en_ulb.zip",
            'https://test-cdn.door43.org/en/udb/v7/udb.zip': "en_udb.zip",
            'https://api.door43.org/v3/catalog.json': "v3_catalog.json",
            'https://test-cdn.door43.org/en/obs/v4/obs.zip': "en_obs.zip",
            'https://test-cdn.door43.org/en/tw/v5/tw.zip': 'en_tw.zip',
            'https://test-cdn.door43.org/en/tn/v4/obs-tn.zip': 'en_obs_tn.zip',
            'https://test-cdn.door43.org/en/tq/v4/obs-tq.zip': 'en_obs_tq.zip',
            'https://test-cdn.door43.org/en/tq/v6/tq.zip': 'en_tq.zip',
            'https://test-cdn.door43.org/en/tn/v6/tn.zip':  'en_tn.zip'
        }
        mock_get_url = lambda url, catch_exception: mockV3Api.get_url(urls[url], catch_exception)
        mock_download = lambda url, dest: mockV3Api.download_file(urls[url], dest)

        event = self.make_event()
        converter = TsV2CatalogHandler(event, mockS3, mockDb, mock_get_url, mock_download)
        converter.run()

        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/catalog.json')
        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/obs/languages.json')
        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/obs/en/resources.json')
        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/obs/en/obs/source.json')
        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/obs/en/notes.json')
        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/obs/en/questions.json')
        # assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/obs/en/tw_cat.json')

        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/1ch/languages.json')
        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/1ch/en/resources.json')
        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/1ch/en/ulb/source.json')
        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/1ch/en/notes.json')
        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/1ch/en/questions.json')
        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/1ch/en/tw_cat.json')

        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/bible/en/words.json')

        # validate urls in generate catalogs match the generated output paths
        root_url = '{}/'.format(event['stage-variables']['cdn_url'].rstrip('/'))
        catalog = json.loads(read_file(mockS3._uploads['v2/ts/catalog.json']))
        url_err_msg = 'url in catalog does not match upload path: {}'
        for project in catalog:
            lang_catalog_path = project['lang_catalog'].replace(root_url, '').split('?')[0]
            self.assertIn(lang_catalog_path, mockS3._uploads, url_err_msg.format(lang_catalog_path))
            lang_catalog = json.loads(read_file(mockS3._uploads[lang_catalog_path]))
            for language in lang_catalog:
                res_catalog_path = language['res_catalog'].replace(root_url, '').split('?')[0]
                self.assertIn(res_catalog_path, mockS3._uploads, url_err_msg.format(res_catalog_path))
                res_catalog = json.loads(read_file(mockS3._uploads[res_catalog_path]))
                for resource in res_catalog:
                    questions_path = resource['checking_questions'].replace(root_url, '').split('?')[0]
                    notes_path = resource['notes'].replace(root_url, '').split('?')[0]
                    source_path = resource['source'].replace(root_url, '').split('?')[0]
                    terms_path = resource['terms'].replace(root_url, '').split('?')[0]
                    terms_map_path = resource['tw_cat'].replace(root_url, '').split('?')[0]

                    if questions_path:
                        self.assertIn(questions_path, mockS3._uploads, url_err_msg.format(questions_path))
                    if notes_path:
                        self.assertIn(notes_path, mockS3._uploads, url_err_msg.format(notes_path))
                    if source_path:
                        self.assertIn(source_path, mockS3._uploads, url_err_msg.format(source_path))
                    if terms_path:
                        self.assertIn(terms_path, mockS3._uploads, url_err_msg.format(terms_path))
                    if terms_map_path:
                        self.assertIn(terms_map_path, mockS3._uploads, url_err_msg.format(terms_map_path))
