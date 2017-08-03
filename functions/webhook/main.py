# -*- coding: utf-8 -*-

#
# Lambda function to handle a Gogs' webhook for updating the catalog
#

from __future__ import print_function
from handler import WebhookHandler
from tools.file_utils import wipe_temp
import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handle(event, context):
    wipe_temp(ignore_errors=True)
    try:
        handler = WebhookHandler(event, logger)
        handler.run()
    except Exception as e:
        raise Exception('Bad Request: {0}'.format(e))

    return {
        "success": True,
        "message": "Successfully added {0} ({1}) to the catalog".format(handler.repo_name, handler.commit_id)
    }
