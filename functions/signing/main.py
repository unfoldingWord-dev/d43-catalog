from __future__ import unicode_literals
import logging
from aws_tools.s3_handler import S3Handler
from aws_tools.dynamodb_handler import DynamoDBHandler
from signing import Signing

logger = logging.getLogger()
logger.setLevel(logging.INFO)


# noinspection PyUnusedLocal
def handle(event, context):
    """
    Triggered by adding a file to the cdn.door43.org/temp S3 folder
    :param dict event:
    :param context:
    """
    global logger
    Signing.handle_s3_trigger(event, S3Handler, DynamoDBHandler, logger)
