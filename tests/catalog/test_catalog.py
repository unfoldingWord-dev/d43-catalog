from __future__ import unicode_literals, print_function
import os
from unittest import TestCase
from tools.test_utils import assert_object_equals_file
from tools.mocks import MockChecker, MockDynamodbHandler, MockS3Handler, MockSESHandler
from functions.catalog.catalog_handler import CatalogHandler

# This is here to test importing main
from functions.catalog import main


class TestCatalog(TestCase):

    resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

    @staticmethod
    def create_event():

        event = {
            'Records': [],
            'api_url': 'my-api',
            'api_bucket': 'my-bucket',
            'to_email': 'me@example.com',
            'from_email': 'me@example.com',
            'cdn_bucket': 'cdn-bucket',
            'cdn_url': 'cdn-url'
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

    def run_with_db(self, progress_db):
        """
        Runs the catalog handler with all the proper mocks
        :param progress_db: the progress database file to use
        :return: an object containing the result and related mocks
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

        mock_ses_handler = lambda: mock_ses
        mock_s3_handler = lambda bucket: mock_s3
        mock_dbs_handler = lambda bucket: dbs[bucket]
        mock_checker_handler = lambda: mock_checker
        catalog = CatalogHandler(event,
                                 s3_handler=mock_s3_handler,
                                 dynamodb_handler=mock_dbs_handler,
                                 ses_handler=mock_ses_handler,
                                 consistency_checker=mock_checker_handler,
                                 url_exists_handler=lambda url: True)
        response = catalog.handle_catalog()

        return {
            'response': response,
            'event': event,
            'mocks': {
                'db': {
                    'progress': mock_progress_db,
                    'status': mock_status_db,
                    'errors': mock_errors_db
                },
                'ses': mock_ses,
                's3': mock_s3,
                'checker': mock_checker
            }
        }

    def test_catalog_valid_obs_content(self):
        state = self.run_with_db('valid.json')

        response = state['response']
        mock_errors_db = state['mocks']['db']['errors']
        mock_progress_db = state['mocks']['db']['progress']

        self.assertTrue(response['success'])
        self.assertFalse(response['incomplete'])
        self.assertIn('Uploaded new catalog', response['message'])
        assert_object_equals_file(self, response['catalog'], os.path.join(self.resources_dir, 'v3_catalog_obs.json'))
        self.assertEqual(0, len(mock_errors_db._db))
        self.assertEqual(1, len(mock_progress_db._db))

    def test_catalog_no_sig_content(self):
        state = self.run_with_db('no_sig.json')

        response = state['response']

        self.assertFalse(response['success'])
        self.assertIn('has not been signed yet', response['message'])

    def test_catalog_mixed_valid_content(self):
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

    def test_catalog_invalid_manifest(self):
        state = self.run_with_db('invalid_manifest.json')

        response = state['response']

        self.assertFalse(response['success'])
        self.assertIn('manifest missing key', response['message'])
        self.assertIsNone(response['catalog'])

    def test_catalog_empty_formats(self):
        """
        Tests missing status and empty formats
        :return:
        """
        state = self.run_with_db('empty_formats.json')

        response = state['response']

        self.assertFalse(response['success'])
        self.assertIn('There were no formats to process', response['message'])
        self.assertFalse(response['incomplete'])

    def test_catalog_ulb_versification(self):
        """
        Tests processing ulb first then versification.
        It's important to test order of processing versification because it can take two code paths
        :return:
        """
        state = self.run_with_db('ulb_versification.json')

        response = state['response']

        assert_object_equals_file(self, response['catalog'], os.path.join(self.resources_dir, 'v3_catalog_versification_ulb.json'))

    def test_catalog_versification_ulb(self):
        """
        Tests processing versification first then ulb.
        It's important to test order of processing versification because it can take two code paths
        :return:
        """
        state = self.run_with_db('versification_ulb.json')

        response = state['response']

        assert_object_equals_file(self, response['catalog'], os.path.join(self.resources_dir, 'v3_catalog_versification_ulb.json'))

    def test_catalog_versification_tq(self):
        """
        Tests processing versification for tQ (a help RC)
        :return:
        """
        state = self.run_with_db('versification_tq.json')

        response = state['response']

        assert_object_equals_file(self, response['catalog'], os.path.join(self.resources_dir, 'v3_catalog_versification_tq.json'))

    def test_catalog_localization(self):
        state = self.run_with_db('localization.json')

        response = state['response']

        assert_object_equals_file(self, response['catalog'], os.path.join(self.resources_dir, 'v3_catalog_localization.json'))

    def test_catalog_complex(self):
        """
        Tests multiple repositories sharing a single resource
        and other complex situations
        :return: 
        """
        state = self.run_with_db('complex.json')

        assert_object_equals_file(self, state['response']['catalog'], os.path.join(self.resources_dir, 'v3_catalog_complex.json'))
