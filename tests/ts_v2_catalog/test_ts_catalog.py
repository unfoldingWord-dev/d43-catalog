import json
import os

from mock import patch
from unittest import TestCase
from libraries.tools.file_utils import load_json_object, read_file
from libraries.tools.mocks import MockS3Handler, MockAPI, MockDynamodbHandler, MockLogger
from libraries.lambda_handlers.ts_v2_catalog_handler import TsV2CatalogHandler
from libraries.tools.test_utils import assert_s3_equals_api_json


# This is here to test importing main

@patch('libraries.lambda_handlers.handler.ErrorReporter')
class TestTsV2Catalog(TestCase):

    resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

    def setUp(self):
        self.latest_catalog = load_json_object(os.path.join(TestTsV2Catalog.resources_dir, "v3_catalog.json"))
        self.assertIsNotNone(self.latest_catalog)

    def make_event(self):
        return {
            'stage-variables': {
                'cdn_bucket': 'cdn.door43.org',
                'cdn_url': 'https://cdn.door43.org',
                'from_email': '',
                'to_email': ''
            }
        }

    def test_inprogress(self, mock_reporter):
        mockV3Api = MockAPI(self.resources_dir, 'https://cdn.door43.org/')
        mockV2Api = MockAPI(os.path.join(self.resources_dir, 'ts_api'), 'https://test')
        mockS3 = MockS3Handler('ts_bucket')
        mockDb = MockDynamodbHandler()
        mockDb._load_db(os.path.join(TestTsV2Catalog.resources_dir, 'ready_inprogress_db.json'))
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
            'https://test-cdn.door43.org/en/tn/v6/tn.zip': 'en_tn.zip'
        }
        mock_get_url = lambda url, catch_exception: mockV3Api.get_url(urls[url], catch_exception)
        mock_download = lambda url, dest: mockV3Api.download_file(urls[url], dest)
        mockLog = MockLogger()
        event = self.make_event()
        converter = TsV2CatalogHandler(event=event,
                                       context=None,
                                       logger=mockLog,
                                       s3_handler=mockS3,
                                       dynamodb_handler=mockDb,
                                       url_handler=mock_get_url,
                                       download_handler=mock_download,
                                       url_exists_handler=lambda url: True)
        converter.run()

        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/catalog.json')
        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/obs/languages.json')
        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/obs/en/resources.json')
        self.assertNotIn('v2/ts/obs/en/obs/source.json', mockS3._recent_uploads)
        # assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/obs/en/obs/source.json')
        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/obs/en/notes.json')
        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/obs/en/questions.json')
        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/obs/en/tw_cat.json')

        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/1ch/languages.json')
        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/1ch/en/resources.json')
        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/1ch/en/ulb/v7/source.json')
        self.assertNotIn('v2/ts/1ch/en/notes.json', mockS3._recent_uploads)
        # assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/1ch/en/notes.json')
        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/1ch/en/questions.json')
        self.assertNotIn('v2/ts/1ch/en/tw_cat.json', mockS3._recent_uploads)
        # assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/1ch/en/tw_cat.json')

        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/bible/en/words.json')

        # validate urls in generate catalogs match the generated output paths
        root_url = '{}/'.format(event['stage-variables']['cdn_url'].rstrip('/'))
        catalog = json.loads(read_file(mockS3._recent_uploads['v2/ts/catalog.json']))
        url_err_msg = 'url in catalog does not match upload path: {}'
        for project in catalog:
            lang_catalog_path = project['lang_catalog'].replace(root_url, '').split('?')[0]
            self.assertIn(lang_catalog_path, mockS3._recent_uploads, url_err_msg.format(lang_catalog_path))
            lang_catalog = json.loads(read_file(mockS3._recent_uploads[lang_catalog_path]))
            for language in lang_catalog:
                res_catalog_path = language['res_catalog'].replace(root_url, '').split('?')[0]
                self.assertIn(res_catalog_path, mockS3._recent_uploads, url_err_msg.format(res_catalog_path))
                res_catalog = json.loads(read_file(mockS3._recent_uploads[res_catalog_path]))
                for resource in res_catalog:
                    questions_path = resource['checking_questions'].replace(root_url, '').split('?')[0]
                    # notes_path = resource['notes'].replace(root_url, '').split('?')[0]
                    # source_path = resource['source'].replace(root_url, '').split('?')[0]
                    terms_path = resource['terms'].replace(root_url, '').split('?')[0]
                    # terms_map_path = resource['tw_cat'].replace(root_url, '').split('?')[0]

                    if questions_path:
                        self.assertIn(questions_path, mockS3._recent_uploads, url_err_msg.format(questions_path))
                    # if notes_path:
                        # self.assertIn(notes_path, mockS3._uploads, url_err_msg.format(notes_path))
                    # if source_path:
                    #     self.assertIn(source_path, mockS3._uploads, url_err_msg.format(source_path))
                    if terms_path:
                        self.assertIn(terms_path, mockS3._recent_uploads, url_err_msg.format(terms_path))
                    # if terms_map_path:
                    #     self.assertIn(terms_map_path, mockS3._uploads, url_err_msg.format(terms_map_path))


    def test_convert_catalog(self, mock_reporter):
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
        mockLog = MockLogger()
        event = self.make_event()
        converter = TsV2CatalogHandler(event=event,
                                       context=None,
                                       logger=mockLog,
                                       s3_handler=mockS3,
                                       dynamodb_handler=mockDb,
                                       url_handler=mock_get_url,
                                       download_handler=mock_download,
                                       url_exists_handler=lambda url: True)
        converter.run()

        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/catalog.json')
        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/obs/languages.json')
        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/obs/en/resources.json')
        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/obs/en/obs/v4/source.json')
        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/obs/en/notes.json')
        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/obs/en/questions.json')
        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/obs/en/tw_cat.json')

        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/1ch/languages.json')
        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/1ch/en/resources.json')
        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/1ch/en/ulb/v7/source.json')
        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/1ch/en/notes.json')
        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/1ch/en/questions.json')
        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/1ch/en/tw_cat.json')

        assert_s3_equals_api_json(self, mockS3, mockV2Api, 'v2/ts/bible/en/words.json')

        self.assertIn('ts/txt/2/catalog.json', mockS3._recent_uploads)

        # validate urls in generate catalogs match the generated output paths
        root_url = '{}/'.format(event['stage-variables']['cdn_url'].rstrip('/'))
        catalog = json.loads(read_file(mockS3._recent_uploads['v2/ts/catalog.json']))
        url_err_msg = 'url in catalog does not match upload path: {}'
        for project in catalog:
            lang_catalog_path = project['lang_catalog'].replace(root_url, '').split('?')[0]
            self.assertIn(lang_catalog_path, mockS3._recent_uploads, url_err_msg.format(lang_catalog_path))
            lang_catalog = json.loads(read_file(mockS3._recent_uploads[lang_catalog_path]))
            for language in lang_catalog:
                res_catalog_path = language['res_catalog'].replace(root_url, '').split('?')[0]
                self.assertIn(res_catalog_path, mockS3._recent_uploads, url_err_msg.format(res_catalog_path))
                res_catalog = json.loads(read_file(mockS3._recent_uploads[res_catalog_path]))
                for resource in res_catalog:
                    questions_path = resource['checking_questions'].replace(root_url, '').split('?')[0]
                    notes_path = resource['notes'].replace(root_url, '').split('?')[0]
                    source_path = resource['source'].replace(root_url, '').split('?')[0]
                    terms_path = resource['terms'].replace(root_url, '').split('?')[0]
                    terms_map_path = resource['tw_cat'].replace(root_url, '').split('?')[0]

                    self.assertNotIn('door43.org', resource['chunks'])
                    if resource['slug'] != 'obs':
                        self.assertIn('api.unfoldingword.org', resource['chunks'])

                    if questions_path:
                        self.assertIn(questions_path, mockS3._recent_uploads, url_err_msg.format(questions_path))
                    if notes_path:
                        self.assertIn(notes_path, mockS3._recent_uploads, url_err_msg.format(notes_path))
                    if source_path:
                        self.assertIn(source_path, mockS3._recent_uploads, url_err_msg.format(source_path))
                    if terms_path:
                        self.assertIn(terms_path, mockS3._recent_uploads, url_err_msg.format(terms_path))
                    if terms_map_path:
                        self.assertIn(terms_map_path, mockS3._recent_uploads, url_err_msg.format(terms_map_path))

    def test_complete_status(self, mock_reporter):
        mockV3Api = MockAPI(self.resources_dir, 'https://cdn.door43.org/')
        mockS3 = MockS3Handler('ts_bucket')
        mockDb = MockDynamodbHandler()
        mockDb._load_db(os.path.join(TestTsV2Catalog.resources_dir, 'complete_db.json'))
        mockLog = MockLogger()
        mock_get_url = lambda url, catch_exception: mockV3Api.get_url(url, catch_exception)
        mock_download = lambda url, dest: mockV3Api.download_file(url, dest)

        event = self.make_event()
        converter = TsV2CatalogHandler(event=event,
                                       context=None,
                                       logger=mockLog,
                                       s3_handler=mockS3,
                                       dynamodb_handler=mockDb,
                                       url_handler=mock_get_url,
                                       download_handler=mock_download,
                                       url_exists_handler=lambda url: True)
        result = converter.run()
        self.assertTrue(result)
        self.assertEqual(0, len(mockS3._recent_uploads))
        self.assertIn('Catalog already generated', mockLog._messages)

    def test_missing_catalog(self, mock_reporter):
        mockV3Api = MockAPI(self.resources_dir, 'https://cdn.door43.org/')
        mockV3Api.add_host(self.resources_dir, 'https://api.door43.org/')
        mockS3 = MockS3Handler('ts_bucket')
        mockDb = MockDynamodbHandler()
        mockDb._load_db(os.path.join(TestTsV2Catalog.resources_dir, 'ready_new_db.json'))
        mockLog = MockLogger()
        mock_get_url = lambda url, catch_exception: mockV3Api.get_url(url, catch_exception)
        mock_download = lambda url, dest: mockV3Api.download_file(url, dest)

        event = self.make_event()
        converter = TsV2CatalogHandler(event=event,
                                       context=None,
                                       logger=mockLog,
                                       s3_handler=mockS3,
                                       dynamodb_handler=mockDb,
                                       url_handler=mock_get_url,
                                       download_handler=mock_download,
                                       url_exists_handler=lambda url: False)
        result = converter.run()
        self.assertFalse(result)
        self.assertIn('https://api.door43.org/v3/catalog.json does not exist', mockLog._messages)

    def test_broken_catalog(self, mock_reporter):
        mockV3Api = MockAPI(self.resources_dir, 'https://cdn.door43.org/')
        mockV3Api.add_host(os.path.join(self.resources_dir, 'broken_api'), 'https://api.door43.org/')
        mockS3 = MockS3Handler('ts_bucket')
        mockDb = MockDynamodbHandler()
        mockDb._load_db(os.path.join(TestTsV2Catalog.resources_dir, 'ready_new_db.json'))
        mockLog = MockLogger()
        mock_get_url = lambda url, catch_exception: mockV3Api.get_url(url, catch_exception)
        mock_download = lambda url, dest: mockV3Api.download_file(url, dest)

        event = self.make_event()
        converter = TsV2CatalogHandler(event=event,
                                       context=None,
                                       logger=mockLog,
                                       s3_handler=mockS3,
                                       dynamodb_handler=mockDb,
                                       url_handler=mock_get_url,
                                       download_handler=mock_download,
                                       url_exists_handler=lambda url: False)
        result = converter.run()
        self.assertFalse(result)
        self.assertIn('Failed to load the catalog json: No JSON object could be decoded', mockLog._messages)



    # @unittest.skipIf(is_travis(), 'Skipping test_everything on Travis CI.')
    # def test_everything(self):
    #     """
    #     This will run through a full catalog build using live data, though nothing will be uploaded to the server.
    #     :return:
    #     """
    #     mockS3 = MockS3Handler('ts_bucket')
    #     mockLogger = MockLogger()
    #     mockDb = MockDynamodbHandler()
    #     mockDb._load_db(os.path.join(TestTsV2Catalog.resources_dir, 'ready_new_db.json')) # you can also play with ready_processing_db.json
    #
    #     event = {
    #         'cdn_bucket': 'cdn.door43.org',
    #         'cdn_url': 'https://cdn.door43.org/',
    #         'catalog_url': 'https://api.door43.org/v3/catalog.json'
    #     }
    #     converter = TsV2CatalogHandler(event=event,
    #                                    context=None,
    #                                    logger=mockLogger,
    #                                    s3_handler=mockS3,
    #                                    dynamodb_handler=mockDb)
    #     converter.run()
    #
    #     db_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'out', 'db.json')
    #     mockDb._exportToFile(db_file)
    #     self.assertTrue(os.path.exists(db_file))
    #     print('done')