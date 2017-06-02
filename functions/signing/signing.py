from __future__ import unicode_literals
import codecs
import inspect
import json
import os
import shlex
import shutil
import tempfile
from aws_tools.s3_handler import S3Handler
from aws_tools.dynamodb_handler import DynamoDBHandler
from aws_decrypt import decrypt_file
from base64 import b64decode
from general_tools.file_utils import write_file
from general_tools.url_utils import download_file
from subprocess import Popen, PIPE


class Signing(object):
    dynamodb_table_name = 'd43-catalog-in-progress'

    def __init__(self, event, logger, s3_handler=None, dynamodb_handler=None, private_pem_file=None,
                                 public_pem_file=None):
        """
        Handles the signing of a file on S3
        :param self:
        :param dict event:
        :param logger:
        :param class s3_handler: This is passed in so it can be mocked for unit testing
        :param class dynamodb_handler: This is passed in so it can be mocked for unit testing
        :param string private_pem_file: This is passed in so it can be mocked for unit testing
        :param string public_pem_file: This is passed in so it can be mocked for unit testing
        :return: bool
        """
        self.event = event
        self.logger = logger
        self.cdn_bucket_name = self.retrieve(event, 'api_bucket')

        if not s3_handler:
            self.cdn_handler = S3Handler(self.cdn_bucket_name)
        else:
            self.cdn_handler = s3_handler

        self.temp_dir = tempfile.mkdtemp(prefix='signing_')

        self.private_pem_file = private_pem_file
        self.public_pem_file = public_pem_file

        if not dynamodb_handler:
            self.db_handler = DynamoDBHandler(Signing.dynamodb_table_name)
        else:
            self.db_handler = dynamodb_handler

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

            raise RuntimeError(err)

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
    def retrieve(dictionary, key, dict_name=None):
        """
        Retrieves a value from a dictionary, raising an error message if the
        specified key is not valid
        :param dict dictionary:
        :param any key:
        :param str|unicode dict_name: name of dictionary, for error message
        :return: value corresponding to key
        """
        if key in dictionary:
            return dictionary[key]
        dict_name = "dictionary" if dict_name is None else dict_name
        raise Exception('{k} not found in {d}'.format(k=repr(key), d=dict_name))

    def handle_s3_trigger(self):
        items = self.db_handler.query_items()
        try:
            for item in items:
                repo_name = item['repo_name']
                try:
                    package = json.loads(item['package'])
                except Exception as e:
                    print('Skipping {}. Bad Manifest: {}'.format(repo_name, e))
                    continue

                if repo_name == "catalogs" or repo_name == 'localization' or repo_name == 'versification':
                    self.process_db_item(item, package)
            return True
        finally:
            if os.path.isdir(self.temp_dir):
                shutil.rmtree(self.temp_dir, ignore_errors=True)


    def process_db_item(self, item, package):
        if 'formats' in package:
            for format in package['formats']:
                # process resource formats
                self.process_format(item, package, format)

        for project in package['projects']:
            if 'formats' in project:
                for format in project['formats']:
                    # process project formats
                    self.process_format(item, package, format)

        record_keys = {'repo_name': item['repo_name']}
        self.db_handler.update_item(record_keys, {'package': json.dumps(package, sort_keys=True)})

    def process_format(self, item, package, format):
        if 'signature' in format and format['signature']:
            return True

        base_name = os.path.basename(format['url'])
        dc = package['dublin_core']
        upload_key = '{0}/{1}/v{2}/{3}'.format(dc['language']['identifier'],
                                               dc['identifier'].split('-')[-1],
                                               dc['version'],
                                               base_name)
        upload_sig_key = '{}.sig'.format(upload_key)
        key = 'temp/{}/{}/()'.format(item['repo_name'], item['commit_id'], base_name)

        # copy the file to a temp directory
        file_to_sign = os.path.join(self.temp_dir, base_name)
        try:
            self.cdn_handler.download_file(key, file_to_sign)
        except Exception as e:
            if self.logger:
                self.logger.warning('The file "{0}" could not be downloaded'.format(base_name))
            return False  # removes files here

        # sign the file
        sig_file = Signing.sign_file(file_to_sign, pem_file=self.private_pem_file)

        # verify the file
        try:
            Signing.verify_signature(file_to_sign, sig_file, pem_file=self.public_pem_file)
        except RuntimeError:
            if self.logger:
                self.logger.warning('The signature was not successfully verified.')
            return False  # remove files here

        # upload files
        self.cdn_handler.upload_file(file_to_sign, upload_key)
        self.cdn_handler.upload_file(sig_file, upload_sig_key)

        # add the url of the sig file to the format
        format['signature'] = '{}.sig'.format(format['url'])

        return True

    @staticmethod
    def legacy_handle_s3_trigger(event, logger, s3_handler=None, dynamodb_handler=None, private_pem_file=None, public_pem_file=None):
        """
        Handles the signing of a file on S3
        :param dict event:
        :param logger:
        :param class s3_handler: This is passed in so it can be mocked for unit testing
        :param class dynamodb_handler: This is passed in so it can be mocked for unit testing
        :param string private_pem_file: This is passed in so it can be mocked for unit testing
        :param string public_pem_file: This is passed in so it can be mocked for unit testing
        :return: bool
        """

        # this shouldn't happen, but just in case
        if 'Records' not in event or not len(event['Records']):
            if logger:
                logger.warning('The signing script was triggered but no `Records` were found.')
            return False

        temp_dir = tempfile.mkdtemp(prefix='signing_')

        try:
            for record in event['Records']:

                # check if this is an S3 bucket record
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
                if not s3_handler:
                    cdn_handler = S3Handler(cdn_bucket_name)
                else:
                    cdn_handler = s3_handler

                # get the file name
                base_name = os.path.basename(key)

                # copy the file to a temp directory
                file_to_sign = os.path.join(temp_dir, base_name)
                try:
                    cdn_handler.download_file(key, file_to_sign)
                except Exception as e:
                    if logger:
                        logger.warning('The file "{0}" could not be downloaded'.format(base_name))
                    return False # removes files here

                # sign the file
                sig_file = Signing.sign_file(file_to_sign, pem_file=private_pem_file)

                # verify the file
                try:
                    Signing.verify_signature(file_to_sign, sig_file, pem_file=public_pem_file)

                except RuntimeError:
                    if logger:
                        logger.warning('The signature was not successfully verified.')
                    return False  # remove files here

                # update the record in DynamoDB
                key_parts = key.split('/')  # test/repo-name/commit/file.name
                repo_name = key_parts[1]
                commit_id = key_parts[2]

                # retrieve id's from project file uploads
                resource_id = None
                project_id = None
                if len(key_parts) == 5:
                    resource_id = key_parts[3]
                    project_id = key_parts[4].split('.')[0]

                if not dynamodb_handler:
                    db_handler = DynamoDBHandler(Signing.dynamodb_table_name)
                else:
                    db_handler = dynamodb_handler
                record_keys = {'repo_name': repo_name}
                row = db_handler.get_item(record_keys)

                if not row or row['commit_id'] != commit_id:
                    return False  # Remove files here

                # verify this is the correct commit
                if row['commit_id'] != commit_id:
                    return False

                manifest = json.loads(row['package'])
                dc = manifest['dublin_core']

                # upload the file and the sig file to the S3 bucket
                if resource_id and project_id:
                    upload_key = '{0}/{1}/v{2}/{3}/{4}'.format(dc['language']['identifier'],
                                                           dc['identifier'].split('-')[-1],
                                                           dc['version'],
                                                           resource_id,
                                                           os.path.basename(key))
                else:
                    upload_key = '{0}/{1}/v{2}/{3}'.format(dc['language']['identifier'],
                                                           dc['identifier'].split('-')[-1],
                                                           dc['version'],
                                                           os.path.basename(key))
                upload_sig_key = '{}.sig'.format(upload_key)

                cdn_handler.upload_file(file_to_sign, upload_key)
                cdn_handler.upload_file(sig_file, upload_sig_key)

                # add the url of the sig file to the format item
                if project_id:
                    # project file
                    for project in manifest['projects']:
                        if 'formats' in project:
                            for fmt in project['formats']:
                                if not fmt['signature'] and fmt['url'].endswith(upload_key):
                                    fmt['signature'] = '{}.sig'.format(fmt['url'])
                                    break
                else:
                    # resource file
                    for fmt in manifest['formats']:
                        if not fmt['signature'] and fmt['url'].endswith(upload_key):
                            fmt['signature'] = '{}.sig'.format(fmt['url'])
                            break

                db_handler.update_item(record_keys, {'package': json.dumps(manifest, sort_keys=True)})

            return True

        finally:
            if os.path.isdir(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
