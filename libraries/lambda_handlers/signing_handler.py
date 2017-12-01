from __future__ import unicode_literals

import datetime
import json
import logging
import os
import shutil
import tempfile
import time
import urlparse
import sys

from libraries.lambda_handlers.instance_handler import InstanceHandler
from d43_aws_tools import S3Handler, DynamoDBHandler
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from libraries.tools.build_utils import get_build_rules
from libraries.tools.date_utils import unix_to_timestamp, str_to_timestamp
from libraries.tools.file_utils import ext_to_mime, read_file, write_file
from libraries.tools.url_utils import url_exists, download_file, url_headers


class SigningHandler(InstanceHandler):
    max_file_size = 400000000  # 400mb

    def __init__(self, event, context, logger, signer, **kwargs):
        super(SigningHandler, self).__init__(event, context)

        env_vars = self.retrieve(event, 'stage-variables', 'payload')
        self.cdn_bucket = self.retrieve(env_vars, 'cdn_bucket', 'Environment Vars')
        self.cdn_url = self.retrieve(env_vars, 'cdn_url', 'Environment Vars')
        self.from_email = self.retrieve(env_vars, 'from_email', 'Environment Vars')
        self.to_email = self.retrieve(env_vars, 'to_email', 'Environment Vars')
        self.api_version = self.retrieve(env_vars, 'version', 'Environment Vars')
        self.api_bucket = self.retrieve(env_vars, 'api_bucket', 'Environment Vars')
        self.logger = logger  # type: logging._loggerClass
        self.signer = signer
        if 's3_handler' in kwargs:
            self.cdn_handler = kwargs['s3_handler']
        else:
            self.cdn_handler = S3Handler(self.cdn_bucket)  # pragma: no cover

        self.temp_dir = tempfile.mkdtemp(prefix='signing_')

        if 'dynamodb_handler' in kwargs:
            self.db_handler = kwargs['dynamodb_handler']
        else:
            self.db_handler = DynamoDBHandler('{}d43-catalog-in-progress'.format(self.stage_prefix()))  # pragma: no cover
        if 'download_handler' in kwargs:
            self.download_file = kwargs['download_handler']
        else:
            self.download_file = download_file  # pragma: no cover
        if 'url_exists_handler' in kwargs:
            self.url_exists = kwargs['url_exists_handler']
        else:
            self.url_exists = url_exists  # pragma: no cover
        if 'url_headers_handler' in kwargs:
            self.url_headers = kwargs['url_headers_handler']
        else:
            self.url_headers = url_headers  # pragma: no cover

    def __del__(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _safe_url_exists(self, url):
        """
        Safely checks if a url exists.
        :param url:
        :return:
        """
        try:
            return self.url_exists(url)
        except Exception as e:
            self.report_error('Failed to read url "{}": {}'.format(url, e.message))
            return False

    def _run(self):
        items = self.db_handler.query_items({
            'signed': False
        })
        try:
            for item in items:
                repo_name = item['repo_name']
                try:
                    package = json.loads(item['package'])
                except Exception as e:
                    self.report_error('Skipping {}. Bad Manifest: {}'.format(repo_name, e))
                    continue

                if repo_name != "catalogs" and repo_name != 'localization' and repo_name != 'versification':
                    self.process_db_item(item, package)

            found_items = len(items) > 0
            if not found_items and self.logger:
                self.logger.info('No items found for signing')
            return found_items
        except Exception as e:
            self.report_error('Failed processing an item: {}'.format(e.message))
            raise Exception, Exception(e), sys.exc_info()[2]
        finally:
            if os.path.isdir(self.temp_dir):
                shutil.rmtree(self.temp_dir, ignore_errors=True)


    def process_db_item(self, item, package):
        was_signed = False
        fully_signed = True
        self.logger.info('Processing {}'.format(item['repo_name']))
        if 'formats' in package:
            for format in package['formats']:
                # process resource formats
                (already_signed, newly_signed) = self.process_format(item, package['dublin_core'], None, format)
                if newly_signed:
                    was_signed = True
                if not(already_signed or newly_signed):
                    fully_signed = False
        for project in package['projects']:
            if 'formats' in project:
                for format in project['formats']:
                    # process project formats
                    (already_signed, newly_signed) = self.process_format(item, package['dublin_core'], project, format)
                    if newly_signed:
                        was_signed = True
                    if not (already_signed or newly_signed):
                        fully_signed = False

                    # process format chapters
                    if 'chapters' in format:
                        sanitized_chapters = []
                        for chapter in format['chapters']:
                            # TRICKY: only process/keep chapters that actually have a valid url
                            if 'url' not in chapter or not self._safe_url_exists(chapter['url']):
                                if 'url' not in chapter:
                                    missing_url = 'empty url'
                                else:
                                    missing_url = chapter['url']
                                self.logger.warning('Skipping chapter {}:{} missing url {}'.format(project['identifier'], chapter['identifier'], missing_url))
                                continue

                            (already_signed, newly_signed) = self.process_format(item, package['dublin_core'], project, chapter)
                            sanitized_chapters.append(chapter)
                            if newly_signed:
                                was_signed = True
                            if not (already_signed or newly_signed):
                                fully_signed = False

                        format['chapters'] = sanitized_chapters
                        # update format
                        if sanitized_chapters and not 'content=' in format['format'] and format['url'].endswith('zip'):
                            if format['chapters'][0]['url'].endswith('.mp3'):
                                format['format'] = 'application/zip; content=audio/mp3'
                            if format['chapters'][0]['url'].endswith('.mp4'):
                                format['format'] = 'application/zip; content=video/mp4'

        if was_signed or fully_signed:
            self.logger.debug('recording signatures')
            record_keys = {'repo_name': item['repo_name']}
            self.db_handler.update_item(record_keys, {
                'package': json.dumps(package, sort_keys=True),
                'signed': fully_signed
            })

    def process_format(self, item, dublin_core, project, format):
        """
        Performs the signing on the format object.
        Files outside of the cdn will not be signed
        :param item:
        :param dublin_core:
        :param project: this may be None.
        :param format:
        :return: (already_signed, newly_signed)
        """
        if 'signature' in format and format['signature']:
            return (True, False)
        else:
            self.logger.debug('Signing {}'.format(format['url']))

        base_name = os.path.basename(format['url'])
        file_to_sign = os.path.join(self.temp_dir, base_name)

        # extract cdn key from url
        url_info = urlparse.urlparse(format['url'])
        src_key = url_info.path.lstrip('/')
        sig_key = '{}.sig'.format(src_key)

        build_rules = get_build_rules(format, 'signing')

        # TRICKY: allow dev environments to download from prod environment
        valid_hosts = [self.cdn_bucket]
        if self.stage_prefix():
            if not self.cdn_bucket.startswith(self.stage_prefix()):
                self.logger.warning('Expected `cdn_bucket` to begin with the stage prefix ({}) but found {}'.format(self.stage_prefix(), self.cdn_bucket))
            prod_cdn_bucket = self.cdn_bucket.lstrip(self.stage_prefix())
            valid_hosts.append(prod_cdn_bucket)
            # TRICKY: force dev environments to handle prod content as external files
            # if format['url'].startswith(prod_cdn_url):
            #     build_rules.append('sign_given_url')

        # TRICKY: some html content is on the api
        if 'html_format' in build_rules:
            valid_hosts.append(self.api_bucket)
            prod_api_bucket = self.api_bucket.lstrip(self.stage_prefix())
            valid_hosts.append(prod_api_bucket)

        # verify url is on the cdn
        if not url_info.hostname in valid_hosts:
            # TODO: external media should be imported if it's not too big
            # This allows media to be hosted on third party servers
            format['signature'] = '{}.sig'.format(format['url'])
            self.logger.warning('cannot sign files outside of the cdn. The hosting provider should upload a signature to '.format(format['signature']))
            return (True, True)

        try:
            headers = self.url_headers(format['url'])
        except Exception as e:
            self.report_error('Could not read headers from {}: {}'.format(format['url'], e))
            return (False, False)

        # skip files that are too large
        size = int(headers.get('content-length', 0))
        if size > SigningHandler.max_file_size:
            sig_url = '{}.sig'.format(format['url'])
            if not self._safe_url_exists(sig_url):
                # wait for signature to be manually uploaded
                self.report_error('File is too large to sign {}'.format(format['url']))
                return (False, False)

            # finish with manually uploaded signature
            format['size'] = size
            if not format['modified']:
                format['modified'] = str_to_timestamp(datetime.datetime.now().isoformat())
            format['signature'] = sig_url
            return (False, True)

        # download file
        try:
            if 'sign_given_url' in build_rules or 'html_format' in build_rules:
                # report error if response is 400+
                if headers.status >= 400:
                    self.report_error('Resource not available at {}'.format(format['url']))
                    return (False, False)

                self.download_file(format['url'], file_to_sign)
            else:
                # TRICKY: most files to be signed are stored in a temp directory
                src_temp_key = 'temp/{}/{}/{}'.format(item['repo_name'], item['commit_id'], src_key)
                self.cdn_handler.download_file(src_temp_key, file_to_sign)
        except Exception as e:
            self.report_error('The file "{}" could not be downloaded: {}'.format(base_name, e))
            return (False, False)

        # strip print script from html
        if 'html_format' in build_rules:
            self.logger.debug('Removing print script from {} html'.format(item['repo_name']))
            self._strip_print_script(file_to_sign)

        # sign file
        sig_file = self.signer.sign_file(file_to_sign)
        try:
            self.signer.verify_signature(file_to_sign, sig_file)
        except RuntimeError:
            if self.logger:
                self.logger.warning('The signature was not successfully verified.')
            return (False, False)

        # TRICKY: re-format html urls
        if 'html_format' in build_rules:
            html_name = dublin_core['identifier']
            if project:
                html_name = project['identifier']
            src_key = '{}/{}/v{}/media/html/{}.html'.format(dublin_core['language']['identifier'], dublin_core['identifier'], self.api_version, html_name)
            sig_key = '{}.sig'.format(src_key)
            format['url'] = '{}/{}'.format(self.cdn_url, src_key)

        # upload files
        if 'sign_given_url' not in build_rules or 'html_format' in build_rules:
            # TRICKY: upload temp files to production
            self.cdn_handler.upload_file(file_to_sign, src_key)
        self.cdn_handler.upload_file(sig_file, sig_key)

        # add the url of the sig file to the format
        format['signature'] = '{}.sig'.format(format['url'])

        # read modified date from file
        stats = os.stat(file_to_sign)
        if not format['modified']:
            modified = headers.get('last-modified')
            if modified:
                # TRICKY: http header gives an odd date format
                date = datetime.datetime.strptime(modified, '%a, %d %b %Y %H:%M:%S %Z')
                modified = str_to_timestamp(date.isoformat())
            else:
                modified = unix_to_timestamp(stats.st_mtime)
            format['modified'] = modified
        format['size'] = stats.st_size

        # retrieve playback time from multimedia files
        _, ext = os.path.splitext(file_to_sign)
        if ext == '.mp3':
            audio = MP3(file_to_sign)
            format['length'] = audio.info.length
        elif ext == '.mp4':
            video = MP4(file_to_sign)
            format['length'] = video.info.length

        # add file format if missing
        if not 'format' in format or not format['format']:
            try:
                mime = ext_to_mime(ext)
                format['format'] = mime
            except Exception as e:
                if self.logger:
                    self.logger.error(e.message)

        # clean up disk space
        os.remove(file_to_sign)

        return (False, True)

    @staticmethod
    def _strip_print_script(file_to_sign):
        html = read_file(file_to_sign)
        html = html.replace('window.print()', '')
        write_file(file_to_sign, html)