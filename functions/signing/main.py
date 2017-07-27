from __future__ import unicode_literals
import logging
import os
from signing_handler import SigningHandler
from signer import Signer
from tools.file_utils import wipe_temp

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
    pem_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'uW-sk.enc')
    signer = Signer(pem_file)
    handler = SigningHandler(event, logger, signer)
    handler.run()
