# -*- coding: utf-8 -*-

#
# Lambda function to handle a Gogs' webhook for updating the catalog
#

from __future__ import print_function

import logging

from libraries.lambda_handlers.webhook_handler import WebhookHandler
from libraries.tools.lambda_utils import wipe_temp

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handle(event, context):
    wipe_temp(ignore_errors=True)

    handler = WebhookHandler(event, context, logger)
    return handler.run()
