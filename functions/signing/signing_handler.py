from __future__ import unicode_literals
import json
import os
import shutil
import tempfile
import time
from d43_aws_tools import S3Handler, DynamoDBHandler
from tools.dict_utils import read_dict
from tools.url_utils import url_exists, download_file


class SigningHandler(object):
    dynamodb_table_name = 'd43-catalog-in-progress'

    def __init__(self, event, logger, signer, s3_handler=None, dynamodb_handler=None, download_handler=None, url_exists_handler=None):
        """
        Handles the signing of a file on S3
        :param self:
        :param dict event:
        :param logger:
        :param class signer: This handles all the signer operations
        :param class s3_handler: This is passed in so it can be mocked for unit testing
        :param class dynamodb_handler: This is passed in so it can be mocked for unit testing
        :return: bool
        """
        # self.event = event
        self.cdn_bucket = read_dict(event, 'cdn_bucket', 'Environment Vars')
        self.cdn_url = read_dict(event, 'cdn_url', 'Environment Vars')

        self.logger = logger
        self.signer = signer
        if not s3_handler:
            self.cdn_handler = S3Handler(self.cdn_bucket)
        else:
            self.cdn_handler = s3_handler

        self.temp_dir = tempfile.mkdtemp(prefix='signing_')

        if not dynamodb_handler:
            self.db_handler = DynamoDBHandler(SigningHandler.dynamodb_table_name)
        else:
            self.db_handler = dynamodb_handler
        if not download_handler:
            self.download_file = download_file
        else:
            self.download_file = download_handler
        if not url_exists_handler:
            self.url_exists = url_exists
        else:
            self.url_exists = url_exists_handler

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
                    if self.logger:
                        self.logger.warning('Skipping {}. Bad Manifest: {}'.format(repo_name, e))
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
                (already_signed, newly_signed, _) = self.process_format(item, format)
                if newly_signed:
                    was_signed = True
                if not(already_signed or newly_signed):
                    fully_signed = False
        for project in package['projects']:
            if 'formats' in project:
                for format in project['formats']:
                    # process project formats
                    (already_signed, newly_signed, _) = self.process_format(item, format)
                    if newly_signed:
                        was_signed = True
                    if not (already_signed or newly_signed):
                        fully_signed = False

                    # process format chapters
                    if 'chapters' in format:
                        sanitized_chapters = []
                        for chapter in format['chapters']:
                            # TRICKY: only process/keep chapters that actually have a valid url
                            if 'url' not in chapter or not self.url_exists(chapter['url']):
                                continue

                            (already_signed, newly_signed) = self.process_format_chapter(item, chapter)
                            sanitized_chapters.append(chapter)
                            if newly_signed:
                                was_signed = True
                            if not (already_signed or newly_signed):
                                fully_signed = False

                        format['chapters'] = sanitized_chapters


        if was_signed or fully_signed:
            print('[INFO] recording signatures')
            record_keys = {'repo_name': item['repo_name']}
            time.sleep(5)
            self.db_handler.update_item(record_keys, {
                'package': json.dumps(package, sort_keys=True),
                'signed': fully_signed
            })

    def process_format_chapter(self, item, chapter):
        """
        Signs a format chapter
        :param item:
        :param chapter:
        :return: (already_signed, newly_signed, meta)
        """
        (already_signed, newly_signed, file_to_sign) = self.process_format(item, chapter)

        if not already_signed and newly_signed and file_to_sign:
            chapter['size'] = os.path.getsize(file_to_sign)
            chapter['length'] = 0 # TODO: if this is an audio file we need to get the audio length
            chapter['modified'] = ''

        return (already_signed, newly_signed)


    def process_format(self, item, format):
        """
        Performs the signing on the format object.
        Files outside of the cdn will not be signed
        :param item:
        :param format:
        :return: (already_signed, newly_signed, file_to_sign)
        """
        if 'signature' in format and format['signature']:
            return (True, False, None)
        else:
            print('[INFO] Signing {}'.format(format['url']))

        base_name = os.path.basename(format['url'])
        file_to_sign = os.path.join(self.temp_dir, base_name)

        # extract cdn key from url
        src_key = format['url'][len(self.cdn_url):].lstrip('/')
        sig_key = '{}.sig'.format(src_key)

        # TRICKY: files to be signed are stored in a temp directory
        src_temp_key = 'temp/{}/{}/{}'.format(item['repo_name'], item['commit_id'], src_key)

        # verify url is on cdn
        if not format['url'].startswith(self.cdn_url):
            # This allows media to be hosted on third party servers
            print('WARNING: cannot sign files outside of the cdn. Guessing signature path for '.format(format['url']))
            format['signature'] = '{}.sig'.format(format['url'])
            try:
                self.download_file(format['url'], file_to_sign)
            except Exception as e:
                return (True, True, None)
            return (True, True, file_to_sign)

        # download file
        try:
            self.cdn_handler.download_file(src_temp_key, file_to_sign)
        except Exception as e:
            if self.logger:
                self.logger.warning('The file "{}" could not be downloaded: {}'.format(base_name, e))
            return (False, False, None)

        sig_file = self.signer.sign_file(file_to_sign)
        try:
            self.signer.verify_signature(file_to_sign, sig_file)
        except RuntimeError:
            if self.logger:
                self.logger.warning('The signature was not successfully verified.')
            return (False, False, None)

        # upload files
        self.cdn_handler.upload_file(file_to_sign, src_key)
        self.cdn_handler.upload_file(sig_file, sig_key)

        # add the url of the sig file to the format
        format['signature'] = '{}.sig'.format(format['url'])

        return (False, True, file_to_sign)