# -*- coding: utf-8 -*-

#
# Class to process a Catalog repo and add it to the d43-catalog-in-progress table
#

from __future__ import print_function

import os
import tempfile
import json

from glob import glob
from datetime import datetime
from stat import *
from general_tools.url_utils import get_url, download_file
from general_tools.file_utils import unzip, read_file, get_mime_type
from aws_tools.dynamodb_handler import DynamoDBHandler
from aws_tools.s3_handler import S3Handler
from manifest_handler import Manifest

class RepoHandler:
    def __init__(self, event):
        env_vars = self.retrieve(event, 'stage-variables', 'payload')
        self.gogs_url = self.retrieve(env_vars, 'gogs_url', 'Environment Vars')
        self.gogs_org = self.retrieve(env_vars, 'gogs_org', 'Environment Vars')
        self.cdn_bucket = self.retrieve(env_vars, 'cdn_bucket', 'Environment Vars')
        self.cdn_url = self.retrieve(env_vars, 'cdn_url', 'Environment Vars')

        self.repo_commit = self.retrieve(event, 'body-json', 'payload')
        self.repo_owner = self.repo_commit['repository']['owner']['username']
        self.repo_name = self.repo_commit['repository']['name']
        self.repo_file = os.path.join(tempfile.gettempdir(), self.repo_name+'.zip')
        self.repo_dir = os.path.join(tempfile.gettempdir(), self.repo_name)

        self.commit_id = self.repo_commit['after']
        commit = None
        for commit in self.repo_commit['commits']:
            if commit['id'] == self.commit_id:
                break
        self.commit_url = commit['url']
        self.timestamp = commit['timestamp']
        self.commit_id = self.commit_id[:10]

        self.db_handler = DynamoDBHandler('d43-catalog-in-progress')
        self.s3_handler = S3Handler(self.cdn_bucket)
        self.manifest = None
        self.files = []

    def run(self):
            if not self.commit_url.startswith(self.gogs_url):
                raise Exception('Only accepting webhooks from {0}'.format(self.gogs_url))

            if self.repo_owner.lower() != self.gogs_org.lower():
                raise Exception("Only accepting repos from the {0} organization".format(self.gogs_org))

            self.download_repo(self.commit_url, self.repo_file)
            self.unzip_repo_file(self.repo_file, tempfile.gettempdir())

            if not os.path.isdir(self.repo_dir):
                raise Exception('Was not able to find {0}'.format(self.repo_dir))

            if self.repo_name == 'localization':
                files = sorted(glob(os.path.join(self.repo_dir, '*.json')))
                localization = {}
                for f in files:
                    print("Reading {0}...".format(f))
                    language = os.path.splitext(os.path.basename(f))[0]
                    localization[language] = json.loads(read_file(f))
                data = {
                    'repo_name': self.repo_name,
                    'commit': self.commit_id,
                    'timestamp': self.timestamp,
                    'data': json.dumps(localization, sort_keys=True)
                }
            elif self.repo_name == 'catalogs':
                catalogs_path = os.path.join(self.repo_dir, 'catalogs.json')
                contents = read_file(catalogs_path)
                data = {
                    'repo_name': self.repo_name,
                    'commit_id': self.commit_id,
                    'timestamp': self.timestamp,
                    'data': contents
                }
            else:
                manifest_path = os.path.join(self.repo_dir, 'manifest.json')
                if not os.path.isfile(manifest_path):
                    raise Exception('Repository {0} does not have a manifest.json file'.format(self.repo_name))
                self.manifest = Manifest(file_name=manifest_path, repo_name=self.repo_name)
                # self.process_files(os.path.join(repo_path, 'content'))
                stats = os.stat(self.repo_file)
                temp_path = 'temp/{0}/{1}/{2}.zip'.format(self.repo_name,
                                                          self.commit_id,
                                                          self.manifest.slug)
                url = '{0}/{1}/{2}/v{3}/{4}.zip'.format(self.cdn_url,
                                                        self.manifest.language['slug'],
                                                        self.manifest.slug.split('-')[1],
                                                        self.manifest.status['version'],
                                                        self.manifest.slug)
                file_info = {
                    'size': stats.st_size,
                    'modified_at': stats.st_mtime,
                    'mime_type': 'application/zip',
                    'url': url,
                    'sig': url + '.sig'
                }
                self.manifest.formats.append(file_info)
                self.files.append(temp_path)
                self.s3_handler.upload_file(self.repo_file, temp_path)
                data = {
                    'repo_name': self.repo_name,
                    'commit_id': self.commit_id,
                    'language': self.manifest.language['slug'],
                    'timestamp': self.timestamp,
                    'files': self.files,
                    'data': json.dumps(self.manifest.__dict__, sort_keys=True)
                }
            self.db_handler.insert_item(data)
            return data

    def process_file(self, path):
        stats = os.stat(path)
        file_path = '{0}/{1}/v{2}/{3}'.format(self.manifest.language['slug'],
                                              self.manifest.slug.split('-')[1],
                                              self.manifest.status['version'],
                                              os.path.basename(path))
        url = '{0}/{1}'.format(self.cdn_url, file_path)
        format = {
            'size': stats.st_size,
            'modified_at': stats.st_mtime,
            'mime_type': get_mime_type(path),
            'url': url,
            'sig': url+'.sig'
        }
        self.manifest.formats.append(format)
        self.files.append(file_path)
        self.s3_handler.upload_file(path, "temp/"+file_path)

    def process_files(self, path):
        self.walktree(path, self.process_file)

    def walktree(self, top, callback):
        for f in os.listdir(top):
            pathname = os.path.join(top, f)
            mode = os.stat(pathname).st_mode
            if S_ISDIR(mode):
                # It's a directory, recurse into it
                self.walktree(pathname, callback)
            elif S_ISREG(mode):
                # It's a file, call the callback function
                callback(pathname)
            else:
                # Unknown file type, print a message
                print('Skipping %s' % pathname)

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

    def retrieve(self, dictionary, key, dict_name=None):
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
