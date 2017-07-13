from __future__ import unicode_literals, print_function
import os
import shutil
import tempfile
import unittest
from unittest import TestCase
from functions.signing import Signer
from tools.test_utils import is_travis


class TestSigner(TestCase):

    def setUp(self):
        pem_file = os.path.normpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '../../functions/signing/uW-sk.enc'))
        self.signer = Signer(pem_file)
        self.resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')
        self.temp_dir = tempfile.mkdtemp(prefix='signing_tests_')
        self.s3keys = []

    def tearDown(self):
        # clean up local temp files
        if os.path.isdir(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

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
        sig_file_name = self.signer.sign_file(source_file,
                                          pem_file=os.path.join(self.resources_dir, 'unit-test-private.pem'))

        # check that .sig file DOES exist now
        self.assertEqual(sig_file, sig_file_name)
        self.assertTrue(os.path.isfile(sig_file))

        # verify the .sig file is correct
        self.assertTrue(self.signer.verify_signature(source_file, sig_file_name,
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
        sig_file_name = self.signer.sign_file(source_file,
                                          pem_file=os.path.join(self.resources_dir, 'unit-test-private.pem'))

        # check that .sig file DOES exist now
        self.assertEqual(sig_file, sig_file_name)
        self.assertTrue(os.path.isfile(sig_file))

        # this should raise an exception
        with self.assertRaises(Exception) as context:
            self.assertTrue(self.signer.verify_signature(source_file, sig_file_name,
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
        sig_file_name = self.signer.sign_file(source_file,
                                          pem_file=os.path.join(self.resources_dir, 'unit-test-private.pem'))

        # check that .sig file DOES exist now
        self.assertEqual(sig_file, sig_file_name)
        self.assertTrue(os.path.isfile(sig_file))

        # this should raise an exception
        with self.assertRaises(Exception) as context:
            self.assertTrue(self.signer.verify_signature(source_file, sig_file_name,
                                                     pem_file=os.path.join(self.resources_dir,
                                                                           'alt-private.pem')))

        self.assertIn('key file', str(context.exception))

    @unittest.skipIf(is_travis(), 'Skipping test_sign_file_with_live_certificate on Travis CI.')
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
        sig_file_name = self.signer.sign_file(source_file)

        # check that .sig file DOES exist now
        self.assertEqual(sig_file, sig_file_name)
        self.assertTrue(os.path.isfile(sig_file))

        # verify the .sig file is correct
        self.assertTrue(self.signer.verify_signature(source_file, sig_file_name))

    def test_get_default_pem_file(self):

        if is_travis():
            with self.assertRaises(Exception) as context:
                self.signer._get_default_pem_file()

            self.assertIn(str(context.exception), ['Not able to decrypt the pem file.', 'You must specify a region.'])

        else:
            pem_file = self.signer._get_default_pem_file()

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
            self.signer.sign_file(source_file, pem_file=os.path.join(self.resources_dir, 'none.pem'))

        self.assertIn('key file', str(context.exception))
