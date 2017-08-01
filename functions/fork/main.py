# -*- coding: utf-8 -*-

#
# Lambda function to check for new repositories in a Gogs' organization.
# new repositories will trigger the webhook
#

from __future__ import print_function
from handler import ForkHandler
from tools.file_utils import wipe_temp
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handle(event, context):
    wipe_temp(ignore_errors=True)
    try:
        handler = ForkHandler(event, logger)
        handler.run()
    except Exception as e:
        raise Exception('Bad Request: {0}'.format(e))

    return {
        "success": True
    }
