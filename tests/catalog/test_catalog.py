from __future__ import unicode_literals, print_function

import os
from mock import patch
from unittest import TestCase

from libraries.tools.mocks import MockChecker, MockDynamodbHandler, MockS3Handler, MockSESHandler, MockAPI, MockLogger

from libraries.lambda_handlers.catalog_handler import CatalogHandler
from libraries.tools.test_utils import assert_object_equals_file, assert_object_equals


# This is here to test importing main
@patch('libraries.lambda_handlers.handler.Handler.report_error')
class TestCatalog(TestCase):

    resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

    @staticmethod
    def create_event():

        event = {
            'Records': [],
            'stage-variables': {
                'api_url': 'my-api',
                'api_bucket': 'my-bucket',
                'to_email': 'me@example.com',
                'from_email': 'me@example.com',
                'cdn_bucket': 'cdn-bucket',
                'cdn_url': 'cdn-url',
                'version': '3',
            }
        }

        return event

    @staticmethod
    def create_s3_instance(bucket):
        pass

    @staticmethod
    def create_s3_record(bucket_name, object_key):

        record = {
            's3': {
                'bucket': {'name': bucket_name},
                'object': {'key': object_key}
            }
        }

        return record

    def make_handler_instance(self, progress_db):
        """
        Generates a new handler instance for testing
        :param progress_db:
        :return:
        """
        progress_db_file = os.path.join(self.resources_dir, 'progress_db/{}'.format(progress_db))
        self.assertTrue(os.path.isfile(progress_db_file))

        # now run the code
        event = self.create_event()
        mock_progress_db = MockDynamodbHandler()
        mock_progress_db._load_db(progress_db_file)
        mock_status_db = MockDynamodbHandler()
        mock_errors_db = MockDynamodbHandler()
        dbs = {
            'd43-catalog-in-progress': mock_progress_db,
            'd43-catalog-status': mock_status_db,
            'd43-catalog-errors': mock_errors_db
        }

        mock_ses = MockSESHandler()
        mock_s3 = MockS3Handler()
        mock_checker = MockChecker()
        mock_api = MockAPI(os.path.join(self.resources_dir), '/')

        mock_ses_handler = lambda: mock_ses
        mock_s3_handler = lambda bucket: mock_s3
        mock_dbs_handler = lambda bucket: dbs[bucket]
        mock_checker_handler = lambda: mock_checker
        handler = CatalogHandler(event,
                                 None,
                                 s3_handler=mock_s3_handler,
                                 dynamodb_handler=mock_dbs_handler,
                                 ses_handler=mock_ses_handler,
                                 consistency_checker=mock_checker_handler,
                                 url_exists_handler=lambda url: True,
                                 get_url_handler=mock_api.get_url)
        return {
            'handler': handler,
            'event': event,
            'mocks': {
                'db': {
                    'progress': mock_progress_db,
                    'status': mock_status_db,
                    'errors': mock_errors_db
                },
                'api': mock_api,
                'ses': mock_ses,
                's3': mock_s3,
                'checker': mock_checker
            }
        }

    def run_with_db(self, progress_db):
        """
        Runs the catalog handler with all the proper mocks
        :param progress_db: the progress database file to use
        :return: an object containing the result and related mocks
        """
        state = self.make_handler_instance(progress_db)
        response = state['handler'].run()
        state.update({
            'response':response
        })
        return state

    def test_catalog_valid_obs_content(self, mock_report_error):
        state = self.run_with_db('valid.json')

        response = state['response']
        mock_errors_db = state['mocks']['db']['errors']
        mock_progress_db = state['mocks']['db']['progress']

        self.assertTrue(response['success'])
        self.assertFalse(response['incomplete'])
        self.assertIn('Uploaded new catalog', response['message'])
        assert_object_equals_file(self, response['catalog'], os.path.join(self.resources_dir, 'v3_catalog_obs.json'))
        self.assertEqual(1, len(mock_progress_db._db))
        mock_report_error.assert_not_called()

    def test_catalog_no_sig_content(self, mock_report_error):
        state = self.run_with_db('no_sig.json')

        response = state['response']

        self.assertFalse(response['success'])
        self.assertIn('has not been signed yet', response['message'])

    def test_catalog_mixed_valid_content(self, mock_report_error):
        """
        Test with one valid and one invalid record
        :return:
        """
        state = self.run_with_db('mixed.json')

        response = state['response']

        self.assertTrue(response['success'])
        self.assertIn('Uploaded new catalog', response['message'])
        self.assertTrue(response['incomplete'])
        # we expect the invalid record to be skipped
        assert_object_equals_file(self, response['catalog'], os.path.join(self.resources_dir, 'v3_catalog_obs.json'))

    def test_catalog_invalid_manifest(self, mock_report_error):
        state = self.run_with_db('invalid_manifest.json')

        response = state['response']

        self.assertFalse(response['success'])
        self.assertIn('manifest missing key', response['message'])
        self.assertIsNone(response['catalog'])

    def test_catalog_empty_formats(self, mock_report_error):
        """
        Tests missing status and empty formats
        :return:
        """
        state = self.run_with_db('empty_formats.json')

        response = state['response']

        self.assertFalse(response['success'])
        self.assertIn('There were no formats to process', response['message'])
        self.assertFalse(response['incomplete'])

    def test_catalog_ulb_versification(self, mock_report_error):
        """
        Tests processing ulb first then versification.
        It's important to test order of processing versification because it can take two code paths
        :return:
        """
        state = self.run_with_db('ulb_versification.json')

        response = state['response']

        assert_object_equals_file(self, response['catalog'], os.path.join(self.resources_dir, 'v3_catalog_versification_ulb.json'))

    def test_catalog_versification_ulb(self, mock_report_error):
        """
        Tests processing versification first then ulb.
        It's important to test order of processing versification because it can take two code paths
        :return:
        """
        state = self.run_with_db('versification_ulb.json')

        response = state['response']

        assert_object_equals_file(self, response['catalog'], os.path.join(self.resources_dir, 'v3_catalog_versification_ulb.json'))

    def test_catalog_versification_tq(self, mock_report_error):
        """
        Tests processing versification for tQ (a help RC)
        :return:
        """
        state = self.run_with_db('versification_tq.json')

        response = state['response']

        assert_object_equals_file(self, response['catalog'], os.path.join(self.resources_dir, 'v3_catalog_versification_tq.json'))

    def test_catalog_localization(self, mock_report_error):
        state = self.run_with_db('localization.json')

        response = state['response']

        assert_object_equals_file(self, response['catalog'], os.path.join(self.resources_dir, 'v3_catalog_localization.json'))

    def test_catalog_complex(self, mock_report_error):
        """
        Tests multiple repositories sharing a single resource
        and other complex situations
        :return: 
        """
        state = self.run_with_db('complex.json')

        assert_object_equals_file(self, state['response']['catalog'], os.path.join(self.resources_dir, 'v3_catalog_complex.json'))

    def test_read_none_status(self, mock_report_error):
        state = self.make_handler_instance('valid.json')
        status = state['handler']._read_status()
        self.assertIsNone(status)

    def test_read_status(self, mock_report_error):
        state = self.make_handler_instance('valid.json')
        state['mocks']['db']['status'].insert_item({
            'api_version': '3'
        })
        status = state['handler']._read_status()
        self.assertIsNotNone(status)

    def test_has_usfm_bundle(self, mock_report_error):
        state = self.make_handler_instance('valid.json')
        result = state['handler'].has_usfm_bundle([{
            'format': 'application/zip; content=text/usfm type=bundle'
        }])
        self.assertTrue(result)

    def test_strip_build_rules(self, mock_report_error):
        state = self.make_handler_instance('valid.json')
        obj = {
            'build_rules': [],
            'id': 'obj',
            'projects': [
                {
                    'build_rules':[],
                    'id':'proj',
                    'formats': [
                        {
                            'build_rules': [],
                            'id': 'fmt',
                            'chapters': [
                                {
                                    'id': 'chp',
                                    'build_rules': []
                                }
                            ]
                        }
                    ]
                }
            ],
            'formats': [
                {
                    'build_rules':[],
                    'id':'fmt'
                }
            ]
        }
        expected = {
            'id': 'obj',
            'projects': [
                {
                    'id':'proj',
                    'formats': [
                        {
                            'id': 'fmt',
                            'chapters': [
                                {
                                    'id': 'chp'
                                }
                            ]
                        }
                    ]
                }
            ],
            'formats': [
                {
                    'id':'fmt'
                }
            ]
        }
        state['handler']._strip_build_rules(obj)
        assert_object_equals(self, expected, obj)