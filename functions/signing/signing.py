from __future__ import unicode_literals
import codecs
import inspect
import json
import os
import shlex
import shutil
import tempfile
from aws_decrypt import decrypt_file
from base64 import b64decode
from general_tools.file_utils import write_file
from general_tools.url_utils import download_file
from subprocess import Popen, PIPE


class Signing(object):

    dynamodb_table_name = 'd43-catalog-in-progress'

    @staticmethod
    def is_travis():
        return 'TRAVIS' in os.environ and os.environ['TRAVIS'] == 'true'

    @staticmethod
    def sign_file(file_to_sign, pem_file=None):
        """
        Generates a .sig file and returns the full file name of the .sig file
        :param str|unicode file_to_sign:
        :param str|unicode|None pem_file:
        :return: str|unicode The full file name of the .sig file
        """
        # if pem file was not passed, use the default one
        if not pem_file:
            pem_file = Signing.get_default_pem_file()

        print(pem_file)

        # # read the file contents
        # with codecs.open(file_to_sign, 'r', encoding='utf-8') as in_file:
        #     content = in_file.read()

        # use openssl to sign the content
        sha384_file = file_to_sign + '.sha384'
        sign_com = 'openssl dgst -sha384 -sign {0} -out {1} {2}'.format(pem_file, sha384_file, file_to_sign)
        command = shlex.split(sign_com)
        com = Popen(command, shell=False, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        out, err = com.communicate()

        if err:
            raise Exception(err)

        # base64 encode the signature
        file_name_without_extension = os.path.splitext(file_to_sign)[0]
        sig_file_name = '{}.sig'.format(file_name_without_extension)
        sign_com = 'openssl base64 -in {0} -out {1}'.format(sha384_file, sig_file_name)
        command = shlex.split(sign_com)
        com = Popen(command, shell=False, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        out, err = com.communicate()

        if err:
            raise Exception(err)

        # get the base64 encoded signature
        with codecs.open(sig_file_name, 'r', encoding='utf-8') as in_file:
            signed_content = in_file.read()

        # save the signed content
        file_content = []
        signature = {'si': 'uW', 'sig': signed_content}
        file_content.append(signature)
        write_file(sig_file_name, file_content)

        return sig_file_name

    @staticmethod
    def verify_signature(content_file, sig_file, pem_file=None):
        """
        Verify that the file content has not changed since it was signed
        :param str|unicode content_file:
        :param str|unicode sig_file:
        :param str|unicode|None pem_file:
        :return:
        """

        temp_dir = tempfile.mkdtemp(prefix='tempVerify_')

        try:

            # if pem file was not passed, use the default one
            if not pem_file:
                pem_file = os.path.join(temp_dir, 'uW-vk.pem')
                download_file('https://pki.unfoldingword.org/uW-vk.pem', pem_file)

            # get the uW signature from the sig file
            with codecs.open(sig_file, 'r', 'utf-8-sig') as in_file:
                sig_file_content = json.loads(in_file.read())

            signature = [x['sig'] for x in sig_file_content if x['si'] == 'uW'][0]
            signature_path = os.path.join(temp_dir, 'signature.sig')

            # save the signature to a temp file
            with open(signature_path, str('w')) as out_file:
                out_file.write(b64decode(signature))

            # Use openssl to verify signature
            command_str = 'openssl dgst -sha384 -verify {0} -signature {1} {2}'.format(pem_file, signature_path,
                                                                                       content_file)
            command = shlex.split(command_str)
            com = Popen(command, shell=False, stdin=PIPE, stdout=PIPE, stderr=PIPE)
            out, err = com.communicate()

            if com.returncode == 0:
                return True

            if err:
                raise Exception(err)

            # we should never get here, but just in case the return code is not zero
            # and no error was reported, just return false
            return False

        finally:
            # clean up temp dir, if used
            if temp_dir and os.path.isdir(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

    @staticmethod
    def get_default_pem_file():
        """
        Decrypts the default pem file and returns the full file name
        :return: str|unicode
        """
        this_dir = os.path.dirname(inspect.stack()[0][1])
        enc_file = os.path.join(this_dir, 'uW-sk.enc')
        pem_file = os.path.join(tempfile.gettempdir(), 'uW-sk.pem')
        result = decrypt_file(enc_file, pem_file)

        if not result:
            raise Exception('Not able to decrypt the pem file.')

        return pem_file

    @staticmethod
    def handle_s3_trigger(event, s3_handler, dynamodb_handler, logger, private_pem_file=None, public_pem_file=None):
        """
        Handles the signing of a file on S3
        :param dict event:
        :param class s3_handler: This is passed in so it can be mocked for unit testing
        :param class dynamodb_handler: This is passed in so it can be mocked for unit testing
        :param logger:
        :param string private_pem_file:
        :param string public_pem_file:
        :return: bool
        """

        # this shouldn't happen, but just in case
        if 'Records' not in event:
            if logger:
                logger.warning('The signing script was triggered but no `Records` were found.')
            return False

        temp_dir = tempfile.mkdtemp(prefix='signing_')

        try:
            for record in event['Records']:

                # check if this is S3 bucket record
                if 's3' not in record:
                    if logger:
                        logger.warning('The record is not an S3 bucket.')
                    return False

                bucket_name = record['s3']['bucket']['name']
                key = record['s3']['object']['key']

                if key.endswith('.sig'):
                    return False

                # detect test bucket
                is_test = bucket_name.startswith('test-')

                cdn_bucket_name = ('test-' if is_test else '') + 'cdn.door43.org'
                cdn_handler = s3_handler(cdn_bucket_name)

                # get the file name
                base_name = os.path.basename(key)

                # copy the file to a temp directory
                file_to_sign = os.path.join(temp_dir, base_name)
                cdn_handler.download_file(key, file_to_sign)

                # sign the file
                sig_file = Signing.sign_file(file_to_sign, pem_file=private_pem_file)

                # verify the file
                verified = Signing.verify_signature(file_to_sign, sig_file, pem_file=public_pem_file)

                if not verified:
                    if logger:
                        logger.warning('The signature was not successfully verified.')
                    return False  # remove files here

                # update the record in DynamoDB
                key_parts = key.split('/')  # test/repo-name/commit/file.name
                repo_name = key_parts[1]
                commit_id = key_parts[2]
                db_handler = dynamodb_handler(Signing.dynamodb_table_name)
                record_keys = {'repo_name': repo_name}
                row = db_handler.get_item(record_keys)

                if not row or row['commit_id'] != commit_id:
                    return False  # Remove files here

                package = json.loads(row['package'])

                # upload the file and the sig file to the S3 bucket
                upload_key = '{0}/{1}/v{2}/{3}'.format(package['language']['slug'],
                                                       package['resource']['slug'].split('-')[1],
                                                       package['resource']['status']['version'],
                                                       os.path.basename(key))
                upload_sig_key = '{}.sig'.format(upload_key)

                cdn_handler.upload_file(file_to_sign, upload_key)
                cdn_handler.upload_file(sig_file, upload_sig_key)

                # add the url of the sig file to the format item
                for fmt in package['resource']['formats']:
                    if not fmt['sig'] and fmt['url'].endswith(upload_key):
                        fmt['sig'] = '{}.sig'.format(fmt['url'])
                        break

                db_handler.update_item(record_keys, {'package': json.dumps(package, sort_keys=True)})

            return True

        finally:
            if os.path.isdir(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
