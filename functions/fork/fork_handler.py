# -*- coding: utf-8 -*-

#
# Class to trigger the webhook if a repository is not being processed
#

from __future__ import print_function

from general_tools.url_utils import get_url
from aws_tools.dynamodb_handler import DynamoDBHandler
import gogs_client as GogsClient
import boto3
import json

class ForkHandler:
    def __init__(self, event, gogs_client=None, dynamodb_handler=None):
        """
        
        :param event: 
        :param gogs_client: Passed in for unit testing
        :param dynamodb_handler: Passed in for unit testing
        """
        env_vars = self.retrieve(event, 'stage-variables', 'payload')
        self.gogs_url = self.retrieve(env_vars, 'gogs_url', 'Environment Vars')
        self.gogs_org = self.retrieve(env_vars, 'gogs_org', 'Environment Vars')

        if not dynamodb_handler:
            self.progress_table = DynamoDBHandler('d43-catalog-in-progress')
        else:
            self.progress_table = dynamodb_handler
        if not gogs_client:
            self.gogs_client = GogsClient
        else:
            self.gogs_client = gogs_client

    def run(self):
        repos = self.get_new_repos()
        client = boto3.client("lambda")

        for repo in repos:
            repo_name = repo.full_name.split("/")[-1]
            # get master branch (includes latest commit)
            branch_content = get_url("https://git.door43.org/api/v1/repos/Door43-Catalog/{}/branches/master".format(repo_name), True)
            if not branch_content:
                print("Missing branch content for {}".format(repo_name))
                continue

            try:
                branch = json.loads(branch_content)
            except Exception as e:
                print("{0}".format(e))
                continue

            commit = branch["commit"]

            print("Triggering webhook for {}".format(repo_name))
            payload={
                "after": commit["id"],
                "commits": [commit],
                "repository": {
                    "owner": {
                        "username": "Door43-Catalog"
                    },
                    "name": repo_name
                }
            }
            client.invoke(
                FunctionName="webhook",
                InvocationType="Event",
                Payload=json.dumps(payload)
            )

    def get_new_repos(self):
        """
        Compares the organization repos with what's in progress
        and returns those that are new.
        :return: 
        """
        api = self.gogs_client.GogsApi(self.gogs_url)
        org_repos = api.get_user_repos(None, self.gogs_org)
        items = self.progress_table.query_items()

        new_repos = []
        for repo in org_repos:
            repo_name = repo.full_name.split("/")[-1]
            if not self.value_in_obj_array('repo_name', repo_name, items):
                new_repos.append(repo)

        return new_repos

    def value_in_obj_array(self, key, value, array):
        """
        Checks if an object in the array contains a key value pair
        :param key: the key to look up
        :param value: the value to match
        :param array: the array to search
        :return: True if a match is found
        """
        for item in array:
            if item[key] == value: return True
        return False

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