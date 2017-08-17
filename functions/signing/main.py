from __future__ import unicode_literals

import logging

from tools.file_utils import wipe_temp
from tools.lambda_utils import lambda_restarted

from handler import SigningHandler
from libraries.tools.signer import Signer, ENC_PRIV_PEM_PATH

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# TRICKY: suppress logging noise from boto3
logging.getLogger('boto3').setLevel(logging.WARNING)

# noinspection PyUnusedLocal
def handle(event, context):
    """
    Triggered by adding a file to the cdn.door43.org/temp S3 folder
    :param dict event:
    :param context:
    """
    # TRICKY: block automatic restarts since we manually recover from timeouts and errors
    if lambda_restarted(context):
        logger.info('Blocked Lambda Restart: {}'.format(context.aws_request_id))
        return
    else:
        logger.info('Starting request: {}'.format(context.aws_request_id))

    wipe_temp(ignore_errors=True)
    global logger
    signer = Signer(ENC_PRIV_PEM_PATH)
    handler = SigningHandler(event, logger, signer)
    handler.run()
