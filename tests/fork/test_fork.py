from unittest import TestCase

import gogs_client as GogsClient
import json
from functions.fork.fork_handler import ForkHandler

class TestFork(TestCase):

    class MockDynamodbHandler(object):
        data = None
        items = []

        @staticmethod
        def insert_item(data):
            TestFork.MockDynamodbHandler.data = data
            TestFork.MockDynamodbHandler.items.append(data)

        @staticmethod
        def query_items():
            return TestFork.MockDynamodbHandler.items

    class MockGogsClient(object):

        @staticmethod
        def GogsApi(api_url):
            return TestFork.MockGogsClient.MockGogsApi(api_url)

        class MockGogsApi(object):
            repos = []
            branch = None
            def __init__(self, base_url, session=None):
                pass
            def get_user_repos(self, auth, username):
                return TestFork.MockGogsClient.MockGogsApi.repos
            def get_branch(self, auth, username, repo_name, branch):
                return TestFork.MockGogsClient.MockGogsApi.branch

    @staticmethod
    def create_event():
        event = {
            'stage-variables': {
                'gogs_url': 'https://git.door43.org/',
                'gogs_org': 'Door43-Catalog'
            }
        }

        return event

    @staticmethod
    def create_repo(name):
        repo_json = {
                "id": 10524,
                "owner": {
                    "id": 10524,
                   "full_name": "Door43-Catalog",
                   "email": "",
                   "username": ""
                },
                "name": name,
                "full_name":"Door43-Catalog/{0}".format(name),
                "default_branch": "master",
                "private": False,
                "fork": False,
                "html_url": "",
                "ssh_url": "",
                "clone_url": "",
                "permissions": {
                    "admin": True,
                    "push": True,
                    "pull": True
               }
            }
        return GogsClient.GogsRepo.from_json(repo_json)

    @staticmethod
    def create_branch(name):
        """
        
        :param name: 
        :return: 
        :rtype: GogsBranch
        """
        branch_json = {
            "name": name,
            "commit": {
                "id": "c17825309a0d52201e78a19f49948bcc89e52488",
                "message": "a commit",
                "url": "Not implemented",
                "author": {
                    "name": "Joel Lonbeck",
                    "email": "joel@neutrinographics.com",
                    "username": "joel"
                },
                "committer": {
                    "name": "Joel Lonbeck",
                    "email": "joel@neutrinographics.com",
                    "username": "joel"
                },
                "verification": {
                    "verified": False,
                    "reason": "gpg.error.not_signed_commit",
                    "signature": "",
                    "payload": ""
                },
                "timestamp": "2017-05-17T21:11:25Z"
            }
        }
        return GogsClient.GogsBranch.from_json(branch_json)

    @staticmethod
    def create_db_item(repo_name):
        return {
            "commit_id": "81bd73f775",
            "language": "en",
            "package": "",
            "repo_name": repo_name,
            "timestamp": "2017-05-03T21:05:33Z"
        }

    def test_get_repos(self):
        event = self.create_event()

        # mock data
        self.MockGogsClient.MockGogsApi.repos = []
        self.MockGogsClient.MockGogsApi.repos.append(TestFork.create_repo("hmr-obs"))
        self.MockGogsClient.MockGogsApi.repos.append(TestFork.create_repo("en-obs"))
        self.MockGogsClient.MockGogsApi.repos.append(TestFork.create_repo("es-obs"))

        self.MockDynamodbHandler.items = []
        self.MockDynamodbHandler.items.append(TestFork.create_db_item("hmr-obs"))
        self.MockDynamodbHandler.items.append(TestFork.create_db_item("pt-br-obs"))

        handler = ForkHandler(event, self.MockGogsClient, self.MockDynamodbHandler)
        repos = handler.get_new_repos()

        self.assertEqual(2, len(repos))
        for repo in repos:
            self.assertNotEqual('Door43-Catalog/hmr-obs', repo.full_name)

    def test_make_hook_payload(self):
        event = self.create_event()

        # mock data
        self.MockGogsClient.MockGogsApi.branch = TestFork.create_branch("branch")

        handler = ForkHandler(event, self.MockGogsClient, self.MockDynamodbHandler)
        repo = TestFork.create_repo("Hello")
        payload = handler.make_hook_payload(repo)

        # TODO: assert some things

