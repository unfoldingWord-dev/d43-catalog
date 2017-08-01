from __future__ import unicode_literals
import logging
from handler import SigningHandler
from tools.signer import Signer, ENC_PRIV_PEM_PATH
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
    signer = Signer(ENC_PRIV_PEM_PATH)
    handler = SigningHandler(event, logger, signer)
    handler.run()
