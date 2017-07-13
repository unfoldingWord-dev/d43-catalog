from __future__ import unicode_literals
import json
import os
import shutil
import tempfile
import time
from d43_aws_tools import S3Handler, DynamoDBHandler
from tools.dict_utils import read_dict


class SigningHandler(object):
    dynamodb_table_name = 'd43-catalog-in-progress'

    def __init__(self, event, logger, signer, s3_handler=None, dynamodb_handler=None, private_pem_file=None,
                                 public_pem_file=None):
        """
        Handles the signing of a file on S3
        :param self:
        :param dict event:
        :param logger:
        :param class signer: This handles all the signer operations
        :param class s3_handler: This is passed in so it can be mocked for unit testing
        :param class dynamodb_handler: This is passed in so it can be mocked for unit testing
        :param string private_pem_file: This is passed in so it can be mocked for unit testing
        :param string public_pem_file: This is passed in so it can be mocked for unit testing
        :return: bool
        """
        # self.event = event
        self.logger = logger
        self.cdn_bucket_name = read_dict(event, 'cdn_bucket', 'Environment Vars')

        if not s3_handler:
            self.cdn_handler = S3Handler(self.cdn_bucket_name)
        else:
            self.cdn_handler = s3_handler

        self.temp_dir = tempfile.mkdtemp(prefix='signing_')

        self.private_pem_file = private_pem_file
        self.public_pem_file = public_pem_file

        if not dynamodb_handler:
            self.db_handler = DynamoDBHandler(SigningHandler.dynamodb_table_name)
        else:
            self.db_handler = dynamodb_handler
        self.signer = signer

    def __del__(self):
        if hasattr(self, 'temp_dir') and os.path.isdir(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def run(self):
        items = self.db_handler.query_items({
            'signed': False
        })
        try:
            for item in items:
                repo_name = item['repo_name']
                try:
                    package = json.loads(item['package'])
                except Exception as e:
                    print('Skipping {}. Bad Manifest: {}'.format(repo_name, e))
                    continue

                if repo_name != "catalogs" and repo_name != 'localization' and repo_name != 'versification':
                    self.process_db_item(item, package)
            return len(items) > 0
        finally:
            if os.path.isdir(self.temp_dir):
                shutil.rmtree(self.temp_dir, ignore_errors=True)


    def process_db_item(self, item, package):
        was_signed = False
        fully_signed = True
        print('[INFO] Processing {}'.format(item['repo_name']))
        if 'formats' in package:
            for format in package['formats']:
                # process resource formats
                (already_signed, newly_signed) = self.process_format(item, package, format)
                if newly_signed:
                    was_signed = True
                if not(already_signed or newly_signed):
                    fully_signed = False
        for project in package['projects']:
            if 'formats' in project:
                for format in project['formats']:
                    # process project formats
                    (already_signed, newly_signed) = self.process_format(item, package, format)
                    if newly_signed:
                        was_signed = True
                    if not (already_signed or newly_signed):
                        fully_signed = False

                    # process format chapters
                        if 'chapters' in format:
                            for chapter in format['chapters']:
                                (already_signed, newly_signed, meta) = self.process_format_chapter(item, package, chapter)
                                if newly_signed:
                                    was_signed = True
                                    chapter.update(meta)
                                if not (already_signed or newly_signed):
                                    fully_signed = False


        if was_signed or fully_signed:
            print('[INFO] recording signatures')
            record_keys = {'repo_name': item['repo_name']}
            time.sleep(5)
            self.db_handler.update_item(record_keys, {
                'package': json.dumps(package, sort_keys=True),
                'signed': fully_signed
            })

    def process_format_chapter(self, item, package, format):
        """
        Signs a format chapter
        :param item:
        :param package:
        :param chapter:
        :return: (already_signed, newly_signed, meta)
        """
        # TODO: this is mostly a copy of process_format
        if 'signature' in format and format['signature']:
            return (True, False)
        else:
            print('[INFO] Signing {}'.format(format['url']))

        base_name = os.path.basename(format['url'])
        dc = package['dublin_core']
        upload_key = '{0}/{1}/v{2}/{3}'.format(dc['language']['identifier'],
                                               dc['identifier'].split('-')[-1],
                                               dc['version'],
                                               base_name)
        upload_sig_key = '{}.sig'.format(upload_key)
        key = 'temp/{}/{}/{}'.format(item['repo_name'], item['commit_id'], base_name)

        # copy the file to a temp directory
        file_to_sign = os.path.join(self.temp_dir, base_name)
        try:
            self.cdn_handler.download_file(key, file_to_sign)
        except Exception as e:
            if self.logger:
                self.logger.warning('The file "{0}" could not be downloaded from {1}: {2}'.format(base_name, key, e))
            return (False, False)

        # sign the file
        sig_file = self.signer.sign_file(file_to_sign, pem_file=self.private_pem_file)

        # verify the file
        try:
            self.signer.verify_signature(file_to_sign, sig_file, pem_file=self.public_pem_file)
        except RuntimeError:
            if self.logger:
                self.logger.warning('The signature was not successfully verified.')
            return (False, False)

        # upload files
        self.cdn_handler.upload_file(file_to_sign, upload_key)
        self.cdn_handler.upload_file(sig_file, upload_sig_key)

        # add the url of the sig file to the format
        format['signature'] = '{}.sig'.format(format['url'])

        return (False, True, {
            "size": os.path.getsize(file_to_sign),
            "length": 0, # TODO: if this is an audio file we need to get the audio length
            "modified": ""
        })


    def process_format(self, item, package, format):
        """
        Signs a format
        :param item:
        :param package:
        :param format:
        :return: (already_signed, newly_signed)
        """
        if 'signature' in format and format['signature']:
            return (True, False)
        else:
            print('[INFO] Signing {}'.format(format['url']))

        base_name = os.path.basename(format['url'])
        dc = package['dublin_core']
        upload_key = '{0}/{1}/v{2}/{3}'.format(dc['language']['identifier'],
                                               dc['identifier'].split('-')[-1],
                                               dc['version'],
                                               base_name)
        upload_sig_key = '{}.sig'.format(upload_key)
        key = 'temp/{}/{}/{}'.format(item['repo_name'], item['commit_id'], base_name)

        # copy the file to a temp directory
        file_to_sign = os.path.join(self.temp_dir, base_name)
        try:
            self.cdn_handler.download_file(key, file_to_sign)
        except Exception as e:
            if self.logger:
                self.logger.warning('The file "{0}" could not be downloaded from {1}: {2}'.format(base_name, key, e))
            return (False, False)

        # sign the file
        sig_file = self.signer.sign_file(file_to_sign, pem_file=self.private_pem_file)

        # verify the file
        try:
            self.signer.verify_signature(file_to_sign, sig_file, pem_file=self.public_pem_file)
        except RuntimeError:
            if self.logger:
                self.logger.warning('The signature was not successfully verified.')
            return (False, False)

        # upload files
        self.cdn_handler.upload_file(file_to_sign, upload_key)
        self.cdn_handler.upload_file(sig_file, upload_sig_key)

        # add the url of the sig file to the format
        format['signature'] = '{}.sig'.format(format['url'])

        return (False, True)