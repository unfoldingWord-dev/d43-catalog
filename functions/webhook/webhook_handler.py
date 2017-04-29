# -*- coding: utf-8 -*-

#
# Class to process a Catalog repo and add it to the d43-catalog-in-progress table
#

from __future__ import print_function

import os
import tempfile
import json
import shutil
import datetime
import yaml
import codecs

from glob import glob
from stat import *
from general_tools.url_utils import get_url, download_file
from general_tools.file_utils import unzip, read_file, get_mime_type, load_json_object
from aws_tools.dynamodb_handler import DynamoDBHandler
from aws_tools.s3_handler import S3Handler
from tools.consistency_checker import ConsistencyChecker
from general_tools.file_utils import write_file


class WebhookHandler:
    def __init__(self, event, s3_handler=None, dynamodb_handler=None):
        env_vars = self.retrieve(event, 'stage-variables', 'payload')
        self.gogs_url = self.retrieve(env_vars, 'gogs_url', 'Environment Vars')
        self.gogs_org = self.retrieve(env_vars, 'gogs_org', 'Environment Vars')
        self.cdn_bucket = self.retrieve(env_vars, 'cdn_bucket', 'Environment Vars')
        self.cdn_url = self.retrieve(env_vars, 'cdn_url', 'Environment Vars')

        self.repo_commit = self.retrieve(event, 'body-json', 'payload')
        self.repo_owner = self.repo_commit['repository']['owner']['username']
        self.repo_name = self.repo_commit['repository']['name']
        self.temp_dir = tempfile.mkdtemp('', self.repo_name, None)
        self.repo_file = os.path.join(self.temp_dir, self.repo_name+'.zip')
        self.repo_dir = os.path.join(self.temp_dir, self.repo_name)

        self.commit_id = self.repo_commit['after']
        commit = None
        for commit in self.repo_commit['commits']:
            if commit['id'] == self.commit_id:
                break
        self.commit_url = commit['url']
        self.timestamp = commit['timestamp']
        self.commit_id = self.commit_id[:10]
        self.resource_id = None # set in self._build
        if not dynamodb_handler:
            self.db_handler = DynamoDBHandler('d43-catalog-in-progress')
        else:
            self.db_handler = dynamodb_handler

        if not s3_handler:
            self.s3_handler = S3Handler(self.cdn_bucket)
        else:
            self.s3_handler = s3_handler

    def run(self):
        if not self.commit_url.startswith(self.gogs_url):
            raise Exception('Only accepting webhooks from {0}'.format(self.gogs_url))

        if self.repo_owner.lower() != self.gogs_org.lower():
            raise Exception("Only accepting repos from the {0} organization".format(self.gogs_org))

        try:
            # build catalog entry
            data = self._build()
            # upload data
            if 'uploads' in data and data['uploads']:
                for upload in data['uploads']:
                    self.s3_handler.upload_file(upload['path'], upload['key'])
            del data['uploads']
            self.db_handler.insert_item(data)
        finally:
            # clean
            if self.temp_dir and os.path.isdir(self.temp_dir):
                shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _build(self):
        """
        Constructs a new catalog entry from the repository
        :return: the constructed object
        """

        self.download_repo(self.commit_url, self.repo_file)
        self.unzip_repo_file(self.repo_file, self.temp_dir)

        if not os.path.isdir(self.repo_dir):
            raise Exception('Was not able to find {0}'.format(self.repo_dir))

        data = {}
        if self.repo_name == 'localization':
            data = self._build_localization()
        elif self.repo_name == 'catalogs':
            data = self._build_catalogs()
        elif self.repo_name == 'versification':
            data = self._build_versification()
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

        stats = os.stat(self.repo_file)
        url = '{0}/{1}/{2}/v{3}/{4}.zip'.format(self.cdn_url,
                                                manifest['dublin_core']['language']['identifier'],
                                                manifest['dublin_core']['identifier'].split('-')[-1],
                                                manifest['dublin_core']['version'],
                                                manifest['dublin_core']['identifier'])

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
        return {
            'repo_name': self.repo_name,
            'commit_id': self.commit_id,
            'language': manifest['dublin_core']['language']['identifier'],
            'timestamp': self.timestamp,
            'package': json.dumps(manifest, sort_keys=True),
            'uploads': [{
                'key': self.make_temp_upload_key('{}.zip'.format(manifest['dublin_core']['identifier'])),
                'path': self.repo_file
            }]
        }

    def _build_versification(self):
        # we may need to upload multiple files and insert multiple versification entries in the db (one for each book)
        # we may need to combine the versification by book.
        # files = sorted(glob(os.path.join(self.repo_dir, 'bible', '*.json')))
        bible_dir = os.path.join(self.repo_dir, 'bible')
        versification_dirs = [x[0] for x in os.walk(bible_dir)]
        books = {}
        package = []
        uploads = []

        # group by project
        for vrs in versification_dirs:
            book_dirs = sorted(glob(os.path.join(bible_dir, vrs, 'chunks', '*.json')))
            for b in book_dirs:
                print('Reading {0}...'.format(b))
                identifier = os.path.splitext(os.path.basename(b))[0]
                try:
                    book_vrs = json.loads(read_file(b))
                except Exception as e:
                    raise Exception('Bad JSON: {0}'.format(e))
                book = WebhookHandler.retrieve_or_make(books, identifier, {
                    'identifier': identifier,
                    'chunks_url': '{0}/bible/{1}/v3/chunks.json'.format(self.cdn_url, identifier),
                    'chunks': {}
                })
                book['chunks'][vrs] = book_vrs
        for book in books:
            book = books[book]

            # write chunks
            temp_dir = tempfile.mkdtemp(prefix='versification_')
            chunk_file = os.path.join(temp_dir, book['identifier'] + '.json')
            write_file(chunk_file, json.dumps(book['chunks'], sort_keys=True))
            # for now we bypass signing and upload chunks directly
            upload_key = 'bible/{}/v3/chunks.json'.format(book['identifier']) # self.make_temp_upload_key('{}/chunks.json'.format(book['identifier']))
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
            'package': package,
            'uploads': uploads
        }


    def _build_localization(self):
        """
        Builds the localization for various components in the catalog
        :return: 
        """
        files = sorted(glob(os.path.join(self.repo_dir, '*.json')))
        localization = {}
        for f in files:
            print("Reading {0}...".format(f))
            language = os.path.splitext(os.path.basename(f))[0]
            try:
                localization[language] = json.loads(read_file(f))
            except Exception as e:
                raise Exception('Bad JSON: {0}'.format(e))
        return {
            'repo_name': self.repo_name,
            'commit_id': self.commit_id,
            'timestamp': self.timestamp,
            'package': json.dumps(localization, sort_keys=True)
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
            'package': package
        }

    def make_temp_upload_key(self, path):
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
            print('Downloading {0}...'.format(repo_zip_url))
            if not os.path.isfile(repo_file):
                download_file(repo_zip_url, repo_file)
        finally:
            print('finished.')

    def unzip_repo_file(self, repo_file, repo_dir):
        try:
            print('Unzipping {0}...'.format(repo_file))
            unzip(repo_file, repo_dir)
        finally:
            print('finished.')

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
