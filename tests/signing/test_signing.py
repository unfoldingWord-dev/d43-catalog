from __future__ import unicode_literals, print_function
import codecs
import json
import os
import shutil
import tempfile
import unittest
import uuid
from unittest import TestCase
from datetime import datetime
from aws_tools.dynamodb_handler import DynamoDBHandler
from aws_tools.s3_handler import S3Handler
from general_tools.file_utils import load_json_object
from functions.signing.aws_decrypt import decrypt_file
from functions.signing.signing import Signing
from tools.mocks import MockDynamodbHandler, MockS3Handler, MockLogger


class TestSigning(TestCase):

    resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

    # class MockLogger(object):
    #
    #     @staticmethod
    #     def warning(message):
    #         print('WARNING: {}'.format(message))

    # class MockS3Handler(object):
    #     temp_dir = ''
    #
    #     def __init__(self, bucket_name):
    #         self.bucket_name = bucket_name
    #
    #     @staticmethod
    #     def download_file(key, local_file):
    #         shutil.copy(key, local_file)
    #
    #     @staticmethod
    #     def upload_file(path, key):
    #         out_path = os.path.join(TestSigning.MockS3Handler.temp_dir, key)
    #         parent_dir = os.path.dirname(out_path)
    #         if not os.path.isdir(parent_dir):
    #             os.makedirs(parent_dir)
    #
    #         shutil.copy(path, out_path)

    # class MockDynamodbHandler(object):
    #
    #     commit_id = ''
    #
    #     def __init__(self, table_name):
    #         self.table_name = table_name
    #
    #     # noinspection PyUnusedLocal
    #     @staticmethod
    #     def get_item(record_keys):
    #         return_val = load_json_object(os.path.join(TestSigning.resources_dir, 'dynamodb_record.json'))
    #         if TestSigning.MockDynamodbHandler.commit_id:
    #             return_val['commit_id'] = TestSigning.MockDynamodbHandler.commit_id
    #         return return_val
    #
    #     # noinspection PyUnusedLocal
    #     @staticmethod
    #     def update_item(record_keys, row):
    #         return True

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix='signing_tests_')
        # MockS3Handler.temp_dir = self.temp_dir
        self.s3keys = []

    def tearDown(self):
        # clean up local temp files
        if os.path.isdir(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

        # clean up temp files on S3
        if len(self.s3keys) > 0:
            s3_handler = S3Handler('test-cdn.door43.org')
            for s3key in self.s3keys:
                s3_handler.delete_file(s3key)

    @staticmethod
    def create_db_item(commit_id=None):
        item = load_json_object(os.path.join(TestSigning.resources_dir, 'dynamodb_record.json'))
        if commit_id:
            item['commit_id'] = commit_id
        return item

    @staticmethod
    def create_event():

        event = {'api_bucket': 'my-bucket'}

        return event

    @staticmethod
    def create_s3_record(bucket_name, object_key):

        record = {
            's3': {
                'bucket': {'name': bucket_name},
                'object': {'key': object_key}
            }
        }

        return record

    @unittest.skipIf(Signing.is_travis(), 'Skipping test_decrypt_file on Travis CI.')
    def test_decrypt_file(self):
        """
        This tests the decryption of an encrypted file. The lambda function will use this to decrypt the key file
        that is used to sign source files
        :return:
        """

        encrypted_file = os.path.join(self.resources_dir, 'test.enc')
        decrypted_file = os.path.join(self.temp_dir, 'test.txt')
        result = decrypt_file(encrypted_file, decrypted_file)

        # verify the file was decrypted
        self.assertTrue(result)
        self.assertTrue(os.path.isfile(decrypted_file))

        # verify the contents
        with codecs.open(decrypted_file, 'r', encoding='utf-8') as in_file:
            decrypted_text = in_file.read()

        with codecs.open(os.path.join(self.resources_dir, 'test.txt'), 'r', encoding='utf-8') as in_file:
            original_text = in_file.read()

        self.assertEqual(decrypted_text, original_text)

    def test_sign_file_with_test_certificate(self):

        # initialization
        source_file = os.path.join(self.temp_dir, 'source.json')
        sig_file = os.path.join(self.temp_dir, 'source.sig')

        # copy test file to the temp directory
        shutil.copy(os.path.join(self.resources_dir, 'source.json'), source_file)

        # check that the source file exists in the temp directory
        self.assertTrue(os.path.isfile(source_file))

        # check that .sig file DOES NOT exist
        self.assertFalse(os.path.isfile(sig_file))

        # sign the file
        sig_file_name = Signing.sign_file(source_file,
                                          pem_file=os.path.join(self.resources_dir, 'unit-test-private.pem'))

        # check that .sig file DOES exist now
        self.assertEqual(sig_file, sig_file_name)
        self.assertTrue(os.path.isfile(sig_file))

        # verify the .sig file is correct
        self.assertTrue(Signing.verify_signature(source_file, sig_file_name,
                                                 pem_file=os.path.join(self.resources_dir, 'unit-test-public.pem')))

    def test_verify_with_bogus_certificate(self):

        # initialization
        source_file = os.path.join(self.temp_dir, 'source.json')
        sig_file = os.path.join(self.temp_dir, 'source.sig')

        # copy test file to the temp directory
        shutil.copy(os.path.join(self.resources_dir, 'source.json'), source_file)

        # check that the source file exists in the temp directory
        self.assertTrue(os.path.isfile(source_file))

        # check that .sig file DOES NOT exist
        self.assertFalse(os.path.isfile(sig_file))

        # sign the file
        sig_file_name = Signing.sign_file(source_file,
                                          pem_file=os.path.join(self.resources_dir, 'unit-test-private.pem'))

        # check that .sig file DOES exist now
        self.assertEqual(sig_file, sig_file_name)
        self.assertTrue(os.path.isfile(sig_file))

        # this should raise an exception
        with self.assertRaises(Exception) as context:
            self.assertTrue(Signing.verify_signature(source_file, sig_file_name,
                                                     pem_file=os.path.join(self.resources_dir,
                                                                           'unit-test-private.pem')))

        self.assertIn('key file', str(context.exception))

    def test_verify_with_wrong_certificate(self):

        # initialization
        source_file = os.path.join(self.temp_dir, 'source.json')
        sig_file = os.path.join(self.temp_dir, 'source.sig')

        # copy test file to the temp directory
        shutil.copy(os.path.join(self.resources_dir, 'source.json'), source_file)

        # check that the source file exists in the temp directory
        self.assertTrue(os.path.isfile(source_file))

        # check that .sig file DOES NOT exist
        self.assertFalse(os.path.isfile(sig_file))

        # sign the file
        sig_file_name = Signing.sign_file(source_file,
                                          pem_file=os.path.join(self.resources_dir, 'unit-test-private.pem'))

        # check that .sig file DOES exist now
        self.assertEqual(sig_file, sig_file_name)
        self.assertTrue(os.path.isfile(sig_file))

        # this should raise an exception
        with self.assertRaises(Exception) as context:
            self.assertTrue(Signing.verify_signature(source_file, sig_file_name,
                                                     pem_file=os.path.join(self.resources_dir,
                                                                           'alt-private.pem')))

        self.assertIn('key file', str(context.exception))

    @unittest.skipIf(Signing.is_travis(), 'Skipping test_sign_file_with_live_certificate on Travis CI.')
    def test_sign_file_with_live_certificate(self):

        # initialization
        source_file = os.path.join(self.temp_dir, 'source.json')
        sig_file = os.path.join(self.temp_dir, 'source.sig')

        # copy test file to the temp directory
        shutil.copy(os.path.join(self.resources_dir, 'source.json'), source_file)

        # check that the source file exists in the temp directory
        self.assertTrue(os.path.isfile(source_file))

        # check that .sig file DOES NOT exist
        self.assertFalse(os.path.isfile(sig_file))

        # sign the file
        sig_file_name = Signing.sign_file(source_file)

        # check that .sig file DOES exist now
        self.assertEqual(sig_file, sig_file_name)
        self.assertTrue(os.path.isfile(sig_file))

        # verify the .sig file is correct
        self.assertTrue(Signing.verify_signature(source_file, sig_file_name))

    def test_get_default_pem_file(self):

        if Signing.is_travis():
            with self.assertRaises(Exception) as context:
                Signing.get_default_pem_file()

            self.assertIn(str(context.exception), ['Not able to decrypt the pem file.', 'You must specify a region.'])

        else:
            pem_file = Signing.get_default_pem_file()

            self.assertTrue(pem_file.endswith('uW-sk.pem'))
            self.assertTrue(os.path.isfile(pem_file))

    def test_openssl_exception_while_signing(self):

        # initialization
        source_file = os.path.join(self.temp_dir, 'source.json')
        sig_file = os.path.join(self.temp_dir, 'source.sig')

        # copy test file to the temp directory
        shutil.copy(os.path.join(self.resources_dir, 'source.json'), source_file)

        # check that the source file exists in the temp directory
        self.assertTrue(os.path.isfile(source_file))

        # check that .sig file DOES NOT exist
        self.assertFalse(os.path.isfile(sig_file))

        # sign the file using bogus key
        with self.assertRaises(Exception) as context:
            Signing.sign_file(source_file, pem_file=os.path.join(self.resources_dir, 'none.pem'))

        self.assertIn('key file', str(context.exception))

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

        private_pem_file = os.path.join(self.resources_dir, 'unit-test-private.pem') if Signing.is_travis() else None
        public_pem_file = os.path.join(self.resources_dir, 'unit-test-public.pem') if Signing.is_travis() else None
        signer = Signing(event, MockLogger(), s3_handler=None, dynamodb_handler=dbHandler,
                                           private_pem_file=private_pem_file, public_pem_file=public_pem_file)
        result = signer.handle_s3_trigger()
        self.assertFalse(result)

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
        item = TestSigning.create_db_item(os.path.basename(self.temp_dir))
        dbHandler.insert_item(item)

        # test that the mock S3 file does not exist
        # self.assertFalse(os.path.isfile(test_txt))
        s3_handler = MockS3Handler('test-cdn_bucket')

        private_pem_file = os.path.join(self.resources_dir, 'unit-test-private.pem') if Signing.is_travis() else None
        public_pem_file = os.path.join(self.resources_dir, 'unit-test-public.pem') if Signing.is_travis() else None
        signer = Signing(event, MockLogger(), s3_handler=s3_handler, dynamodb_handler=dbHandler,
                                           private_pem_file=private_pem_file, public_pem_file=public_pem_file)
        result = signer.handle_s3_trigger()
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

        private_pem_file = os.path.join(self.resources_dir, 'alt-private.pem')
        public_pem_file = os.path.join(self.resources_dir, 'unit-test-public.pem')
        signer = Signing(event, MockLogger(), s3_handler=s3_handler, dynamodb_handler=dbHandler,
                         private_pem_file=private_pem_file, public_pem_file=public_pem_file)
        result = signer.handle_s3_trigger()

        self.assertTrue(result)

        self.assertNotIn('{}.sig'.format(file_key), s3_handler._uploads)

    # @unittest.skipIf(Signing.is_travis(), 'Skipping test_signing_handler_s3 on Travis CI.')
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
        db_handler = MockDynamodbHandler(Signing.dynamodb_table_name)
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
        private_pem_file = os.path.join(self.resources_dir, 'unit-test-private.pem') if Signing.is_travis() else None
        public_pem_file = os.path.join(self.resources_dir, 'unit-test-public.pem') if Signing.is_travis() else None
        signer = Signing(event, MockLogger(), s3_handler, db_handler, private_pem_file=private_pem_file, public_pem_file=public_pem_file)
        result = signer.handle_s3_trigger()
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

        private_pem_file = os.path.join(self.resources_dir, 'unit-test-private.pem') if Signing.is_travis() else None
        public_pem_file = os.path.join(self.resources_dir, 'unit-test-public.pem') if Signing.is_travis() else None
        signer = Signing(event, MockLogger(), s3_handler=s3Handler, dynamodb_handler=dbHandler,
                         private_pem_file=private_pem_file, public_pem_file=public_pem_file)
        result = signer.handle_s3_trigger()

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
        event.pop('Records', None)

        dbHandler = MockDynamodbHandler()
        # item = TestSigning.create_db_item()
        # dbHandler.insert_item(item)

        private_pem_file = os.path.join(self.resources_dir, 'unit-test-private.pem') if Signing.is_travis() else None
        public_pem_file = os.path.join(self.resources_dir, 'unit-test-public.pem') if Signing.is_travis() else None
        signer = Signing(event, MockLogger(), s3_handler=None, dynamodb_handler=dbHandler,
                                           private_pem_file=private_pem_file, public_pem_file=public_pem_file)
        result = signer.handle_s3_trigger()

        self.assertFalse(result)