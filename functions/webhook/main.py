# -*- coding: utf-8 -*-

#
# Lambda function to handle a Gogs' webhook for updating the catalog
#

from __future__ import print_function

import logging

from libraries.lambda_handlers.webhook_handler import WebhookHandler
from libraries.tools.file_utils import wipe_temp

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# TRICKY: suppress logging noise from boto3
logging.getLogger('boto3').setLevel(logging.WARNING)

def handle(event, context):
    wipe_temp(ignore_errors=True)
    try:
        handler = WebhookHandler(event, context, logger)
        handler.run()
    except Exception as e:
        raise Exception('Bad Request: {0}'.format(e.message))

    return {
        "success": True,
        "message": "Successfully added {0} ({1}) to the catalog".format(handler.repo_name, handler.commit_id)
    }
