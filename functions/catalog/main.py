# -*- coding: utf-8 -*-

#
# Lambda function for generating the catalog.json file for the API
#

from __future__ import print_function

import logging

from libraries.tools.lambda_utils import lambda_restarted, wipe_temp

from libraries.lambda_handlers.catalog_handler import CatalogHandler

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# TRICKY: suppress logging noise from boto3
logging.getLogger('boto3').setLevel(logging.WARNING)

def handle(event, context):
    # TRICKY: block automatic restarts since we manually recover from timeouts and errors
    if lambda_restarted(context):
        logger.info('Blocked Lambda Restart: {}'.format(context.aws_request_id))
        return
    else:
        logger.info('Starting request: {}'.format(context.aws_request_id))

    wipe_temp(ignore_errors=True)
    try:
        catalog = CatalogHandler(event, context)
        return catalog.run()
    except Exception as e:
        raise Exception('Bad Request: {0}'.format(e))
