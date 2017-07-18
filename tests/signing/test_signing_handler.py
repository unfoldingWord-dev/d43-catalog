from __future__ import unicode_literals, print_function
import json
import os
import shutil
import tempfile
import uuid
from unittest import TestCase
from datetime import datetime
from tools.file_utils import load_json_object
from functions.signing import SigningHandler
from tools.mocks import MockDynamodbHandler, MockS3Handler, MockLogger, MockSigner, MockAPI
from tools.test_utils import assert_object_not_equals

class TestSigningHandler(TestCase):

    def setUp(self):
        self.mock_signer = MockSigner()
        self.resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')
        self.temp_dir = tempfile.mkdtemp(prefix='signing_tests_')
        self.s3keys = []

    def tearDown(self):
        # clean up local temp files
        if os.path.isdir(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_db_item(self, commit_id=None):
        item = load_json_object(os.path.join(self.resources_dir, 'dynamodb_record.json'))[0]
        if commit_id:
            item['commit_id'] = commit_id
        return item

    def create_event(self):

        event = {
            'cdn_bucket': 'cdn.door43.org',
            'cdn_url': 'https://cdn.door43.org'
        }

        return event

    # def test_signing_handler_text(self):
    #     # mock a lambda event object
    #     event = self.create_event()
    #
    #     # mock the dynamodb handler
    #     dbHandler = MockDynamodbHandler()
    #     dbHandler._load_db(os.path.join(self.resources_dir, 'dynamodb_text_records.json'))
    #     item = dbHandler.query_items()[0]
    #
    #
    #     s3Handler = MockS3Handler('test-cdn_bucket')
    #     key = 'temp/{}/{}/test.txt'.format(item['repo_name'], item['commit_id'])
    #     s3Handler.upload_file(os.path.join(self.resources_dir, 'test.txt'), key)
    #
    #     # test that the mock S3 file exists
    #     self.assertTrue(os.path.isfile(os.path.join(s3Handler.temp_dir, key)))
    #
    #     private_pem_file = os.path.join(self.resources_dir, 'unit-test-private.pem') if Signing.is_travis() else None
    #     public_pem_file = os.path.join(self.resources_dir, 'unit-test-public.pem') if Signing.is_travis() else None
    #     signer = Signing(event, MockLogger(), s3_handler=s3Handler, dynamodb_handler=dbHandler,
    #                                        private_pem_file=private_pem_file, public_pem_file=public_pem_file)
    #     result = signer.handle_s3_trigger()
    #     self.assertTrue(result)
    #
    #     # test that the expected file was output
    #     expected_file = os.path.join(s3Handler.temp_dir, 'en-tmp', 'unit_test', 'v1', 'test.txt.sig')
    #     self.assertTrue(os.path.isfile(expected_file))

    # def test_signing_handler_text_project(self):
    #     repo_name = 'tmp'
    #
    #     # copy file to temp directory
    #     test_proj = os.path.join(self.temp_dir, 'res_id/proj.usfm')
    #     os.mkdir(os.path.join(self.temp_dir, 'res_id'))
    #     shutil.copy(os.path.join(self.resources_dir, 'proj.usfm'), test_proj)
    #
    #     # mock a lambda event object
    #     event = self.create_event()
    #     # event['Records'].append(self.create_s3_record('test-cdn_bucket', test_proj))
    #
    #     # mock the dynamodb handler
    #     dbHandler = MockDynamodbHandler()
    #     item = TestSigning.create_db_item(os.path.basename(self.temp_dir))
    #     item['repo_name'] = repo_name
    #     manifest = json.loads(item['package'])
    #     manifest['projects'] = [{
    #         'categories':[],
    #         'identifier':'proj',
    #         'path':'./proj.usfm',
    #         'sort': 0,
    #         'title': 'Project',
    #         'versification': None,
    #         'formats': [{
    #             'format': 'text/usfm',
    #             'modified': '',
    #             'signature': '',
    #             'size': 0,
    #             'url': 'https://test-cdn.door43.org/temp/unit_test/v1/res_id/proj.usfm'
    #         }]
    #     }]
    #     item['package'] = json.dumps(manifest)
    #     dbHandler.insert_item(item)
    #
    #     s3Handler = MockS3Handler('test-cdn_bucket')
    #
    #     # test that the mock S3 file exists
    #     self.assertTrue(os.path.isfile(test_proj))
    #
    #     private_pem_file = os.path.join(self.resources_dir, 'unit-test-private.pem') if Signing.is_travis() else None
    #     public_pem_file = os.path.join(self.resources_dir, 'unit-test-public.pem') if Signing.is_travis() else None
    #     signer = Signing(event, MockLogger(), s3_handler=s3Handler, dynamodb_handler=dbHandler,
    #                      private_pem_file=private_pem_file, public_pem_file=public_pem_file)
    #     result = signer.handle_s3_trigger()
    #     self.assertTrue(result)
    #
    #     expected_file = os.path.join(self.temp_dir, 'temp', 'unit_test', 'v1', 'res_id', 'proj.usfm.sig')
    #     self.assertTrue(os.path.isfile(expected_file))
    #     expected_file = os.path.join(self.temp_dir, 'temp', 'unit_test', 'v1', 'res_id', 'proj.usfm')
    #     self.assertTrue(os.path.isfile(expected_file))
    #
    #     db_item = dbHandler.last_inserted_item
    #     manifest = json.loads(db_item['package'])
    #     format = manifest['projects'][0]['formats'][0]
    #     self.assertTrue(format['signature'])

    def test_signing_handler_text_no_records(self):
        event = self.create_event()
        mock_db = MockDynamodbHandler()
        mock_s3 = MockS3Handler()

        handler = SigningHandler(event,
                                logger=MockLogger(),
                                signer=self.mock_signer,
                                s3_handler=mock_s3,
                                dynamodb_handler=mock_db)
        result = handler.run()
        self.assertFalse(result)


    def test_signing_handler_invalid_manifest(self):
        event = self.create_event()
        mock_db = MockDynamodbHandler()
        mock_db._load_db(os.path.join(self.resources_dir, 'db/invalid.json'))

        mock_s3 = MockS3Handler()
        mock_s3._load_path(os.path.join(self.resources_dir, 'cdn'))

        mock_logger = MockLogger()

        signer = SigningHandler(event,
                                logger=mock_logger,
                                signer=self.mock_signer,
                                s3_handler=mock_s3,
                                dynamodb_handler=mock_db)
        result = signer.run()

        self.assertTrue(result)
        for f in mock_s3._uploads:
            # assert nothing was uploaded to production
            self.assertTrue(f.startswith('temp/'))
            self.assertFalse(f.endswith('.sig'))
        self.assertIn('Skipping unit-test. Bad Manifest: No JSON object could be decoded', mock_logger._messages)


    def test_signing_handler_text_missing_file(self):
        """
        Signing will continue to run even if a file is missing.
        The missing file will just be ignored.
        :return:
        """
        event = self.create_event()

        mock_db = MockDynamodbHandler()
        mock_db._load_db(os.path.join(self.resources_dir, 'db/valid_unsigned.json'))

        mock_logger = MockLogger()
        mock_s3 = MockS3Handler()

        signer = SigningHandler(event,
                                logger=mock_logger,
                                signer=self.mock_signer,
                                s3_handler=mock_s3,
                                dynamodb_handler=mock_db)
        result = signer.run()
        self.assertTrue(result)
        self.assertEqual(0, len(mock_s3._uploads))
        self.assertIn('The file "obs.zip" could not be downloaded: File not found for key: temp/en_obs/192c997b07/en/obs/v4/obs.zip', mock_logger._messages)

    def test_signing_handler_text_wrong_key(self):
        event = self.create_event()

        mock_db = MockDynamodbHandler()
        mock_db._load_db(os.path.join(self.resources_dir, 'db/valid_unsigned.json'))

        mock_s3 = MockS3Handler()
        mock_s3._load_path(os.path.join(self.resources_dir, 'cdn'))

        mock_logger = MockLogger()

        # TRICKY: a wrong signing key will result in failed verification
        self.mock_signer._fail_verification()
        signer = SigningHandler(event,
                                logger=mock_logger,
                                signer=self.mock_signer,
                                s3_handler=mock_s3,
                                dynamodb_handler=mock_db)
        result = signer.run()

        self.assertTrue(result)
        for f in mock_s3._uploads:
            # assert nothing was uploaded to production
            self.assertTrue(f.startswith('temp/'))
            self.assertFalse(f.endswith('.sig'))
        self.assertIn('The signature was not successfully verified.', mock_logger._messages)

    def test_signing_handler_s3(self):
        mock_s3 = MockS3Handler()
        mock_s3._load_path(os.path.join(self.resources_dir, 'cdn'))

        mock_db = MockDynamodbHandler()
        mock_db._load_db(os.path.join(self.resources_dir, 'db/valid_unsigned.json'))

        mock_logger = MockLogger()

        mock_api = MockAPI(os.path.join(self.resources_dir, 'cdn/temp/en_obs/192c997b07/'), 'https://cdn.door43.org/')

        event = self.create_event()

        original_item = mock_db.get_item({'repo_name': 'en_obs'}).copy()
        self.assertIn('signed', original_item)
        self.assertFalse(original_item['signed'])

        signer = SigningHandler(event,
                                logger=mock_logger,
                                signer=self.mock_signer,
                                s3_handler=mock_s3,
                                dynamodb_handler=mock_db,
                                url_exists_handler=mock_api.url_exists)
        result = signer.run()
        self.assertTrue(result)

        self.assertTrue(len(mock_s3._uploads) > 0)
        has_prod_uploads = False
        for key in mock_s3._uploads:
            # assert prod uploads have signatures
            if not key.startswith('temp/') and not key.endswith('.sig'):
                has_prod_uploads = True
                self.assertIn('{}.sig'.format(key), mock_s3._uploads)
        self.assertTrue(has_prod_uploads)

        updated_item = mock_db.get_item({'repo_name': 'en_obs'}).copy()
        assert_object_not_equals(self, updated_item, original_item)

        # check for the .sig in resource formats
        manifest = json.loads(updated_item['package'], 'utf-8')
        found_file = [f for f in manifest['formats'] if f['signature'].endswith('.sig')]
        self.assertGreater(len(found_file), 0, 'The .sig file was not found in the resource formats list.')

        # check for .sig in project formats
        for project in manifest['projects']:
            found_file = [f for f in project['formats'] if f['signature'].endswith('.sig')]
            self.assertGreater(len(found_file), 0, 'The .sig file was not found in the resource formats list.')
            # check for .sig in chapter formats
            for format in project['formats']:
                if 'chapters' in format and len(format['chapters']):
                    if format['quality'] == '32kbps':
                        # check that we skipped a chapter
                        self.assertEqual(1, len(format['chapters']))
                    else:
                        self.assertTrue(len(format['chapters']) > 1)

                    for chapter in format['chapters']:
                        self.assertTrue(chapter['signature'].endswith('.sig'))
                        self.assertNotEqual('', chapter['modified'])
                        self.assertNotEqual(0, chapter['length'])
                        self.assertNotEqual(0, chapter['size'])

                        # check that we don't have the skipped chapter
                        ch_quality = '{}_{}'.format(chapter['identifier'], format['quality'])
                        self.assertNotEqual(ch_quality, '01_32kbps')  # skipped chapter one audio because it was missing

                    found_file = [c for c in format['chapters'] if c['signature'].endswith('.sig')]
                    self.assertGreater(len(found_file), 0, 'The .sig file was not found in the resource format chapters list.')
                elif 'chapters' in format:
                    raise Exception('Expected some chapters but found none')

        self.assertIn('Skipping chapter obs:01 missing url https://cdn.door43.org/en/obs/v4/32kbps/en_obs_01_32kbps.mp3', mock_logger._messages)

        # check the record is marked as signed
        self.assertIn('signed', updated_item)
        self.assertTrue(updated_item['signed'])

    def test_signing_handler_no_records(self):
        event = self.create_event()

        mock_logger = MockLogger()
        mock_db = MockDynamodbHandler()
        mock_s3 = MockS3Handler()

        signer = SigningHandler(event,
                                logger=mock_logger,
                                signer=self.mock_signer,
                                s3_handler=mock_s3,
                                dynamodb_handler=mock_db)
        result = signer.run()

        self.assertFalse(result)
        self.assertIn('No items found for signing', mock_logger._messages)

    def test_signing_handler_already_signed(self):
        event = self.create_event()
        mock_s3 = MockS3Handler()
        mock_db = MockDynamodbHandler()
        mock_db._load_db(os.path.join(self.resources_dir, 'db/valid_signed.json'))
        mock_logger = MockLogger()
        original_record = mock_db.get_item({'repo_name':'en_obs'}).copy()
        self.assertFalse(original_record['signed'])

        signer = SigningHandler(event,
                                logger=mock_logger,
                                signer=self.mock_signer,
                                s3_handler=mock_s3,
                                dynamodb_handler=mock_db)

        result = signer.run()
        self.assertTrue(result)

        updated_record = mock_db.get_item({'repo_name': 'en_obs'}).copy()
        self.assertTrue(updated_record['signed'])

