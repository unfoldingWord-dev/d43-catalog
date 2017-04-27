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


class RepoHandler:
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

        if not dynamodb_handler:
            self.db_handler = DynamoDBHandler('d43-catalog-in-progress')
        else:
            self.db_handler = dynamodb_handler

        if not s3_handler:
            self.s3_handler = S3Handler(self.cdn_bucket)
        else:
            self.s3_handler = s3_handler

        self.package = None

    def _clean(self):
        """
        Removes temporary files
        :return: 
        """

        if self.temp_dir and os.path.isdir(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def run(self):
        if not self.commit_url.startswith(self.gogs_url):
            raise Exception('Only accepting webhooks from {0}'.format(self.gogs_url))

        if self.repo_owner.lower() != self.gogs_org.lower():
            raise Exception("Only accepting repos from the {0} organization".format(self.gogs_org))

        try:
            data = self._build_catalog_entry()
            self._submit(self.s3_handler, self.db_handler, data)
        finally:
            self._clean()

    def _build_catalog_entry(self):
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
            files = sorted(glob(os.path.join(self.repo_dir, '*.json')))
            localization = {}
            for f in files:
                print("Reading {0}...".format(f))
                language = os.path.splitext(os.path.basename(f))[0]
                try:
                    localization[language] = json.loads(read_file(f))
                except Exception as e:
                    raise Exception('Bad JSON: {0}'.format(e))
            data = {
                'repo_name': self.repo_name,
                'commit_id': self.commit_id,
                'timestamp': self.timestamp,
                'package': json.dumps(localization, sort_keys=True)
            }
        elif self.repo_name == 'catalogs':
            catalogs_path = os.path.join(self.repo_dir, 'catalogs.json')
            package = read_file(catalogs_path)
            data = {
                'repo_name': self.repo_name,
                'commit_id': self.commit_id,
                'timestamp': self.timestamp,
                'package': package
            }
        else:
            package_path = os.path.join(self.repo_dir, 'manifest.yaml')
            if not os.path.isfile(package_path):
                raise Exception('Repository {0} does not have a manifest.yaml file'.format(self.repo_name))
            try:
                self.package = RepoHandler.load_yaml_object(package_path)
            except Exception as e:
                raise Exception('Bad Manifest: {0}'.format(e))

            try:
                ConsistencyChecker.check_manifest(self.package)
            except Exception as e:
                raise Exception('Bad Manifest: {0}'.format(e))

            stats = os.stat(self.repo_file)
            url = '{0}/{1}/{2}/v{3}/{4}.zip'.format(self.cdn_url,
                                                    self.package['dublin_core']['language']['identifier'],
                                                    self.package['dublin_core']['identifier'].split('-')[-1],
                                                    self.package['dublin_core']['version'],
                                                    self.package['dublin_core']['identifier'])

            file_info = {
                'size': stats.st_size,
                'modified': self.timestamp,
                'format': 'application/zip; type={0} content={1} version={2}'.format(self.package['dublin_core']['type'],
                                                                                    self.package['dublin_core']['format'],
                                                                                    self.package['dublin_core']['conformsto']),
                'url': url,
                'signature': ""
            }
            self.package['formats'] = [file_info]
            data = {
                'repo_name': self.repo_name,
                'commit_id': self.commit_id,
                'language': self.package['dublin_core']['language']['identifier'],
                'timestamp': self.timestamp,
                'package': json.dumps(self.package, sort_keys=True)
            }

        return data

    def _submit(self, s3_handler, dynamodb_handler, data):
        """
        Uploads the repo file and inserts the catalog object into the database
        :return: 
        """

        temp_path = 'temp/{0}/{1}/{2}.zip'.format(self.repo_name,
                                                  self.commit_id,
                                                  self.package['dublin_core']['identifier'])
        s3_handler.upload_file(self.repo_file, temp_path)

        dynamodb_handler.insert_item(data)

    # @staticmethod
    # def check_manifest(manifest):
    #     """
    #     Performs checks to ensure the manifest follows the RC0.2 specification
    #     :param manifest:
    #     :return:
    #     """
    #     if not manifest:
    #         raise Exception('Bad Manifest')
    #
    #     for key in ['dublin_core', 'checking', 'projects']:
    #         if key not in manifest:
    #             raise Exception('Bad Manifest: Missing key {0}'.format(key))
    #
    #     # check checking
    #     for key in ['checking_entity', 'checking_level']:
    #         if key not in manifest['checking']:
    #             raise Exception('Bad Manifest: Missing checking key {0}'.format(key))
    #
    #     if not isinstance(manifest['checking']['checking_entity'], list):
    #         raise Exception('Bad Manifest: checking.checking_entity must be a list')
    #
    #     # check projects
    #     if not isinstance(manifest['projects'], list):
    #         raise Exception('Bad Manifest: projects must be a list')
    #
    #     for key in ['categories', 'identifier', 'path', 'sort', 'title', 'versification']:
    #         for project in manifest['projects']:
    #             if key not in project:
    #                 raise Exception('Bad Manifest: Missing project key {0}'.format(key))
    #
    #     # check dublin_core
    #     for key in ['conformsto', 'contributor', 'creator', 'description', 'format', 'identifier', 'issued', 'language',
    #                 'modified', 'publisher', 'relation', 'rights', 'source', 'subject', 'title', 'type', 'version']:
    #         if key not in manifest['dublin_core']:
    #             raise Exception('Bad Manifest: Missing dublin_core key {0}'.format(key))
    #
    #     for key in ['direction', 'identifier', 'title']:
    #         if key not in manifest['dublin_core']['language']:
    #             raise Exception('Bad Manifest: Missing dublin_core.language key {0}'.format(key))
    #
    #     if not isinstance(manifest['dublin_core']['source'], list):
    #         raise Exception('Bad Manifest: dublin_core.source must be a list')
    #
    #     for key in ['version', 'identifier', 'language']:
    #         for source in manifest['dublin_core']['source']:
    #             if key not in source:
    #                 raise Exception('Bad Manifest: Missing dublin_core.source key {0}'.format(key))

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

    # def process_file(self, path):
    #     stats = os.stat(path)
    #     file_path = '{0}/{1}/v{2}/{3}'.format(self.package['language']['slug'],
    #                                           self.package['resource']['slug'].split('-')[-1],
    #                                           self.package['resource']['status']['version'],
    #                                           os.path.basename(path))
    #     url = '{0}/{1}'.format(self.cdn_url, file_path)
    #     format = {
    #         'size': stats.st_size,
    #         'modified_at': stats.st_mtime,
    #         'mime_type': get_mime_type(path),
    #         'url': url,
    #         'sig': url+'.sig'
    #     }
    #     self.package['resource']['formats'].append(format)
    #     self.s3_handler.upload_file(path, "temp/"+file_path)

    # def process_files(self, path):
    #     self.walktree(path, self.process_file)

    # def walktree(self, top, callback):
    #     for f in os.listdir(top):
    #         pathname = os.path.join(top, f)
    #         mode = os.stat(pathname).st_mode
    #         if S_ISDIR(mode):
    #             # It's a directory, recurse into it
    #             self.walktree(pathname, callback)
    #         elif S_ISREG(mode):
    #             # It's a file, call the callback function
    #             callback(pathname)
    #         else:
    #             # Unknown file type, print a message
    #             print('Skipping %s' % pathname)

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
