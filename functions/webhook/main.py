# -*- coding: utf-8 -*-

#
# Webhook client for updating the catalog
#

from __future__ import print_function

import os
import json
import tempfile

from glob import glob
from general_tools.url_utils import get_url, download_file
from general_tools.file_utils import unzip, read_file
from aws_tools.dynamodb_handler import DynamoDBHandler


def download_repo(commit_url, repo_dir):
    repo_zip_url = commit_url.replace('commit', 'archive') + '.zip'
    repo_zip_file = os.path.join(tempfile.gettempdir(), repo_zip_url.rpartition('/')[2])
    try:
        print('Downloading {0}...'.format(repo_zip_url))
        if not os.path.isfile(repo_zip_file):
            download_file(repo_zip_url, repo_zip_file)
    finally:
        print('finished.')

    try:
        print('Unzipping {0}...'.format(repo_zip_file))
        unzip(repo_zip_file, repo_dir)
    finally:
        print('finished.')


def handle(event, context):
    try:
        # Get vars and data
        env_vars = retrieve(event, 'stage-variables', 'payload')
        api_url = retrieve(env_vars, 'api_url', 'Environment Vars')
        gogs_url = retrieve(env_vars, 'gogs_url', 'Environment Vars')
        gogs_org = retrieve(env_vars, 'gogs_org', 'Environment Vars')
        repo_commit = retrieve(event, 'body-json', 'payload')

        commit_id = repo_commit['after']
        commit = None
        for commit in repo_commit['commits']:
            if commit['id'] == commit_id:
                break

        commit_url = commit['url']

        if not commit_url.startswith(gogs_url):
            raise Exception('Only accepting webhooks from {0}'.format(gogs_url))

        repo_owner = repo_commit['repository']['owner']['username']
        repo_name = repo_commit['repository']['name']

        if repo_owner.lower() != gogs_org.lower():
            raise Exception("Org must be {0}".format(gogs_org))

        catalog_handler = DynamoDBHandler('catalog-production')

        if repo_name == 'localization':
            download_repo(commit_url, tempfile.gettempdir())
            files = sorted(glob(os.path.join(tempfile.gettempdir(), repo_name, '*.json')))
            for f in files:
                print("Reading {0}...".format(f))
                contents = read_file(f)
                lang = os.path.splitext(os.path.basename(f))[0]
                data = {
                    'repo_name': 'localization_{0}'.format(lang),
                    'contents': contents
                }
                catalog_handler.insert_item(data)
        if repo_name == 'catalogs':
            catalogs_url = commit_url.replace('/commit/', '/raw/') + '/catalogs.json'
            print("Getting {0}...".format(catalogs_url))
            contents = get_url(catalogs_url)
            data = {
                'repo_name': 'catalogs',
                'contents': contents
            }
            catalog_handler.insert_item(data)
        else:
            manifest_url = commit_url.replace('/commit/', '/raw/') + '/manifest.json'
            print("Getting {0}...".format(manifest_url))
            contents = get_url(manifest_url)
            data = {
                'repo_name': repo_name,
                'contents': contents
            }
            catalog_handler.insert_item(data)
    except Exception as e:
        raise Exception('Bad Request: {0}'.format(e))

    return 'ok'


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
