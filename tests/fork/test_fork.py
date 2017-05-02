from unittest import TestCase

from functions.fork.fork_handler import ForkHandler

class TestFork(TestCase):

    class MockDynamodbHandler(object):
        data = None

        @staticmethod
        def insert_item(data):
            TestFork.MockDynamodbHandler.data = data

    @staticmethod
    def create_event():
        event = {
            'stage-variables': {
                'gogs_url': 'https://git.door43.org/',
                'gogs_org': 'Door43-Catalog'
            }
        }

        return event

    def test_get_repos(self):
        event = self.create_event()

        handler = ForkHandler(event, self.MockDynamodbHandler)
        repos = handler.get_new_repos()