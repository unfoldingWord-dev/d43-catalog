from d43_aws_tools import DynamoDBHandler
import gogs_client as GogsClient
from libraries.lambda_handlers.handler import Handler
import boto3
import time
import json


class ForkHandler(Handler):
    """
    Triggers the webhook lambda if new repositories are found.
    """

    def __init__(self, event, context, **kwargs):
        super(ForkHandler, self).__init__(event, context)

        self.stage_vars = self.retrieve(self.event, 'stage-variables', 'payload')
        gogs_token = self.retrieve(self.stage_vars, 'gogs_token', 'Environment Vars')
        self.gogs_url = self.retrieve(self.stage_vars, 'gogs_url', 'Environment Vars')
        self.gogs_org = self.retrieve(self.stage_vars, 'gogs_org', 'Environment Vars')
        if 'dynamodb_handler' in kwargs:
            self.progress_table = kwargs['dynamodb_handler']
        else:
            self.progress_table = DynamoDBHandler('d43-catalog-in-progress')  # pragma: no cover
        if 'gogs_client' in kwargs:
            self.gogs_client = kwargs['gogs_client']
        else:
            self.gogs_client = GogsClient  # pragma: no cover
        if 'boto_handler' in kwargs:
            self.boto = kwargs['boto_handler']
        else:
            self.boto = boto3  # pragma: no cover
        if 'logger' in kwargs:
            self.logger = kwargs['logger']

        self.gogs_api = self.gogs_client.GogsApi(self.gogs_url)
        self.gogs_auth = self.gogs_client.Token(gogs_token)

    def _run(self, **kwargs):
        """
        :param kwargs:
        :return:
        """

        client = self.boto.client("lambda")  # pragma: no cover
        repos = self.get_new_repos()  # pragma: no cover
        self._trigger_webhook(client, repos)  # pragma: no cover

    def _trigger_webhook(self, client, repos):
        """
        Triggers the webhook in each repo in the list
        :param client boto3.client('lambda'): the lambda client
        :param repos list: an array of repos
        :return:
        """
        if not repos:
            self.logger.info('No new repositories found')
            return
        for repo in repos:
            try:
                payload = self.make_hook_payload(repo)
            except Exception as e:
                self.logger.error("Failed to retrieve master branch for {0}: {1}".format(repo.full_name, e))
                continue
            try:
                self.logger.info("Simulating Webhook for {}".format(repo.full_name))
                client.invoke(
                    FunctionName="d43-catalog_webhook",
                    InvocationType="Event",
                    Payload=json.dumps(payload)
                )
                time.sleep(5)
            except Exception as e:
                self.logger.error("Failed to trigger webhook {0}: {1}".format(repo.full_name, e))
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
        and returns those that are new or updated.
        :return:
        """
        org_repos = self.gogs_api.get_user_repos(None, self.gogs_org)
        items = self.progress_table.query_items()

        new_repos = []
        for repo in org_repos:
            repo_name = repo.full_name.split("/")[-1]
            matching_item = self.__get_obj_in_array('repo_name', repo_name, items)
            if not matching_item or ('dirty' in matching_item and matching_item['dirty']):
                new_repos.append(repo)
            else:
                # check if changed
                # TODO: the branch API is currently broken so this code won't run
                try:
                    branch = self.gogs_api.get_branch(None, self.gogs_org, repo_name, 'master')
                    if branch:
                        commit_id = branch.commit.id[:10]
                        for item in items:
                            if item['repo_name'] == repo_name and item['commit_id'] != commit_id:
                                new_repos.append(repo)
                except Exception as e:
                    # TRICKY: with the api broken this would create a lot of noise
                    # print('WARNING: failed to detect changes: {}'.format(e))
                    pass # pragma: no cover

        return new_repos

    def __get_obj_in_array(self, key, value, array):
        """
        Retrieves the first item in an array if the key matches the value
        :param key:
        :param value:
        :param array:
        :return:
        """
        for item in array:
            if item[key] == value: return item
        return None