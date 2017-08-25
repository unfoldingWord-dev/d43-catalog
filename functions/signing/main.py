from __future__ import unicode_literals

import logging

from libraries.tools.lambda_utils import wipe_temp
from libraries.lambda_handlers.signing_handler import SigningHandler
from libraries.tools.signer import Signer, ENC_PRIV_PEM_PATH

logger = logging.getLogger()
logger.setLevel(logging.INFO)


# noinspection PyUnusedLocal
def handle(event, context):
    """
    Triggered by adding a file to the cdn.door43.org/temp S3 folder
    :param dict event:
    :param context:
    """
    wipe_temp(ignore_errors=True)
    global logger
    signer = Signer(ENC_PRIV_PEM_PATH)
    handler = SigningHandler(event, context, logger, signer)
    handler.run()
