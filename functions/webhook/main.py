# -*- coding: utf-8 -*-

#
# Webhook client for updating the catalog
#

from __future__ import print_function

import os
import sys
import json

from general_tools.url_utils import get_url
from aws_tools.dynamodb_handler import DynamoDBHandler


def handle(event, context):
    try:
        # Get vars and data
        env_vars = retrieve(event, 'stage-variables', 'payload')
        api_url = retrieve(env_vars, 'api_url', 'Environment Vars')
        gogs_url = retrieve(env_vars, 'gogs_url', 'Environment Vars')
        repo_commit = retrieve(event, 'body-json', 'payload')

        commit_id = repo_commit['after']
        commit = None
        for commit in repo_commit['commits']:
            if commit['id'] == commit_id:
                break

        commit_url = commit['url']
        manifest_url = commit_url.replace('/commit/', '/raw/')+'/manifest.json'
        repo_owner = repo_commit['repository']['owner']['username']

        if repo_owner != 'Door43':
            return

        manifest = get_url(manifest_url)

        catalog_handler = DynamoDBHandler('catalog-production')

        data = {
            'repo_name': repo_commit['repository']['name'],
            'manifest': manifest
        }
        print(json.dumps(data))
        catalog_handler.insert_item(data)
    except Exception as e:
        raise Exception('Bad Request: {0}'.format(e))

    return data


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
