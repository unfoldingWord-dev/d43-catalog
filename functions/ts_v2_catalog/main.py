# -*- coding: utf-8 -*-

#
# Lambda function for generating the catalog.json file for the uW v2 API
#

from __future__ import print_function

import logging

from libraries.tools.lambda_utils import lambda_restarted

from handler import TsV2CatalogHandler
from libraries.tools.file_utils import wipe_temp

logger = logging.getLogger()
logger.setLevel(logging.INFO)
# TRICKY: suppress logging noise
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('usfm_tools').setLevel(logging.WARNING)

def handle(event, context):
    # TRICKY: block automatic restarts since we manually recover from timeouts and errors
    if lambda_restarted(context):
        logger.info('Blocked Lambda Restart: {}'.format(context.aws_request_id))
        return
    else:
        logger.info('Starting request: {}'.format(context.aws_request_id))

    wipe_temp(ignore_errors=True)

    try:
        catalog = TsV2CatalogHandler(event, logger)
        return catalog.run()
    except Exception as e:
        raise Exception('Bad Request: {0}'.format(e))
