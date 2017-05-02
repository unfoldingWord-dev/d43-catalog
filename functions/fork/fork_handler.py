# -*- coding: utf-8 -*-

#
# Class to trigger the webhook if a repository is not being processed
#

from __future__ import print_function

from general_tools.url_utils import get_url
from aws_tools.dynamodb_handler import DynamoDBHandler
import gogs_client

class ForkHandler:
    def __init__(self, event, dynamodb_handler=None):
        env_vars = self.retrieve(event, 'stage-variables', 'payload')
        self.gogs_url = self.retrieve(env_vars, 'gogs_url', 'Environment Vars')
        self.gogs_org = self.retrieve(env_vars, 'gogs_org', 'Environment Vars')

        if not dynamodb_handler:
            self.db_handler = DynamoDBHandler('d43-catalog-in-progress')
        else:
            self.db_handler = dynamodb_handler

    def run(self):
        repos = self.get_new_repos()
        # compare with in progress


        print('hello world')

    def get_new_repos(self):
        """
        Compares the organization repos with what's in progress
        and returns those that are new.
        :return: 
        """
        api = gogs_client.GogsApi(self.gogs_url)
        repos = api.get_user_repos(None, self.gogs_org)
        return repos
        # content = get_url('{}{}'.format(self.gogs_url, self.gogs_org))

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