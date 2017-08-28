import os
from shutil import copyfile
from unittest import TestCase

import gogs_client as GogsClient

from libraries.lambda_handlers.fork_handler import ForkHandler
from libraries.lambda_handlers.webhook_handler import WebhookHandler
from libraries.tools.mocks import MockS3Handler, MockDynamodbHandler, MockLogger


# This is here to test importing main


class TestFork(TestCase):
    resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')
    mock_download = None

    class MockBotoClient(object):

        def invoke(self, FunctionName, InvocationType, Payload):
            pass

    class MockGogsRepo(object):
        def __init__(self):
            self.full_name = ''
            self.name = '',
            self.default_branch = ''

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

        class Token(object):
            def __init__(self, sha1):
                pass

    @staticmethod
    def create_event():
        event = {
            "stage-variables": {
                'gogs_token': '',
                'gogs_url': 'https://git.door43.org/',
                'gogs_org': 'Door43-Catalog',
                'cdn_bucket': '',
                'cdn_url': '',
                'from_email': '',
                'to_email': '',
                'version': '3'
            },
            'context': {

            }
        }
        if 'testing_gogs_user_token' in os.environ:
            event['gogs_user_token'] = os.environ['testing_gogs_user_token']

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

    @staticmethod
    def mock_download_file(url, outfile):
        copyfile(TestFork.mock_download, outfile)

    def test_get_repos(self):
        event = self.create_event()

        # mock data
        self.MockGogsClient.MockGogsApi.repos = []
        self.MockGogsClient.MockGogsApi.repos.append(TestFork.create_repo("hmr-obs"))
        self.MockGogsClient.MockGogsApi.repos.append(TestFork.create_repo("en-obs"))
        self.MockGogsClient.MockGogsApi.repos.append(TestFork.create_repo("es-obs"))

        mockBoto = self.MockBotoClient()
        mockDb = MockDynamodbHandler()
        mockDb.insert_item(TestFork.create_db_item("hmr-obs"))
        mockDb.insert_item(TestFork.create_db_item("pt-br-obs"))
        mockLog = MockLogger()

        handler = ForkHandler(event=event,
                              context=None,
                              logger=mockLog,
                              gogs_client=self.MockGogsClient,
                              dynamodb_handler=mockDb,
                              boto_handler=mockBoto)
        repos = handler.get_new_repos()

        self.assertEqual(2, len(repos))
        for repo in repos:
            self.assertNotIn(repo.full_name, ['Door43-Catalog/hmr-obs', 'Door43-Catalog/pt-br-obs'])

    def test_get_dirty_repos(self):
        event = self.create_event()

        # mock data
        self.MockGogsClient.MockGogsApi.repos = []
        self.MockGogsClient.MockGogsApi.repos.append(TestFork.create_repo("hmr-obs"))
        self.MockGogsClient.MockGogsApi.repos.append(TestFork.create_repo("en-obs"))
        self.MockGogsClient.MockGogsApi.repos.append(TestFork.create_repo("es-obs"))

        mockBoto = self.MockBotoClient()
        dirty_record = TestFork.create_db_item("hmr-obs")
        dirty_record['dirty'] = True
        mockDb = MockDynamodbHandler()
        mockDb.insert_item(dirty_record)
        mockDb.insert_item(TestFork.create_db_item("pt-br-obs"))
        mockLog = MockLogger()

        handler = ForkHandler(event=event,
                              context=None,
                              logger=mockLog,
                              gogs_client=self.MockGogsClient,
                              dynamodb_handler=mockDb,
                              boto_handler=mockBoto)
        repos = handler.get_new_repos()

        self.assertEqual(3, len(repos))
        for repo in repos:
            self.assertNotIn(repo.full_name, ['Door43-Catalog/pt-br-obs'])

    def test_make_hook_payload(self):
        event = self.create_event()
        mockDb = MockDynamodbHandler()
        self.MockGogsClient.MockGogsApi.branch = TestFork.create_branch("branch")
        mockLog = MockLogger()

        handler = ForkHandler(event=event,
                              context=None,
                              logger=mockLog,
                              gogs_client=self.MockGogsClient,
                              dynamodb_handler=mockDb)
        repo = TestFork.create_repo("en_obs")
        payload = handler.make_hook_payload(repo)
        self.assertIn('body-json', payload)
        self.assertIn('stage-variables', payload)
        self.assertEqual(1, len(payload['body-json']['commits']))
        self.assertEqual(repo.name, payload['body-json']['repository']['name'])

        TestFork.mock_download = os.path.join(TestFork.resources_dir, 'en_obs.zip')
        s3Handler = MockS3Handler('test')
        mockLogger = MockLogger()
        dbHandler = MockDynamodbHandler()
        webhook_handler = WebhookHandler(event=payload,
                                         context=None,
                                         logger=mockLogger,
                                         s3_handler=s3Handler,
                                         dynamodb_handler=dbHandler,
                                         download_handler=TestFork.mock_download_file)
        webhook_handler.run()

    def test_trigger_hook_with_repos(self):
        event = self.create_event()
        mockDb = MockDynamodbHandler()
        self.MockGogsClient.MockGogsApi.branch = TestFork.create_branch("branch")
        mockLog = MockLogger()

        handler = ForkHandler(event=event,
                              context=None,
                              logger=mockLog,
                              gogs_client=self.MockGogsClient,
                              dynamodb_handler=mockDb)
        mockClient = self.MockBotoClient()
        mockRepo = self.MockGogsRepo()
        mockRepo.full_name = 'my_repo'
        handler._trigger_webhook(mockClient, [mockRepo])

        self.assertIn('Simulating Webhook for my_repo', mockLog._messages)

    def test_trigger_hook_no_repos(self):
        event = self.create_event()
        mockDb = MockDynamodbHandler()
        self.MockGogsClient.MockGogsApi.branch = TestFork.create_branch("branch")
        mockLog = MockLogger()

        handler = ForkHandler(event=event,
                              context=None,
                              logger=mockLog,
                              gogs_client=self.MockGogsClient,
                              dynamodb_handler=mockDb)
        mockClient = self.MockBotoClient()
        handler._trigger_webhook(mockClient, [])

        self.assertIn('No new repositories found', mockLog._messages)

    def test_stage_prefix_prod(self):
        event = self.create_event()
        mockDb = MockDynamodbHandler()
        self.MockGogsClient.MockGogsApi.branch = TestFork.create_branch("branch")
        mockLog = MockLogger()

        handler = ForkHandler(event=event,
                              context=None,
                              logger=mockLog,
                              gogs_client=self.MockGogsClient,
                              dynamodb_handler=mockDb)
        self.assertEqual('', handler.stage_prefix())

    def test_stage_prefix_dev(self):
        event = self.create_event()
        event['context'] = {
            'stage': 'dev'
        }
        mockDb = MockDynamodbHandler()
        self.MockGogsClient.MockGogsApi.branch = TestFork.create_branch("branch")
        mockLog = MockLogger()

        handler = ForkHandler(event=event,
                              context=None,
                              logger=mockLog,
                              gogs_client=self.MockGogsClient,
                              dynamodb_handler=mockDb)
        self.assertEqual('dev-', handler.stage_prefix())