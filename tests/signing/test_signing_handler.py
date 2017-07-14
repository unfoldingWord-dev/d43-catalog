from __future__ import unicode_literals, print_function
import json
import os
import shutil
import tempfile
import unittest
import uuid
from unittest import TestCase
from datetime import datetime
from tools.file_utils import load_json_object
from functions.signing import SigningHandler
from tools.mocks import MockDynamodbHandler, MockS3Handler, MockLogger, MockSigner

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
            'cdn_bucket': 'cdn.door43.org'
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
        dbHandler = MockDynamodbHandler()

        handler = SigningHandler(event,
                                logger=MockLogger(),
                                signer=self.mock_signer,
                                s3_handler=None,
                                dynamodb_handler=dbHandler)
        result = handler.run()
        self.assertFalse(result)


    def test_signing_handler_invalid_manifest(self):
        # mock a lambda event object
        event = self.create_event()

        # mock the dynamodb handler
        dbHandler = MockDynamodbHandler()
        dbHandler._load_db(os.path.join(self.resources_dir, 'corrupt_manifest_record.json'))
        item = dbHandler.query_items()[0]

        s3Handler = MockS3Handler('test-cdn_bucket')
        key = 'temp/{}/{}/test.zip'.format(item['repo_name'], item['commit_id'])
        s3Handler.upload_file(os.path.join(self.resources_dir, 'test.zip'), key)

        signer = SigningHandler(event,
                                logger=MockLogger(),
                                signer=self.mock_signer,
                                s3_handler=s3Handler,
                                dynamodb_handler=dbHandler)
        result = signer.run()

        self.assertTrue(result)

        # test that the expected file was not generated
        expected_file = os.path.join(s3Handler.temp_dir, 'temp', 'unit_test', 'v1', 'test.zip.sig')
        self.assertFalse(os.path.isfile(expected_file))


    def test_signing_handler_text_missing_file(self):
        """
        Signing will continue to run even if a file is missing.
        The missing file will just be ignored.
        :return:
        """

        # mock a lambda event object
        event = self.create_event()
        # event['Records'].append(self.create_s3_record('test-cdn_bucket', test_txt))

        # mock the dynamodb handler
        dbHandler = MockDynamodbHandler()
        item = self.create_db_item(os.path.basename(self.temp_dir))
        dbHandler.insert_item(item)

        # test that the mock S3 file does not exist
        # self.assertFalse(os.path.isfile(test_txt))
        s3_handler = MockS3Handler('test-cdn_bucket')

        signer = SigningHandler(event,
                                logger=MockLogger(),
                                signer=self.mock_signer,
                                s3_handler=s3_handler,
                                dynamodb_handler=dbHandler)
        result = signer.run()
        self.assertTrue(result)

        # test that the expected file was not output
        expected_file = os.path.join(s3_handler.temp_dir, 'temp', 'unit_test', 'v1', 'test.txt.sig')
        self.assertFalse(os.path.isfile(expected_file))

    def test_signing_handler_text_wrong_key(self):

        # copy zip file to temp directory
        test_txt = os.path.join(self.temp_dir, 'test.txt')
        shutil.copy(os.path.join(self.resources_dir, 'test.txt'), test_txt)

        # mock a lambda event object
        event = self.create_event()
        # event['Records'].append(self.create_s3_record('test-cdn_bucket', test_txt))

        # mock the dynamodb handler
        dbHandler = MockDynamodbHandler()
        dbHandler._load_db(os.path.join(self.resources_dir, 'db_zip_records.json'))
        item = dbHandler.query_items()[0]
        item_file = os.path.basename(json.loads(item['package'])['formats'][0]['url'])
        file_key = 'temp/{}/{}/{}'.format(item['repo_name'], item['commit_id'], item_file)

        s3_handler = MockS3Handler('mock-s3')
        s3_handler.upload_file(test_txt, file_key)

        # test when S3 file exists
        self.assertTrue(os.path.isfile(test_txt))

        # TRICKY: a wrong signing key will result in failed verification
        self.mock_signer._fail_verification()
        signer = SigningHandler(event,
                                logger=MockLogger(),
                                signer=self.mock_signer,
                                s3_handler=s3_handler,
                                dynamodb_handler=dbHandler)
        result = signer.run()

        self.assertTrue(result)

        # nothing should have been uploaded
        self.assertEqual(1, len(s3_handler._uploads))
        self.assertIn(file_key, s3_handler._uploads)
        # self.assertNotIn('{}.sig'.format(file_key), s3_handler._uploads)

    # @unittest.skipIf(SigningHandler.is_travis(), 'Skipping test_signing_handler_s3 on Travis CI.')
    def test_signing_handler_s3(self):

        # create test folder on S3
        commit_id = str(uuid.uuid4())[-10:]
        test_source_folder = 'temp/unit_test/{}'.format(commit_id)
        test_target_folder = 'temp/unit_test/v{}'.format(commit_id)
        s3_handler = MockS3Handler('test-cdn.door43.org')
        s3_source_zip_key = '{}/test.zip'.format(test_source_folder)
        s3_target_zip_key = '{}/test.zip'.format(test_target_folder)
        self.s3keys.append(s3_source_zip_key)
        self.s3keys.append(s3_target_zip_key)

        s3_handler.upload_file(os.path.join(self.resources_dir, 'test.zip'), s3_source_zip_key)

        # create a record in dynamodb
        manifest = load_json_object(os.path.join(self.resources_dir, 'package.json'))
        manifest['dublin_core']['version'] = commit_id
        manifest['formats'][0]['url'] = 'https://test-cdn.door43.org/temp/unit_test/v{}/test.zip'.format(commit_id)
        manifest['projects'][0]['formats'][0]['url'] = 'https://test-cdn.door43.org/temp/unit_test/v{}/test.zip'.format(commit_id)
        manifest['projects'][0]['formats'][0]['chapters'][0]['url'] = 'https://test-cdn.door43.org/temp/unit_test/v{}/test.zip'.format(commit_id)
        db_handler = MockDynamodbHandler(SigningHandler.dynamodb_table_name)
        db_handler.insert_item({
            'repo_name': 'unit_test',
            'commit_id': commit_id,
            'package': json.dumps(manifest, sort_keys=True),
            'timestamp': datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            'language': 'temp',
            'signed': False
        })

        # mock a lambda event object
        event = self.create_event()

        # do the signing
        signer = SigningHandler(event,
                                logger=MockLogger(),
                                signer=self.mock_signer,
                                s3_handler=s3_handler,
                                dynamodb_handler=db_handler)
        result = signer.run()
        self.assertTrue(result)

        # check that the sig file was found
        s3_sig = '{}/test.zip.sig'.format(test_target_folder)
        self.s3keys.append(s3_sig)

        expected_file = os.path.join(self.temp_dir, 'test.zip.sig')
        s3_handler.download_file(s3_sig, expected_file)
        self.assertTrue(os.path.isfile(expected_file))

        # check the dynamodb record
        row_keys = {'repo_name': 'unit_test'}
        row = db_handler.get_item(row_keys)

        # verify this is the correct commit
        self.assertEqual(commit_id, row['commit_id'])

        # check for the .sig file in the database
        package_after = json.loads(row['package'], 'utf-8')
        found_file = [f for f in package_after['formats'] if f['signature'].endswith('test.zip.sig')]
        self.assertGreater(len(found_file), 0, 'The .sig file was not found in the resource formats list.')

        # check that media chapters were signed
        for project in package_after['projects']:
            found_file = [f for f in project['formats'] if f['signature'].endswith('test.zip.sig')]
            self.assertGreater(len(found_file), 0, 'The .sig file was not found in the resource formats list.')
            for format in project['formats']:
                if 'chapters' in format:
                    found_file = [c for c in format['chapters'] if c['signature'].endswith('test.zip.sig')]
                    self.assertGreater(len(found_file), 0, 'The .sig file was not found in the resource format chapters list.')

        self.assertIn('signed', row)
        self.assertTrue('signed', row['signed'])

        # added the url of the sig file to the format item
        manifest = json.loads(row['package'])
        found_file = [fmt['signature'] for fmt in manifest['formats'] if fmt['signature'].endswith('test.zip.sig')]
        self.assertGreater(len(found_file), 0, 'The .sig file was not found in the formats list.')

        # clean up
        db_handler.delete_item(row_keys)

    def test_signing_handler_zip(self):

        # mock a lambda event object
        event = self.create_event()

        # mock the dynamodb handler
        dbHandler = MockDynamodbHandler()
        dbHandler._load_db(os.path.join(self.resources_dir, 'db_zip_records.json'))
        item = dbHandler.query_items()[0]


        s3Handler = MockS3Handler('test-cdn_bucket')
        key = 'temp/{}/{}/test.zip'.format(item['repo_name'], item['commit_id'])
        s3Handler.upload_file(os.path.join(self.resources_dir, 'test.zip'), key)

        signer = SigningHandler(event,
                                logger=MockLogger(),
                                signer=self.mock_signer,
                                s3_handler=s3Handler,
                                dynamodb_handler=dbHandler)
        result = signer.run()

        self.assertTrue(result)

        # test that the expected file was output
        expected_file = os.path.join(s3Handler.temp_dir, 'temp', 'unit_test', 'v1', 'test.zip.sig')
        self.assertTrue(os.path.isfile(expected_file))

        # test when S3 file does not exist

        # test successful sig file generation

        # test unsuccessful sig file generation

        # test updating DynamoDB record

    def test_signing_handler_no_records(self):

        # mock a lambda event object
        event = self.create_event()

        dbHandler = MockDynamodbHandler()

        signer = SigningHandler(event,
                                logger=MockLogger(),
                                signer=self.mock_signer,
                                s3_handler=None,
                                dynamodb_handler=dbHandler)
        result = signer.run()

        self.assertFalse(result)

    def test_signing_handler_already_signed(self):
        event = self.create_event()
        dbHandler = MockDynamodbHandler()
        dbHandler._load_db(os.path.join(self.resources_dir, 'db_signed_records.json'))
        item = dbHandler.query_items()[0]

        self.assertFalse(item['signed'])

        # s3Handler = MockS3Handler('test-cdn_bucket')
        # key = 'temp/{}/{}/test.zip'.format(item['repo_name'], item['commit_id'])
        # s3Handler.upload_file(os.path.join(self.resources_dir, 'test.zip'), key)

        signer = SigningHandler(event,
                                logger=MockLogger(),
                                signer=self.mock_signer,
                                s3_handler=None,
                                dynamodb_handler=dbHandler)

        result = signer.run()
        self.assertTrue(result)

        self.assertEqual(1, len(dbHandler.db))
        self.assertTrue(dbHandler.db[0]['signed'])

