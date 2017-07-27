# -*- coding: utf-8 -*-

#
# Lambda function for generating the catalog.json file for the uW v2 API
#

from __future__ import print_function
from ts_v2_catalog_handler import TsV2CatalogHandler
from tools.file_utils import wipe_temp


def handle(event, context):
    wipe_temp(ignore_errors=True)
    try:
        catalog = TsV2CatalogHandler(event)
        return catalog.run()
    except Exception as e:
        raise Exception('Bad Request: {0}'.format(e))
