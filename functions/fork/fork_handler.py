# -*- coding: utf-8 -*-

#
# Class to trigger the webhook if a repository is not being processed
#

from __future__ import print_function

from d43_aws_tools import DynamoDBHandler
import gogs_client as GogsClient
import boto3
import json
import time
from tools.dict_utils import read_dict

class ForkHandler:
    def __init__(self, event, gogs_client=None, dynamodb_handler=None):
        """
        
        :param event: 
        :param gogs_client: Passed in for unit testing
        :param dynamodb_handler: Passed in for unit testing
        """
        gogs_user_token = read_dict(event, 'gogs_user_token', 'Environment Vars')

        #  TRICKY: these var must be structured the same as in the webhook
        self.stage_vars = read_dict(event, 'stage-variables', 'Environment Vars')
        self.gogs_url = read_dict(self.stage_vars, 'gogs_url', 'Environment Vars')
        self.gogs_org = read_dict(self.stage_vars, 'gogs_org', 'Environment Vars')

        if not dynamodb_handler:
            self.progress_table = DynamoDBHandler('d43-catalog-in-progress')
        else:
            self.progress_table = dynamodb_handler
        if not gogs_client:
            self.gogs_client = GogsClient
        else:
            self.gogs_client = gogs_client

        self.gogs_api = self.gogs_client.GogsApi(self.gogs_url)
        self.gogs_auth = self.gogs_client.Token(gogs_user_token)

    def run(self):
        client = boto3.client("lambda")
        repos = self.get_new_repos()
        for repo in repos:
            try:
                payload = self.make_hook_payload(repo)
            except Exception as e:
                print("Failed to retrieve master branch for {0}: {1}".format(repo.full_name, e))
                continue
            try:
                print("Simulating Webhook for {}".format(repo.full_name))
                client.invoke(
                    FunctionName="d43-catalog_webhook",
                    InvocationType="Event",
                    Payload=json.dumps(payload)
                )
                time.sleep(5)
            except Exception as e:
                print("Failed to trigger webhook {0}: {1}".format(repo.full_name, e))
                continue

    def make_hook_payload(self, repo):
        """
        Generates a webhook payload for the repo
        :param repo:
        :return: 
        """

        branch = self.gogs_api.get_branch(self.gogs_auth, self.gogs_org, repo.name, repo.default_branch)
        return {
            "stage-variables": self.stage_vars,
            "body-json": {
                "after": branch.commit.id,
                "commits": [{
                    "id": branch.commit.id,
                    "message": branch.commit.message,
                    "timestamp": branch.commit.timestamp,
                    "url": '{0}{1}/{2}/commit/{3}'.format(self.gogs_url, self.gogs_org, repo.name, branch.commit.id) # branch.commit.url <-- not implemented yet
                }],
                "repository": {
                    "owner": {
                        "username": "Door43-Catalog"
                    },
                    "name": repo.name
                }
            },
        }

    def get_new_repos(self):
        """
        Compares the organization repos with what's in progress
        and returns those that are new.
        :return: 
        """
        org_repos = self.gogs_api.get_user_repos(None, self.gogs_org)
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