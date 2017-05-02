# -*- coding: utf-8 -*-

#
# Lambda function to check for new repositories in a Gogs' organization.
# new repositories will trigger the webhook
#

from __future__ import print_function
from fork_handler import ForkHandler


def handle(event, context):
    try:
        handler = ForkHandler(event)
        handler.run()
    except Exception as e:
        raise Exception('Bad Request: {0}'.format(e))

    return {
        "success": True
    }
