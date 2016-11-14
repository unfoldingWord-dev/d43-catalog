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


class TestSigning(TestCase):

    resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

    class MockLogger(object):

        @staticmethod
        def warning(message):
            print('WARNING: {}'.format(message))

    class MockS3Handler(object):

        def __init__(self, bucket_name):
            self.bucket_name = bucket_name

        @staticmethod
        def download_file(key, local_file):
            shutil.copy(key, local_file)

        @staticmethod
        def upload_file(path, key):
            shutil.copy(path, key)

    class MockDynamodbHandler(object):

        def __init__(self, table_name):
            self.table_name = table_name

        # noinspection PyUnusedLocal
        @staticmethod
        def get_item(record_keys):
            return load_json_object(os.path.join(TestSigning.resources_dir, 'dynamodb_record.json'))

        # noinspection PyUnusedLocal
        @staticmethod
        def update_item(record_keys, row):
            return True

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix='unitTest_')

    def tearDown(self):
        if os.path.isdir(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    @staticmethod
    def create_event():

        event = {'Records': []}

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

    def test_signing_handler_text(self):

        # copy zip file to temp directory
        test_txt = os.path.join(self.temp_dir, 'test.txt')
        shutil.copy(os.path.join(self.resources_dir, 'test.txt'), test_txt)

        # mock a lambda event object
        event = self.create_event()
        event['Records'].append(self.create_s3_record('test-cdn_bucket', test_txt))

        # test when S3 file exists
        self.assertTrue(os.path.isfile(test_txt))

        private_pem_file = os.path.join(self.resources_dir, 'unit-test-private.pem') if Signing.is_travis() else None
        public_pem_file = os.path.join(self.resources_dir, 'unit-test-public.pem') if Signing.is_travis() else None
        result = Signing.handle_s3_trigger(event, self.MockS3Handler, self.MockDynamodbHandler, self.MockLogger(),
                                           private_pem_file=private_pem_file, public_pem_file=public_pem_file)
        self.assertTrue(result)

        expected_file = os.path.join(self.temp_dir, 'test.sig')
        self.assertTrue(os.path.isfile(expected_file))

    @unittest.skipIf(Signing.is_travis(), 'Skipping test_signing_handler_s3 on Travis CI.')
    def test_signing_handler_s3(self):

        # create test folder on S3
        commit_id = str(uuid.uuid4())[-10:]
        test_folder = 'temp/unit-test/{}'.format(commit_id)
        s3_handler = S3Handler('test-cdn.door43.org')
        s3_key = '{}/test.zip'.format(test_folder)
        s3_handler.upload_file(os.path.join(self.resources_dir, 'test.zip'), s3_key)

        # create a record in dynamodb
        db_handler = DynamoDBHandler(Signing.dynamodb_table_name)
        db_handler.insert_item({
            'repo_name': 'unit-test',
            'commit_id': commit_id,
            'data': json.dumps(load_json_object(os.path.join(self.resources_dir, 'manifest.json')), sort_keys=True),
            'timestamp': datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            'files': [s3_key, ],
            'language': 'en'
        })

        # mock a lambda event object
        event = self.create_event()
        event['Records'].append(self.create_s3_record(s3_handler.bucket_name, s3_key))

        # do the signing
        result = Signing.handle_s3_trigger(event, S3Handler, DynamoDBHandler, self.MockLogger())
        self.assertTrue(result)

        # check that the sig file was found
        s3_sig = '{}/test.sig'.format(test_folder)
        expected_file = os.path.join(self.temp_dir, 'test.sig')
        s3_handler.download_file(s3_sig, expected_file)
        self.assertTrue(os.path.isfile(expected_file))

        # check the dynamodb record
        row_keys = {'repo_name': 'unit-test', 'commit_id': commit_id}
        row = db_handler.get_item(row_keys)

        found_file = [f for f in row['files'] if f.endswith('test.sig')]
        self.assertGreater(len(found_file), 0, 'The .sig file was not found in the files list.')

        # add the url of the sig file to the format item
        data = json.loads(row['data'])
        found_file = [fmt['sig'] for fmt in data['formats'] if fmt['sig'].endswith('test.sig')]
        self.assertGreater(len(found_file), 0, 'The .sig file was not found in the formats list.')

        # clean up
        db_handler.delete_item(row_keys)
        s3_handler.delete_file(s3_key)
        s3_handler.delete_file(s3_sig)

    def test_signing_handler_zip(self):

        # copy zip file to temp directory
        test_zip = os.path.join(self.temp_dir, 'test.zip')
        shutil.copy(os.path.join(self.resources_dir, 'test.zip'), test_zip)

        # mock a lambda event object
        event = self.create_event()
        event['Records'].append(self.create_s3_record('test-cdn_bucket', test_zip))

        # test when S3 file exists
        self.assertTrue(os.path.isfile(test_zip))

        private_pem_file = os.path.join(self.resources_dir, 'unit-test-private.pem') if Signing.is_travis() else None
        public_pem_file = os.path.join(self.resources_dir, 'unit-test-public.pem') if Signing.is_travis() else None
        result = Signing.handle_s3_trigger(event, self.MockS3Handler, self.MockDynamodbHandler, self.MockLogger(),
                                           private_pem_file=private_pem_file, public_pem_file=public_pem_file)
        self.assertTrue(result)

        expected_file = os.path.join(self.temp_dir, 'test.sig')
        self.assertTrue(os.path.isfile(expected_file))

        # test when S3 file does not exist

        # test successful sig file generation

        # test unsuccessful sig file generation

        # test updating DynamoDB record

    def test_signing_handler_no_records(self):

        # mock a lambda event object
        event = self.create_event()
        event.pop('Records', None)

        private_pem_file = os.path.join(self.resources_dir, 'unit-test-private.pem') if Signing.is_travis() else None
        public_pem_file = os.path.join(self.resources_dir, 'unit-test-public.pem') if Signing.is_travis() else None
        result = Signing.handle_s3_trigger(event, self.MockS3Handler, self.MockDynamodbHandler, self.MockLogger(),
                                           private_pem_file=private_pem_file, public_pem_file=public_pem_file)
        self.assertFalse(result)

    def test_signing_handler_no_s3(self):

        # mock a lambda event object
        event = self.create_event()
        event['Records'].append({'one': 'two'})

        private_pem_file = os.path.join(self.resources_dir, 'unit-test-private.pem') if Signing.is_travis() else None
        public_pem_file = os.path.join(self.resources_dir, 'unit-test-public.pem') if Signing.is_travis() else None
        result = Signing.handle_s3_trigger(event, self.MockS3Handler, self.MockDynamodbHandler, self.MockLogger(),
                                           private_pem_file=private_pem_file, public_pem_file=public_pem_file)
        self.assertFalse(result)
