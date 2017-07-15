# -*- coding: utf-8 -*-

#
# Lambda function for generating the catalog.json file for the uW v2 API
#

from __future__ import print_function
from uw_v2_catalog_handler import UwV2CatalogHandler

def handle(event, context):
    try:
        catalog = UwV2CatalogHandler(event)
        return catalog.run()
    except Exception as e:
        raise Exception('Bad Request: {0}'.format(e))
