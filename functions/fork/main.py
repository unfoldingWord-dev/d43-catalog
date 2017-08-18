# -*- coding: utf-8 -*-

#
# Lambda function to check for new repositories in a Gogs' organization.
# new repositories will trigger the webhook
#

from __future__ import print_function
from libraries.lambda_handlers.fork_handler import ForkHandler
from libraries.tools.lambda_utils import wipe_temp


def handle(event, context):
    wipe_temp(ignore_errors=True)

    handler = ForkHandler(event, context)
    return handler.run()