# -*- coding: utf-8 -*-

#
# Class to trigger the webhook if a repository is not being processed
#

from __future__ import print_function

from aws_tools.dynamodb_handler import DynamoDBHandler

class ForkHandler:
    def __init__(self, event, dynamodb_handler=None):
        if not dynamodb_handler:
            self.db_handler = DynamoDBHandler('d43-catalog-in-progress')
        else:
            self.db_handler = dynamodb_handler

    def run(self):
        print('hello world')