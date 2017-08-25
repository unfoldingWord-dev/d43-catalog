# -*- coding: utf-8 -*-

#
# Lambda function for generating the catalog.json file for the API
#

from __future__ import print_function

import logging

from libraries.tools.lambda_utils import wipe_temp
from libraries.lambda_handlers.catalog_handler import CatalogHandler

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handle(event, context):
    wipe_temp(ignore_errors=True)
    catalog = CatalogHandler(event, context)
    return catalog.run()