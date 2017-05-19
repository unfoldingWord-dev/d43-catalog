from unittest import TestCase

import gogs_client as GogsClient
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
            def __init__(self, base_url, session=None):
                pass
            def get_user_repos(self, auth, username):
                return TestFork.MockGogsClient.MockGogsApi.repos

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
       return GogsClient.GogsRepo(10524,
                                GogsClient.GogsUser(4589, "Door43-Catalog", "Door43 Resource Catalog", "", ""),
                                "Door43-Catalog/{}".format(name),
                                False,
                                False,
                                GogsClient.GogsRepo.Urls("", "", ""),
                                GogsClient.GogsRepo.Permissions(True, True, True))

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

    def test_hook_repo(self):
        event = self.create_event()
        handler = ForkHandler(event, self.MockGogsClient, self.MockDynamodbHandler)
        repo = GogsClient.GogsRepo.from_json({
                "id": 27,
                "owner": {
                    "id": 1,
                    "username": "unknwon",
                    "full_name": "",
                    "email": "u@gogs.io",
                    "avatar_url": "/avatars/1"
                  },
                  "name": "Hello-World",
                  "full_name": "unknwon/Hello-World",
                  "description": "Some description",
                  "private": False,
                  "fork": False,
                  "parent": None,
                  "default_branch": "master",
                  "empty": False,
                  "size": 42,
                  "html_url": "http://localhost:3000/unknwon/Hello-World",
                  "clone_url": "http://localhost:3000/unknwon/hello-world.git",
                  "ssh_url": "jiahuachen@localhost:unknwon/hello-world.git",
                  "permissions": {
                    "admin": True,
                    "push": True,
                    "pull": True
                  }
                })
        handler.hook_repo(repo)

