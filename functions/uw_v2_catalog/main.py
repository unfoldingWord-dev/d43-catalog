# -*- coding: utf-8 -*-

#
# Lambda function for generating the catalog.json file for the uW v2 API
#

from __future__ import print_function
from handler import UwV2CatalogHandler
from tools.file_utils import wipe_temp
import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# TRICKY: suppress logging noise from boto3
logging.getLogger('boto3').setLevel(logging.WARNING)

def handle(event, context):
    wipe_temp(ignore_errors=True)
    try:
        catalog = UwV2CatalogHandler(event)
        return catalog.run()
    except Exception as e:
        raise Exception('Bad Request: {0}'.format(e))
