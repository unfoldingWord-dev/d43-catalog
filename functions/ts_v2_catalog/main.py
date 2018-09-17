# -*- coding: utf-8 -*-

#
# Lambda function for generating the catalog.json file for the uW v2 API
#

from __future__ import print_function

import logging

from libraries.tools.lambda_utils import wipe_temp
from libraries.lambda_handlers.ts_v2_catalog_handler import TsV2CatalogHandler

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

def handle(event, context):
    wipe_temp(ignore_errors=True)

    catalog = TsV2CatalogHandler(event, context, logger)
    return catalog.run()
