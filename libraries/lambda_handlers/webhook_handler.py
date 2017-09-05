# -*- coding: utf-8 -*-

#
# Class to process a Catalog repo and add it to the d43-catalog-in-progress table
#

from __future__ import print_function

import codecs
import json
import logging
import os
import shutil
import tempfile
import arrow
import sys
import yaml

from glob import glob
from d43_aws_tools import DynamoDBHandler, S3Handler
from libraries.tools.consistency_checker import ConsistencyChecker
from libraries.tools.date_utils import str_to_timestamp
from libraries.tools.file_utils import unzip, read_file, write_file
from libraries.tools.url_utils import get_url, download_file, url_exists

from libraries.lambda_handlers.handler import Handler


class WebhookHandler(Handler):
    def __init__(self, event, context, logger, **kwargs):
        super(WebhookHandler, self).__init__(event, context)

        env_vars = self.retrieve(event, 'stage-variables', 'payload')
        self.gogs_url = self.retrieve(env_vars, 'gogs_url', 'Environment Vars')
        self.gogs_org = self.retrieve(env_vars, 'gogs_org', 'Environment Vars')
        self.cdn_bucket = self.retrieve(env_vars, 'cdn_bucket', 'Environment Vars')
        self.cdn_url = self.retrieve(env_vars, 'cdn_url', 'Environment Vars')
        self.from_email = self.retrieve(env_vars, 'from_email', 'Environment Vars')
        self.to_email = self.retrieve(env_vars, 'to_email', 'Environment Vars')
        self.api_url = self.retrieve(env_vars, 'api_url', 'Environment Vars')
        self.repo_commit = self.retrieve(event, 'body-json', 'payload')
        self.api_version = self.retrieve(env_vars, 'version')
        if 'pull_request' in self.repo_commit:
            self.__parse_pull_request(self.repo_commit)
        else:
            self.__parse_push(self.repo_commit)

        self.resource_id = None # set in self._build
        self.logger = logger # type: logging._loggerClass

        if 'dynamodb_handler' in kwargs:
            self.db_handler = kwargs['dynamodb_handler']
        else:
            self.db_handler = DynamoDBHandler('{}d43-catalog-in-progress'.format(self.stage_prefix())) # pragma: no cover

        if 's3_handler' in kwargs:
            self.s3_handler = kwargs['s3_handler']
        else:
            self.s3_handler = S3Handler(self.cdn_bucket) # pragma: no cover

        if 'download_handler' in kwargs:
            self.download_file = kwargs['download_handler']
        else:
            self.download_file = download_file # pragma: no cover

    def __parse_pull_request(self, payload):
        """
        Parses a  pull request
        :param payload:
        :return: True if the pull request should be processed
        """

        pull_request = self.retrieve(payload, 'pull_request', 'payload')

        self.repo_owner = payload['repository']['owner']['username']
        self.repo_name = payload['repository']['name']
        self.temp_dir = tempfile.mkdtemp('', self.repo_name, None)
        self.repo_file = os.path.join(self.temp_dir, self.repo_name + '.zip')
        # TRICKY: gogs gives a lower case name to the folder in the zip archive
        self.repo_dir = os.path.join(self.temp_dir, self.repo_name.lower())

        commit_sha = self.retrieve(pull_request, 'merge_commit_sha', 'pull_request')
        self.timestamp = str_to_timestamp(self.retrieve(pull_request, 'merged_at', 'pull_request'))
        repository = self.retrieve(payload, 'repository', 'payload')
        url = self.retrieve(repository, 'html_url', 'repository').rstrip('/')
        self.commit_url = '{}/commit/{}'.format(url, commit_sha)
        if commit_sha:
            self.commit_id = commit_sha[:10]
        else:
            self.commit_id = None

    def __parse_push(self, payload):
        """
        Parses a regular push commit
        :param payload:
        :return:
        """
        self.repo_owner = payload['repository']['owner']['username']
        self.repo_name = payload['repository']['name']
        self.temp_dir = tempfile.mkdtemp('', self.repo_name, None)
        self.repo_file = os.path.join(self.temp_dir, self.repo_name + '.zip')
        # TRICKY: gogs gives a lower case name to the folder in the zip archive
        self.repo_dir = os.path.join(self.temp_dir, self.repo_name.lower())

        self.commit_id = payload['after']
        commit = None
        for commit in payload['commits']:
            if commit['id'] == self.commit_id:
                break
        self.commit_url = commit['url']
        self.timestamp = str_to_timestamp(commit['timestamp'])
        self.commit_id = self.commit_id[:10]

    def _run(self):
        if not self.commit_url.startswith(self.gogs_url):
            raise Exception('Only accepting webhooks from {0} but found {1}'.format(self.gogs_url, self.commit_url)) # pragma: no cover

        if self.repo_owner.lower() != self.gogs_org.lower():
            raise Exception("Only accepting repos from the {0} organization".format(self.gogs_org)) # pragma: no cover

        # skip un-merged pull requests
        if 'pull_request' in self.repo_commit:
            pr = self.repo_commit['pull_request']
            if not pr['merged']:
                raise Exception('Skipping un-merged pull request')

        try:
            # build catalog entry
            data = self._build()
            if data:
                # upload data
                if 'uploads' in data:
                    self.logger.debug('Uploading files for "{}"'.format(self.repo_name))
                    for upload in data['uploads']:
                        self.s3_handler.upload_file(upload['path'], upload['key'])
                    del data['uploads']
                else:
                    self.logger.debug('No upload-able content found in "{}"'.format(self.repo_name))
                self.db_handler.insert_item(data)
            else:
                self.logger.debug('No data found in {}'.format(self.repo_name))
        except Exception as e:
            self.report_error(e.message)
            raise Exception, Exception(e), sys.exc_info()[2]
        finally:
            # clean
            if self.temp_dir and os.path.isdir(self.temp_dir):
                shutil.rmtree(self.temp_dir, ignore_errors=True)

        return {
            "success": True,
            "message": "Successfully added {0} ({1}) to the catalog".format(self.repo_name, self.commit_id)
        }

    def _build(self):
        """
        Constructs a new catalog entry from the repository
        :return: the constructed object
        """

        self.download_repo(self.commit_url, self.repo_file)
        self.unzip_repo_file(self.repo_file, self.temp_dir)

        if not os.path.isdir(self.repo_dir):
            raise Exception('Was not able to find {0}'.format(self.repo_dir)) # pragma: no cover

        self.logger.info('Processing repository "{}"'.format(self.repo_name))
        data = {}
        if self.repo_name == 'localization':
            data = self._build_localization()
        elif self.repo_name == 'catalogs':
            data = self._build_catalogs()
        elif self.repo_name == 'versification':
            # TODO: we do not yet know what to do with versification
            return None
        else:
            data = self._build_rc()

        return data

    def _build_rc(self):
        """
        Builds a Resource Container following the RC0.2 spec
        :return:
        """
        manifest_path = os.path.join(self.repo_dir, 'manifest.yaml')
        if not os.path.isfile(manifest_path):
            raise Exception('Repository {0} does not have a manifest.yaml file'.format(self.repo_name))
        try:
            manifest = WebhookHandler.load_yaml_object(manifest_path)
        except Exception as e:
            raise Exception('Bad Manifest: {0}'.format(e))

        try:
            ConsistencyChecker.check_manifest(manifest)
        except Exception as e:
            raise Exception('Bad Manifest: {0}'.format(e))

        # identifiers must be lowercase
        manifest['dublin_core']['identifier'] = self.sanitize_identifier(manifest['dublin_core']['identifier'])

        # build media formats
        media_formats = {}
        media_path = os.path.join(self.repo_dir, 'media.yaml')
        if os.path.isfile(media_path):
            try:
                media = WebhookHandler.load_yaml_object(media_path)
            except Exception as e:
                raise Exception('Bad Media: {0}'.format(e))
            media_formats = self._build_media_formats(self.repo_dir, manifest, media)

        stats = os.stat(self.repo_file)

        # normalize dates
        try:
            manifest['dublin_core']['modified'] = str_to_timestamp(manifest['dublin_core']['modified'])
        except Exception as e:
            self.logger.warning('Invalid datetime detected: {}'.format(e.message))
        try:
            manifest['dublin_core']['issued'] = str_to_timestamp(manifest['dublin_core']['issued'])
        except Exception as e:
            self.logger.warning('Invalid datetime detected: {}'.format(e.message))

        # TRICKY: single-project RCs get named after the project to avoid conflicts with multi-project RCs.
        if len(manifest['projects']) == 1:
            zip_name = manifest['projects'][0]['identifier'].lower()
        else:
            zip_name = manifest['dublin_core']['identifier']

        resource_key = '{}/{}/v{}/{}.zip'.format(
                                                manifest['dublin_core']['language']['identifier'],
                                                manifest['dublin_core']['identifier'].split('-')[-1],
                                                manifest['dublin_core']['version'],
                                                zip_name)
        url = '{}/{}'.format(self.cdn_url, resource_key)

        file_info = {
            'size': stats.st_size,
            'modified': self.timestamp,
            'format': 'application/zip; type={0} content={1} conformsto={2}'.format(manifest['dublin_core']['type'],
                                                                                    manifest['dublin_core'][
                                                                                        'format'],
                                                                                    manifest['dublin_core'][
                                                                                        'conformsto']),
            'url': url,
            'signature': ""
        }
        manifest['formats'] = [file_info]

        uploads = [{
                'key': self.make_upload_key(resource_key),
                'path': self.repo_file
            }]

        # split usfm bundles
        if manifest['dublin_core']['type'] == 'bundle' and manifest['dublin_core']['format'] == 'text/usfm':
            for project in manifest['projects']:
                pid = self.sanitize_identifier(project['identifier'])
                if 'formats' not in project:
                    project['formats'] = []
                resource_id = manifest['dublin_core']['identifier'].split('-')[-1]
                project_key = '{}/{}/v{}/{}.usfm'.format(
                                                        manifest['dublin_core']['language']['identifier'],
                                                        resource_id,
                                                        manifest['dublin_core']['version'],
                                                        pid)
                project_url = '{}/{}'.format(self.cdn_url, project_key)
                p_file_path = os.path.join(self.repo_dir, project['path'].lstrip('\.\/'))
                p_stats = os.stat(p_file_path)
                try:
                    resource_mtime = str_to_timestamp(manifest['dublin_core']['modified'])
                except Exception as e:
                    self.logger.warning('Invalid datetime detected: {}'.format(e.message))
                    resource_mtime = manifest['dublin_core']['modified']
                project['formats'].append({
                    'format': 'text/usfm',
                    'modified': resource_mtime,
                    'signature': '',
                    'size': p_stats.st_size,
                    'url': project_url
                })
                uploads.append({
                    'key': self.make_upload_key(project_key),
                    'path': p_file_path
                })

        # add media to projects
        for project in manifest['projects']:
            pid = self.sanitize_identifier(project['identifier'])
            if pid in media_formats:
                if 'formats' not in project: project['formats'] = []
                project['formats'] = project['formats'] + media_formats[pid]

        # add html format
        for project in manifest['projects']:
            pid = self.sanitize_identifier(project['identifier'])
            if manifest['dublin_core']['identifier'] == 'obs':
                # obs html
                html_url = '{}/tx/print?id={}/{}/{}'.format(self.api_url, self.gogs_org, self.repo_name, self.commit_id)
            elif manifest['dublin_core']['identifier'] == 'ta':
                # ta html
                sort_slug = '{}'.format(int(project['sort']) + 1).zfill(2)
                html_url = '{}/u/Door43-Catalog/{}/{}/{}-{}.html'.format(self.cdn_url, self.repo_name, self.commit_id, sort_slug, pid)
            else:
                # we also have html for Bible resources
                sort_slug = '{}'.format(int(project['sort'])).zfill(2)
                html_url = '{}/u/Door43-Catalog/{}/{}/{}-{}.html'.format(self.cdn_url, self.repo_name, self.commit_id,
                                                                         sort_slug, pid.upper())
            if url_exists(html_url):
                if 'formats' not in project: project['formats'] = []
                project['formats'].append({
                    'format': 'text/html',
                    'modified': '',
                    'signature': '',
                    'size': '',
                    'url': html_url,
                    'build_rules': [
                        'signing.html_format'
                    ]
                })
            else:
                self.logger.warning('Missing html format for {}_{} at {}'.format(self.repo_name, pid, html_url))

        return {
            'repo_name': self.repo_name,
            'commit_id': self.commit_id,
            'language': manifest['dublin_core']['language']['identifier'],
            'timestamp': self.timestamp,
            'added_at': arrow.utcnow().isoformat(),
            'package': json.dumps(manifest, sort_keys=True),
            'signed': False,
            'dirty': False,
            'uploads': uploads
        }

    def _build_media_formats(self, rc_dir, manifest, media):
        """
        Prepares the media formats
        :param rc_dir:
        :param manifest:
        :param media:
        :return:
        """
        formats = {}
        for project in media['projects']:
            pid = self.sanitize_identifier(project['identifier'])
            project_formats = []
            for media in project['media']:
                if 'quality' in media and len(media['quality']) > 0:
                    # build format for each quality
                    for quality in media['quality']:
                        format = {
                            'format': '',
                            'modified': '',
                            'size': 0,
                            'source_version': project['version'],
                            'version': media['version'],
                            'quality': quality,
                            'contributor': media['contributor'],
                            'url': media['url'].replace('{quality}', quality),
                            'signature': '',
                            'build_rules': [
                                'signing.sign_given_url'
                            ]
                        }
                        if 'chapter_url' in media:
                            chapter_url = media['chapter_url'].replace('{quality}', quality)
                            chapters = self._build_media_chapters(rc_dir, manifest, pid, chapter_url)
                            if chapters:
                                format['chapters'] = chapters

                        project_formats.append(format)

                else:
                    # build single format
                    format = {
                        'format': '',
                        'modified': '',
                        'size': 0,
                        'source_version': project['version'],
                        'version': media['version'],
                        'contributor': media['contributor'],
                        'url': media['url'],
                        'signature': '',
                        'build_rules': [
                            'signing.sign_given_url'
                        ]
                    }
                    if 'chapter_url' in media:
                        chapters = self._build_media_chapters(rc_dir, manifest, pid, media['chapter_url'])
                        if chapters:
                            format['chapters'] = chapters
                        pass

                    project_formats.append(format)
            formats[project['identifier']] = project_formats
        return formats

    def _build_media_chapters(self, rc_dir, manifest, pid, chapter_url):
        """
        Generates chapters items for a media format
        :param rc_dir:
        :param manifest:
        :param pid:
        :param chapter_url:
        :return:
        """
        media_chapters = []
        for project in manifest['projects']:
            pid = self.sanitize_identifier(project['identifier'])
            if project['identifier'] == pid:
                id = '_'.join([manifest['dublin_core']['language']['identifier'],
                               manifest['dublin_core']['identifier'],
                               manifest['dublin_core']['type'],
                               pid])
                project_path = os.path.normpath(os.path.join(rc_dir, project['path']))
                if manifest['dublin_core']['type'] == 'book':
                    chapters = os.listdir(project_path)
                    for chapter in chapters:
                        if chapter in ['.', '..', 'toc.yaml', 'config.yaml', 'back', 'front']:
                            continue
                        chapter = chapter.split('.')[0] # trim extension from files
                        media_chapters.append({
                            'size': 0,
                            'length': 0,
                            'modified': '',
                            'identifier': chapter,
                            'url': chapter_url.replace('{chapter}', chapter),
                            'signature': '',
                            'build_rules': [
                                'signing.sign_given_url'
                            ]
                        })
                else:
                    # TODO: add additional support as needed
                    self.logger.warning('Failed to generate media chapters. Only book RCs are currently supported. {}'.format(id))
                    break

        return media_chapters

    def _build_versification(self):
        """
        DEPRECATED

        we are no longer processing versification.
        :return:
        """
        bible_dir = os.path.join(self.repo_dir, 'bible')
        versification_dirs = os.listdir(bible_dir)
        books = {}
        package = []
        uploads = []

        # group by project
        for vrs_dir in versification_dirs:
            vrs_id = os.path.basename(vrs_dir)
            book_files = sorted(glob(os.path.join(bible_dir, vrs_dir, 'chunks', '*.json')))
            for b in book_files:
                self.logger.debug('Reading "{}" versification for "{}"'.format(vrs_id, b))
                b_id = os.path.splitext(os.path.basename(b))[0]
                try:
                    book_vrs = json.loads(read_file(b))
                except Exception as e:
                    raise Exception, Exception('Bad JSON: {0}'.format(e)), sys.exc_info()[2]
                book = WebhookHandler.retrieve_or_make(books, b_id, {
                    'identifier': b_id,
                    'chunks_url': '{0}/bible/{}/{}/v{}/chunks.json'.format(self.cdn_url, vrs_id, b_id, self.api_version),
                    'chunks': {}
                })
                book['chunks'][vrs_id] = book_vrs
        temp_dir = os.path.join(self.temp_dir, 'versification')
        if not os.path.isdir:
            os.mkdir(temp_dir)
        for book in books:
            book = books[book]

            # write chunks
            chunk_file = os.path.join(temp_dir, book['identifier'] + '.json')
            write_file(chunk_file, json.dumps(book['chunks'], sort_keys=True))
            # for now we bypass signing and upload chunks directly
            upload_key = 'bible/{}/{}/v{}/chunks.json'.format(book['identifier'], self.api_version)
            uploads.append({
                'key': upload_key,
                'path': chunk_file
            })

            # build package
            del book['chunks']
            package.append(book)

        return {
            'repo_name': self.repo_name,
            'commit_id': self.commit_id,
            'timestamp': self.timestamp,
            'package': json.dumps(package, sort_keys=True),
            'uploads': uploads,
            'dirty': False
        }


    def _build_localization(self):
        """
        Builds the localization for various components in the catalog
        :return:
        """
        files = sorted(glob(os.path.join(self.repo_dir, '*.json')))
        localization = {}
        for f in files:
            self.logger.debug("Reading {0}...".format(f))
            language = os.path.splitext(os.path.basename(f))[0]
            try:
                localization[language] = json.loads(read_file(f))
            except Exception as e:
                raise Exception('Bad JSON: {0}'.format(e))
        return {
            'repo_name': self.repo_name,
            'commit_id': self.commit_id,
            'timestamp': self.timestamp,
            'package': json.dumps(localization, sort_keys=True),
            'dirty': False
        }

    def _build_catalogs(self):
        """
        Builds the global catalogs
        :return:
        """
        catalogs_path = os.path.join(self.repo_dir, 'catalogs.json')
        package = read_file(catalogs_path)
        return {
            'repo_name': self.repo_name,
            'commit_id': self.commit_id,
            'timestamp': self.timestamp,
            'package': package,
            'dirty': False
        }

    def make_upload_key(self, path):
        """
        Generates an upload key that conforms to the format `temp/<repo_name>/<commit>/<path>`.
        This allows further processing to associate files with an entry in dynamoDB.
        :param path:
        :return:
        """
        return 'temp/{0}/{1}/{2}'.format(self.repo_name, self.commit_id, path)

    @staticmethod
    def retrieve_or_make(dictionary, key, default=None):
        """
        Retrieves a value from a dictionary.
        If the key does not exist it will be created with the default value
        :param dict dictionary:
        :param any key:
        :param default:
        :return:
        """
        if  key not in dictionary:
            dictionary[key] = default
        return dictionary[key]

    @staticmethod
    def load_yaml_object(file_name, default=None):
        """
        Deserialized <file_name> into a Python object
        :param str|unicode file_name: The name of the file to read
        :param default: The value to return if the file is not found
        """
        if not os.path.isfile(file_name):
            return default

        # use utf-8-sig in case the file has a Byte Order Mark
        with codecs.open(file_name, 'r', 'utf-8-sig') as stream:
            return yaml.load(stream)

    def get_url(self, url):
        return get_url(url)

    def download_repo(self, commit_url, repo_file):
        repo_zip_url = commit_url.replace('commit', 'archive') + '.zip'
        try:
            self.logger.debug('Downloading {0}...'.format(repo_zip_url))
            if not os.path.isfile(repo_file):
                self.download_file(repo_zip_url, repo_file)
        finally:
            pass

    def unzip_repo_file(self, repo_file, repo_dir):
        try:
            self.logger.debug('Unzipping {0}...'.format(repo_file))
            unzip(repo_file, repo_dir)
        finally:
            pass